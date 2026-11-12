"""Lot U4 : variante régionale par tuile (table à grosse maille, option `--variant`), réseau coupé.

Points de test au degré entier ou au demi-degré, sans lieu réel visé.
"""

from __future__ import annotations

import json
import re
from importlib import resources

import numpy as np
import pytest
import tomllib
from conftest import straight_north
from openride_compiler import biomes as B
from openride_compiler import cli
from openride_compiler import regional as R
from openride_compiler.frame import LocalFrame
from openride_compiler.pipeline import biome_tile_keys
from openride_compiler.verify import biome_tile_problems, verify_world


def run(*argv):
    return cli.main([str(a) for a in argv])


def table_text() -> str:
    return resources.files("openride_compiler").joinpath("data/regional_variants.toml").read_text("utf-8")


def tiny_table(**extra):
    data = {"neutral": {"ground": "calcaire_blanc"},
            "rule": [{"name": "aride", "biomes": ["sand_desert", "rock_desert"], "min_share": 0.5,
                      "ground": "gres_rose", "roofs": "toit_plat_blanc"},
                     {"name": "nord", "abs_lat_min": 58, "ground": "granite_gris", "roofs": "bois"}],
            "zone": [{"name": "grande", "lat": [40, 50], "lon": [0, 10], "ground": "craie", "roofs": "ardoise"},
                     {"name": "petite", "lat": [44, 45], "lon": [4, 5], "ground": "basalte"}]}
    data.update(extra)
    return R.parse_table(data)


# Critère 2 : grosse maille ---------------------------------------------------------------------

def test_table_has_only_whole_degrees():
    text = table_text()
    for line in text.splitlines():
        code = line.split("#", 1)[0]
        if re.match(r"\s*(lat|lon|abs_lat_min|abs_lat_max)\s*=", code):
            assert "." not in code, line
    data = tomllib.loads(text)
    for zone in data["zone"]:
        for key in ("lat", "lon"):
            assert all(type(v) is int for v in zone[key]), zone["name"]
            assert zone[key][1] - zone[key][0] >= 1, zone["name"]
    for rule in data["rule"]:
        for key in ("abs_lat_min", "abs_lat_max"):
            if key in rule:
                assert type(rule[key]) is int
    table = R.load_table()                         # la table livrée se lit sans erreur
    assert len(table.zones) >= 10 and table.neutral == {"ground": "calcaire_blanc"}


def test_table_refuses_decimals_and_unknown_ids():
    with pytest.raises(ValueError, match="entiers"):
        R.parse_table({"zone": [{"name": "z", "lat": [44.5, 45], "lon": [4, 5], "ground": "craie"}]})
    with pytest.raises(ValueError, match="inconnu"):
        R.parse_table({"zone": [{"name": "z", "lat": [44, 45], "lon": [4, 5], "ground": "marbre"}]})
    with pytest.raises(ValueError, match="inconnue"):
        R.parse_table({"zone": [{"name": "z", "lat": [44, 45], "lon": [4, 5], "ground": "craie", "x": 1}]})
    with pytest.raises(ValueError, match="pas sous"):
        R.parse_table({"zone": [{"name": "z", "lat": [45, 45], "lon": [4, 5], "ground": "craie"}]})


# Critère 3 : règles générales et variante neutre --------------------------------------------------

def test_arid_point_gets_flat_white_roofs():
    v = R.variant_for(25.0, 30.0, {"sand_desert": 0.7, "steppe": 0.3}, tiny_table())
    assert v == {"ground": "gres_rose", "roofs": "toit_plat_blanc", "landscape": None}


def test_far_north_gets_wood():
    v = R.variant_for(62.0, 30.0, {"boreal_forest": 1.0}, tiny_table())
    assert v == {"ground": "granite_gris", "roofs": "bois", "landscape": None}


def test_outside_every_zone_is_neutral():
    v = R.variant_for(10.0, -60.0, {"jungle": 1.0}, tiny_table())
    assert v == {"ground": "calcaire_blanc", "roofs": None, "landscape": None}


def test_smallest_zone_wins_member_by_member():
    table = tiny_table()
    assert R.variant_for(44.5, 4.5, {}, table) == {"ground": "basalte", "roofs": "ardoise", "landscape": None}
    assert R.variant_for(47.0, 2.0, {}, table) == {"ground": "craie", "roofs": "ardoise", "landscape": None}
    assert R.variant_for(50.0, 2.0, {}, table) == {"ground": "calcaire_blanc", "roofs": None, "landscape": None}   # borne nord exclue


