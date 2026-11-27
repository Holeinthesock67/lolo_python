"""Navigation du monde ouvert, revue de code vague 4 (lot K2) : K2-01, K2-02, K2-03, K2-04.

Tout est synthétique (aucun lieu réel) : graphes et bases écrits par les tests, repère de zone des tests W8.
"""

from __future__ import annotations

import math
from pathlib import Path

from openride_compiler.worldgen.graph import RoadGraph
from openride_compiler.worldgen.navigator import Navigator
from openride_compiler.worldgen.osmdb import OsmDbWriter
from test_world_graph import FRAME, Builder, bbox_xz
from test_worldgen_process import E_REF, N_REF, latlon, lonlat, session

RING_R = 100.0


def _ring(e0: float, n0: float, first_id: int = 1) -> tuple[list[int], list[tuple[float, float]]]:
    """Rond-point à 8 nœuds, dans le sens trigonométrique depuis l'est ; le nœud ouest (indice 4) n'a pas le plus
    petit identifiant : c'est le cas où l'ancien identifiant du nœud de choix disparaissait (K2-01)."""
    ids = [first_id + k for k in range(8)]
    pts = [(e0 + RING_R * math.cos(k * math.pi / 4), n0 + RING_R * math.sin(k * math.pi / 4)) for k in range(8)]
    return ids, pts


# --- K2-01 : identifiant de carrefour qui change quand le rond-point est complété -------------------------

def test_resolve_follows_roundabout_completed_later(tmp_path) -> None:
    b = Builder(tmp_path / "rp.sqlite")
    ring = [b.node(9000 + RING_R * math.cos(k * math.pi / 4), -RING_R * math.sin(k * math.pi / 4)) for k in range(8)]
    entry = ring[4]                                                    # ouest, pas le plus petit identifiant
    b.way(400, ring + [ring[0]], junction="roundabout")
    b.way(300, [b.node(0, 0), b.node(4000, 0), entry])                 # 9 km sans carrefour jusqu'au rond-point
    b.way(501, [ring[0], b.node(11_000, 0)])
    b.way(502, [ring[2], b.node(9000, -2000)])
    b.way(503, [ring[6], b.node(9000, 2000)])
    db = b.open()
    g = RoadGraph.build(db, bbox_xz(-1000, -1000, 3000, 1000), FRAME)
    assert g.resolve(entry) == entry and g.nodes[entry].frontier        # bout de l'arête seul dans son groupe
    g.extend(db, bbox_xz(7000, -3000, 12_000, 3000))
    node = g.resolve(entry)
    assert node == min(ring) and entry not in g.nodes                  # l'ancien identifiant n'existe plus
    nav = Navigator(g, "ride", (0.0, 0.0), 90.0, seed=1)
    c = nav.choose(node, "300:0", ["300:0"], arriving_forward=True)
    assert c.phase != "u_turn" and c.branch_edge_id in {"501:0", "502:0", "503:0"}


def _roundabout_db(path: Path) -> Path:
    """Route est-ouest de 9 km sans carrefour, finie par un rond-point à trois sorties hors des cellules du départ."""
    w = OsmDbWriter(path, "test", "test/rond-point")
    ce, cn = E_REF + 9000 + RING_R, N_REF
    ids, pts = _ring(ce, cn)
    entry = ids[4]
    w.add_road(400, {"highway": "tertiary", "junction": "roundabout"}, ids + [ids[0]], [lonlat(*p) for p in pts + [pts[0]]])
    road = [1000 + k for k in range(11)] + [entry]
    coords = [lonlat(E_REF - 1000 + 1000 * k, N_REF) for k in range(11)] + [lonlat(*pts[4])]
    w.add_road(300, {"highway": "tertiary"}, road, coords)
    for wid, k, (de, dn) in ((501, 0, (2000, 0)), (502, 2, (0, 2000)), (503, 6, (0, -2000))):
        w.add_road(wid, {"highway": "tertiary"}, [ids[k], 2000 + wid],
                   [lonlat(*pts[k]), lonlat(pts[k][0] + de, pts[k][1] + dn)])
    w.finish(osm_date="2026-10-20T00:00:00Z")
    return path


def _open(e: float, n: float, heading: float, nav: str = "ride", loop_km: float | None = None) -> dict:
    lat, lon = latlon(e, n)
    return {"type": "open", "lat": lat, "lon": lon, "heading_deg": heading, "nav": nav, "target": None,
            "loop_km": loop_km, "seed": 7, "network": True}


def test_session_leaves_roundabout_completed_after_the_long_edge(tmp_path) -> None:
    s, rec = session(tmp_path, _roundabout_db(tmp_path / "rp.sqlite"))
    s.handle(_open(E_REF + 250, N_REF, 90.0))
    assert not rec.of("error") and [leg.edge_id for leg in s.legs] == ["300:0"]
    s.progress(6000.0)                                  # la cellule du rond-point est chargée maintenant
    ids = [leg.edge_id for leg in s.legs]
    assert ids[0] == "300:0" and ids.count("300:0") == 1, ids           # ni demi-tour ni retour de 9 km
    assert ids[1] in {"501:0", "502:0", "503:0"}
    assert s.legs[1].profile.length_m < 3000.0
    assert any(j.leg == 0 for j in s._junctions())                     # le rond-point est bien proposé


# --- K2-02 : bretelle à sens unique rangée à l'envers qui finit sur une voie exclue ---------------------------

