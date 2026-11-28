"""Maisons des villages en pente : exclure ou simplifier (lot MP1, 28 novembre 2026).

Orientation du propriétaire (brainstorming du 28/11, §10) : plutôt que de corriger les maisons étranges sur
une pente, on les retire de la construction ou on les simplifie ; on perd en fidélité, on gagne en cohérence.
Les règles s'appliquent à la compilation des parcours réels (couche `buildings`, format .world §6), après
`build_osm_layers` et l'ajout de la mer, sans changer le format ni l'engine :

1. **Bâtiment long sur une pente** (plus de LONG_MIN_M et dénivelé sous l'emprise de plus de LONG_DROP_M) :
   coupé en paliers (rectangles de PALIER_M au plus, chacun à sa hauteur) s'il est simple (contour proche de
   son rectangle orienté, sans cour), sinon retiré.
2. **Maison en L ou de forme compliquée** (contour qui remplit moins de FILL_MIN de son rectangle orienté :
   toit plat aujourd'hui, `building_styles.gd`) : remplacée par un rectangle de même aire, même centre et même
   orientation, qui reçoit un toit à pans ; retirée si le contour remplit moins de FILL_DROP.
3. **Socle visible trop haut** : l'engine relève le rez-de-chaussée jusqu'au terrain le plus haut du contour
   (`building_mesh.gd` floor_lift, au plus 4 m), le côté aval montre un socle de (haut − bas) × relief affiché.
   Au-delà de SOCLE_MAX_M affichés, la maison est retirée (au-delà de 4 m, son pied amont serait enterré).
4. **Au bord de l'eau** : maison dont le contour entre dans un lac, la mer ou une grande rivière, ou passe à
   moins de WATER_MARGIN_M de leur bord (ou du lit d'un cours d'eau dessiné en ligne) : retirée.

Seules les maisons et dépendances (familles `house` et `farm` de `building_styles.gd`) sont concernées : les
églises, immeubles, commerces et ateliers restent tels quels. Les bâtiments que la chaussée dessinée traverse
ou frôle (CD1, `osm_streamer.gd` drop_buildings_on_road, à moins de 1,5 m de l'axe) sont retirés par l'engine :
ils sont seulement **comptés** ici (estimation sur l'axe brut de la route), pour que le rapport dise tout ce
qui manque à un village.

Garde-fou : les maisons sont regroupées en villages (moins de VILLAGE_LINK_M entre deux maisons voisines, au
moins VILLAGE_MIN maisons) ; un village dont plus de VILLAGE_ALERT_SHARE des maisons sont retirées est signalé
dans le rapport (la route est à revoir plutôt que de livrer un village vide). Rien n'est remis : c'est une
alerte, pas une correction.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from .osm_layers import OsmLayersResult, point_in_ring, ring_centroid, signed_area

# Relief affiché (×2,5, `config.visual_grade_scale` du core, fixe pour tous d'après la décision du 28/11)
DISPLAY_RELIEF_K = 2.5
# Socle visible au plus (m affichés) côté aval
SOCLE_MAX_M = 1.5
# Bâtiment long sur pente
LONG_MIN_M = 30.0
LONG_DROP_M = 2.0
PALIER_M = 10.0
# Formes
FILL_MIN = 0.8          # même seuil que building_styles.gd FILL_MIN (toit à pans au-dessus)
FILL_DROP = 0.5         # en dessous : forme trop compliquée, retirée
# Eau
WATER_MARGIN_M = 3.0
# Chaussée dessinée (CD1, osm_streamer.gd BUILDING_AXIS_CLEAR_M) : comptée, pas retirée ici
ROAD_AXIS_CLEAR_M = 1.5
# Villages et garde-fou
VILLAGE_LINK_M = 60.0
VILLAGE_MIN = 8
VILLAGE_ALERT_SHARE = 0.30
# Pas des points lus le long des façades (osm_streamer.gd GROUND_SAMPLE_M)
GROUND_SAMPLE_M = 4.0

# Valeurs OSM de `building=*` qui ne sont ni des maisons ni des dépendances (building_styles.gd FAMILIES)
NOT_HOUSE = frozenset({
    "church", "chapel", "cathedral", "religious", "temple", "mosque",
    "apartments", "office", "school", "public", "civic", "government", "hospital", "university",
    "college", "kindergarten", "townhall", "hotel",
    "industrial", "warehouse", "commercial", "retail", "supermarket", "kiosk", "manufacture", "hangar",
    "service", "transportation", "sports_hall",
})

REASON_SOCLE = "socle"
REASON_LONG = "long_sur_pente"
REASON_SHAPE = "forme"
REASON_WATER = "eau"
REASONS = (REASON_SOCLE, REASON_LONG, REASON_SHAPE, REASON_WATER)

# Altitude du terrain réel aux points (xs, zs)
HeightFn = Callable[[np.ndarray, np.ndarray], np.ndarray]
# Tronçon d'un point (cx, cz) : k ou None
ChunkFn = Callable[[float, float], "int | None"]


def is_house(b: dict[str, Any]) -> bool:
    hint = b.get("hint") or {}
    return str(hint.get("building", "yes")).strip().lower() not in NOT_HOUSE


# ---------------------------------------------------------------------------------------------------------
# Géométrie
# ---------------------------------------------------------------------------------------------------------

def _hull(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    p = sorted(set(pts))
    if len(p) <= 2:
        return p

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for q in p:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0:
            lower.pop()
        lower.append(q)
    upper: list[tuple[float, float]] = []
    for q in reversed(p):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0:
            upper.pop()
        upper.append(q)
    return lower[:-1] + upper[:-1]


@dataclass
class OrientedRect:
    cx: float
    cz: float
    ux: float   # grand axe (unitaire)
    uz: float
    length: float
    width: float

    @property
    def area(self) -> float:
        return self.length * self.width

    def corners(self, u0: float, u1: float, half_w: float) -> list[list[float]]:
        """Rectangle de l'abscisse u0 à u1 le long du grand axe, demi-largeur half_w, sens antihoraire."""
        vx, vz = -self.uz, self.ux
        pts = []
        for u, v in ((u0, -half_w), (u1, -half_w), (u1, half_w), (u0, half_w)):
            pts.append([round(self.cx + u * self.ux + v * vx, 2), round(self.cz + u * self.uz + v * vz, 2)])
        if signed_area(pts) < 0:
            pts.reverse()
        return pts


