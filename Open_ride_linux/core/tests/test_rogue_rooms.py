"""Lot R3 : générateur de salles du mode Cyber-Rogue."""

from __future__ import annotations

import json

import pytest

from functools import lru_cache

from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.physics import steady_speed as _steady
from openride_core.rogue.balance import DEFAULT_BALANCE
from openride_core.rogue.rooms import (ARCHETYPES, BOSS_PHASES, DS_M, OBJECTIVES, RoomRider,
                                       generate_room, room_to_route)

RIDER = RoomRider(ftp_w=250.0, params=PhysicsParams(mass_kg=84.0, cda_m2=0.32))
B = DEFAULT_BALANCE


@lru_cache(maxsize=None)
def _speed(power: float, grade: float) -> float:
    return _steady(power, grade, RIDER.params)


def steady_speed(power, grade, params):      # mémoïsé : l'essai appelle la dichotomie des milliers de fois
    return _speed(round(power, 1), round(grade, 2))
CASES = [(a, v, o) for a in ARCHETYPES if a != "boss" for v in ("", "30_30") for o in OBJECTIVES] + [
    ("boss", ph, o) for ph in BOSS_PHASES for o in OBJECTIVES]


def make(a, v, o, seed=1, nominal=300.0):
    return generate_room(a, v, o, nominal, RIDER, seed, B)


def test_deterministic():
    for seed in range(100):
        for a, v, o in CASES[:: 4]:
            r1, r2 = make(a, v, o, seed, 240.0), make(a, v, o, seed, 240.0)
            assert r1 == r2
    assert make("saboteur", "", "seuil", 1) != make("saboteur", "", "seuil", 2)


