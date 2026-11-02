"""Circulation de la route du parcours calculée par le core (lot AS6, série AS, version 2.0).

Module pur (aucune E/S hors `load_villages` et `snow_line`), portage de `engine/scripts/traffic_model.gd`
(lots P13, P25, P32) : même découpage en cases de `SLOT_M`, mêmes sortes et parts (`KINDS`), même tirage
(`hash3`, `_mix` de `vegetation_placer.gd`), mêmes règles de dépassement et de croisement. Le core devient
l'autorité des véhicules proches du cycliste : la physique (abri, aspiration) ne dépend jamais du
préréglage de qualité ; l'engine affiche la liste `vehicles` de `state` (au plus `NEAR_MAX` véhicules à
moins de `NEAR_M`) et ne garde que le décor lointain.

Nouveau cas : véhicule lent devant. Un tracteur, ou un utilitaire dans une montée de plus de
`SLOW_CLIMB_PCT`, tiré dans le même sens (`dir = +1`) et plus lent que le cycliste apparaît devant lui sur
la voie de droite (`slow`) ; le cycliste le rattrape et peut rester derrière ou le doubler (placement d'AS2).
Une fois dépassé, il suit les règles d'un véhicule qui double.

Abri derrière un véhicule (`vehicle_draft`) : même forme que la courbe de P3 (exponentielle en l'écart
entre l'arrière du véhicule et la roue avant), valeur à 3 m et portée propres à chaque sorte (`DRAFT`),
plafond `VEHICLE_ALPHA_CAP`. Points de départ, à recaler sur les mesures publiées :
- Kyle (1979), Ergonomics 22(4) : coureur derrière un véhicule d'entraînement, traînée réduite de plus de
  la moitié à faible distance ;
- Blocken et Toparlar (2015), J. Wind Eng. Ind. Aerodyn. 145, et Blocken, Toparlar et Andrianne (2016),
  J. Wind Eng. Ind. Aerodyn. 155 : véhicules d'accompagnement (voiture, moto) et sillage, ordre de grandeur
  de la portée (plusieurs longueurs de véhicule pour une voiture, beaucoup moins pour une moto).
Le facteur latéral d'AS2 (`draft.lateral_factor`) s'applique à l'écart hors de la largeur du véhicule :
tant que le cycliste est derrière la carrosserie, l'abri est entier.

Aspiration au dépassement (`pass_suction`) : toujours active, même abri coupé. Un véhicule qui double à
moins de `SUCTION_SIDE_M` (carrosserie à cycliste) donne une baisse de résistance en cloche dans le temps,
dont le pic (`SUCTION_PEAK`) se produit quand l'arrière du véhicule passe à la hauteur du cycliste et qui
retombe en moins d'une seconde de part et d'autre.

`lateral` (`lane_m` du contrat) est l'écart à l'axe, positif à droite du sens du parcours, comme `Lane.m`
d'AS2. Le parcours n'est pas bouclé pour la circulation (comme dans l'engine).
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import draft

MASK32 = 0xFFFFFFFF

SLOT_M = 250.0
BASE_RATE = 0.03
VILLAGE_RATE = 0.25
VILLAGE_NEAR_M = 1000.0
OVERTAKE_SHARE = 0.4
SPAWN_AHEAD_M = (600.0, 1200.0)
SPAWN_BEHIND_M = 250.0
REMOVE_BEHIND_M = 300.0
REMOVE_AHEAD_M = 1300.0
PASS_SPEED_KMH = 30.0
PASS_MARGIN_KMH = 10.0
PASS_ZONE_M = (-60.0, 30.0)      # de 60 m derrière à 30 m devant le cycliste : voie de gauche
FOLLOW_GAP_M = 25.0
MIN_SPACING_M = 60.0
MAX_GRADE_PCT = 8.0
DEFAULT_SNOW_LINE_M = 2200.0
RIDER_HALF_WIDTH_M = draft.RIDER_WIDTH_M / 2.0
LATERAL_CLEARANCE_M = 1.5
RIDER_LATERAL_M = draft.RIDER_LANE_M      # RoadBuilder.RIDER_LATERAL_M
RIGHT_LANE_M = 1.5                        # RoadBuilder.LANE_CENTER_M
LATERAL_MPS = 1.5
CYCLIST_GAP_M = 0.5
CYCLIST_LOOK_M = 40.0
CYCLIST_HALF_LENGTH_M = 0.9
LANE_FREE_M = 150.0
HOLD_GAP_M = 5.0
WHEEL_RADIUS_M = 0.33
COLORS = 8
SEED_SALT = 0x7AFF1C

# Sortes (lot P25) : demi-largeur et longueur hors tout de vehicle_mesh.gd, part des tirages et plage de
# vitesse (km/h). L'ordre compte (tirage cumulé de `pick_kind`), comme dans traffic_model.gd.
KINDS: dict[str, dict[str, Any]] = {
    "car_a": {"half_width": 1.03, "length": 4.6, "share": 0.3, "kmh": (50.0, 70.0)},
    "car_b": {"half_width": 1.0, "length": 4.1, "share": 0.25, "kmh": (50.0, 70.0)},
    "van": {"half_width": 1.12, "length": 5.2, "share": 0.13, "kmh": (50.0, 65.0)},
    "truck": {"half_width": 1.42, "length": 9.2, "share": 0.06, "kmh": (45.0, 60.0)},
    "bus": {"half_width": 1.44, "length": 12.2, "share": 0.04, "kmh": (45.0, 60.0)},
    "moto": {"half_width": 0.41, "length": 2.1, "share": 0.07, "kmh": (55.0, 80.0)},
    "tractor": {"half_width": 1.07, "length": 3.8, "share": 0.15, "kmh": (20.0, 30.0)},
}

# Lot AS6 : budget fixe (celui du préréglage high), quel que soit le préréglage de l'engine
BUDGET = 8
NEAR_M = 150.0            # véhicules envoyés à l'engine (liste `vehicles` de `state`)...
NEAR_MAX = 4              # ... au plus 4, les plus proches
# Véhicule lent devant
SLOW_KINDS = ("tractor",)
SLOW_CLIMB_KINDS = ("van",)
SLOW_CLIMB_PCT = 6.0
SLOW_CLIMB_KMH = (18.0, 26.0)     # utilitaire chargé en côte
SLOW_AHEAD_SCALE = 0.25           # apparaît à 150–300 m devant (un quart de SPAWN_AHEAD_M)
# Abri derrière un véhicule : (abri à 3 m de son arrière, portée en m)
DRAFT: dict[str, tuple[float, float]] = {
    "car_a": (0.45, 20.0),
    "car_b": (0.45, 20.0),
    "van": (0.50, 24.0),
    "truck": (0.60, 30.0),
    "bus": (0.60, 30.0),
    "moto": (0.15, 8.0),
    "tractor": (0.45, 20.0),
}
DRAFT_REF_GAP_M = 3.0
DRAFT_TAIL = 0.02          # abri restant au bout de la portée, coupé à 0 au-delà
VEHICLE_ALPHA_CAP = 0.60
VEHICLE_PREFIX = "veh:"    # `draft_bot` d'un véhicule
# Aspiration au dépassement
SUCTION_PEAK: dict[str, float] = {
    "car_a": 0.15, "car_b": 0.15, "van": 0.18, "truck": 0.30, "bus": 0.30, "moto": 0.05, "tractor": 0.12,
}
SUCTION_SIDE_FULL_M = 1.5     # pic entier jusqu'à 1,5 m entre carrosserie et cycliste...
SUCTION_SIDE_M = 2.5          # ... plus rien au-delà de 2,5 m
SUCTION_TAU_S = 0.35          # largeur de la cloche dans le temps (2 % du pic à 0,7 s)
SUCTION_MIN_REL_MPS = 0.5


# --- tirage (vegetation_placer.gd) -----------------------------------------------------------------

def _mix(h: int) -> int:
    h &= MASK32
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & MASK32
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & MASK32
    h ^= h >> 16
    return h


def hash3(a: int, b: int, c: int) -> int:
    h = _mix(a ^ 0x9E3779B9)
    h = _mix(h ^ (b & MASK32))
    return _mix(h ^ (c & MASK32))


def _u(h: int) -> float:
    return float(h & 0xFFFFFF) / 16777216.0


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _move_toward(a: float, b: float, step: float) -> float:
    return b if abs(b - a) <= step else a + math.copysign(step, b - a)


def pick_kind(u: float) -> str:
    """Sorte tirée d'après `u` (0 à 1) et les parts de KINDS, dans l'ordre de la table."""
    acc = 0.0
    for k, info in KINDS.items():
        acc += info["share"]
        if u < acc:
            return k
    return list(KINDS)[-1]


def lane_lateral(kind: str) -> float:
    """Écart du dépassant à la hauteur du cycliste : LATERAL_CLEARANCE_M entre sa carrosserie et le cycliste."""
    return RIDER_LATERAL_M - (RIDER_HALF_WIDTH_M + LATERAL_CLEARANCE_M + KINDS[kind]["half_width"])


def oncoming_lateral(kind: str) -> float:
    """Écart d'un véhicule en face : milieu de sa voie (sa droite), plus loin si le cycliste le demande."""
    return min(-RIGHT_LANE_M, lane_lateral(kind))


