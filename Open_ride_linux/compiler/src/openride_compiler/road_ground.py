"""Règle unique du sol contre la route (21 novembre 2026), appliquée à la génération.

Demande du propriétaire : « résoudre tous ces problèmes de sol et niveau en amont, dès la génération », pour les
parcours compilés, les carrés du monde ouvert et les démonstrations, sans exception ni correctif local.

**Cause commune** des défauts trouvés au banc (sol au-dessus de la chaussée, route qui lévite sans talus) : le
générateur ne traçait pas la même route que l'engine. Il dégageait le sol le long des segments droits entre les
points de la route (tous les 10 m), à l'altitude interpolée en ligne droite. L'engine dessine, lui, une spline de
Catmull-Rom centripète passant par ces points (`route_data.gd`, `core/route.py`), coupe perpendiculaire au cap
interpolé. Au banc du lac d'Annecy, l'écart va jusqu'à 1,23 m de côté dans les virages et 0,20 m en hauteur dans
les creux : la chaussée affichée sortait de la bande dégagée.

**Règle** : la route de référence est celle que l'engine dessine (`road_curve`, portage exact de
`route.py` : mêmes points fantômes, même cap). Sur cette route, le relief du maillage (triangles de
`terrain_tiles.gd` `mesh_height_at`, diagonale de (i + 1, j) à (i, j + 1)) respecte deux bornes :

1. **Chaussée et bas-côtés** (à moins de `ROAD_HALF_WIDTH_M + SHOULDER_WIDTH_M` de l'axe, hors tunnels) : sol au moins
   `ROAD_SINK_M` sous la chaussée (le bas-côté descend de `SHOULDER_DROP_M` = `ROAD_SINK_M` jusqu'au sol). Les
   sommets au-dessus descendent en proportion de leur dépassement, jamais sous la limite (règle bornée de #936).
2. **Appui des talus** (pied du talus de l'engine, `FOOT_OFFSET_M` de l'axe, route posée au sol : hors ponts et
   tunnels) : sol au plus `FOOT_DROP_M / RELIEF_MAX` sous la route, si bien que le talus de `road_builder.gd`
   (2,5 m de haut) touche le sol même au relief le plus exagéré de l'engine (×3) : plus de route qui lévite. Les
   sommets trop bas remontent de même (remblai).

Une passe pour chaque borne, l'appui d'abord, la chaussée ensuite : la première borne a le dernier mot (jamais de
sol sur la route) ; chaque passe ne lit que les triangles qui touchent un sommet, si bien que la valeur finale d'un
sommet ne dépend que du relief à deux cases de lui (les carrés du monde ouvert se calculent avec trois cases de plus
tout autour : bords communs identiques). Un pied de talus encore trop bas (conflit des deux bornes dans une même
case, épingle serrée) est compté (`left_low`). Les sommets sont repérés par leurs indices dans une grille globale
(`step` mètres depuis l'origine du repère) : deux tuiles voisines reçoivent la même valeur sur leur bord commun.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

from . import constants as C

# Coupe de la route dessinée par l'engine (road_builder.gd).
SHOULDER_WIDTH_M = 0.5
SHOULDER_DROP_M = 0.05
SKIRT_DROP_M = 2.5
SKIRT_OUT_M = 1.5
EDGE_M = C.ROAD_HALF_WIDTH_M + SHOULDER_WIDTH_M            # bord extérieur du bas-côté
FOOT_OFFSET_M = EDGE_M + SKIRT_OUT_M                       # pied du talus
FOOT_DROP_M = SHOULDER_DROP_M + SKIRT_DROP_M               # hauteur du talus sous la chaussée
RELIEF_MAX = 3.0                                           # exagération du relief la plus forte (--visual-grade)
FOOT_GAP_M = FOOT_DROP_M / RELIEF_MAX                      # sol au plus ceci sous la route au pied du talus
ALONG_STEP_M = 1.0
ROUNDS = 1                 # une passe d'appui puis une de chaussée (bords communs : voir plus haut)
ACROSS_STEP_M = 0.5
KNOT_EPS_M = 1e-6


def road_curve(x, z, alt, heading_deg, loop: bool = False, step: float = ALONG_STEP_M):
    """Route telle que l'engine la dessine : points (cx, cy, cz) tous les `step` mètres environ sur la spline de
    Catmull-Rom centripète (points fantômes aux extrémités, indices circulaires en boucle), et direction « à
    droite » (rx, rz) de la coupe, d'après le cap interpolé par l'écart le plus court (`route.py` `sample`).
    Rend aussi l'indice du segment et la fraction u de chaque point."""
    p = np.column_stack((np.asarray(x, float), np.asarray(alt, float), np.asarray(z, float)))
    head = np.asarray(heading_deg, float)
    n = len(p)
    if n < 2:
        e = np.empty(0)
        return e, e, e, e, e, e.astype(int), e
    seg = np.linalg.norm(p[1:, [0, 2]] - p[:-1, [0, 2]], axis=1)
    counts = np.maximum(np.ceil(seg / step).astype(int), 1)
    i = np.repeat(np.arange(n - 1), counts)
    first = np.repeat(np.cumsum(counts) - counts, counts)
    u = (np.arange(len(i)) - first) / np.repeat(counts, counts)
    i = np.append(i, n - 2)
    u = np.append(u, 1.0)

    def point(k: np.ndarray) -> np.ndarray:
        if loop:
            return p[k % (n - 1)]
        out = p[np.clip(k, 0, n - 1)].copy()
        lo, hi = k < 0, k > n - 1
        out[lo] = 2 * p[0] - p[1]
        out[hi] = 2 * p[n - 1] - p[n - 2]
        return out

    p0, p1, p2, p3 = point(i - 1), point(i), point(i + 1), point(i + 2)

    def knot(a, b):
        return np.sqrt(np.maximum(np.linalg.norm(b - a, axis=1), KNOT_EPS_M))

    t0 = np.zeros(len(i))
    t1 = t0 + knot(p0, p1)
    t2 = t1 + knot(p1, p2)
    t3 = t2 + knot(p2, p3)
    t = (t1 + u * (t2 - t1))[:, None]

    def lerp(a, b, ta, tb):
        ta, tb = ta[:, None], tb[:, None]
        return (tb - t) / (tb - ta) * a + (t - ta) / (tb - ta) * b

    a1, a2, a3 = lerp(p0, p1, t0, t1), lerp(p1, p2, t1, t2), lerp(p2, p3, t2, t3)
    b1, b2 = lerp(a1, a2, t0, t2), lerp(a2, a3, t1, t3)
    c = lerp(b1, b2, t1, t2)
    h0, h1 = head[i], head[np.minimum(i + 1, n - 1)]
    d = (h1 - h0) % 360.0
    d = np.where(d > 180.0, d - 360.0, d)
    h = np.radians((h0 + u * d) % 360.0)
    # Cap horaire depuis le nord (−z) : droite = (cos h, sin h), comme road_builder.gd.
    return c[:, 0], c[:, 1], c[:, 2], np.cos(h), np.sin(h), i, u


