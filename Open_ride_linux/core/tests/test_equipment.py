"""Lot V3 : catalogue d'équipement, effets bornés, conseil par terrain, temps gagné."""

from __future__ import annotations

import copy

import pytest

from openride_core.equipment import (
    CatalogueError, apply_equipment, advice, equipment_time_gain, fiche, gain_text,
    load_catalogue, physical_deltas, route_terrain,
)
from openride_core.physics import PhysicsParams, steady_speed
from openride_core.profile import DEFAULT_EQUIPPED
from openride_core.progression import _validate, load_table


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


# --- catalogue ---------------------------------------------------------------------------

def test_catalogue_contents(cat):
    assert [i.id for i in cat.by_slot("frame")] == [
        "frame_allround", "frame_climber", "frame_aero", "frame_allround_light", "frame_tt"]
    assert [i.id for i in cat.by_slot("wheels")] == [
        "wheels_standard", "wheels_light", "wheels_deep", "wheels_disc"]
    assert (len(cat.by_slot("helmet")), len(cat.by_slot("kit")),
            len(cat.by_slot("socks")), len(cat.by_slot("glasses"))) == (3, 6, 4, 3)
    assert cat.defaults() == DEFAULT_EQUIPPED          # mêmes défauts que le profil (V4)
    assert not cat["kit_pois"].buyable and cat["frame_climber"].buyable


def test_challenge_rewards_exist(cat, table):
    assert all(ch.reward in cat for ch in table.challenges)


def _broken(table, mutate):
    data = copy.deepcopy(table.data)
    mutate(data)
    return load_catalogue(_validate(data, "test"))


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["items"].append(dict(d["items"][1])), "frame_climber.*double"),
    (lambda d: d["items"][1].update(slot="selle"), "frame_climber.*slot"),
    (lambda d: d["items"][1].update(mass_delta_kg=-3.0), "frame_climber.*mass_delta_kg"),
    (lambda d: d["items"][2].update(cda_delta_pct=-8.0), "frame_aero.*cda_delta_pct"),
    (lambda d: d["items"][2].update(couleur="rouge"), "frame_aero.*couleur"),
    (lambda d: d["items"][1].update(default=True), "frame.*par défaut"),
    (lambda d: next(i for i in d["items"] if i["id"] == "kit_bandes").update(cda_delta_pct=-1.0),
     "kit_bandes.*apparence"),
    (lambda d: d["challenges"][0].update(reward="kit_inexistant"), "kit_inexistant"),
])
def test_invalid_catalogue_names_item(table, mutate, message):
    with pytest.raises(CatalogueError, match=message):
        _broken(table, mutate)


# --- effets bornés ------------------------------------------------------------------------

def test_cda_bound(cat):
    base = PhysicsParams(mass_kg=84.0, cda_m2=0.32)
    p = apply_equipment(base, loadout(frame="frame_tt", wheels="wheels_disc"), cat)
    assert physical_deltas(loadout(frame="frame_tt", wheels="wheels_disc"), cat)[1] == pytest.approx(-7.0)
    assert p.cda_m2 == pytest.approx(0.32 * 0.94)       # −6 %, pas −7 %
    assert p.mass_kg == pytest.approx(85.0)              # hausse non bornée


def test_mass_bound(cat):
    lo = loadout(frame="frame_climber", wheels="wheels_light")
    assert apply_equipment(PhysicsParams(mass_kg=84.0), lo, cat).mass_kg == pytest.approx(82.0)
    assert apply_equipment(PhysicsParams(mass_kg=60.0), lo, cat).mass_kg == pytest.approx(58.2)


def test_appearance_has_no_effect(cat):
    base = PhysicsParams(mass_kg=84.0, cda_m2=0.32, crr=0.005, efficiency=0.96)
    lo = loadout(helmet="helmet_aero", kit="kit_pois", socks="socks_hautes", glasses="glasses_miroir")
    assert apply_equipment(base, lo, cat) == base


def test_crr_and_efficiency_untouched(cat):
    base = PhysicsParams(mass_kg=84.0, cda_m2=0.32, crr=0.005, efficiency=0.96)
    p = apply_equipment(base, loadout(frame="frame_aero"), cat)
    assert (p.crr, p.efficiency, p.wind_mps) == (0.005, 0.96, 0.0)


