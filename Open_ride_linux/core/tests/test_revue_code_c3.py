"""Revue de code, vague 2, lot C3 (piste) : constats C3-01, C3-02, C3-03, C3-04, C3-06 et C3-07 corrigés.

Chaque test échoue sur le code d'avant la correction (`main` du 23 novembre) :
- C3-01 : tours « pris » inventés dès que les premiers ont fini (vainqueur déclassé) ;
- C3-03 : un coureur qui perd un tour ne passe plus aucune ligne (jamais d'arrivée) ;
- C3-02 : omnium, les écarts d'une épreuve reportés sur la suivante (tours pris au premier pas) ;
- C3-04 : relayeur de la poursuite par équipes qui ne remonte jamais quand la séance vide le journal ;
- C3-06 : record par équipes inscrit pour un cycliste lâché ou qui n'a pas mené ;
- C3-07 : coéquipiers du cycliste toujours les bots les plus forts.
"""

from __future__ import annotations

import random
import statistics
import time
from pathlib import Path
from typing import Callable

import pytest

from openride_core import fit_export, profile, velodrome
from openride_core import track as T
from openride_core.bots import RaceHint
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.track import ME, Entrant
from openride_core.track.bot_plan import EASY_CP, TOP_LANE_M, BotPlan

LAP = 250.0
DT = 0.25


def entrants(n_bots: int) -> list[Entrant]:
    return [Entrant(ME, "Toi")] + [Entrant(f"b{i}", f"Bot {i}") for i in range(n_bots)]


def build(eid: str, settings: dict) -> T.TrackEvent:
    s = T.check(eid, settings)
    return T.make(eid, entrants(T.field_size(eid, s)), s, seed=0, clock=lambda: 0.0)


def run(ev: T.TrackEvent, speed: Callable[[str, float], float], start: dict[str, float] | None = None,
        until: float = 5_000.0, after_step: Callable[[], None] | None = None) -> list[dict]:
    """Chaque coureur à la vitesse donnée (bruit de ±1 %, graine fixe) jusqu'à la fin ; lignes du journal."""
    rng = random.Random(3)
    pos = {rid: (x, 0.0) for rid, x in (start or {rid: -1.5 * i for i, rid in enumerate(ev.riders)}).items()}
    ev.start(0.0, pos)
    t, lines = 0.0, []
    while not ev.finished and t < until:
        t += DT
        for rid, (x, _) in pos.items():
            v = max(speed(rid, t), 0.0) * (1.0 + 0.01 * rng.uniform(-1.0, 1.0))
            pos[rid] = (x + v * DT, v)
        ev.step(t, pos)
        lines += ev.take_journal()
        if after_step is not None:
            after_step()
    return lines


def events(lines: list[dict], kind: str) -> list[dict]:
    return [ln for ln in lines if ln["event"] == kind]


# --- C3-01 et C3-03 : courses en peloton avec un doublé ------------------------------------------------

SPEEDS = {ME: 13.6, "b0": 13.2, "b1": 13.1, "b2": 13.0, "b3": 12.9, "b4": 9.0}   # b4 doublé plusieurs fois


@pytest.mark.parametrize("eid", ["scratch", "points"])
def test_no_lap_gained_after_the_first_arrival_and_the_winner_stays_first(eid):
    ev = build(eid, {"opponents": 5, "laps": 20})
    lines = run(ev, lambda rid, t: SPEEDS[rid])
    assert ev.finished
    arrivals = events(lines, "arrival")
    first_t = arrivals[0]["t"]
    assert arrivals[0]["unit"] == ME
    assert not [ln for ln in events(lines, "lap_gained") if ln["t"] >= first_t]
    assert events(lines, "lap_lost")                       # b4 est bien doublé
    ranking = ev.full_ranking()
    if eid == "scratch":
        assert ranking[0] == ME                            # premier sur la ligne, premier au classement
    assert not any(u.gained for u in ev.units.values())    # personne n'a pris de tour : b4 a seulement perdu


