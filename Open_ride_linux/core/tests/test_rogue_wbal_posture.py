"""Lot R2 : W'bal et postures de cadence du mode Cyber-Rogue (modules purs)."""

from __future__ import annotations

import math

import pytest

from openride_core.config import ConfigError, from_dict
from openride_core.rogue.posture import ARRET, FLUIDE, ROC, VELOCE, PostureState, posture_step
from openride_core.rogue.wbal import wbal_initial, wbal_step

CP, WP = 250.0, 20000.0


def run_wbal(profile, dt, cadence=60.0):
    """profile : liste de (durée s, puissance W)."""
    st = wbal_initial(WP)
    for dur, p in profile:
        for _ in range(round(dur / dt)):
            st = wbal_step(st, p, cadence, dt, cp_w=CP, w_prime_j=WP)
    return st


def test_effort_3min_cp_plus_100():
    assert run_wbal([(180, CP + 100)], 0.02).w_bal_j == pytest.approx(2000, rel=0.01)


def test_recovery_time_constant():
    st = wbal_initial(WP)
    st = wbal_step(st, CP + 1000, 60, 20.0, cp_w=CP, w_prime_j=WP)
    assert st.w_bal_j == 0 and st.depleted_s == 20.0
    t = WP / (CP * 0.5)
    for _ in range(round(t / 0.02)):
        st = wbal_step(st, CP * 0.5, 60, 0.02, cp_w=CP, w_prime_j=WP)
    assert st.w_bal_j / WP == pytest.approx(1 - math.exp(-1), abs=0.02)
    assert st.depleted_s == 0


def test_step_independence():
    prof = [(120, 400), (60, 100), (90, 330), (120, 50)]
    a, b = run_wbal(prof, 1.0), run_wbal(prof, 0.02)
    assert abs(a.w_bal_j - b.w_bal_j) < 0.01 * WP


def test_fluid_bonus_only_in_range():
    base = wbal_initial(10000.0)
    slow = wbal_step(base, 100, 60, 10, cp_w=CP, w_prime_j=WP)
    fast = wbal_step(base, 100, 88, 10, cp_w=CP, w_prime_j=WP)
    assert fast.w_bal_j > slow.w_bal_j
    k = (CP - 100) / WP
    assert WP - fast.w_bal_j == pytest.approx((WP - 10000) * math.exp(-1.2 * k * 10), rel=1e-6)
    # posture donnée et différente de FLUIDE : pas de bonus
    other = wbal_step(base, 100, 88, 10, cp_w=CP, w_prime_j=WP, posture=ROC)
    assert other.w_bal_j == pytest.approx(slow.w_bal_j)


def test_invalid_inputs_ignored():
    st = wbal_initial(WP)
    assert wbal_step(st, 300, 80, -1, cp_w=CP, w_prime_j=WP) is st
    assert wbal_step(st, float("nan"), 80, 0.02, cp_w=CP, w_prime_j=WP).w_bal_j <= WP


def run_posture(samples, dt=0.02, state=None):
    """samples : liste de (durée, cadence, puissance) ; renvoie la liste des postures successives."""
    st = state or PostureState()
    seen = []
    for dur, cad, pwr in samples:
        for _ in range(round(dur / dt)):
            st = posture_step(st, cad, pwr, dt)
            if not seen or seen[-1] != st.posture:
                seen.append(st.posture)
    return seen, st


def test_oscillation_around_70_changes_at_most_once():
    samples = [(1.0, 69 + (i % 2) * 3, 150) for i in range(60)]
    seen, _ = run_posture([(5, 85, 150)] + samples)
    assert len(seen) <= 3 and seen.count(ROC) <= 1 and seen[0] == ARRET


def test_ramp_roc_fluide_veloce():
    ramp = [(0.5, 65 + 40 * i / 20, 150) for i in range(21)]   # 65 → 105 rpm en 10 s
    seen, _ = run_posture([(5, 65, 150)] + ramp + [(5, 105, 150)])
    assert seen == [ARRET, ROC, FLUIDE, VELOCE]


def test_stop_immediate_and_resume_after_hold():
    _, st = run_posture([(5, 85, 150)])
    assert st.posture == FLUIDE
    st = posture_step(st, 10, 0, 0.02)
    assert st.posture == ARRET
    seen, st = run_posture([(1.4, 85, 150)], state=st)
    assert st.posture == ARRET
    seen, st = run_posture([(0.2, 85, 150)], state=st)
    assert st.posture == FLUIDE


def test_hysteresis_exit_roc():
    _, st = run_posture([(5, 60, 150)])
    assert st.posture == ROC
    _, st = run_posture([(6, 71, 150)], state=st)
    assert st.posture == ROC          # 71 < 73 : on reste
    _, st = run_posture([(6, 74, 150)], state=st)
    assert st.posture == FLUIDE


def test_config_rogue_bounds():
    cfg = from_dict({"rogue": {"w_prime_j": 15000, "cp_w": 260}})
    assert (cfg.rogue.w_prime_j, cfg.rogue.cp_w) == (15000.0, 260.0)
    for bad in ({"w_prime_j": 1000}, {"cp_w": 2000}):
        with pytest.raises(ConfigError):
            from_dict({"rogue": bad})
