"""Carrés de 1 km du monde ouvert (lot W7) : bords partagés, indépendance de la séance, couches, cache."""

from __future__ import annotations

import json
import math
import statistics
import time

import numpy as np
import pytest

from openride_compiler import constants as C
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.worldgen import squares
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
from openride_compiler.worldgen.squares import FarKey, SquareKey, SquareQueue, generate_far, generate_square
from openride_compiler.worldgen.store import WorldCache

ZONE = "31T"
FRAME = squares.zone_frame(ZONE)
E_REF, N_REF = 680_000, 4_890_000           # coin d'une case de 5 km de la zone 31 (Provence)
IX, IN = E_REF // 1000 + 2, N_REF // 1000 + 2


def lonlat(e: float, n: float) -> tuple[float, float]:
    lat, lon = FRAME.to_latlon(np.array([e]), np.array([-n]))
    return float(lon[0]), float(lat[0])


def provider() -> SyntheticProvider:
    lon, lat = lonlat(E_REF, N_REF)
    return SyntheticProvider(lat, lon)


def ring(e: float, n: float, w: float, h: float) -> list[tuple[float, float]]:
    return [lonlat(e, n), lonlat(e + w, n), lonlat(e + w, n + h), lonlat(e, n + h), lonlat(e, n)]


@pytest.fixture()
def db(tmp_path) -> OsmDb:
    """Une route est-ouest qui traverse les carrés (IX, IN) et (IX + 1, IN) sur la ligne N = 1000 IN + 500."""
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/carres")
    n_road = IN * 1000 + 500
    es = list(range(IX * 1000 - 600, (IX + 2) * 1000 + 601, 100))
    nodes = list(range(1, len(es) + 1))
    w.add_road(1, {"highway": "secondary"}, nodes, [lonlat(e, n_road) for e in es])
    # croisement en E = 1000 IX + 400, puis piste cyclable étroite
    w.add_road(2, {"highway": "tertiary"}, [100, nodes[10], 101],
               [lonlat(IX * 1000 + 400, n_road - 300), lonlat(es[10], n_road), lonlat(IX * 1000 + 400, n_road + 300)])
    w.add_road(3, {"highway": "cycleway"}, [101, 102], [lonlat(IX * 1000 + 400, n_road + 300),
                                                       lonlat(IX * 1000 + 700, n_road + 300)])
    # bâtiment à cheval sur la limite des deux carrés, centre dans le second
    w.add_area("w10", "building", {"building": "house"}, ring((IX + 1) * 1000 - 8, n_road + 40, 20, 12))
    w.add_area("w11", "wood", {"natural": "wood"}, ring(IX * 1000 + 100, IN * 1000 + 100, 200, 150))
    w.add_area("w12", "water", {"natural": "water", "water": "pond"}, ring(IX * 1000 + 600, IN * 1000 + 100, 50, 40))
    w.add_line("w13", "stream", {"waterway": "stream"}, [lonlat(IX * 1000 + 900, IN * 1000 + 50),
                                                       lonlat((IX + 1) * 1000 + 300, IN * 1000 + 80)])
    lon, lat = lonlat(IX * 1000 + 450, n_road + 60)
    w.add_point("n20", "village", "Hameau d'essai", lon, lat)
    w.finish(osm_date="2026-10-20T00:00:00Z")
    return OsmDb(tmp_path / "osm.sqlite")


def cache(path) -> WorldCache:
    return WorldCache(path, 10**9, log=lambda _m: None)


def near(folder) -> np.ndarray:
    return np.frombuffer((folder / "near.f32").read_bytes(), dtype="<f4").reshape(101, 101)


def load(folder, name: str) -> dict:
    return json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))


def test_keys_and_session_mapping() -> None:
    k = SquareKey.at(ZONE, 680_999.9, 4_891_000.0)
    assert (k.ix, k.i_n) == (680, 4891) and k.corner == (680_000, -4_892_000)
    assert k.cache_key == "square:31T/680_4891" and FarKey.at(ZONE, 684_000, 4_899_999).cache_key == "far:31T/136_979"
    # Deux séances d'origines différentes voient le même carré à des indices de tuile différents.
    for e0, n0 in ((675_000, 4_895_000), (690_000, 4_880_000)):
        ix, iz = (IX * 1000 - e0) // 1000, (n0 - IN * 1000) // 1000 - 1
        key = SquareKey.of_session_tile(ZONE, e0, n0, ix, iz)
        assert key == SquareKey(ZONE, IX, IN)
        # tuile de séance (ix, iz) : x = 1000 ix + 10 i, z = 1000 iz + 10 j, soit E = E0 + x, N = N0 − z
        gx, gz = squares.grid_xz(key, 10)
        sx, sz = np.meshgrid(1000 * ix + np.arange(101) * 10.0, 1000 * iz + np.arange(101) * 10.0)
        assert np.array_equal(gx, e0 + sx) and np.array_equal(-gz, n0 - sz)


