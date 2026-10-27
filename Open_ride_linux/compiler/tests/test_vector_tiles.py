"""Tuiles vectorielles OpenFreeMap (lot W13) : conversion, recousage, doublons, préchargement, panne."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from openride_compiler.elevation import SyntheticProvider
from openride_compiler.errors import CompileError
from openride_compiler.worldgen import mvt, vector_tiles as vt
from openride_compiler.worldgen.graph import RoadGraph
from openride_compiler.worldgen.osmdb import OsmDb
from openride_compiler.worldgen.process import FakeClock, WorldSession
from openride_compiler.worldgen.squares import zone_frame
from openride_compiler.worldgen.store import WorldCache
from test_mvt import encode_tile

LAT, LON = 43.0, 4.6                    # point fictif en mer (comme W15)
TX, TY = mvt.lonlat_to_tile(14, LON, LAT)
E = 4096
S_LON, S_LAT = mvt.tile_to_lonlat(14, TX, TY, E, 1500, 2048)      # sur la route est-ouest de la grille


def road(fid: int, pts, **tags) -> dict:
    return {"id": fid, "type": 2, "tags": tags, "paths": [(pts, False)]}


def grid_tile(x: int, y: int) -> bytes:
    """Une ligne est-ouest et une ligne nord-sud par tuile, marge de 64 pixels comme OpenMapTiles."""
    return encode_tile({
        "transportation": [road(1, [(-64, 2048), (4160, 2048)], **{"class": "tertiary"}),
                           road(2, [(2048, -64), (2048, 4160)], **{"class": "minor"})],
        "building": [{"id": 3, "type": 3, "tags": {"render_height": 9},
                      "paths": [([(2200, 2200), (2260, 2200), (2260, 2240), (2200, 2240)], True)]}],
    })


class FakeNet:
    TEMPLATE = "https://tuiles.invalid/t/{z}/{x}/{y}.pbf"

    def __init__(self, tiles=grid_tile, tilejson_ok: bool = True) -> None:
        self.tiles = tiles
        self.tilejson_ok = tilejson_ok
        self.urls: list[str] = []

    def get(self, url: str) -> bytes:
        self.urls.append(url)
        if not self.tilejson_ok:
            raise CompileError(f"{url} : réseau injoignable")
        assert url == vt.TILEJSON_URL
        return json.dumps({"tiles": [self.TEMPLATE]}).encode()

    def download(self, url: str, dest: Path) -> int:
        self.urls.append(url)
        z, x, y = map(int, re.findall(r"/(\d+)/(\d+)/(\d+)\.pbf$", url)[0])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self.tiles(x, y))
        return dest.stat().st_size


def cache(tmp_path: Path, max_bytes: int = 10**9) -> WorldCache:
    return WorldCache(tmp_path / "cache", max_bytes, log=lambda _m: None)


def tile_bbox(x: int, y: int, nx: int = 1, ny: int = 1) -> tuple[float, float, float, float]:
    """Emprise des tuiles, rentrée d'un cheveu pour ne pas toucher les voisines."""
    w, s = mvt.tile_to_lonlat(14, x, y + ny, 1, 0, 0)
    e, n = mvt.tile_to_lonlat(14, x + nx, y, 1, 0, 0)
    eps = 1e-7
    return w + eps, s + eps, e - eps, n - eps


