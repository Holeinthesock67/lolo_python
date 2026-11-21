"""Garde-fou d'altitude du monde ouvert (21 novembre 2026), appliqué à la génération du profil des arêtes.

Demande du propriétaire : en monde ouvert, protéger la route contre les défauts des sources d'altitude (rampes
brutales, pics, trous, marches), à la génération et avec un contrôle bloquant de la CI.

**Constat** (balade du banc `ea1_lac`, relief Copernicus GLO-30) : le profil de la route passait de 0 à 21 % en 10 m
vers s = 4 880 m, puis redescendait à −17 % : bosse de 7 m sur une arête de 118 m entre deux nœuds à 450,8 m et
454,2 m. Le relief GLO-30 est un modèle de **surface** (toits, arbres) : en ville ou sous les arbres, il ajoute à la
route des bosses que le lissage de Savitzky-Golay (fenêtre de 110 m) ne retire pas, et que la pente bornée à ± 25 %
ne voit pas. Aux nœuds, chaque arête était lissée seule : sa pente au bout ne dépendait que d'elle, d'où des
cassures de pente au passage d'une arête à l'autre.

**Règle** (une seule, pour toutes les arêtes et les boucles de retournement) :

1. *Relief lu* (`repair`) : valeurs absentes ou hors de la Terre (NaN, valeurs de remplissage −9999 ou −32767 sous `ALT_MIN_M`, au-dessus de `ALT_MAX_M`)
   remplacées par l'interpolation des voisines valides ; pics et trous isolés (plus de `SPIKE_M` de la médiane
   glissante sur `SPIKE_WINDOW` points) ramenés à cette médiane.
2. *Profil final* (`guard`, après le lissage et le raccord aux nœuds) : altitudes des deux bouts inchangées (nœuds
   communs à plusieurs arêtes), et sur tout le profil

   - pente d'un pas de 10 m au plus `GRADE_MAX_PCT` (± 25 %, la borne de `constants.GRADE_LIMIT_PCT`) ;
   - **changement de pente** d'un pas au suivant au plus `CURVE_MAX_PCT` (4 % pour 10 m : arrondi vertical de
     250 m de rayon ; ×2,5 au relief de séance, 10 %) : plus de rampe brutale ni de marche. Sur les 4 479 arêtes
     du banc `ea1_lac`, 2 % des pas dépassaient cette borne (le pire : 26 %) ;
   - au bout d'une arête, pente à moins de `CURVE_MAX_PCT / 2` de la **pente du nœud** dans la direction de
     l'arête (`node_grade`, gradient du relief au nœud, mêmes 5 points que son altitude) : deux arêtes qui se
     suivent en ligne droite ont la même pente au nœud, la cassure y reste sous `CURVE_MAX_PCT`.

   Les pentes qui dépassent sont rapprochées deux à deux de juste ce qu'il faut (projections alternées), la somme
   des montées et descentes est gardée (bouts inchangés) : un profil déjà conforme ne bouge pas, un défaut ne
   déplace que les points autour de lui. Un profil impossible à rendre conforme (arête trop courte pour la
   différence d'altitude de ses nœuds) est compté (`left`), jamais faussé aux bouts.

Tout en numpy, sans entrée-sortie ; le contrôle (`check`) sert aux tests de la CI et à
`scripts/controle_profil_altitude.py` sur le PC.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import constants as C

GUARD_VERSION = 1
ALT_MIN_M = -9000.0           # valeur absente de la source (−9999, −32767 du GLO-30), NaN aussi
ALT_MAX_M = 9000.0            # au-dessus de l’Everest : valeur aberrante
SPIKE_M = 8.0
SPIKE_WINDOW = 5
GRADE_MAX_PCT = C.GRADE_LIMIT_PCT
CURVE_MAX_PCT = 4.0           # changement de pente au plus, d'un pas de DS_M au suivant
END_TOL_PCT = CURVE_MAX_PCT / 2.0
CHECK_TOL_PCT = 0.05          # marge du contrôle (arrondi des altitudes au cm)
MAX_ROUNDS = 4000
MARGIN = 0.98                 # bornes visées un peu en deçà des bornes contrôlées : arrêt plus rapide
EPS = 1e-6


@dataclass(frozen=True)
class GuardStats:
    repaired: int = 0          # valeurs absentes ou hors de la Terre remplacées
    spikes: int = 0            # pics et trous isolés ramenés à la médiane
    moved: int = 0             # points du profil déplacés par le garde-fou
    max_shift_m: float = 0.0   # plus grand déplacement
    left: int = 0              # pas encore hors des bornes (profil impossible)

    def merged(self, other: "GuardStats") -> "GuardStats":
        return GuardStats(self.repaired + other.repaired, self.spikes + other.spikes, self.moved + other.moved,
                          max(self.max_shift_m, other.max_shift_m), self.left + other.left)


def repair(alt: np.ndarray) -> tuple[np.ndarray, GuardStats]:
    """Relief lu le long d'une arête : trous de la source comblés, pics et creux isolés ramenés à la médiane."""
    a = np.asarray(alt, dtype=float).copy()
    n = len(a)
    bad = ~np.isfinite(a) | (a < ALT_MIN_M) | (a > ALT_MAX_M)
    repaired = int(bad.sum())
    if repaired:
        good = np.flatnonzero(~bad)
        if not len(good):
            raise ValueError("relief absent sur toute l'arête")
        a[bad] = np.interp(np.flatnonzero(bad), good, a[good])
    spikes = 0
    if n >= SPIKE_WINDOW:
        h = SPIKE_WINDOW // 2
        pad = np.concatenate((np.full(h, a[0]), a, np.full(h, a[-1])))
        win = np.lib.stride_tricks.sliding_window_view(pad, SPIKE_WINDOW)
        med = np.median(win, axis=1)
        spike = np.abs(a - med) > SPIKE_M
        spikes = int(spike.sum())
        a[spike] = med[spike]
    return a, GuardStats(repaired=repaired, spikes=spikes)


