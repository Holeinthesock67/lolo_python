"""Grandes rivières en surface (lot EA3, `river_surface.py`)."""

from __future__ import annotations

import io
import json
import math

import jsonschema
import numpy as np
import pytest

from conftest import ORIGIN, WORLD_CONTRACTS, straight_north, to_latlon
from openride_compiler import cache, cli
from openride_compiler import constants as C
from openride_compiler import river_surface as RS
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.terrain import NEAR, read_tile, tile_coords
from openride_compiler.water_terrain import rings_contain
from openride_compiler.worldgen.squares import WORLDGEN_VERSION


def area(poly) -> float:
    outer, holes = poly
    return RS.signed_area(outer) + sum(RS.signed_area(h) for h in holes)


# --- découpe ---------------------------------------------------------------------------------------

def test_u_shape_leaving_and_entering_the_same_side_gives_two_pieces() -> None:
    u = [(0, -50), (100, -50), (100, 80), (70, 80), (70, 10), (30, 10), (30, 80), (0, 80)]
    pieces = RS.clip_to_rect(u, [], -10, 20, 200, 200)
    assert sorted(round(area(p), 6) for p in pieces) == [1800.0, 1800.0]   # deux bras, aucun côté dégénéré


def test_island_cut_by_the_border_becomes_a_notch() -> None:
    outer = [(-100, -100), (300, -100), (300, 300), (-100, 300)]
    island = [(-20, 40), (-20, 60), (20, 60), (20, 40)]
    pieces = RS.clip_to_rect(outer, [island], 0, 0, 100, 100)
    assert len(pieces) == 1 and pieces[0][1] == [] and area(pieces[0]) == pytest.approx(10000 - 400)
    whole = RS.clip_to_rect(outer, [island], -50, 0, 100, 100)   # île entière dans le carré : gardée
    assert len(whole) == 1 and len(whole[0][1]) == 1 and area(whole[0]) == pytest.approx(15000 - 800)


def test_pieces_of_all_cells_add_up_to_the_polygon() -> None:
    rng = np.random.default_rng(3)
    for _ in range(60):
        ang = np.sort(rng.uniform(0, 2 * np.pi, int(rng.integers(5, 30))))
        rad = rng.uniform(20, 150, len(ang))
        ring = [(math.cos(a) * r + 50, math.sin(a) * r + 50) for a, r in zip(ang, rad)]
        isle = [(math.cos(a) * 8 + 50, math.sin(a) * 8 + 50) for a in np.linspace(0, 2 * np.pi, 7)[:-1]]
        if not rings_contain(np.array([p[0] for p in isle]), np.array([p[1] for p in isle]), [np.array(ring)]).all():
            continue
        total = abs(RS.signed_area(ring)) - abs(RS.signed_area(isle))
        got = sum(area(p) for i in range(-3, 5) for j in range(-3, 5)
                  for p in RS.clip_to_rect(ring, [isle], 60 * i, 60 * j, 60 * i + 60, 60 * j + 60))
        assert got == pytest.approx(total, rel=1e-9)


def test_neighbour_cells_share_their_cut_points_exactly() -> None:
    river = [(-300.0, 113.7), (1700.3, 141.2), (1690.1, 251.9), (-310.4, 230.0)]
    west = RS.clip_to_rect(river, [], 0, 0, 1000, 1000)[0][0]
    east = RS.clip_to_rect(river, [], 1000, 0, 2000, 1000)[0][0]
    cut_w = sorted(p for p in west if p[0] == 1000)
    cut_e = sorted(p for p in east if p[0] == 1000)
    assert len(cut_w) == 2 and cut_w == cut_e
    dw = RS.densify_ring(west, C.RIVER_EDGE_STEP_M)
    de = RS.densify_ring(east, C.RIVER_EDGE_STEP_M)
    assert sorted(tuple(p) for p in dw if p[0] == 1000) == sorted(tuple(p) for p in de if p[0] == 1000)


# --- niveau ----------------------------------------------------------------------------------------

