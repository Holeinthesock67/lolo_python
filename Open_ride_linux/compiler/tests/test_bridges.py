"""Ponts dessinés (lot EA4, `bridges.py`) : portions en pont accrochées aux voies OSM `bridge=*`, profil en
ligne droite, terrain non fondu sous le pont, tablier et piles ; `build` et `add-layer bridges` ; monde ouvert
(spans « bridge » des arêtes, carré du milieu du pont). Réseau coupé : réponses Overpass fabriquées."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from conftest import ORIGIN, WORLD_CONTRACTS, straight_north, to_latlon, write_gpx
from openride_compiler import bridges as BR
from openride_compiler import cli
from openride_compiler import constants as C
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.terrain import load_terrain_tiles
from openride_compiler.verify import verify_world
from openride_compiler.worldgen import squares
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
from openride_compiler.worldgen.squares import SquareKey, generate_square
from openride_compiler.worldgen.store import WorldCache

VALLEY_Z = (-1700.0, -1300.0)   # vallée de 30 m de fond, 400 m de large, sous le pont de 1 300 à 1 700 m


def valley(x, z):
    """Plan à 5 % (celui de `straight_north`) creusé d'une vallée en auge entre z = −1 700 et −1 300."""
    z = np.asarray(z, dtype=float)
    base = 1000.0 - 0.05 * z + 0.0 * np.asarray(x, dtype=float)
    d = np.minimum(np.clip(z - VALLEY_Z[0], 0.0, None), np.clip(VALLEY_Z[1] - z, 0.0, None))
    return base - np.clip(d / 60.0, 0.0, 1.0) * 30.0


def way(wid: int, xz: list[tuple[float, float]], **tags) -> dict:
    lat, lon = to_latlon([p[0] for p in xz], [p[1] for p in xz])
    return {"type": "way", "id": wid, "tags": {"highway": "unclassified", **tags},
            "geometry": [{"lat": float(a), "lon": float(o)} for a, o in zip(lat, lon)]}


WAYS = [way(1, [(0.0, 10.0), (0.0, -1300.0)]),
        way(2, [(0.0, -1300.0), (0.0, -1700.0)], bridge="yes", layer="1"),
        way(3, [(0.0, -1700.0), (0.0, -3100.0)]),
        way(4, [(-200.0, -500.0), (200.0, -500.0)], bridge="yes")]   # pont perpendiculaire : ignoré


class FakeClient:
    def __init__(self, ways: list[dict]) -> None:
        self.ways = ways

    def fetch_query(self, query: str) -> dict:
        surface_query = all('way["highway"](' in ln for ln in query.splitlines() if ln.startswith("  "))
        return {"elements": self.ways if surface_query else []}

    def fetch_for_route(self, route, frame) -> list[dict]:
        return [{"elements": []}]


@pytest.fixture
def valley_dem(monkeypatch):
    monkeypatch.setattr(cli, "make_provider", lambda offline, log=None: SyntheticProvider(*ORIGIN, valley))


def build(tmp_path: Path, monkeypatch, layers: str, ways=WAYS) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    gpx = write_gpx(tmp_path / "trace.gpx", *straight_north(length=3000.0)[:2])   # altitude du MNT
    monkeypatch.setattr(cli, "make_osm_client", lambda offline, log=None: FakeClient(ways))
    assert cli.main(["build", str(gpx), "--out", str(tmp_path / "routes"), "--force", "--no-horizon",
                     "--layers", layers]) == 0
    return tmp_path / "routes" / "trace.world"


def _json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_spans_from_flags_pad_merge_and_min_length() -> None:
    s = np.arange(0.0, 501.0, 10.0)
    flags = [False] * len(s)
    for i in (10, 11, 12, 14, 15, 30):      # 100–120 et 140–150 (trou de 20 m : rejointes), 300 seul
        flags[i] = True
    assert BR.spans_from_flags(s, flags, 500.0) == [[95.0, 155.0], [295.0, 305.0]]
    assert BR.spans_from_flags(s, [True] * len(s), 500.0) == [[0.0, 500.0]]
    assert BR.spans_from_flags(s, [False] * len(s), 500.0) == []


def test_flatten_spans_is_a_straight_line_with_margin() -> None:
    s = np.arange(0.0, 201.0, 10.0)
    alt = 100.0 - 20.0 * ((s > 60) & (s < 140))
    out = BR.flatten_spans(s, alt, [[70.0, 130.0]])
    inside = (s >= 60) & (s <= 140)
    assert np.allclose(out[inside], 100.0) and np.array_equal(out[~inside], alt[~inside])