# --- conseil --------------------------------------------------------------------------------

@pytest.mark.parametrize("length_m, climb_m, terrain", [
    (20000, 40, "flat"), (20000, 200, "rolling"), (10000, 600, "climb"), (0, 0, "flat"),
])
def test_route_terrain(length_m, climb_m, terrain):
    assert route_terrain(length_m, climb_m) == terrain


def test_advice(cat):
    assert {s: i.id for s, i in advice("climb", cat).items()} == {
        "frame": "frame_climber", "wheels": "wheels_light"}
    assert {s: i.id for s, i in advice("flat", cat).items()} == {
        "frame": "frame_tt", "wheels": "wheels_disc"}
    assert {s: i.id for s, i in advice("rolling", cat).items()} == {
        "frame": "frame_allround_light", "wheels": "wheels_deep"}


def test_fiche_and_gain_text(cat):
    assert fiche(cat["frame_climber"]) == "Grimpeur — −1,5 kg, CdA = — Conseillé : col"
    assert fiche(cat["frame_tt"]) == "Contre-la-montre — +0,5 kg, CdA −4,0 % — Conseillé : plat"
    assert fiche(cat["kit_pois"]) == "Maillot à pois — apparence"
    assert gain_text("Grimpeur", "frame", -14.2, "dans la montée") == "Cadre Grimpeur : −14 s dans la montée"


# --- temps gagné -----------------------------------------------------------------------------

def climb_records(length_m: float, grade: float, power: float, base: PhysicsParams) -> list[dict]:
    """Journal synthétique à 1 Hz : vitesse d'équilibre de l'équipement de départ."""
    v = steady_speed(power, grade, base)
    n = int(length_m / v) + 1
    return [{"kind": "record", "t": float(i), "distance": min(v * i, length_m), "speed": v,
             "power": power, "grade": grade, "alt": 0.0} for i in range(n + 1)]


def test_time_gain_climb_and_flat(cat):
    base = PhysicsParams(mass_kg=75.0, cda_m2=0.32)
    climber = apply_equipment(base, loadout(frame="frame_climber"), cat)
    aero = apply_equipment(base, loadout(frame="frame_aero"), cat)

    climb = climb_records(5000, 7.0, 250.0, base)
    g_climber = equipment_time_gain(climb, climber, base)
    g_aero = equipment_time_gain(climb, aero, base)
    # Montée de 5 km à 7 % (≈ 19 min) : quelques dizaines de secondes gagnées avec −1,5 kg,
    # quelques secondes perdues avec le cadre aéro (plus lourd, peu de vitesse).
    assert -40 < g_climber < -15
    assert 0 < g_aero < 15

    flat = climb_records(20000, 0.0, 250.0, base)
    f_climber = equipment_time_gain(flat, climber, base)
    f_aero = equipment_time_gain(flat, aero, base)
    # Plat de 20 km (≈ 30 min) : l'aéro gagne nettement, le grimpeur presque rien.
    assert -45 < f_aero < -15
    assert f_aero < f_climber <= 0
    assert abs(f_climber) < 5


def test_time_gain_segment(cat):
    base = PhysicsParams(mass_kg=75.0, cda_m2=0.32)
    climber = apply_equipment(base, loadout(frame="frame_climber"), cat)
    climb = climb_records(5000, 7.0, 250.0, base)
    whole = equipment_time_gain(climb, climber, base, s_start=0.0, s_end=4900.0)
    half = equipment_time_gain(climb, climber, base, s_start=2450.0, s_end=4900.0)
    assert half == pytest.approx(whole / 2, rel=0.15)
    assert equipment_time_gain(climb, climber, base, s_start=0.0, s_end=9000.0) is None


def test_time_gain_neutral_and_missing_data(cat):
    base = PhysicsParams(mass_kg=75.0, cda_m2=0.32)
    recs = climb_records(2000, 3.0, 200.0, base)
    assert equipment_time_gain(recs, apply_equipment(base, DEFAULT_EQUIPPED, cat), base) == 0.0
    no_power = [dict(r, power=None) for r in recs]
    assert equipment_time_gain(no_power, apply_equipment(base, loadout(frame="frame_aero"), cat), base) is None
    assert equipment_time_gain([], base, base) is None
