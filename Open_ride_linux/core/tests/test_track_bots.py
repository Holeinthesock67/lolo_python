"""Lot VD7 : les bots courent les épreuves de piste (consignes `track.bot_plan`, comportements de `bot_tactics`).

Critères du cahier (`docs/lots/LOT_VD7_bots_piste.md` §4) : courses simulées de 4 et 11 bots reproductibles ;
chaque comportement du plan VD §6.1 avec son test positif et négatif ; aucun comportement ne touche à la
physique ni à la réserve W′ hors de son modèle ; `bot_tactics` n'importe pas le paquet `track/` ; pas de bots
superposés.
"""

from __future__ import annotations

import itertools
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from openride_core import bot_tactics as BT, fit_export, profile, velodrome
from openride_core import draft as draft_mod
from openride_core import track as T
from openride_core.bots import ProfileBot, RaceHint
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.rogue.wbal import wbal_step
from openride_core.session import CoreSession
from openride_core.track.base import Entrant
from openride_core.track.bot_plan import EASY_CP, POLE_LANE_M, TOP_LANE_M, BotPlan

DT = 0.05
T0_WALL = 1_790_000_000.0


# --- outils ----------------------------------------------------------------------------------------------

def bot(bid: str, name: str, mode: str = "track_full", reserve_pct: float = 100.0, seed: int = 7) -> ProfileBot:
    b = ProfileBot("rouleur", bot_id=bid, name=name)
    b.tactics.start(seed, mode)
    set_reserve(b, reserve_pct)
    return b


def set_reserve(b: ProfileBot, pct: float) -> None:
    b.wbal = replace(b.wbal, w_bal_j=b.w_prime_j * pct / 100.0)


def named(personality: str, n: int = 1) -> list[str]:
    """Noms de bots du caractère voulu (le caractère se tire du nom, `personality_of`)."""
    out = [f"Bot {i}" for i in range(200) if BT.personality_of(f"Bot {i}") == personality]
    return out[:n]


def view(order, pos, score, to_goal=None, goal="none", key=1, laps_to_go=None) -> BT.RaceView:
    return BT.RaceView(order=tuple(order), pos=pos, score=score, to_goal_m=to_goal, goal=goal, goal_key=key,
                       laps_to_go=laps_to_go)


# --- module commun --------------------------------------------------------------------------------------------

def test_bot_tactics_does_not_import_track():
    code = ("import sys; import openride_core.bot_tactics; "
            "bad = [m for m in sys.modules if m.startswith('openride_core.track')]; "
            "assert not bad, bad")
    subprocess.run([sys.executable, "-c", code], check=True, cwd=Path(__file__).resolve().parents[1])


def test_levels_and_table():
    assert BT.LEVELS == ("none", "simple", "full")
    assert BT.MODE_TACTICS[BT.track_mode("none")] == BT.NONE
    simple, full = BT.MODE_TACTICS[BT.track_mode("simple")], BT.MODE_TACTICS[BT.track_mode("full")]
    assert simple.marking and simple.standings and simple.fatigue and not simple.coalitions and not simple.bluff
    assert full.coalitions and full.marking and full.bluff and full.standings and full.fatigue
    assert not full.attacks                         # pas d'attaque de montée sur une piste plate
    paced = BT.MODE_TACTICS[BT.track_mode("full", paced=True)]
    assert paced.fatigue and not (paced.coalitions or paced.bluff or paced.relays or paced.marking)
    assert BT.track_mode("none", paced=True) == "track_none"
    with pytest.raises(ValueError):
        BT.track_mode("rusée")
    # les autres modes gardent leur réglage : aucun comportement de course hors piste
    for mode in ("none", "classic", "essai", "calibration"):
        assert not BT.MODE_TACTICS[mode].racing


def test_personality_is_stable_from_race_to_race():
    a = Tactics_of("Grimpeur 2", seed=1)
    b = Tactics_of("Grimpeur 2", seed=999)
    assert a.personality == b.personality == BT.personality_of("Grimpeur 2")
    kinds = {BT.personality_of(n) for n in ("Grimpeur", "Rouleur", "Sprinteur", "Diesel", "Grimpeur 2",
                                             "Rouleur 2", "Sprinteur 2", "Diesel 2", "Grimpeur 3", "Rouleur 3")}
    assert kinds == set(BT.PERSONALITIES)          # les trois caractères dans un peloton de 11


