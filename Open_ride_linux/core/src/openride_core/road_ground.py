"""Règle unique du sol contre la route (21 novembre 2026), version du core pour le terrain synthétique.

Jumelle, en bibliothèque standard, de `openride_compiler/road_ground.py` (même règle, mêmes constantes, mêmes résultats
au float près : `compiler/tests/test_road_ground.py` les compare) : la route de référence est celle que l'engine dessine
(`route.Route.sample`, Catmull-Rom centripète, cap interpolé) ; le sol du maillage proche (triangles de
`terrain_tiles.gd`) est au moins `ROAD_SINK_M` sous la chaussée et ses bas-côtés, et au plus `FOOT_GAP_M` sous la route
au pied des talus de `road_builder.gd` (talus enterré même au relief ×3). Une passe pour l'appui, puis une pour la
chaussée, qui a le dernier mot. Voir le module du compilateur pour le constat et la règle complète.
"""

from __future__ import annotations

import math

from .route import Route

ROAD_HALF_WIDTH_M = 3.0
ROAD_SINK_M = 0.05
SHOULDER_WIDTH_M = 0.5
SHOULDER_DROP_M = 0.05
SKIRT_DROP_M = 2.5
SKIRT_OUT_M = 1.5
EDGE_M = ROAD_HALF_WIDTH_M + SHOULDER_WIDTH_M
FOOT_OFFSET_M = EDGE_M + SKIRT_OUT_M
FOOT_DROP_M = SHOULDER_DROP_M + SKIRT_DROP_M
RELIEF_MAX = 3.0
FOOT_GAP_M = FOOT_DROP_M / RELIEF_MAX
ALONG_STEP_M = 1.0
ACROSS_STEP_M = 0.5
TILE_SAMPLES = 101


def corridor(route: dict, sink: float = ROAD_SINK_M) -> tuple[list, list]:
    """(points de chaussée (x, z, limite haute), pieds de talus (x, z, limite basse)) de la route de l'engine : un
    point tous les `ALONG_STEP_M` mètres environ (segment par segment), coupe perpendiculaire au cap."""
    r = Route(route)
    n_off = round(2 * EDGE_M / ACROSS_STEP_M)
    offs = [-EDGE_M + k * ACROSS_STEP_M for k in range(n_off + 1)]
    upper, lower = [], []
    for i in range(r.n - 1):
        s0, s1 = r.s[i], r.s[i + 1]
        seg = math.hypot(r.x[i + 1] - r.x[i], r.z[i + 1] - r.z[i])
        count = max(math.ceil(seg / ALONG_STEP_M), 1)
        last = i == r.n - 2
        for k in range(count + (1 if last else 0)):
            smp = r.sample(s0 + (s1 - s0) * k / count)
            h = math.radians(smp.heading_deg)
            rx, rz = math.cos(h), math.sin(h)
            upper.extend((smp.x + rx * o, smp.z + rz * o, smp.y - sink) for o in offs)
            lower.extend((smp.x + rx * o, smp.z + rz * o, smp.y - FOOT_GAP_M) for o in (-FOOT_OFFSET_M, FOOT_OFFSET_M))
    return upper, lower


def _corners(px: float, pz: float, cell: float):
    ax, az = px / cell, pz / cell
    gi, gj = math.floor(ax), math.floor(az)
    u, v = ax - gi, az - gj
    if u + v <= 1.0:
        return ((gi, gj, 1.0 - u - v), (gi + 1, gj, u), (gi, gj + 1, v))
    return ((gi + 1, gj + 1, u + v - 1.0), (gi, gj + 1, 1.0 - u), (gi + 1, gj, 1.0 - v))


def fit_tiles(tiles: dict[tuple[int, int], list[float]], cell: float, upper: list, lower: list) -> dict:
    """Règle sur place les tuiles (listes de `TILE_SAMPLES`² valeurs, ligne = z) : appui des talus, puis chaussée.
    Rend {"lowered", "raised", "left_low"}."""
    cells = TILE_SAMPLES - 1

    def copies(gi: int, gj: int):
        ti, tj = gi // cells, gj // cells
        li, lj = gi - ti * cells, gj - tj * cells
        out = [(ti, tj, li, lj)]
        if li == 0:
            out.append((ti - 1, tj, cells, lj))
        if lj == 0:
            out.append((ti, tj - 1, li, cells))
        if li == 0 and lj == 0:
            out.append((ti - 1, tj - 1, cells, cells))
        return out

    def get(gi: int, gj: int) -> float | None:
        for ti, tj, li, lj in copies(gi, gj):
            g = tiles.get((ti, tj))
            if g is not None:
                return g[lj * TILE_SAMPLES + li]
        return None

    v: dict[tuple[int, int], float] = {}
    pts = []
    for kind, points in (("up", upper), ("lo", lower)):
        for px, pz, lim in points:
            cs = _corners(px, pz, cell)
            vals = [get(gi, gj) for gi, gj, _ in cs]
            if any(x is None or not math.isfinite(x) for x in vals):
                continue
            for (gi, gj, _), x in zip(cs, vals):
                v[(gi, gj)] = x
            pts.append((kind, [(gi, gj) for gi, gj, _ in cs], [w for _, _, w in cs], lim))
    v0 = dict(v)

    def one_pass(kind: str) -> None:
        cand: dict[tuple[int, int], float] = {}
        for k, ks, ws, lim in pts:
            if k != kind:
                continue
            vk = [v[c] for c in ks]
            h = sum(w * x for w, x in zip(ws, vk))
            if kind == "up":
                if h <= lim + 1e-4:
                    continue
                tgt = lim - 1e-3
                over = sum(w * (x - tgt) for w, x in zip(ws, vk) if x > lim and w > 0)
                alpha = min((h - tgt) / over, 1.0) if over > 0 else 1.0
                for c, w, x in zip(ks, ws, vk):
                    if x > lim and w > 0:
                        y = x - alpha * (x - tgt)
                        cand[c] = min(cand.get(c, y), y)
            else:
                if h >= lim - 1e-4:
                    continue
                tgt = lim + 1e-3
                under = sum(w * (tgt - x) for w, x in zip(ws, vk) if x < lim and w > 0)
                alpha = min((tgt - h) / under, 1.0) if under > 0 else 1.0
                for c, w, x in zip(ks, ws, vk):
                    if x < lim and w > 0:
                        y = x + alpha * (tgt - x)
                        cand[c] = max(cand.get(c, y), y)
        for c, y in cand.items():
            v[c] = min(v[c], y) if kind == "up" else max(v[c], y)

    one_pass("lo")
    one_pass("up")
    lowered = raised = 0
    for c, y in v.items():
        if y == v0[c]:
            continue
        lowered += y < v0[c]
        raised += y > v0[c]
        for ti, tj, li, lj in copies(*c):
            g = tiles.get((ti, tj))
            if g is not None:
                g[lj * TILE_SAMPLES + li] = y
    left_low = 0
    for k, ks, ws, lim in pts:
        if k == "lo" and sum(w * v[c] for c, w in zip(ks, ws)) < lim - 1e-3:
            left_low += 1
    return {"lowered": lowered, "raised": raised, "left_low": left_low}
