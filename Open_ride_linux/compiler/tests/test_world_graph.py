"""Graphe routier local du monde ouvert (lot W4), sur des bases écrites par les tests."""

from __future__ import annotations

import math
import time
from itertools import count

import pytest
from pyproj.enums import TransformDirection

from openride_compiler.frame import LocalFrame
from openride_compiler.worldgen.graph import RoadGraph, heading_of, relative_angle
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter

LAT0, LON0 = 44.15, 5.25
FRAME = LocalFrame.at(LAT0, LON0)


def lonlat(x: float, z: float) -> tuple[float, float]:
    lon, lat = FRAME.transformer.transform(FRAME.e0 + x, FRAME.n0 - z, direction=TransformDirection.INVERSE)
    return float(lon), float(lat)


def bbox_xz(x0: float, z0: float, x1: float, z1: float) -> tuple[float, float, float, float]:
    a, b = lonlat(x0, z1), lonlat(x1, z0)            # coin sud-ouest, coin nord-est
    return a[0], a[1], b[0], b[1]


class Builder:
    """Écrit une base de test : voies données par leurs nœuds (identifiant → (x, z))."""

    def __init__(self, path) -> None:
        self.path = path
        self.w = OsmDbWriter(path, "test", "test/graphe")
        self.pos: dict[int, tuple[float, float]] = {}
        self.ids = count(1)

    def node(self, x: float, z: float) -> int:
        nid = next(self.ids) + 1000
        self.pos[nid] = (x, z)
        return nid

    def way(self, way_id: int, nodes: list[int], **tags) -> None:
        tags.setdefault("highway", "residential")
        self.w.add_road(way_id, tags, nodes, [lonlat(*self.pos[n]) for n in nodes])

    def line(self, way_id: int, pts: list[tuple[float, float]], **tags) -> list[int]:
        nodes = [self.node(*p) for p in pts]
        self.way(way_id, nodes, **tags)
        return nodes

    def open(self) -> OsmDb:
        self.w.finish()
        return OsmDb(self.path)


BIG = bbox_xz(-5000, -5000, 5000, 5000)


def test_heading_and_angle() -> None:
    assert heading_of([(0, 0), (0, -100)]) == pytest.approx(0)       # vers le nord (z négatif)
    assert heading_of([(0, 0), (100, 0)]) == pytest.approx(90)
    assert relative_angle(90, 0) == 90 and relative_angle(270, 0) == -90 and relative_angle(180, 0) == 180


def test_cross(tmp_path) -> None:
    b = Builder(tmp_path / "x.sqlite")
    c = b.node(0, 0)
    b.way(1, [b.node(0, 300), c, b.node(0, -300)])                   # sud → nord
    b.way(2, [b.node(-300, 0), c, b.node(300, 0)])                   # ouest → est
    g = RoadGraph.build(b.open(), BIG, FRAME)
    assert len(g.nodes) == 5 and len(g.edges) == 4
    br = g.out_edges(g.cluster[c], arriving_heading_deg=0.0)
    assert [round(x.angle_deg) for x in br] == [-90, 0, 90]
    assert all(abs(x.edge.length_m - 300) < 1 for x in br)
    assert {x.edge.id for x in br} == {"2:0", "1:1", "2:1"}


def test_oneway_not_offered_against_traffic(tmp_path) -> None:
    b = Builder(tmp_path / "o.sqlite")
    c = b.node(0, 0)
    b.way(1, [b.node(0, 300), c, b.node(0, -300)])
    b.way(2, [b.node(-300, 0), c], oneway="yes")                     # entre seulement vers le carrefour
    b.way(3, [c, b.node(300, 0)], oneway="-1")                       # sens unique vers le carrefour aussi
    b.way(4, [c, b.node(200, 200)], highway="cycleway", surface="asphalt")
    g = RoadGraph.build(b.open(), BIG, FRAME)
    names = {x.edge.id for x in g.out_edges(g.cluster[c], 0.0)}
    assert "2:0" not in names and "3:0" not in names and "1:1" in names and "4:0" in names


def test_bridge_span_inside_edge(tmp_path) -> None:
    b = Builder(tmp_path / "p.sqlite")
    n = [b.node(0, -s) for s in (0, 450, 550, 1000)]
    b.way(1, n[0:2])
    b.way(2, n[1:3], bridge="yes", layer="1")
    b.way(3, n[2:4])
    g = RoadGraph.build(b.open(), BIG, FRAME)
    (e,) = g.edges.values()
    assert e.length_m == pytest.approx(1000, abs=1)
    ((s0, s1, kind),) = e.spans
    assert kind == "bridge" and s0 == pytest.approx(450, abs=1) and s1 == pytest.approx(550, abs=1)


