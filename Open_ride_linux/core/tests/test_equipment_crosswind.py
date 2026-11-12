"""Lot P34 : roue lenticulaire et vent de travers (question V-Q13)."""

from __future__ import annotations

import copy
import math

import pytest

from openride_core.equipment import (
    CatalogueError, apply_equipment, crosswind_cda_ratio, equipment_time_gain, load_catalogue,
    physical_deltas, segment_time_gain,
)
from openride_core.journal import Record, record_line
from openride_core.physics import PhysicsParams, steady_speed
from openride_core.profile import DEFAULT_EQUIPPED
from openride_core.progression import _validate, load_table
from openride_core.wind import WindSample, apparent_yaw_deg, cross_component, head_component

BASE = PhysicsParams(mass_kg=75.0, cda_m2=0.32)
KMH = 1.0 / 3.6


@pytest.fixture(scope="module")
def table():
    return load_table(user_path=None)


@pytest.fixture(scope="module")
def cat(table):
    return load_catalogue(table)


def loadout(**kw):
    out = dict(DEFAULT_EQUIPPED)
    out.update(kw)
    return out


def ratio_of(cat, lo):
    return lambda yaw: crosswind_cda_ratio(lo, cat, yaw)


# --- lacet et composantes du vent -----------------------------------------------------------

def test_apparent_yaw():
    assert apparent_yaw_deg(10.0, 0.0, 0.0) == 0.0
    assert apparent_yaw_deg(10.0, 0.0, 10.0) == pytest.approx(45.0)
    assert apparent_yaw_deg(10.0, 0.0, -10.0) == pytest.approx(45.0)        # de gauche, même lacet
    assert apparent_yaw_deg(5.0, -6.0, 1.0) == pytest.approx(90.0, abs=1e-3)  # vent de dos plus rapide
    side = WindSample(5.0, 90.0, 0.0)                                         # vent d'est, cap nord
    assert cross_component(side, 0.0) == pytest.approx(5.0)
    assert head_component(side, 0.0) == pytest.approx(0.0, abs=1e-9)


# --- effet sur le CdA ---------------------------------------------------------------------------

def test_disc_keeps_full_gain_without_crosswind(cat):
    disc = cat["wheels_disc"]
    assert disc.crosswind_sensitive and disc.cda_keep(0.0) == 1.0 and disc.cda_keep(10.0) == 1.0
    assert disc.cda_keep(15.0) == pytest.approx(0.5)
    assert disc.cda_keep(20.0) == 0.0 and disc.cda_keep(60.0) == 0.0
    # Les autres pièces ne bougent pas avec le vent de travers.
    for item in cat.items.values():
        if item.id != "wheels_disc":
            assert not item.crosswind_sensitive and item.cda_keep(45.0) == 1.0


def test_no_wind_identical(cat):
    """Critère 1 : sans vent, mêmes paramètres et même temps gagné qu'avant le lot."""
    lo = loadout(frame="frame_tt", wheels="wheels_disc")
    assert apply_equipment(BASE, lo, cat) == apply_equipment(BASE, lo, cat, yaw_deg=0.0)
    assert physical_deltas(lo, cat) == (1.0, -7.0)
    assert crosswind_cda_ratio(lo, cat, 0.0) == 1.0
    recs = flat_records(10000, 250.0)
    eq = apply_equipment(BASE, lo, cat)
    assert equipment_time_gain(recs, eq, BASE, cda_ratio=ratio_of(cat, lo)) == equipment_time_gain(recs, eq, BASE)


def test_strong_crosswind_disc_not_better_than_deep(cat):
    """Critère 2 : par fort vent de travers, la lenticulaire ne fait pas mieux que les Profilées."""
    disc, deep = loadout(wheels="wheels_disc"), loadout(wheels="wheels_deep")
    for yaw in (14.0, 20.0, 30.0, 60.0, 90.0):
        assert apply_equipment(BASE, disc, cat, yaw).cda_m2 >= apply_equipment(BASE, deep, cat, yaw).cda_m2
    calm_disc = apply_equipment(BASE, disc, cat).cda_m2
    assert calm_disc < apply_equipment(BASE, deep, cat).cda_m2             # par vent calme, elle reste devant
    assert apply_equipment(BASE, disc, cat, 30.0).cda_m2 == pytest.approx(BASE.cda_m2)


def test_mass_unchanged_by_crosswind(cat):
    disc = loadout(wheels="wheels_disc")
    assert apply_equipment(BASE, disc, cat, 45.0).mass_kg == apply_equipment(BASE, disc, cat).mass_kg


def test_ratio_respects_cda_bound(cat):
    """Cadre CLM (−4 %) et lenticulaire (−3 %) : −6 % borné par vent calme, −4 % au-delà de 20°."""
    lo = loadout(frame="frame_tt", wheels="wheels_disc")
    assert apply_equipment(BASE, lo, cat).cda_m2 == pytest.approx(BASE.cda_m2 * 0.94)
    assert crosswind_cda_ratio(lo, cat, 12.0) == 1.0                    # gain encore au-delà de la borne
    assert crosswind_cda_ratio(lo, cat, 30.0) == pytest.approx(0.96 / 0.94)
    for yaw in (0.0, 12.0, 15.0, 18.0, 25.0):
        assert (apply_equipment(BASE, lo, cat).cda_m2 * crosswind_cda_ratio(lo, cat, yaw)
                == pytest.approx(apply_equipment(BASE, lo, cat, yaw).cda_m2))
    assert crosswind_cda_ratio(loadout(wheels="wheels_deep"), cat, 45.0) == 1.0