def oriented_rect(ring: list[list[float]]) -> OrientedRect | None:
    """Rectangle orienté d'aire minimale (un côté sur un côté de l'enveloppe convexe)."""
    hull = _hull([(float(p[0]), float(p[1])) for p in ring])
    if len(hull) < 3:
        return None
    pts = np.array(hull, dtype=float)
    best: tuple[float, float, float, float, float, float, float] | None = None
    n = len(hull)
    for i in range(n):
        dx, dz = pts[(i + 1) % n] - pts[i]
        ln = math.hypot(dx, dz)
        if ln < 1e-6:
            continue
        ux, uz = dx / ln, dz / ln
        a = pts[:, 0] * ux + pts[:, 1] * uz
        b = -pts[:, 0] * uz + pts[:, 1] * ux
        area = (a.max() - a.min()) * (b.max() - b.min())
        if best is None or area < best[0]:
            best = (area, ux, uz, a.min(), a.max(), b.min(), b.max())
    if best is None:
        return None
    _, ux, uz, a0, a1, b0, b1 = best
    la, lb = a1 - a0, b1 - b0
    am, bm = (a0 + a1) / 2.0, (b0 + b1) / 2.0
    cx, cz = am * ux - bm * uz, am * uz + bm * ux
    if lb > la:   # grand axe = axe b
        ux, uz = -uz, ux
        la, lb = lb, la
    return OrientedRect(cx, cz, ux, uz, la, lb)


def fill_ratio(ring: list[list[float]], rect: OrientedRect | None) -> float:
    if rect is None or rect.area <= 1e-6:
        return 0.0
    return abs(signed_area(ring)) / rect.area


def _densify_ring(ring: list[list[float]], step: float) -> tuple[np.ndarray, np.ndarray]:
    xs: list[float] = []
    zs: list[float] = []
    n = len(ring)
    for i in range(n):
        ax, az = float(ring[i][0]), float(ring[i][1])
        bx, bz = float(ring[(i + 1) % n][0]), float(ring[(i + 1) % n][1])
        steps = max(1, math.ceil(math.hypot(bx - ax, bz - az) / step))
        for j in range(steps):
            t = j / steps
            xs.append(ax + (bx - ax) * t)
            zs.append(az + (bz - az) * t)
    return np.array(xs, dtype=float), np.array(zs, dtype=float)


