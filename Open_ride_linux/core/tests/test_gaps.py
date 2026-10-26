"""Lot T16 : écarts en temps de passage (module pur `gaps`)."""

from __future__ import annotations

import time

import pytest

from openride_core.gaps import HISTORY_S, GapTracker

DT = 0.02


def run(tracker: GapTracker, duration: float, me, bots, speed_me, speed_bots, t0: float = 0.0):
    """Avance cycliste et bots à 50 Hz ; vitesses = fonctions de s. Rend (t, me, bots, report)."""
    t = t0
    report = None
    for _ in range(int(round(duration / DT))):
        report = tracker.step(t, (me, speed_me(me)), {k: (s, speed_bots[k](s)) for k, s in bots.items()})
        me += speed_me(me) * DT
        bots = {k: s + speed_bots[k](s) * DT for k, s in bots.items()}
        t += DT
    report = tracker.step(t, (me, speed_me(me)), {k: (s, speed_bots[k](s)) for k, s in bots.items()})
    return t, me, bots, report


def const(v):
    return lambda s: v


def test_constant_speeds_time_gap_equals_distance_over_speed():
    tr = GapTracker()
    _, me, bots, rep = run(tr, 120.0, 0.0, {"a": 100.0, "b": -50.0}, const(10.0),
                           {"a": const(10.0), "b": const(10.0)})
    assert rep.gaps["a"].gap_s == pytest.approx(10.0, abs=0.02)
    assert not rep.gaps["a"].estimated
    assert rep.gaps["b"].gap_s == pytest.approx(-5.0, abs=0.02)
    assert not rep.gaps["b"].estimated
    assert rep.bot_ahead == "a" and rep.bot_behind == "b"


def test_start_falls_back_to_distance_over_speed():
    tr = GapTracker()
    rep = tr.step(0.0, (0.0, 8.0), {"a": (40.0, 9.0), "b": (-30.0, 6.0)})
    assert rep.gaps["a"].estimated and rep.gaps["a"].gap_s == pytest.approx(5.0)     # 40 / 8
    assert rep.gaps["b"].estimated and rep.gaps["b"].gap_s == pytest.approx(-5.0)    # 30 / 6
    rep = tr.step(0.0, (0.0, 0.0), {"a": (5.0, 0.0)})
    assert rep.gaps["a"].gap_s == pytest.approx(5.0)                                 # plancher 1 m/s


def test_time_gap_stable_on_climb_where_estimate_jumps():
    # Le bot devant entre dans une montée (2 m/s) ; le cycliste roule encore à 10 m/s sur le plat.
    # Écart réel : temps depuis le passage du bot au point du cycliste, stable ; l'estimation
    # distance ÷ vitesse du bot ferait sauter l'écart.
    climb_at = 1500.0

    def v(s):
        return 10.0 if s < climb_at else 2.0

    tr = GapTracker()
    _, me, bots, rep = run(tr, 145.0, 0.0, {"a": 100.0}, v, {"a": v})
    assert me < climb_at < bots["a"]
    assert rep.gaps["a"].gap_s == pytest.approx(10.0, abs=0.05)   # 100 m à 10 m/s, au même point
    estimate_bot_speed = rep.gaps["a"].distance_m / 2.0
    assert estimate_bot_speed > 2 * rep.gaps["a"].gap_s


def test_neighbours_are_the_closest_ones():
    tr = GapTracker()
    rep = tr.step(0.0, (1000.0, 10.0), {"far": (1500.0, 10.0), "near": (1020.0, 10.0),
                                        "back": (990.0, 10.0), "wayback": (500.0, 10.0)})
    assert rep.bot_ahead == "near" and rep.bot_behind == "back"
    rep = tr.step(0.1, (1000.0, 10.0), {"far": (1500.0, 10.0)})
    assert rep.bot_ahead == "far" and rep.bot_behind is None
    rep = tr.step(0.2, (1000.0, 10.0), {})
    assert rep.bot_ahead is None and rep.bot_behind is None and rep.gaps == {}


def test_loop_neighbour_on_current_lap():
    # Boucle de 1 000 m : bot à 1 950 m cumulés (un tour d'avance), cycliste à 1 000 m.
    # Sur le circuit, le bot est 50 m derrière le cycliste.
    tr = GapTracker(length_m=1000.0, loop=True)
    rep = tr.step(0.0, (1000.0, 10.0), {"a": (1950.0, 10.0)})
    assert rep.gaps["a"].distance_m == pytest.approx(-50.0)
    assert rep.bot_behind == "a" and rep.bot_ahead is None


def test_loop_time_gap_uses_history_across_laps():
    tr = GapTracker(length_m=1000.0, loop=True)
    _, me, bots, rep = run(tr, 60.0, 0.0, {"a": 1080.0}, const(10.0), {"a": const(10.0)})
    # Le bot a un tour et 80 m d'avance : sur le circuit, 80 m devant, 8 s.
    assert rep.gaps["a"].distance_m == pytest.approx(80.0, abs=0.01)
    assert rep.gaps["a"].gap_s == pytest.approx(8.0, abs=0.02)
    assert not rep.gaps["a"].estimated
    with pytest.raises(ValueError):
        GapTracker(loop=True)


def test_history_window_then_fallback():
    # Bot 400 s devant : son passage est sorti de l'historique de 300 s → repli.
    tr = GapTracker()
    _, me, bots, rep = run(tr, 450.0, 0.0, {"a": 1600.0}, const(4.0), {"a": const(4.0)})
    assert HISTORY_S < 400.0
    assert rep.gaps["a"].estimated
    assert rep.gaps["a"].gap_s == pytest.approx(400.0, abs=0.5)


def test_cost_per_frame_with_five_bots():
    tr = GapTracker()
    bots = {f"b{i}": (100.0 * i - 200.0, 9.0) for i in range(5)}
    for k in range(3000):
        tr.record(k * DT, {"rider": k * 0.2, **{b: s + k * 0.18 for b, (s, _) in bots.items()}})
    t0 = time.perf_counter()
    n = 2000
    for k in range(n):
        tr.step(60.0 + k * DT, (600.0 + k * 0.2, 10.0), bots)
    per_frame_ms = (time.perf_counter() - t0) / n * 1000.0
    assert per_frame_ms < 0.2
