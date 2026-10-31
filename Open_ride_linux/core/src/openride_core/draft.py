"""Aspiration derrière les bots (lot P3, SRS §5, contrat IPC révision 1.3 : `draft`, `draft_bot`).

Module pur (aucune E/S), en une dimension le long de la route, d'après les mesures en soufflerie
et en simulation numérique de Blocken et coll. (2013 à 2018) :
- courbe exponentielle `α = ALPHA_MAX · exp(−(gap − GAP_MIN_M) / DECAY_M)`, coupée à 0 au-delà de
  `GAP_CUTOFF_M` et devant le bot ; il reste un abri résiduel de quelques pour cent jusqu'à 10 m ;
- effet de file : derrière des bots espacés de moins de `LINE_GAP_M`, l'abri croît avec le rang
  (`LINE_FACTORS`), plafonné à `ALPHA_CAP` (0,45, SRS §5) ;
- vent de travers : l'abri baisse avec l'angle du vent apparent, jusqu'à − 50 % à 45° ;
- poussée vers l'avant : un bot suivi de près gagne `PUSH_FROM_BEHIND` de résistance en moins ;
- le fantôme n'abrite pas (décision du propriétaire du 25 octobre) : seuls les bots `constant` comptent ;
- lot AS1 : les bots s'abritent aussi, derrière les autres bots et derrière le cycliste (`draft_for`,
  `update_bots`), sur les positions du pas précédent pour que l'ordre des bots ne compte pas.

`gap` est l'écart entre la roue arrière du bot et la roue avant du cycliste : la différence de
position `s` moins `BIKE_LENGTH_M`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from typing import Any, NamedTuple

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
WHEEL_GAP_M = 3.0         # lot AS1 : un bot à profil à moins de 3 m derrière un coureur prend sa roue
RIDER_ID = "rider"
SAVED_W_MIN_DRAFT = 0.02  # lot AS5 : watts économisés (`draft_w`) envoyés à partir de cet abri


class Source(NamedTuple):
    """Le cycliste vu comme une source d'abri pour les bots (lot AS1)."""

    s: float
    v: float
    id: str = RIDER_ID
    kind: str = "constant"


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


def draft_for(rider_s: float, sources: Iterable[Any], length_m: float | None = None, is_loop: bool = False,
              rider_v: float = 0.0, head_mps: float = 0.0, cross_mps: float = 0.0, skip: Any = None
              ) -> tuple[float, str | None]:
    """Abri le plus fort devant un coureur à `rider_s` et `id` de la source qui le donne (la plus
    proche de la file). Sert au cycliste comme aux bots (lot AS1).

    `sources` : objets avec `s`, `id` et `kind` (bots de N9, `Source` du cycliste) ; seuls les
    `constant` abritent ; `skip` (le coureur lui-même) est ignoré.
    """
    ahead: list[tuple[float, str]] = []
    for b in sources:
        if b is skip or getattr(b, "kind", "constant") != "constant":
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


def best_draft(rider_s: float, bots: Iterable[Any], length_m: float | None = None, is_loop: bool = False,
               rider_v: float = 0.0, head_mps: float = 0.0, cross_mps: float = 0.0
               ) -> tuple[float, str | None]:
    """Abri du cycliste derrière les bots (lot P3) : `draft_for` avec les bots pour sources."""
    return draft_for(rider_s, bots, length_m, is_loop, rider_v, head_mps, cross_mps)


def wheel_ahead(rider_s: float, sources: Iterable[Any], length_m: float | None = None, is_loop: bool = False,
                skip: Any = None) -> tuple[float, Any] | None:
    """Roue suivie (lot AS1) : écart et source `constant` la plus proche devant, à moins de
    `WHEEL_GAP_M` ; l'écart est négatif quand les deux vélos se chevauchent. None sinon."""
    best: tuple[float, Any] | None = None
    for b in sources:
        if b is skip or getattr(b, "kind", "constant") != "constant":
            continue
        d = ahead_distance(rider_s, b.s, length_m, is_loop)
        if 0.0 < d <= BIKE_LENGTH_M + WHEEL_GAP_M and (best is None or d < best[0]):
            best = (d, b)
    return None if best is None else (best[0] - BIKE_LENGTH_M, best[1])


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


def update_bots(bots: list[Any], rider: Source | None, dt: float, length_m: float | None = None,
                is_loop: bool = False, cross_of: Callable[[Any], float] | None = None) -> None:
    """Abri lissé (`draft`), roue suivie (`wheel` : écart et vitesse) et poussée (`push`) de chaque bot
    `constant` (lot AS1). Sources : les autres bots `constant` et le cycliste ; le fantôme n'en est pas.

    Tout se calcule sur les positions du pas précédent avant que quiconque n'avance : le résultat ne
    dépend pas de l'ordre des bots. `cross_of(bot)` : vent de travers au bot (m/s), 0 sans.
    """
    sources: list[Any] = [b for b in bots if getattr(b, "kind", "constant") == "constant"]
    if rider is not None:
        sources.append(rider)
    for b in sources:
        if b is rider:
            continue
        params = getattr(b, "params", None)
        head = params.wind_mps if params is not None else 0.0
        cross = cross_of(b) if cross_of else 0.0
        target, _ = draft_for(b.s, sources, length_m, is_loop, b.v, head, cross, skip=b)
        b.draft = smooth(getattr(b, "draft", 0.0), target, dt)
        wheel = wheel_ahead(b.s, sources, length_m, is_loop, skip=b)
        b.wheel = None if wheel is None else (wheel[0], wheel[1].v)
        push = 0.0
        if PUSH_ENABLED:
            for f in sources:
                if f is not b:
                    push = max(push, push_bonus(f.s, b.s, length_m, is_loop))
        b.push = push
