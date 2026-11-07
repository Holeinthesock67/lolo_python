"""Simulateur d'équilibrage de la Course tactique (série CT, lot CT0).

    python -m openride_core.tools.tactical_sim [--races 200] [--seed 1] [--circuits plat,col,...]
        [--strategies suceur,rouleur,...] [--balance FICHIER.toml] [--report FICHIER.md] [--json] [--jobs N]

Courses de 4 bots à profil (grimpeur, rouleur, sprinteur, diesel, profils du lot T12) et d'un cycliste
virtuel, en temps accéléré (pas de `dt_s`, 0,5 s), sans trainer ni engine, sur des circuits générés (bouchon
de CT8 : profils en pente seulement, sans virage). Chaque course tire la forme du jour de chacun (± 3 % de CP),
les relais et les attaques des bots à partir de la graine : même graine, même rapport à l'octet près, quel
que soit `--jobs`.

Règles du mode appelées par leurs fonctions pures (`tactical/bouchons.py`, à remplacer par CT2 à CT6) :
réserve W′ de Skiba (`rogue/wbal.py`) et Burnout à 70 % de la CP pendant 8 s pour tout le monde (CT2),
catapulte chargée par l'abri (CT4), crédits gagnés en tête et capacités du catalogue 4.0 (CT6, cycliste
seulement : les bots n'ont pas de bonus, décision du 29 octobre pour la 4.0). L'abri est celui de `draft.py`
en une dimension (file indienne : `K_LINE` pour les sources cachées, plafond de groupe `ALPHA_GROUP_CAP`).

Stratégies du cycliste virtuel : `suceur` (jamais devant), `rouleur` (relais réguliers), `attaquant` (contre
quand un bot de son groupe passe sous 10 % de réserve), `echappee` (seul devant dès le départ), `mixte`
(relais sur le plat, attaque en montée). Rapport : taux de victoire par stratégie et par profil, Burnouts,
catapultes et capacités par course, écarts à l'arrivée, et les critères du cahier CT0 §7.
Code 0 si les critères 2 et 3 sont tenus, 1 sinon, 2 pour un appel invalide.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..bots import FOLLOW_GAIN, FOLLOW_GAP_M, FOLLOW_MIN_CP, FOLLOW_TAU_S, PROFILES
from ..draft import ALPHA_GROUP_CAP, BIKE_LENGTH_M, GAP_CUTOFF_M, K_LINE, draft_coefficient
from ..physics import PhysicsParams, RiderPhysics, draft_saving_w, resistive_force, steady_speed
from ..rogue.balance import BalanceError
from ..rogue.wbal import WbalState, wbal_initial, wbal_step
from ..tactical import bouchons as rules
from ..tactical.balance import DEFAULT_BALANCE, TacticalBalance, balance_hash, load_balance

STRATEGIES = ("suceur", "rouleur", "attaquant", "echappee", "mixte")
BOT_PROFILES = ("climber", "rouleur", "sprinter", "diesel")
RIDER_ID = "rider"
CLIMB_GRADE_PCT = 2.0           # au-dessus : stratégie « montée » des bots (plat en dessous, comme Y10)
GROUP_LOOK_M = 30.0             # coureurs à moins de 30 m : même groupe (pour l'attaquant)
START_GAP_M = 2.0               # grille de départ : un coureur tous les 2 m
START_V_MPS = 8.0               # départ lancé, sans la mise en route
MAX_RACE_S = 4 * 3600.0
MAX_WIN_PCT = 45.0              # critère 2 du cahier : aucune stratégie au-dessus de 45 %...
MAX_BREAKAWAY_PCT = 20.0        # ... et l'échappée solitaire sous 20 %


@dataclass(frozen=True)
class Circuit:
    """Circuit généré (bouchon de CT8) : tronçons (longueur en m, pente en %), sans virage."""

    name: str
    title: str
    parts: tuple[tuple[float, float], ...]

    @property
    def length_m(self) -> float:
        return sum(p[0] for p in self.parts)


def _repeat(n: int, *parts: tuple[float, float]) -> tuple[tuple[float, float], ...]:
    return tuple(parts) * n


CIRCUITS: dict[str, Circuit] = {c.name: c for c in (
    Circuit("plat", "12 km de plat, arrivée au sprint", ((12000.0, 0.0),)),
    Circuit("vallonne", "15 km de bosses de 800 m à 4 %", _repeat(6, (1700.0, 0.0), (800.0, 4.0))),
    Circuit("col", "6 km de plat puis 5 km à 7 %", ((6000.0, 0.0), (5000.0, 7.0))),
    Circuit("bosse_finale", "10 km de plat puis 1 km à 5 % et 300 m de plat",
            ((10000.0, 0.0), (1000.0, 5.0), (300.0, 0.0))),
    Circuit("col_puis_plat", "4 km de plat, 3 km à 6 % puis 6 km de plat",
            ((4000.0, 0.0), (3000.0, 6.0), (6000.0, 0.0))),
    Circuit("bosses_puis_plat", "4 bosses de 600 m à 5 % puis 4 km de plat",
            _repeat(4, (1500.0, 0.0), (600.0, 5.0)) + ((4000.0, 0.0),)),
    Circuit("faux_plat", "14 km de faux plat à 2,5 %", ((14000.0, 2.5),)),
)}


class Profile:
    """Pente le long du circuit (recherche dichotomique sur les débuts de tronçon)."""

    def __init__(self, circuit: Circuit) -> None:
        self.starts: list[float] = []
        self.grades: list[float] = []
        s = 0.0
        for length, grade in circuit.parts:
            self.starts.append(s)
            self.grades.append(grade)
            s += length
        self.length_m = s

    def grade(self, s: float) -> float:
        i = bisect.bisect_right(self.starts, max(s, 0.0)) - 1
        return self.grades[min(max(i, 0), len(self.grades) - 1)]


@dataclass
class Runner:
    """Un coureur de la course simulée : le cycliste virtuel (`strategy`) ou un bot à profil (`profile`)."""

    id: str
    profile: str                       # « rider » ou un profil de bot
    strategy: str | None
    params: PhysicsParams
    cp_w: float
    w_prime_j: float
    phys: RiderPhysics
    wbal: WbalState
    peak_w: float = 0.0
    burn: rules.Burnout = field(default_factory=rules.Burnout)
    alpha: float = 0.0
    wheel: "Runner | None" = None      # coureur juste devant à moins de 15 m
    wheel_gap_m: float = 0.0
    front: bool = False                # personne devant à moins de 15 m
    saved_for_others_w: float = 0.0    # watts économisés par les suiveurs dont il est la première source
    relay_s: float = 0.0
    relay_target_s: float = 0.0
    pending_j: float = 0.0
    work_j: float = 0.0
    spent_pct: float = 0.0
    pull_left_s: float = 0.0
    rest_s: float = 0.0
    chasing: bool = False
    chase_ok: bool = False
    reckless: bool = False
    dropped: bool = False
    attack_at_m: float | None = None
    attack_left_s: float = 0.0
    attacked: bool = False
    peak_used_s: float = 0.0
    sling_pct: float = 0.0
    sling_left_s: float = 0.0
    sling_launch_pct: float = 0.0
    sling_cool_s: float = 0.0
    ability: str | None = None
    ability_left_s: float = 0.0
    finish_s: float | None = None
    power_w: float = 0.0
    burnouts: int = 0
    slings: int = 0
    abilities: int = 0
    climb_attacked: set = field(default_factory=set)
    climb_starts: list = field(default_factory=list)   # débuts des montées (stratégie « mixte »)
    chase_gap_m: float | None = None   # écart au coureur devant hors de portée d'abri (moins de `bot_chase_look_m`)

    @property
    def s(self) -> float:
        return self.phys.s

    @property
    def v(self) -> float:
        return self.phys.v

    @property
    def reserve_pct(self) -> float:
        return 100.0 * self.wbal.w_bal_j / self.w_prime_j

    @property
    def gauge_pct(self) -> float:
        return max(rules.credits_pct(self.work_j, self._bal) - self.spent_pct, 0.0)

    _bal: TacticalBalance = DEFAULT_BALANCE

    def has(self, ability: str) -> bool:
        return self.ability == ability and self.ability_left_s > 0.0


# --- calibrage des bots ---------------------------------------------------------------------------------
# Une échelle commune à tous les bots (et non une par profil comme T13 en séance) : les forces relatives des
# profils validées le 27 octobre (lot T12) restent entières, chaque profil garde son terrain. L'échelle donne
# au peloton des bots, seuls et à leur stratégie, le temps moyen du cycliste seul à `bots_level_pct` % de FTP.

def _solo_time(parts: tuple[tuple[float, float], ...], params: PhysicsParams, power_of) -> float:
    return sum(length / max(steady_speed(power_of(grade), grade, params), 0.1) for length, grade in parts)


def _bot_time(profile: str, circuit: Circuit, scale: float, bal: TacticalBalance) -> float:
    spec = PROFILES[profile]
    params = PhysicsParams(mass_kg=spec.mass_kg + bal.bike_mass_kg)
    cp = spec.cp_wkg * spec.mass_kg * scale
    return _solo_time(circuit.parts, params, lambda g: (spec.climb if g >= CLIMB_GRADE_PCT else spec.flat) * cp)


def calibration(circuit: Circuit, bal: TacticalBalance) -> dict[str, float]:
    """Échelle de CP des bots sur le circuit (la même pour tous les profils)."""
    rider = PhysicsParams(mass_kg=bal.rider_mass_kg + bal.bike_mass_kg)
    p = bal.rider_ftp_w * bal.bots_level_pct / 100.0
    target = _solo_time(circuit.parts, rider, lambda g: p)
    lo, hi = 0.3, 3.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        mean = sum(_bot_time(name, circuit, mid, bal) for name in BOT_PROFILES) / len(BOT_PROFILES)
        if mean > target:
            lo = mid
        else:
            hi = mid
    scale = 0.5 * (lo + hi)
    return {name: scale for name in BOT_PROFILES}


# --- une course --------------------------------------------------------------------------------------------

def _make_field(strategy: str, scales: dict[str, float], bal: TacticalBalance, rng: random.Random,
                length_m: float) -> list[Runner]:
    def form() -> float:
        return 1.0 + bal.form_spread_pct / 100.0 * (2.0 * rng.random() - 1.0)

    out = []
    rp = PhysicsParams(mass_kg=bal.rider_mass_kg + bal.bike_mass_kg)
    cp = bal.rider_ftp_w * form()
    out.append(Runner(RIDER_ID, RIDER_ID, strategy, rp, cp, bal.rider_w_prime_j, RiderPhysics(rp, 0.0, START_V_MPS),
                      wbal_initial(bal.rider_w_prime_j)))
    for i, name in enumerate(BOT_PROFILES):
        spec = PROFILES[name]
        scale = scales[name]
        params = PhysicsParams(mass_kg=spec.mass_kg + bal.bike_mass_kg)
        w = spec.w_prime_j * scale
        r = Runner(f"b{i + 1}", name, None, params, spec.cp_wkg * spec.mass_kg * scale * form(), w,
                   RiderPhysics(params, -(i + 1) * START_GAP_M, START_V_MPS), wbal_initial(w),
                   peak_w=spec.peak_wkg * spec.mass_kg * scale)
        ch = spec.character
        if rng.random() < ch.sprint_attack_chance:
            r.attack_at_m = bal.bot_attack_to_m + rng.random() * (bal.bot_attack_from_m - bal.bot_attack_to_m)
        out.append(r)
    for r in out:
        r._bal = bal
    return out


def _shelter(runners: list[Runner], bal: TacticalBalance) -> None:
    """Abri de chacun (file indienne de `draft.py`), roue devant, coureur en tête et watts donnés aux suiveurs."""
    ordered = sorted(runners, key=lambda r: (-r.s, r.id))
    for r in ordered:
        r.saved_for_others_w = 0.0
    for i, r in enumerate(ordered):
        alphas = []
        r.wheel = None
        for o in reversed(ordered[:i]):            # du plus proche au plus loin devant
            gap = o.s - r.s - BIKE_LENGTH_M
            if gap > GAP_CUTOFF_M:
                break
            if r.wheel is None:
                r.wheel, r.wheel_gap_m = o, gap
            if not o.has("breakaway"):
                alphas.append(draft_coefficient(gap))
        r.front = r.wheel is None
        r.chase_gap_m = None
        if r.front and i > 0:
            gap = ordered[i - 1].s - r.s
            if gap <= bal.bot_chase_look_m:
                r.chase_gap_m = gap
        if alphas:
            keep = 1.0 - alphas[0]
            for a in alphas[1:]:
                keep *= 1.0 - K_LINE * a
            r.alpha = min(1.0 - keep, ALPHA_GROUP_CAP)
        else:
            r.alpha = 0.0
        if r.wheel is not None and r.alpha > 0.0:
            r.wheel.saved_for_others_w += draft_saving_w(r.v, 0.0, r.params, r.alpha)
    # le premier d'une file reçoit les watts de toute la file qui le suit, qu'il emmène
    for r in ordered:
        if not r.front and r.wheel is not None and r.saved_for_others_w > 0.0:
            head = r.wheel
            while not head.front and head.wheel is not None:
                head = head.wheel
            head.saved_for_others_w += r.saved_for_others_w
            r.saved_for_others_w = 0.0


def _need_w(r: Runner, grade: float) -> float:
    """Puissance pour tenir la roue de devant (lot AS1 : `ProfileBot._follow_power`, sans plafond)."""
    lead = r.wheel
    v = r.v
    v_want = max(lead.v + FOLLOW_GAIN * (r.wheel_gap_m - FOLLOW_GAP_M), 0.0)
    force = resistive_force(v_want, grade, 0.0, r.params, r.alpha)
    need = (force * v_want + r.params.mass_kg * (v_want - v) / FOLLOW_TAU_S * v) / r.params.efficiency
    return max(need, FOLLOW_MIN_CP * r.cp_w)


def _launch_sling(r: Runner, bal: TacticalBalance) -> None:
    if r.sling_cool_s <= 0.0 and r.sling_left_s <= 0.0 and r.sling_pct >= bal.sling_min_pct:
        r.sling_launch_pct, r.sling_pct = r.sling_pct, 0.0
        r.sling_left_s, r.sling_cool_s = bal.sling_boost_s, bal.sling_cooldown_s
        r.slings += 1


def _relay(r: Runner, normal_w: float, dt: float, bal: TacticalBalance) -> float:
    """Relais : en tête avec des suiveurs pendant `relay_target_s`, puis on lève le pied pour se faire doubler."""
    if r.pull_left_s > 0.0:
        if not r.front:                             # doublé : le relais est fini
            r.pull_left_s, r.rest_s = 0.0, 20.0
            return normal_w
        r.pull_left_s -= dt
        return normal_w * bal.pull_off_pct / 100.0
    if r.front and r.saved_for_others_w > 0.0:
        r.relay_s += dt
        if r.relay_s >= r.relay_target_s:
            r.pull_left_s, r.relay_s = bal.pull_off_max_s, 0.0
    elif not r.front:
        r.relay_s = 0.0
    return normal_w


def _follow_or_drop(r: Runner, strategy_w: float, grade: float, follow_cap_w: float, rng: random.Random,
                    bal: TacticalBalance) -> float:
    """Suivre ou lâcher (bouchon de CT3) : dans la roue on prend ce qu'il faut ; si la roue accélère au-delà
    de la stratégie, on suit jusqu'à `follow_cap_w` tant que la réserve le permet, sinon on lâche."""
    wheel = r.wheel
    if wheel is None or wheel.pull_left_s > 0.0:
        r.chasing = False
        return strategy_w
    need = _need_w(r, grade)
    if need <= strategy_w:
        r.chasing = False
        return need
    if not r.chasing:                              # une accélération devant : on décide une fois
        r.chasing = True
        r.reckless = r.profile != RIDER_ID and rng.random() < bal.bot_error_pct / 100.0
        r.chase_ok = (r.profile == RIDER_ID or r.reserve_pct > bal.bot_follow_reserve_pct or r.reckless) \
            and not wheel.has("breakaway")
    stop_pct = bal.rider_cut_pct if r.profile == RIDER_ID else bal.bot_follow_stop_pct
    if r.chase_ok and r.reserve_pct < stop_pct and not r.reckless:
        r.chase_ok = False                         # il lâche ; le bot imprudent suit jusqu'à exploser
    return min(need, follow_cap_w) if r.chase_ok else strategy_w