def test_dead_ends(tmp_path) -> None:
    b = Builder(tmp_path / "d.sqlite")
    hub = b.node(0, 0)
    b.way(1, [b.node(-300, 0), hub])                                  # impasse de 300 m
    foot = b.node(0, -100)
    b.way(2, [hub, foot])                                             # 100 m jusqu'à une boucle de 3 km
    r = 3000 / (2 * math.pi)
    loop = [foot] + [b.node(r * math.sin(t), -100 - r + r * math.cos(t))
                     for t in [2 * math.pi * k / 60 for k in range(1, 60)]]
    b.way(3, [*loop, foot])
    b.way(4, [hub, b.node(4000, 0), b.node(9000, 0)])                 # sort de l'emprise
    g = RoadGraph.build(b.open(), bbox_xz(-5000, -5000, 5000, 5000), FRAME)
    dead = {e.id: g.dead_end(e, forward=fwd) for e, fwd in g.branches(g.cluster[hub])}
    assert dead == {"1:0": True, "2:0": False, "4:0": False}
    assert g.nodes[g.cluster[g.edges["4:0"].raw_b]].frontier
    assert g.dead_end("2:0", depth_m=4000)                             # la boucle ne fait que 3,1 km


def test_roundabout_is_one_choice(tmp_path) -> None:
    b = Builder(tmp_path / "r.sqlite")
    ring = [b.node(20 * math.sin(t), -20 * math.cos(t)) for t in [2 * math.pi * k / 8 for k in range(8)]]
    b.way(10, [*ring, ring[0]], highway="tertiary", junction="roundabout")
    # ring[0] au nord, ring[2] à l'est, ring[4] au sud, ring[6] à l'ouest (sens horaire vu du ciel)
    for wid, k, (dx, dz) in ((1, 0, (0, -1)), (2, 2, (1, 0)), (3, 4, (0, 1)), (4, 6, (-1, 0))):
        x, z = b.pos[ring[k]]
        b.way(wid, [ring[k], b.node(x + 300 * dx, z + 300 * dz)], highway="tertiary")
    g = RoadGraph.build(b.open(), BIG, FRAME)
    choice = {g.cluster[n] for n in (ring[0], ring[2], ring[4], ring[6])}
    assert len(choice) == 1
    node = g.nodes[choice.pop()]
    assert node.ring and abs(node.x) < 1 and abs(node.z) < 1
    br = g.out_edges(node.id, arriving_heading_deg=0.0, arriving_edge="3:0")
    assert len(br) == 3 and [round(x.angle_deg / 10) * 10 for x in br] == [-90, 0, 90]


def test_close_junctions_merge(tmp_path) -> None:
    b = Builder(tmp_path / "m.sqlite")
    j1, j2 = b.node(0, 0), b.node(10, 0)
    b.way(1, [b.node(-300, 0), j1, j2, b.node(300, 0)])
    b.way(2, [b.node(0, 300), j1])
    b.way(3, [j2, b.node(10, -300)])
    g = RoadGraph.build(b.open(), BIG, FRAME)
    assert g.cluster[j1] == g.cluster[j2]
    assert sum(e.internal for e in g.edges.values()) == 1
    br = g.out_edges(g.cluster[j1], 0.0, arriving_edge="2:0")
    assert [(x.edge.id, round(x.angle_deg)) for x in br] == [("1:0", -90), ("3:0", 0), ("1:2", 90)]


def test_extend_keeps_ids(tmp_path) -> None:
    b = Builder(tmp_path / "e.sqlite")
    pts = [(x, 0.0) for x in range(-1000, 3001, 100)]
    b.line(1, pts)
    b.line(2, [(500, 500), (500, 0), (500, -500)])
    b.line(3, [(2500, 500), (2500, -500)])
    db = b.open()
    g = RoadGraph.build(db, bbox_xz(-1200, -1200, 1200, 1200), FRAME)
    first = {k: (e.raw_a, e.raw_b, round(e.length_m, 3)) for k, e in g.edges.items()}
    frontier = [n for n in g.nodes.values() if n.frontier]
    assert len(frontier) == 1 and "3:0" not in g.edges
    added = g.extend(db, bbox_xz(1200, -1200, 3500, 1200))
    assert {k: (g.edges[k].raw_a, g.edges[k].raw_b, round(g.edges[k].length_m, 3)) for k in first} == first
    assert "3:0" in added and not any(n.frontier for n in g.nodes.values())


def test_grid_100_km2_builds_fast(tmp_path) -> None:
    b = Builder(tmp_path / "g.sqlite")
    step, half = 200, 5000
    grid = {(i, j): b.node(i * step - half, j * step - half) for i in range(51) for j in range(51)}
    for i in range(51):
        b.way(10_000 + i, [grid[(i, j)] for j in range(51)])
        b.way(20_000 + i, [grid[(j, i)] for j in range(51)])
    db = b.open()
    t0 = time.perf_counter()
    g = RoadGraph.build(db, bbox_xz(-6000, -6000, 6000, 6000), FRAME)
    dt = time.perf_counter() - t0
    print(f"grille de 100 km² : {g.stats()} en {dt:.2f} s")
    # Les quatre coins joignent deux bouts de voie : ce ne sont pas des nœuds, leurs deux arêtes n'en font qu'une.
    assert g.stats()["edges"] == 2 * 51 * 50 - 4 and len(g.nodes) == 51 * 51 - 4
    assert dt < 2.0 * 3          # seuil indicatif de 2 s, marge pour les machines lentes
