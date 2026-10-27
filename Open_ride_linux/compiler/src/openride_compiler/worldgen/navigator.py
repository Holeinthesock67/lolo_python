"""Navigateur du monde ouvert (lot W6, `docs/2.0/PLAN_SERIE_W.md` §2.4 et §5.4).

Choisit la branche par défaut à chaque carrefour quand le cycliste ne touche à rien :

- `ride` (balade) : garder un cap qui dérive lentement en préférant les petites routes ;
- `destination` : plus court chemin vers la cible dans le graphe connu, puis balade une fois arrivé ;
- `loop` (boucle de X km) : s'éloigner, puis revenir au départ quand le budget est presque dépensé.

Pur (aucune entrée-sortie) et déterministe : un même graphe, une même graine et un même
historique donnent toujours le même choix, ce qui permet au générateur (W8) de recalculer la route
engagée après un changement de branche.
"""

from __future__ import annotations

import heapq
import math
import zlib
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .graph import Branch, Edge, RoadGraph, heading_of, relative_angle

# --- poids du coût d'une branche (le plus petit gagne) -----------------------------------------
W_ANGLE = 100.0            # pour un écart de 180° entre la branche et le cap visé
CLASS_COST = {"m": 0.0, "t": 0.0, "c": 0.0, "s": 5.0, "k": 10.0, "p": 25.0}
W_DEAD_END = 1000.0        # exclut l'impasse s'il y a autre chose
W_VISITED = 80.0           # arête déjà parcourue pendant la séance
W_VISITED_RECENT = 250.0   # parcourue dans les 5 dernières minutes (ou les 2 derniers km)
W_TRAPPED = 300.0          # branche après laquelle on ne peut plus faire 1 km sans repasser quelque part
FRESH_M = 1000.0
W_TIE = 1.0                # départage tiré de la graine
W_AWAY = 40.0              # boucle, phase d'aller : prime à s'éloigner du départ
HEADING_LOOKAHEAD_M = 300.0
RECENT_S = 300.0
RECENT_M = 2000.0

# Dérive du cap de balade : ± 20° au plus, lente (périodes de 10 à 40 km).
DRIFT_MAX_DEG = 20.0

# Destination et boucle.
CLASS_FACTOR = {"m": 1.0, "t": 1.0, "c": 1.0, "s": 1.1, "k": 1.2, "p": 1.4}
ARRIVED_M = 200.0
TARGET_IN_GRAPH_M = 300.0
LOOP_OUT_SHARE = 0.4
LOOP_MARGIN_M = 1000.0

MODES = ("ride", "destination", "loop")

XZ = tuple[float, float]
History = Sequence[str | tuple[str, float]]


@dataclass(frozen=True)
class Choice:
    branch_edge_id: str
    forward: bool
    to_node: int
    scores: dict[str, float] = field(default_factory=dict)
    arrived: bool = False
    phase: str = "ride"          # ride, destination, loop_out, loop_middle, loop_return, u_turn


def _hash01(*parts) -> float:
    return (zlib.crc32(":".join(map(str, parts)).encode()) % 100_000) / 100_000.0


def _dist(a: XZ, b: XZ) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _bearing(a: XZ, b: XZ) -> float:
    return math.degrees(math.atan2(b[0] - a[0], -(b[1] - a[1]))) % 360.0


