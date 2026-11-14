"""Cyclistes du décor sur la route du parcours, calculés par le core (lot AS7, série AS, version 2.0).

Module pur (aucune E/S), portage de `engine/scripts/road_cyclists_model.gd` (lot P28, voies du lot P32) :
mêmes cases de `SLOT_M`, mêmes tirages d'après la graine et l'indice de la case, mêmes cas
(`oncoming`, `ahead`, `overtake`), mêmes tailles, mêmes vitesses et mêmes règles de voie. Avec la même
graine, les mêmes montées, les mêmes villages et le même budget, les deux modèles tirent les mêmes groupes
(test de parité `core/tests/test_road_cyclists.py` et `engine/tests/unit/test_road_cyclists_parity.gd`).

Ce que le lot AS7 ajoute au modèle de l'engine :
- le core devient l'autorité des cyclistes proches : `state_list` donne au plus `STATE_MAX` cyclistes à moins
  de `NEAR_M` (`{id, s, v, lane_m, look}`), l'engine les place et garde ses groupes décoratifs au-delà ;
- `sources` donne les cyclistes qui roulent dans le sens du parcours comme des sources d'abri ordinaires
  (attributs `s`, `v`, `id`, `kind`, `lane_m` lus par `draft.py`) ; ceux d'en face n'abritent pas ;
- `hold_after_pass` : un groupe `overtake` qui a doublé garde sa vitesse (sa puissance au moment du
  rabattement) au lieu de suivre celle du cycliste, pour qu'on puisse prendre sa roue ;
- le budget ne dépend plus du préréglage de qualité (`CORE_BUDGET`, celui du préréglage high).

Correctif du 7 novembre (recette vélo sur le gravel, mêmes règles que l'engine) : bords pris sur la
demi-largeur roulable `half_width_at(s)` (`surface_physics.rideable_half_m`), en file sur un chemin étroit,
`FILE_GAP_M` de 2,1 m, écarts latéraux à accélération bornée, pas de dépassement sur la ligne d'un bot proche.

`lateral` (`lane_m` dans le contrat) : écart à l'axe, positif à droite du sens du parcours, comme `lane_m`
du lot AS2. Les positions `s` sont celles du parcours ouvert ; les bots sont donnés par leurs abscisses.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, NamedTuple

MASK32 = 0xFFFFFFFF

SLOT_M = 250.0
DEVELOPMENT_M = 2.1 * 50.0 / 17.0
RATE_FLAT = 0.25
RATE_CLIMB = 0.75
RATE_VILLAGE = 0.4
VILLAGE_NEAR_M = 1000.0
SIZE_SHARES = (0.55, 0.25, 0.20)   # 1, 2, de 3 à 6
CASE_SHARES = (("oncoming", 0.40), ("ahead", 0.35), ("overtake", 0.25))
ONCOMING_KMH = (22.0, 35.0)
AHEAD_KMH = (18.0, 28.0)
OVERTAKE_KMH = (4.0, 8.0)
OVERTAKE_MIN_KMH = 25.0
MAX_KMH = 70.0
MIN_KMH = 9.0
SPAWN_AHEAD_M = (600.0, 1100.0)
SPAWN_SLOW_M = (250.0, 600.0)
SPAWN_BEHIND_M = 150.0
REMOVE_BEHIND_M = 300.0
REMOVE_AHEAD_M = 1200.0
PASS_START_M = 30.0
MERGE_AHEAD_M = 20.0
GIVE_UP_S = 60.0
ABREAST_M = 0.6
FILE_GAP_M = 2.1          # d'axe à axe en file : vélo de 1,7 m (draft.BIKE_LENGTH_M) et 0,4 m de roue à roue
RIDER_HALF_WIDTH_M = 0.3
MIN_GAP_M = 0.7
EDGE_IN_M = 0.5
RIDER_LATERAL_M = 1.2     # RoadBuilder.RIDER_LATERAL_M (lot P32)
BOT_LATERAL_M = 2.1       # RoadBuilder.BOT_LATERAL_M (lot P32)
BOT_LOOK_M = 30.0
FALL_BACK_MPS = 0.5
CROSS_S = 3.0            # lot DB1 : un `overtake` met 3 s à passer de droite à gauche du cycliste (2,6 m, SIDE_*)
CATCH_M = 4.0
LANE_FREE_M = 100.0
MIN_CENTRE_M = MIN_GAP_M + 2.0 * RIDER_HALF_WIDTH_M
GROUP_CLEAR_M = 30.0
VEHICLE_CLEAR_M = 60.0
SIDE_SPEED_MPS = 1.5      # écart latéral : vitesse au plus, ...
SIDE_ACCEL_MPS2 = 2.0     # ... accélération au plus (on s'écarte et on se rabat sans à-coup, essai du 7/11)
SIDE_TAU_S = 0.5          # ... et approche de la place visée,
SIDE_ARRIVE_MPS = 0.1     # ... à au moins 0,1 m/s jusqu'à y être
DL_SPEED_MPS = 1.0        # passage de deux de front à la file (et retour) : recul ou retour d'un membre
SIDE_LOOK_M = 2.5
SIDE_CLEAR_M = 0.8
SPEED_PERIOD_S = 1.0
SALUT_EVERY = 3
ROLL_N = 3.9
WEIGHT_N = 785.0
AIR_K = 0.21

# Lot AS7
SEED = 0                  # graine de living_decor.gd (`cyclists.configure(…, 0, …)`)
CORE_BUDGET = 16          # living(high).cyclists : les groupes proches ne dépendent plus du préréglage
NEAR_M = 60.0             # cyclistes envoyés à l'engine dans `state` (devant ou derrière)
STATE_MAX = 6
SOURCE_ID_PREFIX = "rider:"   # `draft_bot` d'un cycliste du décor : « rider:<id> »
APPEARANCE_MASK = 0xFFFFF     # `look` de la liste `riders` : 20 bits bas du tirage du cycliste


# --- hachage de vegetation_placer.gd ------------------------------------------------------------------

def mix(h: int) -> int:
    """`VegetationPlacer._mix` : mélange 32 bits (finaliseur de MurmurHash3)."""
    h &= MASK32
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & MASK32
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & MASK32
    h ^= h >> 16
    return h


def hash3(a: int, b: int, c: int) -> int:
    """`VegetationPlacer.hash3`."""
    h = mix(a ^ 0x9E3779B9)
    h = mix(h ^ (b & MASK32))
    return mix(h ^ (c & MASK32))


def _u(h: int) -> float:
    return float(h & 0xFFFFFF) / 16777216.0


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _move_toward(a: float, b: float, delta: float) -> float:
    return b if abs(b - a) <= delta else a + math.copysign(delta, b - a)


def _sign(x: float) -> float:
    return 1.0 if x > 0.0 else (-1.0 if x < 0.0 else 0.0)


# --- vitesses ------------------------------------------------------------------------------------------

def power_for(v_mps: float) -> float:
    """Puissance qui donne `v` sur le plat."""
    return ROLL_N * v_mps + AIR_K * v_mps * v_mps * v_mps


def speed_on_grade(p: float, grade_pct: float) -> float:
    """Vitesse à puissance `p` sur une pente `grade_pct` (dans le sens du cycliste du décor), bornée."""
    c = ROLL_N + WEIGHT_N * grade_pct / 100.0
    lo, hi = 0.0, MAX_KMH / 3.6
    for _ in range(18):
        mid = (lo + hi) * 0.5
        if c * mid + AIR_K * mid * mid * mid < p:
            lo = mid
        else:
            hi = mid
    return min(max(lo, MIN_KMH / 3.6), MAX_KMH / 3.6)


def cadence_rpm(v_mps: float) -> float:
    """Cadence (tr/min) à `v` avec le développement DEVELOPMENT_M ; roue libre au-delà de 55 km/h."""
    if v_mps > 55.0 / 3.6:
        return 0.0
    return v_mps / DEVELOPMENT_M * 60.0


# --- montées de l'engine (climb_detector.gd, lot P14) ----------------------------------------------------

CLIMB_STEP_M = 20.0
CLIMB_SMOOTH_M = 100.0
CLIMB_HYSTERESIS_M = 8.0
CLIMB_MERGE_GAP_M = 300.0
CLIMB_PLATEAU_RISE_M = 1.5
CLIMB_MIN_LENGTH_M = 1500.0
CLIMB_MIN_AVG_PCT = 4.0
CLIMB_MIN_GAIN_M = 80.0
CLIMB_REFINE_M = 150.0
CLIMB_SNAP_M = 0.3


def detect_climbs(route: Any) -> list[tuple[float, float]]:
    """Montées `(début, sommet)` de `climb_detector.gd` (`detect`), celles que living_decor.gd donne aux
    cyclistes du décor quand le parcours n'a pas de couche `segments` : mêmes pas, lissage, hystérésis,
    fusion, seuils et recalage sur le profil brut."""
    if route is None or route.length_m <= CLIMB_STEP_M:
        return []
    n = int(math.floor(route.length_m / CLIMB_STEP_M)) + 1
    s_arr = [min(i * CLIMB_STEP_M, route.length_m) for i in range(n)]
    raw = [route.sample(s).alt_m for s in s_arr]
    half = int(round(CLIMB_SMOOTH_M / CLIMB_STEP_M / 2.0))
    sm = [0.0] * n
    acc, count = 0.0, 0
    for i in range(min(half, n)):
        acc += raw[i]
        count += 1
    for i in range(n):
        if i + half < n:
            acc += raw[i + half]
            count += 1
        if i - half - 1 >= 0:
            acc -= raw[i - half - 1]
            count -= 1
        sm[i] = acc / count
    ascents: list[list[int]] = []
    going_up = True
    i_min = i_max = i_rise = 0
    for i in range(1, n):
        if going_up:
            if sm[i] > sm[i_max]:
                i_max = i
            if sm[i] > sm[i_rise] + CLIMB_PLATEAU_RISE_M:
                i_rise = i
            dropped = sm[i] < sm[i_max] - CLIMB_HYSTERESIS_M
            plateau = s_arr[i] - s_arr[i_rise] >= CLIMB_MERGE_GAP_M
            if dropped or plateau:
                if sm[i_max] - sm[i_min] >= CLIMB_HYSTERESIS_M:
                    ascents.append([i_min, i_max])
                going_up = False
                i_min = i
        else:
            if sm[i] <= sm[i_min]:
                i_min = i
            if sm[i] > sm[i_min] + CLIMB_HYSTERESIS_M:
                going_up = True
                i_max = i_rise = i
    if going_up and i_max > i_min and sm[i_max] - sm[i_min] >= CLIMB_HYSTERESIS_M:
        ascents.append([i_min, i_max])
    merged: list[list[int]] = []
    for a in ascents:
        if merged and s_arr[a[0]] - s_arr[merged[-1][1]] < CLIMB_MERGE_GAP_M and sm[a[1]] >= sm[merged[-1][1]]:
            merged[-1][1] = a[1]
        else:
            merged.append([a[0], a[1]])
    r = int(CLIMB_REFINE_M / CLIMB_STEP_M)
    out = []
    for i_lo, i_hi in merged:
        lo, hi = max(0, i_lo - r), min(n - 1, i_lo + r)
        best = lo
        for j in range(lo, hi + 1):
            if raw[j] <= raw[best]:
                best = j
        i0 = next((j for j in range(hi, best - 1, -1) if raw[j] <= raw[best] + CLIMB_SNAP_M), best)
        lo, hi = max(0, i_hi - r), min(n - 1, i_hi + r)
        best = lo
        for j in range(lo, hi + 1):
            if raw[j] > raw[best]:
                best = j
        i1 = next((j for j in range(lo, best + 1) if raw[j] >= raw[best] - CLIMB_SNAP_M), best)
        if i1 <= i0:
            continue
        length = s_arr[i1] - s_arr[i0]
        gain = raw[i1] - raw[i0]
        avg = gain / length * 100.0 if length > 0.0 else 0.0
        if not ((length >= CLIMB_MIN_LENGTH_M and avg >= CLIMB_MIN_AVG_PCT) or gain >= CLIMB_MIN_GAIN_M):
            continue
        out.append((s_arr[i0], s_arr[i1]))
    return out


def climbs_for(route: Any, segments: Iterable[Any] = ()) -> list[tuple[float, float]]:
    """Montées du décor comme living_decor.gd (`climbs_of`) : celles de la couche `segments` quand elle en a
    (série T, `s_start`, `s_end`), sinon `detect_climbs`."""
    segs = list(segments)
    if segs:
        return [(float(sg.s_start), float(sg.s_end)) for sg in segs if getattr(sg, "type", "") == "climb"]
    return detect_climbs(route)


# --- modèle ----------------------------------------------------------------------------------------------

@dataclass
class Member:
    dl: float
    col: int
    jersey: int
    look: int
    phase: float
    index: int
    lateral: float = 0.0
    appearance: int = 0        # `look` du contrat : `jersey` dans les 3 bits bas, `look` à partir du bit 4
    col0: int | None = None
    dl0: float | None = None
    lat_v: float = 0.0         # vitesse latérale (m/s)


@dataclass
class Group:
    id: str
    case: str
    dir: int
    s: float
    flat_mps: float
    delta_mps: float
    power_w: float
    speed_mps: float
    members: list[Member]
    salut: bool
    speed_at: float = -math.inf
    behind_t: float = 0.0
    passed: bool = False
    best_rel: float = -math.inf
    side: str = "right"
    bot_near: bool = False
    pass_lat: float | None = None
    last_rel: float | None = None
    gone: bool = False
    said: bool = False
    bot: bool = False          # bot vu comme un groupe d'un cycliste (lot P32)
    held: bool = False         # lot AS7 : `overtake` rabattu qui garde sa vitesse
    half: float = 3.0          # demi-largeur roulable sous la tête du groupe (`_half_at`)
    moved_mps: float | None = None   # lot DB1 : vitesse du dernier pas, gênes comprises (None : pas encore bougé)

    def pace(self) -> float:
        """Vitesse à laquelle il avance vraiment (lot DB1) : celle de son dernier pas, sinon l'annoncée."""
        return self.speed_mps if self.moved_mps is None else self.moved_mps

    @property
    def size(self) -> int:
        return len(self.members)

    def lateral(self) -> float:
        """Écart à l'axe d'un groupe : celui de son premier membre."""
        return self.members[0].lateral