def corridor(x, z, alt, heading_deg, s=None, open_spans: Iterable = (), ground_spans: Iterable = (),
             loop: bool = False, half_width: float = C.ROAD_HALF_WIDTH_M, sink: float = C.ROAD_SINK_M):
    """Points de contrôle d'une route : (x, z, limite haute) de la chaussée et des bas-côtés, (x, z, limite basse) des
    pieds de talus. `s` : abscisses des points (défaut : longueurs cumulées) ; `open_spans` : portions (s0, s1) **hors**
    de la chaussée à ciel ouvert (tunnels) ; `ground_spans` : portions où la route ne repose pas sur le sol (ponts,
    tunnels : pas de pied de talus). `half_width` : demi-largeur de la chaussée, au moins celle de l'engine."""
    x, z = np.asarray(x, float), np.asarray(z, float)
    if s is None:
        s = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(x), np.diff(z)))))
    s = np.asarray(s, float)
    cx, cy, cz, rx, rz, i, u = road_curve(x, z, alt, heading_deg, loop)
    if not len(cx):
        e = np.empty(0)
        return (e, e, e), (e, e, e)
    sv = s[i] + u * (s[np.minimum(i + 1, len(s) - 1)] - s[i])

    def outside(spans) -> np.ndarray:
        keep = np.ones(len(sv), dtype=bool)
        for sp in spans:
            keep &= ~((sv >= float(sp[0])) & (sv <= float(sp[1])))
        return keep

    hw = max(float(half_width), C.ROAD_HALF_WIDTH_M)
    edge = hw + SHOULDER_WIDTH_M
    offs = np.arange(-edge, edge + 1e-9, ACROSS_STEP_M)
    drop = np.full(len(offs), sink)
    up = outside(open_spans)
    ux = (cx[up, None] + rx[up, None] * offs[None, :]).ravel()
    uz = (cz[up, None] + rz[up, None] * offs[None, :]).ravel()
    ul = (cy[up, None] - drop[None, :]).ravel()
    on = up & outside(ground_spans)
    foot = edge + SKIRT_OUT_M
    fo = np.array([-foot, foot])
    fx = (cx[on, None] + rx[on, None] * fo[None, :]).ravel()
    fz = (cz[on, None] + rz[on, None] * fo[None, :]).ravel()
    fl = np.repeat(cy[on] - FOOT_GAP_M, 2)
    return (ux, uz, ul), (fx, fz, fl)