@pytest.mark.parametrize("a,v,o", CASES)
def test_nominal_time_of_rider_on_target(a, v, o):
    """Cycliste simulé (physique complète) qui tient la cible : temps d'arrivée = `nominal_s` à 2 %."""
    room = make(a, v, o)
    grade = {s: g for s, g in room.profile}
    body = RiderPhysics(RIDER.params, 0.0, steady_speed(room.target_frac[0].frac * RIDER.ftp_w,
                                                         room.profile[0][1], RIDER.params))
    t = 0.0
    while body.s < room.length_m and t < 3 * room.nominal_s:
        s = body.s
        frac = next((x.frac for x in room.target_frac if x.s0_m <= s < x.s1_m), room.target_frac[-1].frac)
        i = min(int(s // DS_M), len(room.profile) - 2)
        u = (s - room.profile[i][0]) / DS_M
        g = room.profile[i][1] + u * (room.profile[i + 1][1] - room.profile[i][1])
        body.step(frac * RIDER.ftp_w, g, 0.0, 0.05)
        t += 0.05
    assert t == pytest.approx(room.nominal_s, rel=0.02)
    assert room.length_m == room.profile[-1][0]


def grade_runs(room, threshold):
    """Durées nominales des passages consécutifs de la pente au-dessus de `threshold`."""
    runs, start = [], None
    for (s, g), t in zip(room.profile, room.time_s):
        if g >= threshold and start is None:
            start = t
        if g < threshold and start is not None:
            runs.append(t - start)
            start = None
    return runs                                   # un passage encore ouvert en fin de salle est ignoré


@pytest.mark.parametrize("a,v,o", CASES)
def test_profile_limits(a, v, o):
    room = make(a, v, o, seed=3)
    g = [x for _, x in room.profile]
    assert all(B.room_grade_min - 1e-6 <= x <= B.room_grade_max + 1e-6 for x in g)
    # aucune chute de plus de max_drop_pts en 10 s
    times = room.time_s
    j = 0
    for i in range(len(g)):
        while j < len(g) and times[j] < times[i] + 10:
            j += 1
        if j < len(g):
            assert g[i] - g[j] <= B.max_drop_pts / 10 * (times[j] - times[i]) + 0.05
    if a == "puncheur":
        assert all(d >= B.min_bump_s - 0.6 for d in grade_runs(room, 5.0))


def test_puncheur_30_30_when_min_bump_longer():
    from dataclasses import replace
    room = generate_room("puncheur", "", "vo2max", 300.0, RIDER, 1, replace(B, min_bump_s=30.0))
    assert room.variant == "30_30"
    assert all(d >= 29.4 for d in grade_runs(room, 5.0))


@pytest.mark.parametrize("a,v,o", CASES)
def test_markers_inside_and_arches_before_breaks(a, v, o):
    room = make(a, v, o, seed=5)
    for m in room.markers:
        assert 0 <= m.s_m <= room.length_m + 1e-6 and m.s_m + m.len_m <= room.length_m + 1e-6
    arches = [m.s_m for m in room.markers if m.kind == "arch"]
    g = [x for _, x in room.profile]
    for i in range(1, len(g)):
        if g[i] - g[i - 1] >= B.break_min_pts:         # montée brusque d'un échantillon à l'autre
            s = room.profile[i][0]
            near = [a_ for a_ in arches if s - 60 <= a_ <= s]
            if s > 60:
                assert near, f"pas d'arche avant la rupture à {s} m"


@pytest.mark.parametrize("a,v,o", [c for c in CASES if c[0] in ("diesel", "puncheur", "grimpeur", "saboteur", "boss")])
def test_markers_do_not_overlap(a, v, o):
    room = make(a, v, o, seed=2, nominal=400.0)
    times = dict(zip((p[0] for p in room.profile), room.time_s))
    import bisect
    xs = [p[0] for p in room.profile]

    def t_at(s):
        i = min(max(bisect.bisect_right(xs, s) - 1, 0), len(xs) - 2)
        u = (s - xs[i]) / DS_M
        return room.time_s[i] + u * (room.time_s[i + 1] - room.time_s[i])

    wins = sorted((t_at(m.s_m), t_at(m.s_m + m.len_m)) for m in room.markers
                  if m.kind in ("strike_target", "parry_zone", "purge"))
    for (a0, a1), (b0, b1) in zip(wins, wins[1:]):
        assert b0 - a1 >= B.marker_gap_s - 0.1


def test_marker_kinds_per_archetype():
    kinds = lambda a, v, o: {m.kind for m in make(a, v, o, nominal=400.0).markers}   # noqa: E731
    assert {"tunnel", "strike_target"} <= kinds("diesel", "", "seuil")
    assert {"parry_zone", "arch"} <= kinds("puncheur", "", "vo2max")
    assert {"rock", "strike_target", "arch"} <= kinds("grimpeur", "", "seuil")
    assert {"pad"} <= kinds("sprinteur", "", "vo2max")
    assert {"purge"} <= kinds("saboteur", "", "seuil")
    assert sum(1 for m in make("boss", "phase1", "seuil", nominal=210).markers if m.kind == "strike_target") == 4
    assert {"shockwave", "parry_zone"} <= kinds("boss", "phase2", "seuil")


def test_boss_phases_structure():
    r = make("boss", "phase3", "seuil", nominal=120.0)
    assert [t.frac for t in r.firewall_plan] == [0.5, 1.2]
    assert max(g for _, g in r.profile) == 0
    r1 = make("boss", "phase1", "endurance", nominal=210.0)
    assert max(g for _, g in r1.profile) == pytest.approx(3.0)


def test_room_to_route():
    room = make("grimpeur", "", "seuil")
    route = room_to_route(room)
    assert route.length_m == pytest.approx(room.length_m, rel=0.001)
    for s, g in room.profile[:: 7]:
        assert route.grade_at(s) == pytest.approx(g, abs=0.001 * 100)


def test_longest_room_message_fits_one_part():
    room = make("grimpeur", "", "vo2max", nominal=300.0)
    msg = room.to_message(1)
    assert len(msg["profile"]) <= 1500
    assert len(json.dumps(msg).encode()) < 60_000
    import jsonschema
    from pathlib import Path
    schema = json.loads((Path(__file__).resolve().parents[2] / "docs/contracts/ipc/room.schema.json").read_text())
    jsonschema.validate(msg, schema)


def test_invalid_arguments():
    with pytest.raises(ValueError):
        make("dragon", "", "seuil")
    with pytest.raises(ValueError):
        make("diesel", "", "seuil", nominal=0)
