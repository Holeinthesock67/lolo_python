"""Grandes rivières en surface (lot EA3, `docs/lots/LOT_EA3_grandes_rivieres_surface.md`).

Une rivière cartographiée en surface (OSM `natural=water` + `water=river`, classe `river` des tuiles
vectorielles) devient une aire d'eau `river` dont la surface **descend le long du cours** : chaque
sommet des anneaux porte son altitude (`outer_y`, `holes_y`), l'engine interpole entre eux.

Une seule règle, parcours compilés et monde ouvert :

- **Niveau en un point** (`RiverLevels.at`) : MNT brut aux nœuds d'une grille de `RIVER_SAMPLE_M` alignée
  sur le repère, dans l'eau de la rivière (îles exceptées), à moins de `RIVER_LEVEL_RADIUS_M` du point ;
  plan ajusté à ces altitudes (la pente du cours ne biaise rien), puis quart le plus bas des écarts au plan
  (`RIVER_LEVEL_QUANTILE`, écarte les nœuds de bord mêlés à la berge), borné entre le plus bas et le plus
  haut de ces nœuds (le plan n'est jamais prolongé au-delà, au bout d'un bras étroit sans nœud). Le MNT Copernicus aplanit les
  grandes rivières en marches qui descendent ; la fenêtre glissante les lisse en une pente. Moins de trois
  nœuds : MNT au point. C'est la règle des lacs (EA1, MNT dans l'eau, valeur basse) sur une fenêtre
  glissante au lieu du plan d'eau entier.
- **Découpe** (`clip_to_rect`) : une rivière peut faire des dizaines de kilomètres ; elle est découpée en
  morceaux par carré de 1 km de la grille du repère (carrés du monde ouvert, tuiles proches des
  parcours). Deux carrés voisins calculent les mêmes points de coupe, au bit près.
- **Sol** : abaissé sous la surface à `niveau − WATER_SINK_M` comme sous un lac (`water_terrain`).
- **Ruban** : le cours d'eau en ligne (`waterway=river`) n'est plus dessiné dans la surface ; il reste
  pour les rivières sans surface.

Tout ne dépend que des coordonnées et des polygones : le niveau d'un point est le même quel que soit
le carré qui le calcule.
"""

from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence

import numpy as np
from scipy.spatial import cKDTree

from . import constants as C
from .water_terrain import rings_contain

HeightFn = Callable[[np.ndarray, np.ndarray], np.ndarray]
Ring = list[list[float]]
Poly = tuple[Ring, list[Ring]]

_EPS_AREA = 1e-6


# --- anneaux -------------------------------------------------------------------------------------

def _clean(ring: Iterable) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in ring:
        q = (float(p[0]), float(p[1]))
        if not out or q != out[-1]:
            out.append(q)
    if len(out) >= 2 and out[0] == out[-1]:
        out.pop()
    return out


def signed_area(ring: Sequence[Sequence[float]]) -> float:
    n = len(ring)
    acc = 0.0
    for i in range(n):
        x1, z1 = ring[i][0], ring[i][1]
        x2, z2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        acc += x1 * z2 - x2 * z1
    return 0.5 * acc


def _oriented(ring: list[tuple[float, float]], positive: bool) -> list[tuple[float, float]]:
    a = signed_area(ring)
    return ring if (a > 0) == positive else ring[::-1]


def densify_ring(ring: Sequence[Sequence[float]], step_m: float) -> list[list[float]]:
    """Anneau aux côtés d'au plus `step_m` ; les points d'un côté sont calculés depuis son extrémité la
    plus petite (ordre lexicographique) : le côté commun de deux morceaux voisins, parcouru dans les deux
    sens, reçoit exactement les mêmes points."""
    pts = [(float(p[0]), float(p[1])) for p in ring]
    n = len(pts)
    out: list[list[float]] = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        out.append([a[0], a[1]])
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        m = int(math.ceil(length / step_m)) if step_m > 0 else 1
        if m <= 1:
            continue
        lo, hi = (a, b) if a <= b else (b, a)
        mids = [(lo[0] + (hi[0] - lo[0]) * k / m, lo[1] + (hi[1] - lo[1]) * k / m) for k in range(1, m)]
        if lo is not a:
            mids.reverse()
        out.extend([[x, z] for x, z in mids])
    return out


# --- découpe d'un polygone à îles par un rectangle -----------------------------------------------