class Navigator:
    def __init__(self, graph: RoadGraph, mode: str, start_xz: XZ, start_heading_deg: float, seed: int,
                 target_xz: XZ | None = None, loop_m: float | None = None) -> None:
        if mode not in MODES:
            raise ValueError(f"mode de navigation inconnu : {mode}")
        if mode == "destination" and target_xz is None:
            raise ValueError("mode destination sans cible")
        if mode == "loop" and not loop_m:
            raise ValueError("boucle sans longueur")
        self.graph = graph
        self.mode = mode
        self.start_xz = (float(start_xz[0]), float(start_xz[1]))
        self.start_heading = float(start_heading_deg) % 360.0
        self.seed = int(seed)
        self.target_xz = target_xz
        self.loop_m = float(loop_m) if loop_m else None
        r = [_hash01(seed, "derive", k) for k in range(4)]
        self._drift = [(0.6, 20_000.0 + 20_000.0 * r[0], 2 * math.pi * r[1]),
                       (0.4, 10_000.0 + 10_000.0 * r[2], 2 * math.pi * r[3])]
        self._start_node = nearest(graph.nodes.values(), self.start_xz) if mode == "loop" else None

    # --- cap de balade ------------------------------------------------------------------------

    def ride_heading(self, ridden_m: float) -> float:
        drift = sum(a * math.sin(2 * math.pi * ridden_m / period + phase) - a * math.sin(phase)
                    for a, period, phase in self._drift)
        return (self.start_heading + DRIFT_MAX_DEG * max(-1.0, min(1.0, drift))) % 360.0

    # --- historique ---------------------------------------------------------------------------

    def _history(self, history: History) -> tuple[list[str], set[str], set[str], float]:
        ids, times = [], []
        for h in history:
            if isinstance(h, str):
                ids.append(h)
                times.append(None)
            else:
                ids.append(h[0])
                times.append(float(h[1]))
        ridden = sum(self.graph.edges[e].length_m for e in ids if e in self.graph.edges)
        recent: set[str] = set()
        if times and times[-1] is not None:
            now = times[-1]
            recent = {e for e, t in zip(ids, times) if t is not None and t >= now - RECENT_S}
        else:
            acc = 0.0
            for e in reversed(ids):
                recent.add(e)
                acc += self.graph.edges[e].length_m if e in self.graph.edges else 0.0
                if acc >= RECENT_M:
                    break
        return ids, set(ids), recent, ridden

    # --- coût de balade -----------------------------------------------------------------------

    def _ride_cost(self, br: Branch, aim_deg: float, seen: set[str], recent: set[str], n: int) -> dict[str, float]:
        h300 = heading_of(br.points, HEADING_LOOKAHEAD_M)
        dev = abs(relative_angle(h300, aim_deg))
        parts = {
            "angle": W_ANGLE * dev / 180.0,
            "class": CLASS_COST.get(br.edge.road_class, 0.0),
            "dead_end": W_DEAD_END if self.graph.dead_end(br.edge, forward=br.forward) else 0.0,
            "visited": W_VISITED_RECENT if br.edge.id in recent else W_VISITED if br.edge.id in seen else 0.0,
            "trapped": W_TRAPPED if seen and not self._fresh_ahead(br, seen) else 0.0,
            "tie": W_TIE * _hash01(self.seed, br.edge.id, int(br.forward), n),
        }
        parts["total"] = sum(parts.values())
        return parts

    def _fresh_ahead(self, br: Branch, seen: set[str]) -> bool:
        """Vrai si, après la branche, un chemin d'au moins 1 km reste sur des arêtes jamais parcourues."""
        g = self.graph
        steps = [0]

        def walk(node: int, dist: float, used: frozenset[str]) -> bool:
            if dist >= FRESH_M or g.nodes[node].frontier:
                return True
            steps[0] += 1
            if steps[0] > 500:
                return True
            for e, fwd in g.branches(node):
                if e.id in seen or e.id in used:
                    continue
                if walk(e.b if fwd else e.a, dist + e.length_m, used | {e.id}):
                    return True
            return False

        return walk(br.to_node, 0.0 if br.edge.id in seen else br.edge.length_m, frozenset({br.edge.id}))

    # --- choix --------------------------------------------------------------------------------

    def arriving_heading(self, node: int, arriving_edge: str | None) -> float:
        if arriving_edge is None:
            return self.start_heading
        e = self.graph.edges[arriving_edge]
        into = e.points if self.graph.cluster.get(e.raw_b) == node else e.points[::-1]
        return (heading_of(into[::-1]) + 180.0) % 360.0

    def choose(self, node: int, arriving_edge: str | None, history: History = ()) -> Choice:
        ids, seen, recent, ridden = self._history(history)
        arr = self.arriving_heading(node, arriving_edge)
        branches = self.graph.out_edges(node, arr, arriving_edge)
        if not branches:
            if arriving_edge is None:
                raise ValueError(f"nœud {node} sans aucune branche")
            e = self.graph.edges[arriving_edge]
            fwd = self.graph.cluster.get(e.raw_a) == node and e.allows(True)
            return Choice(e.id, fwd, e.b if fwd else e.a, {"total": 0.0}, phase="u_turn")
        n = len(ids)
        here = (self.graph.nodes[node].x, self.graph.nodes[node].z)

        if self.mode == "destination":
            assert self.target_xz is not None
            if _dist(here, self.target_xz) <= ARRIVED_M or self._arrived(ids):
                return self._pick_ride(branches, self.ride_heading(ridden), seen, recent, n, arrived=True)
            goal = nearest(self.graph.nodes.values(), self.target_xz)
            gnode = self.graph.nodes[goal]
            if _dist((gnode.x, gnode.z), self.target_xz) <= TARGET_IN_GRAPH_M:
                path = self._shortest_first_step(node, goal, branches)
                if path is not None:
                    br, cost = path
                    return Choice(br.edge.id, br.forward, br.to_node, {"total": cost}, phase="destination")
            return self._pick_ride(branches, _bearing(here, self.target_xz), seen, recent, n, phase="destination")

        if self.mode == "loop":
            assert self.loop_m is not None and self._start_node is not None
            home = self._start_node
            if ridden >= 0.5 * self.loop_m and (node == home or _dist(here, self.start_xz) <= ARRIVED_M):
                return self._pick_ride(branches, self.ride_heading(ridden), seen, recent, n, arrived=True)
            to_home = self._distances_to(home)
            if ridden < LOOP_OUT_SHARE * self.loop_m:
                best = None
                for br in branches:
                    sc = self._ride_cost(br, self.ride_heading(ridden), seen, recent, n)
                    end = self.graph.nodes[br.to_node]
                    gain = (_dist((end.x, end.z), self.start_xz) - _dist(here, self.start_xz)) / max(br.edge.length_m, 1.0)
                    sc["away"] = -W_AWAY * gain
                    sc["total"] += sc["away"]
                    if best is None or sc["total"] < best[1]["total"]:
                        best = (br, sc)
                br, sc = best  # type: ignore[misc]
                return Choice(br.edge.id, br.forward, br.to_node, sc, phase="loop_out")
            budget = self.loop_m - LOOP_MARGIN_M
            ret = [ridden + br.edge.length_m + to_home.get(br.to_node, math.inf) for br in branches]
            if min(ret) >= budget:
                k = min(range(len(branches)), key=lambda i: (ret[i], branches[i].edge.id))
                br = branches[k]
                return Choice(br.edge.id, br.forward, br.to_node, {"total": ret[k]}, phase="loop_return")
            fits = [b for b, r in zip(branches, ret) if r < budget] or branches
            return self._pick_ride(fits, self.ride_heading(ridden), seen, recent, n, phase="loop_middle")

        return self._pick_ride(branches, self.ride_heading(ridden), seen, recent, n)

    def _arrived(self, ids: list[str]) -> bool:
        assert self.target_xz is not None
        for e in ids:
            edge = self.graph.edges.get(e)
            if edge and min(_dist(edge.points[0], self.target_xz), _dist(edge.points[-1], self.target_xz)) <= ARRIVED_M:
                return True
        return False

    def _pick_ride(self, branches: list[Branch], aim: float, seen: set[str], recent: set[str], n: int,
                   arrived: bool = False, phase: str = "ride") -> Choice:
        scored = [(self._ride_cost(br, aim, seen, recent, n), br) for br in branches]
        sc, br = min(scored, key=lambda t: (t[0]["total"], t[1].edge.id, t[1].forward))
        return Choice(br.edge.id, br.forward, br.to_node, sc, arrived=arrived, phase=phase)

    # --- plus courts chemins ------------------------------------------------------------------

    def _weight(self, e: Edge) -> float:
        return e.length_m * CLASS_FACTOR.get(e.road_class, 1.0)

    def _shortest_first_step(self, start: int, goal: int, branches: list[Branch]) -> tuple[Branch, float] | None:
        """A* sur la longueur pondérée par classe ; renvoie la première branche du chemin."""
        if start == goal:
            return None
        g = self.graph
        gx, gz = g.nodes[goal].x, g.nodes[goal].z

        def h(n: int) -> float:
            return math.hypot(g.nodes[n].x - gx, g.nodes[n].z - gz)

        best = None
        for br in branches:
            cost = self._weight(br.edge)
            if br.to_node == goal:
                rest = 0.0
            else:
                rest = self._astar(br.to_node, goal, h, banned=br.from_node)
            if rest < math.inf and (best is None or cost + rest < best[1]):
                best = (br, cost + rest)
        return best

    def _astar(self, start: int, goal: int, h, banned: int | None = None) -> float:
        g = self.graph
        dist = {start: 0.0}
        heap = [(h(start), 0.0, start)]
        while heap:
            _, d, n = heapq.heappop(heap)
            if n == goal:
                return d
            if d > dist.get(n, math.inf):
                continue
            for e, fwd in g.branches(n):
                to = e.b if fwd else e.a
                if to == banned:
                    continue
                nd = d + self._weight(e)
                if nd < dist.get(to, math.inf):
                    dist[to] = nd
                    heapq.heappush(heap, (nd + h(to), nd, to))
        return math.inf

    def _distances_to(self, home: int) -> dict[int, float]:
        """Longueur du plus court retour vers `home` depuis chaque nœud (Dijkstra sur le graphe inversé)."""
        g = self.graph
        rev: dict[int, list[tuple[int, float]]] = {}
        for n in g.nodes:
            for e, fwd in g.branches(n):
                to = e.b if fwd else e.a
                rev.setdefault(to, []).append((n, e.length_m))
        dist = {home: 0.0}
        heap = [(0.0, home)]
        while heap:
            d, n = heapq.heappop(heap)
            if d > dist.get(n, math.inf):
                continue
            for prev, w in rev.get(n, []):
                nd = d + w
                if nd < dist.get(prev, math.inf):
                    dist[prev] = nd
                    heapq.heappush(heap, (nd, prev))
        return dist


def drive(nav: Navigator, start_node: int, max_m: float, until_arrived: bool = False,
          start_edge: str | None = None) -> list[Choice]:
    """Suit le navigateur sans intervention du cycliste (tests et générateur)."""
    node, arriving = start_node, start_edge
    history: list[str] = []
    out: list[Choice] = []
    ridden = 0.0
    while ridden < max_m:
        c = nav.choose(node, arriving, history)
        out.append(c)
        history.append(c.branch_edge_id)
        ridden += nav.graph.edges[c.branch_edge_id].length_m
        node, arriving = c.to_node, c.branch_edge_id
        if until_arrived and c.arrived:
            break
    return out


def nearest(nodes: Iterable, xz: XZ) -> int:
    return min(nodes, key=lambda n: (_dist((n.x, n.z), xz), n.id)).id
