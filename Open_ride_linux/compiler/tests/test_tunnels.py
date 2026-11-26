"""Tunnels dessinés (lot EA5, `tunnels.py`) : portions en tunnel accrochées aux voies OSM `tunnel=*`, profil en
ligne droite, colline gardée au-dessus (ni fondu ni garde-fou), axe du tube ; `build` et `add-layer tunnels` ;
monde ouvert (spans « tunnel » des arêtes, carré du milieu du tunnel). Réseau coupé : réponses Overpass fabriquées."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from conftest import ORIGIN, WORLD_CONTRACTS, straight_north, write_gpx
from openride_compiler import bridges as BR
from openride_compiler import cli
from openride_compiler import constants as C
from openride_compiler import terrain
from openride_compiler import tunnels as TU
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.terrain import load_terrain_tiles
from openride_compiler.verify import verify_world
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
from openride_compiler.worldgen.squares import SquareKey, generate_square
from openride_compiler.worldgen.store import WorldCache
from test_bridges import IN, IX, ZONE, FakeClient, lonlat, way

HILL_Z = -1500.0                 # sommet de la colline de 40 m, sous le tunnel de 1 350 à 1 650 m


def hill(x, z):
    """Plan à 5 % (celui de `straight_north`) avec une colline de 40 m centrée en z = −1 500 (écart type 60 m)."""
    z = np.asarray(z, dtype=float)
    return 1000.0 - 0.05 * z + 40.0 * np.exp(-((z - HILL_Z) ** 2) / (2 * 60.0 ** 2)) + 0.0 * np.asarray(x, float)


WAYS = [way(1, [(0.0, 10.0), (0.0, -1350.0)]),
        way(2, [(0.0, -1350.0), (0.0, -1650.0)], tunnel="yes", layer="-1"),
        way(3, [(0.0, -1650.0), (0.0, -3100.0)]),
        way(4, [(-200.0, -500.0), (200.0, -500.0)], tunnel="yes")]   # tunnel perpendiculaire : ignoré


@pytest.fixture
def hill_dem(monkeypatch):
    monkeypatch.setattr(cli, "make_provider", lambda offline, log=None: SyntheticProvider(*ORIGIN, hill))


def build(tmp_path: Path, monkeypatch, layers: str, ways=WAYS) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    gpx = write_gpx(tmp_path / "trace.gpx", *straight_north(length=3000.0)[:2])   # altitude du MNT
    monkeypatch.setattr(cli, "make_osm_client", lambda offline, log=None: FakeClient(ways))
    assert cli.main(["build", str(gpx), "--out", str(tmp_path / "routes"), "--force", "--no-horizon",
                     "--layers", layers]) == 0
    return tmp_path / "routes" / "trace.world"


def _json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _near_y(tiles, x: float, z: float) -> float:
    """Altitude du terrain proche au sommet de grille le plus près de (x, z)."""
    ix, iz = int(np.floor(x / C.NEAR_TILE_M)), int(np.floor(z / C.NEAR_TILE_M))
    g = tiles[(ix, iz)]
    i = int(round((x - ix * C.NEAR_TILE_M) / C.NEAR_CELL_M))
    j = int(round((z - iz * C.NEAR_TILE_M) / C.NEAR_CELL_M))
    return float(g[j, i])


def test_is_tunnel_and_merge_spans() -> None:
    assert TU.is_tunnel({"tunnel": "yes"}) and TU.is_tunnel({"tunnel": "building_passage"})
    assert not TU.is_tunnel({"tunnel": "no"}) and not TU.is_tunnel({})
    assert TU.merge_spans([[0.0, 10.0], [50.0, 60.0]], [[5.0, 20.0]]) == [[0.0, 20.0], [50.0, 60.0]]
    assert TU.merge_spans([], []) == []


def test_tunnel_item_axis_and_min_length() -> None:
    s = np.arange(0.0, 401.0, 10.0)
    x, z, y = np.zeros_like(s), -s, 100.0 + 0.05 * s
    item = TU.tunnel_item("t0", s, x, z, y, 55.0, 345.0)
    assert item["kind"] == "tunnel" and item["length_m"] == 290.0 and item["half_width_m"] == C.ROAD_HALF_WIDTH_M
    assert item["points"][0] == [0.0, -55.0, 102.75] and item["points"][-1] == [0.0, -345.0, 117.25]
    assert len(item["points"]) == 2 + 29                                 # bouts + points du profil dedans
    assert TU.tunnel_item("t1", s, x, z, y, 50.0, 55.0) is None


def test_build_keeps_the_hill_over_the_tunnel(tmp_path: Path, monkeypatch, hill_dem) -> None:
    world = build(tmp_path, monkeypatch, "route,terrain,tunnels")
    manifest = _json(world / "manifest.json")
    route = _json(world / "route.json")
    info = manifest["layers"]["tunnels"]
    assert info["present"] and info["count"] == 1
    (s0, s1), = info["spans"]
    assert abs(s0 - 1345.0) <= 10.0 and abs(s1 - 1655.0) <= 10.0
    s = BR.route_s(route)
    on = (s > s0) & (s < s1)
    alt = np.asarray(route["alt_m"])
    plane = 1000.0 + 0.05 * s
    mid = (s > s0 + 30.0) & (s < s1 - 30.0)                            # lissage aux bouts (Savitzky-Golay)
    assert np.allclose(np.diff(alt[mid], 2), 0.0, atol=0.02)          # en ligne droite d'un portail à l'autre
    assert np.allclose(alt[on], plane[on], atol=3.0)                  # la colline ne soulève plus la route
    # Terrain proche : la colline reste au-dessus du tunnel ; à ciel ouvert, rien ne dépasse la chaussée
    tiles = load_terrain_tiles(world)["near"]
    assert _near_y(tiles, 0.0, HILL_Z) > 1075.0 + 30.0
    x, z = np.asarray(route["x"]), np.asarray(route["z"])
    for a, b in terrain.open_pieces(route, info["spans"]):
        ex, _x, _z = terrain.terrain_excess(tiles, x[a:b], z[a:b], alt[a:b])
        assert len(ex) and float(ex.max()) <= 1e-3
    (k, items), = ((int(p.stem.split("_")[1]), _json(p)["tunnels"]) for p in (world / "tunnels").glob("chunk_*.json"))
    assert k == 1 and len(items) == 1
    t = items[0]
    assert t["s0_m"] == pytest.approx(s0) and t["s1_m"] == pytest.approx(s1)
    assert np.allclose([p[0] for p in t["points"]], 0.0, atol=0.05)    # axe du tube sur la route
    assert np.allclose([p[2] for p in t["points"]], np.interp([-p[1] for p in t["points"]], s, alt), atol=0.02)
    assert verify_world(world) == []
    jsonschema.validate(_json(world / "tunnels" / "chunk_1.json"), _json(WORLD_CONTRACTS / "tunnels.schema.json"))
    jsonschema.validate(manifest, _json(WORLD_CONTRACTS / "manifest.schema.json"))
    assert manifest["format_version"] == C.FORMAT_VERSION == "1.11"


def test_without_tunnels_layer_the_road_still_cuts_the_hill(tmp_path: Path, monkeypatch, hill_dem) -> None:
    """Sans la couche (parcours d'avant EA5), la règle d'avant reste : garde-fou sur toute la route."""
    world = build(tmp_path, monkeypatch, "route,terrain")
    assert "tunnels" not in _json(world / "manifest.json")["layers"]
    assert not (world / "tunnels").exists()
    route = _json(world / "route.json")
    tiles = load_terrain_tiles(world)["near"]
    y_road = float(np.interp(-HILL_Z, BR.route_s(route), route["alt_m"]))
    assert _near_y(tiles, 0.0, HILL_Z) <= y_road


def test_tunnels_and_bridges_together(tmp_path: Path, monkeypatch, hill_dem) -> None:
    ways = WAYS[:2] + [way(3, [(0.0, -1650.0), (0.0, -2400.0)]), way(5, [(0.0, -2400.0), (0.0, -2500.0)], bridge="yes"),
                       way(6, [(0.0, -2500.0), (0.0, -3100.0)])]
    world = build(tmp_path, monkeypatch, "route,terrain,bridges,tunnels", ways)
    layers = _json(world / "manifest.json")["layers"]
    assert layers["tunnels"]["count"] == 1 and layers["bridges"]["count"] == 1
    assert verify_world(world) == []


def test_add_layer_tunnels_gives_the_same_world_as_build(tmp_path: Path, monkeypatch, hill_dem) -> None:
    full = build(tmp_path / "a", monkeypatch, "route,terrain,tunnels")
    later = build(tmp_path / "b", monkeypatch, "route,terrain")
    assert cli.main(["add-layer", str(later), "tunnels"]) == 0
    assert _json(later / "route.json") == _json(full / "route.json")
    assert _json(later / "tunnels" / "chunk_1.json") == _json(full / "tunnels" / "chunk_1.json")
    a, b = load_terrain_tiles(full)["near"], load_terrain_tiles(later)["near"]
    assert a.keys() == b.keys() and all(np.array_equal(a[k], b[k]) for k in a)
    assert verify_world(later) == []
    # le terrain refait seul garde la colline (portions relues au manifeste)
    assert cli.main(["add-layer", str(later), "terrain", "--no-horizon"]) == 0
    tiles = load_terrain_tiles(later)["near"]
    assert _near_y(tiles, 0.0, HILL_Z) > 1075.0 + 30.0


# --- monde ouvert ------------------------------------------------------------------------------------

class HillProvider:
    """Plateau à 300 m, colline de 40 m centrée en E = IX·1000 + 500 (écart type 60 m)."""

    name = "colline"
    native_resolution_m = 30.0

    def elevations(self, lat, lon):
        from test_bridges import FRAME
        x, _ = FRAME.to_xz(np.asarray(lat, float), np.asarray(lon, float))
        e = np.asarray(x) - IX * 1000.0
        return 300.0 + 40.0 * np.exp(-((e - 500.0) ** 2) / (2 * 60.0 ** 2))


def test_open_world_tunnel_in_the_square_of_its_middle(tmp_path: Path) -> None:
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/tunnel")
    n = IN * 1000 + 500
    e = IX * 1000
    w.add_road(1, {"highway": "tertiary"}, [1, 2], [lonlat(e + 100, n), lonlat(e + 350, n)])
    w.add_road(2, {"highway": "tertiary", "tunnel": "yes", "layer": "-1"}, [2, 3],
               [lonlat(e + 350, n), lonlat(e + 650, n)])
    w.add_road(3, {"highway": "tertiary"}, [3, 4], [lonlat(e + 650, n), lonlat(e + 1400, n)])
    w.finish(osm_date="2026-11-20T00:00:00Z")
    db = OsmDb(tmp_path / "osm.sqlite")
    cache = WorldCache(tmp_path / "cache", 10**9, log=lambda _m: None)
    a = generate_square(SquareKey(ZONE, IX, IN), db, HillProvider(), cache)
    b = generate_square(SquareKey(ZONE, IX + 1, IN), db, HillProvider(), cache)
    da, db_ = _json(a / "tunnels.json"), _json(b / "tunnels.json")
    assert da["version"] == TU.TUNNELS_VERSION and db_["tunnels"] == []
    (item,) = da["tunnels"]
    xs = [p[0] for p in item["points"]]
    assert min(xs) == pytest.approx(350.0, abs=1.0) and max(xs) == pytest.approx(650.0, abs=1.0)   # relatives au coin
    assert all(p[2] < 305.0 for p in item["points"])                     # route à plat sous la colline
    jsonschema.validate(da, _json(WORLD_CONTRACTS / "tunnels.schema.json"))
    near = np.frombuffer((a / "near.f32").read_bytes(), dtype="<f4").reshape(101, 101)
    assert float(near[50, 50]) > 330.0                    # la colline reste au-dessus du tunnel
    meta = _json(a / "meta.json")
    assert meta["counts"]["tunnels"] == 1 and meta["versions"]["worldgen"] >= 10   # tunnels depuis 10 (EA5)
