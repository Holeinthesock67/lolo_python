"""Lot U3 : côte, mer et plages (critères 1 à 6), sur des côtes synthétiques, réseau coupé."""

from __future__ import annotations

import io
import json
import math
import urllib.parse

import jsonschema
import numpy as np
import pytest

from conftest import ORIGIN, WORLD_CONTRACTS, straight_north, to_latlon
from openride_compiler import cache, cli
from openride_compiler import constants as C
from openride_compiler.coast import (CELL_M, assemble_coastlines, build_coast, close_sea, extent_cells,
                                     _ring_area_en)
from openride_compiler.frame import LocalFrame
from openride_compiler.osm_layers import signed_area

COAST_X = 2500.0          # côte droite nord-sud, mer à l'est (hors d'une limite de carré)
FAR_Z = 30000.0           # la côte dépasse largement l'étendue


def route_dict(length=3000.0):
    x, z, alt = straight_north(length=length)
    return {"x": x.tolist(), "z": z.tolist(), "alt_m": alt.tolist(), "n": len(x), "ds_m": 5.0,
            "length_m": length}


def way(way_id, pts_xz, **tags):
    lat, lon = to_latlon([p[0] for p in pts_xz], [p[1] for p in pts_xz])
    return {"type": "way", "id": way_id, "tags": tags,
            "geometry": [{"lat": float(a), "lon": float(o)} for a, o in zip(lat, lon)]}


def circle_xz(cx, cz, r, n=64, ccw_en=True):
    """Cercle ; `ccw_en` : antihoraire dans le repère (est, nord), sens d'une île dans OSM."""
    a = np.linspace(0.0, 2 * math.pi, n, endpoint=False)
    if not ccw_en:
        a = a[::-1]
    pts = [(cx + r * math.cos(t), cz - r * math.sin(t)) for t in a]
    return pts + [pts[0]]


def straight_coast(way_id=1):
    # Vers le nord (z décroissant) : la mer, à droite, est à l'est.
    return way(way_id, [(COAST_X, FAR_Z), (COAST_X, 0.0), (COAST_X, -FAR_Z)], natural="coastline")


def response(*elements):
    return {"osm3s": {"timestamp_osm_base": "2026-03-16T08:00:00Z"}, "elements": list(elements)}


def sea_areas(res):
    return [a for areas in res.sea_chunks.values() for a in areas]


def sea_area_m2(res):
    total = 0.0
    for a in sea_areas(res):
        total += signed_area(a["outer"]) + sum(signed_area(h) for h in a["holes"])
    return total


def expected_east_area(route, x_from=COAST_X):
    total = 0.0
    for ix, _ in extent_cells(route):
        x0, x1 = ix * CELL_M, (ix + 1) * CELL_M
        total += max(0.0, x1 - max(x0, x_from)) * CELL_M
    return total


FRAME = LocalFrame.at(*ORIGIN)


# Critère 2 : côte droite qui coupe l'emprise ------------------------------------------------------

def test_straight_coast_sea_on_the_right_side():
    route = route_dict()
    res = build_coast(route, FRAME, [response(straight_coast())])
    assert res.present
    expected = expected_east_area(route)
    assert expected > 0
    assert abs(sea_area_m2(res) - expected) <= 0.01 * expected
    for a in sea_areas(res):
        assert a["kind"] == "sea" and a["level_y"] == 0.0
        assert signed_area(a["outer"]) > 0                     # antihoraire, comme le format
        assert min(p[0] for p in a["outer"]) >= COAST_X - 0.01  # du bon côté
    # Lignes de côte : la mer à droite du sens des points (vers le nord, z décroissant)
    lines = [ln for ch in res.coast_chunks.values() for ln in ch["lines"]]
    assert lines and all(ln["shore"] == "rock" for ln in lines)
    for ln in lines:
        assert all(abs(p[0] - COAST_X) < 0.01 for p in ln["points"])
        assert ln["points"][0][1] > ln["points"][-1][1]


