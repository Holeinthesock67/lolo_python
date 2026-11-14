"""Plans d'eau et relief (lot EA1, `docs/lots/LOT_EA1_niveau_lacs_sol_sous_eau.md`).

Une seule règle pour les parcours compilés et les carrés du monde ouvert :

- **Niveau d'un plan d'eau** (`lake_level`) : médiane du MNT sur une grille de `LAKE_SAMPLE_M` alignée sur
  le repère, aux points du plan d'eau à plus de `LAKE_SHORE_CLEAR_M` de toute rive (le MNT Copernicus
  aplatit les lacs : cette valeur est la même pour tous les morceaux d'un lac découpé par les tuiles
  vectorielles), plafonnée au quart le plus bas de la rive (`LAKE_SHORE_QUANTILE`, pas d'eau perchée
  au-dessus de la berge ; un exutoire ou le pied d'un barrage seul ne tire plus le lac vers le bas).
  Trop petit pour un échantillon loin de la rive : tous les points dedans ; aucun : minimum de la rive
  (règle d'avant, lot I4).
- **Sol sous l'eau** (`sink_grid`) : les échantillons du relief dans un plan d'eau (îles exceptées)
  descendent à `level_y − WATER_SINK_M` au plus ; jamais remontés ; la chaussée (moins de
  `BLEND_INNER_M` du bord d'une route hors pont) est gardée. Plus de sol qui perce la surface.
- La mer (`sea`, lots U3 et U9) n'est pas concernée : niveau 0, MNT à 0, surface 0,2 m au-dessus.

La décision ne dépend que des coordonnées de l'échantillon et du polygone : deux tuiles voisines
abaissent leur bord commun de la même façon.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

import numpy as np
from scipy.spatial import cKDTree

from . import constants as C

HeightFn = Callable[[np.ndarray, np.ndarray], np.ndarray]

_EDGE_BLOCK = 256   # arêtes traitées ensemble (mémoire : bloc × points)


def _ring_array(ring: Iterable) -> np.ndarray:
    r = np.asarray([[float(p[0]), float(p[1])] for p in ring], dtype=float)
    if len(r) >= 2 and np.allclose(r[0], r[-1]):
        r = r[:-1]
    return r


def rings_contain(px: np.ndarray, pz: np.ndarray, rings: list[np.ndarray]) -> np.ndarray:
    """Points dans le polygone (pair-impair sur tous les anneaux : contour moins îles)."""
    px = np.asarray(px, dtype=float).ravel()
    pz = np.asarray(pz, dtype=float).ravel()
    inside = np.zeros(px.shape, dtype=bool)
    for r in rings:
        if len(r) < 3:
            continue
        xi, zi = r[:, 0], r[:, 1]
        xj, zj = np.roll(xi, 1), np.roll(zi, 1)
        for b in range(0, len(r), _EDGE_BLOCK):
            sl = slice(b, b + _EDGE_BLOCK)
            a_x, a_z, b_x, b_z = xi[sl, None], zi[sl, None], xj[sl, None], zj[sl, None]
            crosses = (a_z > pz[None, :]) != (b_z > pz[None, :])
            dz = np.where(b_z - a_z == 0.0, 1e-12, b_z - a_z)
            x_cut = (b_x - a_x) * (pz[None, :] - a_z) / dz + a_x
            hit = crosses & (px[None, :] < x_cut)
            inside ^= (np.count_nonzero(hit, axis=0) % 2).astype(bool)
    return inside


def _shore_points(rings: list[np.ndarray], step_m: float) -> np.ndarray:
    pts = []
    for r in rings:
        n = len(r)
        for k in range(n):
            a, b = r[k], r[(k + 1) % n]
            seg = float(np.hypot(*(b - a)))
            m = max(1, int(np.ceil(seg / step_m)))
            t = np.arange(m, dtype=float)[:, None] / m
            pts.append(a + t * (b - a))
    return np.concatenate(pts) if pts else np.zeros((0, 2))


def lake_level(outer: list, holes: list, height: HeightFn) -> float | None:
    """Altitude de la surface d'un plan d'eau (règle du module) ; None sans altitude connue."""
    rings = [_ring_array(outer)] + [_ring_array(h) for h in holes]
    rings = [r for r in rings if len(r) >= 3]
    if not rings:
        return None
    shore = _shore_points(rings, C.LAKE_SHORE_STEP_M)
    ys_shore = np.asarray(height(shore[:, 0], shore[:, 1]), dtype=float)
    ys_shore = ys_shore[np.isfinite(ys_shore)]
    if len(ys_shore) == 0:
        return None
    s = C.LAKE_SAMPLE_M
    o = rings[0]
    xs = np.arange(np.floor(o[:, 0].min() / s) * s, o[:, 0].max() + s, s)
    zs = np.arange(np.floor(o[:, 1].min() / s) * s, o[:, 1].max() + s, s)
    gx, gz = (a.ravel() for a in np.meshgrid(xs, zs))
    inside = rings_contain(gx, gz, rings)
    if inside.any():
        gx, gz = gx[inside], gz[inside]
        dist, _ = cKDTree(shore).query(np.column_stack((gx, gz)))
        deep = dist >= C.LAKE_SHORE_CLEAR_M
        if np.count_nonzero(deep) >= 3:
            gx, gz = gx[deep], gz[deep]
        ys = np.asarray(height(gx, gz), dtype=float)
        ys = ys[np.isfinite(ys)]
        if len(ys):
            cap = float(np.quantile(ys_shore, C.LAKE_SHORE_QUANTILE))
            return round(min(float(np.median(ys)), cap), 2)
    return round(float(ys_shore.min()), 2)


def inland_areas(areas: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Plans d'eau qui abaissent le sol : lacs, étangs, réservoirs à niveau connu (pas la mer)."""
    out = []
    for a in areas:
        if a.get("kind") not in C.INLAND_WATER_KINDS:
            continue
        lv = a.get("level_y")
        if not isinstance(lv, (int, float)) or not np.isfinite(lv):
            continue
        rings = [_ring_array(a["outer"])] + [_ring_array(h) for h in a.get("holes") or []]
        rings = [r for r in rings if len(r) >= 3]
        if rings:
            o = rings[0]
            out.append({"level_y": float(lv), "rings": rings,
                        "bbox": (o[:, 0].min(), o[:, 1].min(), o[:, 0].max(), o[:, 1].max())})
    return out


