"""Lots AT2 et V6-r4 : biomes régionaux de `data/biome_zones.toml` (Atlantique et landes), même règle pour les parcours GPX et
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
    assert [r.biome for r in rules] == ["atlantic_heath", "japan",   # japan : lot JP2
                                        "cloud_forest", "temperate_rainforest", "eucalypt_woodland"]   # lot V6-r4
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


# --- Lot V6-r4 : forêt de nuages, forêt pluviale tempérée, bush à eucalyptus (cols de l'étude des biomes 6.0) ---

@pytest.mark.parametrize("name, lat, lon, biome", [
    ("Alto de la Línea", 4.48, -75.50, "cloud_forest"),
    ("Cerro de la Muerte", 9.56, -83.75, "cloud_forest"),
    ("Hurricane Ridge", 47.97, -123.50, "temperate_rainforest"),
    ("Mount Seymour", 49.37, -122.94, "temperate_rainforest"),
    ("Crown Range", -44.95, 168.95, "temperate_rainforest"),
    ("ouest de la Tasmanie", -42.10, 145.50, "temperate_rainforest"),
    ("Willunga Hill", -35.29, 138.55, "eucalypt_woodland"),
    ("Corkscrew Road", -34.88, 138.75, "eucalypt_woodland"),
    ("Mount Buller", -37.15, 146.44, "eucalypt_woodland"),
    ("Mount Hotham", -36.98, 147.13, "eucalypt_woodland"),
])
def test_rank4_cols_are_in_their_zone(name, lat, lon, biome):
    rules = B.biome_zones()[0]
    rule = B.regional_rule([lat], [lon]).tolist()[0]
    assert rule >= 0 and rules[rule].biome == biome, name


@pytest.mark.parametrize("lat, lon", [
    (4.60, -73.00),     # Llanos de Colombie (Aw, hors étage de montagne)
    (-12.40, 130.80),   # Darwin (Aw : la savane du nord de l'Australie reste savane)
    (-25.30, 131.00),   # Uluru (BWh : désert)
    (50.70, -120.30),   # Kamloops, intérieur sec de la Colombie-Britannique (hors rectangle côtier)
])
def test_rank4_neighbours_are_not(lat, lon):
    assert B.regional_rule([lat], [lon]).tolist() == [-1]


@pytest.mark.parametrize("lat, lon, cls, biome", [
    (4.48, -75.50, TREES, "cloud_forest"),
    (47.97, -123.50, TREES, "temperate_rainforest"),
    (-35.29, 138.55, TREES, "eucalypt_woodland"),
    (-35.29, 138.55, SHRUB, "eucalypt_woodland"),    # mallee
])
def test_rank4_classes(lat, lon, cls, biome):
    assert layer_at(lat, lon, cls).shares == {biome: 100.0}


@pytest.mark.parametrize("lat, lon, cls, biome", [
    (4.48, -75.50, GRASS, "cloud_forest"),            # prairies et páramo de l'étage gardent leur biome
    (47.97, -123.50, SHRUB, "temperate_rainforest"),
    (-35.29, 138.55, CROP, "eucalypt_woodland"),      # cultures
])
def test_rank4_other_classes_keep_their_biome(lat, lon, cls, biome):
    assert biome not in layer_at(lat, lon, cls).shares