def valley(slope=0.002, base=300.0, bank=6.0):
    """MNT d'une rivière aplanie en marches de 1 m (comme Copernicus) entre z = 100 et z = 200, qui
    descend vers l'est ; berges `bank` m plus haut."""
    def h(xs, zs):
        xs, zs = np.asarray(xs, float), np.asarray(zs, float)
        water = np.floor(base - slope * xs)
        inside = (zs >= 100) & (zs <= 200)
        return np.where(inside, water, water + bank)
    return h


RIVER = ([(-500.0, 100.0), (3500.0, 100.0), (3500.0, 200.0), (-500.0, 200.0)], [])


def test_level_descends_along_the_course_and_stays_below_the_banks() -> None:
    h = valley()
    lv = RS.RiverLevels([RIVER], h)
    xs = np.arange(0.0, 3001.0, 250.0)
    ys = lv.at(xs, np.full(len(xs), 150.0))
    assert np.all(np.diff(ys) < 0)                                   # descend le long du cours
    assert np.all(np.abs(ys - (300.0 - 0.002 * xs)) < 1.0)           # marches lissées en pente
    near_bank = lv.at(xs, np.full(len(xs), 101.0))
    assert np.all(near_bank <= h(xs, np.full(len(xs), 150.0)) + 1e-9)   # pas tirée vers la berge


def test_level_does_not_depend_on_the_window() -> None:
    h = valley()
    small = RS.RiverLevels([RIVER], h, (840.0, -60.0, 2160.0, 1060.0))   # points ± 160 m
    big = RS.RiverLevels([RIVER], h)
    pts = np.array([[1000.0, 150.0], [1500.0, 120.0], [2000.0, 199.0]])
    assert np.array_equal(small.at(pts[:, 0], pts[:, 1]), big.at(pts[:, 0], pts[:, 1]))


def test_lines_are_cut_inside_the_surface() -> None:
    lv = RS.RiverLevels([RIVER], valley())
    line = {"id": "w1", "kind": "river", "width_m": 6.0,
            "points": [[-900.0, 150.0, 400.0], [-700.0, 150.0, 400.0], [-400.0, 150.0, 400.0],
                       [0.0, 150.0, 400.0], [500.0, 150.0, 400.0]]}
    out = RS.trim_lines([line], lv)
    assert len(out) == 1 and [p[0] for p in out[0]["points"]] == [-900.0, -700.0, -400.0]
    assert out[0]["points"][-1][2] == pytest.approx(float(lv.at([-400.0], [150.0])[0]), abs=0.01)


# --- parcours compilé ------------------------------------------------------------------------------

RIVER_X = (60.0, 160.0)


def river_dem(x, z):
    """Plan de conftest (5 % vers le nord) ; rivière aplanie 10 m plus bas, en marches de 1 m."""
    x, z = np.asarray(x, float), np.asarray(z, float)
    ground = 1000.0 - 0.05 * z
    inside = (x >= RIVER_X[0]) & (x <= RIVER_X[1])
    return np.where(inside, np.floor(ground - 10.0), ground)


def overpass_payload() -> bytes:
    x0, x1 = RIVER_X
    ring = [(x0, 400.0), (x1, 400.0), (x1, -3400.0), (x0, -3400.0), (x0, 400.0)]
    lat, lon = to_latlon([p[0] for p in ring], [p[1] for p in ring])
    zs = np.arange(500.0, -3501.0, -100.0)
    llat, llon = to_latlon(np.full(len(zs), 110.0), zs)
    elements = [
        {"type": "way", "id": 9001, "tags": {"natural": "water", "water": "river", "name": "Rivière d'essai"},
         "geometry": [{"lat": float(a), "lon": float(o)} for a, o in zip(lat, lon)]},
        {"type": "way", "id": 9002, "tags": {"waterway": "river"},
         "geometry": [{"lat": float(a), "lon": float(o)} for a, o in zip(llat, llon)]},
    ]
    return json.dumps({"osm3s": {"timestamp_osm_base": "2026-11-16T00:00:00Z"}, "elements": elements}).encode()


@pytest.fixture
def river_world(monkeypatch, make_gpx, tmp_path):
    payload = overpass_payload()
    monkeypatch.setattr(cache.urllib.request, "urlopen", lambda req, timeout=None: io.BytesIO(payload))
    monkeypatch.setattr(cli, "make_provider", lambda offline, log=None: SyntheticProvider(*ORIGIN, river_dem))
    x, z, alt = straight_north(length=3000.0)
    gpx = make_gpx("riviere.gpx", x, z, alt)
    out = tmp_path / "routes"
    assert cli.main(["build", str(gpx), "--out", str(out), "--layers", "route,terrain,water"]) == 0
    return out / "riviere.world"


