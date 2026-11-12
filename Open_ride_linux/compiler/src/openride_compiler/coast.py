"""Côte, mer et plages (lot U3, série U, version 3.0 ; format .world 1.6, §8 et §8 quinquies).

À partir des lignes de côte OpenStreetMap (`natural=coastline`, la mer à droite du sens de la ligne),
le compilateur écrit :

- les aires `sea` de la couche eau : la mer refermée sur le bord de l'étendue du terrain, découpée
  en carrés de 1 km (la grille des tuiles proches) qui recouvrent les tuiles lointaines ; chaque
  morceau est rangé dans le tronçon de 1 km de la route le plus proche du centre de son carré, si
  bien que l'engine charge la mer avec le reste du tronçon et que deux morceaux ne se recouvrent
  jamais ; les îles sont des trous ;
- la couche `coast` : les lignes de côte coupées aux mêmes carrés, en tronçons de même rivage
  (`cliff`, `sand`, `shingle`, `rock`), et les plages (`natural=beach`, `natural=sand`) qui touchent
  la côte.

Un carré de mer se calcule comme la terre et la mer d'OSM : on coupe les lignes de côte au carré,
puis, de la sortie d'un morceau de côte, on suit le bord du carré dans le sens horaire jusqu'à
l'entrée du morceau suivant (la mer est à droite). Un carré sans côte est tout en mer ou tout en
terre : on le lit sur la mer de l'étendue entière, calculée de la même façon.

Le niveau de la mer est 0 m, comme le contrat (§8) ; le terrain sous la mer n'est pas modifié.
Module sans réseau : les réponses Overpass sont lues par `osm.OverpassClient.fetch_coast`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.spatial import cKDTree

from . import constants as C
from .frame import LocalFrame
from .osm_layers import _extract_polygons, clean_and_orient_ring, extract_osm_date
from .terrain import FAR, select_tiles

HeightFn = Callable[[np.ndarray, np.ndarray], np.ndarray]

CELL_M = float(C.NEAR_TILE_M)          # carrés de la mer : la grille des tuiles proches (1 km)
EPS = 1e-6                             # tolérance des points sur le bord d'un carré (m)

Point = tuple[float, float]            # (e, n) : est, nord (repère direct, z = −n)


# --- étendue et carrés ------------------------------------------------------------------------

def extent_cells(route: dict[str, Any]) -> list[tuple[int, int]]:
    """Carrés de 1 km (indices de la grille proche) qui recouvrent les tuiles lointaines du terrain."""
    per = int(round(FAR.tile_m / CELL_M))
    cells: list[tuple[int, int]] = []
    for fx, fz in select_tiles(route["x"], route["z"], FAR):
        for i in range(per):
            for j in range(per):
                cells.append((fx * per + i, fz * per + j))
    return sorted(set(cells))


def extent_bbox_xz(cells: list[tuple[int, int]]) -> tuple[float, float, float, float]:
    """(x_min, z_min, x_max, z_max) de l'étendue."""
    ix = [c[0] for c in cells]
    iz = [c[1] for c in cells]
    return min(ix) * CELL_M, min(iz) * CELL_M, (max(ix) + 1) * CELL_M, (max(iz) + 1) * CELL_M


def coast_bbox(route: dict[str, Any], frame: LocalFrame) -> tuple[float, float, float, float]:
    """Boîte (south, west, north, east) en degrés de l'étendue, pour la requête Overpass de la côte."""
    x0, z0, x1, z1 = extent_bbox_xz(extent_cells(route))
    lats, lons = frame.to_latlon(np.array([x0, x1, x0, x1]), np.array([z0, z0, z1, z1]))
    return (round(float(lats.min()), 5), round(float(lons.min()), 5),
            round(float(lats.max()), 5), round(float(lons.max()), 5))