def test_a_lapped_bot_still_crosses_the_lines_and_arrives():
    ev = build("scratch", {"opponents": 5, "laps": 20})
    run(ev, lambda rid, t: SPEEDS[rid])
    b4 = ev.units["b4"]
    assert b4.lost >= 2 and b4.finish_t is not None and "b4" in ev.finish_order
    # l'épreuve se clôt à la dernière arrivée, pas après la minute d'attente
    first = min(u.finish_t for u in ev.units.values() if u.finish_t is not None)
    assert ev.end_t - first < T.base.FINISH_GRACE_S - 1.0


def test_the_lapped_rider_keeps_counting_laps_sprints_and_arrives():
    ev = build("points", {"opponents": 3, "laps": 20})
    lines = run(ev, lambda rid, t: 9.5 if rid == ME else 13.0)
    me = ev.units[ME]
    assert me.lost >= 1 and me.finish_t is not None
    lost_t = events(lines, "lap_lost")[0]["t"]
    # après son tour perdu, le cycliste passe encore des lignes (sprints et arrivée) avec le peloton
    assert ME in ev.line_order[ev.laps]
    assert ev.frame()["finished"] and ev.frame()["laps_up"] < 0 and lost_t < me.finish_t


# --- C3-02 : omnium, chaque épreuve repart des places sur la piste ----------------------------------------

def test_omnium_sub_events_do_not_inherit_laps_from_the_previous_one():
    ev = build("omnium", {"opponents": 5})
    # b0 roule nettement moins vite : au cumul, il a plus d'un tour de retard à la fin du scratch
    lines = run(ev, lambda rid, t: 10.5 if rid == "b0" else 13.0, until=4_000.0)
    starts = events(lines, "sub_start")
    assert [s["sub"] for s in starts] == ["scratch", "tempo", "elimination", "points"]
    for s in starts[1:]:
        early = [ln for ln in lines if ln["event"] in ("lap_gained", "lap_lost") and ln.get("sub") == s["sub"]
                 and ln["t"] - s["t"] < 5.0]
        assert not early, f"{s['sub']} : tours distribués au départ {early}"


def test_omnium_regroup_keeps_each_rider_within_a_lap_of_the_lead():
    ev = T.Omnium([Entrant(i, i) for i in (ME, "a", "b", "c")])
    for r, s in zip(ev.riders.values(), (1000.0, 1010.0, 600.0, -490.0)):
        r.s = s
    off = ev._regroup()
    pos = {rid: ev.riders[rid].s - off[rid] for rid in ev.riders}
    lead = max(pos.values())
    assert lead == 1010.0 and all(lead - LAP < p <= lead for p in pos.values())
    assert all(o % LAP == 0 for o in off.values())


# --- C3-04 : relais de la poursuite par équipes, dans l'ordre d'appels de la séance -----------------------

def test_team_pursuit_relay_swings_up_even_when_the_session_takes_the_journal():
    ids = [f"b{i}" for i in range(7)]
    ev = T.make("team_pursuit", [Entrant(ME, "Toi")] + [Entrant(b, b) for b in ids], {"opponents": 1})
    home, t2 = ev.teams["home"].order, ev.teams["t2"].order
    pos = {rid: (-2.0 * k, 0.0) for k, rid in enumerate(home)}
    pos.update({rid: (125.0 - 2.0 * k, 0.0) for k, rid in enumerate(t2)})
    ev.start(0.0, pos)
    plan = BotPlan(ev, {i: "rouleur" for i in ids}, seed=1)
    lead = t2[0]
    swung = False
    for k in range(1, 40):
        plan.update()                       # avant les bots (`_track_before_bots`)
        pos = {rid: (s + 14.0 * 0.5, 14.0) for rid, (s, _) in pos.items()}
        ev.step(k * 0.5, pos)               # après les bots (`_track_after_bots`)…
        ev.take_journal()                   # … et la séance vide le journal dans l'enregistreur
        h, _, _ = plan.update()
        swung = swung or h.get(lead) == RaceHint(power_cp=EASY_CP, lane_m=TOP_LANE_M)
    assert swung and ev.relays


# --- C3-06 : pas de record par équipes sans la part du cycliste ---------------------------------------------

def _sides(ev: T.TrackEvent) -> dict[str, float]:
    return {rid: 0.0 if r.team == "home" else LAP / 2 for rid, r in ev.riders.items()}