def test_bridge_item_piers_only_where_high_and_long() -> None:
    s = np.arange(0.0, 401.0, 10.0)
    x, z, y = np.zeros_like(s), -s, np.full_like(s, 100.0)

    def ground(xs, zs):
        return np.where(np.asarray(zs) < -200.0, 60.0, 98.0)   # sol à 2 m sous le tablier, puis à 40 m
    item = BR.bridge_item("b0", s, x, z, y, 50.0, 350.0, ground)
    assert item["points"][0][:2] == [0.0, -50.0] and item["points"][-1][:2] == [0.0, -350.0]
    assert item["length_m"] == 300.0 and item["half_width_m"] == C.ROAD_HALF_WIDTH_M
    piers = item["piers"]
    assert piers and all(p[1] < -200.0 for p in piers)                   # aucune pile là où le sol est à 2 m
    assert all(p[2] == 100.0 and p[3] == 60.0 - BR.PIER_EMBED_M for p in piers)
    gaps = np.diff([-p[1] for p in piers])
    assert np.all(gaps <= BR.PIER_SPACING_M + 1e-6)
    assert BR.bridge_item("b1", s, x, z, y, 50.0, 70.0, ground)["piers"] == []   # pont court : pas de pile
    assert BR.bridge_item("b2", s, x, z, y, 50.0, 55.0, ground) is None


def test_build_flattens_profile_keeps_valley_and_draws_bridge(tmp_path: Path, monkeypatch, valley_dem) -> None:
    world = build(tmp_path, monkeypatch, "route,terrain,bridges")
    manifest = _json(world / "manifest.json")
    route = _json(world / "route.json")
    info = manifest["layers"]["bridges"]
    assert info["present"] and info["count"] == 1 and info["piers"] > 0
    (s0, s1), = info["spans"]
    assert abs(s0 - 1295.0) <= 10.0 and abs(s1 - 1705.0) <= 10.0
    s = BR.route_s(route)
    on = (s > s0) & (s < s1)
    alt = np.asarray(route["alt_m"])
    plane = 1000.0 + 0.05 * s
    assert np.allclose(np.diff(alt[on], 2), 0.0, atol=0.02)           # en ligne droite d'une culée à l'autre
    assert np.allclose(alt[on], plane[on], atol=2.0)                  # la vallée (30 m) ne tire plus la route
    assert np.all(np.abs(np.asarray(route["grade_pct"])[on]) < 6.0)     # plus de ± 25 % dans la vallée
    # Terrain proche : la vallée reste sous le pont (pas de fondu), la route est fondue ailleurs
    tiles = load_terrain_tiles(world)["near"]
    g = tiles[(0, -2)]                                                 # z de −2 000 à −1 000
    j = int(round((-1500.0 + 2000.0) / C.NEAR_CELL_M))
    assert float(g[j, 0]) < 1075.0 - 25.0                              # fond de vallée sous le pont
    (k, items), = ((int(p.stem.split("_")[1]), _json(p)["bridges"]) for p in (world / "bridges").glob("chunk_*.json"))
    assert k == 1 and len(items) == 1
    b = items[0]
    xs = np.interp([-p[1] for p in b["points"]], -np.asarray(route["z"]), np.asarray(route["x"]))
    assert np.allclose([p[0] for p in b["points"]], xs, atol=0.05)    # axe du tablier sur la route
    clear = [p[2] - p[3] - BR.PIER_EMBED_M for p in b["piers"]]
    assert min(clear) >= BR.PIER_MIN_CLEAR_M - 0.01 and max(clear) > 25.0   # piles hautes au fond de la vallée
    assert verify_world(world) == []
    schema = _json(WORLD_CONTRACTS / "bridges.schema.json")
    jsonschema.validate(_json(world / "bridges" / "chunk_1.json"), schema)
    jsonschema.validate(manifest, _json(WORLD_CONTRACTS / "manifest.schema.json"))


def test_without_bridges_layer_nothing_changes(tmp_path: Path, monkeypatch, valley_dem) -> None:
    world = build(tmp_path, monkeypatch, "route,terrain")
    assert "bridges" not in _json(world / "manifest.json")["layers"]
    assert not (world / "bridges").exists()
    alt = np.asarray(_json(world / "route.json")["alt_m"])
    assert alt.min() < 1000.0 + 0.05 * 1500.0 - 20.0                   # la route plonge dans la vallée


