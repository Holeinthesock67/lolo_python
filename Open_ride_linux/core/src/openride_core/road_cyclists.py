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

`lateral` (`lane_m` dans le contrat) : écart à l'axe, positif à droite du sens du parcours, comme `lane_m`
du lot AS2. Les positions `s` sont celles du parcours ouvert ; les bots sont donnés par leurs abscisses.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
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
FILE_GAP_M = 1.5
RIDER_HALF_WIDTH_M = 0.3
MIN_GAP_M = 0.7
EDGE_IN_M = 0.5
RIDER_LATERAL_M = 1.2     # RoadBuilder.RIDER_LATERAL_M (lot P32)
BOT_LATERAL_M = 2.1       # RoadBuilder.BOT_LATERAL_M (lot P32)
BOT_LOOK_M = 30.0
FALL_BACK_MPS = 0.5
CATCH_M = 4.0
LANE_FREE_M = 100.0
MIN_CENTRE_M = MIN_GAP_M + 2.0 * RIDER_HALF_WIDTH_M
GROUP_CLEAR_M = 30.0
VEHICLE_CLEAR_M = 60.0
SIDE_SPEED_MPS = 1.5
SIDE_LOOK_M = 2.5
SIDE_CLEAR_M = 0.8
SPEED_PERIOD_S = 1.0
SALUT_EVERY = 3
ROLL_N = 3.9
WEIGHT_N = 785.0
AIR_K = 0.21