# --- données du monde -----------------------------------------------------------------------------

def load_villages(world_dir: Path, manifest: dict, length_m: float) -> list[tuple[float, float]]:
    """Points `village` (x, z) de la couche `poi` par tronçons de 1 km, comme living_decor.gd (`load_chunk`
    sans route : les mondes vivants n'en ont pas). Vide si la couche est absente ou illisible."""
    layers = manifest.get("layers")
    info = layers.get("poi") if isinstance(layers, dict) else None
    if not isinstance(info, dict) or info.get("present") is not True:
        return []
    out: list[tuple[float, float]] = []
    for k in range(max(1, math.ceil(length_m / 1000.0))):
        try:
            doc = json.loads((world_dir / "poi" / f"chunk_{k}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pts = doc.get("points") if isinstance(doc, dict) else None
        for p in pts if isinstance(pts, list) else []:
            if isinstance(p, dict) and p.get("kind") == "village" and all(
                    isinstance(p.get(c), (int, float)) and not isinstance(p.get(c), bool) for c in ("x", "z")):
                out.append((float(p["x"]), float(p["z"])))
    return out


def snow_line(theme: dict | None) -> float:
    """`terrain.snow_line_m` du thème, sinon DEFAULT_SNOW_LINE_M (comme traffic_model.gd)."""
    terrain = theme.get("terrain") if isinstance(theme, dict) else None
    v = terrain.get("snow_line_m") if isinstance(terrain, dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else DEFAULT_SNOW_LINE_M


# --- circulation ----------------------------------------------------------------------------------

@dataclass
class Vehicle:
    id: str
    kind: str
    color: int
    s: float
    dir: int
    cruise_mps: float
    speed_mps: float
    lateral: float
    passed: bool = False
    committed: bool = False
    slow: bool = False
    hold_s: float | None = None

    @property
    def half_width(self) -> float:
        return KINDS[self.kind]["half_width"]

    @property
    def length(self) -> float:
        return KINDS[self.kind]["length"]


@dataclass
class Other:
    """Coureur que les véhicules évitent (bot, plus tard cycliste du décor) : position, écart à l'axe, sens."""

    s: float
    lateral: float
    dir: int = 1


@dataclass
class Traffic:
    """Circulation de la route : `configure`, puis `update` à chaque pas du cycliste."""

    route: Any = None
    seed: int = 0
    budget: int = BUDGET
    villages: list[tuple[float, float]] = field(default_factory=list)
    snow_line_m: float = DEFAULT_SNOW_LINE_M
    vehicles: list[Vehicle] = field(default_factory=list)
    spawned_total: int = 0
    overtakes_total: int = 0
    _next_slot: int = 0
    _last_rider_s: float | None = None
    _others: list[Other] = field(default_factory=list)

    def reset(self) -> None:
        self.vehicles.clear()
        self.spawned_total = 0
        self.overtakes_total = 0
        self._next_slot = 0
        self._last_rider_s = None

    def slot_event(self, k: int) -> dict | None:
        """Lancer d'une case : None si elle ne porte rien, sinon le véhicule tiré (même tirage que l'engine)."""
        if self.route is None:
            return None
        s = (k + 0.5) * SLOT_M
        if s > self.route.length_m:
            return None
        smp = self.route.sample(s)
        if smp.alt_m > self.snow_line_m or abs(smp.grade_pct) > MAX_GRADE_PCT:
            return None
        rate = BASE_RATE
        for vx, vz in self.villages:
            if math.hypot(smp.x - vx, smp.z - vz) <= VILLAGE_NEAR_M:
                rate += VILLAGE_RATE
                break
        h = hash3(self.seed, k, SEED_SALT)
        if _u(h) >= rate:
            return None
        kind = pick_kind(_u(_mix(h + 1)))
        lo, hi = KINDS[kind]["kmh"]
        return {
            "slot": k,
            "kind": kind,
            "color": _mix(h + 2) % COLORS,
            "cruise_mps": _lerp(lo, hi, _u(_mix(h + 3))) / 3.6,
            "dir": 1 if _u(_mix(h + 4)) < OVERTAKE_SHARE else -1,
            "ahead_m": _lerp(SPAWN_AHEAD_M[0], SPAWN_AHEAD_M[1], _u(_mix(h + 5))),
            "u_speed": _u(_mix(h + 3)),
        }

    def _segment_ok(self, s: float) -> bool:
        if self.route is None or s < 0.0 or s > self.route.length_m:
            return False
        smp = self.route.sample(s)
        return smp.alt_m <= self.snow_line_m and abs(smp.grade_pct) <= MAX_GRADE_PCT

    def _free_at(self, s: float, d: int) -> bool:
        return all(not (v.dir == d and abs(v.s - s) < MIN_SPACING_M) for v in self.vehicles)

    def _overtaking(self) -> bool:
        """Un véhicule double le cycliste (un véhicule lent encore devant lui ne compte pas)."""
        return any(v.dir == 1 and not (v.slow and not v.passed) for v in self.vehicles)

    def _others_clear_at(self, s: float) -> bool:
        return all(abs(o.s - s) >= MIN_SPACING_M for o in self._others)

    def slow_cruise(self, ev: dict, s: float) -> float | None:
        """Vitesse d'un véhicule lent devant (lot AS6) tiré à `s`, None si la case n'en donne pas un."""
        if ev["dir"] != 1:
            return None
        if ev["kind"] in SLOW_KINDS:
            return ev["cruise_mps"]
        if ev["kind"] in SLOW_CLIMB_KINDS and self.route.grade_at(s) > SLOW_CLIMB_PCT:
            return _lerp(SLOW_CLIMB_KMH[0], SLOW_CLIMB_KMH[1], ev["u_speed"]) / 3.6
        return None

    def update(self, rider_s: float, rider_v: float, dt_s: float, paused: bool = False,
               others: Iterable[Other] = ()) -> None:
        """Un pas : `rider_s` position du cycliste (m), `rider_v` sa vitesse (m/s), `others` les bots."""
        if self.route is None or paused:
            return
        self._others = list(others)
        if self._last_rider_s is None:
            self._next_slot = max(0, math.floor(rider_s / SLOT_M) + 1)
        self._last_rider_s = rider_s
        while self._next_slot * SLOT_M <= rider_s:
            ev = self.slot_event(self._next_slot)
            self._next_slot += 1
            if ev is None or len(self.vehicles) >= self.budget:
                continue
            if ev["dir"] == -1:
                s0 = rider_s + ev["ahead_m"]
                if self._overtaking() or not self._segment_ok(s0) or not self._free_at(s0, -1) \
                        or not self._others_clear_at(s0):
                    continue
                self._spawn(ev, s0, -1)
                continue
            s2 = rider_s + ev["ahead_m"] * SLOW_AHEAD_SCALE
            slow = self.slow_cruise(ev, s2) if self._segment_ok(s2) else None
            if slow is not None and slow < rider_v:
                if self._free_at(s2, 1) and self._others_clear_at(s2):
                    self._spawn(dict(ev, cruise_mps=slow), s2, 1, slow=True)
                continue
            s1 = rider_s - SPAWN_BEHIND_M
            if self._overtaking() or not self._segment_ok(max(s1, 0.0)) or ev["cruise_mps"] <= rider_v \
                    or not self._others_clear_at(s1):
                continue
            self._spawn(ev, s1, 1)
        for v in self.vehicles:
            rel = v.s - rider_s
            if v.dir == -1:
                spd = v.cruise_mps
                for o in self.vehicles:
                    if o is not v and o.dir == -1 and o.s < v.s and v.s - o.s < MIN_SPACING_M + 20.0:
                        spd = min(spd, o.speed_mps)
                v.speed_mps = spd
                v.s -= spd * dt_s
                v.lateral = _move_toward(v.lateral, self._clear_of_others(v, oncoming_lateral(v.kind)),
                                         LATERAL_MPS * dt_s)
            elif v.slow and rel > 0.0 and not v.passed:
                self._move_slow(v, dt_s)
            else:
                self._move_overtaker(v, rel, rider_v, dt_s)
            self._hold(v)
        self.vehicles = [v for v in self.vehicles
                         if -REMOVE_BEHIND_M <= v.s - rider_s <= REMOVE_AHEAD_M and 0.0 <= v.s <= self.route.length_m]

    def _move_slow(self, v: Vehicle, dt_s: float) -> None:
        """Véhicule lent devant : sa vitesse, voie de droite ; une fois doublé, il devient un dépassant."""
        v.speed_mps = v.cruise_mps
        v.s += v.speed_mps * dt_s
        v.lateral = _move_toward(v.lateral, self._clear_of_others(v, RIGHT_LANE_M), LATERAL_MPS * dt_s)

    def _move_overtaker(self, v: Vehicle, rel: float, rider_v: float, dt_s: float) -> None:
        """Dépassement : voie de droite, puis voie de gauche dans PASS_ZONE_M (seulement si rien ne peut
        arriver en face avant la fin), retour à droite ; sans feu vert, il suit à FOLLOW_GAP_M."""
        if v.slow and not v.passed and rel <= 0.0:
            v.passed = True                      # le cycliste l'a doublé : il ne compte pas comme dépassement
            v.committed = False
        cruise = v.cruise_mps
        pass_mps = min(cruise, max(PASS_SPEED_KMH / 3.6, rider_v + PASS_MARGIN_KMH / 3.6))
        left = lane_lateral(v.kind)
        if not v.committed and PASS_ZONE_M[0] - 40.0 <= rel < 0.0 and pass_mps > rider_v \
                and self._clear_to_pass(v, rel, rider_v, pass_mps):
            v.committed = True
        spd, target_lat = cruise, RIGHT_LANE_M
        if v.committed and rel < PASS_ZONE_M[1]:
            spd = pass_mps
            target_lat = left if rel >= PASS_ZONE_M[0] else RIGHT_LANE_M
            if abs(v.lateral - left) > 0.05 and rel > -FOLLOW_GAP_M:
                spd = min(spd, rider_v)
        elif not v.committed:
            if rel >= PASS_ZONE_M[0] - 40.0:
                spd = pass_mps
            if rel + (spd - rider_v) * dt_s >= -FOLLOW_GAP_M:
                spd = min(spd, rider_v)          # il ne s'approche pas (un véhicule lent doublé reste lent)
        v.speed_mps = spd
        v.s += spd * dt_s
        v.lateral = _move_toward(v.lateral, self._clear_of_others(v, target_lat), LATERAL_MPS * dt_s)
        if not v.passed and rel > 0.0:
            v.passed = True
            self.overtakes_total += 1

    def _clear_of_others(self, v: Vehicle, target: float) -> float:
        """Écart visé, décalé pour ne toucher aucun bot (comme traffic_model.gd `_clear_of_others`).

        Lot AS6 : un véhicule lent garde sa ligne face aux coureurs du même sens qui le longent ou le
        doublent (ce sont eux qui s'écartent, placement d'AS2) et ne double jamais un coureur : il attend
        derrière."""
        half_len = v.length * 0.5 + CYCLIST_HALF_LENGTH_M
        out = target
        v.hold_s = None
        for same in (True, False):
            for o in self._others:
                if (o.dir == v.dir) != same:
                    continue
                ahead = (o.s - v.s) * v.dir
                if ahead < -half_len or ahead > half_len + CYCLIST_LOOK_M or (v.slow and same and ahead <= half_len):
                    continue
                room = RIDER_HALF_WIDTH_M + (LATERAL_CLEARANCE_M if same else CYCLIST_GAP_M) + v.half_width
                if same and ahead > half_len and abs(v.lateral - o.lateral) < room - 0.05:
                    self._hold_behind(v, o.s)
                if abs(out - o.lateral) >= room:
                    continue
                if same and ahead > half_len and (v.slow or not self._lane_free(v)):
                    self._hold_behind(v, o.s)
                    continue
                out = o.lateral - room if out < o.lateral else o.lateral + room
        return out

    @staticmethod
    def _hold_behind(v: Vehicle, s: float) -> None:
        if v.hold_s is None or (s - v.hold_s) * v.dir < 0.0:
            v.hold_s = s

    def _lane_free(self, v: Vehicle) -> bool:
        for o in self._others:
            ahead = (o.s - v.s) * v.dir
            if o.dir != v.dir and -5.0 < ahead < LANE_FREE_M:
                return False
        for o in self.vehicles:
            ahead = (o.s - v.s) * v.dir
            if o.dir != v.dir and -5.0 < ahead < LANE_FREE_M:
                return False
        if v.dir == -1 and self._last_rider_s is not None and -5.0 < v.s - self._last_rider_s < LANE_FREE_M:
            return False
        return True

    @staticmethod
    def _hold(v: Vehicle) -> None:
        if v.hold_s is None:
            return
        limit = v.hold_s - v.dir * (v.length * 0.5 + CYCLIST_HALF_LENGTH_M + HOLD_GAP_M)
        if (v.s - limit) * v.dir > 0.0:
            v.s = limit

    def _clear_to_pass(self, v: Vehicle, rel: float, rider_v: float, pass_mps: float) -> bool:
        t_pass = (PASS_ZONE_M[1] - rel) / max(pass_mps - rider_v, 0.5)
        for o in self._others:
            gap = o.s - v.s
            if o.dir == -1 and 0.0 < gap < t_pass * (10.0 + pass_mps) + 100.0:
                return False
        for o in self.vehicles:
            gap = o.s - v.s
            if o.dir == -1 and 0.0 < gap < t_pass * (o.speed_mps + pass_mps) + 100.0:
                return False
        return True

    def _spawn(self, ev: dict, s: float, d: int, slow: bool = False) -> Vehicle:
        self.spawned_total += 1
        v = Vehicle(id=f"v{ev['slot']}", kind=ev["kind"], color=ev["color"], s=s, dir=d,
                    cruise_mps=ev["cruise_mps"], speed_mps=ev["cruise_mps"],
                    lateral=oncoming_lateral(ev["kind"]) if d == -1 else RIGHT_LANE_M, slow=slow)
        self.vehicles.append(v)
        return v

    def place_for_test(self, rider_s: float, kind: str, d: int, rel_m: float, kmh: float,
                       lateral: float | None = None) -> Vehicle:
        """Véhicule posé par un test ou un banc : `slow` s'il roule devant, dans le même sens."""
        ev = {"slot": 1000000 + self.spawned_total, "kind": kind, "color": self.spawned_total % COLORS,
              "cruise_mps": kmh / 3.6}
        v = self._spawn(ev, rider_s + rel_m, 1 if d >= 0 else -1, slow=d >= 0 and rel_m > 0.0)
        if lateral is not None:
            v.lateral = lateral
        return v

    def near(self, rider_s: float) -> list[Vehicle]:
        """Au plus NEAR_MAX véhicules à moins de NEAR_M du cycliste, du plus proche au plus loin."""
        close = [v for v in self.vehicles if abs(v.s - rider_s) < NEAR_M]
        close.sort(key=lambda v: abs(v.s - rider_s))
        return close[:NEAR_MAX]


def state_list(vehicles: Iterable[Vehicle]) -> list[dict]:
    """Liste `vehicles` de `state` (au centimètre) : {id, kind, color, s, dir, v, lane_m}."""
    return [{"id": v.id, "kind": v.kind, "color": v.color, "s": round(v.s, 2), "dir": v.dir,
             "v": round(v.speed_mps, 2), "lane_m": round(v.lateral, 2)} for v in vehicles]


# --- abri et aspiration ---------------------------------------------------------------------------

def vehicle_coefficient(kind: str, gap_m: float) -> float:
    """Abri derrière un véhicule de sorte `kind` à `gap_m` (m) de son arrière ; 0 devant et au-delà de la portée."""
    at3, reach = DRAFT[kind]
    if gap_m < 0.0 or gap_m > reach:
        return 0.0
    decay = (reach - DRAFT_REF_GAP_M) / math.log(at3 / DRAFT_TAIL)
    return min(at3 * math.exp(-(gap_m - DRAFT_REF_GAP_M) / decay), VEHICLE_ALPHA_CAP)


def vehicle_lateral_factor(kind: str, dx_m: float) -> float:
    """Facteur latéral d'AS2 compté depuis le bord de la carrosserie : entier derrière le véhicule."""
    return draft.lateral_factor(max(abs(dx_m) - (KINDS[kind]["half_width"] - RIDER_HALF_WIDTH_M), 0.0))


def vehicle_draft(rider_s: float, rider_lane_m: float, vehicles: Iterable[Vehicle], rider_v: float = 0.0,
                  head_mps: float = 0.0, cross_mps: float = 0.0) -> tuple[float, str | None]:
    """Abri le plus fort derrière un véhicule du même sens devant le cycliste et `veh:<id>` de celui-ci."""
    best, best_id = 0.0, None
    for v in vehicles:
        if v.dir != 1:
            continue
        gap = v.s - v.length * 0.5 - rider_s - draft.BIKE_LENGTH_M * 0.5
        shift = draft.crosswind_shift_m(gap, rider_v, head_mps, cross_mps)   # zone abritée sous le vent (lot AS3)
        a = vehicle_coefficient(v.kind, gap) * vehicle_lateral_factor(v.kind, rider_lane_m - v.lateral - shift)
        if a > best:
            best, best_id = a, VEHICLE_PREFIX + v.id
    if best_id is None:
        return 0.0, None
    return best * draft.crosswind_residual(rider_v, head_mps, cross_mps), best_id


def suction_side_factor(clear_m: float) -> float:
    """Part du pic d'aspiration à `clear_m` entre la carrosserie et le cycliste : 1 jusqu'à 1,5 m, 0 à 2,5 m."""
    if clear_m <= SUCTION_SIDE_FULL_M:
        return 1.0
    if clear_m >= SUCTION_SIDE_M:
        return 0.0
    return 0.5 * (1.0 + math.cos(math.pi * (clear_m - SUCTION_SIDE_FULL_M) / (SUCTION_SIDE_M - SUCTION_SIDE_FULL_M)))


def pass_suction(rider_s: float, rider_v: float, rider_lane_m: float, vehicles: Iterable[Vehicle]) -> float:
    """Baisse de résistance due aux véhicules qui doublent le cycliste (0 à SUCTION_PEAK de la sorte)."""
    best = 0.0
    for v in vehicles:
        rel_v = v.speed_mps - rider_v
        if v.dir != 1 or rel_v <= 0.0:
            continue
        clear = abs(rider_lane_m - v.lateral) - v.half_width - RIDER_HALF_WIDTH_M
        side = suction_side_factor(clear)
        if side <= 0.0:
            continue
        t = (v.s - v.length * 0.5 - rider_s) / max(rel_v, SUCTION_MIN_REL_MPS)   # < 0 : l'arrière n'est pas passé
        best = max(best, SUCTION_PEAK[v.kind] * side * math.exp(-(t / SUCTION_TAU_S) ** 2))
    return best