class Rider(NamedTuple):
    """Un cycliste du décor : abscisse, vitesse (m/s, positive dans son sens), écart à l'axe."""

    id: str
    s: float
    v: float
    lane_m: float
    dir: int
    look: int
    jersey: int
    group: str
    case: str
    appearance: int = 0


class DraftSource(NamedTuple):
    """Cycliste du décor vu comme une source d'abri par `draft.py` (`kind` constant : il abrite)."""

    s: float
    v: float
    id: str
    lane_m: float
    kind: str = "constant"


class RoadCyclists:
    """Portage de `road_cyclists_model.gd`. `route` : `route.Route` (ou objet avec `length_m`,
    `sample(s)` → x, z, grade_pct). `climbs` : (début, sommet) ; `villages` : (x, z) des POI `village`."""

    def __init__(self, route: Any, climbs: Iterable[Sequence[float]] = (),
                 villages: Iterable[Sequence[float]] = (), budget: int = CORE_BUDGET, seed: int = 0,
                 road_width_m: float = 6.0, hold_after_pass: bool = True,
                 half_width_at: Callable[[float], float] | None = None) -> None:
        self.route = route
        self.climbs = [(float(c[0]), float(c[1])) for c in climbs]
        self.villages = [(float(v[0]), float(v[1])) for v in villages]
        self.budget = max(0, int(budget))
        self.seed = int(seed)
        self.road_width_m = float(road_width_m)
        self.hold_after_pass = hold_after_pass
        # Demi-largeur roulable en s (option gravel : surface_physics.rideable_half_m), sinon celle du bitume
        self.half_width_at = half_width_at
        self.vehicles: list[Any] = []     # circulation du core (lot AS6) : attributs/clés `s`, `dir`
        self.groups: list[Group] = []
        self.reset()

    def reset(self) -> None:
        self.groups = []
        self.spawned_total = 0
        self.passed_total = 0
        self.overtook_total = 0
        self.last_event: dict[str, Any] = {}
        self._next_slot = 0
        self._started = False
        self._clock = 0.0
        self._bot_groups: list[Group] = []
        self._last_bots_s: list[float] = []

    def rider_count(self) -> int:
        return sum(g.size for g in self.groups)

    def in_climb(self, s: float) -> bool:
        return any(c0 <= s <= c1 for c0, c1 in self.climbs)

    # --- tirages ---------------------------------------------------------------------------------------

    def slot_event(self, k: int) -> dict[str, Any]:
        """Lancer d'une case : {} si elle ne porte rien, sinon le groupe tiré."""
        s = (k + 0.5) * SLOT_M
        if s > self.route.length_m:
            return {}
        rate = RATE_FLAT
        if self.in_climb(s):
            rate = RATE_CLIMB
        elif self.villages:
            smp = self.route.sample(s)
            for vx, vz in self.villages:
                if math.hypot(smp.x - vx, smp.z - vz) <= VILLAGE_NEAR_M:
                    rate = RATE_VILLAGE
                    break
        h = hash3(self.seed, k, 0xC1C1E5)
        if _u(h) >= rate:
            return {}
        us = _u(mix(h + 1))
        size = 1
        if us >= SIZE_SHARES[0] + SIZE_SHARES[1]:
            size = 3 + int(_u(mix(h + 2)) * 4.0)
        elif us >= SIZE_SHARES[0]:
            size = 2
        uc = _u(mix(h + 3))
        case = CASE_SHARES[-1][0]
        acc = 0.0
        for name, share in CASE_SHARES:
            acc += share
            if uc < acc:
                case = name
                break
        lo, hi = ONCOMING_KMH if case == "oncoming" else (AHEAD_KMH if case == "ahead" else OVERTAKE_KMH)
        return {
            "slot": k, "case": case, "size": size,
            "abreast": size >= 2 and (h >> 9) & 1 == 0,
            "kmh": _lerp(lo, hi, _u(mix(h + 4))),
            "dist_m": _u(mix(h + 5)),
            "salut": mix(h + 6) % SALUT_EVERY == 0,
            "hash": h,
        }

    # --- une image ---------------------------------------------------------------------------------------

    def _grade_at(self, s: float, direction: int) -> float:
        return self.route.sample(min(max(s, 0.0), self.route.length_m)).grade_pct * direction

    def _half_at(self, s: float) -> float:
        half = self.road_width_m * 0.5
        if self.half_width_at is not None:
            half = min(half, float(self.half_width_at(s)))
        return max(half, EDGE_IN_M)

    @staticmethod
    def _edge_lateral(half: float) -> float:
        """Écart à l'axe de la place la plus proche du bord droit, roues à EDGE_IN_M du bord."""
        return half - EDGE_IN_M

    @staticmethod
    def _narrow(half: float) -> bool:
        """Chemin trop étroit pour rouler à MIN_GAP_M du cycliste en restant dessus : on y roule en file."""
        return half - EDGE_IN_M < RIDER_LATERAL_M + MIN_CENTRE_M - 1e-6

    def update(self, rider_s: float, rider_v: float, dt_s: float, paused: bool = False,
               bots: Sequence[tuple[float, float]] = ()) -> None:
        """Une image : `rider_s`, `rider_v` (m/s) du cycliste ; `bots` : places des bots `(s, lateral)`
        (comme `bots_view_model.places()` de l'engine)."""
        self.last_event = {}
        if paused:
            return
        self._clock += dt_s
        if not self._started:
            self._started = True
            self._next_slot = max(0, int(math.floor(rider_s / SLOT_M)) + 1)
        while self._next_slot * SLOT_M <= rider_s:
            ev = self.slot_event(self._next_slot)
            self._next_slot += 1
            if ev and self.rider_count() + ev["size"] <= self.budget:
                self._spawn(ev, rider_s, rider_v, bots)
        self._bot_groups = []
        for i, (b, b_lat) in enumerate(bots):
            v_b = rider_v
            if i < len(self._last_bots_s) and dt_s > 0.0:
                v_b = max(0.0, (b - self._last_bots_s[i]) / dt_s)
            self._bot_groups.append(Group(
                id=f"bot{i}", case="bot", dir=1, s=float(b), flat_mps=v_b, delta_mps=0.0, power_w=0.0,
                speed_mps=v_b, salut=False, bot=True,
                members=[Member(dl=0.0, col=0, jersey=0, look=0, phase=0.0, index=0, lateral=float(b_lat))]))
        self._last_bots_s = [float(b) for b, _ in bots]
        kept = []
        for g in self.groups:
            self._move(g, rider_s, rider_v, dt_s, bots)
            rel = g.s - rider_s
            if (not g.gone and -REMOVE_BEHIND_M <= rel <= REMOVE_AHEAD_M
                    and 0.0 <= g.s <= self.route.length_m):
                kept.append(g)
        self.groups = kept

    @staticmethod
    def _field(obj: Any, key: str, default: Any) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _spawn(self, ev: dict[str, Any], rider_s: float, rider_v: float, bots: Sequence[tuple[float, float]] = (),
               at_s: float | None = None) -> None:
        case = ev["case"]
        direction = -1 if case == "oncoming" else 1
        if at_s is not None:
            s0 = at_s
        elif case == "oncoming":
            if self.vehicles:
                return
            s0 = rider_s + _lerp(*SPAWN_AHEAD_M, ev["dist_m"])
        elif case == "ahead":
            s0 = rider_s + _lerp(*SPAWN_SLOW_M, ev["dist_m"])
        else:
            s0 = rider_s - SPAWN_BEHIND_M
            if s0 < 0.0:
                return
        if s0 < 0.0 or s0 > self.route.length_m:
            return
        if at_s is None:
            for v in self.vehicles:
                if abs(float(self._field(v, "s", math.inf)) - s0) < VEHICLE_CLEAR_M:
                    return
            for h in self.groups:
                if abs(h.s - s0) < GROUP_CLEAR_M:
                    return
        flat = ev["kmh"] / 3.6
        if case == "overtake":
            flat = max(rider_v + flat, OVERTAKE_MIN_KMH / 3.6)
        h = ev["hash"]
        abreast = ev["abreast"] and case != "overtake"
        members = []
        for i in range(ev["size"]):
            hi = mix(h + 100 + i)
            members.append(Member(
                dl=float(i // 2 if abreast else i) * FILE_GAP_M, col=i % 2 if abreast else 0,
                jersey=hi % 8, look=(hi >> 4) & 0xFFFF, phase=_u(mix(hi + 1)), index=i,
                appearance=hi & APPEARANCE_MASK))
        g = Group(id=f"c{ev['slot']}", case=case, dir=direction, s=s0, flat_mps=flat,
                  delta_mps=ev["kmh"] / 3.6, power_w=power_for(flat), speed_mps=flat, members=members,
                  salut=ev["salut"], side="left" if direction < 0 else "right")
        g.bot_near = self._bot_near(g, bots)
        g.half = self._half_at(s0)
        if self._narrow(g.half):
            for i, m in enumerate(members):
                m.col0, m.dl0 = m.col, m.dl
                m.col, m.dl = 0, float(i) * FILE_GAP_M
        for m in members:
            m.lateral = self._target_lateral(g, m)
        self.groups.append(g)
        self.spawned_total += 1

    def place_for_test(self, rider_s: float, rider_v: float, case: str, rel_m: float, size: int = 1,
                       abreast: bool = False, kmh: float | None = None) -> Group | None:
        """Groupe posé par un test : cas `case`, `size` cyclistes, tête à `rel_m` du cycliste, à `kmh` sur
        le plat (par défaut, comme `place_for_test` de l'engine)."""
        if case not in ("oncoming", "ahead", "overtake"):
            return None
        default = {"oncoming": ONCOMING_KMH[0], "ahead": AHEAD_KMH[0], "overtake": OVERTAKE_KMH[1]}[case]
        self._spawn({"case": case, "slot": 1000000 + self.spawned_total, "kmh": default if kmh is None else kmh,
                     "dist_m": 0.0, "size": max(1, size), "abreast": abreast,
                     "hash": 7919 * (self.spawned_total + 1), "salut": False},
                    rider_s, rider_v, (), rider_s + rel_m)
        return self.groups[-1]

    def _bot_near(self, g: Group, bots: Sequence[tuple[float, float]]) -> bool:
        head = g.s
        tail = head - g.dir * g.size * FILE_GAP_M
        lo, hi = min(head, tail) - BOT_LOOK_M, max(head, tail) + BOT_LOOK_M
        return any(lo < float(b) < hi for b, _ in bots)

    def _target_lateral(self, g: Group, m: Member) -> float:
        own = self._base_lateral(g, m)
        if g.pass_lat is not None:
            own = min(own, g.pass_lat) if g.dir == 1 else max(own, g.pass_lat)
        if self._narrow(g.half):   # chemin étroit : jamais hors de la bande roulable
            edge = self._edge_lateral(g.half)
            own = min(max(own, -edge), edge)
        return own

    def _base_lateral(self, g: Group, m: Member) -> float:
        edge = self._edge_lateral(g.half)
        col = m.col * ABREAST_M
        if self._narrow(g.half):
            # Chemin étroit : le plus à l'extérieur de front sur le bord, les autres à l'intérieur, le temps de
            # reculer dans la file (dans le même ordre en travers)
            col -= max(o.col for o in g.members) * ABREAST_M
        if g.case == "oncoming":
            return -(edge + col)
        if g.case == "overtake" and g.side == "left":
            return RIDER_LATERAL_M - MIN_CENTRE_M
        if g.bot_near and not self._narrow(g.half):
            return max(edge, BOT_LATERAL_M + MIN_CENTRE_M)
        return edge + col

    def _formation(self, g: Group, file: bool, dt_s: float) -> None:
        """De deux de front à la file (`file`) et retour, sans se chevaucher : en file, un membre recule à
        DL_SPEED_MPS jusqu'à sa place puis se range dans la ligne ; de retour de front, il reprend sa colonne et
        ne remonte qu'une fois à côté de celui qu'il suit."""
        for i, m in enumerate(g.members):
            if m.col0 is None:
                m.col0, m.dl0 = m.col, m.dl
            if file:
                dl_t = float(i) * FILE_GAP_M
                m.dl = _move_toward(m.dl, dl_t, DL_SPEED_MPS * dt_s)
                if abs(m.dl - dl_t) < 1e-6:
                    m.col = 0
            else:
                m.col = m.col0
                if abs(m.lateral - self._target_lateral(g, m)) < 0.05:
                    m.dl = _move_toward(m.dl, m.dl0, DL_SPEED_MPS * dt_s)

    def _side_step(self, g: Group, m: Member, dt_s: float, rider_s: float,
                   bots: Sequence[tuple[float, float]]) -> None:
        """Écart latéral vers sa place sans à-coup : vitesse au plus SIDE_SPEED_MPS, approche en SIDE_TAU_S,
        accélération et freinage au plus SIDE_ACCEL_MPS2 (arrêt sur la place, sans la dépasser)."""
        lat0 = m.lateral
        target = self._target_lateral(g, m)
        d = target - lat0
        want = _sign(d) * min(SIDE_SPEED_MPS, math.sqrt(2.0 * SIDE_ACCEL_MPS2 * abs(d)),
                              max(abs(d) / SIDE_TAU_S, SIDE_ARRIVE_MPS))
        v1 = _move_toward(m.lat_v, want, SIDE_ACCEL_MPS2 * dt_s)
        lat1 = lat0 + v1 * dt_s
        if (target - lat1) * d <= 0.0:   # arrivé : posé sur sa place
            lat1, v1 = target, 0.0
        if self._side_blocked(g, g.s - g.dir * m.dl, lat0, lat1, rider_s, bots):
            lat1, v1 = lat0, 0.0
        m.lateral, m.lat_v = lat1, v1

    def _move(self, g: Group, rider_s: float, rider_v: float, dt_s: float, bots: Sequence[tuple[float, float]]) -> None:
        direction = g.dir
        members = g.members
        if self._clock - g.speed_at >= SPEED_PERIOD_S:
            g.speed_at = self._clock
            grade = self._grade_at(g.s, direction)
            spd = speed_on_grade(g.power_w, grade)
            if g.case == "overtake" and not g.held:
                spd = max(rider_v + g.delta_mps, speed_on_grade(power_for(OVERTAKE_MIN_KMH / 3.6), grade))
                spd = min(spd, MAX_KMH / 3.6)
            g.speed_mps = spd
        near = self._bot_near(g, bots)
        g.bot_near = near
        g.half = self._half_at(g.s)
        case = g.case
        spd_now = g.speed_mps
        rel_now = g.s - rider_s
        if case == "overtake":
            tail_now = rel_now - (g.size - 1) * FILE_GAP_M
            # Lot DB1 : il ne se met sur la gauche (en traversant la ligne du cycliste) qu'avec la place de finir son
            # écart avant d'arriver sur lui ; plus près derrière, il se laisse distancer jusqu'à l'avoir ; déjà à sa
            # hauteur ou devant (gêné dans une montée), il reste à droite et se laisse doubler
            cross_m = FILE_GAP_M + max(g.speed_mps - rider_v, 0.0) * CROSS_S
            if g.side == "right" and rel_now >= -PASS_START_M and tail_now < MERGE_AHEAD_M:
                if near:
                    spd_now = min(spd_now, rider_v)
                elif rel_now < -cross_m:
                    g.side = "left"
                elif rel_now < 0.0:
                    spd_now = min(spd_now, rider_v - FALL_BACK_MPS)
            elif g.side == "left" and tail_now > MERGE_AHEAD_M and not near:
                g.side = "right"
        # Lot P32 : un groupe qui en rattrape un autre du même sens le double vers l'axe (voir l'engine)
        g.pass_lat = None
        alongside = self._caught_groups(g)
        own = self._base_lateral(g, members[0])
        cur = g.lateral()
        near_groups = [h for h in alongside
                       if abs(h.lateral() - own) < MIN_CENTRE_M or abs(h.lateral() - cur) < MIN_CENTRE_M]
        if near_groups:
            # Bots à moins de BOT_LOOK_M : on ne double pas sur leur ligne, ni en la traversant (file longue)
            lanes = alongside + [b for b in self._bot_groups if b not in alongside
                                 and abs(b.s - g.s) < BOT_LOOK_M + g.size * FILE_GAP_M]
            pass_lat = own
            for _ in range(3):
                for h in lanes:
                    h_lat = h.lateral()
                    if abs(pass_lat - h_lat) < MIN_CENTRE_M:
                        pass_lat = h_lat - _sign(h_lat) * MIN_CENTRE_M
            # Lot DB1 : `slowest` (tous, devant et derrière) décide s'il double ; `limit` (ceux de devant seuls, à
            # la vitesse où ils avancent vraiment) règle sa vitesse : un groupe ne ralentit jamais pour celui qui le
            # suit, et celui qui suit se règle sur l'allure réelle du premier, gêné lui-même, pas sur l'annoncée
            slowest = math.inf
            limit = math.inf
            blocking = False
            for h in near_groups:
                slowest = min(slowest, h.speed_mps)
                if (h.s - g.s) * direction > 0.0:
                    limit = min(limit, h.pace())
                # encore derrière lui, un de ses membres sur sa ligne (la queue se décale après la tête)
                if (g.s - h.s) * direction < 0.0 and min(abs(m.lateral - h.lateral()) for m in members) < MIN_CENTRE_M - 0.05:
                    blocking = True
            crossing = False
            for h in lanes:
                h_lat = h.lateral()
                through = min(cur, pass_lat) < h_lat < max(cur, pass_lat)
                if through or (abs(pass_lat - h_lat) < MIN_CENTRE_M - 0.05
                               and abs(pass_lat - h_lat) < abs(cur - h_lat)):
                    crossing = True
                    slowest = min(slowest, h.speed_mps)
                    if (h.s - g.s) * direction > 0.0:
                        limit = min(limit, h.pace())
                    if (g.s - h.s) * direction < 0.0:
                        blocking = True
            faster = spd_now > slowest
            out = not blocking
            if crossing:
                if blocking:
                    spd_now = min(spd_now, limit - FALL_BACK_MPS)
            elif faster and (out or self._lane_free_for(g, rider_s) and (
                    direction == -1 or abs(pass_lat - RIDER_LATERAL_M) >= MIN_CENTRE_M
                    or abs(g.s - rider_s) > PASS_START_M)):
                if abs(pass_lat - own) > 1e-3:
                    g.pass_lat = pass_lat
                if blocking:
                    spd_now = min(spd_now, limit)
            elif blocking or not faster:
                spd_now = min(spd_now, limit - FALL_BACK_MPS)
        g.s += direction * spd_now * dt_s
        g.moved_mps = max(spd_now, 0.0)
        rel = g.s - rider_s
        rel0 = rel if g.last_rel is None else g.last_rel
        g.last_rel = rel
        # En file près d'un bot (`ahead`, sur l'accotement) et sur un chemin étroit (tous les cas)
        self._formation(g, self._narrow(g.half) or (case == "ahead" and near), dt_s)
        for m in members:
            self._side_step(g, m, dt_s, rider_s, bots)
        if case == "ahead":
            tail = g.size * FILE_GAP_M
            if not g.passed and rel - tail < 0.0 <= rel0 - tail:
                g.passed = True
                self.passed_total += 1
        elif case == "overtake":
            last_rel = rel - (g.size - 1) * FILE_GAP_M
            if rel >= 0.0 > rel0 and g.salut and not g.said:
                g.said = True
                self.last_event = {"kind": "voice_salut", "s": g.s, "lateral": members[0].lateral}
            if not g.passed and last_rel > MERGE_AHEAD_M:
                g.passed = True
                self.overtook_total += 1
                if self.hold_after_pass:
                    # Lot AS7 : rabattu, il garde sa vitesse (sa puissance à cet instant sur cette pente)
                    g.held = True
                    v = g.speed_mps
                    g.power_w = (ROLL_N + WEIGHT_N * self._grade_at(g.s, direction) / 100.0) * v + AIR_K * v ** 3
            if rel <= g.best_rel + 0.01 and rel < 0.0:
                g.behind_t += dt_s
                if g.behind_t >= GIVE_UP_S:
                    g.gone = True
            else:
                g.behind_t = 0.0
            g.best_rel = max(g.best_rel, rel)

    def _caught_groups(self, g: Group) -> list[Group]:
        direction = g.dir
        g_head = g.s * direction
        g_tail = g_head - (g.size - 1) * FILE_GAP_M
        out = []
        for h in self.groups + self._bot_groups:
            if h is g or h.dir != direction:
                continue
            h_head = h.s * direction
            h_tail = h_head - (h.size - 1) * FILE_GAP_M
            if h_tail > g_head + CATCH_M or h_head < g_tail - CATCH_M:
                continue
            out.append(h)
        return out

    def _side_blocked(self, g: Group, s: float, lat0: float, lat1: float, rider_s: float,
                      bots: Sequence[tuple[float, float]]) -> bool:
        if abs(lat1 - lat0) < 1e-6:
            return False
        near = []
        if abs(rider_s - s) < SIDE_LOOK_M:
            near.append(RIDER_LATERAL_M)
        for b, b_lat in bots:
            if abs(float(b) - s) < SIDE_LOOK_M:
                near.append(float(b_lat))
        for h in self.groups:
            if h is g or abs(h.s - s) > SIDE_LOOK_M + h.size * FILE_GAP_M:
                continue
            for m in h.members:
                if abs(h.s - h.dir * m.dl - s) < SIDE_LOOK_M:
                    near.append(m.lateral)
        for o_lat in near:
            d1 = abs(lat1 - o_lat)
            if d1 < SIDE_CLEAR_M and d1 < abs(lat0 - o_lat):
                return True
        return False

    def _lane_free_for(self, g: Group, rider_s: float) -> bool:
        direction = g.dir
        s = g.s
        for h in self.groups:
            ahead = (h.s - s) * direction
            if h.dir != direction and -5.0 < ahead < LANE_FREE_M:
                return False
        for v in self.vehicles:
            ahead2 = (float(self._field(v, "s", math.inf)) - s) * direction
            if int(self._field(v, "dir", direction)) != direction and -5.0 < ahead2 < LANE_FREE_M:
                return False
        if direction == -1 and -5.0 < (s - rider_s) < LANE_FREE_M:
            return False
        return True

    # --- sorties du lot AS7 ----------------------------------------------------------------------------

    def riders(self) -> list[Rider]:
        """Tous les cyclistes du décor, dans l'ordre des groupes puis des membres."""
        out = []
        for g in self.groups:
            for m in g.members:
                out.append(Rider(id=f"{g.id}-{m.index}", s=g.s - g.dir * m.dl, v=g.speed_mps,
                                 lane_m=m.lateral, dir=g.dir, look=m.look, jersey=m.jersey,
                                 group=g.id, case=g.case, appearance=m.appearance))
        return out

    def sources(self) -> list[DraftSource]:
        """Cyclistes du décor qui roulent dans le sens du parcours, comme sources d'abri de `draft.py`
        (id « rider:<id> », pour `draft_bot`) ; ceux d'en face n'abritent pas."""
        return [DraftSource(s=r.s, v=r.v, id=SOURCE_ID_PREFIX + r.id, lane_m=r.lane_m)
                for r in self.riders() if r.dir == 1]

    def state_list(self, rider_s: float) -> list[dict[str, Any]]:
        """Liste `riders` de `state` (au centimètre, comme `vehicles` du lot AS6) : au plus STATE_MAX
        cyclistes à moins de NEAR_M, du plus proche au plus loin, `{id, s, dir, v, lane_m, look}` ; `v` est
        positive dans le sens `dir` ; `look` (20 bits) : maillot (`look % 8`) et tenue (`look >> 4`) de P28."""
        return [{"id": r.id, "s": round(r.s, 2), "dir": r.dir, "v": round(r.v, 2), "lane_m": round(r.lane_m, 2),
                 "look": r.appearance} for r in self.near(rider_s)]

    def near(self, rider_s: float) -> list[Rider]:
        """Au plus STATE_MAX cyclistes à moins de NEAR_M du cycliste, du plus proche au plus loin."""
        close = [r for r in self.riders() if abs(r.s - rider_s) < NEAR_M]
        close.sort(key=lambda r: abs(r.s - rider_s))
        return close[:STATE_MAX]


def source_id(rider_id: str) -> str:
    """`draft_bot` d'un cycliste du décor."""
    return SOURCE_ID_PREFIX + rider_id


def is_source_id(draft_bot: Any) -> bool:
    return isinstance(draft_bot, str) and draft_bot.startswith(SOURCE_ID_PREFIX)


__all__ = ["RoadCyclists", "Rider", "DraftSource", "Group", "Member", "hash3", "mix", "power_for",
           "speed_on_grade", "cadence_rpm", "source_id", "is_source_id"]
