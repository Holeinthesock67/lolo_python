"""Lot U24 : zone climatique des biomes tirée de la carte de Köppen-Geiger embarquée, paysages volcaniques.

Lieux publics connus (cols du pack, grandes régions), aucun accès réseau.
"""

from __future__ import annotations

import numpy as np
import pytest

from openride_compiler import biomes as B
from openride_compiler import koppen as K
from openride_compiler.frame import LocalFrame
from openride_compiler.pipeline import biome_tile_keys

BARE, TREES, GRASS = 60, 10, 30


def main_zone(lat, lon):
    return B.ZONES[int(np.argmax(B.zone_weights([lat], [lon])[0]))]


def test_map_shape_and_codes():
    g = K.grid()
    assert g.shape == (K.HEIGHT, K.WIDTH) and g.dtype == np.uint8
    assert set(np.unique(g).tolist()) <= set(range(1, len(K.CODES) + 1)) | {K.OCEAN}
    assert set(K.ZONE_OF) == set(K.CODES) and set(K.ZONE_OF.values()) == set(K.ZONES)


@pytest.mark.parametrize("lat, lon, zone", [
    (-3.0, -60.0, "tropical"),          # Amazonie
    (23.0, 5.0, "arid"),                # Sahara
    (37.4, -6.0, "warm"),               # Séville (Csa)
    (43.2, -5.9, "temperate"),          # Angliru, Asturies (Csb et Cfb : végétation atlantique)
    (47.8, 6.8, "temperate"),           # Ballon d'Alsace (Cfb)
    (35.45, 138.78, "temperate"),       # pied nord du Fuji (Cfb)
    (62.0, 100.0, "boreal"),            # Sibérie centrale
    (78.0, 16.0, "polar"),              # Svalbard
])
def test_main_zone_at_known_places(lat, lon, zone):
    assert main_zone(lat, lon) == zone


def test_mountain_tundra_counts_as_boreal():
    assert K.codes([45.83], [6.86]) == ["ET"]            # Mont Blanc
    w = B.zone_weights([45.83], [6.86])[0]
    assert w[B.ZONES.index("polar")] == 0.0 and w[B.ZONES.index("boreal")] > 0.5


def test_open_sea_falls_back_to_latitude_bands():
    assert K.codes([30.0], [-40.0]) == [None]
    assert np.allclose(B.zone_weights([30.0], [-40.0]), B.latitude_zone_weights([30.0]))


def test_longitude_wraps_and_latitude_is_clamped():
    assert K.pixel([0.0], [180.0])[1][0] == K.pixel([0.0], [-180.0])[1][0] == 0
    assert K.pixel([90.0, -90.0], [0.0, 0.0])[0].tolist() == [0, K.HEIGHT - 1]


def test_volcanic_table_is_valid_and_located():
    areas = B.volcanic_areas()
    assert len(areas) >= 20 and len({a.name for a in areas}) == len(areas)
    assert all(-90 <= a.lat <= 90 and -180 <= a.lon <= 180 and 0 < a.radius_km <= 300 for a in areas)
    inside = B.in_volcanic_area([28.27, 35.36, 48.85, 47.82], [-16.64, 138.73, 2.35, 6.84])
    assert inside.tolist() == [True, True, False, False]   # Teide, Fuji, Paris, Ballon d'Alsace


def layer_at(lat, lon, cls):
    s = np.arange(0.0, 3000.0 + 1e-9, 10.0)
    route = {"x": np.zeros_like(s).tolist(), "z": (-s).tolist(), "alt_m": [500.0] * len(s)}
    frame = LocalFrame.at(lat, lon)
    inputs = B.Inputs(to_latlon=frame.to_latlon,
                      landcover=lambda la, lo: np.full(np.shape(la), cls, dtype=np.uint8))
    return B.build_biome_layer(biome_tile_keys(route), route["x"], route["z"], inputs=inputs)


def test_bare_ground_of_a_volcano_is_volcanic():
    assert layer_at(28.22, -16.66, BARE).shares == {"volcanic": 100.0}      # Las Cañadas
    assert "volcanic" not in layer_at(23.0, 5.0, BARE).shares              # Sahara : désert


def test_volcano_keeps_its_forests():
    assert "volcanic" not in layer_at(28.22, -16.66, TREES).shares


def test_galicia_trees_are_not_mediterranean():
    assert layer_at(42.9, -8.5, TREES).shares == {"temperate_forest": 100.0}   # Saint-Jacques-de-Compostelle
    assert layer_at(37.4, -6.0, TREES).shares == {"mediterranean": 100.0}      # Séville


def test_osm_sand_of_a_volcano_is_volcanic():
    s = np.arange(0.0, 3000.0 + 1e-9, 10.0)
    route = {"x": np.zeros_like(s).tolist(), "z": (-s).tolist(), "alt_m": [500.0] * len(s)}
    frame = LocalFrame.at(28.22, -16.66)                                   # Las Cañadas
    sand = B.OsmArea(B.osm_class({"natural": "sand"}),
                     [[-5000.0, -8000.0], [5000.0, -8000.0], [5000.0, 5000.0], [-5000.0, 5000.0]])
    inputs = B.Inputs(to_latlon=frame.to_latlon, osm=[sand],
                      landcover=lambda la, lo: np.full(np.shape(la), BARE, dtype=np.uint8))
    layer = B.build_biome_layer(biome_tile_keys(route), route["x"], route["z"], inputs=inputs)
    assert layer.shares == {"volcanic": 100.0}
