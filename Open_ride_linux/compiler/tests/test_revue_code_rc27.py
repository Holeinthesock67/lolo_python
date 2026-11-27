"""Lot RC27 (revue de code vague 4, K3-01, K3-04, K3-05, K3-06) : couches OSM des parcours compilés.

- K3-01 : la colline au-dessus d'un tunnel reste en place quand un plan d'eau abaisse le sol du même parcours.
- K3-04 : un grand lac, une rivière large ou une forêt longés par la route sont gardés (règle du bord).
- K3-05 : un cours d'eau qui sort du couloir et y rentre est coupé, sans faux tronçon droit.
- K3-06 : le contrôle des anneaux qui se recoupent donne le même résultat, en une fraction du temps.

Réseau coupé : réponses Overpass fabriquées, MNT synthétique.
"""

from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path

import numpy as np
import pytest

from conftest import ORIGIN, straight_north, to_latlon, write_gpx
from openride_compiler import cli
from openride_compiler import osm_layers as L
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.terrain import load_terrain_tiles
from openride_compiler.verify import verify_world
from test_bridges import FakeClient
from test_tunnels import HILL_Z, WAYS, _near_y, hill


def _geom(xz: list[tuple[float, float]]) -> list[dict]:
    lat, lon = to_latlon([p[0] for p in xz], [p[1] for p in xz])
    return [{"lat": float(a), "lon": float(o)} for a, o in zip(lat, lon)]


def area(wid: int, xz: list[tuple[float, float]], **tags) -> dict:
    """Aire fermée (way) aux étiquettes `tags`, sommets (x, z) dans le repère du parcours."""
    return {"type": "way", "id": wid, "tags": tags, "geometry": _geom(list(xz) + [xz[0]])}


def line(wid: int, xz: list[tuple[float, float]], **tags) -> dict:
    return {"type": "way", "id": wid, "tags": tags, "geometry": _geom(xz)}


def rect(x0: float, x1: float, z0: float, z1: float) -> list[tuple[float, float]]:
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]


class OsmClient(FakeClient):
    """Voies du parcours (ponts, tunnels) par `fetch_query`, couches OSM par `fetch_for_route`."""

    def __init__(self, ways: list[dict], elements: list[dict]) -> None:
        super().__init__(ways)
        self.elements = elements

    def fetch_for_route(self, route, frame) -> list[dict]:
        return [{"elements": self.elements}]

    def fetch_coast(self, route, frame) -> list[dict]:
        return [{"elements": []}]


@pytest.fixture
def hill_dem(monkeypatch):
    monkeypatch.setattr(cli, "make_provider", lambda offline, log=None: SyntheticProvider(*ORIGIN, hill))


def build(tmp_path: Path, monkeypatch, layers: str, elements: list[dict], ways=WAYS) -> Path:
    gpx = write_gpx(tmp_path / "trace.gpx", *straight_north(length=3000.0)[:2])
    monkeypatch.setattr(cli, "make_osm_client", lambda offline, log=None: OsmClient(ways, elements))
    assert cli.main(["build", str(gpx), "--out", str(tmp_path / "routes"), "--force", "--no-horizon",
                     "--layers", layers]) == 0
    return tmp_path / "routes" / "trace.world"


