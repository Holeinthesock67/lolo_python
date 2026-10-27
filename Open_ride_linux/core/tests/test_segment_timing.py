"""Lot T4 : chronométrage des segments (module pur `segment_timing`)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from openride_core.journal import JournalWriter, Record
from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.segment_timing import SegmentTimer, passes_from_journal

DT = 0.02


@dataclass(frozen=True)
class Seg:
    id: str
    s_start: float
    s_end: float
    type: str = "climb"
    name: str = "Montée 1"


def ride(timer: SegmentTimer, v: float, duration_s: float, power: float = 200.0,
         t0: float = 0.0, s0: float = 0.0, bonus=None, dt: float = DT) -> tuple[float, float]:
    t, s = t0, s0
    n = int(round(duration_s / dt))
    for _ in range(n):
        timer.step(t, s, power, bonus)
        t += dt
        s += v * dt
    timer.step(t, s, power, bonus)
    return t, s


def test_constant_speed_exact_time_and_stats():
    # 1 000 m à 10 m/s : 100 s ; segment décalé pour que les bornes tombent entre deux pas.
    timer = SegmentTimer([Seg("climb1", 1000.07, 2000.07)], 5000.0, rider_mass_kg=80.0)
    ride(timer, 10.0, 300.0)
    (p,) = timer.passes
    assert p.time_s == pytest.approx(100.0, abs=0.02)
    assert p.t_start == pytest.approx(100.007, abs=0.02)
    assert p.avg_power_w == pytest.approx(200.0, abs=0.5)
    assert p.avg_wkg == pytest.approx(2.5, abs=0.01)
    assert p.avg_speed_kmh == pytest.approx(36.0, abs=0.05)
    assert p.lap == 0 and p.bonuses == () and not p.with_bonus


def test_interpolation_precision_with_physics_50hz():
    # Rider simulé (vitesse variable) : comparaison avec la référence fine à 1 kHz.
    params = PhysicsParams(mass_kg=80.0)

    def run(dt: float) -> float:
        rp = RiderPhysics(params)
        timer = SegmentTimer([Seg("s", 333.3, 777.7, "sprint")], 2000.0)
        t = 0.0
        while not timer.passes and t < 300:
            timer.step(t, rp.s, 400.0)
            rp.step(400.0, 0.0, 0.0, dt)
            t += dt
        timer.step(t, rp.s, 400.0)
        return timer.passes[0].time_s

    assert run(DT) == pytest.approx(run(0.001), abs=0.02)


def test_pause_cancels_segment_then_next_pass_counts():
    timer = SegmentTimer([Seg("climb1", 1000.0, 2000.0)], 10_000.0, loop=False)
    t, s = ride(timer, 10.0, 150.0)       # au milieu du segment (s = 1 500)
    timer.pause("trainer_lost")
    assert timer.cancelled == [("climb1", 0, "trainer_lost")]
    t, s = ride(timer, 10.0, 100.0, t0=t, s0=s)   # reprise dans le segment : pas de passage
    assert timer.passes == []


def test_loop_counts_each_lap():
    timer = SegmentTimer([Seg("sprint1", 400.0, 700.0, "sprint")], 1000.0, loop=True)
    ride(timer, 10.0, 350.0)              # 3 500 m : tours 0, 1, 2 complets, tour 3 sorti à 700
    assert [p.lap for p in timer.passes] == [0, 1, 2]
    assert all(p.time_s == pytest.approx(30.0, abs=0.02) for p in timer.passes)


def test_segment_starting_at_zero_and_loop_line():
    timer = SegmentTimer([Seg("climb1", 0.0, 500.0)], 2000.0)
    ride(timer, 10.0, 80.0)
    assert len(timer.passes) == 1 and timer.passes[0].t_start == pytest.approx(0.0)
    timer = SegmentTimer([Seg("climb1", 0.0, 500.0)], 1000.0, loop=True)
    ride(timer, 10.0, 160.0)              # 1 600 m : tours 0 et 1
    assert [p.lap for p in timer.passes] == [0, 1]


def test_overlapping_segments_and_bonus_flag():
    timer = SegmentTimer([Seg("climb1", 100.0, 900.0), Seg("sprint1", 600.0, 800.0, "sprint")],
                         2000.0)
    t, s = ride(timer, 10.0, 50.0)        # s = 500
    t, s = ride(timer, 10.0, 20.0, t0=t, s0=s, bonus="aero")   # s = 700, bonus actif
    ride(timer, 10.0, 50.0, t0=t, s0=s)
    by_id = {p.segment_id: p for p in timer.passes}
    assert set(by_id) == {"climb1", "sprint1"}
    assert by_id["climb1"].bonuses == ("aero",)
    assert by_id["sprint1"].bonuses == ("aero",)


def test_whole_segment_in_one_step():
    timer = SegmentTimer([Seg("tiny", 10.0, 10.5)], 100.0)
    timer.step(0.0, 0.0, 100.0)
    timer.step(1.0, 20.0, 100.0)
    (p,) = timer.passes
    assert p.time_s == pytest.approx(0.025)


def test_live_approach_active_and_loop_next_lap():
    segs = [Seg("climb1", 1000.0, 2000.0), Seg("sprint1", 3000.0, 3300.0, "sprint", "Sprint 1")]
    timer = SegmentTimer(segs, 4000.0, loop=True)
    live = timer.live(0.0, 0.0)
    assert live.state == "approach" and live.segment_id == "climb1" and live.distance_m == 1000.0
    t, s = ride(timer, 10.0, 120.0)        # s = 1 200
    live = timer.live(t, s)
    assert live.state == "active" and live.distance_m == pytest.approx(800.0, abs=0.5)
    assert live.elapsed_s == pytest.approx(20.0, abs=0.05)
    t, s = ride(timer, 10.0, 220.0, t0=t, s0=s)   # s = 3 400 : prochain = climb1 au tour suivant
    live = timer.live(t, s)
    assert live.segment_id == "climb1" and live.distance_m == pytest.approx(1600.0, abs=0.5)
    open_timer = SegmentTimer(segs, 4000.0)
    assert open_timer.live(0.0, 3500.0) is None


def test_rejects_segment_outside_route():
    with pytest.raises(ValueError):
        SegmentTimer([Seg("x", 900.0, 1200.0)], 1000.0)


def test_to_dict_is_json():
    timer = SegmentTimer([Seg("climb1", 100.0, 300.0)], 1000.0, rider_mass_kg=75.0)
    ride(timer, 8.0, 60.0)
    d = json.loads(json.dumps(timer.passes[0].to_dict()))
    assert set(d) == {"segment_id", "lap", "t_start", "t_end", "time_s", "avg_power_w", "avg_wkg",
                      "avg_speed_kmh", "bonuses"}


def test_passes_from_journal_matches_live_and_pauses(tmp_path: Path):
    path = tmp_path / "j.jsonl"
    segs = [Seg("climb1", 1000.0, 2000.0), Seg("sprint1", 3000.0, 3300.0, "sprint")]
    with JournalWriter(path, route_id="r") as w:
        w.event("start", 0.0)
        t = 0
        s = 0.0
        while s < 4000.0:
            if t == 320:           # pause dans le sprint (s ≈ 3 200)
                w.event("pause", 1000.0 + t)
                w.event("resume", 1060.0 + t)
            w.record(Record(ts=1000.0 + t, t=float(t), distance=s, speed=10.0, power=250.0))
            t += 1
            s += 10.0
    passes = passes_from_journal(path, segs, 5000.0, rider_mass_kg=80.0)
    assert [p.segment_id for p in passes] == ["climb1"]        # le sprint est annulé par la pause
    assert passes[0].time_s == pytest.approx(100.0, abs=0.01)
    assert passes[0].avg_power_w == pytest.approx(250.0)