def test_reversed_coast_puts_the_sea_west():
    route = route_dict()
    reversed_coast = way(1, [(COAST_X, -FAR_Z), (COAST_X, 0.0), (COAST_X, FAR_Z)], natural="coastline")
    res = build_coast(route, FRAME, [response(reversed_coast)])
    west = sum(max(0.0, min((ix + 1) * CELL_M, COAST_X) - ix * CELL_M) * CELL_M
               for ix, _ in extent_cells(route))
    assert abs(sea_area_m2(res) - west) <= 0.01 * west
    assert all(max(p[0] for p in a["outer"]) <= COAST_X + 0.01 for a in sea_areas(res))


def test_sea_pieces_never_overlap_and_stay_in_their_square():
    route = route_dict()
    res = build_coast(route, FRAME, [response(straight_coast())])
    seen = set()
    for a in sea_areas(res):
        _, ix, iz, _ = a["id"].split("_")
        cell = (int(ix), int(iz))
        xs = [p[0] for p in a["outer"]]
        zs = [p[1] for p in a["outer"]]
        assert cell[0] * CELL_M - 0.01 <= min(xs) and max(xs) <= (cell[0] + 1) * CELL_M + 0.01
        assert cell[1] * CELL_M - 0.01 <= min(zs) and max(zs) <= (cell[1] + 1) * CELL_M + 0.01
        assert cell not in seen
        seen.add(cell)


# Critère 3 : île au large -------------------------------------------------------------------------

def test_island_offshore_is_a_hole():
    route = route_dict()
    inside = way(2, circle_xz(4500.0, -1500.0, 200.0), natural="coastline")     # dans un seul carré
    across = way(3, circle_xz(6000.0, -3000.0, 300.0), natural="coastline")     # à cheval sur quatre
    res = build_coast(route, FRAME, [response(straight_coast(), inside, across)])
    holed = [a for a in sea_areas(res) if a["holes"]]
    assert len(holed) == 1 and holed[0]["id"].startswith("sea_4_-2_")
    assert signed_area(holed[0]["holes"][0]) < 0
    island_area = math.pi * 200.0 ** 2 + math.pi * 300.0 ** 2
    expected = expected_east_area(route) - island_area
    assert abs(sea_area_m2(res) - expected) <= 0.01 * expected
    # Les carrés coupés par la grande île ne couvrent pas son centre.
    for a in sea_areas(res):
        assert not (a["id"].startswith("sea_5_-3_") or a["id"].startswith("sea_6_-3_")) or a["holes"] == []


def test_route_on_an_island_has_sea_all_around():
    route = route_dict(length=1000.0)
    island = way(7, circle_xz(0.0, -500.0, 2600.0, n=256), natural="coastline")
    res = build_coast(route, FRAME, [response(island)])
    total = len(extent_cells(route)) * CELL_M * CELL_M
    expected = total - math.pi * 2600.0 ** 2
    assert abs(sea_area_m2(res) - expected) <= 0.01 * expected


# Critère 4 : baie fermée par deux segments mal ordonnés -------------------------------------------

def test_bay_from_two_misordered_segments_is_one_polygon():
    # Repère (est, nord) d'un carré de 1 km ; la baie s'ouvre au nord.
    a = [(700.0, 1000.0), (700.0, 400.0), (500.0, 400.0)]
    b = [(500.0, 400.0), (300.0, 400.0), (300.0, 1000.0)]
    lines = assemble_coastlines([b, a])
    assert len(lines) == 1 and lines[0][0] == (700.0, 1000.0) and lines[0][-1] == (300.0, 1000.0)
    sea = close_sea(lines, (0.0, 0.0, 1000.0, 1000.0), lambda: False)
    assert len(sea.polygons) == 1
    assert abs(abs(_ring_area_en(sea.polygons[0][0])) - 400.0 * 600.0) < 1e-6


# Critère 5 : falaise et plage ---------------------------------------------------------------------

