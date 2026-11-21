"""Sol des tuiles de la balade réglé sur la route engagée (21 novembre 2026, `worldgen/session_ground.py`).

Constat du banc du lac d'Annecy : le carré du cache règle son sol sur chacune de ses arêtes, mais l'engine dessine la
balade, recousue et rééchantillonnée tous les 10 m, avec les virages pris aux carrefours et les boucles de demi-tour
des impasses. Contrôle bloquant : sur un extrait de monde ouvert difficile (relief en dévers de 35 %, virages serrés,
carrefours, route voisine parallèle, pont, impasse), aucun point de sol au-dessus de la chaussée dessinée, aucun pied
de talus sans appui, sur toute la route engagée ; la tuile du carré seule, elle, en laisse.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from openride_compiler import road_ground as RG
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.worldgen import process
from openride_compiler.worldgen import session_ground as SG
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
from openride_compiler.worldgen.process import WorldSession
from openride_compiler.worldgen.squares import zone_frame
from openride_compiler.worldgen.store import WorldCache

ZONE = "31T"
FRAME = zone_frame(ZONE)
E_REF, N_REF = 680_000, 4_890_000


def lonlat(e: float, n: float) -> tuple[float, float]:
    lat, lon = FRAME.to_latlon(np.array([e]), np.array([-n]))
    return float(lon[0]), float(lat[0])


def relief(x, z):
    """Dévers de 35 % vers le sud, bosses de 4 m tous les 200 m environ (au-dessus de la résolution du MNT, 30 m) :
    chaque virage passe en travers de la pente."""
    x, z = np.asarray(x, float), np.asarray(z, float)
    return 400.0 + 0.35 * z + 4.0 * np.sin(x / 37.0) * np.cos(z / 29.0)


class Steep(SyntheticProvider):
    def __init__(self) -> None:
        lon, lat = lonlat(E_REF, N_REF)
        super().__init__(lat, lon, relief)


def hard_db(path) -> None:
    """Route principale sinueuse (virages de 25 m de rayon) de 0 à 5 km, impasse au bout ; branches en biais tous les
    600 m, impasses elles aussi ; voie parallèle à 6 m au nord sur 500 m (piste) ; pont sur 60 m."""
    w = OsmDbWriter(path, "test", "test/difficile")
    pts = []
    for d in range(0, 5001, 10):
        pts.append((E_REF + d, N_REF + 30.0 * math.sin(d / 90.0)))
    main_nodes = [40_000 + k for k in range(len(pts))]
    cuts = [k for k in range(0, len(pts), 60)] + [len(pts) - 1]
    for a, b in zip(cuts[:-1], cuts[1:]):
        tags = {"highway": "tertiary"}
        if a == 120:
            # tronçon de 600 m dont un pont : coupé en trois voies (avant, pont, après)
            w.add_road(9_000 + a, tags, main_nodes[a:a + 21], [lonlat(*p) for p in pts[a:a + 21]])
            w.add_road(9_500 + a, {**tags, "bridge": "yes"}, main_nodes[a + 20:a + 27], [lonlat(*p) for p in pts[a + 20:a + 27]])
            w.add_road(9_700 + a, tags, main_nodes[a + 26:b + 1], [lonlat(*p) for p in pts[a + 26:b + 1]])
            continue
        w.add_road(9_000 + a, tags, main_nodes[a:b + 1], [lonlat(*p) for p in pts[a:b + 1]])
    for j, k in enumerate(cuts[1:-1]):            # branches vers le nord-est
        e, n = pts[k]
        nodes = [main_nodes[k]] + [60_000 + 100 * j + i for i in range(1, 31)]
        # en biais sur la pente (environ 13 %) : une route ne monte pas droit dans un dévers de 35 % (le garde-fou
        # d'altitude borne les pentes à 15 %)
        coords = [lonlat(e, n)] + [lonlat(e + 18.0 * i + 5.0 * math.sin(i / 3.0), n + 8.0 * i) for i in range(1, 31)]
        w.add_road(20_000 + j, {"highway": "residential"}, nodes, coords)
    par = [(E_REF + 2000 + d, N_REF + 30.0 * math.sin((2000 + d) / 90.0) + 6.0) for d in range(0, 501, 10)]
    w.add_road(30_000, {"highway": "cycleway"}, [80_000 + i for i in range(len(par))], [lonlat(*p) for p in par])
    w.finish(osm_date="2026-10-20T00:00:00Z")


def test_ground_follows_the_engaged_route_in_a_hard_open_world(tmp_path) -> None:
    hard_db(tmp_path / "difficile.sqlite")
    cache = WorldCache(tmp_path / "cache", 10**10, log=lambda _m: None)
    logs: list[str] = []
    s = WorldSession(cache, Steep(), lambda _m: None, {}, tmp_path / "seance.world", clock=process.FakeClock(),
                     log=logs.append, db=OsmDb(tmp_path / "difficile.sqlite"))
    lat, lon = FRAME.to_latlon(np.array([E_REF + 50.0]), np.array([-N_REF]))
    s.handle({"type": "open", "lat": float(lat[0]), "lon": float(lon[0]), "heading_deg": 90.0, "nav": "ride",
              "target": None, "loop_km": None, "seed": 3, "network": False})
    for k in range(1, 25):
        s.handle({"type": "progress", "s_m": 250.0 * k, "v_mps": 8.0})
        while s.has_work():
            s.work()
    assert s.length_m > 8000.0                       # impasse au bout : demi-tour compris
    cut, (upper, lower) = s._ground_points()
    assert len(upper[0]) > 10_000
    # Toutes les tuiles réglées sur la route engagée : rien. Celles que l'engine avait quand la route a changé près
    # d'elles (la balade revient vers le cycliste après le demi-tour) attendent qu'il s'éloigne ; leur sol de carré
    # (dégagé un peu plus large et plus bas que la route de l'arête) reste sous la chaussée.
    assert s.ground_stale, "le scénario doit faire revenir la route près du cycliste"
    chk = s.ground.check(upper, lower, set(s.ground.sources) - s.ground_stale)
    assert chk["over"] == 0 and chk["short"] == 0, (chk, [m for m in logs if "sol / route" in m])
    stale = s.ground.check(upper, lower, s.ground_stale)
    assert stale["over_max_m"] < 0.02, stale
    # La tuile du carré seule (réglée sur ses arêtes) laisse du sol sur la route dessinée ou des talus sans appui :
    # le test distingue bien la règle de la balade.
    raw = {k: SG._read(p) for k, p in s.ground.sources.items()}
    gather, _, step = RG.tiles_access(raw, SG.TILE_M)
    before = RG.residual(gather, step, upper, lower)
    assert before["over"] + before["short"] > 0
    assert s.stats["ground_fits"] > 0 and s.stats["ground_over"] == 0


def test_route_spans_follow_the_leg_direction_and_offset() -> None:
    from types import SimpleNamespace as NS
    edges = {"a": NS(length_m=100.0, spans=[(20.0, 40.0, "bridge")]),
             "b": NS(length_m=100.0, spans=[(10.0, 30.0, "tunnel")])}
    legs = [NS(edge_id="a", forward=True, s0=0.0, profile=NS(length_m=100.0)),
            NS(edge_id="b", forward=False, s0=100.0, profile=NS(length_m=150.0))]   # boucle de 50 m en tête
    assert SG.route_spans(legs, edges) == [(20.0, 40.0, "bridge"), (100.0 + 50 + 70, 100.0 + 50 + 90, "tunnel")]


def test_fit_keeps_borders_shared_with_tiles_not_refitted(tmp_path) -> None:
    """Un sommet partagé avec une voisine déjà en place garde sa valeur : pas de fente entre deux tuiles."""
    n = 101
    src = tmp_path / "src"
    src.mkdir()
    g = SG.SessionGround(tmp_path / "s")
    g.dir.mkdir(parents=True)
    for k in ((0, 0), (1, 0)):
        y = np.full((n, n), 10.0, "<f4")
        (src / f"{k[0]}_{k[1]}.f32").write_bytes(y.tobytes())
        g.add(k, src / f"{k[0]}_{k[1]}.f32")
    nb = np.full((n, n), 10.0, "<f4")
    nb[:, 0] = 9.5                                   # voisine déjà affichée : bord ouest au-dessus de la route
    g.path((1, 0)).write_bytes(nb.tobytes())
    # route nord-sud le long du bord commun (x = 1000), à 9 m
    z = np.arange(100.0, 900.0, 10.0)
    route = {"x": np.full(len(z), 1000.0), "z": z, "alt_m": np.full(len(z), 9.0), "heading_deg": np.full(len(z), 180.0),
             "s": z - z[0]}
    up, lo = SG.route_corridor(route, [])
    g.fit({(0, 0)}, up, lo)
    y0 = SG._read(g.path((0, 0)))
    assert np.array_equal(y0[:, -1], nb[:, 0].astype(float))      # bord commun : valeur de la voisine
    assert y0[:, -2].min() < 10.0                                 # le reste de la tuile s'abaisse sous la route
    assert SG._read(g.path((1, 0)))[:, 0].tolist() == nb[:, 0].astype(float).tolist()
