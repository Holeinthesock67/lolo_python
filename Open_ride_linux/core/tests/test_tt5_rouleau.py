"""Lot TT5 : bonus Rouleau compresseur (roulement du bitume sur le non revêtu pendant 30 s)."""

from __future__ import annotations

import pytest

from openride_core import classic, surface_physics
from openride_core.config import GravelConfig
from openride_core.physics import PhysicsParams, RiderPhysics, steady_speed
from openride_core.powerups import DEFAULT_TABLE, Context, PowerUps, unpaved_ahead

PLAN = PhysicsParams(mass_kg=84.0, cda_m2=0.32, crr=0.004)
GRAVEL = GravelConfig(mode="auto")
G = GRAVEL.factor_gravel   # 2,5


def ctx(ds: float = 0.0, gravel: bool = True) -> Context:
    return Context(ds_m=ds, gravel_ahead=lambda: gravel)


def test_table_line():
    s = DEFAULT_TABLE.specs["roller"]
    assert (s.effect, s.factor, s.duration_s, s.sets) == ("crr", 1.0, 25.0, ("tactiques",))
    assert s.draw_if == ("gravel_ahead",) and s.refuse_unless == (("gravel_ahead", "no_gravel"),)


def test_unpaved_ahead_needs_1_km_in_5_km():
    track = lambda start, length: (lambda s: "gravel" if start <= s < start + length else "paved")
    assert unpaved_ahead(track(2000.0, 1000.0), 0.0)
    assert not unpaved_ahead(track(2000.0, 900.0), 0.0)
    assert not unpaved_ahead(track(4500.0, 1000.0), 0.0)                  # 500 m seulement dans les 5 km
    assert not unpaved_ahead(track(500.0, 2000.0), 0.0, length_m=1200.0)  # arrivée avant
    assert unpaved_ahead(lambda s: "dirt", 0.0)


def test_never_drawn_without_gravel_and_refused():
    pu = PowerUps(seed=4, set_name="tactiques")
    assert "roller" not in {pu.award("segment", ctx(gravel=False)) for _ in range(1000)}
    assert "roller" in {pu.award("segment", ctx()) for _ in range(300)}
    pu = PowerUps(set_name="tactiques")
    pu.reserve = "roller"
    assert not pu.activate(0.0, ctx(gravel=False)) and pu.contract()["refused"]["reason"] == "no_gravel"
    # Sans option gravel, la course ne donne aucune surface : jamais tiré.
    race = classic.ClassicRace("demo", (), 5000.0, powerup_set="tactiques", grade_at=lambda s: 0.0)
    assert not race.context(0.0).gravel_ahead()


def test_fade_over_20_m_in_and_out():
    pu = PowerUps(set_name="tactiques")
    pu.reserve = "roller"
    assert pu.activate(0.0, ctx())
    assert pu.surface_factor(G) == G                                     # rien avant le premier mètre
    pu.step(1.0, ctx(10.0))
    assert pu.surface_factor(G) == pytest.approx(1.0 + (G - 1.0) * 0.5)  # 10 m sur 20
    pu.step(1.0, ctx(10.0))
    assert pu.surface_factor(G) == pytest.approx(1.0)                    # bitume
    pu.step(28.0, ctx(0.0))
    assert pu.active is None and pu.surface_factor(G) == pytest.approx(1.0)
    pu.step(1.0, ctx(5.0))
    assert pu.surface_factor(G) == pytest.approx(1.0 + (G - 1.0) * 0.25)  # sortie sur 20 m
    pu.step(1.0, ctx(15.0))
    assert pu.surface_factor(G) == G and pu.params(PLAN) is PLAN          # crr de base jamais touché


def test_sim_gravel_offset_disappears():
    full = surface_physics.grade_offset_pct(PLAN.crr, G, 0.0)
    assert full == pytest.approx(0.6)                                    # plan : −0,6 point environ
    pu = PowerUps(set_name="tactiques")
    pu.reserve = "roller"
    pu.activate(0.0, ctx())
    pu.step(2.0, ctx(20.0))
    assert surface_physics.grade_offset_pct(PLAN.crr, pu.surface_factor(G), 0.0) == pytest.approx(0.0)


def test_gain_in_ideal_terrain():
    """Gravier (× 2,5) sur le plat, 250 W : 2,0 s mesurés 60 s après l'appui (2,5 s à 30 s avant le banc TT8)."""
    dt, grade = 0.02, 0.0
    rough = PhysicsParams(mass_kg=PLAN.mass_kg, cda_m2=PLAN.cda_m2, crr=PLAN.crr * G)
    v = steady_speed(250.0, grade, rough)
    pu = PowerUps(set_name="tactiques")
    pu.reserve = "roller"
    assert pu.activate(0.0, ctx())
    a, b = RiderPhysics(rough, 0.0, v), RiderPhysics(rough, 0.0, v)
    t = 0.0
    while t < 60.0 - 1e-9:
        t += dt
        a.p = PhysicsParams(mass_kg=PLAN.mass_kg, cda_m2=PLAN.cda_m2, crr=PLAN.crr * pu.surface_factor(G))
        s0 = a.s
        a.step(250.0, grade, 0.0, dt)
        b.step(250.0, grade, 0.0, dt)
        pu.step(dt, ctx(a.s - s0))
    assert (a.s - b.s) / v == pytest.approx(1.98, abs=0.1)
