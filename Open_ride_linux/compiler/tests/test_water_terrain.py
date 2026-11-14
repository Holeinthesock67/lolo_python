"""Niveau des plans d'eau et sol abaissé dessous (lot EA1, `water_terrain.py`)."""

from __future__ import annotations

import numpy as np
import pytest

from openride_compiler import constants as C
from openride_compiler import water_terrain as WT
from openride_compiler.terrain import NEAR, tile_coords
from openride_compiler.worldgen import squares
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
from openride_compiler.worldgen.squares import SquareKey, generate_square
from openride_compiler.worldgen.store import WorldCache


def rect(x0, z0, x1, z1):
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


def lake_bowl(level=100.0, cx=500.0, cz=500.0, r=300.0, bank=4.0):
    """MNT d'un lac aplati (comme Copernicus) : `level` jusqu'à r, puis berge qui monte de `bank` m en 30 m."""
    def h(xs, zs):
        d = np.hypot(np.asarray(xs) - cx, np.asarray(zs) - cz)
        return level + np.clip((d - r) / 30.0, 0.0, 1.0) * bank
    return h


def test_rings_contain_with_island() -> None:
    rings = [WT._ring_array(rect(0, 0, 100, 100)), WT._ring_array(rect(40, 40, 60, 60))]
    px = np.array([10.0, 50.0, 150.0, 99.0])
    pz = np.array([10.0, 50.0, 50.0, 50.0])
    assert WT.rings_contain(px, pz, rings).tolist() == [True, False, False, True]


def test_level_is_flat_dem_and_same_for_both_pieces_of_a_cut_lake() -> None:
    h = lake_bowl()
    # contour carré qui déborde un peu sur la berge : son minimum reste le lac, mais la berge le tire vers le haut
    whole = WT.lake_level(rect(205, 205, 795, 795), [], h)
    # le même lac coupé en deux par le bord d'une tuile vectorielle (x = 430) : contours différents
    west = WT.lake_level(rect(205, 205, 430, 795), [], h)
    east = WT.lake_level(rect(430, 205, 795, 795), [], h)
    assert whole == west == east == 100.0


def test_outlet_does_not_pull_the_lake_down() -> None:
    base = lake_bowl()

    def h(xs, zs):
        y = base(xs, zs)
        # exutoire, ou pied d'un barrage : 8 m plus bas sur 20 m de rive
        low = (np.abs(np.asarray(xs) - 500.0) < 10.0) & (np.asarray(zs) > 780.0)
        return np.where(low, y - 8.0, y)
    outer = rect(220, 220, 780, 790)
    assert min(h(*WT._shore_points([WT._ring_array(outer)], C.LAKE_SHORE_STEP_M).T)) == 92.0   # ancienne règle : 92
    assert WT.lake_level(outer, [], h) == 100.0


def test_level_never_above_the_low_shore() -> None:
    # MNT non aplati (étang en pente) : la médiane du dedans dépasse la rive basse, le plafond l'arrête
    def h(xs, zs):
        return 50.0 + 0.05 * np.asarray(xs)
    outer = rect(0, 0, 400, 400)
    shore = h(*WT._shore_points([WT._ring_array(outer)], C.LAKE_SHORE_STEP_M).T)
    level = WT.lake_level(outer, [], h)
    assert level == pytest.approx(float(np.quantile(shore, C.LAKE_SHORE_QUANTILE)), abs=0.01)
    assert level < 60.0    # médiane du dedans : 60


def test_tiny_pond_keeps_the_shore_minimum() -> None:
    def h(xs, zs):
        return 10.0 + np.asarray(xs) * 0.1
    assert WT.lake_level(rect(3, 3, 13, 11), [], h) == pytest.approx(10.3, abs=1e-6)


def test_sink_grid_lowers_inside_only_never_raises_and_keeps_road() -> None:
    gx, gz = np.meshgrid(np.arange(0.0, 110.0, 10.0), np.arange(0.0, 110.0, 10.0))
    y = np.full(gx.shape, 101.0)
    y[0, 0] = 50.0
    areas = WT.inland_areas([
        {"kind": "lake", "level_y": 100.0, "outer": rect(15, 15, 95, 95), "holes": [rect(45, 45, 65, 65)]},
        {"kind": "sea", "level_y": 0.0, "outer": rect(-5, -5, 105, 105), "holes": []},
    ])
    protect = np.zeros(gx.shape, dtype=bool)
    protect[:, 9] = True                         # chaussée en x = 90
    n = WT.sink_grid(gx, gz, y, areas, protect=protect)
    inside = (gx > 15) & (gx < 95) & (gz > 15) & (gz < 95) & ~((gx > 45) & (gx < 65) & (gz > 45) & (gz < 65))
    lowered = inside & ~protect
    assert n == int(lowered.sum())
    assert np.all(y[lowered] == 100.0 - C.WATER_SINK_M)
    assert np.all(y[~lowered & (y != 50.0)] == 101.0)    # île, chaussée, dehors ; la mer n'abaisse rien
    assert y[0, 0] == 50.0


