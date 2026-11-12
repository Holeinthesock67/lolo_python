"""Lot AT2 : biomes régionaux de `data/biome_zones.toml` (Atlantique et landes), même règle pour les parcours GPX et
le monde ouvert (classify_level).

Lieux publics connus (cols cités par l'étude des biomes de la 6.0), aucun accès réseau.
"""

from __future__ import annotations

import numpy as np
import pytest

from openride_compiler import biomes as B
from openride_compiler.frame import LocalFrame
from openride_compiler.pipeline import biome_tile_keys

TREES, SHRUB, GRASS, CROP, MOSS = 10, 20, 30, 40, 100


def test_table_is_valid():
    rules, zones = B.biome_zones()
    assert [r.biome for r in rules] == ["atlantic_heath", "japan"]   # japan : lot JP2
    assert all(r.biome in B.BIOMES and r.cls >= 202 and B.CLASS_BIOME[r.cls] == (r.biome,) * len(B.ZONES) for r in rules)
    assert len({r.cls for r in rules}) == len(rules)
    assert len({z.name for z in zones}) == len(zones) and {z.biome for z in zones} <= {r.biome for r in rules}
    assert all(-90 <= z.lat[0] < z.lat[1] <= 90 and -180 <= z.lon[0] < z.lon[1] <= 180 for z in zones)


@pytest.mark.parametrize("lat, lon", [
    (43.22, -5.93),    # Angliru
    (43.27, -4.98),    # Lagos de Covadonga
    (43.35, -1.85),    # Jaizkibel
    (48.20, -3.00),    # Mûr-de-Bretagne
    (57.42, -5.70),    # Bealach na Bà
    (54.40, -3.17),    # Hardknott Pass
    (52.18, -10.20),   # Conor Pass
])
def test_atlantic_cols_are_in_a_zone(lat, lon):
    assert B.regional_rule([lat], [lon]).tolist() == [0]


@pytest.mark.parametrize("lat, lon", [(48.85, 2.35), (40.40, -3.70), (37.40, -6.00), (45.06, 6.08), (35.36, 138.73)])
def test_other_places_are_not(lat, lon):
    # Paris (Cfb hors rectangle), Madrid, Séville, Alpe d'Huez, Fuji
    assert B.regional_rule([lat], [lon]).tolist() == [-1]


def test_koppen_code_must_be_in_the_list():
    # Un point d'un rectangle sous un climat hors liste (injecté) n'est pas régional
    assert B.regional_rule([43.22, 43.22], [-5.93, -5.93], codes=["Cfb", "BSk"]).tolist() == [0, -1]


def layer_at(lat, lon, cls, regional=None):
    s = np.arange(0.0, 3000.0 + 1e-9, 10.0)
    route = {"x": np.zeros_like(s).tolist(), "z": (-s).tolist(), "alt_m": [500.0] * len(s)}
    frame = LocalFrame.at(lat, lon)
    kw = {} if regional is None else {"regional": regional}
    inputs = B.Inputs(to_latlon=frame.to_latlon,
                      landcover=lambda la, lo: np.full(np.shape(la), cls, dtype=np.uint8), **kw)
    return B.build_biome_layer(biome_tile_keys(route), route["x"], route["z"], inputs=inputs)


@pytest.mark.parametrize("cls", [SHRUB, GRASS, MOSS])
def test_angliru_heath(cls):
    assert layer_at(43.22, -5.93, cls).shares == {"atlantic_heath": 100.0}


@pytest.mark.parametrize("cls, biome", [(TREES, "temperate_forest"), (CROP, "farmland")])
def test_forests_and_crops_keep_their_biome(cls, biome):
    assert layer_at(43.22, -5.93, cls).shares == {biome: 100.0}


def test_osm_heath_is_atlantic_in_a_zone_only():
    heath = B.osm_class({"natural": "heath"})
    assert B.regional_class(0, np.array([heath, TREES])).tolist() == [203, TREES]
    assert layer_at(48.85, 2.35, GRASS).shares == {"temperate_grassland": 100.0}   # Paris


def test_regional_rule_is_injectable():
    # Même règle que le monde ouvert : Inputs.regional remplace la table (ici : aucun biome régional)
    none = lambda la, lo: np.full(np.size(la), -1, dtype=np.int64)
    assert layer_at(43.22, -5.93, GRASS, regional=none).shares == {"temperate_grassland": 100.0}