def test_road_cut_between_tiles_is_one_way_in_graph(tmp_path) -> None:
    def tiles(x: int, y: int) -> bytes:
        if x == TX:   # tuile ouest : route 1 entière dans la marge ; route 2 coupée à la marge (sommet propre)
            return encode_tile({"transportation": [
                road(1, [(1000, 1000), (E + 40, 1100)], **{"class": "tertiary"}),
                road(2, [(1000, 3000), (E + 64, 3000 + round(150 * (E + 64 - 1000) / (E + 3000 - 1000)))],
                     **{"class": "primary"})]})
        return encode_tile({"transportation": [
            road(1, [(1000 - E, 1000), (40, 1100)], **{"class": "tertiary"}),
            road(2, [(-64, 3000 + round(150 * (E - 64 - 1000) / (E + 3000 - 1000))), (3000, 3150)],
                 **{"class": "primary"})]})

    src = vt.TileSource(cache(tmp_path), FakeNet(tiles))
    assert src.ensure(tile_bbox(TX, TY, 2, 1)) == 2
    db = OsmDb(src.db_path)
    g = RoadGraph.build(db, tile_bbox(TX, TY, 2, 1), zone_frame("31T"))
    by_class = sorted((e.road_class, len(e.osm_nodes)) for e in g.edges.values())
    assert by_class == [("p", 3), ("t", 3)]                     # une arête par route, recousue au bord


def test_classes_bridges_and_unpaved(tmp_path) -> None:
    feats = [road(1, [(100, 100), (900, 100)], **{"class": "primary", "brunnel": "bridge"}),
             road(2, [(100, 300), (900, 300)], **{"class": "path", "subclass": "cycleway"}),
             road(3, [(100, 500), (900, 500)], **{"class": "track", "surface": "paved"}),
             road(4, [(100, 700), (900, 700)], **{"class": "track"}),
             road(5, [(100, 900), (900, 900)], **{"class": "minor", "surface": "unpaved"}),
             road(6, [(100, 1100), (900, 1100)], **{"class": "motorway", "oneway": 1}),
             road(7, [(100, 1300), (900, 1300)], **{"class": "secondary", "brunnel": "tunnel", "oneway": -1}),
             road(8, [(100, 1500), (900, 1500)], **{"class": "rail"})]
    data = encode_tile({"transportation": feats,
                        "waterway": [road(9, [(0, 2000), (4096, 2000)], **{"class": "river"})],
                        "water": [{"id": 10, "type": 3, "tags": {"class": "lake"},
                                   "paths": [([(3000, 3000), (5000, 3000), (5000, 3500), (3000, 3500)], True)]}],
                        "landcover": [{"id": 11, "type": 3, "tags": {"class": "wood", "subclass": "forest"},
                                       "paths": [([(100, 3000), (900, 3000), (900, 3500), (100, 3500)], True)]}],
                        "place": [{"id": 12, "type": 1, "tags": {"class": "village", "name": "Fictif"},
                                   "paths": [([(2000, 2500)], False)]}]})
    db = vt.TileDb(tmp_path / "t.sqlite")
    added = db.load(TX, TY, data)
    assert added == {"roads": 7, "areas": 2, "lines": 1, "points": 1}
    db.close()
    with OsmDb(tmp_path / "t.sqlite") as r:
        box = tile_bbox(TX - 1, TY - 1, 3, 3)
        assert sorted(v.road_class for v in r.roads_in(box, include_excluded=True)) == ["c", "k", "p", "s", "x", "x", "x"]
        assert sorted(v.road_class for v in r.roads_in(box)) == ["c", "k", "p", "s"]
        prim = next(v for v in r.roads_in(box) if v.road_class == "p")
        sec = next(v for v in r.roads_in(box) if v.road_class == "s")
        assert prim.bridge and not prim.tunnel and sec.tunnel and sec.oneway == -1
        lake = next(a for a in r.areas_in(box) if a.kind == "water")
        assert max(p[0] for p in lake.outer) == pytest.approx(tile_bbox(TX, TY)[2], abs=1e-6)     # découpé au bord
        assert [p.name for p in r.points_in(box)] == ["Fictif"]


def test_same_tile_twice_no_duplicates(tmp_path) -> None:
    src = vt.TileSource(cache(tmp_path), FakeNet())
    src.ensure(tile_bbox(TX, TY))
    first = src.db.counts()
    assert src.db.load(TX, TY, grid_tile(TX, TY)) == {}
    src.ensure(tile_bbox(TX, TY))
    assert src.db.counts() == first and first["roads"] >= 2


