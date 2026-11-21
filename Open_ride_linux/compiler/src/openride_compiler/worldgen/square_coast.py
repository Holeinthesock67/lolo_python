"""Mer, côte et plages d'un carré du monde ouvert (lot W23, format §13).

Même calcul que le compilateur (lot U3, `coast.py`), appliqué au carré de 1 km au lieu de l'étendue
d'un parcours :

- les lignes de côte de la base locale (`coastline`, la mer à droite) qui passent près du carré sont
  recollées bout à bout (`assemble_coastlines`, après avoir soudé les bouts distants de moins de
  `JOIN_M` : les tuiles vectorielles coupent la côte à leurs bords), puis coupées au carré ;
- la mer du carré se referme comme celle d'une cellule du compilateur (`close_sea`) ; un carré que
  la côte ne traverse pas est en mer si son centre est du côté mer de la côte la plus proche, à moins
  de `SEA_SEARCH_M` (sinon il est à terre) ;
- les tronçons de rivage (`cliff`, `sand`, `shingle`, `rock`) et les plages qui touchent la côte
  suivent les mêmes règles (`classify_shore`, `shore_runs`) ;
- la mer s'ajoute aux aires de la couche eau (`kind` = `sea`, `level_y` = 0) ; la côte est la couche
  `coast` du carré, coordonnées relatives à son coin comme les autres couches (§13).

Repère : celui de la zone (x = E, z = −N) ; les fonctions de `coast.py` travaillent en (e, n) = (x, −z).
"""

from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np
from scipy.spatial import cKDTree

from .. import coast as K
from .. import constants as C
from ..frame import LocalFrame
from .osmdb import OsmDb

SEA_SEARCH_M = 5000.0     # côte cherchée jusqu'à 5 km du carré pour savoir s'il est en mer
COAST_SQUARE_VERSION = 1  # version de la mer et de la côte des carrés (clé `coast` des versions d'un carré)
JOIN_M = 3.0              # bouts de côte soudés (coupure des tuiles vectorielles)
BEACH_SEARCH_M = 1000.0   # une plage dont le centre est dans le carré peut déborder

Point = K.Point
HeightFn = Callable[[np.ndarray, np.ndarray], np.ndarray]


def _en_line(frame: LocalFrame, coords) -> list[Point]:
    lon = np.array([c[0] for c in coords], float)
    lat = np.array([c[1] for c in coords], float)
    xs, zs = frame.to_xz(lat, lon)
    return [(float(x), float(-z)) for x, z in zip(np.atleast_1d(xs), np.atleast_1d(zs))]


def weld_ends(chains: list[list[Point]], tol: float = JOIN_M) -> list[list[Point]]:
    """Pose au même point les bouts de lignes distants de moins de `tol` (fin sur début)."""
    starts = [c[0] for c in chains]
    if not starts:
        return chains
    tree = cKDTree(np.asarray(starts, float))
    out = [list(c) for c in chains]
    for i, c in enumerate(out):
        d, j = tree.query(c[-1], distance_upper_bound=tol)
        if math.isfinite(d) and int(j) != i:
            c[-1] = out[int(j)][0]
    return out


def sea_side(p: Point, lines: list[list[Point]]) -> bool | None:
    """Le point est-il du côté mer (à droite) de la côte la plus proche ? None sans côte.

    Au plus près d'un sommet, la normale est la somme des normales des deux côtés voisins (règle
    de la pseudo-normale) : le résultat ne dépend pas du côté retenu.
    """
    best: tuple[float, int, int, float] | None = None
    arrays = [np.asarray(ln, float) for ln in lines if len(ln) >= 2]
    px, pn = p
    for li, a in enumerate(arrays):
        u, v = a[:-1], a[1:]
        d = v - u
        L2 = (d ** 2).sum(axis=1)
        L2[L2 == 0] = 1e-12
        t = np.clip(((px - u[:, 0]) * d[:, 0] + (pn - u[:, 1]) * d[:, 1]) / L2, 0.0, 1.0)
        q = u + d * t[:, None]
        dist = np.hypot(q[:, 0] - px, q[:, 1] - pn)
        k = int(np.argmin(dist))
        if best is None or dist[k] < best[0]:
            best = (float(dist[k]), li, k, float(t[k]))
    if best is None:
        return None
    _, li, k, t = best
    a = arrays[li]

    def right(i: int) -> np.ndarray:
        de, dn = a[i + 1] - a[i]
        n = math.hypot(de, dn) or 1.0
        return np.array([dn / n, -de / n])        # normale à droite (côté mer)

    closed = K.is_closed([tuple(x) for x in a])
    nseg = len(a) - 1
    normal = right(k)
    if t >= 1.0 and (k + 1 < nseg or closed):
        normal = normal + right((k + 1) % nseg)
        vtx = a[k + 1]
    elif t <= 0.0 and (k > 0 or closed):
        normal = normal + right((k - 1) % nseg)
        vtx = a[k]
    else:
        vtx = a[k] + (a[k + 1] - a[k]) * t
    return float((px - vtx[0]) * normal[0] + (pn - vtx[1]) * normal[1]) > 0.0