def _bot_power(r: Runner, grade: float, to_go: float, dt: float, rng: random.Random, bal: TacticalBalance) -> float:
    spec = PROFILES[r.profile]
    climbing = grade >= CLIMB_GRADE_PCT
    base = (spec.climb if climbing else spec.flat) * r.cp_w
    tactical = False
    if r.peak_w > 0.0 and to_go <= spec.sprint_last_m and r.peak_used_s < spec.peak_s:
        r.peak_used_s += dt
        base, tactical = r.peak_w, True
    elif r.peak_w <= 0.0 and to_go <= bal.bot_sprint_m:
        base, tactical = bal.bot_sprint_cp_pct / 100.0 * r.cp_w, True
    elif climbing and spec.climb_attack > 0.0 and r.reserve_pct > bal.bot_climb_attack_reserve_pct:
        base, tactical = bal.bot_climb_attack_cp_pct / 100.0 * r.cp_w, True
    elif r.attack_at_m is not None and to_go <= r.attack_at_m and not r.attacked:
        r.attacked, r.attack_left_s = True, math.inf    # attaque au long cours, jusqu'à vider sa réserve
    if r.attack_left_s > 0.0 and not tactical:
        if r.reserve_pct > bal.bot_attack_stop_pct:
            base, tactical = bal.bot_attack_cp_pct / 100.0 * r.cp_w, True
        else:
            r.attack_left_s = 0.0
    if tactical:
        _launch_sling(r, bal)
        r.chasing = False
        return base
    if r.front and r.reserve_pct > bal.bot_relay_reserve_pct and r.chase_gap_m is not None:
        base = max(base, bal.bot_chase_cp_pct / 100.0 * r.cp_w)   # poursuite d'un coureur parti devant
    relays = spec.character.relays and r.reserve_pct > bal.bot_relay_reserve_pct
    if r.relay_s <= 0.0 and r.pull_left_s <= 0.0:
        u = min(max((r.reserve_pct - bal.bot_relay_reserve_pct) / (100.0 - bal.bot_relay_reserve_pct), 0.0), 1.0)
        r.relay_target_s = (bal.bot_relay_min_s + u * (bal.bot_relay_max_s - bal.bot_relay_min_s)) if relays else 5.0
    base = _relay(r, base, dt, bal) if not climbing else base
    return _follow_or_drop(r, base, grade, bal.bot_follow_cp_pct / 100.0 * r.cp_w, rng, bal)