def _areas(world):
    return [a for p in sorted((world / "water").glob("chunk_*.json"))
            for a in json.loads(p.read_text(encoding="utf-8"))["areas"]]


def test_compiled_river_surface_descends_and_ground_is_sunk(river_world) -> None:
    world = river_world
    assert cli.main(["verify", str(world)]) == 0
    schema = json.loads((WORLD_CONTRACTS / "water.schema.json").read_text(encoding="utf-8"))
    for p in sorted((world / "water").glob("chunk_*.json")):
        jsonschema.validate(json.loads(p.read_text(encoding="utf-8")), schema)
    rivers = [a for a in _areas(world) if a["kind"] == "river"]
    assert len(rivers) >= 3 and all("_c" in a["id"] for a in rivers)       # un morceau par carré de 1 km
    for a in rivers:
        assert len(a["outer_y"]) == len(a["outer"]) and a["holes_y"] == []
        zs = np.array([p[1] for p in a["outer"]])
        ys = np.array(a["outer_y"])
        assert np.corrcoef(zs, ys)[0, 1] < -0.9                          # plus bas vers le nord (z < 0)
        assert np.all(np.abs(ys - (990.0 - 0.05 * zs)) < 4.0)
    # ruban de la rivière : plus rien dans la surface, il reste à l'amont (z > 400)
    lines = [ln for p in sorted((world / "water").glob("chunk_*.json"))
             for ln in json.loads(p.read_text(encoding="utf-8"))["lines"]]
    for ln in lines:
        pts = np.array(ln["points"])
        deep = (pts[:, 0] > RIVER_X[0]) & (pts[:, 0] < RIVER_X[1]) & (pts[:, 1] < 300) & (pts[:, 1] > -3300)
        assert not deep.any()
    # sol sous l'eau : 1 m sous la surface au plus ; la route (x = 0) n'est pas touchée
    tile = read_tile(world / "terrain" / "near" / "tile_0_-2.f32")
    gx, gz = tile_coords(0, -2, NEAR)
    mid = (gx > 75) & (gx < 145)
    expect = 990.0 - 0.05 * gz[mid]
    assert np.all(tile[mid] <= expect - C.WATER_SINK_M + 1.5)
    road = np.abs(gx) < 2
    assert np.allclose(tile[road], 1000.0 - 0.05 * gz[road], atol=0.2)


def test_add_layer_water_gives_the_same_world(river_world) -> None:
    world = river_world
    before_t = {p.name: p.read_bytes() for p in (world / "terrain" / "near").glob("*.f32")}
    before_w = {p.name: p.read_bytes() for p in (world / "water").glob("*.json")}
    assert cli.main(["add-layer", str(world), "water"]) == 0
    assert {p.name: p.read_bytes() for p in (world / "terrain" / "near").glob("*.f32")} == before_t
    assert {p.name: p.read_bytes() for p in (world / "water").glob("*.json")} == before_w


# --- monde ouvert ----------------------------------------------------------------------------------