def test_shared_border_is_bit_identical_and_road_is_flat(db, tmp_path) -> None:
    c = cache(tmp_path / "cache")
    prov = provider()
    a = generate_square(SquareKey(ZONE, IX, IN), db, prov, c)
    b = generate_square(SquareKey(ZONE, IX + 1, IN), db, prov, c)
    ya, yb = near(a), near(b)
    assert ya[:, 100].tobytes() == yb[:, 0].tobytes()
    # La route suit la ligne j = 50 (N = 1000 IN + 500) : le terrain y vaut le profil − 5 cm.
    graph, profiles = squares.square_edges(SquareKey(ZONE, IX, IN), db, prov)
    main = sorted((profiles[k] for k, e in graph.edges.items() if e.road_class == "s"), key=lambda p: p.x[0])
    assert [p.edge_id for p in main] == ["1:0", "1:10"] and main[0].x[-1] == main[1].x[0]
    xs, alt = np.concatenate([p.x for p in main]), np.concatenate([p.alt_m for p in main])
    cols = np.arange(0, 101)
    expect = np.interp(IX * 1000 + 10.0 * cols, xs, alt) - C.ROAD_SINK_M
    assert np.abs(ya[50, :].astype(float) - expect).max() < 2e-3
    # Loin des routes (coin sud-ouest), relief seul.
    gx, gz = squares.grid_xz(SquareKey(ZONE, IX, IN), 10)
    lat, lon = FRAME.to_latlon(gx[100, 0:1], gz[100, 0:1])
    assert ya[100, 0] == np.float32(prov.elevations(lat, lon)[0])


def test_narrow_track_and_terrain_independent_of_session(db, tmp_path) -> None:
    key = SquareKey(ZONE, IX, IN)
    p1, p2 = generate_square(key, db, provider(), cache(tmp_path / "c1")), \
        generate_square(key, db, provider(), cache(tmp_path / "c2"))
    for name in ("near.f32", "edges.json", "meta.json", "buildings.json", "vegetation.json", "water.json", "poi.json"):
        assert (p1 / name).read_bytes() == (p2 / name).read_bytes(), name
    meta = load(p1, "meta")
    assert meta["versions"]["worldgen"] == squares.WORLDGEN_VERSION and meta["versions"]["osm_date"].startswith("2026")
    edges = load(p1, "edges")["edges"]
    assert {e["road_class"] for e in edges} == {"s", "t", "c"} and meta["counts"]["edges"] >= len(edges)


def test_roads_axis_widths_and_spans() -> None:
    """Demi-largeur par classe ; pas de segment entre deux polylignes ; ponts exclus du fondu."""
    x = np.arange(0.0, 101.0, 10.0)
    axis = squares.RoadsAxis([(x, np.zeros_like(x), np.full_like(x, 100.0), 3.0),
                              (x, np.full_like(x, 50.0), np.full_like(x, 200.0), squares.half_width("c"))])
    d, y = axis.nearest(np.array([50.0, 50.0, 50.0]), np.array([5.0, 45.0, 25.0]), 25.0)
    assert d.tolist() == pytest.approx([2.0, 3.0, 22.0]) and y.tolist() == pytest.approx([100.0, 200.0, 100.0])
    d, _ = axis.nearest(np.array([105.0]), np.array([25.0]), 25.0)     # pas de segment (100, 0)–(0, 50)
    assert d[0] == pytest.approx(math.hypot(5, 25) - 3)
    prof = squares.EdgeProfile("1:0", x, x, np.zeros_like(x), np.full_like(x, 5.0), x * 0, x * 0, x, x, 0)
    pieces = squares.axis_pieces(prof, 3.0, [[30.0, 60.0, "bridge"]])
    assert [p[0].tolist() for p in pieces] == [[0.0, 10.0, 20.0, 30.0], [60.0, 70.0, 80.0, 90.0, 100.0]]


def test_objects_belong_to_one_square(db, tmp_path) -> None:
    c = cache(tmp_path / "cache")
    a = generate_square(SquareKey(ZONE, IX, IN), db, provider(), c)
    b = generate_square(SquareKey(ZONE, IX + 1, IN), db, provider(), c)
    assert load(a, "buildings")["buildings"] == []
    (house,) = load(b, "buildings")["buildings"]
    x0, z0 = SquareKey(ZONE, IX + 1, IN).corner
    xs = [p[0] + x0 for p in house["outer"]]
    assert min(xs) == pytest.approx((IX + 1) * 1000 - 8, abs=0.006) and min(p[0] for p in house["outer"]) < 0
    zs = [-(p[1] + z0) for p in house["outer"]]               # retour au nord global
    assert min(zs) == pytest.approx(IN * 1000 + 540, abs=0.006)
    terrain_b = near(b)
    assert house["base_y"] <= float(terrain_b[44:47, 0:2].max()) + 1e-6
    (wood,) = load(a, "vegetation")["areas"]
    assert wood["kind"] == "wood" and wood["density"] == C.DENSITY_WOOD
    (pond,) = load(a, "water")["areas"]
    assert pond["kind"] == "pond"
    stream_a, stream_b = load(a, "water")["lines"], load(b, "water")["lines"]
    assert len(stream_a) == 1 and len(stream_b) == 1
    assert stream_a[0]["points"][-1][0] > 1000 and stream_b[0]["points"][0][0] < 0      # pas de trou au bord
    (village,) = load(a, "poi")["points"]
    assert village["kind"] == "village" and village["x"] == pytest.approx(450, abs=0.01) \
        and village["z"] == pytest.approx(1000 - 560, abs=0.01)


