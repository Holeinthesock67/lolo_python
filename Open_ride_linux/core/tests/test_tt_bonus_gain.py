"""Lot TT-BONUS : bonus plus longs et plus forts, temps gagné affiché à la fin du bonus (`powerup.gain`, 1.41)."""

from __future__ import annotations

import pytest

from openride_core.physics import PhysicsParams, RiderPhysics, steady_speed
from openride_core.powerups import GAIN_SHOW_S, Context, PowerUps

PLAN = PhysicsParams(mass_kg=84.0, cda_m2=0.32, crr=0.004)
DT = 0.02


def ride(kind: str, grade: float, power_w: float = 140.0, seconds: float = 45.0, erg_at: float | None = None,
         ctx: Context | None = None):
    """Séance réduite : le pas du cycliste (bonus compris) puis `track_gain`, comme `CoreSession._step`."""
    pu = PowerUps(set_name="tactiques")
    pu.reserve = kind
    assert pu.activate(0.0, ctx)
    rider = RiderPhysics(PLAN, 0.0, steady_speed(power_w, grade, PLAN))
    gains, t = [], 0.0
    while t < seconds - 1e-9:
        if erg_at is not None and t >= erg_at:
            pu.set_erg(True)
        rider.p = pu.params(PLAN)
        used = pu.power(power_w)
        before = (rider.distance, rider.v)
        rider.step(used, grade, 0.0, DT)
        g = pu.track_gain(t, rider.p, used, grade, 0.0, DT, 0.0, before, (rider.distance, rider.v))
        if g is not None:
            gains.append((t, g))
        pu.step(DT)
        t += DT
    return pu, gains


@pytest.mark.parametrize("kind, grade, lo, hi", [("aero", 0.0, 3.5, 5.5), ("feather", 3.0, 4.0, 6.0),
                                                  ("power", 3.0, 4.0, 6.0)])
def test_gain_announced_once_at_the_end_of_the_bonus(kind, grade, lo, hi):
    """4 à 5 s gagnées sur le terrain de chaque bonus à 140 W (fiche de cohérence du 22/11, §3 bis), annoncées
    une fois, juste après les 30 s du bonus ; l'élan gardé après la fin est compté."""
    pu, gains = ride(kind, grade)
    assert len(gains) == 1
    t, g = gains[0]
    assert t == pytest.approx(30.0, abs=0.05) and g.kind == kind and lo <= g.gain_s <= hi
    assert pu.gains == [g]


def test_gain_shown_six_seconds_in_the_contract():
    pu, gains = ride("aero", 0.0, seconds=30.04)
    assert pu.contract()["gain"] == {"kind": "aero", "gain_s": gains[0][1].gain_s}
    pu.step(GAIN_SHOW_S - 0.1)
    assert "gain" in pu.contract()
    pu.step(0.2)
    assert "gain" not in pu.contract() and pu.gain is None


def test_wrong_terrain_gains_little():
    _, gains = ride("aero", 6.0)        # Casque en montée : presque rien
    assert 0.0 < gains[0][1].gain_s < 1.5
    _, gains = ride("feather", 0.0)     # Plume sur le plat : presque rien
    assert abs(gains[0][1].gain_s) < 1.0


def test_no_gain_for_bonuses_without_mass_cda_or_power():
    _, gains = ride("breakaway", 0.0, ctx=Context(has_bots=True))
    assert gains == []


def test_erg_cuts_the_bonus_without_gain():
    pu, gains = ride("aero", 0.0, erg_at=10.0)
    assert gains == [] and "gain" not in pu.contract()