def test_shipped_rules():
    """Table livrée : règles du cahier (aride, nord, tropiques) ; toits laissés au biome hors des zones."""
    assert R.variant_for(25.0, 30.0, {"sand_desert": 0.8}) == {"ground": "gres_rose", "roofs": None, "landscape": None}
    assert R.variant_for(62.0, 30.0, {"boreal_forest": 1.0}) == {"ground": "granite_gris", "roofs": None, "landscape": None}
    assert R.variant_for(5.0, -60.0, {"jungle": 1.0}) == {"ground": "laterite_rouge", "roofs": None, "landscape": None}
    assert R.variant_for(-35.0, -60.0, {"steppe": 1.0}) == {"ground": "calcaire_blanc", "roofs": None, "landscape": None}
    assert R.variant_for(10.0, 40.0, {"volcanic": 0.6}) == {"ground": "basalte", "roofs": None, "landscape": None}
    assert R.variant_for(43.5, 5.5, {"mediterranean": 1.0}) == {"ground": "calcaire_blanc",
                                                                 "roofs": "tuile_ronde", "landscape": None}


# Tuiles : centre des tuiles proches, majorité dans les lointaines -----------------------------------

def straight_route(length=12000.0):
    s = np.arange(0.0, length + 1e-9, 25.0)
    return {"x": np.zeros_like(s).tolist(), "z": (-s).tolist(), "alt_m": [500.0] * len(s)}