def Tactics_of(name: str, seed: int) -> BT.Tactics:
    b = ProfileBot("climber", bot_id="b9", name=name)
    b.tactics.start(seed, "track_full")
    return b.tactics


# coalitions

def test_coalition_forms_far_from_goal_and_breaks_before_the_sprint():
    names = named("attacker", 3)
    bots = [bot(f"b{i}", n) for i, n in enumerate(names)]
    pos = {"me": (100.0, 12.0), "b0": (99.0, 12.0), "b1": (97.5, 12.0), "b2": (96.0, 12.0)}
    f = BT.RaceField(seed=3)
    order = ["me", "b0", "b1", "b2"]
    for _ in range(10):
        BT.race_update(f, bots, view(order, pos, {k: 0 for k in order}, to_goal=2000.0, goal="finish"), 0.5)
    assert f.coalition and len(f.coalition) in (2, 3) and f.counts["coalition"] == 1
    member = next(b for b in bots if b.id in f.coalition)
    p, leave, lane = member.tactics.race_power(member, 0.95 * member.cp_w, False, f.t)
    assert p == pytest.approx(BT.COALITION_FACTOR * member.cp_w) and not leave and lane is None
    BT.race_update(f, bots, view(order, pos, {k: 0 for k in order}, to_goal=300.0, goal="finish"), 0.5)
    assert f.coalition == () and all(b.tactics.race.coalition == () for b in bots)   # redeviennent rivaux


def test_no_coalition_near_goal_low_reserve_or_simple_level():
    names = named("attacker", 3)
    order = ["b0", "b1", "b2"]
    pos = {"b0": (99.0, 12.0), "b1": (97.5, 12.0), "b2": (96.0, 12.0)}
    for bots, goal in (([bot(f"b{i}", n) for i, n in enumerate(names)], 200.0),
                       ([bot(f"b{i}", n, reserve_pct=40.0) for i, n in enumerate(names)], 2000.0),
                       ([bot(f"b{i}", n, mode="track_simple") for i, n in enumerate(names)], 2000.0)):
        f = BT.RaceField(seed=3)
        for _ in range(10):
            BT.race_update(f, bots, view(order, pos, {k: 0 for k in order}, to_goal=goal, goal="finish"), 0.5)
        assert f.coalition == () and f.counts["coalition"] == 0


def test_coalition_takes_a_lap():
    """Scratch de 60 tours : deux attaquants unis à 1,12 × CP prennent un tour au peloton qui roule à 0,95 × CP
    (vitesse ∝ puissance^1/3, sans abri : seul le comportement change)."""
    names = named("attacker", 2) + named("follower", 2)
    ids = ["b0", "b1", "b2", "b3"]
    bots = {bid: bot(bid, n) for bid, n in zip(ids, names)}
    for bid in ("b2", "b3"):        # le peloton : comportements de course coupés
        bots[bid].tactics.start(7, "track_none")
    ev = T.Scratch([Entrant("me", "Toi")] + [Entrant(b, b) for b in ids], laps=60)
    pos = {"me": (0.0, 10.0), "b0": (-2.0, 10.0), "b1": (-3.5, 10.0), "b2": (-5.0, 10.0), "b3": (-6.5, 10.0)}
    ev.start(0.0, pos)
    f = BT.RaceField(seed=11)
    t, dt = 0.0, 0.5
    while t < 1500 and not (ev.units["b0"].gained and ev.units["b1"].gained):
        order = sorted(pos, key=lambda k: -pos[k][0])
        BT.race_update(f, list(bots.values()), view(order, pos, {k: 0 for k in order}, to_goal=60 * 250.0,
                                                    goal="finish", laps_to_go=60), dt)
        for bid, b in bots.items():
            p, _, _ = b.tactics.race_power(b, 0.95 * b.cp_w, False, f.t)
            v = 10.0 * (p / (0.95 * b.cp_w)) ** (1 / 3)
            pos[bid] = (pos[bid][0] + v * dt, v)
        pos["me"] = (pos["me"][0] + 10.0 * dt, 10.0)
        t += dt
        ev.step(t, pos)
    assert f.counts["coalition"] >= 1
    assert ev.units["b0"].gained >= 1 and ev.units["b1"].gained >= 1      # tour pris par la coalition
    assert ev.units["b2"].gained == 0 and ev.units["b3"].gained == 0