def _seg_dist(px: np.ndarray, pz: np.ndarray, ax: float, az: float, bx: float, bz: float) -> np.ndarray:
    dx, dz = bx - ax, bz - az
    l2 = dx * dx + dz * dz
    if l2 < 1e-12:
        return np.hypot(px - ax, pz - az)
    t = np.clip(((px - ax) * dx + (pz - az) * dz) / l2, 0.0, 1.0)
    return np.hypot(px - (ax + t * dx), pz - (az + t * dz))


def _bbox(ring: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [float(p[0]) for p in ring]
    zs = [float(p[1]) for p in ring]
    return min(xs), min(zs), max(xs), max(zs)


def _bbox_near(a: tuple[float, float, float, float], b: tuple[float, float, float, float], m: float) -> bool:
    return not (a[2] + m < b[0] or b[2] + m < a[0] or a[3] + m < b[1] or b[3] + m < a[1])


# ---------------------------------------------------------------------------------------------------------
# Terrain et eau
# ---------------------------------------------------------------------------------------------------------

def footprint_drop(ring: list[list[float]], height: HeightFn, base_y: float) -> float:
    """Dénivelé réel sous l'emprise : terrain le plus haut le long du contour − base_y (≥ 0)."""
    xs, zs = _densify_ring(ring, GROUND_SAMPLE_M)
    ys = np.asarray(height(xs, zs), dtype=float)
    ys = ys[np.isfinite(ys)]
    if len(ys) == 0:
        return 0.0
    return max(0.0, float(ys.max()) - float(base_y))


def footprint_base(ring: list[list[float]], height: HeightFn, fallback: float) -> float:
    """Terrain le plus bas sous l'emprise (contour, centre et grille de 5 m), comme `compute_footprint_base_y`."""
    xs, zs = _densify_ring(ring, GROUND_SAMPLE_M)
    x0, z0, x1, z1 = _bbox(ring)
    gx = [float(x) for x in np.arange(x0, x1 + 0.1, 5.0)]
    gz = [float(z) for z in np.arange(z0, z1 + 0.1, 5.0)]
    inner = [(x, z) for x in gx for z in gz if point_in_ring(x, z, ring)]
    cx, cz = ring_centroid(ring)
    inner.append((cx, cz))
    ax = np.concatenate([xs, np.array([p[0] for p in inner], dtype=float)])
    az = np.concatenate([zs, np.array([p[1] for p in inner], dtype=float)])
    ys = np.asarray(height(ax, az), dtype=float)
    ys = ys[np.isfinite(ys)]
    return round(float(ys.min()), 2) if len(ys) else round(float(fallback), 2)


@dataclass
class WaterIndex:
    """Bords de l'eau : aires (lacs, mer, grandes rivières) et cours d'eau dessinés en ligne."""
    areas: list[tuple[list[list[float]], tuple[float, float, float, float]]] = field(default_factory=list)
    lines: list[tuple[np.ndarray, float, tuple[float, float, float, float]]] = field(default_factory=list)

    @classmethod
    def from_chunks(cls, water_chunks: dict[int, dict[str, list[dict[str, Any]]]]) -> "WaterIndex":
        idx = cls()
        for ch in water_chunks.values():
            for a in ch.get("areas", []):
                outer = a.get("outer") or []
                if len(outer) >= 3:
                    idx.areas.append((outer, _bbox(outer)))
            for ln in ch.get("lines", []):
                pts = ln.get("points") or []
                if len(pts) >= 2:
                    arr = np.array([[float(p[0]), float(p[1])] for p in pts], dtype=float)
                    bb = (float(arr[:, 0].min()), float(arr[:, 1].min()), float(arr[:, 0].max()),
                          float(arr[:, 1].max()))
                    idx.lines.append((arr, float(ln.get("width_m", 2.0)), bb))
        return idx

    def touches(self, ring: list[list[float]]) -> bool:
        bb = _bbox(ring)
        xs, zs = _densify_ring(ring, 2.0)
        for outer, abb in self.areas:
            if not _bbox_near(bb, abb, WATER_MARGIN_M):
                continue
            if any(point_in_ring(float(x), float(z), outer) for x, z in zip(xs, zs)):
                return True
            sel = [i for i in range(len(outer))]
            for i in sel:
                a, b = outer[i], outer[(i + 1) % len(outer)]
                if float(_seg_dist(xs, zs, float(a[0]), float(a[1]), float(b[0]), float(b[1])).min()) \
                        < WATER_MARGIN_M:
                    return True
        for arr, width, lbb in self.lines:
            m = width / 2.0 + WATER_MARGIN_M
            if not _bbox_near(bb, lbb, m):
                continue
            for i in range(len(arr) - 1):
                if float(_seg_dist(xs, zs, arr[i, 0], arr[i, 1], arr[i + 1, 0], arr[i + 1, 1]).min()) < m:
                    return True
        return False


class RoadAxisIndex:
    """Axe brut de la route, par cases de 50 m : bâtiments que la chaussée dessinée de l'engine retirera."""

    CELL_M = 50.0

    def __init__(self, route: dict[str, Any]):
        xs = [float(v) for v in route.get("x", [])]
        zs = [float(v) for v in route.get("z", [])]
        self.segs: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}
        for i in range(len(xs) - 1):
            seg = (xs[i], zs[i], xs[i + 1], zs[i + 1])
            x0, x1 = sorted((seg[0], seg[2]))
            z0, z1 = sorted((seg[1], seg[3]))
            for ix in range(math.floor(x0 / self.CELL_M), math.floor(x1 / self.CELL_M) + 1):
                for iz in range(math.floor(z0 / self.CELL_M), math.floor(z1 / self.CELL_M) + 1):
                    self.segs.setdefault((ix, iz), []).append(seg)

    def on_road(self, ring: list[list[float]]) -> bool:
        x0, z0, x1, z1 = _bbox(ring)
        m = ROAD_AXIS_CLEAR_M
        seen: set[tuple[float, float, float, float]] = set()
        xs, zs = _densify_ring(ring, 0.5)
        for ix in range(math.floor((x0 - m) / self.CELL_M), math.floor((x1 + m) / self.CELL_M) + 1):
            for iz in range(math.floor((z0 - m) / self.CELL_M), math.floor((z1 + m) / self.CELL_M) + 1):
                for seg in self.segs.get((ix, iz), []):
                    if seg in seen:
                        continue
                    seen.add(seg)
                    if point_in_ring(seg[0], seg[1], ring) or point_in_ring(seg[2], seg[3], ring):
                        return True
                    if float(_seg_dist(xs, zs, *seg).min()) < m:
                        return True
        return False