def test_near_tile_center_and_far_majority():
    route = straight_route()
    frame = LocalFrame.at(46.0, 4.0)        # trace vers le nord depuis le bord sud d'une zone
    keys = biome_tile_keys(route)
    table = R.parse_table({"neutral": {"ground": "calcaire_blanc"},
                           "zone": [{"name": "z", "lat": [46, 47], "lon": [3, 5], "ground": "craie"}]})
    tiles = {level: B.forced_tiles(keys[level], "farmland") for level in ("near", "far")}
    R.assign_variants(tiles, {"near": 1000.0, "far": 5000.0}, frame.to_latlon, table=table)
    for (ix, iz), tile in tiles["near"].items():
        lat, _ = frame.to_latlon(np.array([(ix + 0.5) * 1000.0]), np.array([(iz + 0.5) * 1000.0]))
        expected = "craie" if 46 <= float(lat[0]) < 47 else "calcaire_blanc"
        assert tile["variant"] == {"ground": expected, "roofs": None, "landscape": None}
    grounds = {t["variant"]["ground"] for t in tiles["near"].values()}
    assert grounds == {"craie", "calcaire_blanc"}
    for (fx, fz), far in tiles["far"].items():
        inside = [t["variant"]["ground"] for (ix, iz), t in tiles["near"].items()
                  if (ix + 0.5) // 5 == fx and (iz + 0.5) // 5 == fz]
        if inside:   # majorité, à égalité le plus petit identifiant
            best = min(set(inside), key=lambda g: (-inside.count(g), g))
            assert far["variant"]["ground"] == best
        assert biome_tile_problems(far) == []


# Critères 4 et 5 : `--variant`, compilations identiques ---------------------------------------------

def load(world):
    return json.loads((world / "manifest.json").read_text(encoding="utf-8"))


def tiles_of(world):
    return {p.relative_to(world / "biome").as_posix(): json.loads(p.read_text())
            for p in sorted((world / "biome").rglob("*.json"))}


def test_forced_variant_everywhere(make_gpx, tmp_path, capsys):
    gpx = make_gpx("v.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path, "--biome", "alpine", "--variant", "basalte,ardoise") == 0
    world = tmp_path / "v.world"
    tiles = tiles_of(world)
    assert len(tiles) > 2
    assert all(t["variant"] == {"ground": "basalte", "roofs": "ardoise", "landscape": None} for t in tiles.values())
    assert verify_world(world) == []
    assert "variantes (imposées" in capsys.readouterr().err


def test_forced_variant_with_add_layer_and_empty_member(make_gpx, tmp_path):
    gpx = make_gpx("w.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path, "--biome", "farmland") == 0
    world = tmp_path / "w.world"
    # Trace de conftest près de 45° N 6° E : zone « alpes » de la table, toit laissé au biome.
    assert {json.dumps(t["variant"]) for t in tiles_of(world).values()} == {
        json.dumps({"ground": "schiste_sombre", "roofs": None, "landscape": None})}
    assert run("add-layer", world, "biome", "--biome", "farmland", "--variant", ",tuile_ronde") == 0
    assert all(t["variant"] == {"ground": None, "roofs": "tuile_ronde", "landscape": None} for t in tiles_of(world).values())
    assert verify_world(world) == []


@pytest.mark.parametrize("text", ["basalte", "marbre,ardoise", "basalte,chaume", ",", ",,", "a,b,c", "basalte,,lagon", "a,b,c,d"])
def test_bad_variant_is_an_input_error(make_gpx, tmp_path, text):
    gpx = make_gpx("x.gpx", *straight_north())
    with pytest.raises(SystemExit) as exc:
        run("build", gpx, "--out", tmp_path, "--biome", "alpine", "--variant", text)
    assert exc.value.code == 1


def test_two_builds_same_variants(make_gpx, tmp_path):
    gpx = make_gpx("deux.gpx", *straight_north())
    snaps = []
    for out in ("a", "b"):
        assert run("build", gpx, "--out", tmp_path / out, "--biome", "steppe") == 0
        snaps.append({k: t["variant"] for k, t in tiles_of(tmp_path / out / "deux.world").items()})
    assert snaps[0] == snaps[1]


def test_verify_catches_unknown_variant():
    tile = B.forced_tiles([(0, 0)], "alpine")[(0, 0)]
    tile["variant"] = {"ground": "marbre", "roofs": None}
    assert any("marbre" in p for p in biome_tile_problems(tile))
    tile["variant"] = {"ground": "craie"}
    assert any("variant" in p for p in biome_tile_problems(tile))
    tile["variant"] = {"ground": None, "roofs": None, "landscape": "lagon"}
    assert any("lagon" in p for p in biome_tile_problems(tile))
    tile["variant"] = {"ground": "craie", "roofs": None, "landscape": None, "x": 1}
    assert any("variant" in p for p in biome_tile_problems(tile))
    tile["variant"] = {"ground": "craie", "roofs": None}          # tuile écrite avant le lot U25
    assert biome_tile_problems(tile) == []
    tile["variant"] = None
    assert biome_tile_problems(tile) == []


# Lot U25 : paysages (canyons, fjords, îles volcaniques, rizières) ------------------------------------

def test_landscape_member_from_zones_only_member_by_member():
    table = tiny_table(zone=[{"name": "grande", "lat": [40, 50], "lon": [0, 10], "ground": "craie"},
                             {"name": "paysage", "lat": [44, 46], "lon": [4, 6], "landscape": "fjord"}])
    assert R.variant_for(45.0, 5.0, {}, table) == {"ground": "craie", "roofs": None, "landscape": "fjord"}
    assert R.variant_for(42.0, 5.0, {}, table)["landscape"] is None
    with pytest.raises(ValueError, match="inconnu"):
        R.parse_table({"zone": [{"name": "z", "lat": [44, 45], "lon": [4, 5], "landscape": "lagon"}]})


@pytest.mark.parametrize("lat, lon, shares, expected", [
    (62.0, 7.0, {"alpine": 1.0}, {"ground": "schiste_sombre", "roofs": "bois_peint", "landscape": "fjord"}),
    (68.0, 14.0, {"coast": 1.0}, {"ground": "schiste_sombre", "roofs": "bois_peint", "landscape": "fjord"}),
    (37.0, -111.0, {"rock_desert": 1.0}, {"ground": "gres_rose", "roofs": None, "landscape": "canyon"}),
    (28.0, -16.0, {"temperate_grassland": 1.0}, {"ground": "basalte", "roofs": None, "landscape": "ile_volcanique"}),
    (32.5, -17.0, {"temperate_forest": 1.0}, {"ground": "basalte", "roofs": None, "landscape": "ile_volcanique"}),
    (38.0, -28.0, {"temperate_grassland": 1.0}, {"ground": "basalte", "roofs": None, "landscape": "ile_volcanique"}),
    (16.0, 108.0, {"farmland": 1.0}, {"ground": "laterite_rouge", "roofs": None, "landscape": "rizieres"}),
    (-8.5, 115.0, {"farmland": 1.0}, {"ground": "laterite_rouge", "roofs": None, "landscape": "rizieres"}),
    (46.0, 7.0, {"alpine": 1.0}, {"ground": "schiste_sombre", "roofs": None, "landscape": None}),
])
def test_shipped_landscapes(lat, lon, shares, expected):
    """Table livrée : un point de chaque zone de paysage (degrés ronds), et les Alpes sans paysage."""
    assert R.variant_for(lat, lon, shares) == expected


def test_forced_landscape(make_gpx, tmp_path):
    gpx = make_gpx("p.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path, "--biome", "rock_desert", "--variant", "gres_rose,,canyon") == 0
    world = tmp_path / "p.world"
    assert all(t["variant"] == {"ground": "gres_rose", "roofs": None, "landscape": "canyon"}
               for t in tiles_of(world).values())
    assert verify_world(world) == []


def test_far_majority_counts_whole_variant():
    """Une tuile lointaine prend le triplet majoritaire (paysage compris) des tuiles proches."""
    table = R.parse_table({"neutral": {"ground": "craie"},
                           "zone": [{"name": "p", "lat": [44, 46], "lon": [4, 6], "landscape": "fjord"}]})
    near = {(k, 0): B.forced_tiles([(k, 0)], "coast")[(k, 0)] for k in range(5)}
    tiles = {"near": near, "far": B.forced_tiles([(0, 0)], "coast")}

    def to_latlon(x, z):   # trois tuiles proches dans la zone, deux dehors
        return np.full_like(x, 45.0), np.where(x < 3000.0, 5.0, 20.0)

    R.assign_variants(tiles, {"near": 1000.0, "far": 5000.0}, to_latlon, table=table)
    assert R.summary(near) == "craie/—/fjord 3, craie/—/— 2"
    assert tiles["far"][(0, 0)]["variant"] == {"ground": "craie", "roofs": None, "landscape": "fjord"}
