"""Lot B2 : couche terrain (critères 2 à 7), avec le MNT synthétique, sans réseau."""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np
import pytest

from conftest import ORIGIN, circle, require_core, straight_north
from openride_compiler import cli
from openride_compiler import constants as C
from openride_compiler.elevation import SyntheticProvider, default_relief
from openride_compiler.frame import LocalFrame
from openride_compiler.terrain import (FAR, NEAR, TILE_BYTES, RouteAxis, blend, build_terrain,
                                       read_tile, select_tiles, tile_coords, tile_filename)


def run(*argv):
    return cli.main([str(a) for a in argv])


@pytest.fixture
def relief(monkeypatch):
    """La CLI utilise le relief synthétique du lot (1000 + 200·sin(x/700)·cos(z/900))."""
    monkeypatch.setattr(cli, "make_provider",
                        lambda offline, log=None: SyntheticProvider(*ORIGIN, default_relief))


@pytest.fixture
def world(relief, make_gpx, tmp_path):
    """Trace sans altitude (l'altitude vient donc du MNT synthétique), couches route et terrain."""
    x, z, _ = straight_north(length=3000.0)
    xs = x + 150.0 * np.sin(-z / 600.0)               # un peu sinueuse
    gpx = make_gpx("relief.gpx", xs, z)
    assert run("build", gpx, "--out", tmp_path / "routes") == 0
    return tmp_path / "routes" / "relief.world"


def load(world):
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    return manifest, route


def tiles_of(world, level):
    return {tuple(t): read_tile(world / "terrain" / level / tile_filename(*t))
            for t in load(world)[0]["layers"]["terrain"]["tiles"][level]}


# Manifeste --------------------------------------------------------------------------------

def test_manifest_terrain_block(world):
    manifest, _ = load(world)
    t = manifest["layers"]["terrain"]
    assert t["present"] is True and t["version"] == "1.0"
    assert t["sources"] == ["synthetic"]
    assert t["near_cell_m"] == 10 and t["far_cell_m"] == 50
    assert len(t["tiles"]["near"]) > 0 and len(t["tiles"]["far"]) > 0
    assert manifest["route"]["alt_source"] == "synthetic"
    assert manifest["format_version"] == "1.5"


# Critère 2 : tuile proche ------------------------------------------------------------------

def test_near_tile_size_and_values(world):
    _, route = load(world)
    axis = RouteAxis(route["x"], route["z"], route["alt_m"])
    checked = 0
    for (ix, iz), grid in tiles_of(world, "near").items():
        path = world / "terrain" / "near" / tile_filename(ix, iz)
        assert path.stat().st_size == TILE_BYTES == 40804
        gx, gz = tile_coords(ix, iz, NEAR)
        assert gx[0, 7] == ix * 1000 + 7 * 10 and gz[5, 0] == iz * 1000 + 5 * 10   # (i, j) = (colonne, ligne)
        dist, _ = axis.nearest(gx, gz, C.ROAD_HALF_WIDTH_M + C.BLEND_OUTER_M)
        outside = ~np.isfinite(dist.reshape(gx.shape))
        expected = default_relief(gx, gz)
        assert np.all(np.abs(grid[outside] - expected[outside]) < 0.01)
        checked += int(outside.sum())
    assert checked > 100_000


def test_far_tile_values(world):
    for (ix, iz), grid in tiles_of(world, "far").items():
        gx, gz = tile_coords(ix, iz, FAR)
        assert np.all(np.abs(grid - default_relief(gx, gz)) < 0.01)


def test_tile_bytes_little_endian_row_major(world):
    (ix, iz), grid = next(iter(tiles_of(world, "far").items()))
    raw = (world / "terrain" / "far" / tile_filename(ix, iz)).read_bytes()
    i, j = 37, 61
    value = np.frombuffer(raw[(j * 101 + i) * 4:(j * 101 + i) * 4 + 4], dtype="<f4")[0]
    assert abs(value - default_relief(ix * 5000.0 + i * 50, iz * 5000.0 + j * 50)) < 0.01


# Critère 3 : bords partagés ----------------------------------------------------------------

