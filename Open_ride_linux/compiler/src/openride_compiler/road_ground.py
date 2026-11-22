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
   `ROAD_SINK_M` sous la chaussée (le bas-côté descend de `SHOULDER_DROP_M` = `ROAD_SINK_M` jusqu'au sol).
2. **Appui des talus** (pied du talus de l'engine, `FOOT_OFFSET_M` de l'axe, route posée au sol : hors ponts et
   tunnels) : sol au plus `FOOT_DROP_M / RELIEF_MAX` sous la route, si bien que le talus de `road_builder.gd`
   (2,5 m de haut) touche le sol même au relief le plus exagéré de l'engine (×3) : plus de route qui lévite.

Chaque point en défaut est projeté sur sa borne (Kaczmarz, 21/11 soir) : le sommet qui pèse le plus dans son triangle
bouge le plus, un sommet éloigné de la route presque pas (la première version bougeait tous les sommets du même
facteur et ne tenait pas les deux bornes en pente raide : 10 m de maille, route à 15 % en dévers). Une paire de passes,
l'appui d'abord, la chaussée ensuite : la première borne a le dernier mot (jamais de sol sur la route). Une tuile
entière se règle en `TILE_ROUNDS` paires (conflits des deux bornes résolus) ; les carrés du monde ouvert en une
seule, si bien que la valeur finale d'un sommet ne dépend que du relief à deux cases de lui (trois cases de plus tout
autour : bords communs identiques), la balade les reprenant ensuite sur sa route (`worldgen/session_ground.py`). Un
pied de talus encore trop bas (épingle plus serrée que la maille) est compté (`left_low`). Les sommets sont repérés par leurs indices dans une grille globale
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
ROUNDS = 1                 # une passe d'appui puis une de chaussée (carrés : bords communs, voir plus haut)
TILE_ROUNDS = 6            # tuile entière : parcours compilés, démonstrations, balade du monde ouvert
PROJECT_STEPS = 4
PROJECT_GAIN = 3.0           # pas d'un sommet au plus ceci fois le reste du point (règle bornée)
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
    """Voir `corridor_s` (sans les abscisses des points)."""
    (ux, uz, ul, _), (fx, fz, fl, _) = corridor_s(x, z, alt, heading_deg, s, open_spans, ground_spans, loop,
                                                  half_width, sink)
    return (ux, uz, ul), (fx, fz, fl)