def _liang_barsky(a, b, x0, z0, x1, z1):
    t0, t1 = 0.0, 1.0
    dx, dz = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dz, a[1] - z0), (dz, z1 - a[1])):
        if p == 0.0:
            if q < 0.0:
                return None
            continue
        r = q / p
        if p < 0.0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
    if t0 > t1:
        return None
    return t0, t1


def _snap(p, x0, z0, x1, z1):
    """Point de coupe posé exactement sur le côté le plus proche du rectangle."""
    x, z = p
    d = (abs(x - x0), abs(x - x1), abs(z - z0), abs(z - z1))
    k = d.index(min(d))
    if k == 0:
        return (x0, min(max(z, z0), z1))
    if k == 1:
        return (x1, min(max(z, z0), z1))
    if k == 2:
        return (min(max(x, x0), x1), z0)
    return (min(max(x, x0), x1), z1)


def _perimeter_t(p, x0, z0, x1, z1) -> float:
    """Abscisse curviligne sur le bord, dans le sens direct : bas, droite, haut, gauche."""
    w, h = x1 - x0, z1 - z0
    x, z = p
    if z == z0 and x < x1:
        return x - x0
    if x == x1 and z < z1:
        return w + (z - z0)
    if z == z1 and x > x0:
        return w + h + (x1 - x)
    return 2 * w + h + (z1 - z)


def _inside_closed(p, x0, z0, x1, z1) -> bool:
    return x0 <= p[0] <= x1 and z0 <= p[1] <= z1


def _chains(ring: list[tuple[float, float]], x0, z0, x1, z1):
    """Morceaux d'un anneau dans le rectangle ; None si l'anneau n'en sort jamais."""
    n = len(ring)
    start = next((i for i, p in enumerate(ring) if not _inside_closed(p, x0, z0, x1, z1)), None)
    if start is None:
        return None
    chains = []
    cur: list[tuple[float, float]] | None = None
    for k in range(n):
        a, b = ring[(start + k) % n], ring[(start + k + 1) % n]
        seg = _liang_barsky(a, b, x0, z0, x1, z1)
        if seg is None:
            continue
        t0, t1 = seg
        if cur is None:
            cur = [_snap((a[0] + t0 * (b[0] - a[0]), a[1] + t0 * (b[1] - a[1])), x0, z0, x1, z1)]
        if t1 < 1.0:
            p1 = _snap((a[0] + t1 * (b[0] - a[0]), a[1] + t1 * (b[1] - a[1])), x0, z0, x1, z1)
            if p1 != cur[-1]:
                cur.append(p1)
            if len(cur) >= 2:
                chains.append(cur)
            cur = None
        elif b != cur[-1]:
            cur.append(b)
    return chains


def clip_to_rect(outer: Sequence, holes: Sequence[Sequence], x0: float, z0: float,
                 x1: float, z1: float) -> list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]]:
    """Polygone à îles découpé par le rectangle : liste de (contour direct, îles indirectes).

    Weiler-Atherton sur un rectangle : chaque morceau d'anneau dans le rectangle va d'une entrée à une
    sortie sur le bord ; depuis une sortie, on suit le bord dans le sens direct jusqu'à l'entrée suivante.
    Un polygone qui sort et rentre plusieurs fois donne plusieurs morceaux, sans côté dégénéré.
    """
    o = _clean(outer)
    if len(o) < 3 or abs(signed_area(o)) < _EPS_AREA:
        return []
    o = _oriented(o, True)
    hs = [_oriented(h, False) for h in (_clean(h) for h in holes) if len(h) >= 3 and abs(signed_area(h)) >= _EPS_AREA]
    rect = (x0, z0, x1, z1)
    inner_holes: list[list[tuple[float, float]]] = []
    chains: list[list[tuple[float, float]]] = []
    outer_inside = False
    oc = _chains(o, *rect)
    if oc is None:
        outer_inside = True
    else:
        chains += oc
    for h in hs:
        hc = _chains(h, *rect)
        if hc is None:
            inner_holes.append(h)
        else:
            chains += hc
    polys: list[list[tuple[float, float]]] = []
    if outer_inside:
        polys.append(o)
    elif chains:
        polys += _walk(chains, *rect)
    elif rings_contain(np.array([x0]), np.array([z0]), [np.asarray(o), *(np.asarray(h) for h in hs)])[0]:
        # aucun anneau ne coupe le rectangle : tout eau, ou tout terre (hors du contour, ou sur une île qui
        # le contient entier, K3-03)
        polys.append([(x0, z0), (x1, z0), (x1, z1), (x0, z1)])
    out = []
    for p in polys:
        if len(p) < 3 or signed_area(p) < _EPS_AREA:
            continue
        pa = np.asarray(p)
        mine = [h for h in inner_holes if rings_contain(np.array([h[0][0]]), np.array([h[0][1]]), [pa])[0]]
        out.append((p, mine))
    return out