# marquage

def test_marking_follows_the_most_dangerous_and_lets_him_go_far_away():
    b = bot("b1", named("follower")[0])
    f = BT.RaceField(seed=5)
    score = {"me": 12, "b1": 3, "b2": 0}
    pos = {"me": (110.0, 12.0), "b1": (100.0, 12.0), "b2": (90.0, 12.0)}   # le leader au classement à 0,8 s devant
    BT.race_update(f, [b], view(["me", "b1", "b2"], pos, score, to_goal=2000.0), 0.5)
    assert b.tactics.race.mark == "me"
    p, leave, _ = b.tactics.race_power(b, 0.9 * b.cp_w, False, f.t, view(["me", "b1", "b2"], pos, score))
    assert p == pytest.approx(BT.MARK_FACTOR * b.cp_w) and leave       # il revient sur sa roue
    close = {"me": (105.0, 12.0), "b1": (100.0, 12.0), "b2": (90.0, 12.0)}   # 0,4 s : dans sa roue
    p, leave, _ = b.tactics.race_power(b, 0.9 * b.cp_w, False, f.t, view(["me", "b1", "b2"], close, score))
    assert p == pytest.approx(0.9 * b.cp_w) and not leave
    far = {"me": (200.0, 12.0), "b1": (100.0, 12.0), "b2": (90.0, 12.0)}     # 8 s : on le laisse partir
    BT.race_update(f, [b], view(["me", "b1", "b2"], far, score, to_goal=2000.0), 0.5)
    assert b.tactics.race.mark is None


def test_no_marking_without_the_behaviour_or_far_from_the_leader():
    b = bot("b1", named("follower")[0], mode="track_none")
    f = BT.RaceField(seed=5)
    pos = {"me": (110.0, 12.0), "b1": (100.0, 12.0)}
    BT.race_update(f, [b], view(["me", "b1"], pos, {"me": 12, "b1": 3}, to_goal=2000.0), 0.5)
    assert b.tactics.race.mark is None
    b = bot("b1", named("follower")[0])
    far = {"me": (200.0, 12.0), "b1": (100.0, 12.0)}
    BT.race_update(f, [b], view(["me", "b1"], far, {"me": 12, "b1": 3}, to_goal=2000.0), 0.5)
    assert b.tactics.race.mark is None and f.counts["mark"] == 0


# bluff

def _bluffer(seed_range=range(200)):
    """(bot, graine) d'un attaquant qui bluffe à l'objectif 1 (la chance se tire de la graine)."""
    name = named("attacker")[0]
    for seed in seed_range:
        if BT.draw(seed, "b1", "bluff", 1) < BT.RATES["attacker"]["bluff"]:
            return bot("b1", name, seed=seed), seed
    raise AssertionError("aucune graine")


def test_bluff_then_sit_up():
    b, seed = _bluffer()
    f = BT.RaceField(seed=seed)
    pos = {"b1": (100.0, 12.0), "me": (99.0, 12.0)}
    v = view(["b1", "me"], pos, {"b1": 0, "me": 0}, to_goal=400.0, goal="sprint", key=1)
    BT.race_update(f, [b], v, 0.1)
    it = b.tactics.race
    assert BT.BLUFF_S[0] <= it.bluff_until - f.t <= BT.BLUFF_S[1]
    p, leave, _ = b.tactics.race_power(b, b.cp_w, False, f.t)
    assert p == pytest.approx(BT.BLUFF_FACTOR * b.cp_w) and leave           # fausse attaque
    p, leave, _ = b.tactics.race_power(b, b.cp_w, False, it.bluff_until + 1.0)
    assert p == pytest.approx(BT.SIT_UP_FACTOR * b.cp_w) and not leave      # il se relève
    p, _, _ = b.tactics.race_power(b, b.cp_w, False, it.sit_up_until + 0.1)
    assert p == pytest.approx(b.cp_w)
    BT.race_update(f, [b], v, 0.1)                                            # une fois par objectif
    assert f.counts["bluff"] == 1


