"""Graphe routier local du monde ouvert (lot W4, `docs/2.0/PLAN_SERIE_W.md` §5.4).

Construit depuis la base locale (`osmdb.py`, W3 ou W13) dans le repère d'une séance (x vers l'est,
z vers le sud, en mètres). Seules les voies admises (`road_class` différent de `x`) y entrent.

- Nœud du graphe : nœud OSM où se croisent au moins trois bouts de voie, bout de voie, changement
  de classe ou de sens unique entre deux voies, dans la base entière. Une voie qui sort de l'emprise
  est suivie jusqu'à un tel nœud ; s'il a des branches hors de l'emprise, il est `frontier` (la
  suite est complétée quand l'emprise s'agrandit). Les arêtes ne dépendent donc pas de l'emprise :
  `extend` ne renumérote ni ne modifie jamais une arête connue.
- Arête : portion de voie entre deux nœuds, éventuellement faite de plusieurs voies OSM mises bout à
  bout (un pont au milieu d'une route reste dans la même arête, dans `spans`). Identifiant stable
  `"<id de la voie OSM>:<indice du segment de départ dans la voie>"`, pris au bout qui donne le plus
  petit couple (voie, segment) ; chaque segment n'appartenant qu'à une arête, il est unique.
- Point de choix : un rond-point, ou deux carrefours à moins de 15 m l'un de l'autre, ne font qu'un
  choix ; leurs arêtes intérieures (`internal`) ne sont jamais proposées.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

from ..constants import LENGTH_EPS_M
from ..frame import LocalFrame
from . import osmdb
from .osmdb import BBox, OsmDb, Road

MERGE_M = 15.0
HEADING_M = 20.0
NO_U_TURN_DEG = 170.0
DEAD_END_M = 2000.0
MAX_SEARCH_STEPS = 20_000
MAX_CHAIN_SEGMENTS = 500_000     # garde-fou : voies suivies hors de l'emprise

Point = tuple[float, float]


@dataclass
class Node:
    id: int                          # nœud de choix : plus petit identifiant OSM de ses membres
    x: float
    z: float
    frontier: bool = False
    members: list[int] = field(default_factory=list)
    ring: list[Point] | None = None  # géométrie d'un rond-point (pour le profil, W5)


@dataclass
class Edge:
    id: str
    a: int                           # nœuds de choix aux deux bouts
    b: int
    raw_a: int                       # nœuds OSM aux deux bouts
    raw_b: int
    points: list[Point]
    length_m: float
    road_class: str
    oneway: int                      # 1 : de a vers b seulement ; -1 : de b vers a seulement ; 0 : les deux
    spans: list[list]                # [s_début, s_fin, "bridge" | "tunnel"]
    name: str | None
    osm_nodes: list[int]
    roundabout: bool = False
    internal: bool = False           # intérieur d'un point de choix (rond-point, carrefour double)

    @property
    def degenerate(self) -> bool:
        """Arête sans longueur (points confondus, fréquent après la quantification des tuiles) : pas de profil possible."""
        return self.length_m < LENGTH_EPS_M

    def allows(self, forward: bool) -> bool:
        return self.oneway == 0 or (self.oneway == 1) == forward

    def oriented(self, forward: bool) -> list[Point]:
        return self.points if forward else self.points[::-1]


@dataclass(frozen=True)
class Branch:
    edge: Edge
    forward: bool
    from_node: int
    to_node: int
    heading_deg: float               # cap initial (0 = nord, 90 = est)
    angle_deg: float                 # relatif au cap d'arrivée, positif à droite, dans ]−180, 180]

    @property
    def points(self) -> list[Point]:
        return self.edge.oriented(self.forward)


def heading_of(points: list[Point], dist_m: float = HEADING_M) -> float:
    """Cap moyen sur les `dist_m` premiers mètres (direction du début vers le point à cette distance)."""
    x0, z0 = points[0]
    done = 0.0
    tx, tz = points[-1]
    for (xa, za), (xb, zb) in zip(points, points[1:]):
        seg = math.hypot(xb - xa, zb - za)
        if done + seg >= dist_m and seg > 0:
            t = (dist_m - done) / seg
            tx, tz = xa + t * (xb - xa), za + t * (zb - za)
            break
        done += seg
    return math.degrees(math.atan2(tx - x0, -(tz - z0))) % 360.0


def relative_angle(heading: float, arriving: float) -> float:
    a = (heading - arriving) % 360.0
    return a - 360.0 if a > 180.0 else a


def _length(points: list[Point]) -> float:
    return sum(math.hypot(xb - xa, zb - za) for (xa, za), (xb, zb) in zip(points, points[1:]))


class RoadGraph:
    def __init__(self, frame: LocalFrame) -> None:
        self.frame = frame
        self.bboxes: list[BBox] = []
        self.ways: dict[int, Road] = {}
        self.pos: dict[int, Point] = {}
        self.nodes: dict[int, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.cluster: dict[int, int] = {}          # nœud OSM → nœud de choix
        self._raw_graph_nodes: set[int] = set()
        self._adj: dict[int, list[Edge]] = {}
        self._full: dict[int, list[tuple[int, int, bool]]] = {}
        self._db: OsmDb | None = None

    # --- construction ---------------------------------------------------------------------------

    @classmethod
    def build(cls, db: OsmDb, bbox: BBox, frame: LocalFrame) -> "RoadGraph":
        g = cls(frame)
        g.extend(db, bbox)
        return g

    def extend(self, db: OsmDb, bbox: BBox) -> list[str]:
        """Ajoute les routes qui touchent une nouvelle emprise ; renvoie les arêtes nouvelles."""
        self._db = db
        self.bboxes.append(tuple(bbox))  # type: ignore[arg-type]
        self._add_ways(db.roads_in(bbox))
        before = set(self.edges)
        self._rebuild()
        return sorted(set(self.edges) - before)

    def _add_ways(self, roads: Iterable[Road]) -> None:
        new = [r for r in roads if r.osm_id not in self.ways]
        for r in new:
            self.ways[r.osm_id] = r
        self._project(new)

    def _project(self, ways: Iterable[Road]) -> None:
        ids, lons, lats = [], [], []
        for r in ways:
            for nid, (lon, lat) in zip(r.nodes, r.coords):
                if nid not in self.pos:
                    ids.append(nid)
                    lons.append(lon)
                    lats.append(lat)
        if not ids:
            return
        x, z = self.frame.to_xz(np.array(lats), np.array(lons))
        for nid, xi, zi in zip(ids, np.atleast_1d(x), np.atleast_1d(z)):
            self.pos[nid] = (float(xi), float(zi))

    def _touching(self, r: Road) -> list[int]:
        """Indices des segments de la voie qui touchent une des emprises chargées."""
        return [i for i in range(len(r.coords) - 1)
                if any(osmdb.segment_touches(r.coords[i], r.coords[i + 1], b) for b in self.bboxes)]

    def _inside(self, p: tuple[float, float]) -> bool:
        return any(b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3] for b in self.bboxes)

    def _full_incidence(self, nid: int, lonlat: tuple[float, float]) -> list[tuple[int, int, bool]]:
        """Tous les bouts de segment admis au nœud dans la base entière (voies chargées au passage)."""
        if nid in self._full:
            return self._full[nid]
        eps = 1e-6
        lon, lat = lonlat
        self._add_ways(self._db.roads_in((lon - eps, lat - eps, lon + eps, lat + eps)))
        out = []
        for wid, r in self.ways.items():
            for k, n in enumerate(r.nodes):
                if n == nid:
                    if k < len(r.nodes) - 1:
                        out.append((wid, k, True))
                    if k > 0:
                        out.append((wid, k - 1, False))
        self._full[nid] = out
        return out

    def _attrs(self, wid: int) -> tuple:
        r = self.ways[wid]
        return r.road_class, r.oneway != 0, r.junction == "roundabout"

    def _rebuild(self) -> None:
        """Arêtes canoniques : une voie qui sort de l'emprise est suivie jusqu'à son vrai carrefour.

        Ainsi une arête ne dépend jamais de l'emprise demandée : deux graphes construits sur des
        emprises différentes donnent la même arête (mêmes nœuds, même géométrie, même identifiant),
        ce qui permet au terrain des carrés (W7) d'être le même quelle que soit la séance.
        """
        kept: set[tuple[int, int]] = set()
        todo: list[tuple[int, tuple[float, float]]] = []
        for wid, r in list(self.ways.items()):
            for i in self._touching(r):
                kept.add((wid, i))
                for k in (i, i + 1):
                    if not self._inside(r.coords[k]):
                        todo.append((r.nodes[k], r.coords[k]))
        graph = set(self._raw_graph_nodes)
        frontier: set[int] = set()
        done: set[int] = set()
        while todo:                                   # suivre les voies hors de l'emprise
            nid, ll = todo.pop()
            if nid in done:
                continue
            done.add(nid)
            full = self._full_incidence(nid, ll)
            if len(full) == 2 and len({self._attrs(w) for w, _, _ in full}) == 1 and len(kept) < MAX_CHAIN_SEGMENTS:
                for wid, i, fwd in full:
                    if (wid, i) not in kept:
                        kept.add((wid, i))
                        r = self.ways[wid]
                        k = i + 1 if fwd else i
                        if not self._inside(r.coords[k]):
                            todo.append((r.nodes[k], r.coords[k]))
                continue
            graph.add(nid)
            if any((w, i) not in kept for w, i, _ in full):
                frontier.add(nid)

        inc: dict[int, list[tuple[int, int, bool]]] = {}
        for wid, i in sorted(kept):
            r = self.ways[wid]
            inc.setdefault(r.nodes[i], []).append((wid, i, True))
            inc.setdefault(r.nodes[i + 1], []).append((wid, i, False))
        for nid, ends in inc.items():
            if len(ends) != 2 or len({self._attrs(w) for w, _, _ in ends}) > 1:
                if nid not in done or nid in graph or len(self._full.get(nid, ends)) != 2:
                    graph.add(nid)

        edges: dict[str, Edge] = {}
        seen: set[tuple[int, int]] = set()

        def walk(start: int, wid: int, i: int, fwd: bool) -> None:
            pts = [self.pos[start]]
            osm = [start]
            segs: list[tuple[int, int, bool]] = []
            node = start
            while True:
                seen.add((wid, i))
                segs.append((wid, i, fwd))
                r = self.ways[wid]
                node = r.nodes[i + 1] if fwd else r.nodes[i]
                pts.append(self.pos[node])
                osm.append(node)
                if node in graph:
                    break
                nxt = [e for e in inc[node] if (e[0], e[1]) not in seen]
                if not nxt:              # boucle fermée sans carrefour
                    break
                wid, i, fwd = nxt[0]
            self._make_edge(edges, segs, pts, osm)

        for nid in sorted(graph):
            for wid, i, fwd in sorted(inc.get(nid, [])):
                if (wid, i) not in seen:
                    walk(nid, wid, i, fwd)
        # Anneau sans aucun nœud de graphe : coupé à son plus petit nœud OSM (choix canonique).
        for wid, i in sorted(kept):
            if (wid, i) in seen:
                continue
            ring, stack = set(), [self.ways[wid].nodes[i]]
            while stack:
                n = stack.pop()
                if n in ring:
                    continue
                ring.add(n)
                for w2, i2, f2 in inc[n]:
                    r2 = self.ways[w2]
                    stack.append(r2.nodes[i2 + 1] if f2 else r2.nodes[i2])
            start = min(ring)
            graph.add(start)
            w0, i0, f0 = min(inc[start])
            walk(start, w0, i0, f0)

        self._raw_graph_nodes = graph
        self.edges = edges
        self._cluster(frontier, inc)

    def _make_edge(self, edges: dict[str, Edge], segs, pts: list[Point], osm: list[int]) -> None:
        first, last = segs[0], segs[-1]
        key_a, key_b = (first[0], first[1]), (last[0], last[1])      # (voie, segment) à chaque bout
        r0 = self.ways[first[0]]
        oneway = 0
        if r0.oneway:
            oneway = r0.oneway if first[2] else -r0.oneway
        cum = [0.0]
        for (xa, za), (xb, zb) in zip(pts, pts[1:]):
            cum.append(cum[-1] + math.hypot(xb - xa, zb - za))
        spans: list[list] = []
        for k, (wid, _, _) in enumerate(segs):
            r = self.ways[wid]
            kind = "bridge" if r.bridge else "tunnel" if r.tunnel else None
            if kind is None:
                continue
            if spans and spans[-1][2] == kind and abs(spans[-1][1] - cum[k]) < 1e-6:
                spans[-1][1] = cum[k + 1]
            else:
                spans.append([cum[k], cum[k + 1], kind])
        length = cum[-1]
        if key_b < key_a:                                   # identifiant pris au plus petit bout
            pts, osm, key_a = pts[::-1], osm[::-1], key_b
            oneway = -oneway
            spans = [[length - e, length - s, k] for s, e, k in reversed(spans)]
            r0 = self.ways[last[0]]
        spans = [[round(s, 2), round(e, 2), k] for s, e, k in spans]
        eid = f"{key_a[0]}:{key_a[1]}"
        edges[eid] = Edge(eid, osm[0], osm[-1], osm[0], osm[-1], pts, length, r0.road_class, oneway, spans,
                          r0.name, osm, roundabout=r0.junction == "roundabout")

    def _cluster(self, frontier: set[int], inc: dict[int, list]) -> None:
        parent: dict[int, int] = {}

        def find(n: int) -> int:
            while parent.get(n, n) != n:
                n = parent[n]
            return n

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

        def junction(n: int) -> bool:
            return n not in frontier and len(inc.get(n, [])) >= 3

        for e in self.edges.values():
            short = e.length_m < MERGE_M and junction(e.raw_a) and junction(e.raw_b)
            if e.degenerate:                                  # jamais parcourue ni accrochée : ses bouts ne font qu'un
                e.internal = True
                if e.raw_a != e.raw_b:
                    union(e.raw_a, e.raw_b)
            elif (e.roundabout or short) and e.raw_a != e.raw_b:
                e.internal = True
                union(e.raw_a, e.raw_b)
            elif e.roundabout:
                e.internal = True
        self.cluster = {n: find(n) for n in self._raw_graph_nodes}
        groups: dict[int, list[int]] = {}
        for n, c in self.cluster.items():
            groups.setdefault(c, []).append(n)
        self.nodes = {}
        for c, members in groups.items():
            xs = [self.pos[m][0] for m in members]
            zs = [self.pos[m][1] for m in members]
            ring = [p for e in self.edges.values() if e.roundabout and self.cluster.get(e.raw_a) == c
                    for p in e.points] or None
            if ring:
                xs, zs = [p[0] for p in ring], [p[1] for p in ring]
            self.nodes[c] = Node(c, float(np.mean(xs)), float(np.mean(zs)),
                                 frontier=any(m in frontier for m in members), members=sorted(members), ring=ring)
        self._adj = {}
        for e in self.edges.values():
            e.a, e.b = self.cluster[e.raw_a], self.cluster[e.raw_b]
            if not e.internal:
                self._adj.setdefault(e.a, []).append(e)
                if e.b != e.a:
                    self._adj.setdefault(e.b, []).append(e)

    # --- requêtes -------------------------------------------------------------------------------

    def node_of(self, osm_node: int) -> Node:
        return self.nodes[self.cluster[osm_node]]

    def branches(self, node: int) -> list[tuple[Edge, bool]]:
        """Toutes les sorties permises d'un nœud de choix (arête, sens), sans cap."""
        out = []
        for e in self._adj.get(node, []):
            if e.a == node and e.allows(True):
                out.append((e, True))
            if e.b == node and e.allows(False):
                out.append((e, False))
        return out

    def out_edges(self, node: int, arriving_heading_deg: float, arriving_edge: str | None = None) -> list[Branch]:
        """Branches au départ d'un nœud, triées de la plus à gauche à la plus à droite ; demi-tour exclu.

        `arriving_edge` : arête d'arrivée, exclue (sinon, toute branche à plus de 170° est un demi-tour).
        """
        out = []
        for e, fwd in self.branches(node):
            pts = e.oriented(fwd)
            h = heading_of(pts)
            ang = relative_angle(h, arriving_heading_deg)
            if arriving_edge is not None:
                if e.id == arriving_edge and e.a != e.b:
                    continue
            elif abs(ang) > NO_U_TURN_DEG:
                continue
            out.append(Branch(e, fwd, node, e.b if fwd else e.a, h, ang))
        return sorted(out, key=lambda br: br.angle_deg)

    def dead_end(self, edge: Edge | str, depth_m: float = DEAD_END_M, forward: bool = True) -> bool:
        """Vrai si, en prenant l'arête dans ce sens, aucun chemin sans retour ne fait `depth_m`.

        Un nœud au bord de l'emprise compte comme ouvert (la route continue hors du graphe connu).
        """
        e = self.edges[edge] if isinstance(edge, str) else edge
        start, first = (e.a, e.b) if forward else (e.b, e.a)
        steps = [0]

        def open_from(node: int, came_by: str, dist: float, visited: frozenset[int]) -> bool:
            if dist >= depth_m or self.nodes[node].frontier:
                return True
            steps[0] += 1
            if steps[0] > MAX_SEARCH_STEPS:
                return True
            for nxt, fwd in self.branches(node):
                to = nxt.b if fwd else nxt.a
                if nxt.a == nxt.b:                      # boucle qui revient au même nœud
                    if dist + nxt.length_m >= depth_m:
                        return True
                    continue
                if nxt.id == came_by:
                    continue
                if to in visited and to != start:
                    continue
                if to == start and dist + nxt.length_m < depth_m:
                    continue
                if open_from(to, nxt.id, dist + nxt.length_m, visited | {to}):
                    return True
            return False

        return not open_from(first, e.id, e.length_m, frozenset({start, first}))

    def stats(self) -> dict[str, int]:
        return {"nodes": len(self.nodes), "edges": sum(not e.internal for e in self.edges.values()),
                "internal_edges": sum(e.internal for e in self.edges.values()), "ways": len(self.ways)}