def _corners(px, pz, step):
    """Sommets globaux (gi, gj) des trois coins du triangle qui contient chaque point, et leurs poids."""
    ax, az = px / step, pz / step
    gi, gj = np.floor(ax), np.floor(az)
    fu, fv = ax - gi, az - gj
    gi, gj = gi.astype(np.int64), gj.astype(np.int64)
    low = fu + fv <= 1.0
    ci = np.where(low[:, None], np.stack([gi, gi + 1, gi], 1), np.stack([gi + 1, gi, gi + 1], 1))
    cj = np.where(low[:, None], np.stack([gj, gj, gj + 1], 1), np.stack([gj + 1, gj + 1, gj], 1))
    w = np.where(low[:, None], np.stack([1 - fu - fv, fu, fv], 1), np.stack([fu + fv - 1, 1 - fu, 1 - fv], 1))
    return ci, cj, w


def heights(gather, step: float, px, pz) -> np.ndarray:
    """Sol du maillage (triangles de l'engine) aux points (px, pz) ; NaN là où un coin manque."""
    px, pz = np.asarray(px, float), np.asarray(pz, float)
    if not len(px):
        return np.empty(0)
    ci, cj, w = _corners(px, pz, step)
    v = np.asarray(gather(ci.ravel(), cj.ravel()), dtype=float).reshape(ci.shape)
    return (w * v).sum(1)