@pytest.mark.parametrize("level", ["near", "far"])
def test_shared_edges_byte_equal(world, level):
    grids = tiles_of(world, level)
    pairs = 0
    for (ix, iz), g in grids.items():
        if (ix + 1, iz) in grids:
            assert g[:, 100].tobytes() == grids[(ix + 1, iz)][:, 0].tobytes()
            pairs += 1
        if (ix, iz + 1) in grids:
            assert g[100, :].tobytes() == grids[(ix, iz + 1)][0, :].tobytes()
            pairs += 1
    assert pairs > 0


# Critère 4 : fondu ---------------------------------------------------------------------------

def test_blend_function():
    y_mnt = np.array([500.0, 500.0, 500.0, 500.0, 500.0, np.nan, np.nan])
    y_road = np.full(7, 520.0)
    axis_dist = np.array([5.0, 33.0, 7.0, 17.5, np.inf, 5.0, 40.0])   # ruban : distance − 3 m
    y = blend(y_mnt, axis_dist, y_road)
    assert abs(y[0] - (520.0 - 0.05)) < 0.01            # 2 m du ruban
    assert abs(y[1] - 500.0) < 0.01                     # 30 m du ruban
    assert abs(y[2] - (520.0 - 0.05)) < 0.01            # 4 m : encore la route
    assert abs(y[3] - (0.5 * (520.0 - 0.05) + 0.5 * 500.0)) < 0.01   # milieu : smoothstep(0,5) = 0,5
    assert y[4] == 500.0
    assert y[5] == pytest.approx(519.95)                # MNT inconnu près de la route : la route
    assert np.isnan(y[6])


def test_route_axis_distance_between_vertices():
    axis = RouteAxis([0.0, 0.0, 0.0], [0.0, -10.0, -20.0], [100.0, 101.0, 102.0])
    d, y = axis.nearest(np.array([5.0, -7.0, 50.0]), np.array([-5.0, -15.0, -5.0]), 28.0)
    assert d[0] == pytest.approx(5.0) and y[0] == pytest.approx(100.5)
    assert d[1] == pytest.approx(7.0) and y[1] == pytest.approx(101.5)
    assert np.isinf(d[2]) and np.isnan(y[2])


def test_blend_in_tiles(world):
    """Sur le ruban, le terrain suit la route (− 5 cm) ; à plus de 25 m du ruban, le MNT."""
    _, route = load(world)
    axis = RouteAxis(route["x"], route["z"], route["alt_m"])
    on_road = far_off = 0
    for (ix, iz), grid in tiles_of(world, "near").items():
        gx, gz = tile_coords(ix, iz, NEAR)
        dist, y_route = axis.nearest(gx.ravel(), gz.ravel(), 60.0)
        d = dist - C.ROAD_HALF_WIDTH_M
        g = grid.ravel().astype(float)
        mnt = default_relief(gx.ravel(), gz.ravel())
        near = d <= 4.0
        assert np.all(np.abs(g[near] - (y_route[near] - 0.05)) < 0.01)
        ring = (d >= 27.0) & (d <= 33.0)
        assert np.all(np.abs(g[ring] - mnt[ring]) < 0.01)
        on_road += int(near.sum())
        far_off += int(ring.sum())
    assert on_road > 50 and far_off > 50


# Critère 5 : couverture ----------------------------------------------------------------------

@pytest.mark.parametrize("level", [NEAR, FAR], ids=["near", "far"])
def test_coverage(world, level):
    _, route = load(world)
    keys = set(tiles_of(world, level.name))
    x, z = np.array(route["x"]), np.array(route["z"])
    angles = np.linspace(0.0, 2 * math.pi, 24, endpoint=False)
    for r in (0.0, level.band_m * 0.5, level.band_m - 0.01):
        qx = (x[:, None] + r * np.cos(angles)).ravel()
        qz = (z[:, None] + r * np.sin(angles)).ravel()
        needed = set(zip(np.floor(qx / level.tile_m).astype(int).tolist(),
                         np.floor(qz / level.tile_m).astype(int).tolist()))
        assert needed <= keys
    # Aucune tuile au-delà de l'étendue plus une tuile.
    for ix, iz in keys:
        dx = np.maximum(np.maximum(ix * level.tile_m - x, 0), x - (ix + 1) * level.tile_m)
        dz = np.maximum(np.maximum(iz * level.tile_m - z, 0), z - (iz + 1) * level.tile_m)
        assert np.hypot(dx, dz).min() <= level.band_m + level.tile_m


