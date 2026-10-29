"""Lot WTF1 : mode « What the fuck », règles désactivables et surprise du chef (modules purs `wtf`)."""

from __future__ import annotations

import json
import random

import pytest

from openride_core.physics import PhysicsParams
from openride_core.wtf import chef as chef_mod
from openride_core.wtf.chef import Chef
from openride_core.wtf.events import (JUPITER_G, MOON_G, Cheese, Collapse, Ctx, Effects, Eggs, Gravity, Micro,
                                      Storm, WtfInput)
from openride_core.wtf.mode import (DRAFT_CAP, FEEL_MAX_PCT, FEEL_MIN_PCT, FEEL_OFFSET_MAX_PCT, KATA_KG_MAX,
                                    WtfMode)
from openride_core.wtf.rules import (DEFAULT_TABLE, EVENT_IDS, RULE_IDS, WtfError, WtfTable, dump_table,
                                     load_table, save_table)

DT = 0.02
FTP = 250.0
PARAMS = PhysicsParams(mass_kg=80.0)
CTX = Ctx(FTP, PARAMS)


class Rider:
    """Cycliste de test : avance à `v` constante, mesures choisies par l'appelant."""

    def __init__(self, s: float = 0.0, t: float = 0.0) -> None:
        self.s, self.t = s, t

    def inp(self, power=200.0, cadence=90.0, grade=0.0, v=8.0, ok=True) -> WtfInput:
        self.t += DT
        self.s += v * DT
        return WtfInput(self.t, DT, self.s, v, power, cadence, grade, ok)


def ride(target, rider: Rider, seconds: float, **kw) -> None:
    for _ in range(round(seconds / DT)):
        target.step(rider.inp(**kw))
        if getattr(target, "done", False):
            return


def only(*rules: str, **kw) -> WtfTable:
    return WtfTable(frozenset(rules), **kw)


# --- catalogue et fichier ---------------------------------------------------------------------

def test_catalogue_has_twelve_ideas_plus_chef():
    assert len(RULE_IDS) == 13 and len(set(RULE_IDS)) == 13
    assert "chef" in EVENT_IDS
    assert DEFAULT_TABLE.enabled == frozenset(RULE_IDS)          # tout est actif par défaut


def test_table_file_roundtrip_and_toggle(tmp_path):
    path = tmp_path / "wtf.toml"
    assert load_table(path) == DEFAULT_TABLE                      # pas de fichier : défauts
    table = DEFAULT_TABLE.with_rule("storm", False).with_rule("tiny", False)
    save_table(table, path)
    back = load_table(path)
    assert back.enabled == frozenset(RULE_IDS) - {"storm", "tiny"}
    assert not back.on("storm") and back.on("chef")
    assert [r["on"] for r in back.rules_list() if r["id"] == "storm"] == [False]
    assert "storm = false" in dump_table(back)


@pytest.mark.parametrize("text, message", [
    ("[rules]\nlicorne = true\n", "inconnues"),
    ("[rules]\nstorm = 1\n", "true ou false"),
    ("[ravito]\n", "sections inconnues"),
    ("[director]\ngap_min_s = 100\ngap_max_s = 50\n", "inférieur"),
    ("[director]\ngap_min_s = 1\n", "hors de"),
    ("[rules\n", "illisible"),
])
def test_table_file_errors(tmp_path, text, message):
    path = tmp_path / "wtf.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(WtfError, match=message):
        load_table(path)


def test_unknown_rule_toggle_refused():
    with pytest.raises(WtfError):
        DEFAULT_TABLE.with_rule("licorne", True)


# --- chef d'orchestre -------------------------------------------------------------------------

def test_director_only_draws_enabled_events_one_at_a_time():
    mode = WtfMode(only("gravity", "camera", gap_min_s=15, gap_max_s=15, first_s=5), FTP, PARAMS, seed=3)
    rider = Rider()
    seen = set()
    for _ in range(round(1200 / DT)):
        mode.step(rider.inp())
        if mode.event is not None:
            seen.add(mode.event.id)
    assert seen == {"gravity", "camera"}
    assert all(line["event"] in seen for line in mode.played)
    assert len(mode.played) >= 10


def test_all_rules_off_means_plain_ride():
    mode = WtfMode(only(), FTP, PARAMS, seed=1)
    rider = Rider()
    ride(mode, rider, 600, grade=-6.0)
    assert mode.event is None and mode.played == []
    eff = mode.effects()
    assert mode.grade(5.0, eff) == 5.0 and mode.power(300.0, eff) == 300.0
    assert mode.physics_params(PARAMS, eff) is PARAMS
    assert mode.frame(rider.t, rider.s) == {"points": 0, "event": None}


