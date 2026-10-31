"""Lot DS1 : règles du mode « Dernier survivant » (module pur `survivor`)."""

from __future__ import annotations

import json
import random

import pytest

from openride_core.bots import ConstantPowerBot
from openride_core.segments import Segment
from openride_core.survivor import (FIRST_ARCH_MIN_M, ME, SNAP_M, TIE_S, SurvivorError, SurvivorRace,
                                    arch_positions, check_settings, course_length_m, fits, plan_field)

DT = 0.02


def seg(kind: str, s0: float, s1: float, sid: str = "s1") -> Segment:
    return Segment(sid, sid, kind, s0, s1, s1 - s0, 0.0, 0.0, None if kind == "sprint" else "4", "auto")


def race(n: int = 4, spacing_km: float = 1.0) -> SurvivorRace:
    arches = arch_positions(n, spacing_km)
    bots = [(f"bot{i + 1}", f"Bot {i + 1}", 100.0 - i) for i in range(n)]
    return SurvivorRace(arches, bots, spacing_km)


def run(r: SurvivorRace, speeds: dict[str, float], until_s: float = 1e9, t: float = 0.0,
        pos: dict[str, float] | None = None) -> tuple[float, dict[str, float]]:
    """Fait rouler chaque coureur à vitesse constante jusqu'à la fin de la course."""
    pos = dict(pos or {rid: 0.0 for rid in speeds})
    if t == 0.0:
        r.start(0.0, {rid: (s, speeds[rid]) for rid, s in pos.items()})
    while not r.finished and t < until_s:
        t += DT
        for rid in pos:
            pos[rid] += speeds[rid] * DT
        r.step(t, {rid: (s, speeds[rid]) for rid, s in pos.items()})
    return t, pos


# --- réglages et arches -----------------------------------------------------------------------

def test_settings_accepted_and_refused() -> None:
    check_settings(4, 2, "normal", "ride")
    check_settings(11, 3, "wide", "end")
    for bad in [(1, 2, "normal", "ride"), (12, 2, "normal", "ride"), (True, 2, "normal", "ride"),
                (4, 5, "normal", "ride"), (4, 2, "énorme", "ride"), (4, 2, "normal", "quit")]:
        with pytest.raises(SurvivorError):
            check_settings(*bad)
    with pytest.raises(SurvivorError):
        check_settings(5, 2, "normal", "ride", max_opponents=4)


def test_one_arch_per_opponent_evenly_spaced() -> None:
    assert course_length_m(4, 2) == 8000.0
    assert arch_positions(4, 2) == [2000.0, 4000.0, 6000.0, 8000.0]
    assert arch_positions(3, 1, s0=500.0) == [1500.0, 2500.0, 3500.0]


def test_route_too_short_refused_except_loop_and_open_world() -> None:
    assert fits(4, 2, 8000.0, False)
    assert not fits(4, 2, 7999.0, False)
    assert not fits(4, 2, 8500.0, False, s0=600.0)
    assert fits(4, 2, 3000.0, True)
    assert fits(11, 3, None, False)
    with pytest.raises(SurvivorError, match="trop court"):
        arch_positions(4, 2, length_m=5000.0)
    # circuit de 3 km : la distance continue au tour suivant
    assert arch_positions(4, 2, length_m=3000.0, loop=True) == [2000.0, 4000.0, 6000.0, 8000.0]


def test_arch_snaps_to_sprint_line_or_summit() -> None:
    segs = [seg("sprint", 1600.0, 1850.0, "sp"), seg("climb", 3000.0, 4200.0, "c1")]
    assert arch_positions(3, 2, segments=segs, length_m=10_000.0) == [1850.0, 4200.0, 6000.0]
    # trop loin (plus de 300 m) : pas de calage
    far = [seg("sprint", 1400.0, 2000.0 + SNAP_M + 1.0)]
    assert arch_positions(2, 2, segments=far, length_m=10_000.0) == [2000.0, 4000.0]