class ChunkLocator:
    """Tronçon de 1 km de la route le plus proche d'un carré (centre du carré, sans limite de distance)."""

    def __init__(self, route: dict[str, Any]) -> None:
        self.tree = cKDTree(np.column_stack((np.asarray(route["x"], float), np.asarray(route["z"], float))))
        self.n = int(route["n"])
        self.ds_m = float(route["ds_m"])
        self.length_m = float(route["length_m"])
        self._cache: dict[tuple[int, int], int] = {}

    def of_cell(self, ix: int, iz: int) -> int:
        key = (ix, iz)
        if key not in self._cache:
            _, idx = self.tree.query([(ix + 0.5) * CELL_M, (iz + 0.5) * CELL_M])
            i = int(idx)
            s = self.length_m if i >= self.n - 1 else i * self.ds_m
            self._cache[key] = int(s // C.CHUNK_LENGTH_M)
        return self._cache[key]

    def of_point(self, x: float, z: float) -> int:
        return self.of_cell(*cell_of(x, z))


def cell_of(x: float, z: float) -> tuple[int, int]:
    return int(math.floor(x / CELL_M)), int(math.floor(z / CELL_M))


def cell_rect_en(ix: int, iz: int) -> tuple[float, float, float, float]:
    """Rectangle (e0, n0, e1, n1) d'un carré dans le repère (est, nord)."""
    return ix * CELL_M, -(iz + 1) * CELL_M, (ix + 1) * CELL_M, -iz * CELL_M


# --- assemblage des lignes de côte ------------------------------------------------------------

def assemble_coastlines(chains: list[list[Point]]) -> list[list[Point]]:
    """Recolle bout à bout (fin d'une ligne = début de la suivante) des chemins donnés dans n'importe
    quel ordre ; le sens des lignes est gardé (la mer reste à droite). Une ligne refermée a son
    premier point répété à la fin."""
    def key(p: Point) -> tuple[float, float]:
        return round(p[0], 3), round(p[1], 3)

    chains = [list(c) for c in chains if len(c) >= 2]
    by_start: dict[tuple[float, float], list[int]] = {}
    ends = set()
    for i, c in enumerate(chains):
        by_start.setdefault(key(c[0]), []).append(i)
        ends.add(key(c[-1]))
    heads = [i for i, c in enumerate(chains) if key(c[0]) not in ends]
    order = heads + [i for i in range(len(chains)) if i not in set(heads)]
    used = [False] * len(chains)
    out: list[list[Point]] = []
    for i in order:
        if used[i]:
            continue
        used[i] = True
        line = list(chains[i])
        while key(line[-1]) != key(line[0]):
            nxt = next((j for j in by_start.get(key(line[-1]), []) if not used[j]), None)
            if nxt is None:
                break
            used[nxt] = True
            line.extend(chains[nxt][1:])
        out.append(line)
    return out


def is_closed(line: list[Point]) -> bool:
    return len(line) >= 4 and abs(line[0][0] - line[-1][0]) <= EPS and abs(line[0][1] - line[-1][1]) <= EPS


# --- découpe d'une ligne par un rectangle -----------------------------------------------------

def _snap(p: Point, rect: tuple[float, float, float, float]) -> Point:
    """Pose exactement sur le bord le plus proche un point calculé sur le bord du rectangle."""
    e0, n0, e1, n1 = rect
    e, n = p
    d = [abs(e - e0), abs(e - e1), abs(n - n0), abs(n - n1)]
    i = int(np.argmin(d))
    if d[i] > 1e-6 * max(1.0, CELL_M):
        return p
    if i == 0:
        e = e0
    elif i == 1:
        e = e1
    elif i == 2:
        n = n0
    else:
        n = n1
    return e, n


def _clip_segment(p: Point, q: Point, rect) -> tuple[float, float] | None:
    """Liang–Barsky : paramètres (t0, t1) de la partie de [p, q] dans le rectangle, ou None."""
    e0, n0, e1, n1 = rect
    de, dn = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-de, p[0] - e0), (de, e1 - p[0]), (-dn, p[1] - n0), (dn, n1 - p[1])):
        if pp == 0.0:
            if qq < 0.0:
                return None
            continue
        r = qq / pp
        if pp < 0.0:
            if r > t1:
                return None
            t0 = max(t0, r)
        else:
            if r < t0:
                return None
            t1 = min(t1, r)
    if t1 - t0 <= 0.0:
        return None
    return t0, t1