def test_same_seed_same_ride():
    def play(seed):
        mode = WtfMode(DEFAULT_TABLE, FTP, PARAMS, seed=seed)
        rider = Rider()
        rng = random.Random(0)
        for _ in range(round(1800 / DT)):
            mode.step(rider.inp(power=rng.uniform(150, 260), cadence=rng.uniform(80, 100),
                                grade=rng.choice((-5.0, 0.0, 4.0))))
        return mode.played
    assert play(7) == play(7)


def test_long_random_ride_stays_within_safety_bounds():
    """2 h de séance, toutes règles actives : pente ressentie et supplément toujours bornés."""
    mode = WtfMode(DEFAULT_TABLE, FTP, PARAMS, seed=11)
    rider = Rider()
    rng = random.Random(5)
    grade = 0.0
    for i in range(round(7200 / DT)):
        if i % 500 == 0:
            grade = rng.uniform(-10, 16)
        inp = rider.inp(power=rng.uniform(0, 600), cadence=rng.uniform(0, 130), grade=grade,
                        ok=rng.random() > 0.01)
        mode.step(inp)
        if i % 3 == 0:
            mode.press(rng.choice(("Z_SHORT", "A_SHORT", "PLUS_SHORT")))
        eff = mode.effects()
        off = mode.feel_offset(eff)
        assert -FEEL_OFFSET_MAX_PCT <= off <= FEEL_OFFSET_MAX_PCT
        assert FEEL_MIN_PCT <= mode.clamp_feel(mode.grade(grade, eff) + off) <= FEEL_MAX_PCT
        assert eff.power_factor > 0.0 and eff.mass_add_kg <= KATA_KG_MAX
        if i % 1500 == 0:
            frame = mode.frame(rider.t, rider.s)
            assert len(json.dumps(frame, ensure_ascii=False).encode()) < 1200   # place dans la trame state
    assert {line["event"] for line in mode.played} >= {"gravity", "micro", "chef", "cheese"}


def test_erg_cancels_every_effect():
    mode = WtfMode(only("gravity", "katamari", first_s=5), FTP, PARAMS, seed=2)
    rider = Rider()
    ride(mode, rider, 400)
    mode.set_erg(True)
    eff = mode.effects()
    assert eff == Effects()


def test_feel_clamp():
    assert WtfMode.clamp_feel(25.0) == FEEL_MAX_PCT and WtfMode.clamp_feel(-20.0) == FEEL_MIN_PCT
    assert WtfMode.feel_offset(Effects(feel_offset_pct=9.0)) == FEEL_OFFSET_MAX_PCT


# --- physique détraquée -----------------------------------------------------------------------

def test_gravity_moon_and_jupiter():
    rng = random.Random(0)
    planets = set()
    for _ in range(20):
        ev = Gravity(rng, CTX, Rider().inp())
        eff = Effects()
        ev.apply(eff)
        planets.add(ev.planet)
        k = MOON_G if ev.planet == "moon" else JUPITER_G
        assert WtfMode.grade(6.0, eff) == pytest.approx(6.0 * k)
        assert eff.crr_factor == pytest.approx(k)
    assert planets == {"moon", "jupiter"}


def test_moon_hops():
    rng = random.Random(0)
    while True:
        ev = Gravity(rng, CTX, Rider().inp())
        if ev.planet == "moon":
            break
    rider = Rider()
    hops = []
    for _ in range(200):
        ev.step(rider.inp(v=10.0))
        hops.append(ev.hop_m)
    assert 0.5 < max(hops) <= 3.0 and min(hops) < 0.1


def test_upside_down_turns_climbs_into_descents():
    mode = WtfMode(only("upside_down", first_s=5), FTP, PARAMS, seed=1)
    rider = Rider()
    ride(mode, rider, 6)
    assert mode.event.id == "upside_down"
    assert mode.grade(7.0, mode.effects()) == -7.0
    ride(mode, rider, 50)
    assert mode.event is None and mode.played[0]["points"] == 50


def test_collapse_strong_rider_escapes_weak_rider_falls():
    strong = Collapse(random.Random(0), CTX, Rider().inp())
    rider = Rider()
    ride(strong, rider, 70, v=12.0)
    assert strong.outcome == "escaped" and strong.points == 150
    weak = Collapse(random.Random(0), CTX, Rider().inp())
    rider = Rider()
    ride(weak, rider, 70, v=3.0)
    assert weak.outcome == "fell" and weak.points == 0