def test_add_layer_bridges_gives_the_same_world_as_build(tmp_path: Path, monkeypatch, valley_dem) -> None:
    full = build(tmp_path / "a", monkeypatch, "route,terrain,bridges")
    later = build(tmp_path / "b", monkeypatch, "route,terrain")
    assert cli.main(["add-layer", str(later), "bridges"]) == 0
    assert _json(later / "route.json") == _json(full / "route.json")
    assert _json(later / "bridges" / "chunk_1.json") == _json(full / "bridges" / "chunk_1.json")
    a, b = load_terrain_tiles(full)["near"], load_terrain_tiles(later)["near"]
    assert a.keys() == b.keys() and all(np.array_equal(a[k], b[k]) for k in a)
    assert verify_world(later) == []
    # rejouée, rien ne bouge (à l'arrondi du centimètre près)
    assert cli.main(["add-layer", str(later), "bridges"]) == 0
    again, ref = _json(later / "route.json"), _json(full / "route.json")
    assert np.allclose(again["alt_m"], ref["alt_m"], atol=0.011)
    assert _json(later / "manifest.json")["layers"]["bridges"]["spans"] == _json(full / "manifest.json")["layers"]["bridges"]["spans"]


# --- monde ouvert ------------------------------------------------------------------------------------

ZONE = "31T"
FRAME = squares.zone_frame(ZONE)
IX, IN = 682, 4892


def lonlat(e, n):
    lat, lon = FRAME.to_latlon(np.array([e]), np.array([-n]))
    return float(lon[0]), float(lat[0])


class GorgeProvider:
    """Plateau à 300 m, gorge de 40 m de fond entre E = IX·1000 + 400 et + 600."""

    name = "gorge"
    native_resolution_m = 30.0

    def elevations(self, lat, lon):
        x, _ = FRAME.to_xz(np.asarray(lat, float), np.asarray(lon, float))
        e = np.asarray(x) - IX * 1000.0
        d = np.minimum(np.clip(e - 400.0, 0.0, None), np.clip(600.0 - e, 0.0, None))
        return 300.0 - np.clip(d / 30.0, 0.0, 1.0) * 40.0


def test_open_world_bridge_in_the_square_of_its_middle(tmp_path: Path) -> None:
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/pont")
    n = IN * 1000 + 500
    e = IX * 1000
    w.add_road(1, {"highway": "tertiary"}, [1, 2], [lonlat(e + 100, n), lonlat(e + 400, n)])
    w.add_road(2, {"highway": "tertiary", "bridge": "yes", "layer": "1"}, [2, 3], [lonlat(e + 400, n), lonlat(e + 600, n)])
    w.add_road(3, {"highway": "tertiary"}, [3, 4], [lonlat(e + 600, n), lonlat(e + 1400, n)])
    w.finish(osm_date="2026-11-16T00:00:00Z")
    db = OsmDb(tmp_path / "osm.sqlite")
    cache = WorldCache(tmp_path / "cache", 10**9, log=lambda _m: None)
    a = generate_square(SquareKey(ZONE, IX, IN), db, GorgeProvider(), cache)
    b = generate_square(SquareKey(ZONE, IX + 1, IN), db, GorgeProvider(), cache)
    da, db_ = _json(a / "bridges.json"), _json(b / "bridges.json")
    assert da["version"] == BR.BRIDGES_VERSION and db_["bridges"] == []
    (item,) = da["bridges"]
    xs = [p[0] for p in item["points"]]
    assert min(xs) == pytest.approx(400.0, abs=1.0) and max(xs) == pytest.approx(600.0, abs=1.0)   # relatives au coin
    assert all(p[2] == pytest.approx(300.0, abs=0.5) for p in item["points"])                      # tablier à plat
    assert item["piers"] and all(p[2] - p[3] > 30.0 for p in item["piers"])
    jsonschema.validate(da, _json(WORLD_CONTRACTS / "bridges.schema.json"))
    near = np.frombuffer((a / "near.f32").read_bytes(), dtype="<f4").reshape(101, 101)
    assert float(near.min()) < 270.0                       # la gorge n'est pas comblée sous le pont
    assert _json(a / "meta.json")["counts"]["bridges"] == 1
