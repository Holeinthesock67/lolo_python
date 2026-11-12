"""Lot JP2 (version 6.0) : pose du biome `japan` (zone Japon × climat de Köppen × arbres et arbustes WorldCover)
et toit `kawara` des variantes régionales. Lieux publics connus, aucun accès réseau."""

from __future__ import annotations

import numpy as np
import pytest

from openride_compiler import biomes as B
from openride_compiler import regional
from openride_compiler.frame import LocalFrame
from openride_compiler.pipeline import biome_tile_keys

TREES, SHRUB, GRASS, CROP, BARE = 10, 20, 30, 40, 60


def layer_at(lat, lon, cls):
    s = np.arange(0.0, 3000.0 + 1e-9, 10.0)
    route = {"x": np.zeros_like(s).tolist(), "z": (-s).tolist(), "alt_m": [500.0] * len(s)}
    inputs = B.Inputs(to_latlon=LocalFrame.at(lat, lon).to_latlon,
                      landcover=lambda la, lo: np.full(np.shape(la), cls, dtype=np.uint8))
    return B.build_biome_layer(biome_tile_keys(route), route["x"], route["z"], inputs=inputs)


@pytest.mark.parametrize("lat, lon, inside", [
    (35.23, 139.07, True),      # Hakone (Cfa)
    (35.36, 138.80, True),      # Fuji Azami Line (Cfb)
    (36.65, 138.19, True),      # Nagano (Dfa)
    (43.06, 141.35, True),      # Sapporo (Dfa / Dfb)
    (33.59, 130.40, True),      # Fukuoka (Cfa)
    (26.21, 127.68, False),     # Naha, Okinawa : subtropical, hors des rectangles
    (35.10, 129.04, False),     # Busan, Corée
    (37.57, 126.98, False),     # Séoul
    (43.12, 131.89, False),     # Vladivostok
    (48.85, 2.35, False),       # Paris
    (36.0, 138.0, True),        # coin d'un rectangle : borne sud et ouest comprises
])
def test_japan_zone_at_known_places(lat, lon, inside):
    assert B.in_japan_zone([lat], [lon]).tolist() == [inside]


def test_japan_zone_table_is_valid():
    zone = B.japan_zone()
    assert zone.climates == {"Cfa", "Cfb", "Dfa", "Dfb"}
    for name, (s, n), (w, e) in zone.boxes:
        assert -90 <= s < n <= 90 and -180 <= w < e <= 180, name


def test_forests_and_shrubs_of_japan_are_japan():
    assert layer_at(35.23, 139.07, TREES).shares == {"japan": 100.0}       # Hakone
    assert layer_at(35.36, 138.80, SHRUB).shares == {"japan": 100.0}       # Fuji, flanc est


@pytest.mark.parametrize("cls, biome", [(CROP, "farmland"), (GRASS, "temperate_grassland")])
def test_other_land_of_japan_keeps_its_biome(cls, biome):
    assert layer_at(35.23, 139.07, cls).shares == {biome: 100.0}


def test_bare_ground_of_fuji_stays_volcanic():
    assert layer_at(35.36, 138.73, BARE).shares == {"volcanic": 100.0}


def test_forests_outside_japan_are_unchanged():
    assert layer_at(37.57, 126.98, TREES).shares == {"temperate_forest": 100.0}   # Séoul
    assert layer_at(47.8, 6.8, TREES).shares == {"temperate_forest": 100.0}       # Ballon d'Alsace


def test_japan_can_be_turned_off_by_injection():
    s = np.arange(0.0, 3000.0 + 1e-9, 10.0)
    route = {"x": np.zeros_like(s).tolist(), "z": (-s).tolist(), "alt_m": [500.0] * len(s)}
    inputs = B.Inputs(to_latlon=LocalFrame.at(35.23, 139.07).to_latlon,
                      landcover=lambda la, lo: np.full(np.shape(la), TREES, dtype=np.uint8),
                      japan=lambda la, lo: np.zeros(np.size(la), dtype=bool))
    layer = B.build_biome_layer(biome_tile_keys(route), route["x"], route["z"], inputs=inputs)
    assert layer.shares == {"temperate_forest": 100.0}


def test_regional_kawara_zones_match_the_japan_zone():
    table = regional.load_table()
    kawara = sorted((z.lat, z.lon) for z in table.zones if z.values.get("roofs") == "kawara")
    assert kawara == sorted((lat, lon) for _, lat, lon in B.japan_zone().boxes)
    assert regional.variant_for(35.23, 139.07, {"japan": 1.0}, table) == {"ground": "basalte", "roofs": "kawara"}
    assert regional.variant_for(35.10, 129.04, {"temperate_forest": 1.0}, table).get("roofs") != "kawara"