def water_items(world: Path) -> tuple[list[dict], list[dict]]:
    lines, areas = [], []
    for p in sorted((world / "water").glob("chunk_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        lines += d.get("lines", [])
        areas += d.get("areas", [])
    return lines, areas


# Étang à 900 m du tunnel (sommet de la colline en z = −1 500), à 60 m de la route
POND = area(9001, rect(60.0, 110.0, -620.0, -580.0), natural="water", water="pond")


# --- K3-01 ------------------------------------------------------------------------------------------------------


def test_k3_01_hill_over_tunnel_kept_with_a_pond(tmp_path: Path, monkeypatch, hill_dem) -> None:
    world = build(tmp_path, monkeypatch, "route,terrain,water,tunnels", [POND])
    _, areas = water_items(world)
    assert [a["id"] for a in areas] == ["w9001"]
    tiles = load_terrain_tiles(world)["near"]
    assert _near_y(tiles, 85.0, -600.0) < areas[0]["level_y"]          # sol abaissé sous l'étang : le rappel a lieu
    assert _near_y(tiles, 0.0, HILL_Z) > 1075.0 + 30.0                 # la colline reste au-dessus du tube
    assert verify_world(world) == []


def test_k3_01_add_layer_terrain_and_water_keep_the_hill(tmp_path: Path, monkeypatch, hill_dem) -> None:
    world = build(tmp_path, monkeypatch, "route,terrain,water,tunnels", [POND])
    for layer in ("terrain", "water"):
        assert cli.main(["add-layer", str(world), layer]) == 0
        tiles = load_terrain_tiles(world)["near"]
        assert _near_y(tiles, 0.0, HILL_Z) > 1075.0 + 30.0, layer
    assert verify_world(world) == []


def test_k3_01_sink_under_water_passes_tunnels(monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(cli, "sink_route_tiles", lambda *a, **k: 3)
    monkeypatch.setattr(cli, "fit_route_ground", lambda tiles, route, level, spans, tunnels=None:
                        seen.update(spans=spans, tunnels=tunnels))
    cli._sink_under_water({"near": {(0, 0): None}}, {}, [], [[0.0, 50.0], [100.0, 200.0]],
                          tunnels=[[100.0, 200.0]])
    assert seen == {"spans": [[0.0, 50.0], [100.0, 200.0]], "tunnels": [[100.0, 200.0]]}


# --- K3-04 et K3-05 ---------------------------------------------------------------------------------------------


def test_k3_04_large_areas_along_the_road_are_kept(tmp_path: Path, monkeypatch, hill_dem) -> None:
    elements = [
        area(1, rect(50.0, 2050.0, -2500.0, -500.0), natural="water"),                 # lac de 2 km, rive à 50 m
        area(2, rect(-2030.0, -30.0, -2500.0, -500.0), natural="wood"),                # forêt de 2 km à 30 m
        area(3, rect(50.0, 350.0, -300.0, -100.0), natural="water", water="pond"),     # étang témoin
        area(4, rect(-3000.0, -2500.0, -2000.0, -1000.0), natural="water"),            # lac loin : écarté
    ]
    world = build(tmp_path, monkeypatch, "route,terrain,water,vegetation", elements, ways=[])
    _, areas = water_items(world)
    assert sorted(a["id"] for a in areas) == ["w1", "w3"]
    veg = []
    for p in (world / "vegetation").glob("chunk_*.json"):
        veg += json.loads(p.read_text(encoding="utf-8"))["areas"]
    assert [v["id"] for v in veg] == ["w2"]
    assert verify_world(world) == []


def test_k3_04_wide_river_along_the_road_is_kept(tmp_path: Path, monkeypatch, hill_dem) -> None:
    river = area(5, rect(50.0, 950.0, -3200.0, 200.0), natural="water", water="river")   # 900 m de large
    world = build(tmp_path, monkeypatch, "route,terrain,water", [river], ways=[])
    _, areas = water_items(world)
    pieces = [a for a in areas if a["kind"] == "river"]
    assert pieces, "rivière large longée par la route écartée"
    # morceaux de la première colonne de carrés, sur toute la longueur du parcours (pas de coupure droite)
    zs = sorted({min(p[1] for p in a["outer"]) for a in pieces})
    assert zs[0] <= -3000.0 and zs[-1] >= -1000.0
    assert verify_world(world) == []


def test_k3_05_stream_leaving_and_reentering_is_cut(tmp_path: Path, monkeypatch, hill_dem) -> None:
    stream = line(7, [(200.0, -1000.0), (200.0, -1200.0), (600.0, -1300.0), (600.0, -1600.0),
                      (200.0, -1700.0), (200.0, -1900.0)], waterway="stream")
    world = build(tmp_path, monkeypatch, "route,terrain,water", [stream], ways=[])
    lines, _ = water_items(world)
    assert len(lines) >= 2 and all(ln["id"].startswith("w7_") for ln in lines)
    for ln in lines:
        pts = np.asarray(ln["points"], dtype=float)
        assert float(np.hypot(*np.diff(pts[:, :2], axis=0).T).max()) <= 26.0   # densifiée à 25 m, pas de saut
        assert float(np.abs(pts[:, 0]).max()) <= 400.0 + 1e-6
    assert verify_world(world) == []


# --- K3-06 ------------------------------------------------------------------------------------------------------


def _reference(ring: list[list[float]]) -> bool:
    """Ancienne version en Python pur, en O(m²) (avant RC27)."""
    m = len(ring)
    if m < 4:
        return False
    for i in range(m):
        a, b = ring[i], ring[(i + 1) % m]
        for j in range(i + 2, m):
            if i == 0 and j == m - 1:
                continue
            if L._segments_intersect(a, b, ring[j], ring[(j + 1) % m]):
                return True
    return False


def test_k3_06_same_answer_as_the_reference() -> None:
    rnd = random.Random(27)
    hits = 0
    for _ in range(1500):
        m = rnd.randint(3, 25)
        if rnd.random() < 0.5:   # grille : points alignés, doublons, arêtes confondues
            ring = [[float(rnd.randint(0, 5)), float(rnd.randint(0, 5))] for _ in range(m)]
        else:                    # étoilé, parfois deux sommets échangés
            ang = sorted(rnd.random() * 2 * math.pi for _ in range(m))
            ring = [[math.cos(t) * (1 + rnd.random() / 2), math.sin(t) * (1 + rnd.random() / 2)] for t in ang]
            if rnd.random() < 0.5:
                i, j = rnd.randrange(m), rnd.randrange(m)
                ring[i], ring[j] = ring[j], ring[i]
        want = _reference(ring)
        hits += want
        assert L.is_self_intersecting(ring) == want, ring
    assert 200 < hits < 1300                                             # les deux cas sont bien couverts


def test_k3_06_large_ring_is_fast() -> None:
    n = 20_000
    ring = [[1000.0 * math.cos(2 * math.pi * k / n) * (1 + 0.01 * math.sin(74 * math.pi * k / n)),
             1000.0 * math.sin(2 * math.pi * k / n)] for k in range(n)]
    t0 = time.monotonic()
    assert L.is_self_intersecting(ring) is False
    crossed = ring[:]
    crossed[100], crossed[n // 2] = crossed[n // 2], crossed[100]
    assert L.is_self_intersecting(crossed) is True
    assert time.monotonic() - t0 < 5.0                                   # ~100 s avant RC27
    assert L.clean_and_orient_ring(ring) is not None
