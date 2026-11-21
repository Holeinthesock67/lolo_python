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
    # La route suit la ligne j = 50 (N = 1000 IN + 500) : le terrain y vaut le profil − 5 cm, sauf au croisement
    # (E = 1000 IX + 400, colonnes 40 et 41) où la route tertiaire monte à 30 % : le garde-fou de la chaussée
    # (13/11) y abaisse le sommet sous la route, jamais au-dessus.
    graph, profiles = squares.square_edges(SquareKey(ZONE, IX, IN), db, prov)
    main = sorted((profiles[k] for k, e in graph.edges.items() if e.road_class == "s"), key=lambda p: p.x[0])
    assert [p.edge_id for p in main] == ["1:0", "1:10"] and main[0].x[-1] == main[1].x[0]
    xs, alt = np.concatenate([p.x for p in main]), np.concatenate([p.alt_m for p in main])
    cols = np.arange(0, 101)
    expect = np.interp(IX * 1000 + 10.0 * cols, xs, alt) - C.ROAD_SINK_M
    gap = ya[50, :].astype(float) - expect
    away = np.abs(cols - 40.5) > 2.0
    # jamais au-dessus du profil − 5 cm ; au plus 10 cm dessous (20/11 : sur un profil courbe, le garde-fou abaisse
    # aussi les sommets de la chaussée de quelques centimètres quand les coins hors chaussée ne suffisent pas). Au
    # croisement, les sommets à moins de deux cases suivent la tertiaire à 30 % dessinée par l'engine (21/11 : route de
    # l'engine et bas-côtés compris, règle road_ground.py).
    # 21/11 (garde-fou d'altitude, pente du monde ouvert bornée à 15 %) : sur ce relief de synthèse à 28 %, la route
    # passe en tranchée de plusieurs mètres ; la règle sol / route y abaisse aussi les sommets de l'axe (sol caché sous
    # la chaussée), jusqu'à 1,5 m sous le profil. Jamais au-dessus.
    assert gap.max() < 2e-3 and gap[away].min() > -1.5, (gap.max(), gap[away].min())
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