# ---------------------------------------------------------------------------------------------------------
# Règles
# ---------------------------------------------------------------------------------------------------------

@dataclass
class Decision:
    """Sort d'un bâtiment : gardé tel quel, simplifié (rectangle), coupé en paliers, ou retiré (raison)."""
    kept: list[dict[str, Any]]
    action: str            # "garde", "rectangle", "paliers", "retire"
    reason: str | None = None


def _socle_ok(drop_m: float, k: float) -> bool:
    return drop_m * k <= SOCLE_MAX_M


def decide(b: dict[str, Any], height: HeightFn, water: WaterIndex, k: float = DISPLAY_RELIEF_K) -> Decision:
    """Règles du lot MP1 pour un bâtiment de la couche `buildings` (objet du format §6)."""
    if not is_house(b):
        return Decision([b], "garde")
    outer = b.get("outer") or []
    if len(outer) < 3:
        return Decision([b], "garde")
    if water.touches(outer):
        return Decision([], "retire", REASON_WATER)

    rect = oriented_rect(outer)
    fill = fill_ratio(outer, rect)
    base_y = float(b.get("base_y", 0.0))
    drop = footprint_drop(outer, height, base_y)
    simple = rect is not None and fill >= FILL_MIN and not b.get("holes")

    # 1. Long bâtiment sur une pente : paliers si simple, sinon retiré
    if rect is not None and rect.length > LONG_MIN_M and drop > LONG_DROP_M:
        if not simple:
            return Decision([], "retire", REASON_LONG)
        n = max(2, math.ceil(rect.length / PALIER_M))
        step = rect.length / n
        pieces: list[dict[str, Any]] = []
        for i in range(n):
            ring = rect.corners(-rect.length / 2 + i * step, -rect.length / 2 + (i + 1) * step, rect.width / 2)
            p_base = footprint_base(ring, height, base_y)
            if not _socle_ok(footprint_drop(ring, height, p_base), k):
                return Decision([], "retire", REASON_LONG)
            piece = dict(b)
            piece.update({"id": f"{b['id']}_p{i}", "outer": ring, "holes": [], "base_y": p_base})
            pieces.append(piece)
        return Decision(pieces, "paliers")

    # 2. Maison en L ou compliquée : rectangle de même aire (toit à pans), ou retirée
    action = "garde"
    if rect is not None and (fill < FILL_MIN or b.get("holes")):
        if fill < FILL_DROP:
            return Decision([], "retire", REASON_SHAPE)
        s = math.sqrt(max(fill, 1e-6))
        ring = rect.corners(-rect.length * s / 2, rect.length * s / 2, rect.width * s / 2)
        nb = dict(b)
        nb.update({"outer": ring, "holes": [], "base_y": footprint_base(ring, height, base_y)})
        b, outer, action = nb, ring, "rectangle"
        drop = footprint_drop(outer, height, float(b["base_y"]))

    # 3. Socle visible trop haut
    if not _socle_ok(drop, k):
        return Decision([], "retire", REASON_SOCLE)
    return Decision([b], action)