def test_arch_never_snaps_into_first_kilometre_or_past_route_end() -> None:
    early = [seg("sprint", 600.0, 900.0)]
    assert arch_positions(2, 1, segments=early, length_m=5000.0)[0] == 1000.0
    assert 1000.0 >= FIRST_ARCH_MIN_M
    late = [seg("climb", 3000.0, 4200.0)]
    assert arch_positions(2, 2, segments=late, length_m=4000.0) == [2000.0, 4000.0]


def test_arch_snaps_on_every_lap_of_a_circuit() -> None:
    segs = [seg("sprint", 2500.0, 2800.0)]
    # tour de 3 km : ligne à 2800 puis 5800 ; arches nominales 3000 et 6000
    assert arch_positions(2, 3, segments=segs, length_m=3000.0, loop=True) == [2800.0, 5800.0]


def test_plan_field_profiles_and_levels() -> None:
    field = plan_field(4, 100.0, "normal")
    assert [p for p, _ in field] == ["climber", "rouleur", "sprinter", "diesel"]
    levels = [lv for _, lv in field]
    assert levels[0] == 108.0 and levels[-1] == 92.0 and levels == sorted(levels, reverse=True)
    assert [p for p, _ in plan_field(6, 100.0, "tight")][4:] == ["climber", "rouleur"]
    assert plan_field(2, 145.0, "wide") == [("climber", 150.0), ("rouleur", 130.0)]
    with pytest.raises(SurvivorError):
        plan_field(4, 100.0, "énorme")


# --- éliminations -----------------------------------------------------------------------------

def test_slowest_is_eliminated_at_each_arch_and_places_are_unique() -> None:
    r = race(4)
    speeds = {ME: 10.0, "bot1": 11.0, "bot2": 9.0, "bot3": 8.0, "bot4": 7.0}
    run(r, speeds)
    order = [line[1] for line in r.summary()["eliminated"]]
    assert order == ["bot4", "bot3", "bot2", ME]
    assert r.winner == "bot1"
    places = sorted(rc.place for rc in r.racers.values())
    assert places == [1, 2, 3, 4, 5]
    assert r.racers[ME].place == 2 and r.racers["bot4"].place == 5


def test_last_rider_eliminated_at_once_even_far_behind() -> None:
    r = race(2)
    speeds = {ME: 10.0, "bot1": 10.0, "bot2": 1.0}   # bot2 loin derrière
    pos = {ME: 0.0, "bot1": 0.0, "bot2": 0.0}
    r.start(0.0, {k: (v, speeds[k]) for k, v in pos.items()})
    t = 0.0
    gone: list[str] = []
    while not gone:
        t += DT
        for k in pos:
            pos[k] += speeds[k] * DT
        gone = r.step(t, {k: (v, speeds[k]) for k, v in pos.items()})
    assert gone == ["bot2"]
    assert pos["bot2"] < 200.0                      # éliminé sans avoir atteint l'arche
    assert r.racers["bot2"].gap_s > 80.0


def test_eliminated_rider_does_not_count_anymore() -> None:
    r = race(2)
    speeds = {ME: 10.0, "bot1": 9.0, "bot2": 5.0}
    run(r, speeds, until_s=150.0)
    assert r.is_out("bot2") and r.alive == [ME, "bot1"]
    # bot2 continue à rouler : ses passages ne changent plus rien
    t, pos = 150.0, {ME: 1500.0, "bot1": 1350.0, "bot2": 750.0}
    r._prev.update({k: (t, s) for k, s in pos.items()})
    speeds["bot2"] = 50.0
    run(r, speeds, t=t, pos=pos)
    assert r.winner == ME and r.racers["bot2"].place == 3


def test_leader_crossing_next_arch_before_current_one_is_decided() -> None:
    r = race(3, spacing_km=1.0)
    speeds = {ME: 20.0, "bot1": 3.0, "bot2": 2.9, "bot3": 2.8}
    run(r, speeds)
    assert [line[1] for line in r.summary()["eliminated"]] == ["bot3", "bot2", "bot1"]
    assert r.winner == ME and r.racers[ME].place == 1