def clip_line(line: list[Point], rect, seg_mask: np.ndarray | None = None) -> list[list[Point]]:
    """Morceaux d'une ligne dans le rectangle, dans l'ordre de la ligne. `seg_mask` : segments dont
    la boîte touche le rectangle (les autres sont dehors). Une ligne refermée qui ne sort pas du
    rectangle donne un seul morceau refermé."""
    pieces: list[list[Point]] = []
    cur: list[Point] | None = None
    idx = range(len(line) - 1) if seg_mask is None else np.flatnonzero(seg_mask).tolist()
    last_i = None
    for i in idx:
        if cur is not None and last_i is not None and i != last_i + 1:
            pieces.append(cur)
            cur = None
        last_i = i
        p, q = line[i], line[i + 1]
        r = _clip_segment(p, q, rect)
        if r is None:
            if cur is not None:
                pieces.append(cur)
                cur = None
            continue
        t0, t1 = r
        a = p if t0 <= 0.0 else _snap((p[0] + t0 * (q[0] - p[0]), p[1] + t0 * (q[1] - p[1])), rect)
        b = q if t1 >= 1.0 else _snap((p[0] + t1 * (q[0] - p[0]), p[1] + t1 * (q[1] - p[1])), rect)
        if cur is None or t0 > 0.0:
            if cur is not None:
                pieces.append(cur)
            cur = [a]
        cur.append(b)
        if t1 < 1.0:
            pieces.append(cur)
            cur = None
    if cur is not None:
        pieces.append(cur)
    pieces = [pc for pc in pieces if len(pc) >= 2]
    # Ligne refermée coupée à son point de départ : on recolle la fin et le début.
    if is_closed(line) and len(pieces) >= 2:
        first, last = pieces[0], pieces[-1]
        if _same(first[0], line[0]) and _same(last[-1], line[-1]):
            pieces = [last + first[1:]] + pieces[1:-1]
    return pieces