# ---------------------------------------------------------------------------------------------------------
# Villages et rapport
# ---------------------------------------------------------------------------------------------------------

def _villages(centres: list[tuple[float, float]]) -> list[int]:
    """Groupe de chaque maison (liens simples à moins de VILLAGE_LINK_M), cases de VILLAGE_LINK_M."""
    n = len(centres)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cell = VILLAGE_LINK_M
    grid: dict[tuple[int, int], list[int]] = {}
    for i, (x, z) in enumerate(centres):
        grid.setdefault((math.floor(x / cell), math.floor(z / cell)), []).append(i)
    l2 = VILLAGE_LINK_M * VILLAGE_LINK_M
    for (gx, gz), members in grid.items():
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for j in grid.get((gx + dx, gz + dz), []):
                    for i in members:
                        if i < j:
                            xi, zi = centres[i]
                            xj, zj = centres[j]
                            if (xi - xj) ** 2 + (zi - zj) ** 2 <= l2:
                                ri, rj = find(i), find(j)
                                if ri != rj:
                                    parent[rj] = ri
    return [find(i) for i in range(n)]


@dataclass
class SimplifyReport:
    houses: int = 0
    kept: int = 0
    rectangles: int = 0
    split: int = 0
    split_pieces: int = 0
    removed: dict[str, int] = field(default_factory=lambda: {r: 0 for r in REASONS})
    road_removed: int = 0
    villages: list[dict[str, Any]] = field(default_factory=list)

    @property
    def removed_total(self) -> int:
        return sum(self.removed.values())

    @property
    def alerts(self) -> list[dict[str, Any]]:
        return [v for v in self.villages if v["alerte"]]

    def to_json(self) -> dict[str, Any]:
        return {
            "lot": "MP1",
            "regles": {
                "relief_affiche": DISPLAY_RELIEF_K, "socle_max_m": SOCLE_MAX_M, "long_min_m": LONG_MIN_M,
                "long_denivele_m": LONG_DROP_M, "palier_m": PALIER_M, "remplissage_min": FILL_MIN,
                "remplissage_retire": FILL_DROP, "marge_eau_m": WATER_MARGIN_M,
                "axe_chaussee_m": ROAD_AXIS_CLEAR_M, "village_lien_m": VILLAGE_LINK_M,
                "village_min": VILLAGE_MIN, "village_alerte_part": VILLAGE_ALERT_SHARE,
            },
            "maisons": self.houses,
            "gardees_telles_quelles": self.kept,
            "simplifiees_rectangle": self.rectangles,
            "coupees_en_paliers": self.split,
            "paliers": self.split_pieces,
            "retirees": dict(self.removed),
            "retirees_total": self.removed_total,
            "retirees_par_la_chaussee_engine": self.road_removed,
            "villages": self.villages,
            "villages_en_alerte": len(self.alerts),
        }

    def lines(self) -> list[str]:
        out = [
            f"maisons (MP1) : {self.houses} ; gardées {self.kept}, rectangles {self.rectangles}, "
            f"paliers {self.split} ({self.split_pieces} morceaux), retirées {self.removed_total} "
            f"(socle {self.removed[REASON_SOCLE]}, long {self.removed[REASON_LONG]}, "
            f"forme {self.removed[REASON_SHAPE]}, eau {self.removed[REASON_WATER]}), "
            f"sur la chaussée (engine) {self.road_removed}"
        ]
        for v in self.alerts:
            out.append(f"  ALERTE village {v['id']} ({v['x']:.0f}, {v['z']:.0f}) : {v['retirees']}/{v['maisons']} "
                       f"maisons retirées ({v['part']:.0%}) : revoir les points de passage de la route")
        return out