def _walk(chains, x0, z0, x1, z1) -> list[list[tuple[float, float]]]:
    w, h = x1 - x0, z1 - z0
    per = 2 * (w + h)
    corners = [(w, (x1, z0)), (w + h, (x1, z1)), (2 * w + h, (x0, z1)), (per, (x0, z0))]
    entry = [_perimeter_t(c[0], x0, z0, x1, z1) for c in chains]
    exit_ = [_perimeter_t(c[-1], x0, z0, x1, z1) for c in chains]
    used = [False] * len(chains)
    out = []
    for first in range(len(chains)):
        if used[first]:
            continue
        poly: list[tuple[float, float]] = []
        k = first
        for _ in range(len(chains) + 1):
            used[k] = True
            for p in chains[k]:
                if not poly or poly[-1] != p:
                    poly.append(p)
            t = exit_[k]
            best, best_d = None, math.inf
            for j in range(len(chains)):
                if used[j] and j != first:
                    continue
                d = (entry[j] - t) % per
                if d < best_d:
                    best, best_d = j, d
            if best is None:
                break
            for tc, pc in sorted(corners, key=lambda c: (c[0] - t) % per):
                dc = (tc - t) % per
                if 0.0 < dc < best_d and (not poly or poly[-1] != pc):
                    poly.append(pc)
            if best == first:
                break
            k = best
        if len(poly) >= 2 and poly[0] == poly[-1]:
            poly.pop()
        out.append(poly)
    return out


def cells_of(bbox: tuple[float, float, float, float], cell_m: float) -> list[tuple[int, int]]:
    x0, z0, x1, z1 = bbox
    return [(i, j) for i in range(math.floor(x0 / cell_m), math.floor(x1 / cell_m) + 1)
            for j in range(math.floor(z0 / cell_m), math.floor(z1 / cell_m) + 1)]


