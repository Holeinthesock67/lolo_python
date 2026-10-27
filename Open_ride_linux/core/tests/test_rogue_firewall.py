"""Lot R4 : Firewall du mode Cyber-Rogue."""

from __future__ import annotations

import pytest

from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.rogue.balance import DEFAULT_BALANCE
from openride_core.rogue.firewall import Firewall
from openride_core.rogue.rooms import RoomRider, generate_room

RIDER = RoomRider(ftp_w=250.0, params=PhysicsParams(mass_kg=84.0, cda_m2=0.32))
DT = 0.02


def run(room, player_frac_of_wall, seconds=None, paused_between=None):
    """Joueur à `player_frac_of_wall` × la puissance du mur ; renvoie la liste des (t, état)."""
    fw = Firewall(room, RIDER)
    player = RiderPhysics(RIDER.params)
    seconds = seconds or room.nominal_s
    out = []
    for k in range(round(seconds / DT)):
        wall_p = fw.frac_at(player.s) * RIDER.ftp_w
        player.step(wall_p * player_frac_of_wall, fw.grade_at(player.s), 0.0, DT)
        paused = bool(paused_between and paused_between[0] <= k * DT < paused_between[1])
        out.append((k * DT, fw.step(DT, player.s, paused=paused)))
    return out


def diesel(objective="threshold", nominal=240.0):
    return generate_room("diesel", "", objective, nominal, RIDER, 1)


def test_same_power_constant_gap():
    states = run(diesel("endurance"), 1.0)
    assert all(abs(st.gap_m - 150.0) <= 5.0 for _, st in states[100:])


def test_below_wall_makes_contact():
    states = run(diesel(nominal=480.0), 0.90)
    assert any(st.contact for _, st in states)
    assert all(st.gap_m >= 0 for _, st in states)


def test_above_wall_gap_capped():
    states = run(diesel(nominal=900.0), 1.10)
    gaps = [st.gap_m for _, st in states]
    assert max(gaps) <= DEFAULT_BALANCE.max_gap_m + 1e-9 and max(gaps) > 150.0
    assert not any(st.contact for _, st in states)
    assert gaps[-1] == pytest.approx(DEFAULT_BALANCE.max_gap_m)       # le plafond est atteint et tenu


def test_sprinter_bursts_close_the_gap():
    room = generate_room("sprinteur", "", "threshold", 200.0, RIDER, 1)
    states = run(room, 0.95)
    times = [t for t, _ in states]
    gap_at = lambda t: states[min(round(t / DT), len(states) - 1)][1].gap_m   # noqa: E731
    bursts = [(t0, t1) for t0, t1 in _bursts(room)]
    assert bursts
    for t0, t1 in bursts:
        assert gap_at(t1) < gap_at(t0), (t0, t1, times[-1])


def _bursts(room):
    """Fenêtres de temps des salves (tronçons du plan à 1,30 FTP)."""
    for st in room.firewall_plan:
        if st.frac > 1.0:
            ts = [t for (s, _), t in zip(room.profile, room.time_s) if st.s0_m <= s <= st.s1_m]
            if len(ts) >= 2:
                yield ts[0], ts[-1]


def test_pause_and_lost_click_freeze_the_wall():
    room = diesel("endurance")
    fw = Firewall(room, RIDER)
    player = RiderPhysics(RIDER.params)
    for _ in range(500):
        player.step(180, 2.0, 0.0, DT)
        fw.step(DT, player.s)
    before = fw.state
    for _ in range(250):
        player.step(180, 2.0, 0.0, DT)
        paused = fw.step(DT, player.s, paused=True)
        lost = fw.step(DT, player.s, input_lost=True)
    assert paused.s == lost.s == before.s and paused.v == before.v