def test_route_tiles_sunk_identically_on_shared_border() -> None:
    tiles = {"near": {}, "far": {}}
    for key in ((0, 0), (1, 0)):
        gx, _ = tile_coords(*key, NEAR)
        tiles["near"][key] = np.full(gx.shape, 101.0, dtype="<f4")
    route = {"x": [0.0, 2000.0], "z": [-500.0, -500.0], "alt_m": [101.0, 101.0]}
    n = WT.sink_route_tiles(tiles, route, [{"kind": "lake", "level_y": 100.0,
                                           "outer": rect(800, 200, 1300, 700), "holes": []}])
    a, b = tiles["near"][(0, 0)], tiles["near"][(1, 0)]
    assert n > 0 and np.array_equal(a[:, -1], b[:, 0])
    assert a[50, -1] == 100.0 - C.WATER_SINK_M and a[50, 0] == 101.0


# --- monde ouvert ------------------------------------------------------------------------------------

ZONE = "31T"
FRAME = squares.zone_frame(ZONE)
IX, IN = 682, 4892


def lonlat(e, n):
    lat, lon = FRAME.to_latlon(np.array([e]), np.array([-n]))
    return float(lon[0]), float(lat[0])


class BowlProvider:
    """MNT d'un lac de 600 m de rayon centré sur le coin commun des carrés (IX, IN) et (IX + 1, IN)."""

    name = "bol"
    native_resolution_m = 30.0

    def __init__(self) -> None:
        self.h = lake_bowl(level=200.0, cx=(IX + 1) * 1000.0, cz=-(IN * 1000.0 + 500.0), r=600.0)

    def elevations(self, lat, lon):
        x, z = FRAME.to_xz(np.asarray(lat, float), np.asarray(lon, float))
        return self.h(x, z)


def test_open_world_lake_cut_in_two_pieces_has_one_level_and_sunk_ground(tmp_path) -> None:
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/lac")
    e_mid, n_mid = (IX + 1) * 1000, IN * 1000 + 500
    # deux morceaux du même lac, coupés au bord d'une tuile vectorielle (E = e_mid + 120)
    for k, (e0, e1) in enumerate(((e_mid - 550, e_mid + 120), (e_mid + 120, e_mid + 550))):
        w.add_area(f"v{k}", "water", {"natural": "water", "water": "lake"},
                   [lonlat(e0, n_mid - 380), lonlat(e1, n_mid - 380), lonlat(e1, n_mid + 380),
                    lonlat(e0, n_mid + 380), lonlat(e0, n_mid - 380)])
    w.finish(osm_date="2026-11-14T00:00:00Z")
    db = OsmDb(tmp_path / "osm.sqlite")
    c = WorldCache(tmp_path / "cache", 10**9, log=lambda _m: None)
    pv = BowlProvider()
    a = generate_square(SquareKey(ZONE, IX, IN), db, pv, c)
    b = generate_square(SquareKey(ZONE, IX + 1, IN), db, pv, c)
    import json
    areas = [x for f in (a, b) for x in json.loads((f / "water.json").read_text())["areas"]]
    assert sorted(x["id"] for x in areas) == ["v0", "v1"]
    assert {x["level_y"] for x in areas} == {200.0}
    na = np.frombuffer((a / "near.f32").read_bytes(), dtype="<f4").reshape(101, 101)
    nb = np.frombuffer((b / "near.f32").read_bytes(), dtype="<f4").reshape(101, 101)
    assert np.array_equal(na[:, -1], nb[:, 0])                    # bord commun identique
    assert na[50, -1] == pytest.approx(200.0 - C.WATER_SINK_M)    # sous le lac, au bord commun
    assert nb[50, 30] == pytest.approx(200.0 - C.WATER_SINK_M)    # sous le second morceau
    assert na[50, 0] > 200.0                                       # berge, hors du lac