def test_cliff_by_slope_and_beaches():
    route = route_dict()
    tan60 = math.tan(math.radians(60.0))

    def height(xs, zs):
        xs, zs = np.asarray(xs, float), np.asarray(zs, float)
        steep = zs < -6000.0
        return np.where(steep, np.maximum(0.0, COAST_X - xs) * tan60, np.maximum(0.0, COAST_X - xs) * 0.02)

    beach = way(20, [(COAST_X - 40.0, -1000.0), (COAST_X, -1000.0), (COAST_X, -1600.0),
                     (COAST_X - 40.0, -1600.0), (COAST_X - 40.0, -1000.0)], natural="beach", surface="sand")
    pebbles = way(21, [(COAST_X - 30.0, -3000.0), (COAST_X, -3000.0), (COAST_X, -3300.0),
                       (COAST_X - 30.0, -3300.0), (COAST_X - 30.0, -3000.0)],
                  natural="beach", surface="pebblestone")
    inland_sand = way(22, [(-3000.0, -1000.0), (-2900.0, -1000.0), (-2900.0, -1100.0),
                           (-3000.0, -1100.0), (-3000.0, -1000.0)], natural="sand")
    cliff = way(23, [(COAST_X - 10.0, 2000.0), (COAST_X - 10.0, 2500.0)], natural="cliff")
    res = build_coast(route, FRAME, [response(straight_coast(), beach, pebbles, inland_sand, cliff)], height)

    def shore_at(z):
        for ch in res.coast_chunks.values():
            for ln in ch["lines"]:
                zs = [p[1] for p in ln["points"]]
                if min(zs) < z < max(zs):
                    return ln["shore"]
        return None

    assert shore_at(-7300.0) == "cliff"            # pente de 60°
    assert shore_at(-1300.0) == "sand"             # natural=beach
    assert shore_at(-3150.0) == "shingle"          # surface=pebblestone
    assert shore_at(2250.0) == "cliff"             # natural=cliff à 10 m
    assert shore_at(-4500.0) == "rock"
    beaches = {b["id"]: b for ch in res.coast_chunks.values() for b in ch["beaches"]}
    assert set(beaches) == {"w20", "w21"}         # le sable de l'intérieur ne touche pas la côte
    assert beaches["w20"]["kind"] == "sand" and beaches["w21"]["kind"] == "shingle"
    assert res.beaches_count == 2


# Ligne de commande : build, add-layer, verify ; critère 6 (parcours sans côte) ----------------------

class FakeOverpass:
    """Faux Overpass : la requête de la côte reçoit `coast`, les autres une réponse vide."""

    def __init__(self, coast: dict) -> None:
        self.coast = coast
        self.queries: list[str] = []

    def __call__(self, req, timeout=None):
        query = urllib.parse.parse_qs(req.data.decode("utf-8"))["data"][0]
        self.queries.append(query)
        body = self.coast if "coastline" in query else response()
        return io.BytesIO(json.dumps(body).encode("utf-8"))


def run(*argv) -> int:
    return cli.main([str(a) for a in argv])


def schema(name):
    return json.loads((WORLD_CONTRACTS / name).read_text(encoding="utf-8"))


@pytest.fixture
def coastal_overpass(monkeypatch):
    beach = way(20, [(COAST_X - 40.0, -1000.0), (COAST_X, -1000.0), (COAST_X, -1600.0),
                     (COAST_X - 40.0, -1600.0), (COAST_X - 40.0, -1000.0)], natural="beach")
    fake = FakeOverpass(response(straight_coast(), beach, way(2, circle_xz(4500.0, -1500.0, 200.0),
                                                              natural="coastline")))
    monkeypatch.setattr(cache.urllib.request, "urlopen", fake)
    return fake