def test_cheese_starts_on_descent_and_can_squash():
    mode = WtfMode(only("cheese"), FTP, PARAMS, seed=1)
    rider = Rider()
    ride(mode, rider, 2.5, grade=-5.0)
    assert mode.event is None                         # 3 s de descente d'abord
    ride(mode, rider, 1.0, grade=-5.0)
    assert mode.event is not None and mode.event.id == "cheese"
    slow = Cheese(random.Random(0), CTX, Rider().inp(v=10.0))
    rider = Rider()
    ride(slow, rider, 80, v=6.0)
    assert slow.outcome == "caught"
    fast = Cheese(random.Random(0), CTX, Rider().inp(v=10.0))
    rider = Rider()
    ride(fast, rider, 80, v=25.0)
    assert fast.outcome == "escaped" and fast.points == 150


def test_storm_pushback_and_wind():
    ev = Storm(random.Random(0), CTX, Rider().inp())
    rider = Rider()
    ride(ev, rider, 10, power=50.0)
    assert ev.pushback_m == pytest.approx(15.0, abs=0.1)
    eff = Effects()
    ev.apply(eff)
    assert eff.wind_add_mps > 0 and eff.feel_offset_pct > 0
    ride(ev, rider, 40, power=200.0)
    assert ev.outcome == "held"


# --- micro-défis et œufs ----------------------------------------------------------------------

def _micro(kind: str) -> Micro:
    rng = random.Random(0)
    while True:
        ev = Micro(rng, CTX, Rider().inp())
        if ev.kind == kind:
            return ev


def test_micro_sprint_wins_early_and_cap_fails():
    ev = _micro("sprint")
    rider = Rider()
    ride(ev, rider, 6, power=400.0)
    assert ev.results == [True] and ev.kind != "sprint"
    ev = _micro("cap")
    rider = Rider()
    ride(ev, rider, 4, power=FTP)                     # au-dessus de 60 % de la FTP pendant 4 s
    assert ev.results == [False]


def test_micro_three_rounds_then_points():
    ev = Micro(random.Random(1), CTX, Rider().inp())
    rider = Rider()
    ride(ev, rider, 100, power=0.0, cadence=0.0)
    assert ev.done and len(ev.results) == 3
    assert ev.points == 100 * sum(ev.results)


def test_micro_steady_reference_from_first_seconds():
    ev = _micro("steady")
    rider = Rider()
    ride(ev, rider, 31, power=210.0)
    assert ev.results == [True]


def test_eggs_break_on_jerks_not_on_dropouts():
    ev = Eggs(random.Random(0), CTX, Rider().inp())
    rider = Rider()
    ride(ev, rider, 5, power=200.0)
    ride(ev, rider, 1, power=0.0, ok=False)           # coupure du trainer : rien ne casse
    ride(ev, rider, 3, power=200.0)
    assert ev.eggs == 6
    for _ in range(3):                                # trois à-coups de +150 W
        ride(ev, rider, 2, power=350.0)
        ride(ev, rider, 2, power=200.0)
    assert ev.eggs < 6
    smooth = Eggs(random.Random(0), CTX, Rider().inp())
    rider = Rider()
    ride(smooth, rider, 400, power=200.0, v=10.0)
    assert smooth.outcome == "delivered" and smooth.points == 300


# --- surprise du chef -------------------------------------------------------------------------

def _chef(dish: str) -> Chef:
    rng = random.Random(0)
    while True:
        ev = Chef(rng, CTX, Rider().inp())
        if ev.dish == dish:
            return ev


def test_chef_phases_and_refusal_makes_him_vexed():
    mode = WtfMode(only("chef", first_s=5, gap_min_s=15, gap_max_s=15), FTP, PARAMS, seed=4)
    rider = Rider()
    ride(mode, rider, 6)
    ev = mode.event
    assert ev.id == "chef" and ev.phase == "arrive"
    assert not mode.press("Z_SHORT")                  # pas encore de cloche soulevée
    assert ev.frame()["dish"] is None
    ride(mode, rider, 4.5)
    assert ev.phase == "reveal" and ev.frame()["dish"] in chef_mod.DISHES
    assert mode.press("Z_SHORT")
    ride(mode, rider, 0.1)
    assert mode.event is None and mode.played[-1]["outcome"] == "refused"
    ride(mode, rider, 16)
    assert mode.event.dish == chef_mod.SPICIEST       # le chef vexé revient avec le piment


