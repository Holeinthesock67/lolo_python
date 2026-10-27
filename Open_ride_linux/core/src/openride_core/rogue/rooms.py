"""Générateur de salles du mode Cyber-Rogue (lot R3).

Une salle est conçue en secondes (tronçons de pente et de puissance du Firewall), puis convertie en
mètres par la physique d'un cycliste qui tient la cible de chaque tronçon : celui-ci finit la salle
en `nominal_s`. Module pur et déterministe : mêmes arguments, même salle.
"""

from __future__ import annotations

import bisect
import math
import random
from dataclasses import astuple, dataclass
from functools import lru_cache

from ..physics import PhysicsParams, RiderPhysics, steady_speed
from .balance import DEFAULT_BALANCE, RogueBalance

ARCHETYPES = ("diesel", "puncheur", "grimpeur", "sprinteur", "saboteur", "boss")
OBJECTIVES = ("endurance", "seuil", "vo2max")
DS_M = 10.0               # pas du profil
DT_S = 0.5                # pas de la conception en temps
SUB_DT = 0.05             # pas de la physique du cycliste de référence
BOSS_PHASES = ("phase1", "phase2", "phase3")


@dataclass(frozen=True)
class RoomRider:
    """Cycliste de référence : FTP et physique (masse totale, CdA, Crr, rendement)."""
    ftp_w: float
    params: PhysicsParams


@dataclass(frozen=True)
class Marker:
    kind: str
    s_m: float
    len_m: float
    param: float | str | None = None


@dataclass(frozen=True)
class Stretch:
    """Tronçon [s0_m, s1_m) et fraction de FTP associée."""
    s0_m: float
    s1_m: float
    frac: float


@dataclass(frozen=True)
class Room:
    archetype: str
    variant: str
    objective: str
    length_m: float
    nominal_s: float
    profile: tuple              # ((s_m, grade_pct), ...) tous les 10 m
    time_s: tuple               # temps nominal d'arrivée à chaque point du profil
    markers: tuple              # Marker, triés par s_m
    firewall_plan: tuple        # Stretch : puissance du Firewall en fraction de FTP
    target_frac: tuple          # Stretch : cible de puissance du joueur (le rythme du Firewall)

    def to_message(self, room_id: int, next_room: dict | None = None) -> dict:
        """Message `room` de l'IPC 1.4 (une seule partie ; le découpage est fait par l'envoi)."""
        return {
            "type": "room", "v": 1, "room_id": room_id, "part": 1, "parts": 1,
            "archetype": self.archetype, "variant": self.variant,
            "length_m": self.length_m, "nominal_s": self.nominal_s,
            "profile": [[round(s, 1), round(g, 2)] for s, g in self.profile],
            "markers": [{"kind": m.kind, "s_m": round(m.s_m, 1), "len_m": round(m.len_m, 1),
                         "param": m.param} for m in self.markers],
            "next": next_room,
        }


@dataclass
class _Leg:
    dur: float
    g0: float
    g1: float
    fw: float
    tag: str = ""


@lru_cache(maxsize=65536)
def _speed(power_w: float, grade_pct: float, params: tuple) -> float:
    return steady_speed(power_w, grade_pct, PhysicsParams(*params))


# --- conception en temps -------------------------------------------------------------------

def _resolve_objective(archetype: str, objective: str, table: dict) -> str:
    """Colonne du tableau la plus proche de l'objectif demandé (ordre endurance < seuil < VO2max)."""
    avail = [o for o in OBJECTIVES if o in table[archetype]]
    want = OBJECTIVES.index(objective) if objective in OBJECTIVES else 1
    return min(avail, key=lambda o: (abs(OBJECTIVES.index(o) - want), OBJECTIVES.index(o)))


def _fill(cycle: list, total: float, min_bump: float) -> list:
    """Répète `cycle` jusqu'à `total` secondes. Un tronçon `bump` trop court est absorbé par le précédent."""
    legs: list[_Leg] = []
    t = 0.0
    while t < total - 1e-9:
        for leg in cycle:
            d = min(leg.dur, total - t)
            if d <= 1e-9:
                break
            if leg.tag == "bump" and d < min_bump and legs:
                legs[-1].dur += d
            else:
                legs.append(_Leg(d, leg.g0, leg.g1 if d == leg.dur else leg.g0
                                 + (leg.g1 - leg.g0) * d / leg.dur, leg.fw, leg.tag))
            t += d
            if t >= total - 1e-9:
                break
    return legs