def _rider_power(r: Runner, runners: list[Runner], grade: float, to_go: float, dt: float, rng: random.Random,
                 bal: TacticalBalance) -> float:
    cp = r.cp_w
    st = r.strategy
    climbing = grade >= CLIMB_GRADE_PCT
    if to_go <= bal.rider_finale_m:                       # capacités du final : Z long à jauge pleine, Z court ensuite
        name = rules.ability_for(r.gauge_pct, True, bal)
        if name is None and to_go <= bal.rider_sprint_m:
            name = rules.ability_for(r.gauge_pct, False, bal)
        if name is not None and r.ability_left_s <= 0.0:
            _use(r, name, bal)
    if to_go <= bal.rider_sprint_m:
        _launch_sling(r, bal)
        return bal.rider_sprint_cp_pct / 100.0 * cp
    if r.attack_left_s > 0.0:
        r.attack_left_s -= dt
        if r.reserve_pct > bal.rider_cut_pct:
            return bal.rider_attack_cp_pct / 100.0 * cp
        r.attack_left_s = 0.0
    if st == "echappee":
        return bal.rider_solo_cp_pct / 100.0 * cp
    attack = False
    if st == "attaquant" and r.reserve_pct > bal.rider_attack_min_pct and not r.attacked:
        near = [o for o in runners if o is not r and o.finish_s is None and abs(o.s - r.s) < GROUP_LOOK_M]
        attack = any(o.reserve_pct < bal.rider_attack_trigger_pct for o in near)
    elif st == "mixte" and climbing and r.reserve_pct > 60.0:
        key = bisect.bisect_right(r.climb_starts, r.s)   # une attaque par montée
        if key not in r.climb_attacked:
            r.climb_attacked.add(key)
            attack = True
    if attack:
        r.attack_left_s = 60.0
        if r.gauge_pct >= bal.breakaway_cost_pct and r.ability_left_s <= 0.0:
            _use(r, "breakaway", bal)
        _launch_sling(r, bal)
        return bal.rider_attack_cp_pct / 100.0 * cp
    alone_w = 0.95 * cp
    if st in ("rouleur", "mixte"):
        r.relay_target_s = bal.rider_relay_s
        base = _relay(r, cp, dt, bal)
    else:                                                  # suceur, attaquant : jamais devant
        r.relay_target_s = 0.0
        base = 0.8 * cp if r.front and r.saved_for_others_w > 0.0 else alone_w
    cap = cp if r.reserve_pct < bal.rider_cut_pct else 1.3 * cp
    return _follow_or_drop(r, base, grade, cap, rng, bal)


