"""Requêtes du menu du monde ouvert (lot W11) : recherche, carte simplifiée à 20 m, régions, épinglage."""

from __future__ import annotations

import json
import math

import pytest

from openride_compiler.worldgen import menu_query
from openride_compiler.worldgen.osmdb import OsmDbWriter
from openride_compiler.worldgen.store import WorldCache

LAT, LON = 44.1740, 5.2788      # sommet du Ventoux


@pytest.fixture
def cache(tmp_path) -> WorldCache:
    c = WorldCache(tmp_path / "monde", 10_000_000, dem_dir=tmp_path / "dem", log=lambda _: None)
    c.set_region("provence", "Provence", [4.2, 42.9, 7.7, 45.2])
    c.osm_db_path("provence").parent.mkdir(parents=True, exist_ok=True)
    w = OsmDbWriter(c.osm_db_path("provence"), "geofabrik", "provence")
    # Route presque droite de 3 km avec un léger zigzag de 5 m, plus une route éloignée.
    pts = [(LON + i * 0.0003, LAT + (0.00004 if i % 2 else 0.0)) for i in range(120)]
    w.add_road(1, {"highway": "tertiary"}, list(range(len(pts))), pts)
    w.add_road(2, {"highway": "motorway"}, [900, 901], [(LON, LAT), (LON + 0.01, LAT)])
    w.add_road(3, {"highway": "residential"}, [902, 903], [(LON + 0.5, LAT + 0.5), (LON + 0.51, LAT + 0.5)])
    w.add_point("n1", "mountain_pass", "Mont Ventoux", LON, LAT)
    w.add_point("n2", "village", "Bédoin", 5.18, 44.12)
    w.finish()
    c.add("brut:provence", "osm", c.osm_db_path("provence"), region="provence")
    return c


def test_simplify_keeps_every_point_within_tolerance() -> None:
    pts = [(i * 10.0, 4.0 * math.sin(i)) for i in range(200)]
    kept = menu_query.simplify(pts, 20.0)
    assert 2 <= len(kept) < len(pts) and kept[0] == pts[0] and kept[-1] == pts[-1]
    assert menu_query.simplify(pts[:2]) == pts[:2]
    kept_idx = [pts.index(p) for p in kept]
    for a, b in zip(kept_idx, kept_idx[1:]):
        (ax, az), (bx, bz) = pts[a], pts[b]
        for i in range(a + 1, b):
            d = abs((bx - ax) * (az - pts[i][1]) - (ax - pts[i][0]) * (bz - az)) / math.hypot(bx - ax, bz - az)
            assert d <= 20.0 + 1e-9


def test_world_map_roads_simplified_and_relative(cache) -> None:
    roads = menu_query.world_map(cache, LAT, LON, 5000.0)
    assert [r["c"] for r in roads] == ["t"]                         # autoroute exclue, route lointaine hors du rayon
    xz = roads[0]["xz"]
    assert len(xz) % 2 == 0 and len(xz) <= 8                        # le zigzag de 5 m disparaît
    assert xz[0] == 0 and xz[1] in (0, -4, -5)                      # première coupe au point demandé
    assert xz[-2] == pytest.approx(119 * 0.0003 * 111320 * math.cos(math.radians(LAT)), abs=2)
    assert all(isinstance(v, int) for v in xz)
    assert menu_query.world_map(cache, 10.0, 10.0, 5000.0) == []     # hors de toute région


def test_search_and_regions(cache) -> None:
    items = menu_query.search(cache, "ventoux")
    assert [(i["name"], i["kind"], i["cached"], i["source"]) for i in items] == [("Mont Ventoux", "mountain_pass", True, "base")]
    assert menu_query.search(cache, "bedoin")[0]["name"] == "Bédoin"
    assert menu_query.search(cache, "zzz") == []
    out = menu_query.regions(cache)
    assert out["cache_max_bytes"] == 10_000_000 and out["items"][0]["id"] == "provence" and not out["items"][0]["pinned"]
    assert out["items"][0]["last_used"] is None or out["items"][0]["last_used"].endswith("Z")


def test_cli_outputs_one_json_line(cache, tmp_path, capsys, monkeypatch) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[open_world]\ncache_dir = "{cache.root}"\n', encoding="utf-8")
    assert menu_query.main(["--config", str(cfg), "search", "--text", "ventoux"]) == 0
    assert json.loads(capsys.readouterr().out)["items"][0]["name"] == "Mont Ventoux"
    assert menu_query.main(["--config", str(cfg), "pin", "--region", "provence", "--pinned", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["items"][0]["pinned"] is True
    assert menu_query.main(["--config", str(cfg), "map", "--lat", str(LAT), "--lon", str(LON), "--radius", "4000"]) == 0
    assert len(json.loads(capsys.readouterr().out)["roads"]) == 1