def _diesel(p, T, rng, b):
    jitter = rng.uniform(-0.2, 0.2)
    g0, g1 = p["g0"] + jitter, p["g1"] + jitter
    return [_Leg(T, g0, g1, p["fw"], "ramp")]


def _puncheur(p, T, rng, b, variant):
    bump_s = p["bump_s"]
    fw_b, fw_v = p["fw_bump"], p["fw_valley"]
    if variant == "30_30" or bump_s < b.min_bump_s:
        variant = "30_30"
        bump_s, fw_b, fw_v = p["bump_s_30_30"], p["fw_bump_30_30"], p["fw_valley_30_30"]
    lead = float(rng.randint(0, 10))
    legs = [_Leg(min(lead, T), p["valley_grade"], p["valley_grade"], fw_v, "valley")] if lead > 0 else []
    rest = T - sum(l.dur for l in legs)
    cycle = [_Leg(p["valley_s"], p["valley_grade"], p["valley_grade"], fw_v, "valley"),
             _Leg(bump_s, p["bump_grade"], p["bump_grade"], fw_b, "bump")]
    return legs + _fill(cycle, rest, b.min_bump_s), variant


def _grimpeur(p, T, rng, b):
    legs, t, i = [], 0.0, 0
    steps = p["steps"]
    while t < T - 1e-9:
        g = steps[min(i, len(steps) - 1)]
        d = min(p["step_s"], T - t)
        if d < 20.0 and legs:               # palier final trop court : absorbé par le précédent
            legs[-1].dur += d
        else:
            legs.append(_Leg(d, g, g, p["fw"], "step"))
        t += d
        i += 1
    return legs


def _sprinteur(p, T, rng, b):
    offset = p["period_s"] - p["burst_s"] + rng.randint(0, 5) - 5     # première salve vers la fin de la période
    offset = max(offset, 5.0)
    legs, t = [], 0.0
    while t < T - 1e-9:
        calm = min(offset if t == 0 else p["period_s"] - p["burst_s"], T - t)
        legs.append(_Leg(calm, 0.0, 0.0, p["fw"], "calm"))
        t += calm
        burst = min(p["burst_s"], T - t)
        if burst >= p["burst_s"] - 1e-9:
            legs.append(_Leg(burst, 0.0, 0.0, p["burst_fw"], "burst"))
        elif burst > 0:
            legs.append(_Leg(burst, 0.0, 0.0, p["fw"], "calm"))
        t += burst
    return legs


def _saboteur(p, T, rng, b):
    p1, p2 = rng.uniform(30, 60), rng.uniform(30, 60)
    f1, f2 = rng.uniform(0, 2 * math.pi), rng.uniform(0, 2 * math.pi)
    mid, amp = (p["hi"] + p["lo"]) / 2, (p["hi"] - p["lo"]) / 2

    def g(t):
        return mid + amp * (0.5 * math.sin(2 * math.pi * t / p1 + f1) + 0.5 * math.sin(2 * math.pi * t / p2 + f2))

    legs, t = [], 0.0
    while t < T - 1e-9:
        d = min(5.0, T - t)
        legs.append(_Leg(d, g(t), g(t + d), p["fw"], "smooth"))
        t += d
    return legs


def _boss(p, T, phase, b):
    trans = min(b.transition_s, T)
    legs = [_Leg(trans, 0.0, 0.0, b.transition_frac, "transition")]
    combat = T - trans
    if combat <= 0:
        return legs
    if phase == "phase1":
        legs.append(_Leg(combat, p["p1_grade"], p["p1_grade"], p["p1_fw"], "ramp"))
    elif phase == "phase2":
        cycle = [_Leg(p["p2_block_s"], g, g, fw, "block") for g, fw in zip(p["p2_grades"], p["p2_fw"])]
        legs += _fill(cycle, combat, 0.0)
    else:
        legs.append(_Leg(combat, p["p3_grade"], p["p3_grade"], p["p3_fw"], "flat"))
    return legs


def _grid(legs: list, total: float):
    """Pente et fraction de FTP aux nœuds du pas de temps ; pente de chaque nœud avant l'étalement."""
    n = max(1, math.ceil(total / DT_S - 1e-9))
    times = [min(k * DT_S, total) for k in range(n + 1)]
    starts, t = [], 0.0
    for l in legs:
        starts.append(t)
        t += l.dur

    def leg_at(tt, right=True):
        i = bisect.bisect_right(starts, tt + (1e-9 if right else -1e-9)) - 1
        return legs[min(max(i, 0), len(legs) - 1)], starts[min(max(i, 0), len(legs) - 1)]

    grades = []
    for tt in times:
        l, t0 = leg_at(tt)
        u = (tt - t0) / l.dur if l.dur > 0 else 0.0
        grades.append(l.g0 + (l.g1 - l.g0) * min(max(u, 0.0), 1.0))
    return times, grades, starts, leg_at