def ring_bbox(ring: Sequence[Sequence[float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in ring]
    zs = [p[1] for p in ring]
    return min(xs), min(zs), max(xs), max(zs)


# --- niveau le long du cours ---------------------------------------------------------------------

class RiverLevels:
    """Niveau des rivières en tout point (règle du module), d'après leurs polygones et le MNT brut.

    `window` (x0, z0, x1, z1) borne la grille des nœuds : il doit couvrir les points qu'on évaluera,
    élargis de `RIVER_LEVEL_RADIUS_M` (les nœuds ne dépendent que des polygones, pas de la fenêtre).
    """

    def __init__(self, polys: Iterable[Poly], height: HeightFn,
                 window: tuple[float, float, float, float] | None = None) -> None:
        self.height = height
        s = C.RIVER_SAMPLE_M
        keys: list[np.ndarray] = []
        self.polys: list[tuple[list[np.ndarray], tuple[float, float, float, float]]] = []
        for outer, holes in polys:
            rings = [np.asarray(r, dtype=float)[:, :2] for r in [outer, *holes] if len(r) >= 3]
            if not rings:
                continue
            bb = (float(rings[0][:, 0].min()), float(rings[0][:, 1].min()),
                  float(rings[0][:, 0].max()), float(rings[0][:, 1].max()))
            self.polys.append((rings, bb))
            x0, z0, x1, z1 = bb
            if window is not None:
                x0, z0 = max(x0, window[0]), max(z0, window[1])
                x1, z1 = min(x1, window[2]), min(z1, window[3])
                if x0 > x1 or z0 > z1:
                    continue
            ii = np.arange(math.ceil(x0 / s), math.floor(x1 / s) + 1)
            jj = np.arange(math.ceil(z0 / s), math.floor(z1 / s) + 1)
            if not len(ii) or not len(jj):
                continue
            gi, gj = (a.ravel() for a in np.meshgrid(ii, jj))
            inside = rings_contain(gi * s, gj * s, rings)
            if inside.any():
                keys.append(np.column_stack((gi[inside], gj[inside])))
        if keys:
            k = np.unique(np.concatenate(keys), axis=0)
            self.nodes = k.astype(float) * s
            self.node_y = np.asarray(height(self.nodes[:, 0], self.nodes[:, 1]), dtype=float)
            ok = np.isfinite(self.node_y)
            self.nodes, self.node_y = self.nodes[ok], self.node_y[ok]
        else:
            self.nodes, self.node_y = np.zeros((0, 2)), np.zeros(0)
        self.tree = cKDTree(self.nodes) if len(self.nodes) else None

    def __bool__(self) -> bool:
        return bool(self.polys)

    def at(self, xs, zs) -> np.ndarray:
        xs = np.asarray(xs, dtype=float).ravel()
        zs = np.asarray(zs, dtype=float).ravel()
        out = np.full(len(xs), np.nan)
        if self.tree is not None and len(xs):
            near = self.tree.query_ball_point(np.column_stack((xs, zs)), C.RIVER_LEVEL_RADIUS_M)
            for i, idx in enumerate(near):
                if len(idx) < 3:
                    continue
                idx = np.sort(np.asarray(idx))   # même ordre quel que soit l'arbre : résultat au bit près
                ny = self.node_y[idx]
                # plan ajusté aux nœuds (la pente du cours ne biaise pas le quart bas), puis quart bas des écarts
                a = np.column_stack((np.ones(len(idx)), self.nodes[idx, 0] - xs[i], self.nodes[idx, 1] - zs[i]))
                coef = np.linalg.lstsq(a, ny, rcond=None)[0]
                y = float(coef[0] + np.quantile(ny - a @ coef, C.RIVER_LEVEL_QUANTILE))
                # borné aux nœuds de la fenêtre (K3-02) : au bout d'un bras étroit sans nœud, le plan serait
                # prolongé sans limite (eau des dizaines de mètres au-dessus du terrain, ou sol creusé dessous)
                out[i] = min(max(y, float(ny.min())), float(ny.max()))
        miss = ~np.isfinite(out)
        if miss.any():
            out[miss] = np.asarray(self.height(xs[miss], zs[miss]), dtype=float)
        return out

    def inside(self, xs, zs) -> np.ndarray:
        """Points dans l'eau d'une des rivières (îles exceptées)."""
        xs = np.asarray(xs, dtype=float).ravel()
        zs = np.asarray(zs, dtype=float).ravel()
        mask = np.zeros(len(xs), dtype=bool)
        for rings, (x0, z0, x1, z1) in self.polys:
            sel = np.flatnonzero(~mask & (xs >= x0) & (xs <= x1) & (zs >= z0) & (zs <= z1))
            if len(sel):
                mask[sel[rings_contain(xs[sel], zs[sel], rings)]] = True
        return mask


def piece_rings(outer: Sequence, holes: Sequence[Sequence]) -> tuple[Ring, list[Ring]]:
    """Anneaux d'un morceau tels qu'écrits : côtés densifiés (`RIVER_EDGE_STEP_M`), arrondis au cm."""
    o = [[round(p[0], 2), round(p[1], 2)] for p in densify_ring(outer, C.RIVER_EDGE_STEP_M)]
    hs = [[[round(p[0], 2), round(p[1], 2)] for p in densify_ring(h, C.RIVER_EDGE_STEP_M)] for h in holes]
    return o, hs


def river_area(item_id: str, outer: Ring, holes: list[Ring], levels: RiverLevels) -> dict | None:
    """Aire `river` (format 1.10) : altitude de chaque sommet (`outer_y`, `holes_y`), `level_y` médian
    (lecteurs d'avant 1.10)."""
    if len(outer) < 3:
        return None
    oy = levels.at([p[0] for p in outer], [p[1] for p in outer])
    hys = [levels.at([p[0] for p in h], [p[1] for p in h]) for h in holes]
    allv = np.concatenate([oy, *hys])
    if not np.all(np.isfinite(allv)):
        return None
    return {"id": item_id, "kind": "river", "level_y": round(float(np.median(allv)), 2),
            "outer": outer, "holes": holes, "outer_y": [round(float(v), 2) for v in oy],
            "holes_y": [[round(float(v), 2) for v in hy] for hy in hys]}


def trim_lines(lines: list[dict], levels: RiverLevels, x0: float = 0.0, z0: float = 0.0) -> list[dict]:
    """Rubans des cours d'eau (`[x, z, y]`, coordonnées relatives à (x0, z0)) coupés dans les rivières en
    surface ; le point dedans gardé à chaque bout prend le niveau de la surface."""
    out = []
    for line in lines:
        pts = line.get("points") or []
        if len(pts) < 2:
            out.append(line)
            continue
        xs = np.array([p[0] + x0 for p in pts], dtype=float)
        zs = np.array([p[1] + z0 for p in pts], dtype=float)
        inside = levels.inside(xs, zs)
        if not inside.any():
            out.append(line)
            continue
        ys = np.array([p[2] for p in pts], dtype=float)
        ys[inside] = levels.at(xs[inside], zs[inside])
        pieces = outside_pieces(inside)
        for n, (i, j) in enumerate(pieces):
            item = dict(line)
            if len(pieces) > 1:
                item["id"] = f"{line['id']}_r{n}"
            item["points"] = [[pts[q][0], pts[q][1], round(float(ys[q]), 2)] for q in range(i, j)]
            out.append(item)
    return out


def route_cells(route: dict, band_m: float, cell_m: float) -> set[tuple[int, int]]:
    """Carrés de la grille du repère à moins de `band_m` de la route (au sens des axes)."""
    xs = np.asarray(route["x"], dtype=float)
    zs = np.asarray(route["z"], dtype=float)
    offs = np.unique(np.append(np.arange(-band_m, band_m, cell_m), band_m))
    cells: set[tuple[int, int]] = set()
    for dx in offs:
        for dz in offs:
            ij = np.unique(np.column_stack((np.floor((xs + dx) / cell_m), np.floor((zs + dz) / cell_m))), axis=0)
            cells.update((int(a), int(b)) for a, b in ij)
    return cells


def add_route_rivers(river_polys: list[tuple[str, list, list]], route: dict, axis, height: HeightFn,
                     water_chunks: dict[int, dict[str, list[dict]]]) -> int:
    """Grandes rivières en surface d'un parcours compilé : chaque rivière est découpée par carré de 1 km
    du repère près de la route ; un morceau va au tronçon le plus proche de son centre (à moins de
    `OSM_BAND_M`), ou de son sommet le plus proche s'il n'entre dans le couloir que par un bord (K3-04 : rivière
    large longée par la route) ; les rubans des cours d'eau sont coupés dans la surface. Rend le nombre d'aires."""
    from .osm_layers import area_chunk_and_y

    cell = C.RIVER_CELL_M
    corridor = route_cells(route, C.OSM_BAND_M, cell)
    placed: list[tuple[int, str, Ring, list[Ring]]] = []
    for item_id, outer, holes in river_polys:
        for ci, cj in sorted(c for c in cells_of(ring_bbox(outer), cell) if c in corridor):
            x0, z0 = ci * cell, cj * cell
            pieces = clip_to_rect(outer, holes, x0, z0, x0 + cell, z0 + cell)
            for n, (po, ph) in enumerate(pieces):
                o, hs = piece_rings(po, ph)
                k, _ = area_chunk_and_y(o, route, axis)
                if k is not None:
                    placed.append((k, f"{item_id}_c{ci}_{cj}" + (f"_{n}" if len(pieces) > 1 else ""), o, hs))
    if not placed:
        return 0
    levels = RiverLevels([(o, hs) for _, _, o, hs in placed], height)
    count = 0
    for k, pid, o, hs in placed:
        area = river_area(pid, o, hs, levels)
        if area is not None:
            water_chunks.setdefault(k, {"lines": [], "areas": []})["areas"].append(area)
            count += 1
    for ch in water_chunks.values():
        if ch.get("lines"):
            ch["lines"] = trim_lines(ch["lines"], levels)
    return count


def outside_pieces(inside: np.ndarray) -> list[tuple[int, int]]:
    """Intervalles [i, j) d'une ligne hors des rivières, prolongés d'un point dedans à chaque bout
    (le ruban rejoint la surface, sans trou)."""
    n = len(inside)
    out = []
    i = 0
    while i < n:
        if inside[i]:
            i += 1
            continue
        j = i
        while j < n and not inside[j]:
            j += 1
        a, b = max(0, i - 1), min(n, j + 1)
        if b - a >= 2:
            out.append((a, b))
        i = j
    return out