def _limits(ds: np.ndarray) -> np.ndarray:
    """Changement de pente permis entre deux pas voisins, proportionnel à leur longueur moyenne (pas court au bout)."""
    return CURVE_MAX_PCT / 100.0 * (ds[:-1] + ds[1:]) / (2.0 * C.DS_M)


def guard(alt: np.ndarray, s: np.ndarray, start_grade_pct: float | None = None,
          end_grade_pct: float | None = None) -> tuple[np.ndarray, GuardStats]:
    """Profil `alt` aux abscisses `s` ramené aux bornes de pente et de changement de pente, bouts inchangés.

    Arête plus raide en moyenne que `GRADE_MAX_PCT` (ruelle, chemin en escalier, falaise du relief) : la pente permise
    y est sa pente moyenne. Bornes impossibles à tenir avec les pentes des nœuds (arête courte) : essai sans elles. Le
    profil rendu est celui des essais qui a le moins de défauts, l'entrée comprise : jamais pire qu'avant.

    `start_grade_pct`, `end_grade_pct` : pente visée au premier et au dernier pas (pente du nœud dans le sens de
    l'arête), à `END_TOL_PCT` près ; None : libre.

    Projections alternées en altitude : chaque contrainte non tenue (changement de pente sur trois points voisins,
    pente sur deux) déplace ses seuls points de juste ce qu'il faut, les bouts ne bougent jamais ; les contraintes
    d'une même classe (indices modulo 3 ou 2) ne se touchent pas et se traitent ensemble. Un défaut ne déplace donc
    que les points autour de lui, de proche en proche, jusqu'à ce que toutes les bornes tiennent."""
    a0 = np.asarray(alt, dtype=float)
    s = np.asarray(s, dtype=float)
    if len(a0) < 3:
        return a0.copy(), GuardStats()
    span = max(float(s[-1] - s[0]), EPS)
    gmax = max(GRADE_MAX_PCT, 100.0 * abs(float(a0[-1] - a0[0])) / span + 0.5)
    best, best_left = a0.copy(), len(check(a0, s, start_grade_pct, end_grade_pct, grade_max_pct=gmax))
    tries = [(start_grade_pct, end_grade_pct)]
    if start_grade_pct is not None or end_grade_pct is not None:
        tries.append((None, None))
    for t0, t1 in tries:
        if not best_left:
            break
        out = _project(a0, s, t0, t1, gmax)
        left = len(check(out, s, start_grade_pct, end_grade_pct, grade_max_pct=gmax))
        if left < best_left:
            best, best_left = out, left
    shift = np.abs(best - a0)
    moved = int((shift > 1e-3).sum())
    return best, GuardStats(moved=moved, max_shift_m=float(shift.max()) if moved else 0.0, left=best_left)


