"""Aspiration derrière les bots (lot P3, SRS §5, contrat IPC révision 1.3 : `draft`, `draft_bot`).

Module pur (aucune E/S), en une dimension le long de la route, d'après les mesures en soufflerie
et en simulation numérique de Blocken et coll. (2013 à 2018) :
- courbe exponentielle `α = ALPHA_MAX · exp(−(gap − GAP_MIN_M) / DECAY_M)`, coupée à 0 au-delà de
  `GAP_CUTOFF_M` et devant le bot ; il reste un abri résiduel de quelques pour cent jusqu'à 10 m ;
- abri de groupe (lot AS4, remplace l'effet de file de P3) : chaque coureur devant à moins de 15 m et à
  moins de `GROUP_SIDE_M` sur le côté donne un abri `α_i` ; l'abri total vaut `1 − Π(1 − k_i·α_i)`, `k_i`
  = 1 pour la source la plus forte, `K_GROUP` pour les autres, `K_LINE` pour une source cachée derrière
  un coureur plus proche sur sa ligne ; plafonné à `ALPHA_GROUP_CAP` (0,55, décision du propriétaire du
  29 octobre ; jusqu'à 90 % au cœur d'un grand peloton chez Blocken et coll., 2018) ;
- vent de travers : l'abri baisse avec l'angle du vent apparent, jusqu'à − 50 % à 45° ;
- poussée vers l'avant : un bot suivi de près gagne `PUSH_FROM_BEHIND` de résistance en moins ;
- le fantôme n'abrite pas (décision du propriétaire du 25 octobre) : seuls les bots `constant` comptent ;
- lot AS1 : les bots s'abritent aussi, derrière les autres bots et derrière le cycliste (`draft_for`,
  `update_bots`), sur les positions du pas précédent pour que l'ordre des bots ne compte pas ;
- lot AS2 : deux dimensions. Chaque coureur a un écart à l'axe de la route (`Lane.m`, positif à droite) ;
  l'abri est multiplié par `lateral_factor(dx)`, `dx` étant l'écart latéral entre les deux coureurs.
  La courbe en cloche (1 jusqu'à 0,3 m, 0,5 vers 0,6 m, 0 au-delà de 1,0 m) reprend l'ordre de grandeur
  des mesures en soufflerie de coureurs décalés latéralement (Barry et coll., 2015, Sports Engineering ;
  Blocken et coll., 2018, J. Wind Eng. Ind. Aerodyn., peloton) : l'abri tombe de moitié quand la roue
  avant ne recouvre plus qu'à moitié le sillage, et disparaît à un guidon d'écart. Le placement
  automatique (`update_lanes`) range chaque coureur dans la roue du coureur devant et l'en sort pour
  doubler ; deux coureurs qui se chevauchent gardent au moins `SIDE_CLEAR_M` d'écart latéral.

`gap` est l'écart entre la roue arrière du bot et la roue avant du cycliste : la différence de
position `s` moins `BIKE_LENGTH_M`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, NamedTuple

ALPHA_MAX = 0.40          # roue dans la roue
GAP_MIN_M = 0.3
DECAY_M = 4.0
GAP_CUTOFF_M = 15.0
BIKE_LENGTH_M = 1.7       # d'un axe à l'autre plus les demi-roues : écart s entre deux vélos collés
CROSSWIND_FULL_DEG = 45.0
CROSSWIND_MAX_LOSS = 0.5
PUSH_FROM_BEHIND = 0.025  # résistance aérodynamique en moins pour un bot suivi à moins de 1 m
PUSH_GAP_M = 1.0
PUSH_ENABLED = True       # poussée vers l'avant (facultative) : False la coupe
SMOOTH_TAU_S = 1.0        # lissage de l'abri ressenti
SMOOTH_MIN_RATE = 0.1     # vitesse minimale de la fin du lissage (par seconde)
WHEEL_GAP_M = 3.0         # lot AS1 : un bot à profil à moins de 3 m derrière un coureur prend sa roue
RIDER_ID = "rider"

# Lot AS4 : abri dans un groupe (constantes à recaler sur les mesures publiées)
ALPHA_GROUP_CAP = 0.55    # plafond au cœur d'un groupe (SRS §5)
GROUP_SIDE_M = 1.5        # au-delà de 1,5 m sur le côté, une source ne compte pas
K_GROUP = 0.6             # part de l'abri d'une source après la plus forte, sur une autre ligne
K_LINE = 0.3              # même chose cachée derrière un coureur plus proche : file de P3 à ±0,02 (1,12, 1,18)
FLANK_ALPHA = 0.05        # coureur côte à côte (roues qui se chevauchent) : un peu d'abri de flanc
CDA_REF_M2 = 0.32         # CdA de référence (PhysicsParams.cda_m2 par défaut)
SIZE_MIN, SIZE_MAX = 0.85, 1.15   # gabarit : abri × (CdA_source / CdA_réf)^0,5, borné

# Lot AS2 : position sur la route, écart à l'axe positif à droite (constantes de voie de road_builder.gd, lot P32)
LATERAL_FULL_M = 0.3      # abri entier jusqu'à 0,3 m d'écart latéral
LATERAL_HALF_M = 0.6      # moitié de l'abri vers 0,6 m
LATERAL_CUTOFF_M = 1.0    # plus d'abri au-delà de 1,0 m
RIDER_LANE_M = 1.2        # place du cycliste sans placement (RoadBuilder.RIDER_LATERAL_M)
BOT_LANE_M = 2.1          # place des bots seuls (RoadBuilder.BOT_LATERAL_M), 0,9 m à droite du cycliste
LANE_MIN_M = 0.3          # hors dépassement, jamais plus près de l'axe (circulation à droite)
LANE_MAX_M = 2.6          # bord de la voie de droite (chaussée de 6 m, 0,4 m du bord)
PASS_LANE_MIN_M = -1.5    # dépassement : jamais plus loin dans la voie d'en face
LANE_RATE_MPS = 0.8       # vitesse latérale maximale
LANE_ACCEL_MPS2 = 1.6     # accélération latérale maximale : pas d'à-coup
LANE_TAU_S = 0.6          # approche de la cible
FOLLOW_LOOK_M = 15.0      # placement dans la roue d'un coureur à moins de 15 m devant
FOLLOW_SPEED_TOL_MPS = 0.5   # « même vitesse » : pas plus de 0,5 m/s plus vite que soi
PASS_SPEED_MPS = 0.5      # dépassement : plus de 0,5 m/s plus vite...
PASS_GAP_M = 3.0          # ... à moins de 3 m de sa roue
PASS_TOUCH_GAP_M = 0.2    # roue contre roue en se rapprochant, quel que soit l'écart de vitesse : on se décale
PASS_OFFSET_M = 1.0       # on double à 1,0 m à gauche du coureur doublé
SIDE_CLEAR_M = 0.9        # deux coureurs qui se chevauchent : au moins 0,9 m d'écart latéral
SIDE_LOOK_S = 1.0         # on se décale dès qu'on toucherait la roue (devant ou derrière) dans 1 s
START_ROW_M = BIKE_LENGTH_M + 1.0   # grille de départ : un rang de deux bots tous les 2,7 m derrière le cycliste
RIDER_WIDTH_M = 0.6       # largeur d'un coureur (2 × RIDER_HALF_WIDTH_M de traffic_model.gd) : contact en dessous


@dataclass
class Lane:
    """Écart à l'axe d'un coureur (lot AS2) : position `m`, vitesse latérale `rate`, place `home` sans
    roue à prendre ; `auto` faux : le coureur garde `home` (placement coupé) et les autres l'évitent ;
    `rank` départage deux coureurs à la même place (départ groupé) : le plus grand passe à gauche."""

    m: float
    home: float
    auto: bool = True
    rank: int = 0
    rate: float = 0.0
    target: float = 0.0
    passing: bool = False

    def __post_init__(self) -> None:
        self.target = self.m


class Source(NamedTuple):
    """Le cycliste vu comme une source d'abri pour les bots (lot AS1) ; `lane_m` : son écart à l'axe (AS2)."""

    s: float
    v: float
    id: str = RIDER_ID
    kind: str = "constant"
    lane_m: float | None = None
    cda_m2: float | None = None


def lane_of(runner: Any) -> float | None:
    """Écart à l'axe d'un coureur (`lane_m` ou `lane.m`) ; None s'il n'en a pas (aligné sur tous)."""
    m = getattr(runner, "lane_m", None)
    if m is None:
        lane = getattr(runner, "lane", None)
        m = lane.m if lane is not None else None
    return m


def lateral_factor(dx_m: float) -> float:
    """Part de l'abri gardée à l'écart latéral `dx_m` (m) entre deux coureurs (lot AS2) : 1 jusqu'à
    `LATERAL_FULL_M`, environ 0,5 à `LATERAL_HALF_M`, 0 à `LATERAL_CUTOFF_M` et au-delà ; décroissante
    et continue (cloche gaussienne recalée pour s'annuler à `LATERAL_CUTOFF_M`)."""
    dx = abs(dx_m)
    if dx <= LATERAL_FULL_M:
        return 1.0
    if dx >= LATERAL_CUTOFF_M:
        return 0.0
    return (math.exp(-_BELL_K * (dx - LATERAL_FULL_M) ** 2) - _BELL_FLOOR) / (1.0 - _BELL_FLOOR)


_BELL_K = math.log(2.0) / (LATERAL_HALF_M - LATERAL_FULL_M) ** 2   # cloche de lateral_factor, calculée une fois
_BELL_FLOOR = math.exp(-_BELL_K * (LATERAL_CUTOFF_M - LATERAL_FULL_M) ** 2)


def size_factor(source: Any) -> float:
    """Gabarit d'une source (lot AS4) : `(CdA / CDA_REF_M2)^0,5` borné à [`SIZE_MIN`, `SIZE_MAX`]. CdA :
    `cda_m2` (le cycliste) ou celui de sa physique sans la poussée du pas précédent (bots) ; 1 sans CdA."""
    cda = getattr(source, "cda_m2", None)
    if cda is None:
        params = getattr(source, "params", None)
        if params is None:
            return 1.0
        cda = params.cda_m2 / (1.0 - getattr(source, "push", 0.0))
    return min(max(math.sqrt(max(cda, 0.0) / CDA_REF_M2), SIZE_MIN), SIZE_MAX)


def _shelters(sources: Iterable[Any]) -> list[tuple[float, Any, float | None, float]]:
    """Sources qui abritent (bots `constant`, cycliste) : (s, objet, écart à l'axe, gabarit)."""
    return [(b.s, b, lane_of(b), size_factor(b)) for b in sources if getattr(b, "kind", "constant") == "constant"]


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


def _group_draft(rider_s: float, lane_m: float | None, shelters: list[tuple[float, Any, float | None, float]],
                 length_m: float | None, is_loop: bool, skip: Any = None) -> tuple[float, str | None]:
    """Abri de groupe (lot AS4) avant vent de travers, et `id` de la source la plus forte."""
    found: list[tuple[float, float, float | None, str]] = []   # (α_i, distance devant, écart à l'axe, id)
    for s, b, b_lane, size in shelters:
        if b is skip:
            continue
        d = ahead_distance(rider_s, s, length_m, is_loop)
        if d <= 0.0 or d > GAP_CUTOFF_M + BIKE_LENGTH_M + 1.0:   # au-delà, draft_coefficient vaut 0
            continue
        dx = None if lane_m is None or b_lane is None else abs(lane_m - b_lane)
        if dx is not None and dx > GROUP_SIDE_M:
            continue
        if d >= BIKE_LENGTH_M:
            alpha = draft_coefficient(d - BIKE_LENGTH_M) * (1.0 if dx is None else lateral_factor(dx))
        else:   # roues qui se chevauchent : flanc seulement, et seulement côte à côte (en une dimension, rien)
            alpha = FLANK_ALPHA if dx is not None else 0.0
        if alpha > 0.0:
            found.append((alpha * size, d, b_lane, b.id))
    if not found:
        return 0.0, None
    top = max(found, key=lambda f: (f[0], -f[1]))
    keep = 1.0 - top[0]
    for f in found:
        if f is top:
            continue
        hidden = 0.0   # caché derrière un coureur plus proche sur sa ligne : K_LINE au lieu de K_GROUP
        for g in found:
            if g[1] < f[1]:
                hidden = max(hidden, 1.0 if g[2] is None or f[2] is None else lateral_factor(f[2] - g[2]))
                if hidden >= 1.0:
                    break
        keep *= 1.0 - (K_GROUP - (K_GROUP - K_LINE) * hidden) * f[0]
    return min(1.0 - keep, ALPHA_GROUP_CAP), top[3]


def draft_for(rider_s: float, sources: Iterable[Any], length_m: float | None = None, is_loop: bool = False,
              rider_v: float = 0.0, head_mps: float = 0.0, cross_mps: float = 0.0, skip: Any = None,
              lane_m: float | None = None) -> tuple[float, str | None]:
    """Abri d'un coureur à `rider_s` dans le groupe devant lui et `id` de la source la plus forte. Sert au
    cycliste comme aux bots (lot AS1).

    `sources` : objets avec `s`, `id` et `kind` (bots de N9, `Source` du cycliste) ; seuls les
    `constant` abritent ; `skip` (le coureur lui-même) est ignoré. `lane_m` : écart à l'axe du
    coureur (lot AS2) ; l'abri de chaque source est multiplié par `lateral_factor` de l'écart latéral.
    Lot AS4 : abri de toutes les sources devant et sur les côtés, combinées (`_group_draft`).
    """
    alpha, best_id = _group_draft(rider_s, lane_m, _shelters(sources), length_m, is_loop, skip)
    if best_id is None:
        return 0.0, None
    return alpha * crosswind_factor(rider_v, head_mps, cross_mps), best_id


def best_draft(rider_s: float, bots: Iterable[Any], length_m: float | None = None, is_loop: bool = False,
               rider_v: float = 0.0, head_mps: float = 0.0, cross_mps: float = 0.0, lane_m: float | None = None
               ) -> tuple[float, str | None]:
    """Abri du cycliste derrière les bots (lot P3) : `draft_for` avec les bots pour sources."""
    return draft_for(rider_s, bots, length_m, is_loop, rider_v, head_mps, cross_mps, lane_m=lane_m)


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


def push_bonus(rider_s: float, bot_s: float, length_m: float | None = None, is_loop: bool = False,
               dx_m: float = 0.0) -> float:
    """Résistance aérodynamique en moins pour un bot suivi de près par le cycliste (0 sinon) ; `dx_m` :
    écart latéral entre les deux (lot AS2), la poussée suit `lateral_factor` comme l'abri."""
    d = ahead_distance(rider_s, bot_s, length_m, is_loop) - BIKE_LENGTH_M
    return PUSH_FROM_BEHIND * lateral_factor(dx_m) if 0.0 <= d < PUSH_GAP_M else 0.0


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
    shelters = _shelters(sources)   # positions, voies et gabarits lus une fois par pas (lot AS4)
    for b in sources:
        if b is rider:
            continue
        params = getattr(b, "params", None)
        head = params.wind_mps if params is not None else 0.0
        cross = cross_of(b) if cross_of else 0.0
        me = lane_of(b)
        target, src = _group_draft(b.s, me, shelters, length_m, is_loop, skip=b)
        if src is not None:
            target *= crosswind_factor(b.v, head, cross)
        b.draft = smooth(getattr(b, "draft", 0.0), target, dt)
        wheel = wheel_ahead(b.s, sources, length_m, is_loop, skip=b)
        b.wheel = None if wheel is None else (wheel[0], wheel[1].v)
        push = 0.0
        if PUSH_ENABLED:
            for s, f, other, _ in shelters:
                if f is not b and 0.0 <= ahead_distance(s, b.s, length_m, is_loop) - BIKE_LENGTH_M < PUSH_GAP_M:
                    dx = 0.0 if me is None or other is None else other - me
                    push = max(push, PUSH_FROM_BEHIND * lateral_factor(dx))
        b.push = push


def lane_target(s: float, v: float, lane: Lane, others: Iterable[tuple[float, float, Lane]],
                length_m: float | None = None, is_loop: bool = False) -> tuple[float, bool]:
    """Écart à l'axe visé par un coureur (lot AS2) et vrai s'il double.

    Placement automatique (`lane.auto`) : à moins de `FOLLOW_LOOK_M` derrière un coureur plus lent ou à
    la même vitesse, sa ligne ; pour doubler (plus de `PASS_SPEED_MPS` plus vite à moins de `PASS_GAP_M`),
    `PASS_OFFSET_M` à sa gauche ; sinon `lane.home`. Puis le couloir : chaque coureur côte à côte (roues
    qui se chevauchent, ou qui se toucheront dans `SIDE_LOOK_S`, devant comme derrière) borne la cible
    à `SIDE_CLEAR_M` de lui, du côté où l'on est déjà ; à écart égal, celui de derrière (à la même place,
    celui de plus grand `rank` ; face à un coureur figé, toujours soi) passe à gauche. Coincé entre deux coureurs trop proches : le milieu du couloir.
    `others` : (s, v, Lane) des autres coureurs, positions du pas précédent. Placement coupé : `home`.
    """
    if not lane.auto:
        return lane.home, False
    target, passing = lane.home, False
    left_bound, right_bound = PASS_LANE_MIN_M, LANE_MAX_M
    lead: tuple[float, float, Lane] | None = None
    for o_s, o_v, o_lane in others:
        d = ahead_distance(s, o_s, length_m, is_loop)
        if 0.0 < d <= BIKE_LENGTH_M + FOLLOW_LOOK_M and (lead is None or d < lead[0]):
            lead = (d, o_v, o_lane)
        gap = abs(d) - BIKE_LENGTH_M                 # roue à roue, qu'il soit devant ou derrière
        closing = (v - o_v) if d > 0.0 else (o_v - v)   # > 0 : on se rapproche
        if not (gap < 0.0 or closing > 0.0 and gap < max(PASS_TOUCH_GAP_M, closing * SIDE_LOOK_S)):
            continue
        dx = lane.m - o_lane.m
        tie_left = d > 0.0 or (d == 0.0 and lane.rank > o_lane.rank) or not o_lane.auto
        if dx < -0.05 or (abs(dx) <= 0.05 and tie_left):
            right_bound = min(right_bound, o_lane.m - SIDE_CLEAR_M)   # il est à ma droite
        else:
            left_bound = max(left_bound, o_lane.m + SIDE_CLEAR_M)
    if lead is not None:
        d, o_v, o_lane = lead
        gap, dv = d - BIKE_LENGTH_M, v - lead[1]
        if dv > PASS_SPEED_MPS and gap < PASS_GAP_M:
            target, passing = o_lane.m - PASS_OFFSET_M, True
        elif o_v <= v + FOLLOW_SPEED_TOL_MPS:
            target = o_lane.m
    if not passing:
        target = max(target, LANE_MIN_M)
    if left_bound > right_bound:
        target = 0.5 * (left_bound + right_bound)
    else:
        target = min(max(target, left_bound), right_bound)
    passing = passing or target < LANE_MIN_M
    return min(max(target, PASS_LANE_MIN_M if passing else LANE_MIN_M), LANE_MAX_M), passing


def start_grid(bots: Iterable[Any], rider_s: float) -> None:
    """Grille de départ (lot AS2) : les bots `constant` posés à la place du cycliste (bots du menu, recréés
    au départ) se rangent par deux, à `BOT_LANE_M` et `LANE_MIN_M` (0,9 m de chaque côté du cycliste), le
    premier rang à sa hauteur, les suivants `START_ROW_M` derrière (avant la ligne de départ s'il le faut,
    `s` négatif) : personne ne part dans un autre coureur, et aucun bot ne part devant le cycliste."""
    placed = 0
    for b in bots:
        lane = getattr(b, "lane", None)
        if lane is None or getattr(b, "kind", "constant") != "constant" or abs(b.s - rider_s) >= BIKE_LENGTH_M:
            continue
        row, side = divmod(placed, 2)
        lane.m = lane.target = BOT_LANE_M if side == 0 else LANE_MIN_M
        lane.rate = 0.0
        b.physics.s = rider_s - row * START_ROW_M
        placed += 1


def step_lane(lane: Lane, target: float, dt: float) -> None:
    """Avance l'écart à l'axe vers `target` : au plus `LANE_RATE_MPS`, accélération bornée, sans à-coup."""
    want = max(-LANE_RATE_MPS, min(LANE_RATE_MPS, (target - lane.m) / LANE_TAU_S))
    dv = max(-LANE_ACCEL_MPS2 * dt, min(LANE_ACCEL_MPS2 * dt, want - lane.rate))
    lane.rate += dv
    lane.m += lane.rate * dt
    if abs(target - lane.m) < 0.005 and abs(lane.rate) < 0.05:
        lane.m, lane.rate = target, 0.0


def update_lanes(runners: list[tuple[float, float, Lane]], dt: float, length_m: float | None = None,
                 is_loop: bool = False) -> None:
    """Placement de tous les coureurs (lot AS2) : cibles calculées sur les positions du pas précédent,
    puis chacun avance ; l'ordre de la liste ne compte pas. `runners` : (s, v, Lane) du cycliste et des
    bots `constant` (le fantôme n'en est pas : il passe à travers)."""
    targets = []
    for i, (s, v, lane) in enumerate(runners):
        others = [r for j, r in enumerate(runners) if j != i]
        targets.append(lane_target(s, v, lane, others, length_m, is_loop))
    for (_, _, lane), (target, passing) in zip(runners, targets):
        lane.target, lane.passing = target, passing
        step_lane(lane, target, dt)