def _slew_and_clamp(times, grades, b: RogueBalance):
    """Étale les chutes de pente plus rapides que `max_drop_pts` en 10 s ; borne la pente."""
    rate = b.max_drop_pts / 10.0
    out = [min(max(grades[0], b.room_grade_min), b.room_grade_max)]
    for k in range(1, len(grades)):
        g = min(max(grades[k], b.room_grade_min), b.room_grade_max)
        out.append(max(g, out[-1] - rate * (times[k] - times[k - 1])))
    return out


# --- génération ----------------------------------------------------------------------------

def generate_room(archetype: str, variant: str, objective: str, nominal_s: float, rider: RoomRider,
                  seed: int, balance: RogueBalance = DEFAULT_BALANCE) -> Room:
    """Salle `archetype` d'objectif `objective` (colonne la plus proche si le tableau n'en a pas).

    `variant` : "" (standard) ou "30_30" (Puncheur, bosses de 30 s) ; pour le boss "phase1", "phase2"
    ou "phase3". Pur et déterministe.
    """
    b = balance
    if archetype not in ARCHETYPES:
        raise ValueError(f"archétype inconnu : {archetype!r}")
    if not nominal_s > 0 or not math.isfinite(nominal_s):
        raise ValueError(f"nominal_s invalide : {nominal_s!r}")
    obj = _resolve_objective(archetype, objective, b.room_profiles)
    p = b.room_profiles[archetype][obj]
    rng = random.Random(f"{seed}|{archetype}|{variant}|{obj}|{nominal_s}")
    T = float(nominal_s)

    if archetype == "diesel":
        legs = _diesel(p, T, rng, b)
    elif archetype == "puncheur":
        legs, variant = _puncheur(p, T, rng, b, variant)
    elif archetype == "grimpeur":
        legs = _grimpeur(p, T, rng, b)
    elif archetype == "sprinteur":
        legs = _sprinteur(p, T, rng, b)
    elif archetype == "saboteur":
        legs = _saboteur(p, T, rng, b)
    else:
        if variant not in BOSS_PHASES:
            variant = "phase1"
        legs = _boss(p, T, variant, b)
    if archetype != "puncheur" and archetype != "boss":
        variant = ""

    times, raw, starts, leg_at = _grid(legs, T)
    grades = _slew_and_clamp(times, raw, b)

    # distance cumulée : un cycliste qui tient la cible de chaque tronçon, physique complète (inertie
    # comprise), parti à la vitesse d'équilibre du premier tronçon
    first = legs[0]
    body = RiderPhysics(rider.params, 0.0, _speed(round(first.fw * rider.ftp_w, 2), round(grades[0], 3),
                                                  astuple(rider.params)))
    dist = [0.0]
    for k in range(1, len(times)):
        tm = 0.5 * (times[k - 1] + times[k])
        leg, _ = leg_at(tm)
        g = 0.5 * (grades[k - 1] + grades[k])
        span = times[k] - times[k - 1]
        n_sub = max(1, round(span / SUB_DT))
        for _ in range(n_sub):
            body.step(leg.fw * rider.ftp_w, g, 0.0, span / n_sub)
        dist.append(max(body.s, dist[-1] + 1e-6))

    def s_of_t(t):
        k = min(max(bisect.bisect_right(times, t) - 1, 0), len(times) - 2)
        u = (t - times[k]) / (times[k + 1] - times[k])
        return dist[k] + (dist[k + 1] - dist[k]) * u

    def t_of_s(s):
        s = min(max(s, 0.0), dist[-1])
        k = min(max(bisect.bisect_right(dist, s) - 1, 0), len(dist) - 2)
        span = dist[k + 1] - dist[k]
        u = (s - dist[k]) / span if span > 0 else 0.0
        return times[k] + (times[k + 1] - times[k]) * u

    def grade_at_t(t):
        k = min(max(bisect.bisect_right(times, t) - 1, 0), len(times) - 2)
        u = (t - times[k]) / (times[k + 1] - times[k])
        return grades[k] + (grades[k + 1] - grades[k]) * u

    n = max(1, round(dist[-1] / DS_M))
    length = n * DS_M
    sample_t = [t_of_s(i * DS_M) for i in range(n + 1)]
    profile = tuple((i * DS_M, round(grade_at_t(sample_t[i]), 3)) for i in range(n + 1))
    time_s = tuple(round(t, 3) for t in sample_t)

    # tronçons de puissance en distance
    plan, t0 = [], 0.0
    for leg, st in zip(legs, starts):
        s0, s1 = s_of_t(st), s_of_t(st + leg.dur)
        if plan and abs(plan[-1].frac - leg.fw) < 1e-9:
            plan[-1] = Stretch(plan[-1].s0_m, s1, leg.fw)
        else:
            plan.append(Stretch(s0, s1, leg.fw))
    plan[-1] = Stretch(plan[-1].s0_m, length, plan[-1].frac)
    plan_t = tuple(plan)

    markers = [Marker(m.kind, m.s_m, round(min(m.len_m, length - m.s_m), 2), m.param)
               for m in _markers(archetype, variant, legs, starts, T, p, b, s_of_t, rng)
               if m.s_m <= length]       # la longueur est arrondie à 10 m : un marqueur au bout peut sortir
    return Room(archetype=archetype, variant=variant, objective=obj, length_m=length, nominal_s=T,
                profile=profile, time_s=time_s, markers=tuple(markers),
                firewall_plan=plan_t, target_frac=plan_t)


