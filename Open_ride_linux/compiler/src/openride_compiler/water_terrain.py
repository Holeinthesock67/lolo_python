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
  descendent à `level_y − WATER_SINK_M` au plus ; jamais remontés. Plus de sol qui perce la surface.
  Près d'une route (hors pont), le fond du lac passe par le même fondu route / MNT que le relief
  (`terrain.blend_weight`, argument `road`) : chaussée gardée en deçà de `BLEND_INNER_M`, puis rive
  qui descend en douceur jusqu'au fond à `BLEND_OUTER_M` (20/11 : la route qui longe un lac ne
  surplombe plus une chute de 7 m sans talus, monde ouvert comme parcours compilés).
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

_ROW_CELLS = 4_000_000   # lignes × arêtes traitées ensemble (mémoire)
_MAX_LEVEL_SAMPLES = 20_000   # échantillons du MNT au plus pour le niveau d'un grand lac


def _ring_array(ring: Iterable) -> np.ndarray:
    r = np.asarray([[float(p[0]), float(p[1])] for p in ring], dtype=float)
    if len(r) >= 2 and np.allclose(r[0], r[-1]):
        r = r[:-1]
    return r


def rings_contain(px: np.ndarray, pz: np.ndarray, rings: list[np.ndarray]) -> np.ndarray:
    """Points dans le polygone (pair-impair sur tous les anneaux : contour moins îles).

    Balayage par lignes : les points d'une grille partagent peu de valeurs de z ; pour chacune, les
    abscisses où les arêtes coupent la ligne sont triées une fois, puis comptées à droite de chaque point
    (coût en lignes × arêtes, et non points × arêtes : un grand lac de 5 000 sommets reste rapide).
    """
    px = np.asarray(px, dtype=float).ravel()
    pz = np.asarray(pz, dtype=float).ravel()
    inside = np.zeros(px.shape, dtype=bool)
    rings = [r for r in rings if len(r) >= 3]
    if not len(px) or not rings:
        return inside
    ax = np.concatenate([r[:, 0] for r in rings])
    az = np.concatenate([r[:, 1] for r in rings])
    bx = np.concatenate([np.roll(r[:, 0], 1) for r in rings])
    bz = np.concatenate([np.roll(r[:, 1], 1) for r in rings])
    dz = np.where(bz - az == 0.0, 1e-12, bz - az)
    uz, row = np.unique(pz, return_inverse=True)
    order = np.argsort(row, kind="stable")
    starts = np.searchsorted(row[order], np.arange(len(uz) + 1))
    block = max(1, _ROW_CELLS // len(ax))
    for b0 in range(0, len(uz), block):
        zz = uz[b0:b0 + block, None]
        crosses = (az[None, :] > zz) != (bz[None, :] > zz)
        cut = np.where(crosses, (bx - ax)[None, :] * (zz - az[None, :]) / dz[None, :] + ax[None, :], np.inf)
        cut.sort(axis=1)
        n_cross = np.count_nonzero(crosses, axis=1)
        for k in range(len(zz)):
            n = int(n_cross[k])
            if n == 0:
                continue
            idx = order[starts[b0 + k]:starts[b0 + k + 1]]
            right = n - np.searchsorted(cut[k, :n], px[idx], side="right")
            inside[idx] = (right % 2).astype(bool)
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
    o = rings[0]
    # maille de 30 m, élargie par multiples entiers pour un grand lac (au plus _MAX_LEVEL_SAMPLES dans
    # l'emprise) : elle ne dépend que du polygone, donc reste la même pour toute tuile qui le calcule
    area = float((o[:, 0].max() - o[:, 0].min()) * (o[:, 1].max() - o[:, 1].min()))
    s = C.LAKE_SAMPLE_M * max(1, int(np.ceil(np.sqrt(area / (C.LAKE_SAMPLE_M ** 2 * _MAX_LEVEL_SAMPLES)))))
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


def inland_areas(areas: Iterable[dict[str, Any]], rivers: Any = None) -> list[dict[str, Any]]:
    """Plans d'eau qui abaissent le sol : lacs, étangs, réservoirs à niveau connu (pas la mer) ; rivières
    en surface (lot EA3) si `rivers` (`river_surface.RiverLevels`) donne leur niveau en chaque point."""
    out = []
    for a in areas:
        kind = a.get("kind")
        if kind == "river":
            lv_r = a.get("levels") or rivers
            if lv_r is None:
                continue
            entry: dict[str, Any] = {"level_at": lv_r.at}
        elif kind in C.INLAND_WATER_KINDS:
            lv = a.get("level_y")
            if not isinstance(lv, (int, float)) or not np.isfinite(lv):
                continue
            entry = {"level_y": float(lv)}
        else:
            continue
        rings = [_ring_array(a["outer"])] + [_ring_array(h) for h in a.get("holes") or []]
        rings = [r for r in rings if len(r) >= 3]
        if rings:
            o = rings[0]
            entry.update({"rings": rings, "bbox": (o[:, 0].min(), o[:, 1].min(), o[:, 0].max(), o[:, 1].max())})
            out.append(entry)
    return out


def sink_grid(gx: np.ndarray, gz: np.ndarray, y: np.ndarray, areas: list[dict[str, Any]],
              protect: np.ndarray | None = None, depth: float = C.WATER_SINK_M,
              road: tuple[np.ndarray, np.ndarray] | None = None) -> int:
    """Abaisse (sur place) les échantillons `y` dans les plans d'eau de `inland_areas` ; rend leur nombre.

    `road` = (distance au bord de la chaussée, altitude de la route) de chaque échantillon (inf / NaN loin de toute
    route) : le fond visé est fondu avec la route comme le relief (`terrain.blend`), si bien que la rive remonte
    jusqu'à la chaussée au lieu de tomber à pic. `protect` : échantillons jamais abaissés."""
    from .terrain import blend_weight

    fx, fz, fy = np.ravel(gx), np.ravel(gz), y.reshape(-1)
    keep = None if protect is None else np.ravel(protect)
    if road is not None:
        r_d, r_y = np.ravel(road[0]), np.ravel(road[1])
    count = 0
    for a in areas:
        x0, z0, x1, z1 = a["bbox"]
        sel = np.flatnonzero((fx >= x0) & (fx <= x1) & (fz >= z0) & (fz <= z1))
        if keep is not None:
            sel = sel[~keep[sel]]
        if not len(sel):
            continue
        sel = sel[rings_contain(fx[sel], fz[sel], a["rings"])]
        if not len(sel):
            continue
        if "level_at" in a:   # rivière (lot EA3) : surface qui descend le long du cours
            target = np.asarray(a["level_at"](fx[sel], fz[sel]), dtype=float) - depth
        else:
            target = np.full(len(sel), a["level_y"] - depth)
        if road is not None:   # même fondu que le relief : la route, puis la rive, puis le fond
            w = blend_weight(r_d[sel])
            ry = r_y[sel] - C.ROAD_SINK_M
            target = np.where(np.isfinite(ry) & (w < 1.0), (1.0 - w) * ry + w * target, target)
        low = np.isfinite(fy[sel]) & np.isfinite(target) & (fy[sel] > target)
        sel, target = sel[low], target[low]
        fy[sel] = target
        count += len(sel)
    return count


def chunk_areas(water_chunks: dict[Any, dict[str, Any]]) -> list[dict[str, Any]]:
    """Aires de la couche eau d'un parcours compilé (`water_chunks` : tronçon → {lines, areas})."""
    return [a for ch in water_chunks.values() for a in (ch.get("areas") or [])]


def sink_route_tiles(tiles: dict[str, dict[tuple[int, int], np.ndarray]], route: dict,
                     areas: Iterable[dict[str, Any]], spans=None, height: HeightFn | None = None) -> int:
    """Parcours compilé : sol des niveaux proche et lointain abaissé sous les plans d'eau (pas l'horizon,
    sans eau à cette distance) ; chaussée de la route gardée, hors ponts `spans` (lot EA4, comme le monde
    ouvert). Rend le nombre d'échantillons abaissés.

    `height` (MNT brut) donne le niveau des rivières en surface (lot EA3) ; sans lui, elles n'abaissent rien."""
    from .terrain import LEVELS, route_axis, tile_coords

    areas = list(areas)
    rivers = river_levels(areas, height) if height is not None else None
    lakes = inland_areas(areas, rivers)
    if not lakes:
        return 0
    axis = route_axis(route, spans)
    reach = C.ROAD_HALF_WIDTH_M + C.BLEND_OUTER_M
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
            dist, y_route = axis.nearest(gx, gz, reach)
            y = g.astype(float)
            n = sink_grid(gx, gz, y, mine, road=(dist - C.ROAD_HALF_WIDTH_M, y_route))
            if n:
                g[:, :] = y.astype(g.dtype)
                count += n
    return count


def river_levels(areas: Iterable[dict[str, Any]], height: HeightFn, window=None):
    """`RiverLevels` des aires `river` (lot EA3) ; None s'il n'y en a pas."""
    from .river_surface import RiverLevels

    polys = [(a["outer"], a.get("holes") or []) for a in areas if a.get("kind") == "river"]
    return RiverLevels(polys, height, window) if polys else None


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