def _use(r: Runner, name: str, bal: TacticalBalance) -> None:
    r.ability, r.ability_left_s = name, rules.ability_duration(name, bal)
    r.spent_pct += rules.ability_cost(name, bal)
    r.abilities += 1


def race(circuit: Circuit, strategy: str, seed: int, bal: TacticalBalance = DEFAULT_BALANCE,
         scales: dict[str, float] | None = None) -> dict[str, Any]:
    """Une course : vainqueur, écarts à l'arrivée et compteurs (Burnouts, catapultes, capacités)."""
    if strategy not in STRATEGIES:
        raise ValueError(f"stratégie inconnue : {strategy}")
    rng = random.Random(f"{seed}:{circuit.name}:{strategy}")
    prof = Profile(circuit)
    length = prof.length_m
    runners = _make_field(strategy, scales or calibration(circuit, bal), bal, rng, length)
    s0 = 0.0
    for part_len, grade in circuit.parts:
        if grade >= CLIMB_GRADE_PCT:
            runners[0].climb_starts.append(s0)
        s0 += part_len
    dt = bal.dt_s
    t = 0.0
    while t < MAX_RACE_S:
        active = [r for r in runners if r.finish_s is None]
        if not active:
            break
        _shelter(active, bal)
        for r in active:
            grade = prof.grade(r.s)
            to_go = length - r.s
            if r.profile == RIDER_ID:
                p = _rider_power(r, runners, grade, to_go, dt, rng, bal)
            else:
                p = _bot_power(r, grade, to_go, dt, rng, bal)
            if r.burn.active:
                p = min(p, rules.burnout_cap_w(r.cp_w, bal))
            r.power_w = p
        for r in active:
            grade = prof.grade(r.s)
            applied = r.power_w
            if r.sling_left_s > 0.0:
                applied = rules.sling_power(applied, r.sling_launch_pct, bal)
                r.sling_left_s -= dt
            alpha = r.alpha
            if r.has("aero"):
                alpha = 1.0 - (1.0 - alpha) * bal.aero_cda_mult
            s_before = r.s
            r.phys.step(applied, grade, 0.0, dt, alpha)
            r.wbal = wbal_step(r.wbal, r.power_w, 0.0, dt, cp_w=r.cp_w, w_prime_j=r.w_prime_j)
            r.burn, started = rules.burnout_step(r.burn, r.wbal.w_bal_j, dt, bal, shielded=r.has("shield"))
            if started:
                r.burnouts += 1
            r.sling_pct = rules.sling_charge(r.sling_pct, r.alpha, dt, bal)
            r.sling_cool_s = max(r.sling_cool_s - dt, 0.0)
            r.ability_left_s = max(r.ability_left_s - dt, 0.0)
            r.rest_s = max(r.rest_s - dt, 0.0)
            if r.front and r.saved_for_others_w > 0.0:
                r.pending_j += rules.relay_credit_j(r.saved_for_others_w, dt)
                if r.relay_s >= bal.relay_min_s or r.pull_left_s > 0.0:
                    r.work_j, r.pending_j = r.work_j + r.pending_j, 0.0
            elif not r.front:
                r.pending_j = 0.0
            if r.s >= length:
                frac = (length - s_before) / max(r.s - s_before, 1e-9)
                r.finish_s = t + frac * dt
        t += dt
    done = sorted((r for r in runners if r.finish_s is not None), key=lambda r: (r.finish_s, r.id))
    first = done[0].finish_s if done else 0.0
    me = next(r for r in runners if r.profile == RIDER_ID)
    return {
        "winner": done[0].profile if done else None,
        "rider_rank": 1 + done.index(me) if me in done else None,
        "rider_gap_s": None if me.finish_s is None else round(me.finish_s - first, 3),
        "gaps_s": {r.profile: (None if r.finish_s is None else round(r.finish_s - first, 3)) for r in runners},
        "burnouts": sum(r.burnouts for r in runners),
        "rider_burnouts": me.burnouts,
        "slings": sum(r.slings for r in runners),
        "abilities": me.abilities,
        "time_s": round(first, 3),
    }