def test_select_tiles_negative_indices():
    keys = select_tiles([0.0, 0.0], [0.0, -10.0], NEAR)
    assert keys == [(-1, -1), (-1, 0), (0, -1), (0, 0)]


# Critère 6 : altitude absente ----------------------------------------------------------------

def test_missing_altitude_follows_dem(world):
    _, route = load(world)
    expected = default_relief(np.array(route["x"]), np.array(route["z"]))
    assert np.max(np.abs(np.array(route["alt_raw_m"]) - expected)) < 0.01
    assert np.max(np.abs(np.array(route["alt_m"]) - expected)) < 0.5     # après lissage


def test_partial_altitude_uses_dem(relief, make_gpx, tmp_path):
    x, z, alt = straight_north()
    alt = list(alt)
    alt[10] = None
    gpx = make_gpx("partiel.gpx", x, z, alt)
    assert run("build", gpx, "--out", tmp_path, "--layers", "route") == 0
    manifest = json.loads((tmp_path / "partiel.world" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["route"]["alt_source"] == "synthetic"
    assert manifest["layers"]["terrain"] == {"present": False}


def test_aberrant_gpx_altitude_replaced(relief, make_gpx, tmp_path, capsys):
    x, z, _ = straight_north()
    gpx = make_gpx("faux.gpx", x, z, np.full(len(x), 3000.0))     # 2 000 m trop haut
    assert run("build", gpx, "--out", tmp_path, "--layers", "route") == 0
    assert "jugée aberrante" in capsys.readouterr().err
    _, route = load(tmp_path / "faux.world")
    assert abs(route["alt_raw_m"][0] - default_relief(0.0, 0.0)) < 0.01


def test_good_gpx_altitude_kept(make_gpx, tmp_path):
    """Le MNT par défaut des tests (plan à 5 %) correspond à l'altitude GPX : on la garde."""
    x, z, alt = straight_north()
    gpx = make_gpx("bon.gpx", x, z, alt + 20.0)                   # 20 m d'écart : toléré
    assert run("build", gpx, "--out", tmp_path, "--layers", "route") == 0
    manifest, route = load(tmp_path / "bon.world")
    assert manifest["route"]["alt_source"] == "gpx"
    assert abs(route["alt_raw_m"][0] - 1020.0) < 0.01


# Critère 7 : add-layer ------------------------------------------------------------------------

def test_add_layer_keeps_route_and_replaces_tiles(world, monkeypatch, capsys):
    route_sha = hashlib.sha256((world / "route.json").read_bytes()).hexdigest()
    stale = world / "terrain" / "near" / "tile_99_99.f32"
    stale.write_bytes(b"\0" * TILE_BYTES)
    before = tiles_of(world, "far")

    monkeypatch.setattr(cli, "make_provider", lambda offline, log=None: SyntheticProvider(
        *ORIGIN, lambda x, z: default_relief(x, z) + 100.0))
    assert run("add-layer", world, "terrain") == 0
    assert hashlib.sha256((world / "route.json").read_bytes()).hexdigest() == route_sha
    assert not stale.exists()
    after = tiles_of(world, "far")
    assert after.keys() == before.keys()
    for key in before:
        assert np.allclose(after[key], before[key] + 100.0, atol=0.01)
    assert not [p for p in world.iterdir() if p.name.startswith(".")]
    assert run("verify", world) == 0


def test_add_layer_on_route_only_world(relief, make_gpx, tmp_path):
    x, z, alt = straight_north()
    gpx = make_gpx("seule.gpx", x, z, alt)
    assert run("build", gpx, "--out", tmp_path, "--layers", "route") == 0
    w = tmp_path / "seule.world"
    assert not (w / "terrain").exists()
    assert run("add-layer", w, "terrain") == 0
    manifest, _ = load(w)
    assert manifest["layers"]["terrain"]["present"] is True
    assert run("verify", w) == 0


def test_add_layer_failure_keeps_old_terrain(world, monkeypatch):
    before = {p.name: p.read_bytes() for p in (world / "terrain" / "near").iterdir()}
    import openride_compiler.terrain as terrain

    def broken(folder, tiles):
        (folder / "near").mkdir(parents=True)
        raise OSError("disque plein (simulé)")

    monkeypatch.setattr(terrain, "write_terrain", broken)
    assert run("add-layer", world, "terrain") == 2
    assert {p.name: p.read_bytes() for p in (world / "terrain" / "near").iterdir()} == before
    assert not [p for p in world.iterdir() if p.name.startswith(".")]


def test_add_layer_bad_world(tmp_path):
    assert run("add-layer", tmp_path / "absent.world", "terrain") == 1


def test_add_layer_refuses_synthetic_demo_world(tmp_path, capsys):
    write_demo_world = require_core("openride_core.demo_world").write_demo_world

    demo = write_demo_world(tmp_path)
    assert run("add-layer", demo, "terrain") == 1
    assert "UTM" in capsys.readouterr().err
    assert not (demo / "terrain").exists()


# verify : contrôles du terrain ------------------------------------------------------------------

def test_verify_terrain_ok(world):
    assert run("verify", world) == 0


def _first_pair(world, level="near"):
    grids = tiles_of(world, level)
    for (ix, iz) in grids:
        if (ix + 1, iz) in grids:
            return (ix, iz)
    raise AssertionError("pas de tuiles voisines")


def test_verify_detects_broken_edge(world, capsys):
    ix, iz = _first_pair(world)
    path = world / "terrain" / "near" / tile_filename(ix, iz)
    g = read_tile(path).copy()
    g[50, 100] += 1.0
    path.write_bytes(g.astype("<f4").tobytes())
    assert run("verify", world) == 1
    assert "bord(s) partagé(s)" in capsys.readouterr().out


def test_verify_detects_bad_size_and_missing_tile(world, capsys):
    near = sorted((world / "terrain" / "near").glob("*.f32"))
    near[0].write_bytes(near[0].read_bytes()[:-4])
    near[1].unlink()
    assert run("verify", world) == 1
    out = capsys.readouterr().out
    assert "40800 octets au lieu de 40804" in out and "tuile listée absente" in out


def test_verify_detects_nan_near_route(world, capsys):
    _, route = load(world)
    ix, iz = math.floor(route["x"][50] / 1000), math.floor(route["z"][50] / 1000)
    path = world / "terrain" / "near" / tile_filename(ix, iz)
    g = read_tile(path).copy()
    i = int(round((route["x"][50] - ix * 1000) / 10))
    j = int(round((route["z"][50] - iz * 1000) / 10))
    g[j, i] = np.nan
    path.write_bytes(g.astype("<f4").tobytes())
    assert run("verify", world) == 1
    assert "NaN à moins de 25 m" in capsys.readouterr().out


def test_nan_far_from_route_is_allowed(world):
    """Un NaN (donnée absente) loin de la route est permis par le format."""
    _, route = load(world)
    axis = RouteAxis(route["x"], route["z"], route["alt_m"])
    for key, g in tiles_of(world, "near").items():
        gx, gz = tile_coords(*key, NEAR)
        dist, _ = axis.nearest(gx[1:-1, 1:-1], gz[1:-1, 1:-1], 100.0)
        far = ~np.isfinite(dist.reshape(99, 99))
        if far.any():
            j, i = np.argwhere(far)[0] + 1                 # échantillon intérieur, hors bords partagés
            g = g.copy()
            g[j, i] = np.nan
            (world / "terrain" / "near" / tile_filename(*key)).write_bytes(g.astype("<f4").tobytes())
            break
    else:
        raise AssertionError("aucun échantillon loin de la route")
    assert run("verify", world) == 0


# Boucle et terrain ------------------------------------------------------------------------------

def test_loop_with_terrain(relief, make_gpx, tmp_path):
    gpx = make_gpx("boucle.gpx", *circle(radius=600.0, n_points=600))
    assert run("build", gpx, "--out", tmp_path) == 0
    assert run("verify", tmp_path / "boucle.world") == 0


def test_build_terrain_direct():
    route = {"x": [0.0, 0.0], "z": [0.0, -10.0], "alt_m": [5.0, 5.0]}
    frame = LocalFrame.at(*ORIGIN)
    tiles = build_terrain(route, frame, SyntheticProvider(*ORIGIN, lambda x, z: 0 * x + 7.0), log=lambda m: None)
    assert set(tiles) == {"near", "far"}
    g = tiles["near"][(0, 0)]
    assert g.dtype == np.dtype("<f4") and g.shape == (101, 101)
    assert g[0, 0] == pytest.approx(4.95)            # sur l'axe : route − 5 cm
    assert g[100, 100] == pytest.approx(7.0)         # loin de la route : MNT