def test_no_bluff_out_of_window_or_low_reserve():
    b, seed = _bluffer()
    f = BT.RaceField(seed=seed)
    pos = {"b1": (100.0, 12.0)}
    BT.race_update(f, [b], view(["b1"], pos, {"b1": 0}, to_goal=900.0, goal="sprint", key=1), 0.1)
    assert f.counts["bluff"] == 0
    set_reserve(b, 30)
    BT.race_update(f, [b], view(["b1"], pos, {"b1": 0}, to_goal=400.0, goal="sprint", key=1), 0.1)
    assert f.counts["bluff"] == 0 and b.tactics.race.bluff_until < 0


# gestion du classement

def test_leader_watches_and_the_others_go_all_in_at_the_end():
    lead = bot("b1", named("follower")[0])
    chaser_name = next(n for n in named("attacker", 40) if BT.draw(9, "b2", "tout") < BT.RATES["attacker"]["all_in"])
    chaser = bot("b2", chaser_name, seed=9)
    f = BT.RaceField(seed=9)
    pos = {"b1": (100.0, 12.0), "b2": (98.0, 12.0)}
    v = view(["b1", "b2"], pos, {"b1": 20, "b2": 11}, to_goal=500.0, goal="finish", laps_to_go=2)
    BT.race_update(f, [lead, chaser], v, 0.5)
    assert lead.tactics.race.watch and lead.tactics.race.mark == "b2"      # il surveille son dauphin
    p, _, _ = lead.tactics.race_power(lead, lead.cp_w, False, f.t, v)
    assert p == pytest.approx(BT.WATCH_CAP * lead.cp_w)
    assert chaser.tactics.race.all_in
    p, leave, _ = chaser.tactics.race_power(chaser, chaser.cp_w, False, f.t, v)
    assert p == pytest.approx(BT.ALL_IN_FACTOR * chaser.cp_w) and leave
    set_reserve(chaser, 10)                           # vide : il arrête
    BT.race_update(f, [lead, chaser], v, 0.5)
    assert not chaser.tactics.race.all_in


def test_no_standings_management_before_the_last_laps():
    lead, other = bot("b1", named("follower")[0]), bot("b2", named("attacker")[0])
    f = BT.RaceField(seed=9)
    v = view(["b1", "b2"], {"b1": (100.0, 12.0), "b2": (98.0, 12.0)}, {"b1": 20, "b2": 11}, to_goal=500.0,
             laps_to_go=8)
    BT.race_update(f, [lead, other], v, 0.5)
    assert not lead.tactics.race.watch and not other.tactics.race.all_in and f.counts["all_in"] == 0


# fatigue visible

def test_empty_bot_sits_up_drops_and_climbs_the_track():
    b = bot("b1", "Rouleur", reserve_pct=5.0)
    f = BT.RaceField()
    v = view(["b1"], {"b1": (100.0, 12.0)}, {"b1": 0}, to_goal=2000.0)
    BT.race_update(f, [b], v, 0.5)
    assert b.tactics.race.tired
    p, leave, lane = b.tactics.race_power(b, 1.2 * b.cp_w, True, f.t)
    assert p == pytest.approx(BT.TIRED_CAP * b.cp_w) and not leave and lane == BT.TIRED_LANE_M
    set_reserve(b, 20)
    BT.race_update(f, [b], v, 0.5)
    assert b.tactics.race.tired                                             # pas encore remis (25 %)
    set_reserve(b, 30)
    BT.race_update(f, [b], v, 0.5)
    assert not b.tactics.race.tired


def test_no_visible_fatigue_without_the_behaviour_or_with_reserve():
    b = bot("b1", "Rouleur", mode="track_none", reserve_pct=5.0)
    f = BT.RaceField()
    BT.race_update(f, [b], view(["b1"], {"b1": (100.0, 12.0)}, {"b1": 0}), 0.5)
    assert not b.tactics.race.tired and b.tactics.race_power(b, 300.0, True, f.t) == (300.0, True, None)
    b = bot("b1", "Rouleur", reserve_pct=50.0)
    BT.race_update(f, [b], view(["b1"], {"b1": (100.0, 12.0)}, {"b1": 0}), 0.5)
    assert not b.tactics.race.tired


# physique et réserve inchangées

def test_behaviours_touch_neither_physics_nor_the_wprime_model():
    b = bot("b1", named("attacker")[0], reserve_pct=60.0)
    before = asdict(b.params)
    b.tactics.race.all_in = True
    b.race_view = None
    for _ in range(200):
        prev = b.wbal
        b.step(0.05)
        expect = wbal_step(prev, b.power_w, 0.0, 0.05, cp_w=b.cp_w, w_prime_j=b.w_prime_j)
        assert b.wbal.w_bal_j == pytest.approx(expect.w_bal_j)
    assert asdict(b.params) == before
    assert b.power_w == pytest.approx(BT.ALL_IN_FACTOR * b.cp_w)