# --- rapport -----------------------------------------------------------------------------------------------

def _batch(args: tuple[str, str, int, int, TacticalBalance]) -> dict[str, Any]:
    circuit_name, strategy, races, seed, bal = args
    circuit = CIRCUITS[circuit_name]
    scales = calibration(circuit, bal)
    t0 = time.perf_counter()
    rows = [race(circuit, strategy, seed * 100003 + i, bal, scales) for i in range(races)]
    wall = time.perf_counter() - t0
    wins: dict[str, int] = {}
    for r in rows:
        wins[r["winner"]] = wins.get(r["winner"], 0) + 1
    def mean(key: str) -> float:
        vals = [r[key] for r in rows if r[key] is not None]
        return sum(vals) / len(vals) if vals else 0.0

    gaps = {p: [r["gaps_s"][p] for r in rows if r["gaps_s"][p] is not None] for p in (RIDER_ID, *BOT_PROFILES)}
    return {"circuit": circuit_name, "strategy": strategy, "races": len(rows),
            "wins": {k: wins.get(k, 0) for k in (RIDER_ID, *BOT_PROFILES)},
            "burnouts": mean("burnouts"), "rider_burnouts": mean("rider_burnouts"), "slings": mean("slings"),
            "abilities": mean("abilities"), "time_s": mean("time_s"),
            "gap_s": {p: (sum(v) / len(v) if v else None) for p, v in gaps.items()},
            "scales": {k: round(v, 4) for k, v in scales.items()}, "wall_s": wall}