def sink_grid(gx: np.ndarray, gz: np.ndarray, y: np.ndarray, areas: list[dict[str, Any]],
              protect: np.ndarray | None = None, depth: float = C.WATER_SINK_M) -> int:
    """Abaisse (sur place) les échantillons `y` dans les plans d'eau de `inland_areas` ; rend leur nombre."""
    fx, fz, fy = np.ravel(gx), np.ravel(gz), y.reshape(-1)
    keep = None if protect is None else np.ravel(protect)
    count = 0
    for a in areas:
        x0, z0, x1, z1 = a["bbox"]
        sel = np.flatnonzero((fx >= x0) & (fx <= x1) & (fz >= z0) & (fz <= z1))
        if keep is not None:
            sel = sel[~keep[sel]]
        if not len(sel):
            continue
        sel = sel[rings_contain(fx[sel], fz[sel], a["rings"])]
        target = a["level_y"] - depth
        sel = sel[np.isfinite(fy[sel]) & (fy[sel] > target)]
        fy[sel] = target
        count += len(sel)
    return count


def chunk_areas(water_chunks: dict[Any, dict[str, Any]]) -> list[dict[str, Any]]:
    """Aires de la couche eau d'un parcours compilé (`water_chunks` : tronçon → {lines, areas})."""
    return [a for ch in water_chunks.values() for a in (ch.get("areas") or [])]


def sink_route_tiles(tiles: dict[str, dict[tuple[int, int], np.ndarray]], route: dict,
                     areas: Iterable[dict[str, Any]]) -> int:
    """Parcours compilé : sol des niveaux proche et lointain abaissé sous les plans d'eau (pas l'horizon,
    sans eau à cette distance) ; chaussée de la route gardée. Rend le nombre d'échantillons abaissés."""
    from .terrain import LEVELS, RouteAxis, tile_coords

    lakes = inland_areas(areas)
    if not lakes:
        return 0
    axis = RouteAxis(route["x"], route["z"], route["alt_m"])
    reach = C.ROAD_HALF_WIDTH_M + C.BLEND_INNER_M
    count = 0
    for level in LEVELS:
        for (ix, iz), g in (tiles.get(level.name) or {}).items():
            x0, z0 = ix * level.tile_m, iz * level.tile_m
            x1, z1 = x0 + level.tile_m, z0 + level.tile_m
            mine = [a for a in lakes if a["bbox"][0] <= x1 and a["bbox"][2] >= x0
                    and a["bbox"][1] <= z1 and a["bbox"][3] >= z0]
            if not mine:
                continue
            gx, gz = tile_coords(ix, iz, level)
            dist, _ = axis.nearest(gx, gz, reach)
            y = g.astype(float)
            n = sink_grid(gx, gz, y, mine, protect=np.isfinite(dist).reshape(gx.shape))
            if n:
                g[:, :] = y.astype(g.dtype)
                count += n
    return count


def read_world_areas(world) -> list[dict[str, Any]]:
    """Aires de `water/chunk_<k>.json` d'un parcours compilé (illisible : ignoré)."""
    import json
    from pathlib import Path

    out: list[dict[str, Any]] = []
    for p in sorted((Path(world) / "water").glob("chunk_*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out += [a for a in (doc.get("areas") or []) if isinstance(a, dict)]
    return out