def _project(alt: np.ndarray, s: np.ndarray, start_grade_pct: float | None, end_grade_pct: float | None,
             grade_max_pct: float) -> np.ndarray:
    """Projections alternées en altitude d'un essai de `guard` (voir là)."""
    a0 = alt
    n = len(a0)
    ds = np.maximum(np.diff(s), EPS)
    inv = 1.0 / ds
    free = np.ones(n)
    free[0] = free[-1] = 0.0
    m = MARGIN
    lim = m * _limits(ds)                                     # triple i (1 … n − 2) : points i − 1, i, i + 1
    gmax = m * grade_max_pct / 100.0
    lo = np.full(n - 1, -gmax)                                 # pas i (0 … n − 2) : points i, i + 1
    hi = np.full(n - 1, gmax)
    for k, target in ((0, start_grade_pct), (n - 2, end_grade_pct)):
        if target is not None:
            t = float(np.clip(target / 100.0, -gmax, gmax))
            lo[k], hi[k] = max(lo[k], t - m * END_TOL_PCT / 100.0), min(hi[k], t + m * END_TOL_PCT / 100.0)
    tri = np.arange(1, n - 1)
    tri_classes = [tri[tri % 3 == r] for r in range(3)]
    step = np.arange(n - 1)
    step_classes = [step[step % 2 == r] for r in range(2)]
    # coefficients des contraintes (changement de pente du triple i, pente du pas i)
    c_prev, c_mid, c_next = inv[tri - 1], -(inv[tri - 1] + inv[tri]), inv[tri]

    a = _carry(a0, ds, inv, lo, hi)

    def curve(v: np.ndarray, i: np.ndarray) -> np.ndarray:
        return (v[i + 1] - v[i]) * inv[i] - (v[i] - v[i - 1]) * inv[i - 1]

    def ok(v: np.ndarray) -> bool:
        d = curve(v, tri)
        q = np.diff(v) * inv
        return bool((np.abs(d) <= lim / m + EPS).all() and (q >= lo - EPS * 10).all() and (q <= hi + EPS * 10).all()
                    and (np.abs(q) <= grade_max_pct / 100.0 + EPS).all())

    if not ok(a):
        for it in range(MAX_ROUNDS):
            for cls in tri_classes:
                d = curve(a, cls)
                li = lim[cls - 1]
                e = d - np.clip(d, -li, li)
                k = e != 0.0
                if k.any():
                    i = cls[k]
                    cp, cm, cn = c_prev[i - 1] * free[i - 1], c_mid[i - 1] * free[i], c_next[i - 1] * free[i + 1]
                    norm = cp * cp + cm * cm + cn * cn
                    f = e[k] / np.where(norm > 0, norm, 1.0)
                    a[i - 1] -= f * cp
                    a[i] -= f * cm
                    a[i + 1] -= f * cn
            for cls in step_classes:
                q = (a[cls + 1] - a[cls]) * inv[cls]
                e = q - np.clip(q, lo[cls], hi[cls])
                k = e != 0.0
                if k.any():
                    i = cls[k]
                    c0, c1 = -inv[i] * free[i], inv[i] * free[i + 1]
                    norm = c0 * c0 + c1 * c1
                    f = e[k] / np.where(norm > 0, norm, 1.0)
                    a[i] -= f * c0
                    a[i + 1] -= f * c1
            if it % 8 == 7 and ok(a):
                break
    return a


def _carry(alt: np.ndarray, ds: np.ndarray, inv: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Départ des projections : pentes hors de [lo, hi] ramenées à la borne, la montée en trop reportée sur les pas
    suivants (puis, au bout, sur les précédents) : bouts inchangés, le défaut ne se répand qu'autour de lui."""
    g = np.diff(alt) * inv
    if ((g >= lo) & (g <= hi)).all():
        return alt.copy()
    g = g.tolist()
    lo_l, hi_l, ds_l = lo.tolist(), hi.tolist(), ds.tolist()
    carry = 0.0                       # montée (m) encore à placer ; reste de l'aller repris au retour
    for order in (range(len(g)), range(len(g) - 1, -1, -1)):
        for i in order:
            v = g[i] + carry / ds_l[i]
            c = min(max(v, lo_l[i]), hi_l[i])
            carry = (v - c) * ds_l[i]
            g[i] = c
    out = np.concatenate(([alt[0]], alt[0] + np.cumsum(np.asarray(g) * ds)))
    out[-1] = alt[-1]
    return out


def node_grade(gx: float, gz: float, dx: float, dz: float) -> float:
    """Pente du nœud (%) dans la direction (dx, dz), d'après le gradient du relief (gx, gz) en m/m."""
    n = float(np.hypot(dx, dz))
    if n < EPS:
        return 0.0
    return 100.0 * (gx * dx + gz * dz) / n


def check(alt, s, start_grade_pct: float | None = None, end_grade_pct: float | None = None,
          tol_pct: float = CHECK_TOL_PCT, grade_max_pct: float = GRADE_MAX_PCT) -> list[tuple[float, str, float]]:
    """Défauts d'un profil : liste de (s, nature, valeur en %), nature « trou », « pente », « cassure » ou « bout ».
    `grade_max_pct` : pente permise (celle de l'arête si elle est plus raide en moyenne)."""
    a = np.asarray(alt, dtype=float)
    s = np.asarray(s, dtype=float)
    out: list[tuple[float, str, float]] = []
    if len(a) < 2:
        return out
    if not np.isfinite(a).all():
        return [(float(s[int(np.flatnonzero(~np.isfinite(a))[0])]), "trou", float("nan"))]
    ds = np.maximum(np.diff(s), EPS)
    g = 100.0 * np.diff(a) / ds
    for i in np.flatnonzero(np.abs(g) > grade_max_pct + tol_pct):
        out.append((float(s[i]), "pente", float(g[i])))
    if len(g) >= 2:
        d = np.diff(g)
        lim = 100.0 * _limits(ds)
        for i in np.flatnonzero(np.abs(d) > lim + tol_pct):
            out.append((float(s[i + 1]), "cassure", float(d[i])))
    for t, gi, si in ((start_grade_pct, g[0], s[0]), (end_grade_pct, g[-1], s[-1])):
        if t is None:
            continue
        t = float(np.clip(t, -grade_max_pct, grade_max_pct))
        if abs(gi - t) > END_TOL_PCT + tol_pct:
            out.append((float(si), "bout", float(gi - t)))
    return out