def simulate(circuits: list[str], strategies: list[str], races: int, seed: int, bal: TacticalBalance,
             jobs: int = 1) -> dict[str, Any]:
    tasks = [(c, s, races, seed, bal) for c in circuits for s in strategies]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            batches = list(ex.map(_batch, tasks))
    else:
        batches = [_batch(t) for t in tasks]
    return {"seed": seed, "races": races, "balance": balance_hash(bal), "level_pct": bal.bots_level_pct,
            "batches": batches}


def criteria(out: dict[str, Any]) -> list[dict[str, Any]]:
    """Critères 2 et 3 du cahier CT0 §7 (le 4, même graine même rapport, est vérifié par les tests)."""
    by_strategy: dict[str, list[int]] = {}
    for b in out["batches"]:
        w = by_strategy.setdefault(b["strategy"], [0, 0])
        w[0] += b["wins"][RIDER_ID]
        w[1] += b["races"]
    checks = []
    for st, (won, n) in by_strategy.items():
        pct = 100.0 * won / max(n, 1)
        limit = MAX_BREAKAWAY_PCT if st == "echappee" else MAX_WIN_PCT
        checks.append({"ok": pct < limit if st == "echappee" else pct <= limit,
                       "text": f"stratégie {st} : {pct:.1f} % de victoires du cycliste "
                               f"({'moins de' if st == 'echappee' else 'au plus'} {limit:g} %)"})
    circuit_winner: dict[str, str] = {}
    for c in dict.fromkeys(b["circuit"] for b in out["batches"]):
        tot = {p: 0 for p in BOT_PROFILES}
        for b in out["batches"]:
            if b["circuit"] == c:
                for p in BOT_PROFILES:
                    tot[p] += b["wins"][p]
        circuit_winner[c] = max(BOT_PROFILES, key=lambda p: (tot[p], -BOT_PROFILES.index(p)))
    for p in BOT_PROFILES:
        won = sorted(c for c, w in circuit_winner.items() if w == p)
        checks.append({"ok": bool(won), "text": f"profil {PROFILES[p].name} : premier bot sur "
                                                f"{', '.join(won) if won else 'aucun circuit'}"})
    return checks