def test_tie_bot_eliminated_before_rider() -> None:
    r = race(2)
    speeds = {ME: 10.0, "bot1": 10.0, "bot2": 15.0}
    run(r, speeds, until_s=110.0)
    assert r.racers["bot1"].out_arch == 1 and not r.is_out(ME)


def test_tie_between_bots_lowest_level_then_largest_id() -> None:
    arches = arch_positions(2, 1)
    r = SurvivorRace(arches, [("bot1", "A", 100.0), ("bot2", "B", 95.0)], 1)
    run(r, {ME: 20.0, "bot1": 10.0, "bot2": 10.0}, until_s=150.0)
    assert r.racers["bot2"].out_arch == 1
    r = SurvivorRace(arches, [("bot1", "A", 100.0), ("bot2", "B", 100.0)], 1)
    run(r, {ME: 20.0, "bot1": 10.0, "bot2": 10.0}, until_s=150.0)
    assert r.racers["bot2"].out_arch == 1


def test_near_tie_waits_one_step_then_is_decided_by_crossing_time() -> None:
    r = race(2)
    r.start(0.0, {ME: (999.0, 10.0), "bot1": (900.0, 10.0), "bot2": (999.0, 10.0)})
    # bot2 passe au pas 1 ; le cycliste est à 0,5 mm de l'arche : égalité possible, on attend
    gone = r.step(DT, {ME: (999.9995, 10.0), "bot1": (900.2, 10.0), "bot2": (1000.2, 10.0)})
    assert gone == []
    r.step(2 * DT, {ME: (1000.2, 10.0), "bot1": (900.4, 10.0), "bot2": (1000.4, 10.0)})
    assert not r.is_out(ME)


def test_interpolated_crossing_time() -> None:
    r = race(2)
    r.start(0.0, {ME: (990.0, 10.0), "bot1": (0.0, 1.0), "bot2": (0.0, 1.0)})
    r.step(2.0, {ME: (1010.0, 10.0), "bot1": (2.0, 1.0), "bot2": (2.0, 1.0)})
    assert r.crossings[0][ME] == pytest.approx(1.0)


def test_no_step_means_no_elimination_during_pause() -> None:
    r = race(2)
    r.start(0.0, {ME: (0.0, 10.0), "bot1": (0.0, 10.0), "bot2": (0.0, 1.0)})
    r.step(1.0, {ME: (900.0, 10.0), "bot1": (900.0, 10.0), "bot2": (5.0, 1.0)})
    # pause de 10 min : la séance n'appelle pas step ; à la reprise les positions n'ont pas bougé
    assert r.step(601.0, {ME: (900.0, 0.0), "bot1": (900.0, 0.0), "bot2": (5.0, 0.0)}) == []
    assert r.alive == [ME, "bot1", "bot2"]


# --- messages, trame, journal, bilan -------------------------------------------------------------

def test_elimination_message_sent_three_times() -> None:
    r = race(2)
    run(r, {ME: 10.0, "bot1": 9.0, "bot2": 5.0}, until_s=150.0)
    t = 150.0
    sent = []
    for i in range(5):
        sent += r.due_results(t + i)
    first = [m for m in sent if m["rider"] == "bot2"]
    assert len(first) == 3
    m = first[0]
    assert m == {"type": "elimination", "v": 1, "arch": 1, "rider": "bot2", "name": "Bot 2", "place": 3,
                 "gap_s": m["gap_s"], "alive": 2}
    assert r.due_results(t + 10) == []