# --- consignes des épreuves ------------------------------------------------------------------------------------

def plan_for(ev, ids):
    return BotPlan(ev, {i: "rouleur" for i in ids}, seed=1)


def test_keirin_riders_never_pass_the_pacer():
    ids = [f"b{i}" for i in range(4)]
    ev = T.Keirin([Entrant("me", "Toi")] + [Entrant(b, b) for b in ids], laps=6)
    pos = {"me": (-3.0, 0.0), **{b: (-3.0 - 2.7 * (i + 1), 0.0) for i, b in enumerate(ids)}}
    ev.start(0.0, pos)
    hints, _, _ = plan_for(ev, ids).update()
    pacer_s = ev.origin + ev.pacer_d
    for b in ids:
        assert hints[b].wheel is not None and hints[b].wheel[0] == pytest.approx(pacer_s - pos[b][0] - draft_mod.BIKE_LENGTH_M)
        assert hints[b].wheel[1] == pytest.approx(ev.pacer_v)


def test_pursuit_bot_holds_a_constant_pace_at_the_pole():
    ev = T.Pursuit([Entrant("me", "Toi"), Entrant("b1", "Bot")], distance_m=3000.0)
    ev.start(0.0, {"me": (0.0, 0.0), "b1": (125.0, 0.0)})
    plan = plan_for(ev, ["b1"])
    h, _, _ = plan.update()
    assert h["b1"].power_cp > 1.0 and h["b1"].lane_m == POLE_LANE_M       # départ arrêté
    ev.step(30.0, {"me": (400.0, 14.0), "b1": (525.0, 14.0)})
    h, _, _ = plan.update()
    assert h["b1"] == RaceHint(power_cp=1.0, tactical=True, lane_m=POLE_LANE_M)


def test_team_pursuit_lead_relays_and_swings_up():
    ids = [f"b{i}" for i in range(7)]
    ev = T.make("team_pursuit", [Entrant("me", "Toi")] + [Entrant(b, b) for b in ids], {"opponents": 1})
    home = ev.teams["home"].order
    pos = {rid: (-2.0 * k, 0.0) for k, rid in enumerate(home)}
    pos.update({rid: (125.0 - 2.0 * k, 0.0) for k, rid in enumerate(ev.teams["t2"].order)})
    ev.start(0.0, pos)
    plan = plan_for(ev, ids)
    lead = ev.teams["t2"].order[0]
    h, _, _ = plan.update()
    assert h[lead].tactical and h[lead].power_cp >= 1.1
    for k in range(1, 30):   # l'équipe roule un demi-tour : relais
        pos = {rid: (s + 14.0 * 0.5, 14.0) for rid, (s, _) in pos.items()}
        ev.step(k * 0.5, pos)
    assert ev.teams["t2"].order[0] != lead
    h, _, _ = plan.update()
    assert h[lead] == RaceHint(power_cp=EASY_CP, lane_m=TOP_LANE_M)        # il remonte
    assert h[ev.teams["t2"].order[0]].tactical


def test_madison_resting_bot_waits_at_the_top_and_relay_gives_the_speed():
    s, run = _session(6950)
    s._on_command("start", {"mode": "track", "track": {"event": "madison", "opponents": 3, "laps": 20}}, 2)
    ev = s.track_event
    run(s, 20.0)
    resting = [m for u in ev.units.values() for m in u.members if m != ev.racer(u.id) and m != "me"]
    assert resting and all(s._find_bot(r).hint == RaceHint(power_cp=EASY_CP, lane_m=TOP_LANE_M) for r in resting)
    tid = next(u for u in ev.units if u != "home")
    to = ev.units[tid].members[1 - ev.active[tid]]
    s._find_bot(to).physics.v = 3.0
    s._track_relay({"event": "relay", "team": tid, "rider": ev.racer(tid), "to": to, "v": 15.0})
    assert s._find_bot(to).physics.v == 15.0                                 # lancer simulé
    s._mp.undo()