def simplify_buildings(res: OsmLayersResult, route: dict[str, Any], height: HeightFn, chunk_of: ChunkFn,
                       k: float = DISPLAY_RELIEF_K) -> SimplifyReport:
    """Applique les règles MP1 à `res.buildings_chunks` (en place) et rend le rapport.

    `height` : terrain réel ; `chunk_of` : tronçon d'un centre de bâtiment (les paliers d'un long bâtiment
    peuvent changer de tronçon). Les compteurs du manifeste suivent (`buildings_count`)."""
    water = WaterIndex.from_chunks(res.water_chunks)
    road = RoadAxisIndex(route)
    rep = SimplifyReport()
    new_chunks: dict[int, list[dict[str, Any]]] = {}
    centres: list[tuple[float, float]] = []
    fates: list[str] = []   # "garde", "retire", "route"

    for k_chunk in sorted(res.buildings_chunks):
        for b in res.buildings_chunks[k_chunk]:
            if not is_house(b):
                new_chunks.setdefault(k_chunk, []).append(b)
                continue
            rep.houses += 1
            centres.append(ring_centroid(b["outer"]) if len(b.get("outer") or []) >= 3 else (0.0, 0.0))
            d = decide(b, height, water, k)
            if d.action == "retire":
                rep.removed[d.reason or REASON_SOCLE] += 1
                fates.append("retire")
                continue
            if d.action == "rectangle":
                rep.rectangles += 1
            elif d.action == "paliers":
                rep.split += 1
                rep.split_pieces += len(d.kept)
            else:
                rep.kept += 1
            on_road = False
            for nb in d.kept:
                if road.on_road(nb["outer"]):
                    on_road = True
                cx, cz = ring_centroid(nb["outer"])
                kk = chunk_of(cx, cz) if d.action == "paliers" else k_chunk
                new_chunks.setdefault(k_chunk if kk is None else kk, []).append(nb)
            if on_road:
                rep.road_removed += 1
            fates.append("route" if on_road else "garde")

    groups = _villages(centres)
    by_group: dict[int, list[int]] = {}
    for i, g in enumerate(groups):
        by_group.setdefault(g, []).append(i)
    vid = 0
    for g in sorted(by_group, key=lambda g: min(by_group[g])):
        members = by_group[g]
        if len(members) < VILLAGE_MIN:
            continue
        vid += 1
        gone = sum(1 for i in members if fates[i] != "garde")
        share = gone / len(members)
        rep.villages.append({
            "id": vid,
            "x": round(float(np.mean([centres[i][0] for i in members])), 1),
            "z": round(float(np.mean([centres[i][1] for i in members])), 1),
            "maisons": len(members),
            "retirees": gone,
            "part": round(share, 3),
            "alerte": share > VILLAGE_ALERT_SHARE,
        })

    res.buildings_chunks = {kk: v for kk, v in sorted(new_chunks.items()) if v}
    res.buildings_count = sum(len(v) for v in res.buildings_chunks.values())
    return rep


REPORT_FILE = "rapport_maisons.json"


def simplify_for_compile(res: OsmLayersResult, route: dict[str, Any], frame: Any,
                         near_tiles: dict[tuple[int, int], np.ndarray] | None = None,
                         provider: Any = None) -> SimplifyReport:
    """Entrée du compilateur : terrain des tuiles proches (sinon MNT), tronçons de `nearest_chunk_and_y`."""
    from . import constants as C
    from .osm_layers import RouteAxis, nearest_chunk_and_y, sample_terrain_y

    axis = RouteAxis(route["x"], route["z"], route["alt_m"])

    def height(xs: np.ndarray, zs: np.ndarray) -> np.ndarray:
        xs = np.asarray(xs, dtype=float)
        return sample_terrain_y(xs, np.asarray(zs, dtype=float), frame, near_tiles, provider,
                                np.full(len(xs), np.nan))

    def chunk_of(cx: float, cz: float) -> int | None:
        return nearest_chunk_and_y(cx, cz, route, axis, C.OSM_BAND_M)[0]

    return simplify_buildings(res, route, height, chunk_of)


def write_report(folder: Any, rep: SimplifyReport) -> None:
    """Rapport des exclusions à côté des tronçons de la couche (`buildings/rapport_maisons.json`)."""
    import json
    from pathlib import Path

    p = Path(folder) / REPORT_FILE
    p.write_text(json.dumps(rep.to_json(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