def _markers(archetype, variant, legs, starts, T, p, b, s_of_t, rng) -> list:
    out: list[Marker] = []

    def add(kind, t0, t1, param=None):
        if t0 < 0 or t1 > T + 1e-9:
            return
        s0 = s_of_t(t0)
        out.append(Marker(kind, round(s0, 2), round(s_of_t(t1) - s0, 2), param))

    # arches : une avant chaque rupture de pente d'au moins `break_min_pts`
    for i in range(1, len(legs)):
        delta = legs[i].g0 - legs[i - 1].g1
        if abs(delta) >= b.break_min_pts:
            add("arch", starts[i] - b.arch_lead_s, starts[i] - b.arch_lead_s, "up" if delta > 0 else "down")

    if archetype == "diesel":
        t = b.tunnel_period_s - b.tunnel_len_s
        while t + b.tunnel_len_s <= T:
            add("tunnel", t, t + b.tunnel_len_s, b.tunnel_cadence_rpm)
            add("strike_target", t + b.tunnel_len_s, t + b.tunnel_len_s, 1)
            t += b.tunnel_period_s
    elif archetype == "puncheur":
        for l, st in zip(legs, starts):
            if l.tag == "bump":
                add("parry_zone", st - b.parry_lead_s, st)
    elif archetype == "grimpeur":
        for l, st in zip(legs, starts):
            if l.tag == "step":
                add("strike_target", st + 0.35 * l.dur, st + 0.35 * l.dur, 1)
                add("rock", st + 0.65 * l.dur, st + 0.65 * l.dur, b.rock_armor)
    elif archetype == "sprinteur":
        for l, st in zip(legs, starts):
            if l.tag == "burst":
                add("pad", st, st + l.dur, b.pad_threshold_frac)
    elif archetype == "saboteur":
        t = b.purge_first_s
        while t <= T:
            add("purge", t, t, b.hack_delay_s)
            t += b.purge_period_s
    else:
        trans = min(b.transition_s, T)
        combat = T - trans
        if variant == "phase1" and combat > 0:
            for k in range(int(p["p1_locks"])):
                tt = trans + combat * (k + 1) / (p["p1_locks"] + 1)
                add("strike_target", tt, tt, 1)
        elif variant == "phase2" and combat > 0:
            tt = trans + p["shock_period_s"]
            while tt <= T:
                add("parry_zone", tt - b.parry_lead_s, tt)
                add("shockwave", tt, tt, None)
                tt += p["shock_period_s"]
    out.sort(key=lambda m: (m.s_m, m.kind))
    return out


# --- route en mémoire ----------------------------------------------------------------------

def room_to_route(room: Room):
    """Route sans GPS lue par `route.py` comme un parcours : droite vers l'est, pente de la salle."""
    from ..route import Route

    n = len(room.profile)
    alts, alt = [], 0.0
    for i, (_, g) in enumerate(room.profile):
        alts.append(round(alt, 3))
        if i + 1 < n:
            alt += DS_M * (g + room.profile[i + 1][1]) / 2 / 100.0
    return Route({
        "version": "1.0", "ds_m": DS_M, "n": n, "length_m": room.length_m, "type": "open",
        "lat": [0.0] * n, "lon": [0.0] * n, "alt_m": alts,
        "x": [i * DS_M for i in range(n)], "z": [0.0] * n,
        "grade_pct": [g for _, g in room.profile], "heading_deg": [90.0] * n,
    })