def _past_session(c: WorldCache, name: str, lat: float, lon: float, mtime: float) -> None:
    part = c.sessions_dir() / f"{name}.world" / "route" / "part_0.json"
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_text(json.dumps({"lat": [lat, lat], "lon": [lon, lon]}))
    import os
    os.utime(part, (mtime, mtime))


def test_prefetch_order_budget_and_eviction(tmp_path) -> None:
    c = cache(tmp_path, max_bytes=4_000_000)
    a, b = (LAT, LON), (LAT + 0.3, LON + 0.3)
    _past_session(c, "ow-1", *a, 1000.0)
    _past_session(c, "ow-2", *b, 3000.0)            # B plus récent, mais A deux fois
    _past_session(c, "ow-3", a[0] + 0.001, a[1], 2000.0)
    plan = vt.prefetch_plan(vt.past_starts(c), radius_km=3.0)
    assert [p["count"] for p in plan] == [2, 1] and plan[0]["lat"] == pytest.approx(a[0], abs=0.001)
    big = b"x" * 150_000

    src = vt.TileSource(c, FakeNet(lambda x, y: big))
    got = vt.prefetch(src, plan, tile_bytes=150_000)
    assert got["tiles"] > 0 and c.total_bytes() <= 0.9 * c.max_bytes
    entries = [e for e in c.entries() if e.kind == "tile"]
    assert entries and all(e.prefetch for e in entries)
    a_tiles = set(plan[0]["tiles"])
    fetched = {(int(e.key.split("/")[1]), int(e.key.split("/")[2])) for e in entries}
    assert a_tiles <= fetched or fetched <= a_tiles               # A d'abord : B seulement après A complet
    # Entrées ordinaires au-delà du plafond : les entrées préchargées partent en dernier.
    for k in range(10):
        p = c.root / "brut" / "dem" / f"t{k}.tif"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"d" * 300_000)
        c.add(f"dem:t{k}", "dem", p)
    removed = c.evict()
    kinds = [k.split(":")[0] for k in removed]
    assert kinds and all(k == "dem" for k in kinds[:kinds.index("tile")]) if "tile" in kinds else all(k == "dem" for k in kinds)



def test_tilejson_unavailable_session_continues_on_cache(tmp_path) -> None:
    c = cache(tmp_path)
    vt.TileSource(c, FakeNet()).ensure(tile_bbox(TX - 1, TY - 1, 3, 3))       # tuiles du départ déjà sur le PC
    logs: list[str] = []
    rec: list[dict] = []
    s = WorldSession(c, SyntheticProvider(LAT, LON), rec.append, {}, tmp_path / "s.world", network=True,
                     clock=FakeClock(1e12), log=logs.append)
    s.tile_net = FakeNet(tilejson_ok=False)
    s.handle({"type": "open", "lat": S_LAT, "lon": S_LON, "heading_deg": 90, "nav": "ride", "target": None,
              "loop_km": None, "seed": 1, "network": True})
    assert any("TileJSON OpenFreeMap indisponible" in m for m in logs)
    assert rec[-1]["type"] == "revision" and any(m["type"] == "status" and m["phase"] == "tiles" for m in rec)


def test_session_without_region_uses_vector_tiles(tmp_path) -> None:
    c = cache(tmp_path)
    rec: list[dict] = []
    s = WorldSession(c, SyntheticProvider(LAT, LON), rec.append, {}, tmp_path / "s.world", network=True,
                     clock=FakeClock(), log=lambda _m: None)
    s.tile_net = FakeNet()
    s.handle({"type": "open", "lat": S_LAT, "lon": S_LON, "heading_deg": 90, "nav": "ride", "target": None,
              "loop_km": None, "seed": 1, "network": True})
    assert rec[-1]["type"] == "revision" and rec[-1]["length_m"] >= 3000
    assert s.tiles is not None and s.tiles.downloads >= 4
    assert c.get(vt.tile_key(TX, TY)) is not None
    with pytest.raises(CompileError):
        vt.TileSource(cache(tmp_path / "b"), FakeNet(), network=False).template()
