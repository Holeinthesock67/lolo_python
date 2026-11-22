"""Règle unique du sol contre la route (21 novembre 2026), version du core pour le terrain synthétique.

Jumelle, en bibliothèque standard, de `openride_compiler/road_ground.py` (même règle, mêmes constantes, mêmes résultats
au float près : `compiler/tests/test_road_ground.py` les compare) : la route de référence est celle que l'engine dessine
(`route.Route.sample`, Catmull-Rom centripète, cap interpolé) ; le sol du maillage proche (triangles de
`terrain_tiles.gd`) est au moins `ROAD_SINK_M` sous la chaussée et ses bas-côtés, et au plus `FOOT_GAP_M` sous la route
au pied des talus de `road_builder.gd` (talus enterré même au relief ×3). Points en défaut projetés sur leur borne
(Kaczmarz), `TILE_ROUNDS` fois une passe pour l'appui puis une pour la chaussée, qui a le dernier mot. Voir le module
du compilateur pour le constat et la règle complète.
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
TILE_ROUNDS = 6
PROJECT_STEPS = 4


FOOT_COVER_M = SKIRT_OUT_M + 0.5
SAME_PART_M = 25.0


def corridor(route: dict, sink: float = ROAD_SINK_M) -> tuple[list, list]:
    """(points de chaussée (x, z, limite haute), pieds de talus (x, z, limite basse)) de la route de l'engine : un
    point tous les `ALONG_STEP_M` mètres environ (segment par segment), coupe perpendiculaire au cap ; pieds de talus
    qui tombent sur la chaussée d'une autre partie de la route, ou tout près, retirés (`drop_covered_feet`)."""
    upper, lower, us, ls = corridor_s(route, sink)
    return upper, drop_covered_feet(upper, lower, us, ls)


def drop_covered_feet(upper: list, lower: list, upper_s: list, lower_s: list) -> list:
    """Comme le compilateur : pied de talus retiré s'il tombe sur une chaussée (à moins de 1,5 fois `ACROSS_STEP_M`
    d'un de ses points), ou à moins de `FOOT_COVER_M` de celle d'une autre partie de la route (abscisses à plus de
    `SAME_PART_M`)."""
    cell = FOOT_COVER_M
    grid: dict[tuple[int, int], list[int]] = {}
    for n, (x, z, _) in enumerate(upper):
        grid.setdefault((math.floor(x / cell), math.floor(z / cell)), []).append(n)
    near_on = ACROSS_STEP_M * 1.5
    last = len(upper_s) - 1
    edge = [n == 0 or n == last or upper_s[n] != upper_s[n - 1] or upper_s[n] != upper_s[n + 1]
            for n in range(len(upper_s))]      # bords des coupes seuls pour l'autre partie (comme le compilateur)
    sub, pos = [], 0
    for n in range(len(upper_s)):              # un point sur deux de chaque coupe, et ses bords (comme le compilateur)
        pos = 0 if n == 0 or upper_s[n] != upper_s[n - 1] else pos + 1
        sub.append(edge[n] or pos % 2 == 0)
    out = []
    for (fx, fz, fl), fs in zip(lower, lower_s):
        gi, gj = math.floor(fx / cell), math.floor(fz / cell)
        covered = False
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for n in grid.get((gi + di, gj + dj), ()):
                    ux, uz, _ = upper[n]
                    d2 = (ux - fx) ** 2 + (uz - fz) ** 2
                    if (sub[n] and d2 < near_on * near_on) or (edge[n] and d2 <= cell * cell and abs(upper_s[n] - fs) > SAME_PART_M):
                        covered = True
                        break
                if covered:
                    break
            if covered:
                break
        if not covered:
            out.append((fx, fz, fl))
    return out


def corridor_s(route: dict, sink: float = ROAD_SINK_M) -> tuple[list, list, list, list]:
    """`corridor` avant le retrait des pieds couverts, avec l'abscisse de chaque point."""
    r = Route(route)
    n_off = round(2 * EDGE_M / ACROSS_STEP_M)
    offs = [-EDGE_M + k * ACROSS_STEP_M for k in range(n_off + 1)]
    upper, lower, us, ls = [], [], [], []
    for i in range(r.n - 1):
        s0, s1 = r.s[i], r.s[i + 1]
        seg = math.hypot(r.x[i + 1] - r.x[i], r.z[i + 1] - r.z[i])
        count = max(math.ceil(seg / ALONG_STEP_M), 1)
        last = i == r.n - 2
        for k in range(count + (1 if last else 0)):
            sk = s0 + (s1 - s0) * k / count
            smp = r.sample(sk)
            h = math.radians(smp.heading_deg)
            rx, rz = math.cos(h), math.sin(h)
            upper.extend((smp.x + rx * o, smp.z + rz * o, smp.y - sink) for o in offs)
            lower.extend((smp.x + rx * o, smp.z + rz * o, smp.y - FOOT_GAP_M) for o in (-FOOT_OFFSET_M, FOOT_OFFSET_M))
            us.extend([sk] * len(offs))
            ls.extend([sk, sk])
    return upper, lower, us, ls


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
            pts.append((kind, [(gi, gj) for gi, gj, _ in cs], [w for _, _, w in cs], lim,
                        [math.hypot(px - gi * cell, pz - gj * cell) for gi, gj, _ in cs]))
    v0 = dict(v)

    def one_pass(kind: str) -> None:
        """Comme le compilateur : d'abord les seuls sommets en défaut sur leur propre borne (celle du point le plus
        proche d'eux), sans la franchir, puis le reste sur tous les sommets du triangle."""
        cand: dict[tuple[int, int], float] = {}
        sign = 1.0 if kind == "up" else -1.0
        near: dict[tuple[int, int], tuple[float, float]] = {}
        for k, ks, ws, lim, ds in pts:
            if k != kind:
                continue
            for c, d in zip(ks, ds):
                if c not in near or d < near[c][0]:
                    near[c] = (d, lim)
        for k, ks, ws, lim, ds in pts:
            if k != kind:
                continue
            vk = [v[c] for c in ks]
            h = sum(w * x for w, x in zip(ws, vk))
            if sign * (h - lim) <= -1e-4:
                continue
            tgt = lim - sign * 1e-3
            stop = [near[c][1] - sign * 1e-3 for c in ks]
            for _ in range(PROJECT_STEPS):
                rest = sum(w * x for w, x in zip(ws, vk)) - tgt
                wrong = [w if w > 0 and sign * (x - s) > 0 else 0.0 for w, x, s in zip(ws, vk, stop)]
                n1 = sum(w * w for w in wrong)
                if sign * rest <= 0 or n1 <= 0:
                    break
                vk = [x - sign * min(sign * rest / n1 * w, sign * (x - s)) if w > 0 else x
                      for w, x, s in zip(wrong, vk, stop)]
            rest = sum(w * x for w, x in zip(ws, vk)) - tgt
            n2 = sum(w * w for w in ws)
            for c, w, x in zip(ks, ws, vk):
                if w <= 0:
                    continue
                y = x - (rest / n2 * w if sign * rest > 0 and n2 > 0 else 0.0)
                old = cand.get(c)
                cand[c] = y if old is None else (min(old, y) if kind == "up" else max(old, y))
        for c, y in cand.items():
            v[c] = min(v[c], y) if kind == "up" else max(v[c], y)

    for _ in range(TILE_ROUNDS):
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
    for k, ks, ws, lim, _ in pts:
        if k == "lo" and sum(w * v[c] for c, w in zip(ks, ws)) < lim - 1e-3:
            left_low += 1
    return {"lowered": lowered, "raised": raised, "left_low": left_low}