def test_open_world_river_cut_by_squares_matches_on_the_border(tmp_path) -> None:
    from openride_compiler.worldgen import squares
    from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
    from openride_compiler.worldgen.squares import SquareKey, generate_square
    from openride_compiler.worldgen.store import WorldCache

    zone, ix, i_n = "31T", 682, 4892
    frame = squares.zone_frame(zone)

    def lonlat(e, n):
        lat, lon = frame.to_latlon(np.array([e]), np.array([-n]))
        return float(lon[0]), float(lat[0])

    n0, n1 = i_n * 1000 + 400, i_n * 1000 + 520          # rivière est-ouest de 120 m, sur deux carrés et plus
    e0, e1 = ix * 1000 - 800, (ix + 2) * 1000 + 800

    class Provider:
        name = "vallee"
        native_resolution_m = 30.0

        def elevations(self, lat, lon):
            x, z = frame.to_xz(np.asarray(lat, float), np.asarray(lon, float))
            water = np.floor(400.0 - 0.003 * (x - ix * 1000))
            return np.where((-z >= n0) & (-z <= n1), water, water + 8.0)

    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/riviere")
    w.add_area("r1", "river", {"natural": "water", "water": "river"},
               [lonlat(e0, n0), lonlat(e1, n0), lonlat(e1, n1), lonlat(e0, n1), lonlat(e0, n0)])
    w.add_line("l1", "river", {}, [lonlat(e, (n0 + n1) / 2) for e in range(e0 - 400, e1 + 1, 100)])
    w.finish(osm_date="2026-11-16T00:00:00Z")
    db = OsmDb(tmp_path / "osm.sqlite")
    c = WorldCache(tmp_path / "cache", 10**9, log=lambda _m: None)
    a = generate_square(SquareKey(zone, ix, i_n), db, Provider(), c)
    b = generate_square(SquareKey(zone, ix + 1, i_n), db, Provider(), c)
    wa = json.loads((a / "water.json").read_text())
    wb = json.loads((b / "water.json").read_text())
    ra = [x for x in wa["areas"] if x["kind"] == "river"]
    rb = [x for x in wb["areas"] if x["kind"] == "river"]
    assert len(ra) == 1 and len(rb) == 1 and ra[0]["id"] != rb[0]["id"]
    # sommets du bord commun (E = 1000 (ix + 1)) : mêmes points, même altitude
    edge_a = sorted((round(p[1], 2), y) for p, y in zip(ra[0]["outer"], ra[0]["outer_y"]) if p[0] == 1000.0)
    edge_b = sorted((round(p[1], 2), y) for p, y in zip(rb[0]["outer"], rb[0]["outer_y"]) if p[0] == 0.0)
    assert len(edge_a) >= 2 and edge_a == edge_b
    assert ra[0]["level_y"] > rb[0]["level_y"]                          # descend vers l'est
    na = np.frombuffer((a / "near.f32").read_bytes(), dtype="<f4").reshape(101, 101)
    nb = np.frombuffer((b / "near.f32").read_bytes(), dtype="<f4").reshape(101, 101)
    assert np.array_equal(na[:, -1], nb[:, 0])
    row = 54                                                             # N = 1000 (IN + 1) − 10 j = 1000 IN + 460
    assert na[row, 50] <= 400.0 - 0.003 * 500 - C.WATER_SINK_M + 1.0
    # ruban : rien dans la surface
    for ln in wa["lines"] + wb["lines"]:
        inside = [(n0 + 15 < 1000 * (i_n + 1) - p[1] < n1 - 15) for p in ln["points"]]
        assert not any(inside[1:-1])
    assert json.loads((a / "meta.json").read_text())["versions"]["worldgen"] == WORLDGEN_VERSION


def test_vector_tile_river_class_is_kept_and_old_tile_base_is_refilled(tmp_path) -> None:
    import sqlite3

    from openride_compiler.worldgen import mvt, vector_tiles as vt
    from openride_compiler.worldgen.osmdb import OsmDb

    tx, ty = mvt.lonlat_to_tile(14, 4.6, 43.0)
    data = mvt.encode_tile({"water": [{"id": 1, "type": 3, "tags": {"class": "river"},
                                       "paths": [([(100, 1000), (4000, 1000), (4000, 1300), (100, 1300)], True)]}]})
    db = vt.TileDb(tmp_path / "t.sqlite")
    assert db.load(tx, ty, data) == {"roads": 0, "areas": 1, "lines": 0, "points": 0}
    db.close()
    with OsmDb(tmp_path / "t.sqlite") as r:
        (a,) = r.areas_in((-180.0, -85.0, 180.0, 85.0))
        assert a.kind == "river" and a.tags.get("water") == "river"
    con = sqlite3.connect(tmp_path / "t.sqlite")
    con.execute("UPDATE meta SET value = '1' WHERE key = 'convert_version'")
    con.commit()
    con.close()
    db = vt.TileDb(tmp_path / "t.sqlite")                   # base d'avant EA3 : vidée, tuiles à reverser
    assert not db.loaded(tx, ty) and db.counts()["areas"] == 0
    assert db.load(tx, ty, data)["areas"] == 1
    db.close()