def test_points_bots_sprint_near_the_sprint_line_only():
    ids = [f"b{i}" for i in range(4)]
    ev = T.Points([Entrant("me", "Toi")] + [Entrant(b, b) for b in ids], laps=20)
    pos = {"me": (0.0, 12.0), **{b: (-2.0 * (i + 1), 12.0) for i, b in enumerate(ids)}}
    ev.start(0.0, pos)
    plan = plan_for(ev, ids)
    h, v, _ = plan.update()
    assert all(h[b] is None for b in ids) and v.goal == "sprint" and v.to_goal_m == pytest.approx(10 * 250.0)
    near = {k: (s + 9 * 250.0 + 150.0, 12.0) for k, (s, _) in pos.items()}
    ev.step(200.0, near)
    h, v, _ = plan.update()
    assert all(h[b] is not None and h[b].peak and h[b].tactical for b in ids)
    plan.set_reserves({b: 30.0 for b in ids})                                # sprint intermédiaire : réserve gardée
    h, _, _ = plan.update()
    assert all(h[b] is None for b in ids)


def test_elimination_uses_the_survivor_hints():
    s, run = _session(6960)
    s._on_command("start", {"mode": "track", "track": {"event": "elimination", "opponents": 4}}, 2)
    run(s, 10.0)
    assert any(b.survival is not None for b in s.bots)
    s._mp.undo()


# --- courses simulées ---------------------------------------------------------------------------------------

def _session(port: int, power_w: float = 330.0):
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    wall = [T0_WALL]
    mp = pytest.MonkeyPatch()
    mp.setattr(fit_export, "ACTIVITIES_DIR", tmp / "act")
    mp.setattr(profile, "PROFILE_PATH", tmp / "profile.json")
    mp.setattr(time, "time", lambda: wall[0])
    routes = tmp / "routes"
    velodrome.write_velodrome(routes)
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    cfg.render.living = False
    cfg.depart.mode = "immediat"
    s = CoreSession(cfg, driver=MockDriver(base_power_w=power_w, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                    journal_dir=tmp / "journal", routes_root=routes, workouts_dir=tmp / "wk",
                    records_path=tmp / "records.json", powerups_path=tmp / "pu.toml", wtf_path=tmp / "wtf.toml")
    s.server.send_raw = lambda m, max_size=None: None
    s.server.send_error = lambda code, msg: (_ for _ in ()).throw(AssertionError((code, msg)))
    s.server.send_input_event = lambda ev: None
    s.bot_tactics_seed = 42
    s._on_command("select_route", {"route_id": velodrome.TRACK_ID}, 1)
    s._find_bot = lambda bid: next(b for b in s.bots if b.id == bid)

    def run(sess, seconds, each=None):
        for i in range(int(round(seconds / DT))):
            if sess.state.session_state != "RUNNING":
                return
            wall[0] += DT
            sess._step(DT, wall[0])
            if each and i % 4 == 0:
                each(sess)

    s._mp = mp
    return s, run


def _race(port: int, opponents: int) -> tuple[list[str], list[tuple], int, float]:
    s, run = _session(port)
    s._on_command("start", {"mode": "track", "track": {"event": "scratch", "opponents": opponents, "laps": 10}}, 2)
    ev, field = s.track_event, s._race_field
    closest = [9e9]

    def each(sess):
        racing = [b for b in sess.bots if ev.riders[b.id].out is None]
        for a, b in itertools.combinations(racing, 2):
            if abs(a.lane.m - b.lane.m) < draft_mod.RIDER_WIDTH_M:
                closest[0] = min(closest[0], abs(a.s - b.s))

    run(s, 400.0, each)
    s._mp.undo()
    assert ev.finished
    track = [(b.id, round(b.s, 3), round(b.lane.m, 3)) for b in s.bots]
    return ev._ranking(), track, sum(field.counts.values()), closest[0]


@pytest.mark.parametrize("opponents", [4, 11])
def test_simulated_races_are_reproducible_and_never_stack_bots(opponents):
    r1, t1, n1, close1 = _race(6900 + opponents * 4, opponents)
    r2, t2, n2, _ = _race(6902 + opponents * 4, opponents)
    assert r1 == r2 and t1 == t2 and n1 == n2                             # même graine, même course
    assert len(r1) == opponents + 1 and n1 > 0                            # les comportements ont joué
    assert close1 >= 0.5 * draft_mod.BIKE_LENGTH_M                        # jamais deux bots à la même place