def fit(gather, scatter, step: float, upper, lower) -> dict:
    """Règle les sommets du maillage (grille globale de pas `step`) aux deux bornes.

    `gather(gi, gj)` rend la hauteur des sommets (NaN si absents), `scatter(gi, gj, y)` écrit ceux qui changent.
    `upper` = (x, z, limite) : sol au plus à la limite ; `lower` = (x, z, plancher) : sol au moins au plancher.
    Rend {"lowered", "raised", "left_low"} (sommets abaissés, remontés, points de pied encore trop bas)."""
    ux, uz, ul = (np.asarray(a, float) for a in upper)
    lx, lz, ll = (np.asarray(a, float) for a in lower)
    px, pz = np.concatenate((ux, lx)), np.concatenate((uz, lz))
    if not len(px):
        return {"lowered": 0, "raised": 0, "left_low": 0}
    ci, cj, w = _corners(px, pz, step)
    i_min, j_min = int(ci.min()), int(cj.min())
    span = int(cj.max()) - j_min + 1
    code = (ci.ravel() - i_min) * span + (cj.ravel() - j_min)   # un entier par sommet : np.unique rapide
    ucode, inv = np.unique(code, return_inverse=True)
    inv = inv.reshape(ci.shape)
    uniq = np.stack([ucode // span + i_min, ucode % span + j_min], 1)
    v0 = np.asarray(gather(uniq[:, 0], uniq[:, 1]), dtype=float)
    ok = np.isfinite(v0[inv]).all(axis=1)
    nu = len(ux)
    up_sel = np.flatnonzero(ok[:nu])
    lo_sel = nu + np.flatnonzero(ok[nu:])
    lim = np.concatenate((ul, ll))
    v = v0.copy()

    def lower_pass(sel):
        if not len(sel):
            return
        k, wk = inv[sel], w[sel]
        h = (wk * v[k]).sum(1)
        bad = h > lim[sel] + 1e-4
        if not bad.any():
            return
        k, wk, h, top = k[bad], wk[bad], h[bad], lim[sel][bad]
        tgt = top - 1e-3
        vk = v[k]
        above = (vk > top[:, None]) & (wk > 0)
        over = np.where(above, wk * (vk - tgt[:, None]), 0.0).sum(1)
        alpha = np.where(over > 0, np.minimum((h - tgt) / np.where(over > 0, over, 1.0), 1.0), 1.0)
        cand = vk - alpha[:, None] * (vk - tgt[:, None])
        np.minimum.at(v, k[above], cand[above])

    def raise_pass(sel):
        if not len(sel):
            return
        k, wk = inv[sel], w[sel]
        h = (wk * v[k]).sum(1)
        bad = h < lim[sel] - 1e-4
        if not bad.any():
            return
        k, wk, h, bot = k[bad], wk[bad], h[bad], lim[sel][bad]
        tgt = bot + 1e-3
        vk = v[k]
        below = (vk < bot[:, None]) & (wk > 0)
        under = np.where(below, wk * (tgt[:, None] - vk), 0.0).sum(1)
        alpha = np.where(under > 0, np.minimum((tgt - h) / np.where(under > 0, under, 1.0), 1.0), 1.0)
        cand = vk + alpha[:, None] * (tgt[:, None] - vk)
        np.maximum.at(v, k[below], cand[below])

    for _ in range(ROUNDS):
        raise_pass(lo_sel)        # talus appuyés (remblai)
        lower_pass(up_sel)        # puis la chaussée, qui a le dernier mot : jamais de sol sur la route
    changed = np.isfinite(v0) & (v != v0)
    if changed.any():
        scatter(uniq[changed, 0], uniq[changed, 1], v[changed])
    left_low = 0
    if len(lo_sel):
        h = (w[lo_sel] * v[inv[lo_sel]]).sum(1)
        left_low = int((h < lim[lo_sel] - 1e-3).sum())
    return {"lowered": int((changed & (v < v0)).sum()), "raised": int((changed & (v > v0)).sum()), "left_low": left_low}


def fit_grid(y: np.ndarray, x0: float, z0: float, step: float, upper, lower) -> dict:
    """`fit` sur une grille seule (lignes = z, colonnes = x, sommet (0, 0) en (x0, z0), multiples de `step`)."""
    i0, j0 = int(round(x0 / step)), int(round(z0 / step))
    rows, cols = y.shape

    def gather(gi, gj):
        li, lj = gi - i0, gj - j0
        out = np.full(len(gi), np.nan)
        ok = (li >= 0) & (li < cols) & (lj >= 0) & (lj < rows)
        out[ok] = y[lj[ok], li[ok]]
        return out

    def scatter(gi, gj, val):
        y[gj - j0, gi - i0] = val

    return fit(gather, scatter, step, upper, lower)


def tiles_access(tiles: dict[tuple[int, int], np.ndarray], tile_m: float):
    """(gather, scatter, step) de tuiles de `C.TILE_SAMPLES` sommets de côté (bord commun en double : les deux copies
    reçoivent la même valeur)."""
    cells = C.TILE_SAMPLES - 1
    step = tile_m / cells

    def copies(gi, gj):
        """(tuile, li, lj) de chaque copie possible d'un sommet : sa tuile, et celles d'avant sur un bord."""
        ti, tj = gi // cells, gj // cells
        li, lj = gi - ti * cells, gj - tj * cells
        bi, bj = li == 0, lj == 0
        return [(ti, tj, li, lj),
                (np.where(bi, ti - 1, ti), tj, np.where(bi, cells, li), lj),
                (ti, np.where(bj, tj - 1, tj), li, np.where(bj, cells, lj)),
                (np.where(bi, ti - 1, ti), np.where(bj, tj - 1, tj), np.where(bi, cells, li), np.where(bj, cells, lj))]

    def gather(gi, gj):
        out = np.full(len(gi), np.nan)
        for ti, tj, li, lj in copies(gi, gj):
            for key in set(zip(ti.tolist(), tj.tolist())):
                g = tiles.get(key)
                if g is None:
                    continue
                sel = np.flatnonzero((ti == key[0]) & (tj == key[1]) & np.isnan(out))
                out[sel] = g[lj[sel], li[sel]]
        return out

    def scatter(gi, gj, val):
        for ti, tj, li, lj in copies(gi, gj):
            for key in set(zip(ti.tolist(), tj.tolist())):
                g = tiles.get(key)
                if g is None:
                    continue
                sel = np.flatnonzero((ti == key[0]) & (tj == key[1]))
                g[lj[sel], li[sel]] = val[sel].astype(g.dtype)

    return gather, scatter, step


def fit_tiles(tiles: dict[tuple[int, int], np.ndarray], tile_m: float, upper, lower) -> dict:
    """`fit` sur des tuiles (`tiles_access`)."""
    gather, scatter, step = tiles_access(tiles, tile_m)
    return fit(gather, scatter, step, upper, lower)