# Lot AS7
CORE_BUDGET = 16          # living(high).cyclists : les groupes proches ne dépendent plus du préréglage
NEAR_M = 60.0             # cyclistes envoyés à l'engine dans `state` (devant ou derrière)
STATE_MAX = 6
SOURCE_ID_PREFIX = "rider:"   # `draft_bot` d'un cycliste du décor : « rider:<id> »


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
    col0: int | None = None
    dl0: float | None = None


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
                 road_width_m: float = 6.0, hold_after_pass: bool = True) -> None:
        self.route = route
        self.climbs = [(float(c[0]), float(c[1])) for c in climbs]
        self.villages = [(float(v[0]), float(v[1])) for v in villages]
        self.budget = max(0, int(budget))
        self.seed = int(seed)
        self.road_width_m = float(road_width_m)
        self.hold_after_pass = hold_after_pass
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

    def _edge_lateral(self) -> float:
        return max(self.road_width_m * 0.5 - EDGE_IN_M, RIDER_LATERAL_M + MIN_CENTRE_M)

    def update(self, rider_s: float, rider_v: float, dt_s: float, paused: bool = False,
               bots_s: Sequence[float] = ()) -> None:
        """Une image : `rider_s`, `rider_v` (m/s) du cycliste ; `bots_s` : abscisses des bots."""
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
                self._spawn(ev, rider_s, rider_v, bots_s)
        self._bot_groups = []
        for i, b in enumerate(bots_s):
            v_b = rider_v
            if i < len(self._last_bots_s) and dt_s > 0.0:
                v_b = max(0.0, (b - self._last_bots_s[i]) / dt_s)
            self._bot_groups.append(Group(
                id=f"bot{i}", case="bot", dir=1, s=float(b), flat_mps=v_b, delta_mps=0.0, power_w=0.0,
                speed_mps=v_b, salut=False, bot=True,
                members=[Member(dl=0.0, col=0, jersey=0, look=0, phase=0.0, index=0, lateral=BOT_LATERAL_M)]))
        self._last_bots_s = [float(b) for b in bots_s]
        kept = []
        for g in self.groups:
            self._move(g, rider_s, rider_v, dt_s, bots_s)
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

    def _spawn(self, ev: dict[str, Any], rider_s: float, rider_v: float, bots_s: Sequence[float] = (),
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
                jersey=hi % 8, look=(hi >> 4) & 0xFFFF, phase=_u(mix(hi + 1)), index=i))
        g = Group(id=f"c{ev['slot']}", case=case, dir=direction, s=s0, flat_mps=flat,
                  delta_mps=ev["kmh"] / 3.6, power_w=power_for(flat), speed_mps=flat, members=members,
                  salut=ev["salut"], side="left" if direction < 0 else "right")
        g.bot_near = self._bot_near(g, bots_s)
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

    def _bot_near(self, g: Group, bots_s: Sequence[float]) -> bool:
        head = g.s
        tail = head - g.dir * g.size * FILE_GAP_M
        lo, hi = min(head, tail) - BOT_LOOK_M, max(head, tail) + BOT_LOOK_M
        return any(lo < float(b) < hi for b in bots_s)

    def _target_lateral(self, g: Group, m: Member) -> float:
        own = self._base_lateral(g, m)
        if g.pass_lat is not None:
            return min(own, g.pass_lat) if g.dir == 1 else max(own, g.pass_lat)
        return own

    def _base_lateral(self, g: Group, m: Member) -> float:
        edge = self._edge_lateral()
        col = m.col * ABREAST_M
        if g.case == "oncoming":
            return -(self.road_width_m * 0.5 - EDGE_IN_M + col)
        if g.case == "overtake" and g.side == "left":
            return RIDER_LATERAL_M - MIN_CENTRE_M
        if g.bot_near:
            return max(edge, BOT_LATERAL_M + MIN_CENTRE_M)
        return edge + col

    def _move(self, g: Group, rider_s: float, rider_v: float, dt_s: float, bots_s: Sequence[float]) -> None:
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
        near = self._bot_near(g, bots_s)
        g.bot_near = near
        case = g.case
        spd_now = g.speed_mps
        rel_now = g.s - rider_s
        if case == "overtake":
            tail_now = rel_now - (g.size - 1) * FILE_GAP_M
            if g.side == "right" and rel_now >= -PASS_START_M and tail_now < MERGE_AHEAD_M:
                if near:
                    spd_now = min(spd_now, rider_v)
                else:
                    g.side = "left"
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
            pass_lat = own
            for _ in range(3):
                for h in alongside:
                    h_lat = h.lateral()
                    if abs(pass_lat - h_lat) < MIN_CENTRE_M:
                        pass_lat = h_lat - _sign(h_lat) * MIN_CENTRE_M
            slowest = math.inf
            blocking = False
            for h in near_groups:
                slowest = min(slowest, h.speed_mps)
                if (g.s - h.s) * direction < 0.0 and abs(cur - h.lateral()) < MIN_CENTRE_M - 0.05:
                    blocking = True
            crossing = False
            for h in alongside:
                h_lat = h.lateral()
                through = min(cur, pass_lat) < h_lat < max(cur, pass_lat)
                if through or (abs(pass_lat - h_lat) < MIN_CENTRE_M - 0.05
                               and abs(pass_lat - h_lat) < abs(cur - h_lat)):
                    crossing = True
                    slowest = min(slowest, h.speed_mps)
                    if (g.s - h.s) * direction < 0.0:
                        blocking = True
            faster = spd_now > slowest
            out = not blocking
            if crossing:
                if blocking:
                    spd_now = min(spd_now, slowest - FALL_BACK_MPS)
            elif faster and (out or self._lane_free_for(g, rider_s) and (
                    direction == -1 or abs(pass_lat - RIDER_LATERAL_M) >= MIN_CENTRE_M
                    or abs(g.s - rider_s) > PASS_START_M)):
                if abs(pass_lat - own) > 1e-3:
                    g.pass_lat = pass_lat
                if blocking:
                    spd_now = min(spd_now, slowest)
            elif blocking or not faster:
                spd_now = min(spd_now, slowest - FALL_BACK_MPS)
        g.s += direction * spd_now * dt_s
        rel = g.s - rider_s
        rel0 = rel if g.last_rel is None else g.last_rel
        g.last_rel = rel
        if case == "ahead":
            for i, m in enumerate(members):
                if m.col0 is None:
                    m.col0, m.dl0 = m.col, m.dl
                m.col = 0 if near else m.col0
                m.dl = float(i) * FILE_GAP_M if near else m.dl0
        for m in members:
            lat0 = m.lateral
            lat1 = _move_toward(lat0, self._target_lateral(g, m), SIDE_SPEED_MPS * dt_s)
            if self._side_blocked(g, g.s - direction * m.dl, lat0, lat1, rider_s, bots_s):
                lat1 = lat0
            m.lateral = lat1
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
                      bots_s: Sequence[float]) -> bool:
        if abs(lat1 - lat0) < 1e-6:
            return False
        near = []
        if abs(rider_s - s) < SIDE_LOOK_M:
            near.append(RIDER_LATERAL_M)
        for b in bots_s:
            if abs(float(b) - s) < SIDE_LOOK_M:
                near.append(BOT_LATERAL_M)
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
                                 group=g.id, case=g.case))
        return out

    def sources(self) -> list[DraftSource]:
        """Cyclistes du décor qui roulent dans le sens du parcours, comme sources d'abri de `draft.py`
        (id « rider:<id> », pour `draft_bot`) ; ceux d'en face n'abritent pas."""
        return [DraftSource(s=r.s, v=r.v, id=SOURCE_ID_PREFIX + r.id, lane_m=r.lane_m)
                for r in self.riders() if r.dir == 1]

    def state_list(self, rider_s: float) -> list[dict[str, Any]]:
        """Liste `riders` de `state` : au plus STATE_MAX cyclistes à moins de NEAR_M, du plus proche au plus
        loin ; `v` est signée (négative en face) pour que l'engine extrapole `s` entre deux trames."""
        near = sorted((r for r in self.riders() if abs(r.s - rider_s) < NEAR_M),
                      key=lambda r: abs(r.s - rider_s))[:STATE_MAX]
        return [{"id": r.id, "s": round(r.s, 2), "v": round(r.v * r.dir, 2), "lane_m": round(r.lane_m, 2),
                 "look": r.look} for r in near]


def source_id(rider_id: str) -> str:
    """`draft_bot` d'un cycliste du décor."""
    return SOURCE_ID_PREFIX + rider_id


def is_source_id(draft_bot: Any) -> bool:
    return isinstance(draft_bot, str) and draft_bot.startswith(SOURCE_ID_PREFIX)


__all__ = ["RoadCyclists", "Rider", "DraftSource", "Group", "Member", "hash3", "mix", "power_for",
           "speed_on_grade", "cadence_rpm", "source_id", "is_source_id"]