def corridor_s(x, z, alt, heading_deg, s=None, open_spans: Iterable = (), ground_spans: Iterable = (),
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
        return (e, e, e, e), (e, e, e, e)
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
    us = np.repeat(sv[up], len(offs))
    fs = np.repeat(sv[on], 2)
    return (ux, uz, ul, us), (fx, fz, fl, fs)


FOOT_COVER_M = SKIRT_OUT_M + 0.5   # pied de talus à moins de ceci de la chaussée d'une autre partie de la route
SAME_PART_M = 25.0                 # même partie de la route : abscisses à moins de ceci


def drop_covered_feet(upper, lower, upper_key=None, lower_key=None):
    """Pieds de talus retirés là où ils tombent sur une autre chaussée, ou tout près (la même route qui repasse, une
    boucle de demi-tour, une autre route au carrefour, dans le coin entre deux routes) : le talus y rejoint cette
    chaussée, il n'a pas d'appui à demander, et sa borne contredirait celle de la chaussée voisine (sol au plus 5 cm
    sous la route). `upper_key` / `lower_key` : abscisse de chaque point le long de sa route (une route différente :
    décalée de 1e7 m) ; sans elles, seuls les pieds sur une chaussée (à moins de `ACROSS_STEP_M`) sont retirés."""
    from scipy.spatial import cKDTree
    ux, uz = (np.asarray(a, float) for a in upper[:2])
    fx, fz, fl = (np.asarray(a, float) for a in lower[:3])
    if not len(ux) or not len(fx):
        return fx, fz, fl
    edge = sub = None
    if upper_key is not None and lower_key is not None:
        # Coupes repérées par leur abscisse (répétée sur la coupe) : bords (premier et dernier point) et un point sur
        # deux, soit une grille de 1 m sur 1 m dont tout point de la chaussée est à moins de 0,71 m (carrés denses :
        # 580 000 points de chaussée, deux fois moins d'arbre à construire)
        uk, fk = np.asarray(upper_key, float), np.asarray(lower_key, float)
        first = np.ones(len(uk), bool)
        first[1:] = uk[1:] != uk[:-1]
        last = np.ones(len(uk), bool)
        last[:-1] = first[1:]
        start = np.flatnonzero(first)
        pos = np.arange(len(uk)) - start[np.cumsum(first) - 1]
        edge = np.flatnonzero(first | last)
        sub = np.flatnonzero(first | last | (pos % 2 == 0))
    pts = np.c_[ux, uz] if sub is None else np.c_[ux[sub], uz[sub]]
    tree = cKDTree(pts, balanced_tree=False, compact_nodes=False)     # construction plus rapide
    keep = ~np.isfinite(tree.query(np.c_[fx, fz], distance_upper_bound=ACROSS_STEP_M * 1.5, workers=-1)[0])
    if edge is not None:
        cand = np.flatnonzero(keep)
        # autre partie : bords des chaussées seuls, un pied hors d'une chaussée est plus près de son bord que de son
        # milieu (un pied dessus est retiré ci-dessus)
        if len(cand):    # paires (pied, bord de chaussée) à moins de FOOT_COVER_M, sans boucle Python
            pairs = cKDTree(np.c_[fx[cand], fz[cand]]).sparse_distance_matrix(
                cKDTree(np.c_[ux[edge], uz[edge]]), FOOT_COVER_M, output_type="ndarray")
            fi, uj = cand[pairs["i"]], edge[pairs["j"]]
            keep[fi[np.abs(uk[uj] - fk[fi]) > SAME_PART_M]] = False
    return fx[keep], fz[keep], fl[keep]


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


def fit(gather, scatter, step: float, upper, lower, fixed=None, rounds: int = ROUNDS) -> dict:
    """Règle les sommets du maillage (grille globale de pas `step`) aux deux bornes.

    `gather(gi, gj)` rend la hauteur des sommets (NaN si absents), `scatter(gi, gj, y)` écrit ceux qui changent ;
    `fixed(gi, gj)` (facultatif) : sommets à ne pas bouger (bord d'une tuile déjà affichée), les autres sommets des
    triangles concernés compensent ; `rounds` : paires de passes (appui puis chaussée), une par défaut (valeur d'un
    sommet qui ne dépend que du relief à deux cases : carrés du monde ouvert), davantage pour une tuile entière.
    `upper` = (x, z, limite) : sol au plus à la limite ; `lower` = (x, z, plancher) : sol au moins au plancher.
    Rend {"lowered", "raised", "left_low"} (sommets abaissés, remontés, points de pied encore trop bas)."""
    ux, uz, ul = (np.asarray(a, float) for a in upper)
    lx, lz, ll = (np.asarray(a, float) for a in lower)
    px, pz = np.concatenate((ux, lx)), np.concatenate((uz, lz))
    if not len(px):
        return {"lowered": 0, "raised": 0, "left_low": 0, "over": 0, "over_max_m": 0.0, "short": 0, "short_max_m": 0.0}
    ci, cj, w = _corners(px, pz, step)
    i_min, j_min = int(ci.min()), int(cj.min())
    span = int(cj.max()) - j_min + 1
    code = (ci.ravel() - i_min) * span + (cj.ravel() - j_min)   # un entier par sommet
    size = (int(ci.max()) - i_min + 1) * span
    if size <= 1 << 24:          # emprise petite (carré, tuiles) : table directe, sans tri
        seen = np.zeros(size, bool)
        seen[code] = True
        ucode = np.flatnonzero(seen)
        look = np.empty(size, np.int64)
        look[ucode] = np.arange(len(ucode))
        inv = look[code].reshape(ci.shape)
    else:
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
    free = ~np.asarray(fixed(uniq[:, 0], uniq[:, 1]), bool) if fixed is not None else np.ones(len(v0), bool)

    # distance de chaque point à chacun des trois coins de son triangle : la borne propre d'un sommet est celle du
    # point le plus proche (ci-dessous)
    dc = np.hypot(px[:, None] - ci * step, pz[:, None] - cj * step)

    def own_bound(sel) -> np.ndarray:
        """Borne propre de chaque sommet : celle du point de `sel` le plus proche de lui (NaN sans point)."""
        k, d = inv[sel], dc[sel]
        dmin = np.full(len(v), np.inf)
        np.minimum.at(dmin, k.ravel(), d.ravel())
        hit = d <= dmin[k]
        first = np.full(len(v), len(sel))                    # à égalité, le premier point (comme le core)
        np.minimum.at(first, k[hit], np.broadcast_to(np.arange(len(sel))[:, None], k.shape)[hit])
        out = np.full(len(v), np.nan)
        got = first < len(sel)
        out[got] = lim[sel][first[got]]
        return out

    def project(sel, sign: float, own: np.ndarray) -> bool:
        """Chaque point en défaut ramené sur sa borne (`sign` = +1 : sol au plus la limite, −1 : sol au moins le
        plancher), projection de Kaczmarz : les sommets bougent en proportion de leur poids, le sommet qui pèse le plus
        bouge le plus, un sommet éloigné de la route presque pas ; sommet tiré par plusieurs points : la valeur la plus
        exigeante. D'abord les seuls sommets en défaut sur leur propre borne (celle du point le plus proche d'eux),
        sans la franchir, `PROJECT_STEPS` fois : le sommet de la chaussée ne remonte pas pour un pied de talus voisin,
        et dans une pente le sommet amont, au-dessus de la borne d'un point aval sans être en défaut, ne prend pas le
        reste (21/11 : chaussée creusée de 30 cm dans une pente de 22 %). S'il manque encore (sommet figé, ou routes
        voisines d'altitudes incompatibles), le reste se répartit sur tous les sommets libres du triangle."""
        if not len(sel):
            return False
        k, wk = inv[sel], w[sel]
        h = (wk * v[k]).sum(1)
        bad = sign * (h - lim[sel]) > -1e-4
        if not bad.any():
            return False
        k, wk, h, b = k[bad], wk[bad], h[bad], lim[sel][bad]
        tgt = b - sign * 1e-3                                # 1 mm au-delà de la borne
        vk = v[k].copy()
        wa = wk * free[k]
        stop = np.where(np.isfinite(own[k]), own[k] - sign * 1e-3, tgt[:, None])   # jamais au-delà de sa borne
        for _ in range(PROJECT_STEPS):
            rest = (wk * vk).sum(1) - tgt
            wrong = wa * (sign * (vk - stop) > 0)
            n1 = (wrong * wrong).sum(1)
            go = (sign * rest > 0) & (n1 > 0)
            if not go.any():
                break
            d1 = np.where(go, rest / np.where(n1 > 0, n1, 1.0), 0.0)[:, None] * wrong
            d1 = sign * np.minimum(sign * d1, sign * (vk - stop))
            vk -= np.where(wrong > 0, d1, 0.0)
        rest = (wk * vk).sum(1) - tgt                        # reste : tous les sommets libres
        n2 = (wa * wa).sum(1)
        need = (sign * rest > 0) & (n2 > 0)
        cand = vk - np.where(need, rest / np.where(n2 > 0, n2, 1.0), 0.0)[:, None] * wa
        m = wa > 0
        (np.minimum if sign > 0 else np.maximum).at(v, k[m], cand[m])
        return True

    own_lo, own_up = own_bound(lo_sel), own_bound(up_sel)     # bornes propres des sommets, une fois
    for _ in range(rounds):
        moved = project(lo_sel, -1.0, own_lo)       # talus appuyés (remblai)
        moved |= project(up_sel, 1.0, own_up)       # puis la chaussée, qui a le dernier mot : jamais de sol sur la route
        if not moved:                               # tout tient déjà : tours suivants inutiles
            break
    changed = np.isfinite(v0) & (v != v0)
    if changed.any():
        scatter(uniq[changed, 0], uniq[changed, 1], v[changed])
    left_low = 0
    if len(lo_sel):
        h = (w[lo_sel] * v[inv[lo_sel]]).sum(1)
        left_low = int((h < lim[lo_sel] - 1e-3).sum())
    out = {"lowered": int((changed & (v < v0)).sum()), "raised": int((changed & (v > v0)).sum()), "left_low": left_low}
    # contrôle (comme `residual`, sans relire le maillage) sur tous les points, coins figés compris : ce que
    # `controle_sol_route` compte sur les tuiles écrites (22/11 : le journal taisait les points d'un bord figé)
    for name, sel, sign in (("over", up_sel, 1.0), ("short", lo_sel, -1.0)):
        gap = sign * ((w[sel] * v[inv[sel]]).sum(1) - lim[sel]) if len(sel) else np.empty(0)
        out[name] = int((gap > 2e-3).sum())
        out[f"{name}_max_m"] = round(float(gap.max()), 3) if len(gap) else 0.0
    return out


def residual(gather, step: float, upper, lower, tol: float = 2e-3) -> dict:
    """Contrôle de la règle : points de chaussée où le sol dépasse sa limite, pieds de talus sans appui (au-delà de
    `tol`), et leur plus grand écart (m) ; points sans sol (hors des tuiles) ignorés."""
    out = {}
    for name, pts, sign in (("over", upper, 1.0), ("short", lower, -1.0)):
        px, pz, lim = (np.asarray(a, float) for a in pts)
        h = heights(gather, step, px, pz) if len(px) else np.empty(0)
        gap = sign * (h - lim)
        gap = gap[np.isfinite(gap)]
        out[name] = int((gap > tol).sum())
        out[f"{name}_max_m"] = round(float(gap.max()), 3) if len(gap) else 0.0
    return out


def fit_grid(y: np.ndarray, x0: float, z0: float, step: float, upper, lower, rounds: int = ROUNDS) -> dict:
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

    return fit(gather, scatter, step, upper, lower, rounds=rounds)


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

    def groups(idx, ti, tj):
        """(tuile, indices de `idx`) des sommets `idx` groupés par tuile (tri, sans un masque par tuile)."""
        if not len(idx):
            return
        a, b = ti[idx], tj[idx]
        order = np.lexsort((b, a))
        a, b, idx = a[order], b[order], idx[order]
        cut = np.flatnonzero((np.diff(a) != 0) | (np.diff(b) != 0)) + 1
        for part in np.split(np.arange(len(idx)), cut):
            yield (int(a[part[0]]), int(b[part[0]])), idx[part]

    def gather(gi, gj):
        out = np.full(len(gi), np.nan)
        for ti, tj, li, lj in copies(gi, gj):
            for key, sel in groups(np.flatnonzero(np.isnan(out)), ti, tj):
                g = tiles.get(key)
                if g is not None:
                    out[sel] = g[lj[sel], li[sel]]
        return out

    def scatter(gi, gj, val):
        for ti, tj, li, lj in copies(gi, gj):
            for key, sel in groups(np.arange(len(gi)), ti, tj):
                g = tiles.get(key)
                if g is not None:
                    g[lj[sel], li[sel]] = val[sel].astype(g.dtype)

    return gather, scatter, step


def fit_tiles(tiles: dict[tuple[int, int], np.ndarray], tile_m: float, upper, lower) -> dict:
    """`fit` sur des tuiles entières (`tiles_access`), en `TILE_ROUNDS` paires de passes."""
    gather, scatter, step = tiles_access(tiles, tile_m)
    return fit(gather, scatter, step, upper, lower, rounds=TILE_ROUNDS)