def _ramp_db(path: Path, upstream: int, downstream: int) -> Path:
    w = OsmDbWriter(path, "test", "test/bretelle")
    w.add_road(10, {"highway": "residential"}, [100, 101, 102],
               [lonlat(E_REF - 1000, N_REF), lonlat(E_REF, N_REF), lonlat(E_REF + 1000, N_REF)])
    w.add_road(upstream, {"highway": "tertiary_link", "oneway": "yes"}, [102, 103],
               [lonlat(E_REF + 1000, N_REF), lonlat(E_REF + 1450, N_REF)])
    w.add_road(downstream, {"highway": "tertiary_link", "oneway": "yes"}, [103, 104],
               [lonlat(E_REF + 1450, N_REF), lonlat(E_REF + 1900, N_REF)])
    w.add_road(900, {"highway": "trunk"}, [105, 104, 106],
               [lonlat(E_REF + 1900, N_REF - 3000), lonlat(E_REF + 1900, N_REF), lonlat(E_REF + 1900, N_REF + 3000)])
    w.finish(osm_date="2026-10-20T00:00:00Z")
    return path


def test_oneway_dead_end_stored_reversed_says_no_more_road(tmp_path) -> None:
    for up, down in ((300, 500), (500, 300)):        # le second rangeait l'arête à l'envers et la répétait sans fin
        d = tmp_path / f"{up}_{down}"
        s, rec = session(d, _ramp_db(d.with_suffix(".sqlite"), up, down))
        s.handle(_open(E_REF + 250, N_REF, 90.0))
        ids = [leg.edge_id for leg in s.legs]
        assert ids.count("300:0") == 1, (up, down, ids)
        assert s.data_state == "missing", (up, down)
        assert any("plus de route connue" in str(m) for m in rec.of("status")), (up, down)


def test_u_turn_goes_against_the_arrival(tmp_path) -> None:
    b = Builder(tmp_path / "u.sqlite")
    a, m, z = b.node(0, 0), b.node(0, -450), b.node(0, -900)
    b.way(10, [b.node(0, 1000), a])
    b.way(500, [a, m], oneway="yes")
    b.way(300, [m, z], oneway="yes")                                   # aval au plus petit identifiant
    g = RoadGraph.build(b.open(), bbox_xz(-3000, -3000, 3000, 3000), FRAME)
    e = g.edges["300:0"]
    assert e.oneway == -1 and g.resolve(z) == e.a                      # rangée à l'envers : on arrive au bout `a`
    nav = Navigator(g, "ride", (0.0, 1000.0), 0.0, seed=1)
    for fwd_hint in (False, None):                                     # sens d'arrivée donné, ou déduit du nœud
        u = nav.choose(e.a, "300:0", ["10:0", "300:0"], arriving_forward=fwd_hint)
        assert u.phase == "u_turn" and u.forward is True and not e.allows(u.forward)


# --- K2-04 : maison de la boucle sur une voie isolée ---------------------------------------------------------

def _loop_db(path: Path, isolated: bool) -> Path:
    """Grille de 500 m sur 8 × 8 km ; en option, une voie isolée (sans accès admis) à 35 m du départ."""
    w = OsmDbWriter(path, "test", "test/boucle")
    es = list(range(E_REF - 4000, E_REF + 4001, 500))
    ns = list(range(N_REF - 4000, N_REF + 4001, 500))
    nid = {(i, j): 1 + i * len(ns) + j for i in range(len(es)) for j in range(len(ns))}
    for j, n in enumerate(ns):
        w.add_road(100_000 + j, {"highway": "tertiary"}, [nid[(i, j)] for i in range(len(es))],
                   [lonlat(e, n) for e in es])
    for i, e in enumerate(es):
        w.add_road(200_000 + i, {"highway": "residential"}, [nid[(i, j)] for j in range(len(ns))],
                   [lonlat(e, n) for n in ns])
    if isolated:
        w.add_road(900, {"highway": "service"}, [90_000, 90_001],
                   [lonlat(E_REF + 240, N_REF + 35), lonlat(E_REF + 320, N_REF + 35)])
    w.finish(osm_date="2026-10-20T00:00:00Z")
    return path


def test_loop_home_is_on_the_start_edge(tmp_path) -> None:
    for isolated in (False, True):
        d = tmp_path / ("isolee" if isolated else "temoin")
        s, rec = session(d, _loop_db(d.with_suffix(".sqlite"), isolated))
        s.handle(_open(E_REF + 240, N_REF, 90.0, nav="loop", loop_km=10.0))
        assert not rec.of("error")
        first = s.graph.edges[s.legs[0].edge_id]
        assert s.nav._home_raw in (first.raw_a, first.raw_b) and s.nav._home_raw < 90_000
        km = 0.0
        while s.finish_m is None and km < 20_000.0:
            km += 1000.0
            s.progress(km)
        assert s.finish_m is not None and s.finish_m < 15_000.0, (isolated, s.finish_m)


def test_loop_without_any_return_aims_at_the_start(tmp_path) -> None:
    """Maison sans aucun retour fini : le choix vise le cap du départ, pas l'ordre des identifiants (K2-04)."""
    b = Builder(tmp_path / "l.sqlite")
    c = b.node(0, 0)
    b.way(1, [b.node(-3000, 0), c])                                    # arrivée de l'ouest
    b.way(2, [c, b.node(3000, -100)])                                  # vers l'est, s'éloigne du départ (plus petit id)
    b.way(9, [c, b.node(-200, -3000)])                                 # vers le nord-ouest, revient vers le départ
    iso = b.node(-6000, 50)
    b.way(50, [iso, b.node(-6000, 400)])                               # voie isolée près du départ
    g = RoadGraph.build(b.open(), bbox_xz(-8000, -8000, 8000, 8000), FRAME)
    nav = Navigator(g, "loop", (-6000.0, 0.0), 90.0, seed=1, loop_m=4000.0, home_node=iso)
    ch = nav.choose(g.resolve(c), "1:0", ["1:0"], arriving_forward=True)
    assert ch.phase == "loop_return" and ch.branch_edge_id == "9:0"
