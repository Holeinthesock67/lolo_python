"""Aspiration derrière les bots (lot P3, SRS §5, contrat IPC révision 1.3 : `draft`, `draft_bot`).

Module pur (aucune E/S), en une dimension le long de la route, d'après les mesures en soufflerie
et en simulation numérique de Blocken et coll. (2013 à 2018) :
- courbe exponentielle `α = ALPHA_MAX · exp(−(gap − GAP_MIN_M) / DECAY_M)`, coupée à 0 au-delà de
  `GAP_CUTOFF_M` et devant le bot ; il reste un abri résiduel de quelques pour cent jusqu'à 10 m ;
- effet de file : derrière des bots espacés de moins de `LINE_GAP_M`, l'abri croît avec le rang
  (`LINE_FACTORS`), plafonné à `ALPHA_CAP` (0,45, SRS §5) ;
- vent de travers : l'abri baisse avec l'angle du vent apparent, jusqu'à − 50 % à 45° ;
- poussée vers l'avant : un bot suivi de près gagne `PUSH_FROM_BEHIND` de résistance en moins ;
- le fantôme n'abrite pas (décision du propriétaire du 25 octobre) : seuls les bots `constant` comptent.

`gap` est l'écart entre la roue arrière du bot et la roue avant du cycliste : la différence de
position `s` moins `BIKE_LENGTH_M`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

ALPHA_MAX = 0.40          # roue dans la roue
ALPHA_CAP = 0.45          # plafond de la SRS §5, file comprise
GAP_MIN_M = 0.3
DECAY_M = 4.0
GAP_CUTOFF_M = 15.0
BIKE_LENGTH_M = 1.7       # d'un axe à l'autre plus les demi-roues : écart s entre deux vélos collés
LINE_GAP_M = 3.0          # écart maximal entre deux bots d'une même file
LINE_FACTORS = (1.00, 1.12, 1.18)   # derrière un, deux, trois bots ou plus
CROSSWIND_FULL_DEG = 45.0
CROSSWIND_MAX_LOSS = 0.5
PUSH_FROM_BEHIND = 0.025  # résistance aérodynamique en moins pour un bot suivi à moins de 1 m
PUSH_GAP_M = 1.0
PUSH_ENABLED = True       # poussée vers l'avant (facultative) : False la coupe
SMOOTH_TAU_S = 1.0        # lissage de l'abri ressenti
SMOOTH_MIN_RATE = 0.1     # vitesse minimale de la fin du lissage (par seconde)


def draft_coefficient(gap_m: float) -> float:
    """Abri derrière un seul bot à l'écart `gap_m` (m) ; 0 devant le bot et au-delà de 15 m."""
    if gap_m < 0.0 or gap_m > GAP_CUTOFF_M:
        return 0.0
    return ALPHA_MAX * math.exp(-max(gap_m - GAP_MIN_M, 0.0) / DECAY_M)


def crosswind_factor(rider_v: float, head_mps: float, cross_mps: float) -> float:
    """Part de l'abri gardée selon l'angle du vent apparent : 1 sans vent de travers, 0,5 à 45° et plus."""
    along = rider_v + head_mps
    if cross_mps == 0.0:
        return 1.0
    yaw = math.degrees(math.atan2(abs(cross_mps), max(along, 1e-6)))
    return 1.0 - CROSSWIND_MAX_LOSS * min(yaw / CROSSWIND_FULL_DEG, 1.0)


def ahead_distance(rider_s: float, bot_s: float, length_m: float | None, is_loop: bool) -> float:
    """Distance du bot devant le cycliste le long de la route (négative derrière) ; boucle comprise."""
    d = bot_s - rider_s
    if is_loop and length_m:
        d %= length_m
        if d > length_m / 2.0:
            d -= length_m
    return d


def best_draft(rider_s: float, bots: Iterable[Any], length_m: float | None = None, is_loop: bool = False,
               rider_v: float = 0.0, head_mps: float = 0.0, cross_mps: float = 0.0
               ) -> tuple[float, str | None]:
    """Abri le plus fort devant le cycliste et `id` du bot qui le donne (le plus proche de la file).

    `bots` : objets avec `s`, `id` et `kind` (bots de N9) ; seuls les bots `constant` abritent.
    """
    ahead: list[tuple[float, str]] = []
    for b in bots:
        if getattr(b, "kind", "constant") != "constant":
            continue
        d = ahead_distance(rider_s, b.s, length_m, is_loop)
        if 0.0 < d <= GAP_CUTOFF_M + BIKE_LENGTH_M + LINE_GAP_M * 3:
            ahead.append((d, b.id))
    if not ahead:
        return 0.0, None
    ahead.sort()
    best, best_id = 0.0, None
    for i, (d, bot_id) in enumerate(ahead):
        base = draft_coefficient(d - BIKE_LENGTH_M)
        if base <= 0.0:
            continue
        # File : bots suivants espacés de moins de LINE_GAP_M devant celui-ci
        rank, prev = 1, d
        for d2, _ in ahead[i + 1:]:
            if d2 - prev - BIKE_LENGTH_M > LINE_GAP_M:
                break
            rank, prev = rank + 1, d2
        alpha = min(base * LINE_FACTORS[min(rank, len(LINE_FACTORS)) - 1], ALPHA_CAP)
        if alpha > best:
            best, best_id = alpha, bot_id
    if best_id is None:
        return 0.0, None
    return best * crosswind_factor(rider_v, head_mps, cross_mps), best_id


def push_bonus(rider_s: float, bot_s: float, length_m: float | None = None, is_loop: bool = False) -> float:
    """Résistance aérodynamique en moins pour un bot suivi de près par le cycliste (0 sinon)."""
    d = ahead_distance(rider_s, bot_s, length_m, is_loop) - BIKE_LENGTH_M
    return PUSH_FROM_BEHIND if 0.0 <= d < PUSH_GAP_M else 0.0


def smooth(current: float, target: float, dt: float, tau_s: float = SMOOTH_TAU_S) -> float:
    """Premier ordre de constante de temps `tau_s` : pas d'à-coup en entrant ou en sortant de la roue.

    La fin de l'approche se fait à `SMOOTH_MIN_RATE` au moins, pour atteindre vraiment la cible
    (0,40 vers 0 en 2,4 s) au lieu de s'en approcher sans fin.
    """
    diff = target - current
    step = max(abs(diff) * (1.0 - math.exp(-dt / tau_s)), SMOOTH_MIN_RATE * dt)
    return target if step >= abs(diff) else current + math.copysign(step, diff)
