"""Lot R15 : scénariste de run du Cyber-Rogue."""

from __future__ import annotations

import itertools

import pytest

from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.rogue.balance import DEFAULT_BALANCE
from openride_core.rogue.combat import target_at
from openride_core.rogue.rooms import RoomRider
from openride_core.rogue.run import RunEngine, RunInputs
from openride_core.rogue.scenario import DURATIONS, OBJECTIVES, adapt_after_room, compose_run

B = DEFAULT_BALANCE
RIDER = RoomRider(ftp_w=250.0, params=PhysicsParams(mass_kg=84.0, cda_m2=0.32))


def total_nominal(sc):
    total = 0.0
    for st in sc.steps:
        total += st.nominal_s
        if st.kind == "corridor" and st.doors:
            total += st.doors[0].nominal_s
    return total


def paths(sc):
    """Toutes les suites d'archétypes que peut jouer le joueur (première salle puis une porte par couloir)."""
    first = next(s for s in sc.steps if s.kind == "room").archetype
    layers = [tuple(d.archetype for d in s.doors) for s in sc.steps if s.kind == "corridor" and s.doors]
    return [(first,) + p for p in itertools.product(*layers)]


@pytest.mark.parametrize("duration", DURATIONS)
@pytest.mark.parametrize("objective", OBJECTIVES)
def test_durations_reservoirs_and_rules(duration, objective):
    for seed in range(100):
        sc = compose_run(objective, duration, seed, RIDER, B)
        assert abs(total_nominal(sc) - duration * 60.0) <= 30.0
        pool = set(B.reservoirs[objective]) | ({"sprinteur"} if objective == "threshold" else set())
        rooms = [s for s in sc.steps if s.kind == "room"] + [d for s in sc.steps if s.doors for d in s.doors]
        assert all(r.archetype in pool and r.objective == objective for r in rooms)
        assert all(180.0 <= r.nominal_s <= 300.0 for r in rooms)
        for s in sc.steps:
            if s.doors:
                assert len(s.doors) == 2 and s.doors[0].archetype != s.doors[1].archetype
        assert sc.steps[0].kind == "warmup" and sc.steps[-1].kind == "cooldown"
        assert [s.kind for s in sc.steps if s.kind == "boss"] == ["boss"] * 3
        corridors = [s for s in sc.steps if s.kind == "corridor"]
        assert corridors[-1].doors == () and all(c.doors for c in corridors[:-1])
        if seed < 12:                                   # tous les chemins possibles
            for path in paths(sc):
                assert all(len(set(path[i:i + 3])) > 1 for i in range(len(path) - 2)), path
                if objective == "threshold":
                    assert path.count("sprinteur") <= 1


def test_no_vo2max_room_in_endurance_and_same_seed_same_scenario():
    sc = compose_run("endurance", 45, 7, RIDER, B)
    assert all(s.variant == "" and s.objective == "endurance" for s in sc.steps if s.kind == "room")
    assert sc == compose_run("endurance", 45, 7, RIDER, B)
    assert sc != compose_run("endurance", 45, 8, RIDER, B)
    assert not {"puncheur"} & {s.archetype for s in sc.steps if s.kind == "room"}


def test_invalid_arguments():
    with pytest.raises(ValueError):
        compose_run("sprint", 45, 1)
    with pytest.raises(ValueError):
        compose_run("endurance", 40, 1)


def test_adapt_shortens_corridors_then_drops_a_room():
    sc = compose_run("threshold", 45, 3, RIDER, B)
    first = next(i for i, s in enumerate(sc.steps) if s.kind == "room")
    on_time = sum(s.nominal_s for s in sc.steps[:first + 1])
    same, skipped = adapt_after_room(sc, first, on_time, B)
    assert same == sc and skipped == 0
    late, skipped = adapt_after_room(sc, first, on_time + 60.0, B)
    assert skipped == 0 and any(s.nominal_s == B.corridor_min_s for s in late.steps if s.kind == "corridor")
    assert sum(1 for s in late.steps if s.kind == "boss") == 3 and late.steps[-1].kind == "cooldown"
    very_late, skipped = adapt_after_room(sc, first, on_time + 900.0, B)
    assert skipped >= 1
    assert sum(1 for s in very_late.steps if s.kind == "boss") == 3 and very_late.steps[-1].kind == "cooldown"
    assert [s for s in very_late.steps if s.kind == "corridor"][-1].doors == ()


class SlowRider:
    def __init__(self, engine, mult, dt=0.1):
        self.e, self.mult, self.dt = engine, mult, dt
        self.body, self.room_id, self.t = RiderPhysics(RIDER.params), None, 0.0
        self.skipped_events, self.outs = 0, []

    def run(self, max_s):
        e = self.e
        while self.t < max_s:
            if e.room is not None and e.room_id != self.room_id:
                self.room_id, self.body = e.room_id, RiderPhysics(RIDER.params)
            in_room = e.room is not None and e.phase in ("ROOM", "BOSS")
            power = target_at(e.room, self.body.s) * 250.0 * self.mult if in_room else 150.0
            out = e.step(self.dt, RunInputs(power_w=power, cadence_rpm=85, gear=6, ftp_w=250.0,
                                            s_m=self.body.s if e.room else 0.0, v_mps=self.body.v))
            self.body.step(power, out.grade_enemy, 0.0, self.dt)
            self.skipped_events += out.rogue["events"].count("room_skipped")
            self.outs.append(out)
            self.t += self.dt
            if out.finished:
                break
        return self.t


def test_slow_player_45_min_finishes_by_47_with_boss_and_signals_skips():
    sc = compose_run("threshold", 45, 2, RIDER, B)
    e = RunEngine(sc, RIDER, 20000.0, 250.0, B)
    r = SlowRider(e, 0.9)
    end = r.run(4000.0)
    assert r.outs[-1].finished and end <= 47 * 60.0
    s = e.summary()
    assert s["boss"] in ("won", "fled") and any(o.rogue["boss_phase"] == 3 for o in r.outs) or s["boss"] == "fled"
    assert r.skipped_events == s["rooms_skipped"] == e.rooms_skipped
    assert s["rooms_total"] == sc.rooms_total
    assert s["rooms_won"] + s["rooms_fled"] + s["defeats"] + s["rooms_skipped"] >= s["rooms_total"] - 1


def test_skipped_room_costs_ten_gold():
    sc = compose_run("threshold", 45, 2, RIDER, B)
    e = RunEngine(sc, RIDER, 20000.0, 250.0, B)
    e.t_total += 900.0                                   # joueur très en retard dès la première salle
    r = SlowRider(e, 1.0)
    prev_gold, delta = 0, None
    while not r.outs or "room_skipped" not in r.outs[-1].rogue["events"]:
        before = (e.gold, e.perfect_shifts)
        r.run(r.t + 0.1)
        if "room_skipped" in r.outs[-1].rogue["events"]:
            won = e.rooms_won + e.rooms_fled
            room_gold = B.win_gold + B.win_gold_per_ps * (e.perfect_shifts - before[1]) if e.rooms_won else B.flee_gold
            delta = (before[0], e.gold, room_gold, e.rooms_skipped)
        if r.t > 3000:
            break
    assert delta is not None
    g0, g1, room_gold, k = delta
    assert g1 == pytest.approx(max(g0 + room_gold - 10.0 * k, 0.0))
    assert r.outs[-1].rogue["events"].count("room_skipped") == k