def _same(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= EPS and abs(a[1] - b[1]) <= EPS


# --- fermeture de la mer dans un rectangle ----------------------------------------------------

def _on_border(p: Point, rect) -> bool:
    e0, n0, e1, n1 = rect
    tol = 1e-6 * max(1.0, CELL_M)
    inside = e0 - tol <= p[0] <= e1 + tol and n0 - tol <= p[1] <= n1 + tol
    return inside and (abs(p[0] - e0) <= tol or abs(p[0] - e1) <= tol
                       or abs(p[1] - n0) <= tol or abs(p[1] - n1) <= tol)


def _perimeter_t(p: Point, rect) -> float:
    """Abscisse sur le bord, dans le sens horaire depuis le coin nord-ouest."""
    e0, n0, e1, n1 = rect
    w, h = e1 - e0, n1 - n0
    tol = 1e-6 * max(1.0, CELL_M)
    e, n = p
    if abs(n - n1) <= tol and e < e1 - tol:
        return e - e0
    if abs(e - e1) <= tol and n > n0 + tol:
        return w + (n1 - n)
    if abs(n - n0) <= tol and e > e0 + tol:
        return w + h + (e1 - e)
    return 2 * w + h + (n - n0)


def _corners(rect) -> list[tuple[float, Point]]:
    e0, n0, e1, n1 = rect
    w, h = e1 - e0, n1 - n0
    return [(0.0, (e0, n1)), (w, (e1, n1)), (w + h, (e1, n0)), (2 * w + h, (e0, n0))]


def _ring_area_en(ring: list[Point]) -> float:
    acc = 0.0
    m = len(ring)
    for i in range(m):
        e0, n0 = ring[i]
        e1, n1 = ring[(i + 1) % m]
        acc += e0 * n1 - e1 * n0
    return 0.5 * acc


def _strip_closing(line: list[Point]) -> list[Point]:
    return line[:-1] if is_closed(line) else line


@dataclass
class SeaPolygons:
    """Mer d'un rectangle, repère (e, n) : contours (horaires ou non) et trous, morceaux ignorés."""

    polygons: list[tuple[list[Point], list[list[Point]]]] = field(default_factory=list)
    dangling: int = 0


def close_sea(pieces: list[list[Point]], rect, rect_is_sea: Callable[[], bool]) -> SeaPolygons:
    """Polygones de mer d'un rectangle à partir des morceaux de côte qu'il contient.

    `pieces` : morceaux de `clip_line` (ouverts, qui entrent et sortent par le bord, ou refermés,
    tout entiers dedans). `rect_is_sea` : sans morceau ouvert, dit si le bord du rectangle est en mer.
    """
    res = SeaPolygons()
    open_pieces: list[list[Point]] = []
    rings: list[list[Point]] = []
    for pc in pieces:
        if is_closed(pc):
            rings.append(_strip_closing(pc))
        elif _on_border(pc[0], rect) and _on_border(pc[-1], rect):
            open_pieces.append(pc)
        else:
            res.dangling += 1           # ligne de côte interrompue dans l'étendue (données OSM)

    outers: list[list[Point]] = []
    if open_pieces:
        perim = 2 * ((rect[2] - rect[0]) + (rect[3] - rect[1]))
        ts = [_perimeter_t(pc[0], rect) for pc in open_pieces]
        te = [_perimeter_t(pc[-1], rect) for pc in open_pieces]
        corners = _corners(rect)
        unused = set(range(len(open_pieces)))
        while unused:
            first = min(unused)
            unused.discard(first)
            ring = list(open_pieces[first])
            cur = te[first]
            for _ in range(len(open_pieces) + 1):
                cands = list(unused) + [first]
                best = min(cands, key=lambda c: ((ts[c] - cur) % perim, c != first))
                gap = (ts[best] - cur) % perim
                between = sorted(((t - cur) % perim, p) for t, p in corners if 0.0 < (t - cur) % perim < gap)
                ring.extend(p for _, p in between)
                if best == first:
                    break
                ring.extend(open_pieces[best])
                unused.discard(best)
                cur = te[best]
            outers.append(ring)
    else:
        if rect_is_sea():
            e0, n0, e1, n1 = rect
            outers.append([(e0, n1), (e1, n1), (e1, n0), (e0, n0)])

    islands = [r for r in rings if _ring_area_en(r) > 0.0]      # terre à gauche : île
    lagoons = [r for r in rings if _ring_area_en(r) < 0.0]      # mer à droite, refermée : mer intérieure
    outers.extend(lagoons)
    holes: list[list[list[Point]]] = [[] for _ in outers]
    for isl in islands:
        for i, o in enumerate(outers):
            if o in lagoons:
                continue
            if _point_in_ring_en(isl[0], o):
                holes[i].append(isl)
                break
    res.polygons = list(zip(outers, holes))
    return res


def _point_in_ring_en(p: Point, ring: list[Point]) -> bool:
    inside = False
    m = len(ring)
    j = m - 1
    for i in range(m):
        ei, ni = ring[i]
        ej, nj = ring[j]
        if (ni > p[1]) != (nj > p[1]) and p[0] < (ej - ei) * (p[1] - ni) / ((nj - ni) or 1e-12) + ei:
            inside = not inside
        j = i
    return inside


class SeaTester:
    """Dit si un point est en mer d'après les polygones de l'étendue entière (test vectorisé)."""

    def __init__(self, polygons: list[tuple[list[Point], list[list[Point]]]]) -> None:
        self.rings: list[np.ndarray] = []
        for outer, holes in polygons:
            self.rings.append(np.asarray(outer, float))
            self.rings.extend(np.asarray(h, float) for h in holes)

    def __call__(self, p: Point) -> bool:
        crossings = 0
        for r in self.rings:
            a, b = r, np.roll(r, -1, axis=0)
            cond = (a[:, 1] > p[1]) != (b[:, 1] > p[1])
            if not cond.any():
                continue
            a, b = a[cond], b[cond]
            ex = (b[:, 0] - a[:, 0]) * (p[1] - a[:, 1]) / (b[:, 1] - a[:, 1]) + a[:, 0]
            crossings += int(np.count_nonzero(p[0] < ex))
        return crossings % 2 == 1


def merge_cells(cells: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """Regroupe des carrés (ix, iz) en blocs rectangulaires (ix0, iz0, largeur, hauteur) qui ne se
    recouvrent pas : suites de carrés voisins par rangée, puis rangées identiques empilées."""
    rows: dict[int, list[int]] = {}
    for ix, iz in set(cells):
        rows.setdefault(iz, []).append(ix)
    runs: list[tuple[int, int, int]] = []          # (iz, ix0, largeur)
    for iz in sorted(rows):
        xs = sorted(rows[iz])
        start = prev = xs[0]
        for ix in xs[1:] + [None]:
            if ix is not None and ix == prev + 1:
                prev = ix
                continue
            runs.append((iz, start, prev - start + 1))
            if ix is not None:
                start = prev = ix
    blocks: list[list[int]] = []                    # [ix0, iz0, largeur, hauteur]
    open_by_span: dict[tuple[int, int], list[int]] = {}
    for iz, ix0, w in runs:
        b = open_by_span.get((ix0, w))
        if b is not None and b[1] + b[3] == iz:
            b[3] += 1
        else:
            b = [ix0, iz, w, 1]
            blocks.append(b)
            open_by_span[(ix0, w)] = b
    return [tuple(b) for b in blocks]


# --- rivage -----------------------------------------------------------------------------------

def _densify(pts: list[Point], step: float) -> list[Point]:
    out = [pts[0]]
    for (e0, n0), (e1, n1) in zip(pts, pts[1:]):
        k = max(1, int(math.ceil(math.hypot(e1 - e0, n1 - n0) / step)))
        out.extend((e0 + (e1 - e0) * s / k, n0 + (n1 - n0) * s / k) for s in range(1, k + 1))
    return out


def _land_normals(pts: list[Point]) -> np.ndarray:
    """Normale unitaire vers la terre (à gauche du sens de la ligne) en chaque point, repère (e, n)."""
    a = np.asarray(pts, float)
    t = np.zeros_like(a)
    t[1:-1] = a[2:] - a[:-2]
    t[0] = a[1] - a[0]
    t[-1] = a[-1] - a[-2]
    norm = np.hypot(t[:, 0], t[:, 1])
    norm[norm == 0] = 1.0
    t /= norm[:, None]
    return np.column_stack((-t[:, 1], t[:, 0]))


def cliff_by_slope(pts: list[Point], height_fn: HeightFn | None) -> np.ndarray:
    """Vrai où la pente du MNT dépasse 45° sur les 30 premiers mètres côté terre."""
    if height_fn is None or not pts:
        return np.zeros(len(pts), bool)
    a = np.asarray(pts, float)
    nrm = _land_normals(pts)
    offs = np.asarray(C.COAST_SLOPE_OFFSETS_M, float)
    e = (a[:, None, 0] + nrm[:, None, 0] * offs[None, :]).ravel()
    n = (a[:, None, 1] + nrm[:, None, 1] * offs[None, :]).ravel()
    ys = np.asarray(height_fn(e, -n), float).reshape(len(pts), len(offs))
    rise = np.diff(ys, axis=1) / np.diff(offs)[None, :]
    with np.errstate(invalid="ignore"):
        return np.nanmax(np.where(np.isfinite(rise), rise, -np.inf), axis=1) > math.tan(math.radians(C.COAST_CLIFF_SLOPE_DEG))


def points_in_ring(pts: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Points (tableau N × 2) dans un anneau (M × 2), règle pair-impair, boucle sur les arêtes."""
    inside = np.zeros(len(pts), bool)
    for (e0, n0), (e1, n1) in zip(ring, np.roll(ring, -1, axis=0)):
        cond = (n0 > pts[:, 1]) != (n1 > pts[:, 1])
        if not cond.any():
            continue
        ex = (e1 - e0) * (pts[cond, 1] - n0) / (n1 - n0) + e0
        inside[np.flatnonzero(cond)[pts[cond, 0] < ex]] ^= True
    return inside


@dataclass
class ShoreContext:
    cliff_tree: cKDTree | None
    beach_tree: cKDTree | None
    beach_kinds: list[str]
    height_fn: HeightFn | None
    beach_rings: list[tuple[str, np.ndarray]] = field(default_factory=list)   # (sorte, anneau (e, n))


def classify_shore(pts: list[Point], ctx: ShoreContext) -> list[str]:
    """Sorte du rivage en chaque point : falaise, puis plage de sable ou de galets, sinon roche."""
    a = np.asarray(pts, float)
    out = ["rock"] * len(pts)
    if ctx.beach_tree is not None:
        d, i = ctx.beach_tree.query(a, distance_upper_bound=C.COAST_BEACH_DIST_M)
        for k in np.flatnonzero(np.isfinite(d)):
            out[k] = ctx.beach_kinds[int(i[k])]
    for kind, ring in ctx.beach_rings:          # côte qui traverse la plage
        for k in np.flatnonzero(points_in_ring(a, ring)):
            out[k] = kind
    cliff = cliff_by_slope(pts, ctx.height_fn)
    if ctx.cliff_tree is not None:
        d, _ = ctx.cliff_tree.query(a, distance_upper_bound=C.COAST_CLIFF_DIST_M)
        cliff |= np.isfinite(d)
    for k in np.flatnonzero(cliff):
        out[k] = "cliff"
    return out


def shore_runs(pts: list[Point], shores: list[str]) -> list[tuple[str, list[Point]]]:
    """Tronçons de même rivage ; deux tronçons voisins partagent leur point de jonction."""
    runs: list[tuple[str, list[Point]]] = []
    start = 0
    for i in range(1, len(pts) + 1):
        if i == len(pts) or shores[i] != shores[start]:
            seg = pts[start:min(i + 1, len(pts))]
            if len(seg) >= 2:
                runs.append((shores[start], seg))
            elif runs:
                runs[-1][1].extend(seg[1:] if _same(runs[-1][1][-1], seg[0]) else seg)
            start = i
    return runs


# --- couche complète --------------------------------------------------------------------------

@dataclass
class CoastResult:
    present: bool
    sea_chunks: dict[int, list[dict[str, Any]]]
    coast_chunks: dict[int, dict[str, list[dict[str, Any]]]]
    sea_count: int
    lines_count: int
    beaches_count: int
    ignored_count: int
    osm_date: str | None


def _en(lat_lon_pts, frame: LocalFrame) -> list[Point]:
    lats = np.array([p[0] for p in lat_lon_pts], float)
    lons = np.array([p[1] for p in lat_lon_pts], float)
    xs, zs = frame.to_xz(lats, lons)
    return [(float(x), float(-z)) for x, z in zip(np.atleast_1d(xs), np.atleast_1d(zs))]


def _xz_ring(ring_en: list[Point], outer: bool) -> list[list[float]] | None:
    return clean_and_orient_ring([[e, -n] for e, n in ring_en], outer=outer)


def _round_pts(pts: list[Point]) -> list[list[float]]:
    out: list[list[float]] = []
    for e, n in pts:
        p = [round(e, 2), round(-n, 2) + 0.0]
        if not out or out[-1] != p:
            out.append(p)
    return out


def _bbox_overlap_mask(arr: np.ndarray, rect) -> np.ndarray:
    a, b = arr[:-1], arr[1:]
    e0, n0, e1, n1 = rect
    return ((np.minimum(a[:, 0], b[:, 0]) <= e1) & (np.maximum(a[:, 0], b[:, 0]) >= e0)
            & (np.minimum(a[:, 1], b[:, 1]) <= n1) & (np.maximum(a[:, 1], b[:, 1]) >= n0))


def build_coast(
    route: dict[str, Any],
    frame: LocalFrame,
    responses: list[dict[str, Any]],
    height_fn: HeightFn | None = None,
) -> CoastResult:
    """Mer (aires `sea` par tronçon) et couche côte d'un parcours, d'après les réponses Overpass."""
    chains: list[list[Point]] = []
    cliffs: list[list[Point]] = []
    beach_polys: list[tuple[str, str, list[list[float]], list[list[list[float]]]]] = []
    seen: set[str] = set()
    for resp in responses:
        for el in resp.get("elements") or []:
            el_type, raw_id = el.get("type"), el.get("id")
            if el_type not in ("way", "relation") or raw_id is None:
                continue
            obj_id = f"{'w' if el_type == 'way' else 'r'}{raw_id}"
            if obj_id in seen:
                continue
            seen.add(obj_id)
            tags = el.get("tags") or {}
            natural = tags.get("natural")
            if natural in ("coastline", "cliff") and el_type == "way":
                geom = [(float(p["lat"]), float(p["lon"])) for p in el.get("geometry") or []
                        if "lat" in p and "lon" in p]
                if len(geom) >= 2:
                    (chains if natural == "coastline" else cliffs).append(_en(geom, frame))
            elif natural in ("beach", "sand"):
                surface = str(tags.get("surface", ""))
                kind = "shingle" if surface in C.COAST_SHINGLE_SURFACES else "sand"
                polys, _ = _extract_polygons(el, frame)
                for i, (outer, holes) in enumerate(polys):
                    beach_polys.append((obj_id if len(polys) == 1 else f"{obj_id}_{i}", kind, outer, holes))

    osm_date = extract_osm_date(responses)
    lines = assemble_coastlines(chains)
    if not lines:
        return CoastResult(False, {}, {}, 0, 0, 0, 0, osm_date)

    cells = extent_cells(route)
    locator = ChunkLocator(route)
    x0, z0, x1, z1 = extent_bbox_xz(cells)
    extent_rect = (x0, -z1, x1, -z0)

    # Mer de l'étendue entière : sert aux carrés sans côte.
    whole_pieces = [pc for ln in lines for pc in clip_line(ln, extent_rect)]
    rings_inside = [_strip_closing(pc) for pc in whole_pieces if is_closed(pc)]

    def extent_is_sea() -> bool:     # sans côte qui traverse l'étendue : île entourée de mer ?
        if not rings_inside:
            return False
        big = max(rings_inside, key=lambda r: abs(_ring_area_en(r)))
        return _ring_area_en(big) > 0.0

    whole = close_sea(whole_pieces, extent_rect, extent_is_sea)
    tester = SeaTester(whole.polygons)

    # Plages qui touchent la côte et lignes de falaise.
    coast_pts = np.asarray([p for ln in lines for p in _densify(ln, C.COAST_SAMPLE_STEP_M)], float)
    coast_tree = cKDTree(coast_pts)
    beaches: list[tuple[str, str, list[list[float]], list[list[list[float]]]]] = []
    beach_pts: list[Point] = []
    beach_kinds: list[str] = []
    for bid, kind, outer, holes in beach_polys:
        ring_en = [(p[0], -p[1]) for p in outer]
        dense = _densify(ring_en + [ring_en[0]], C.COAST_SAMPLE_STEP_M)
        d, _ = coast_tree.query(np.asarray(dense, float), distance_upper_bound=C.COAST_BEACH_DIST_M)
        if np.isfinite(d).any():
            beaches.append((bid, kind, outer, holes))
            beach_pts.extend(dense)
            beach_kinds.extend([kind] * len(dense))
    cliff_pts = [p for c in cliffs for p in _densify(c, C.COAST_SAMPLE_STEP_M)]
    ctx = ShoreContext(cKDTree(np.asarray(cliff_pts, float)) if cliff_pts else None,
                       cKDTree(np.asarray(beach_pts, float)) if beach_pts else None,
                       beach_kinds, height_fn,
                       [(kind, np.asarray([(p[0], -p[1]) for p in outer], float))
                        for _, kind, outer, _ in beaches])

    arrays = [np.asarray(ln, float) for ln in lines]
    boxes = [(a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()) for a in arrays]
    sea_chunks: dict[int, list[dict[str, Any]]] = {}
    coast_chunks: dict[int, dict[str, list[dict[str, Any]]]] = {}
    pending_lines: list[tuple[int, str, list[Point]]] = []
    open_cells: dict[int, list[tuple[int, int]]] = {}    # carrés tout en mer, par tronçon
    sea_count = 0
    ignored = whole.dangling
    for ix, iz in cells:
        rect = cell_rect_en(ix, iz)
        pieces: list[list[Point]] = []
        for ln, arr, (be0, bn0, be1, bn1) in zip(lines, arrays, boxes):
            if be1 < rect[0] or be0 > rect[2] or bn1 < rect[1] or bn0 > rect[3]:
                continue
            pieces.extend(clip_line(ln, rect, _bbox_overlap_mask(arr, rect)))
        if not pieces:
            if tester((rect[0] + 0.01, rect[3] - 0.01)):
                open_cells.setdefault(locator.of_cell(ix, iz), []).append((ix, iz))
            continue
        k = locator.of_cell(ix, iz)
        sea = close_sea(pieces, rect, lambda r=rect: tester((r[0] + 0.01, r[3] - 0.01)))
        for n_poly, (outer_en, holes_en) in enumerate(sea.polygons):
            outer = _xz_ring(outer_en, outer=True)
            if outer is None:
                ignored += 1
                continue
            holes = [h for h in (_xz_ring(r, outer=False) for r in holes_en) if h is not None]
            sea_chunks.setdefault(k, []).append({
                "id": f"sea_{ix}_{iz}_{n_poly}", "kind": "sea", "level_y": C.SEA_LEVEL_Y,
                "outer": outer, "holes": holes})
            sea_count += 1
        for n_pc, pc in enumerate(pieces):
            pending_lines.append((k, f"c{ix}_{iz}_{n_pc}", _densify(pc, C.COAST_LINE_STEP_M)))

    # Carrés tout en mer d'un même tronçon regroupés en blocs rectangulaires : une aire par bloc et
    # non par carré (r790 : 214 aires, dont une centaine pour un seul tronçon, préparées en 20 s par
    # l'engine, bateaux, faune et maillage de l'eau compris).
    for k, blocks in ((k, merge_cells(c)) for k, c in sorted(open_cells.items())):
        for ix0, iz0, w, h in blocks:
            x0b, z0b = ix0 * CELL_M, iz0 * CELL_M
            x1b, z1b = (ix0 + w) * CELL_M, (iz0 + h) * CELL_M
            sea_chunks.setdefault(k, []).append({
                "id": f"sea_{ix0}_{iz0}_b{w}x{h}", "kind": "sea", "level_y": C.SEA_LEVEL_Y,
                "outer": clean_and_orient_ring([[x0b, z1b], [x1b, z1b], [x1b, z0b], [x0b, z0b]], outer=True),
                "holes": []})
            sea_count += 1

    # Rivage : un seul appel au MNT pour tous les points des lignes.
    lines_count = 0
    if pending_lines:
        flat = [p for _, _, pts in pending_lines for p in pts]
        flat_shore = classify_shore(flat, ctx)
        pos = 0
        for k, lid, pts in pending_lines:
            shores = flat_shore[pos:pos + len(pts)]
            pos += len(pts)
            for n_run, (shore, run) in enumerate(shore_runs(pts, shores)):
                rounded = _round_pts(run)
                if len(rounded) < 2:
                    continue
                coast_chunks.setdefault(k, {"lines": [], "beaches": []})["lines"].append(
                    {"id": f"{lid}_{n_run}", "shore": shore, "points": rounded})
                lines_count += 1

    beaches_count = 0
    for bid, kind, outer, holes in beaches:
        cx = sum(p[0] for p in outer) / len(outer)
        cz = sum(p[1] for p in outer) / len(outer)
        if cell_of(cx, cz) not in set(cells):
            continue
        coast_chunks.setdefault(locator.of_point(cx, cz), {"lines": [], "beaches": []})["beaches"].append(
            {"id": bid, "kind": kind, "outer": outer, "holes": holes})
        beaches_count += 1

    return CoastResult(True, sea_chunks, coast_chunks, sea_count, lines_count, beaches_count,
                       ignored, osm_date)


def coast_manifest(res: CoastResult) -> dict[str, Any]:
    """Bloc `layers.coast` du manifeste ; `present: false` pour un parcours sans côte."""
    if not res.present:
        return {"present": False}
    return {"present": True, "version": C.COAST_VERSION, "lines_count": res.lines_count,
            "beaches_count": res.beaches_count, "osm_date": res.osm_date}


def write_coast_dir(folder: Path, chunks: dict[int, dict[str, list[dict[str, Any]]]]) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for k in sorted(chunks):
        payload = {"version": C.COAST_VERSION, "lines": chunks[k]["lines"], "beaches": chunks[k]["beaches"]}
        (folder / f"chunk_{k}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
