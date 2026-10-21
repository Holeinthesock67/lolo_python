"""Tests de physique (SRS §12) : 250 W à plat, arrêt, montée à 0 W, descente à 0 W."""

import pytest

from openride_core.config import Config
from openride_core.physics import (
    V_MAX, PhysicsParams, RiderPhysics, air_density, steady_speed,
)

REF = PhysicsParams(mass_kg=84.0, cda_m2=0.32, crr=0.004, efficiency=0.97)


def ride(phys: RiderPhysics, power: float, grade: float, seconds: float, alt: float = 0.0):
    for _ in range(int(seconds / 0.02)):
        phys.step(power, grade, alt)
    return phys.v


def test_reference_case_250w_flat():
    v = ride(RiderPhysics(REF), 250.0, 0.0, 300.0)
    assert v == pytest.approx(10.2, rel=0.03)
    assert v == pytest.approx(steady_speed(250.0, 0.0, REF), rel=1e-3)


def test_stable_at_rest():
    phys = RiderPhysics(REF)
    ride(phys, 0.0, 0.0, 60.0)
    assert phys.v == 0.0 and phys.s == 0.0


def test_no_rollback_uphill_at_zero_power():
    phys = RiderPhysics(REF, v=5.0)
    ride(phys, 0.0, 8.0, 30.0)
    s_stop = phys.s
    assert phys.v == 0.0
    ride(phys, 0.0, 8.0, 30.0)
    assert phys.s == s_stop  # ne recule pas, ne repart pas


def test_downhill_at_zero_power_accelerates():
    phys = RiderPhysics(REF)
    ride(phys, 0.0, -6.0, 5.0)
    v5 = phys.v
    ride(phys, 0.0, -6.0, 5.0)
    assert 0.5 < v5 < phys.v


def test_starts_from_rest_with_power():
    phys = RiderPhysics(REF)
    ride(phys, 200.0, 0.0, 2.0)
    assert phys.v > 1.0


def test_speed_capped():
    phys = RiderPhysics(REF, v=79.0)
    ride(phys, 2000.0, -25.0, 10.0)
    assert phys.v <= V_MAX


def test_air_density_decreases_with_altitude():
    assert air_density(0) == pytest.approx(1.225)
    assert air_density(2000) < air_density(0)


def test_params_from_default_config():
    p = PhysicsParams.from_config(Config())
    assert p.mass_kg == pytest.approx(84.0)
    assert p.cda_m2 == pytest.approx(0.32)


def test_draft_reduces_power_needed():
    assert steady_speed(250, 0, REF) < ride(RiderPhysics(REF), 250, 0, 300) + 1  # sanity
    phys = RiderPhysics(REF)
    for _ in range(int(300 / 0.02)):
        phys.step(250.0, 0.0, 0.0, alpha_draft=0.3)
    assert phys.v > steady_speed(250, 0, REF)