def _pct(x: int, n: int) -> str:
    return f"{100.0 * x / max(n, 1):.1f} %"


def report_markdown(out: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    """Rapport du cahier CT0 §4 (sans temps de calcul : même graine, même rapport à l'octet près)."""
    names = {RIDER_ID: "Cycliste", **{p: PROFILES[p].name for p in BOT_PROFILES}}
    lines = ["# Rapport d'équilibrage de la Course tactique (lot CT0)", "",
             "Produit par `python -m openride_core.tools.tactical_sim --report docs/5.0/RAPPORT_EQUILIBRAGE_CT0.md` "
             f"(graine {out['seed']}, {out['races']} courses par configuration, table d'équilibrage `{out['balance']}`).",
             "Ne pas modifier à la main : relancer l'outil.", "",
             "Une configuration = un circuit généré × une stratégie du cycliste virtuel. Chaque course : le cycliste "
             "(FTP 250 W, W′ 20 kJ, 75 kg) et 4 bots à profil (forces relatives du lot T12) mis à une échelle commune : seuls, leur temps moyen sur le circuit est celui du cycliste seul à "
             f"{out['level_pct']:g} % de la FTP (valeur `bots_level_pct` de la table) ; forme du jour "
             "tirée pour chacun.", "",
             "Règles simulées par des bouchons tant que leurs lots ne sont pas faits (`tactical/bouchons.py`) : "
             "Burnout (CT2), catapulte (CT4), crédits et capacités (CT6), suivre ou lâcher (CT3). "
             "Non simulés : virages (CT7, pas de courbure sur les circuits générés), placement latéral (AS2), "
             "parade (CT5), variantes asymétriques (CT8).", "", "## Critères du cahier (§7)", ""]
    lines += [f"- [{'OK' if c['ok'] else 'ÉCHEC'}] {c['text']}" for c in checks]
    lines += ["", "## Circuits", "", "| Circuit | Longueur | Description | Échelle commune des bots |",
              "| --- | --- | --- | --- |"]
    seen = set()
    for b in out["batches"]:
        if b["circuit"] in seen:
            continue
        seen.add(b["circuit"])
        c = CIRCUITS[b["circuit"]]
        sc = f"{b['scales'][BOT_PROFILES[0]]:.3f}"
        lines.append(f"| `{c.name}` | {c.length_m / 1000:.1f} km | {c.title} | {sc} |")
    lines += ["", "## Victoires par stratégie (toutes configurations)", "",
              "| Stratégie | Cycliste | Grimpeur | Rouleur | Sprinteur | Diesel |", "| --- | --- | --- | --- | --- | --- |"]
    for st in dict.fromkeys(b["strategy"] for b in out["batches"]):
        tot = {p: 0 for p in (RIDER_ID, *BOT_PROFILES)}
        n = 0
        for b in out["batches"]:
            if b["strategy"] == st:
                n += b["races"]
                for p in tot:
                    tot[p] += b["wins"][p]
        lines.append(f"| {st} | " + " | ".join(_pct(tot[p], n) for p in (RIDER_ID, *BOT_PROFILES)) + " |")
    lines += ["", "## Victoires par profil et par circuit (toutes stratégies)", "",
              "| Circuit | Cycliste | Grimpeur | Rouleur | Sprinteur | Diesel |", "| --- | --- | --- | --- | --- | --- |"]
    for c in dict.fromkeys(b["circuit"] for b in out["batches"]):
        tot = {p: 0 for p in (RIDER_ID, *BOT_PROFILES)}
        n = 0
        for b in out["batches"]:
            if b["circuit"] == c:
                n += b["races"]
                for p in tot:
                    tot[p] += b["wins"][p]
        lines.append(f"| `{c}` | " + " | ".join(_pct(tot[p], n) for p in (RIDER_ID, *BOT_PROFILES)) + " |")
    lines += ["", "## Détail par configuration", "",
              "Écarts moyens à l'arrivée en secondes derrière le vainqueur ; Burnouts, catapultes : moyennes par "
              "course pour les 5 coureurs ; capacités : achetées par le cycliste.", "",
              "| Circuit | Stratégie | Vainqueur le plus fréquent | Cycliste gagne | Écart cycliste | Écart G / R / S / D "
              "| Burnouts (dont cycliste) | Catapultes | Capacités |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for b in out["batches"]:
        top = max((RIDER_ID, *BOT_PROFILES), key=lambda p: (b["wins"][p], -(RIDER_ID, *BOT_PROFILES).index(p)))
        g = b["gap_s"]

        def f(x: float | None) -> str:
            return "—" if x is None else f"{x:.1f}"

        lines.append(f"| `{b['circuit']}` | {b['strategy']} | {names[top]} ({_pct(b['wins'][top], b['races'])}) | "
                     f"{_pct(b['wins'][RIDER_ID], b['races'])} | {f(g[RIDER_ID])} | "
                     f"{' / '.join(f(g[p]) for p in BOT_PROFILES)} | {b['burnouts']:.2f} ({b['rider_burnouts']:.2f}) | "
                     f"{b['slings']:.2f} | {b['abilities']:.2f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Simulateur d'équilibrage de la Course tactique (lot CT0).")
    ap.add_argument("--races", type=int, default=200, help="courses par configuration (circuit × stratégie)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--circuits", default=",".join(CIRCUITS))
    ap.add_argument("--strategies", default=",".join(STRATEGIES))
    ap.add_argument("--balance", type=Path, help="surcharge de la table (défaut ~/OpenRide/tactical_balance.toml)")
    ap.add_argument("--report", type=Path, help="écrit le rapport Markdown dans ce fichier")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--jobs", type=int, default=1)
    args = ap.parse_args(argv)
    circuits = [c.strip() for c in args.circuits.split(",") if c.strip()]
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    bad = [c for c in circuits if c not in CIRCUITS] + [s for s in strategies if s not in STRATEGIES]
    if bad or not circuits or not strategies or args.races < 1:
        print(f"appel invalide : {', '.join(bad) or 'liste vide ou --races < 1'} "
              f"(circuits : {', '.join(CIRCUITS)} ; stratégies : {', '.join(STRATEGIES)})", file=sys.stderr)
        return 2
    try:
        bal = load_balance(args.balance, required=args.balance is not None)
    except BalanceError as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 2
    t0 = time.perf_counter()
    out = simulate(circuits, strategies, args.races, args.seed, bal, max(args.jobs, 1))
    checks = criteria(out)
    text = report_markdown(out, checks)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    if args.json:
        print(json.dumps({**out, "checks": checks}, ensure_ascii=False, indent=2))
    else:
        print(text, end="")
        slowest = max(b["wall_s"] for b in out["batches"])
        print(f"\nCalcul en {time.perf_counter() - t0:.1f} s (configuration la plus lente : {slowest:.1f} s "
              f"pour {args.races} courses)")
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
