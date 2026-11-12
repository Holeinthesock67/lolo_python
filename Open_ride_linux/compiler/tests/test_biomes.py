"""Lot U2 : classification des biomes et option `--biome` (critères 2 à 8 du cahier), réseau coupé.

Petites grilles WorldCover générées ici (fonctions de la latitude et de la longitude) ; latitudes de test
au degré entier, sans lieu réel visé.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from conftest import ORIGIN, FakeLandcover, straight_north
from openride_compiler import biomes as B
from openride_compiler import cli
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.frame import LocalFrame
from openride_compiler.landcover import Window, WorldCoverSource
from openride_compiler.pipeline import biome_tile_keys
from openride_compiler.verify import biome_tile_problems, verify_world

TREES, CROP, GRASS, WATER = 10, 40, 30, 80


def run(*argv):
    return cli.main([str(a) for a in argv])


def straight_route(length=3000.0):
    s = np.arange(0.0, length + 1e-9, 10.0)
    return {"x": np.zeros_like(s).tolist(), "z": (-s).tolist(), "alt_m": [500.0] * len(s)}


def latitude_bands(lat, lon):
    """Climat de test : bandes de latitude seules (les latitudes de test ne visent aucun lieu réel)."""
    return B.latitude_zone_weights(lat)


def no_volcano(lat, lon):
    return np.zeros(np.size(lat), dtype=bool)


def layer_at(lat, landcover=None, elevation=None, osm=None, route=None):
    route = route or straight_route()
    frame = LocalFrame.at(lat, 7.0)
    keys = biome_tile_keys(route)
    inputs = B.Inputs(to_latlon=frame.to_latlon, landcover=landcover, elevation=elevation, osm=osm or (),
                      zones=latitude_bands, volcanic=no_volcano)
    return B.build_biome_layer(keys, route["x"], route["z"], inputs=inputs, sources=["test"]), frame


def const(cls):
    return lambda lat, lon: np.full(np.shape(lat), cls, dtype=np.uint8)


def full(tile):
    return {b: np.asarray(g).reshape(17, 17) for b, g in zip(tile["biomes"], tile["weights"])}


def check_tiles(tiles):
    """Critère 5 : somme 255 partout, 4 biomes au plus, bords communs identiques."""
    for (ix, iz), tile in tiles.items():
        assert biome_tile_problems(tile) == []
        g = full(tile)
        for (dx, dz), ea, eb in (((1, 0), lambda a: a[:, -1], lambda b: b[:, 0]),
                                 ((0, 1), lambda a: a[-1, :], lambda b: b[0, :])):
            other = tiles.get((ix + dx, iz + dz))
            if other is None:
                continue
            h = full(other)
            for b in set(g) | set(h):
                za = ea(g[b]) if b in g else np.zeros(17)
                zb = eb(h[b]) if b in h else np.zeros(17)
                assert np.array_equal(za, zb), ((ix, iz), (dx, dz), b)


# Critère 2 : cultures, vignes ---------------------------------------------------------------

def test_cropland_at_46_is_farmland():
    layer, _ = layer_at(46.0, landcover=const(CROP))
    assert layer.shares["farmland"] > 90.0
    for level in ("near", "far"):
        for tile in layer.tiles[level].values():
            assert tile["biomes"] == ["farmland"]


def test_vineyard_on_a_quarter_stays_farmland():
    route = straight_route()
    # Un quart de l'emprise proche (à l'est de la route, moitié nord) en vigne, sur fond de prairie.
    vineyard = B.OsmArea(B.osm_class({"landuse": "vineyard"}),
                         [[0.0, -3000.0], [1500.0, -3000.0], [1500.0, -1500.0], [0.0, -1500.0]])
    crops, _ = layer_at(46.0, landcover=const(CROP), osm=[vineyard], route=route)
    assert crops.shares == {"farmland": 100.0}
    grass, _ = layer_at(46.0, landcover=const(GRASS), osm=[vineyard], route=route)
    assert set(grass.shares) == {"farmland", "temperate_grassland"}
    assert 20.0 < grass.shares["farmland"] < 80.0
    assert abs(sum(grass.shares.values()) - 100.0) <= 0.2


# Critère 3 : arbres selon la latitude ---------------------------------------------------------

@pytest.mark.parametrize("lat, biome", [(46.0, "temperate_forest"), (64.0, "boreal_forest"),
                                        (-46.0, "temperate_forest"), (5.0, "jungle")])
def test_trees_follow_climate_zone(lat, biome):
    layer, _ = layer_at(lat, landcover=const(TREES))
    assert layer.shares == {biome: 100.0}


def test_latitude_bands_sum_to_one_and_blend_at_limits():
    lat = np.linspace(-90, 90, 721)
    w = B.latitude_zone_weights(lat)
    assert np.allclose(w.sum(axis=1), 1.0) and (w >= 0).all()
    assert B.ZONES[int(np.argmax(B.latitude_zone_weights([46.0])[0]))] == "temperate"
    mid = B.latitude_zone_weights([B.ZONE_LIMITS_DEG[3]])[0]
    assert mid[3] == pytest.approx(0.5) and mid[4] == pytest.approx(0.5)


def test_climate_map_zones_sum_to_one_everywhere():
    lat, lon = np.meshgrid(np.linspace(-89.9, 89.9, 181), np.linspace(-179.9, 179.9, 361))
    w = B.zone_weights(lat.ravel(), lon.ravel())
    assert w.shape == (lat.size, len(B.ZONES))
    assert np.allclose(w.sum(axis=1), 1.0) and (w >= 0).all()


# Critère 4 : altitude --------------------------------------------------------------------------

def test_alpine_share_grows_with_altitude_at_45():
    route = straight_route(6000.0)

    def relief(lat, lon):          # 600 m au départ, 2 600 m à 6 km au nord
        return 600.0 + (np.asarray(lat) - 45.0) * 111_000.0 / 3.0

    layer, frame = layer_at(45.0, landcover=const(GRASS), elevation=relief, route=route)
    alts, alpine = [], []
    for (ix, iz), tile in layer.tiles["near"].items():
        g = full(tile)
        k = np.arange(17) * B.NEAR.cell_m
        gx, gz = np.meshgrid(ix * B.NEAR.tile_m + k, iz * B.NEAR.tile_m + k)
        lat, lon = frame.to_latlon(gx.ravel(), gz.ravel())
        alts.append(relief(lat, lon))
        alpine.append(g.get("alpine", np.zeros((17, 17))).ravel())
    alts, alpine = np.concatenate(alts), np.concatenate(alpine)
    assert alpine[alts < 1500.0].max() == 0
    assert alpine[alts > 2450.0].min() == 255
    order = np.argsort(alts)
    assert (np.diff(alpine[order].astype(int)) >= -1).all()     # croissante (à l'arrondi près)
    assert 0 < layer.shares["alpine"] < 100
    check_tiles(layer.tiles["near"])


def test_alpine_line_depends_on_latitude():
    assert B.alpine_line_m(45.0) == 1800.0
    assert B.alpine_line_m(35.0) > B.alpine_line_m(45.0) > B.alpine_line_m(60.0)
    assert B.alpine_part(np.array([1499.0, np.nan]), np.array([45.0, 45.0])).tolist() == [0.0, 0.0]


# Critère 5 : tuiles voisines, sommes, quatre biomes ------------------------------------------

def test_mosaic_keeps_rules_on_shared_edges():
    def mosaic(lat, lon):          # damier serré de huit classes : bien plus de quatre biomes en jeu
        classes = np.array([10, 20, 30, 40, 60, 70, 90, 100], dtype=np.uint8)
        k = (np.floor(np.asarray(lat) * 300).astype(int) * 7 + np.floor(np.asarray(lon) * 300).astype(int) * 3)
        return classes[k % len(classes)]

    route = straight_route(4000.0)
    route["x"] = (300.0 * np.sin(np.asarray(route["z"]) / 500.0)).tolist()
    for lat in (35.0, 44.0, 64.0):
        layer, _ = layer_at(lat, landcover=mosaic, route=route)
        for level in ("near", "far"):
            check_tiles(layer.tiles[level])
        assert any(len(t["biomes"]) == 4 for t in layer.tiles["near"].values())


def test_water_only_falls_back_to_zone_grassland():
    layer, _ = layer_at(46.0, landcover=const(WATER))
    assert layer.shares == {"temperate_grassland": 100.0}


# Critère 6 : --biome ---------------------------------------------------------------------------

@pytest.fixture
def no_landcover(monkeypatch):
    def refuse(offline, log=None):
        raise AssertionError("WorldCover ne doit pas être consulté avec --biome")
    monkeypatch.setattr(cli, "make_landcover", refuse)
    monkeypatch.setattr(cli, "make_biome_osm_client", refuse)


def load(world):
    return json.loads((world / "manifest.json").read_text(encoding="utf-8"))


def test_forced_biome_everywhere(no_landcover, make_gpx, tmp_path, capsys):
    gpx = make_gpx("force.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path, "--biome", "savanna") == 0
    world = tmp_path / "force.world"
    m = load(world)["layers"]["biome"]
    assert m["forced"] == "savanna" and m["default_biome"] == "savanna"
    assert m["shares"] == {"savanna": 100.0} and m["sources"] == ["forced"]
    for level in ("near", "far"):
        assert m["tiles"][level] == load(world)["layers"]["terrain"]["tiles"][level]
        for ix, iz in m["tiles"][level]:
            tile = json.loads((world / "biome" / level / f"tile_{ix}_{iz}.json").read_text())
            assert tile["biomes"] == ["savanna"] and set(tile["weights"][0]) == {255}
    assert verify_world(world) == []
    assert "imposé : savanna" in capsys.readouterr().err


def test_forced_biome_with_add_layer_and_build_all(no_landcover, make_gpx, tmp_path):
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    make_gpx("gpx/a.gpx", *straight_north())
    assert run("build-all", "--gpx-dir", gpx_dir, "--routes-dir", tmp_path / "r", "--biome", "polar") == 0
    assert load(tmp_path / "r" / "a.world")["layers"]["biome"]["forced"] == "polar"
    assert run("add-layer", tmp_path / "r" / "a.world", "biome", "--biome", "alpine") == 0
    m = load(tmp_path / "r" / "a.world")["layers"]["biome"]
    assert m["forced"] == "alpine" and m["shares"] == {"alpine": 100.0}
    assert verify_world(tmp_path / "r" / "a.world") == []


def test_unknown_biome_is_an_input_error(make_gpx, tmp_path):
    gpx = make_gpx("x.gpx", *straight_north())
    with pytest.raises(SystemExit) as exc:
        run("build", gpx, "--out", tmp_path, "--biome", "prairie")
    assert exc.value.code == 1


# Critère 7 : hors ligne, sans réseau -----------------------------------------------------------

def failing_reader(url, s, w, n, e):
    raise OSError("réseau coupé")


def test_offline_without_cache_fails_clearly(monkeypatch, make_gpx, tmp_path, capsys):
    monkeypatch.setattr(cli, "make_landcover", lambda offline, log=None: WorldCoverSource(
        cache_dir=tmp_path / "lc", offline=offline, reader=failing_reader, log=lambda m: None))
    gpx = make_gpx("hl.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path, "--offline") == 1
    err = capsys.readouterr().err
    assert "WorldCover absente du cache" in err and "--offline" in err
    assert not (tmp_path / "hl.world").exists()


def test_no_network_falls_back_with_warning(monkeypatch, make_gpx, tmp_path, capsys):
    monkeypatch.setattr(cli, "make_landcover", lambda offline, log=None: WorldCoverSource(
        cache_dir=tmp_path / "lc", offline=offline, reader=failing_reader, sleep=lambda s: None,
        log=lambda m: None))
    gpx = make_gpx("repli.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path) == 0
    world = tmp_path / "repli.world"
    assert verify_world(world) == []
    m = load(world)["layers"]["biome"]
    assert m["sources"] == ["dem", "koppen_1986_2010"] and m["forced"] is None
    assert "attribution" not in m
    assert sum(m["shares"].values()) == pytest.approx(100.0, abs=0.2)
    assert "avertissement : occupation du sol indisponible" in capsys.readouterr().err


# Critère 8 et chaîne complète --------------------------------------------------------------------

class FakeOverpass:
    """Réponse Overpass fabriquée : un vignoble au nord-est du départ."""

    def __init__(self):
        lat0, lon0 = ORIGIN
        ring = [(lat0 + 0.005, lon0), (lat0 + 0.005, lon0 + 0.01), (lat0 + 0.015, lon0 + 0.01),
                (lat0 + 0.015, lon0), (lat0 + 0.005, lon0)]
        self.response = {"elements": [{"type": "way", "id": 7, "tags": {"landuse": "vineyard"},
                                       "geometry": [{"lat": a, "lon": o} for a, o in ring]}]}
        self.calls = 0

    def fetch_biome_for_route(self, route, frame):
        self.calls += 1
        return [self.response, self.response]     # deux tronçons : le doublon est fusionné


def test_full_build_twice_is_bit_identical(monkeypatch, make_gpx, tmp_path, capsys):
    forest_west = FakeLandcover(lambda lat, lon: np.where(lon < ORIGIN[1] - 0.003, TREES, GRASS))
    osm = FakeOverpass()
    monkeypatch.setattr(cli, "make_landcover", lambda offline, log=None: forest_west)
    monkeypatch.setattr(cli, "make_biome_osm_client", lambda offline, log=None: osm)
    monkeypatch.setattr(cli, "make_provider", lambda offline, log=None: SyntheticProvider(
        *ORIGIN, lambda x, z: 1000.0 - 0.05 * np.asarray(z) + 0.0 * np.asarray(x)))
    gpx = make_gpx("deux.gpx", *straight_north())
    snapshots = []
    for out in ("a", "b"):
        assert run("build", gpx, "--out", tmp_path / out) == 0
        world = tmp_path / out / "deux.world"
        assert verify_world(world) == []
        snapshots.append({p.relative_to(world / "biome").as_posix(): p.read_bytes()
                          for p in sorted((world / "biome").rglob("*.json"))})
    assert snapshots[0] == snapshots[1] and len(snapshots[0]) > 10
    m = load(tmp_path / "a" / "deux.world")["layers"]["biome"]
    assert m["sources"] == ["esa_worldcover_2021", "osm", "dem", "koppen_1986_2010"]
    assert "CC BY 4.0" in m["attribution"]
    assert {"temperate_grassland", "farmland"} <= set(m["shares"])
    err = capsys.readouterr().err
    assert "biomes (sources : esa_worldcover_2021, osm, dem, koppen_1986_2010" in err
    all_tiles = {}
    for name, data in snapshots[0].items():
        level, fname = name.split("/")[0], name.split("/")[1]
        ix, iz = (int(v) for v in fname[5:-5].split("_"))
        all_tiles.setdefault(level, {})[(ix, iz)] = json.loads(data)
    for tiles in all_tiles.values():
        check_tiles(tiles)


def test_near_tile_is_small(monkeypatch, make_gpx, tmp_path):
    gpx = make_gpx("petit.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path) == 0
    sizes = [p.stat().st_size for p in (tmp_path / "petit.world" / "biome" / "near").iterdir()]
    assert sizes and max(sizes) < 8 * 1024


def test_verify_catches_broken_biome_tile(make_gpx, tmp_path):
    gpx = make_gpx("casse.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path) == 0
    world = tmp_path / "casse.world"
    tile_path = next((world / "biome" / "near").iterdir())
    tile = json.loads(tile_path.read_text())
    tile["weights"][0][5] -= 1
    tile_path.write_text(json.dumps(tile))
    problems = verify_world(world)
    assert any("somme des poids diffère de 255" in p for p in problems)
    tile_path.unlink()
    assert any("tuile listée absente" in p for p in verify_world(world))


def test_default_build_has_biome_layer_and_info(make_gpx, tmp_path, capsys):
    gpx = make_gpx("defaut.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path) == 0
    out = capsys.readouterr().out
    assert "couches route,terrain,biome,segments" in out
    assert run("info", tmp_path / "defaut.world") == 0
    assert "Biomes            : temperate_grassland 100,0 %" in capsys.readouterr().out


def test_layers_without_biome_skip_it(no_landcover, make_gpx, tmp_path):
    gpx = make_gpx("sans.gpx", *straight_north())
    assert run("build", gpx, "--out", tmp_path, "--layers", "route,terrain") == 0
    assert "biome" not in load(tmp_path / "sans.world")["layers"]
    assert not (tmp_path / "sans.world" / "biome").exists()


def test_window_lookup_clamps_to_square():
    win = Window(np.array([[10, 20], [30, 40]], dtype=np.uint8), 6.0, 45.1, 0.05, 0.05)
    assert win.lookup(np.array([45.09, 45.01, 44.0]), np.array([6.01, 6.09, 7.0])).tolist() == [10, 40, 40]