def test_frame_shape_and_gaps() -> None:
    r = race(4, spacing_km=2.0)
    r.start(0.0, {ME: (0.0, 10.0), "bot1": (0.0, 10.0), "bot2": (0.0, 10.0), "bot3": (0.0, 10.0),
                  "bot4": (0.0, 10.0)})
    r.step(1.0, {ME: (1350.0, 10.0), "bot1": (1400.0, 10.0), "bot2": (1300.0, 10.0),
                 "bot3": (1330.0, 10.0), "bot4": (1326.0, 8.0)})
    f = r.frame()
    assert f["arch"] == 1 and f["arches"] == 4 and f["d_m"] == 650.0
    assert f["alive"] == ["bot1", ME, "bot3", "bot4", "bot2"] and f["last"] == "bot2"
    assert f["gap_last_s"] == 5.0 and f["out"] == [] and f["me_out"] is None and f["winner"] is None
    # cycliste dernier : écart avec celui qui le précède, à sa propre vitesse
    r.step(2.0, {ME: (1300.0, 10.0), "bot1": (1400.0, 10.0), "bot2": (1350.0, 10.0),
                 "bot3": (1330.0, 10.0), "bot4": (1326.0, 8.0)})
    f = r.frame()
    assert f["last"] == ME and f["gap_last_s"] == 2.6


def test_frame_after_rider_out_and_winner() -> None:
    r = race(4)
    run(r, {ME: 10.0, "bot1": 11.0, "bot2": 9.0, "bot3": 8.0, "bot4": 7.0})
    f = r.frame()
    assert f["me_out"] == 4 and f["d_m"] is None and f["winner"] == "bot1" and f["alive"] == ["bot1"]
    assert f["out"] == [["bot4", 1], ["bot3", 2], ["bot2", 3]]
    s = r.summary()
    assert s["place"] == 2 and s["of"] == 5 and s["arches"] == 4 and s["winner"] == "bot1"
    lines = r.take_journal()
    assert [ln["rider"] for ln in lines] == ["bot4", "bot3", "bot2", ME, "bot1"]
    assert lines[-1]["place"] == 1 and r.take_journal() == []


def test_bad_race_definition_refused() -> None:
    with pytest.raises(SurvivorError):
        SurvivorRace([1000.0], [("bot1", "A", 100.0), ("bot2", "B", 100.0)])
    with pytest.raises(SurvivorError):
        SurvivorRace([2000.0, 1000.0], [("bot1", "A", 100.0), ("bot2", "B", 100.0)])
    with pytest.raises(SurvivorError):
        SurvivorRace([1000.0, 2000.0], [("bot1", "A", 100.0), ("bot1", "B", 100.0)])


# --- courses simulées ---------------------------------------------------------------------------

def simulated(n: int, seed: int) -> SurvivorRace:
    """Course de n bots à puissance constante (physique du core) contre un cycliste à 220 W."""
    rnd = random.Random(seed)
    bots = [ConstantPowerBot(rnd.uniform(180.0, 260.0), bot_id=f"bot{i + 1}") for i in range(n)]
    me = ConstantPowerBot(220.0, bot_id=ME)
    r = SurvivorRace(arch_positions(n, 1), [(b.id, b.name, b.power_w) for b in bots], 1)
    everyone = [me, *bots]
    r.start(0.0, {b.id: (b.s, b.v) for b in everyone})
    t = 0.0
    while not r.finished and t < 7200.0:
        t += DT
        for b in everyone:
            if not r.is_out(b.id):
                b.step(DT)
        r.step(t, {b.id: (b.s, b.v) for b in everyone})
    return r


@pytest.mark.parametrize("n", [4, 11])
def test_simulated_race_one_elimination_per_arch(n: int) -> None:
    r = simulated(n, seed=n)
    assert r.finished
    outs = sorted(rc.out_arch for rc in r.racers.values() if rc.out_arch is not None)
    assert outs == list(range(1, n + 1))
    assert sorted(rc.place for rc in r.racers.values()) == list(range(1, n + 2))
    assert len(json.dumps(r.frame(), ensure_ascii=False).encode()) < 400


def test_same_seed_same_race() -> None:
    assert simulated(4, seed=7).summary() == simulated(4, seed=7).summary()


def test_tie_threshold_is_one_millisecond() -> None:
    assert TIE_S == 0.001