def test_cache_reuse_and_version_change(db, tmp_path, monkeypatch) -> None:
    c = cache(tmp_path / "cache")
    key = SquareKey(ZONE, IX, IN)
    prov = provider()
    path = generate_square(key, db, prov, c)
    first = (path / "near.f32").read_bytes()
    prov.calls = 0
    assert generate_square(key, db, prov, c) == path and prov.calls == 0
    monkeypatch.setattr(squares, "WORLDGEN_VERSION", squares.WORLDGEN_VERSION + 1)
    generate_square(key, db, prov, c)
    assert prov.calls > 0 and (path / "near.f32").read_bytes() == first
    assert c.get(key.cache_key).versions["worldgen"] == squares.WORLDGEN_VERSION
    assert not list(path.parent.glob(".*"))                    # pas de dossier temporaire laissé


def test_far_tile(tmp_path) -> None:
    c = cache(tmp_path / "cache")
    prov = provider()
    key = FarKey(ZONE, E_REF // 5000, N_REF // 5000)
    path = generate_far(key, prov, c)
    y = np.frombuffer(path.read_bytes(), dtype="<f4").reshape(101, 101)
    gx, gz = squares.grid_xz(key, 50)
    assert gx[0, 100] - gx[0, 0] == 5000
    lat, lon = FRAME.to_latlon(gx.ravel(), gz.ravel())
    assert np.array_equal(y.ravel(), prov.elevations(lat, lon).astype("<f4"))
    prov.calls = 0
    generate_far(key, prov, c)
    assert prov.calls == 0 and c.get(key.cache_key).kind == "far"


def test_queue_priorities() -> None:
    q = SquareQueue()
    k = [SquareKey(ZONE, i, 0) for i in range(5)]
    q.request(k[0], crow_m=500)
    q.request(k[1], crow_m=2000, route_m=1500)
    q.request(k[2], crow_m=100, route_m=3000)
    q.request(k[3], crow_m=9000)
    assert not q.request(k[1], crow_m=2500, route_m=2000)       # moins urgent : ignoré
    assert q.request(k[0], crow_m=400, route_m=200)             # désormais sur la route engagée
    assert len(q) == 4
    assert q.cancel_beyond(5000) == [k[3]]
    assert [q.pop(), q.pop(), q.pop(), q.pop()] == [k[0], k[1], k[2], None]
    assert SquareQueue.workers(8) == 4 and SquareQueue.workers(2) == 1 and SquareQueue.workers(1) == 1


def test_square_time(db, tmp_path) -> None:
    c = cache(tmp_path / "cache")
    prov = provider()
    times = []
    for i in range(3):
        t0 = time.perf_counter()
        generate_square(SquareKey(ZONE, IX + i - 1, IN), db, prov, c)
        times.append(time.perf_counter() - t0)
    med = statistics.median(times)
    print(f"carré de 1 km : médiane {med * 1000:.0f} ms ({', '.join(f'{t * 1000:.0f}' for t in times)} ms)")
    assert med < 3.0 and math.isfinite(med)      # seuil large ; 300 ms visés sur le PC (W0)


def test_zero_length_road_has_no_profile(db, tmp_path) -> None:
    """Un tronçon aux points confondus ne fait tomber ni les profils ni la génération du carré."""
    w = OsmDbWriter(tmp_path / "osm0.sqlite", "test", "test/carres0")
    n_road = IN * 1000 + 500
    p = lonlat(IX * 1000 + 300, n_road)
    w.add_road(1, {"highway": "secondary"}, [1, 2], [lonlat(IX * 1000 + 100, n_road), p])
    w.add_road(2, {"highway": "secondary"}, [2, 3], [p, p])
    w.add_road(3, {"highway": "secondary"}, [3, 4], [p, lonlat(IX * 1000 + 600, n_road)])
    w.add_road(4, {"highway": "tertiary"}, [2, 5], [p, lonlat(IX * 1000 + 300, n_road - 200)])   # carrefours aux deux bouts
    w.add_road(5, {"highway": "tertiary"}, [3, 6], [p, lonlat(IX * 1000 + 300, n_road + 200)])
    w.finish(osm_date="2026-10-20T00:00:00Z")
    db0 = OsmDb(tmp_path / "osm0.sqlite")
    graph, profiles = squares.square_edges(SquareKey(ZONE, IX, IN), db0, provider())
    assert any(e.degenerate for e in graph.edges.values())
    assert profiles and all(not graph.edges[k].degenerate for k in profiles)
    generate_square(SquareKey(ZONE, IX, IN), db0, provider(), cache(tmp_path / "cache0"))