def _square_excess(key: SquareKey, folder, db, prov, tunnels: bool = True) -> float:
    """Plus grand dépassement (m) du maillage du carré au-dessus de la chaussée moins ROAD_SINK_M, sur toutes les
    routes du carré, ponts compris, tunnels compris si `tunnels` (20/11), aux points de chaussée tous les mètres, sur au
    moins la largeur du ruban de l'engine (ROAD_HALF_WIDTH_M), même pour une piste fondue sur 2 m."""
    from openride_compiler import terrain
    graph, profiles = squares.square_edges(key, db, prov)
    x0, z0 = key.corner
    tiles = {(x0 // 1000, z0 // 1000): near(folder).astype(float)}
    worst = -math.inf
    for k in sorted(profiles):
        e = graph.edges[k]
        skip = [] if tunnels else [sp for sp in e.spans if sp[2] == "tunnel"]
        for px, pz, pa, hw in squares.axis_pieces(profiles[k], max(squares.half_width(e.road_class), C.ROAD_HALF_WIDTH_M), skip):
            ex, _x, _z = terrain.terrain_excess(tiles, px, pz, pa, half_width=hw)
            if len(ex):
                worst = max(worst, float(ex.max()))
    return worst


def test_square_terrain_never_covers_road(tmp_path) -> None:
    """13/11 (« même qualité que les circuits précalculés ») : comme le compilateur (terrain.clear_road, 31/10),
    aucun triangle du maillage de 10 m ne dépasse la chaussée, même en diagonale sur un flanc raide ; les bords
    communs des carrés restent identiques au bit près."""
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/flanc")
    e0, n0 = IX * 1000 - 300, IN * 1000 - 300
    pts = [lonlat(e0 + 23.0 * i, n0 + 17.0 * i) for i in range(0, 120)]    # diagonale qui traverse 4 carrés
    w.add_road(1, {"highway": "secondary"}, list(range(1, len(pts) + 1)), pts)
    w.finish(osm_date="2026-10-20T00:00:00Z")
    db = OsmDb(tmp_path / "osm.sqlite")
    lon, lat = lonlat(E_REF, N_REF)
    # flanc à 35 % en travers de la route, avec des bosses de 20 m
    prov = SyntheticProvider(lat, lon, lambda x, z: 400.0 + 0.35 * (x - z) + 6.0 * np.sin(x / 20.0) * np.cos(z / 17.0))
    c = cache(tmp_path / "cache")
    out = {}
    for di in (0, 1):
        for dn in (0, 1):
            key = SquareKey(ZONE, IX + di, IN + dn)
            out[(di, dn)] = generate_square(key, db, prov, c)
            assert _square_excess(key, out[(di, dn)], db, prov) <= 1e-3, key
    assert near(out[(0, 0)])[:, 100].tobytes() == near(out[(1, 0)])[:, 0].tobytes()
    assert near(out[(0, 1)])[100, :].tobytes() == near(out[(0, 0)])[0, :].tobytes()


def test_square_terrain_tunnel_keeps_its_hill(tmp_path) -> None:
    """20/11 : une route en tunnel sous une colline de 25 m. Le garde-fou dégage toute la chaussée à ciel ouvert,
    jusqu'aux entrées du tunnel, mais ne taille pas de gorge au-dessus du tunnel (banc #936, Sevrier : parois
    grises de 40 m) ; les tunnels se dessineront dans un lot à venir. Bords communs identiques au bit près."""
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/tunnel")
    n_road = IN * 1000 + 500
    es = list(range(IX * 1000 + 200, (IX + 1) * 1000 + 801, 50))
    # tunnel du milieu : de E = 1000 (IX + 1) − 200 à 1000 (IX + 1) + 200, à cheval sur les deux carrés
    t0, t1 = es.index((IX + 1) * 1000 - 200), es.index((IX + 1) * 1000 + 200)
    nodes = list(range(1, len(es) + 1))
    w.add_road(1, {"highway": "secondary"}, nodes[:t0 + 1], [lonlat(e, n_road) for e in es[:t0 + 1]])
    w.add_road(2, {"highway": "secondary", "tunnel": "yes", "layer": "-1"}, nodes[t0:t1 + 1],
               [lonlat(e, n_road) for e in es[t0:t1 + 1]])
    w.add_road(3, {"highway": "secondary"}, nodes[t1:], [lonlat(e, n_road) for e in es[t1:]])
    w.finish(osm_date="2026-10-20T00:00:00Z")
    db = OsmDb(tmp_path / "osm.sqlite")
    lon, lat = lonlat(E_REF, N_REF)
    hill_x, hill_z = (IX + 1) * 1000 - E_REF, -(n_road - N_REF)     # repère local du relief, origine (E_REF, N_REF)

    def relief(x, z):
        d2 = (np.asarray(x) - hill_x) ** 2 + (np.asarray(z) - hill_z) ** 2
        return 300.0 + 25.0 * np.exp(-d2 / (2 * 150.0 ** 2))
    prov = SyntheticProvider(lat, lon, relief)
    graph, profiles = squares.square_edges(SquareKey(ZONE, IX, IN), db, prov)
    assert any(kind == "tunnel" for k in profiles for _s0, _s1, kind in graph.edges[k].spans)
    c = cache(tmp_path / "cache")
    a = generate_square(SquareKey(ZONE, IX, IN), db, prov, c)
    b = generate_square(SquareKey(ZONE, IX + 1, IN), db, prov, c)
    for key, folder in ((SquareKey(ZONE, IX, IN), a), (SquareKey(ZONE, IX + 1, IN), b)):
        assert _square_excess(key, folder, db, prov, tunnels=False) <= 1e-3, key
        assert _square_excess(key, folder, db, prov) > 5.0, key      # la colline reste au-dessus du tunnel
    assert near(a)[:, 100].tobytes() == near(b)[:, 0].tobytes()
    # sommet de la colline à 100 m de la route : intact (≈ 300 + 25·exp(−100²/(2·150²)) = 320 m)
    top = float(near(b)[40, 0])
    assert top > 319.0, top


def test_narrow_road_cleared_on_engine_width(tmp_path) -> None:
    """20/11 (« le talus passe sur la route », lac d'Annecy) : une piste cyclable (fondue sur 2 m) sur un flanc à
    45 % est dessinée par l'engine à la largeur du thème (6 m) quand on la roule ; le talus ne doit pas passer sur le
    bord de ce ruban."""
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/piste")
    n_road = IN * 1000 + 500
    pts = [lonlat(IX * 1000 - 100 + 23.0 * i, n_road - 150 + 9.0 * i + 25.0 * math.sin(i / 3.0)) for i in range(0, 50)]
    w.add_road(1, {"highway": "cycleway"}, list(range(1, len(pts) + 1)), pts)
    w.finish(osm_date="2026-10-20T00:00:00Z")
    db = OsmDb(tmp_path / "osm.sqlite")
    lon, lat = lonlat(E_REF, N_REF)
    prov = SyntheticProvider(lat, lon, lambda x, z: 400.0 + 0.45 * (z - 0.4 * x) + 4.0 * np.sin(x / 13.0) * np.cos(z / 11.0))
    key = SquareKey(ZONE, IX, IN)
    folder = generate_square(key, db, prov, cache(tmp_path / "cache"))
    assert _square_excess(key, folder, db, prov) <= 1e-3


def test_roadside_building_keeps_its_footing(tmp_path) -> None:
    """20/11 (banc #936, lac d'Annecy) : le garde-fou de la chaussée entaille le talus au bord de la route. Une maison
    dont l'empreinte touche l'entaille gardait comme pied le fond de l'entaille (minimum du relief final sous
    l'empreinte) et disparaissait dans le talus. Le pied se prend sur le relief d'avant le garde-fou."""
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/maison")
    n_road = IN * 1000 + 503
    es = list(range(IX * 1000 - 100, (IX + 1) * 1000 + 101, 50))
    # route sur un pont (relief non fondu dessous) : le garde-fou entaille la butte qui dépasse le tablier
    t0, t1 = es.index(IX * 1000 + 400), es.index(IX * 1000 + 650)
    nodes = list(range(1, len(es) + 1))
    w.add_road(1, {"highway": "secondary"}, nodes[:t0 + 1], [lonlat(e, n_road) for e in es[:t0 + 1]])
    w.add_road(2, {"highway": "secondary", "bridge": "yes"}, nodes[t0:t1 + 1], [lonlat(e, n_road) for e in es[t0:t1 + 1]])
    w.add_road(3, {"highway": "secondary"}, nodes[t1:], [lonlat(e, n_road) for e in es[t1:]])
    # maison de 10 m × 8 m, de 4 à 12 m au nord de l'axe
    w.add_area("w50", "building", {"building": "house"}, ring(IX * 1000 + 503, n_road + 4, 10, 8))
    w.finish(osm_date="2026-10-20T00:00:00Z")
    db = OsmDb(tmp_path / "osm.sqlite")
    lon, lat = lonlat(E_REF, N_REF)
    z_house = -(n_road + 3 - N_REF)            # repère local du relief, origine (E_REF, N_REF)
    # butte de 10 m sous le pont et la maison
    prov = SyntheticProvider(lat, lon, lambda x, z: 400.0 + 10.0 * np.exp(-((np.asarray(z) - z_house) / 12.0) ** 2))
    key = SquareKey(ZONE, IX, IN)
    graph, profiles = squares.square_edges(key, db, prov)
    ground, final = squares.square_relief(key, graph, profiles, prov, FRAME)
    assert (ground - final).max() > 0.3, "le garde-fou doit entailler le talus pour que l'essai ait un sens"
    folder = generate_square(key, db, prov, cache(tmp_path / "cache"))
    assert near(folder).tobytes() == final.tobytes()
    b = load(folder, "buildings")["buildings"][0]
    x0, z0 = key.corner
    outer = [[p[0] + x0, p[1] + z0] for p in b["outer"]]
    tiles = {(key.ix, -(key.i_n + 1)): ground}
    from openride_compiler import osm_layers as L
    assert b["base_y"] == L.compute_footprint_base_y(outer, FRAME, tiles, prov)
    sunk = L.compute_footprint_base_y(outer, FRAME, {(key.ix, -(key.i_n + 1)): final}, prov)
    assert b["base_y"] > sunk


def test_clear_never_digs_below_the_road() -> None:
    """20/11 (banc #936, lac d'Annecy) : un point de chaussée au ras d'un sommet trop haut (route voisine plus haute),
    les deux autres coins ayant un poids presque nul. L'ancienne règle divisait le besoin par ce poids et enfonçait ces
    coins de milliers de mètres (falaises grises au bord de la route) ; aucun sommet ne doit descendre sous la limite
    de la chaussée (règle bornée de road_ground.fit)."""
    from openride_compiler import road_ground as RG
    y = np.zeros((3, 3))
    y[0, 0] = 0.5                                   # sommet sous la chaussée, 50 cm au-dessus de ce point de route
    lim = 0.0 - C.ROAD_SINK_M
    upper = (np.array([0.0005]), np.array([0.0005]), np.array([lim]))
    e = np.empty(0)
    RG.fit_grid(y, 0.0, 0.0, 10.0, upper, (e, e, e))
    assert float(y.min()) >= lim - 1e-3 - 1e-6, y
    assert float(y[0, 0]) <= lim + 1e-6             # le sommet descend à la limite : la route est dégagée