@pytest.mark.parametrize("change, message", [
    (dict(crosswind_fade_deg=20.0, crosswind_zero_deg=10.0), "wheels_disc.*crosswind"),
    (dict(crosswind_zero_deg=120.0), "wheels_disc.*crosswind"),
    (dict(cda_delta_pct=0.0), "wheels_disc.*vent de travers"),
])
def test_invalid_crosswind_keys(table, change, message):
    data = copy.deepcopy(table.data)
    next(i for i in data["items"] if i["id"] == "wheels_disc").update(change)
    with pytest.raises(CatalogueError, match=message):
        load_catalogue(_validate(data, "test"))


# --- temps gagné avec le vent du parcours --------------------------------------------------

def flat_records(length_m: float, power: float, head: float | None = None,
                 cross: float | None = None) -> list[dict]:
    p = PhysicsParams(mass_kg=BASE.mass_kg, cda_m2=BASE.cda_m2, wind_mps=head or 0.0)
    v = steady_speed(power, 0.0, p)
    n = int(length_m / v) + 1
    out = []
    for i in range(n + 1):
        r = {"kind": "record", "t": float(i), "distance": min(v * i, length_m), "speed": v,
             "power": power, "grade": 0.0, "alt": 0.0}
        if head is not None:
            r.update(head_mps=head, cross_mps=cross)
        out.append(r)
    return out


def test_time_gain_with_route_wind(cat):
    disc, deep = loadout(wheels="wheels_disc"), loadout(wheels="wheels_deep")
    e_disc, e_deep = apply_equipment(BASE, disc, cat), apply_equipment(BASE, deep, cat)
    calm = flat_records(10000, 250.0)
    assert equipment_time_gain(calm, e_disc, BASE, cda_ratio=ratio_of(cat, disc)) < \
        equipment_time_gain(calm, e_deep, BASE, cda_ratio=ratio_of(cat, deep)) < 0
    # Vent de 20 km/h plein travers à environ 37 km/h : lacet proche de 28°.
    side = flat_records(10000, 250.0, head=0.0, cross=20 * KMH)
    g_disc = equipment_time_gain(side, e_disc, BASE, cda_ratio=ratio_of(cat, disc))
    g_deep = equipment_time_gain(side, e_deep, BASE, cda_ratio=ratio_of(cat, deep))
    assert g_disc > 0 and g_deep < 0 and g_disc > g_deep      # seule la masse de la lenticulaire reste
    # Vent de face sans travers : la lenticulaire garde tout son gain, plus grand que par vent calme.
    head = flat_records(10000, 250.0, head=15 * KMH, cross=0.0)
    g_head = equipment_time_gain(head, e_disc, BASE, cda_ratio=ratio_of(cat, disc))
    assert g_head < equipment_time_gain(calm, e_disc, BASE, cda_ratio=ratio_of(cat, disc))


def test_segment_gain_with_crosswind(cat):
    disc = loadout(wheels="wheels_disc")
    eq = apply_equipment(BASE, disc, cat)
    side = flat_records(3000, 250.0, head=0.0, cross=20 * KMH)
    t_end = next(r["t"] for r in side if r["distance"] >= 2000.0)
    calm_gain = segment_time_gain(flat_records(3000, 250.0), eq, BASE, 0.0, t_end, 0.0, 2000.0,
                                  cda_ratio=ratio_of(cat, disc))
    side_gain = segment_time_gain(side, eq, BASE, 0.0, t_end, 0.0, 2000.0, cda_ratio=ratio_of(cat, disc))
    assert calm_gain < 0 < side_gain


# --- journal ----------------------------------------------------------------------------------

def test_journal_cross_key_optional():
    rec = Record(ts=0.0, t=0.0, lat=0.0, lon=0.0, alt=0.0, distance=0.0, speed=0.0, power=0,
                 cadence=0, hr=None)
    assert "cross_mps" not in record_line(rec)
    line = record_line(Record(**{**rec.__dict__, "head_mps": 1.0, "cross_mps": -2.5}))
    assert line["cross_mps"] == -2.5 and math.isfinite(line["head_mps"])


# --- séance -----------------------------------------------------------------------------------

def test_session_applies_crosswind_to_step_cda_only(tmp_path, monkeypatch):
    """Lenticulaire dans la séance : CdA du pas réduit par vent de travers, sans s'accumuler d'un pas
    à l'autre ; équipement de la séance et puissance enregistrée inchangés ; `cross_mps` au journal."""
    from openride_core.wind import WindModel
    from test_progression_session import make

    s, _ = make(tmp_path, monkeypatch, port=6090)
    s.progress_svc.profile.purchases.append({"item_id": "wheels_disc", "price": 0, "ts": 1})
    s.progress_svc.profile.equipped.update(wheels="wheels_disc")
    s._base_params = s._equipped_params()
    s.physics.p = s._base_params
    calm_cda = s._base_params.cda_m2
    s._on_command("select_route", {}, 1)
    heading = s.route.sample(0.0).heading_deg
    s.wind = WindModel("fixed", speed_kmh=25.0, from_deg=heading + 90.0)   # plein travers, de droite
    s._on_command("start", {}, 2)
    for i in range(1500):
        s.physics.s, s.physics.v = 0.0, 10.0       # même point, 36 km/h : lacet ≈ 35°, gain annulé
        s._step(0.02, 10.0 + i * 0.02)
    assert s._cross_mps == pytest.approx(25.0 * KMH, abs=0.05)
    assert s._base_params.cda_m2 == calm_cda
    expected = calm_cda * crosswind_cda_ratio(s.progress_svc.profile.equipped, s.progress_svc.catalogue,
                                              apparent_yaw_deg(10.0, s._head_mps, s._cross_mps))
    assert s.physics.p.cda_m2 == pytest.approx(expected) and s.physics.p.cda_m2 > calm_cda
    recs = s._rec.records
    assert recs and all("cross_mps" in r for r in recs)