def test_no_team_pursuit_record_for_a_dropped_rider():
    ev = build("team_pursuit", {"opponents": 1})
    run(ev, lambda rid, t: (0.0 if t > 5.0 else 8.0) if rid == ME else 15.0, start=_sides(ev), until=600.0)
    assert ev.finished and ev.riders[ME].out == "dropped"
    assert ev.team_time_s("home") is not None and ev.record() is None


def test_team_pursuit_record_kept_when_the_rider_holds_on():
    ev = build("team_pursuit", {"opponents": 1})
    run(ev, lambda rid, t: 15.0, start=_sides(ev), until=600.0)
    assert ev.finished and ev.riders[ME].out is None and ev.record() is not None


def test_no_team_sprint_record_when_the_rider_never_led_his_lap():
    ev = build("team_sprint", {"opponents": 1, "place": 1})
    run(ev, lambda rid, t: (0.0 if t > 3.0 else 5.0) if rid == ME else 16.0, start=_sides(ev), until=300.0)
    assert ev.team_time_s("home") is not None and ev.record() is None


def test_team_sprint_record_when_everyone_led_his_lap():
    ev = build("team_sprint", {"opponents": 1, "place": 1})
    run(ev, lambda rid, t: 16.0, start=_sides(ev), until=300.0)
    assert ev.record() is not None and ev.record()["id"] == "track:team_sprint"


# --- C3-07 : équipes de force égale -----------------------------------------------------------------------

def test_team_order_balances_the_teams():
    lv = [108.0, 105.3, 102.7, 100.0, 97.3, 94.7, 92.0]
    order = T.team_order(lv, 4)
    assert sorted(order) == list(range(7))
    home = [lv[i] for i in order[:3]] + [statistics.median(lv)]
    away = [lv[i] for i in order[3:]]
    assert abs(sum(home) - sum(away)) < 3.0
    assert T.team_order([0.0] * 7, 4) == list(range(7))   # niveaux égaux : ordre des bots gardé
    assert T.team_order([110.0, 100.0, 90.0], 2) == [1, 0, 2]   # américaine : coéquipier au niveau du cycliste


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    monkeypatch.setattr(time, "time", lambda: 1_790_000_000.0)
    routes = tmp_path / "routes"
    velodrome.write_velodrome(routes)
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = 6990, 6991
    s = CoreSession(cfg, driver=MockDriver(base_power_w=250.0, ramp_amplitude_w=0.0),
                    inputs=[NullProvider()], journal_dir=tmp_path / "journal", routes_root=routes,
                    workouts_dir=tmp_path / "wk", records_path=tmp_path / "records.json",
                    powerups_path=tmp_path / "powerups.toml", wtf_path=tmp_path / "wtf.toml")
    errors: list[tuple[str, str]] = []
    s.server.send_raw = lambda m, max_size=None: None
    s.server.send_error = lambda code, msg: errors.append((code, msg))
    s.server.send_input_event = lambda ev: None
    s._on_command("select_route", {"route_id": velodrome.TRACK_ID}, 1)
    return s, errors


def test_session_team_pursuit_teammates_are_not_the_strongest_bots(session):
    s, errors = session
    s._on_command("start", {"mode": "track", "track": {"event": "team_pursuit", "opponents": 1}}, 2)
    assert not errors
    ev = s.track_event
    level = {r.id: r.level for r in ev.riders.values() if r.id != ME}
    mates = [level[i] for i in ev.teams["home"].order if i != ME]
    away = [level[i] for i in ev.teams["t2"].order]
    assert len(mates) == 3 and len(away) == 4 and len(set(level.values())) > 1
    assert max(level.values()) not in mates or min(level.values()) in mates
    me = statistics.median(level.values())
    assert abs((sum(mates) + me) / 4 - sum(away) / 4) < 1.5
    # chaque bot est placé du côté de son équipe : coéquipiers derrière le cycliste, adversaires en face
    for b in s.bots:
        side = ev.riders[b.id].team
        assert (abs(b.s - s.physics.s) < 20.0) == (side == "home")