def square_coast(x0: float, z0: float, size_m: float, db: OsmDb, frame: LocalFrame,
                 bbox_of: Callable[[float, float, float, float], tuple[float, float, float, float]],
                 height_fn: HeightFn | None, tag: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aires de mer (coordonnées absolues du repère de zone) et couche `coast` (absolue aussi).

    `x0`, `z0` : coin nord-ouest du carré ; `bbox_of(x0, z0, x1, z1)` : emprise géographique d'un
    rectangle de zone ; `tag` : suffixe des identifiants (indices du carré).
    """
    rect = (x0, -(z0 + size_m), x0 + size_m, -z0)          # (e0, n0, e1, n1)
    m = SEA_SEARCH_M
    near_lines = db.coast_lines_in(bbox_of(x0 - m, z0 - m, x0 + size_m + m, z0 + size_m + m))
    chains = [_en_line(frame, ln.coords) for ln in near_lines if ln.kind == "coastline"]
    cliffs = [_en_line(frame, ln.coords) for ln in near_lines if ln.kind == "cliff"]
    lines = K.assemble_coastlines(weld_ends([c for c in chains if len(c) >= 2]))
    empty = {"version": C.COAST_VERSION, "lines": [], "beaches": []}
    if not lines:
        return [], empty

    pieces: list[list[Point]] = []
    for ln in lines:
        pieces.extend(K.clip_line(ln, rect))
    centre = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2)
    sea = K.close_sea(pieces, rect, lambda: bool(sea_side(centre, lines)))
    areas: list[dict[str, Any]] = []
    for n_poly, (outer_en, holes_en) in enumerate(sea.polygons):
        outer = K._xz_ring(outer_en, outer=True)
        if outer is None:
            continue
        holes = [h for h in (K._xz_ring(r, outer=False) for r in holes_en) if h is not None]
        areas.append({"id": f"sea_{tag}_{n_poly}", "kind": "sea", "level_y": C.SEA_LEVEL_Y,
                      "outer": outer, "holes": holes})
    if not pieces:
        return areas, empty

    # Plages qui touchent la côte (centre dans le carré) et rivage des morceaux de côte du carré.
    b = BEACH_SEARCH_M
    coast_pts = np.asarray([p for ln in lines for p in K._densify(ln, C.COAST_SAMPLE_STEP_M)], float)
    coast_tree = cKDTree(coast_pts)
    beaches: list[dict[str, Any]] = []
    beach_pts: list[Point] = []
    beach_kinds: list[str] = []
    rings: list[tuple[str, np.ndarray]] = []
    for a in db.beaches_in(bbox_of(x0 - b, z0 - b, x0 + size_m + b, z0 + size_m + b)):
        ring_en = _en_line(frame, a.outer)
        outer = K._xz_ring(ring_en, outer=True)
        if outer is None:
            continue
        dense = K._densify(ring_en + [ring_en[0]], C.COAST_SAMPLE_STEP_M)
        d, _ = coast_tree.query(np.asarray(dense, float), distance_upper_bound=C.COAST_BEACH_DIST_M)
        if not np.isfinite(d).any():
            continue
        kind = "shingle" if str(a.tags.get("surface", "")) in C.COAST_SHINGLE_SURFACES else "sand"
        beach_pts.extend(dense)
        beach_kinds.extend([kind] * len(dense))
        rings.append((kind, np.asarray(ring_en, float)))
        cx = sum(p[0] for p in outer) / len(outer)
        cz = sum(p[1] for p in outer) / len(outer)
        if x0 <= cx < x0 + size_m and z0 <= cz < z0 + size_m:
            holes = [h for h in (K._xz_ring(_en_line(frame, h), outer=False) for h in a.holes) if h is not None]
            beaches.append({"id": a.osm_id, "kind": kind, "outer": outer, "holes": holes})
    cliff_pts = [p for c in cliffs for p in K._densify(c, C.COAST_SAMPLE_STEP_M)]
    ctx = K.ShoreContext(cKDTree(np.asarray(cliff_pts, float)) if cliff_pts else None,
                         cKDTree(np.asarray(beach_pts, float)) if beach_pts else None,
                         beach_kinds, height_fn, rings)
    out_lines: list[dict[str, Any]] = []
    for n_pc, pc in enumerate(pieces):
        pts = K._densify(pc, C.COAST_LINE_STEP_M)
        for n_run, (shore, run) in enumerate(K.shore_runs(pts, K.classify_shore(pts, ctx))):
            rounded = K._round_pts(run)
            if len(rounded) >= 2:
                out_lines.append({"id": f"c{tag}_{n_pc}_{n_run}", "shore": shore, "points": rounded})
    return areas, {"version": C.COAST_VERSION, "lines": out_lines, "beaches": beaches}