def test_build_and_verify_coastal_route(coastal_overpass, make_gpx, tmp_path):
    x, z, alt = straight_north(length=3000.0)
    gpx = make_gpx("littoral.gpx", x, z, alt)
    out = tmp_path / "routes"
    assert run("build", gpx, "--out", out, "--layers", "route,terrain,water,coast", "--no-surface") == 0
    world = out / "littoral.world"
    assert run("verify", world) == 0
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema("manifest.schema.json"))
    coast = manifest["layers"]["coast"]
    assert coast["present"] is True and coast["version"] == C.COAST_VERSION and coast["beaches_count"] == 1
    lines = beaches = 0
    for f in sorted((world / "coast").glob("chunk_*.json")):
        chunk = json.loads(f.read_text(encoding="utf-8"))
        jsonschema.validate(chunk, schema("coast.schema.json"))
        lines += len(chunk["lines"])
        beaches += len(chunk["beaches"])
    assert (lines, beaches) == (coast["lines_count"], coast["beaches_count"])
    seas = 0
    for f in sorted((world / "water").glob("chunk_*.json")):
        chunk = json.loads(f.read_text(encoding="utf-8"))
        jsonschema.validate(chunk, schema("water.schema.json"))
        seas += sum(1 for a in chunk["areas"] if a["kind"] == "sea")
    assert seas > 0 and manifest["layers"]["water"]["areas_count"] == seas

    # add-layer coast seul, hors ligne : mêmes fichiers ; add-layer water garde la mer.
    before = {f.name: f.read_bytes() for f in (world / "coast").glob("*.json")}
    assert run("add-layer", world, "coast", "--offline") == 0
    assert {f.name: f.read_bytes() for f in (world / "coast").glob("*.json")} == before
    assert run("add-layer", world, "water", "--offline") == 0
    assert run("verify", world) == 0
    after = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    assert after["layers"]["water"]["areas_count"] == seas


def test_verify_rejects_a_sea_outside_its_square(coastal_overpass, make_gpx, tmp_path, capsys):
    x, z, alt = straight_north(length=3000.0)
    gpx = make_gpx("littoral.gpx", x, z, alt)
    out = tmp_path / "routes"
    assert run("build", gpx, "--out", out, "--layers", "route,terrain,water,coast", "--no-surface") == 0
    world = out / "littoral.world"
    f = next(p for p in sorted((world / "water").glob("chunk_*.json"))
             if any(a["kind"] == "sea" for a in json.loads(p.read_text(encoding="utf-8"))["areas"]))
    chunk = json.loads(f.read_text(encoding="utf-8"))
    sea = next(a for a in chunk["areas"] if a["kind"] == "sea")
    sea["outer"] = [[p[0] + 250.0, p[1]] for p in sea["outer"]]       # à cheval sur deux carrés
    f.write_text(json.dumps(chunk), encoding="utf-8")
    capsys.readouterr()
    assert run("verify", world) != 0
    captured = capsys.readouterr()
    assert "mer non refermée dans son carré" in captured.out + captured.err


def test_route_without_coast_keeps_water_unchanged(monkeypatch, make_gpx, tmp_path):
    lake = {"type": "way", "id": 5002, "tags": {"natural": "water", "water": "pond"},
            "geometry": [{"lat": float(a), "lon": float(o)} for a, o in zip(*to_latlon(
                [30.0, 60.0, 60.0, 30.0, 30.0], [-500.0, -500.0, -530.0, -530.0, -500.0]))]}
    fake = FakeOverpass(response())
    monkeypatch.setattr(cache.urllib.request, "urlopen",
                        lambda req, timeout=None: fake(req, timeout) if b"coastline" in req.data
                        else io.BytesIO(json.dumps(response(lake)).encode("utf-8")))
    x, z, alt = straight_north(length=2000.0)
    gpx = make_gpx("interieur.gpx", x, z, alt)
    with_coast, without = tmp_path / "a", tmp_path / "b"
    assert run("build", gpx, "--out", with_coast, "--layers", "route,terrain,water,coast", "--no-surface") == 0
    assert run("build", gpx, "--out", without, "--layers", "route,terrain,water", "--no-surface") == 0
    wa, wb = with_coast / "interieur.world", without / "interieur.world"
    ma = json.loads((wa / "manifest.json").read_text(encoding="utf-8"))
    mb = json.loads((wb / "manifest.json").read_text(encoding="utf-8"))
    assert ma["layers"]["coast"] == {"present": False} and mb["layers"]["coast"] == {"present": False}
    assert not (wa / "coast").exists()
    assert ma["layers"]["water"] == mb["layers"]["water"] and ma["layers"]["water"]["areas_count"] == 1
    for f in sorted((wb / "water").glob("*.json")):
        assert (wa / "water" / f.name).read_bytes() == f.read_bytes()
    assert run("verify", wa) == 0