def test_chef_dishes_effects():
    rider = Rider()
    sp = _chef("spaghetti")
    ride(sp, rider, 11)
    values = []
    for _ in range(400):
        sp.step(rider.inp())
        eff = Effects()
        sp.apply(eff)
        values.append(eff.grade_add_pct)
    assert max(values) > 1.4 and min(values) < -1.4
    chili = _chef("chili")
    rider = Rider()
    ride(chili, rider, 10)
    eff = Effects()
    chili.apply(eff)
    assert eff.power_factor == pytest.approx(1.25)
    ride(chili, rider, 30)
    eff = Effects()
    chili.apply(eff)
    assert eff.power_factor == pytest.approx(0.85) and chili.frame()["burning"]
    jelly = _chef("jelly")
    rider = Rider()
    ride(jelly, rider, 10)
    eff = Effects()
    jelly.apply(eff)
    assert eff.crr_factor == 1.5 and eff.feel_offset_pct == 1.0


def test_chef_souffle_rises_when_smooth():
    ev = _chef("souffle")
    rider = Rider()
    ride(ev, rider, 60, power=200.0)
    assert ev.outcome == "success" and ev.points == 120
    ev = _chef("souffle")
    rider = Rider()
    for _ in range(30):
        ride(ev, rider, 1, power=350.0)
        ride(ev, rider, 1, power=100.0)
    assert ev.outcome == "flop"


def test_chef_musette_points_for_cadence_in_tempo():
    ev = _chef("musette")
    rider = Rider()
    ride(ev, rider, 9.5)
    assert ev.phase == "eat" and ev.frame()["tempo_rpm"] == 80.0
    ride(ev, rider, 15, cadence=80.0)
    assert ev.points >= 28
    assert ev.tempo == 95.0


# --- règles permanentes -----------------------------------------------------------------------

def test_katamari_grows_and_weighs():
    mode = WtfMode(only("katamari"), FTP, PARAMS, seed=2)
    rider = Rider()
    ride(mode, rider, 600, v=10.0)
    assert mode.kata_count > 30 and mode.kata_size > 1.5
    eff = mode.effects()
    assert 0 < eff.mass_add_kg <= KATA_KG_MAX and 0 < eff.feel_offset_pct <= 2.0
    assert mode.physics_params(PARAMS, eff).mass_kg == pytest.approx(80.0 + eff.mass_add_kg)
    nxt = mode.frame(rider.t, rider.s)["kata"]["next"]
    assert len(nxt) == 3 and all(d > 0 for d, _ in nxt)


def test_peloton_skins_whale_draft_and_granny_attack():
    mode = WtfMode(only("peloton"), FTP, PARAMS, seed=1)
    skins = [mode.bot_skin(f"b{i}") for i in range(8)]
    assert skins[:4] == ["grandma", "tractor", "bathtub", "whale"]
    assert skins.count("whale") == 1
    assert mode.bot_skin("b3") == "whale"             # costume stable
    assert mode.draft("b3", 0.30) == pytest.approx(0.45)
    assert mode.draft("b3", 0.45) == DRAFT_CAP
    assert mode.draft("b1", 0.30) == 0.30
    rider = Rider()
    attacked = set()
    for _ in range(round(600 / DT)):
        mode.step(rider.inp())
        if mode.attack_bot:
            attacked.add(mode.attack_bot)
            assert mode.bot_power_factor(mode.attack_bot) == 1.3
    assert attacked and all(mode.skins[b] == "grandma" for b in attacked)


def test_cadence_drives_clock_and_fish():
    mode = WtfMode(only("clock"), FTP, PARAMS, seed=1)
    rider = Rider()
    ride(mode, rider, 60, cadence=90.0)
    assert mode.clock_h == pytest.approx(13.0, abs=0.01)   # 90 rpm : 3 h par minute
    assert not mode.fish
    ride(mode, rider, 1, cadence=101.0)
    assert mode.fish
    ride(mode, rider, 1, cadence=97.0)
    assert mode.fish                                    # hystérésis
    ride(mode, rider, 1, cadence=90.0)
    assert not mode.fish


def test_summary_counts_events():
    mode = WtfMode(only("camera", "tiny", first_s=5, gap_min_s=15, gap_max_s=15), FTP, PARAMS, seed=1)
    rider = Rider()
    ride(mode, rider, 600)
    summary = mode.summary()
    assert sum(summary["events"].values()) == len(mode.played) > 0
    assert summary["points"] == sum(line["points"] for line in mode.played)
    lines = mode.take_journal()
    assert lines and all(line["kind"] == "wtf" for line in lines) and mode.take_journal() == []
