"""Règles de combat d'une salle du Cyber-Rogue (lot R5).

Module pur et déterministe : `combat_step` reçoit l'état, les entrées d'un pas et la salle (R3), et
rend le nouvel état et les événements du pas. Les changements de braquet eux-mêmes restent à la
session (R8, `apply_gear_buttons`) ; le combat lit le braquet obtenu et signale le piratage en cours.
Toutes les constantes sont dans `RogueBalance`.
"""

from __future__ import annotations

import bisect
import random
from dataclasses import dataclass, replace

from .balance import DEFAULT_BALANCE, RogueBalance
from .posture import ARRET, ROC, VELOCE
from .rooms import Room

FIGHT, RECOVERY, DONE = "FIGHT", "RECOVERY", "DONE"
Z_SHORT = "Z_SHORT"


@dataclass(frozen=True)
class CombatInputs:
    power_w: float
    cadence_rpm: float
    posture: str
    gear: int
    ftp_w: float
    s_m: float                      # distance dans la salle
    v_mps: float                    # vitesse (fenêtres de temps converties en distance)
    contact: bool = False           # le Firewall touche le joueur (R4)
    buttons: frozenset = frozenset()    # événements de bouton de la trame : Z_SHORT, Z_LONG, ...
    objective: str = "threshold"
    card_mult: float = 1.0          # m_cards (R6)
    w_bal_j: float = 0.0
    run_gold: float = 0.0           # or de la run (perte de 25 % en cas de défaite)


@dataclass(frozen=True)
class CombatState:
    seed: int
    enemy_hp: float
    enemy_hp_max: float
    shield: float
    adrenaline: float = 0.0
    t_s: float = 0.0
    gear: int = 6
    prev_gear: int = 6
    phase: str = FIGHT
    recovery_s: float = 0.0
    outcome: str | None = None         # "won", "fled", "defeat", "boss_fled" une fois la salle finie
    down_s_m: float | None = None      # distance où l'ennemi est tombé à 0 PV
    perfect_shifts: int = 0
    gold: float = 0.0                  # or de la salle
    gold_lost: float = 0.0             # or de la run perdu au contact et en cas de défaite
    contact_prev: bool = False
    over_s: float = 0.0
    overheat: bool = False
    tunnel_s: float = 0.0              # temps cumulé dans la bande de cadence d'un tunnel
    charges: int = 0                   # charges de tunnel (Diesel)
    roc_s: float = 0.0
    roc_charges: int = 0               # coups chargés (Grimpeur)
    hook_until_s: float = 0.0          # fin de l'aspiration (temps de combat)
    grade_scale: float = 1.0           # 0,5 tant qu'une bosse est aspirée (lu par R8)
    hack_kind: str | None = None       # "blocked" ou "forced_gear"
    forced_gear: int | None = None
    hack_t_s: float = 0.0              # début du piratage en cours
    done_markers: frozenset = frozenset()
    rock_armor: tuple = ()             # ((indice, armure restante), ...)
    bins: tuple = ()                   # puissance moyenne des dernières secondes entières
    bin_sum: float = 0.0
    bin_n: int = 0
    crit_second: int = -1              # seconde déjà tirée pour le coup critique
    crit_now: bool = False


# --- aides ---------------------------------------------------------------------------------

def m_gear(gear: int, b: RogueBalance) -> float:
    return 1.0 + b.gear_step * (gear - b.gear_ref)


def target_mean(room: Room) -> float:
    """Moyenne temporelle de `target_frac` sur la salle."""
    total = 0.0
    for st in room.target_frac:
        t0, t1 = _time_at(room, st.s0_m), _time_at(room, st.s1_m)
        total += st.frac * (t1 - t0)
    return total / max(room.time_s[-1], 1e-9)


def _time_at(room: Room, s: float) -> float:
    xs = [p[0] for p in room.profile]
    i = min(max(bisect.bisect_right(xs, s) - 1, 0), len(xs) - 2)
    u = (s - xs[i]) / (xs[i + 1] - xs[i])
    return room.time_s[i] + u * (room.time_s[i + 1] - room.time_s[i])


def s_at_time(room: Room, t: float) -> float:
    i = min(max(bisect.bisect_right(room.time_s, t) - 1, 0), len(room.time_s) - 2)
    span = room.time_s[i + 1] - room.time_s[i]
    u = (t - room.time_s[i]) / span if span > 0 else 0.0
    return room.profile[i][0] + u * (room.profile[i + 1][0] - room.profile[i][0])


def target_at(room: Room, s: float) -> float:
    for st in room.target_frac:
        if st.s0_m <= s < st.s1_m:
            return st.frac
    return room.target_frac[-1].frac


def apply_gear_buttons(gear: int, buttons, hack_kind: str | None, forced_gear: int | None,
                       b: RogueBalance = DEFAULT_BALANCE) -> int:
    """Braquet après les boutons de la trame : ±1 court, ±3 long, borné à 1..12 ; piratage respecté."""
    if hack_kind == "forced_gear" and forced_gear is not None:
        return forced_gear
    if hack_kind == "blocked":
        return gear
    delta = 0
    for name in buttons:
        delta += {"PLUS_SHORT": 1, "MINUS_SHORT": -1,
                  "PLUS_LONG": b.long_press_gears, "MINUS_LONG": -b.long_press_gears}.get(name, 0)
    return min(max(gear + delta, b.gear_min), b.gear_max)


def combat_start(room: Room, seed: int, balance: RogueBalance = DEFAULT_BALANCE,
                 shield: float | None = None, gear: int | None = None) -> CombatState:
    b = balance
    hp = b.hp_factor * target_mean(room) * room.nominal_s
    g = b.gear_ref if gear is None else gear
    return CombatState(seed=seed, enemy_hp=hp, enemy_hp_max=hp,
                       shield=b.shield_max if shield is None else shield, gear=g, prev_gear=g)


def _window(marker, speed: float, width_s: float) -> tuple:
    half = max(0.5 * width_s * max(speed, 0.0), 3.0)
    return marker.s_m - half, marker.s_m + marker.len_m + half


def _hack_schedule(room: Room, b: RogueBalance, seed: int) -> list:
    """Piratages du Saboteur : (début m, balise de purge m, indice de balise, genre, braquet imposé)."""
    out = []
    for i, m in enumerate(room.markers):
        if m.kind != "purge":
            continue
        delay = float(m.param or 0.0)
        start = s_at_time(room, max(_time_at(room, m.s_m) - delay, 0.0))
        rng = random.Random(f"{seed}|hack|{i}")
        kind = rng.choice(("blocked", "forced_gear"))
        out.append((start, m.s_m, i, kind, rng.randint(b.gear_min, b.gear_max)))
    return out


# --- pas de combat -------------------------------------------------------------------------

def combat_step(state: CombatState, inp: CombatInputs, room: Room,
                balance: RogueBalance = DEFAULT_BALANCE, dt: float = 0.02) -> tuple:
    b = balance
    if state.phase == DONE or dt <= 0:
        return state, ()
    events: list[str] = []
    st = state
    t = st.t_s + dt

    if st.phase == RECOVERY:
        rec = st.recovery_s + dt
        if rec >= b.recovery_s:
            return replace(st, t_s=t, recovery_s=b.recovery_s, phase=DONE), ()
        return replace(st, t_s=t, recovery_s=rec), ()

    s, v = inp.s_m, inp.v_mps
    ftp = max(inp.ftp_w, 1.0)
    frac = inp.power_w / ftp
    tgt = target_at(room, s)
    boss = room.archetype == "boss"

    # piratage du Saboteur (début à la distance prévue, fin par purge ou expiration)
    hack_kind, forced, hack_t = st.hack_kind, st.forced_gear, st.hack_t_s
    done = set(st.done_markers)
    if room.archetype == "saboteur":
        for start, _purge_s, idx, kind, pick in _hack_schedule(room, b, st.seed):
            if ("hack", idx) not in done and s >= start:
                done.add(("hack", idx))
                hack_kind, forced, hack_t = kind, (pick if kind == "forced_gear" else None), t
    if hack_kind is not None and t - hack_t > b.hack_max_s:
        hack_kind, forced = None, None
    hacked = hack_kind is not None
    gear = forced if (hack_kind == "forced_gear" and forced is not None) else inp.gear

    # Perfect Shift
    ps = st.perfect_shifts
    adr = st.adrenaline
    if gear != st.prev_gear:
        direction = "up" if gear > st.prev_gear else "down"
        half = 0.5 * b.ps_window_s * max(v, 0.1)
        for i, m in enumerate(room.markers):
            if m.kind == "arch" and ("arch", i) not in done and m.param == direction and abs(s - m.s_m) <= half:
                done.add(("arch", i))
                ps += 1
                adr += b.perfect_shift_adrenaline
                events.append("perfect_shift")
                break

    # fenêtre de puissance (aspiration du Puncheur)
    bins, bsum, bn = st.bins, st.bin_sum + inp.power_w * dt, st.bin_n + 1
    if int(t) > int(st.t_s):
        bins = (bins + (bsum / max(bn, 1),))[-5:]
        bsum, bn = 0.0, 0

    # surchauffe (objectif endurance seulement)
    over_s, overheat = st.over_s, False
    if inp.objective == "endurance" and frac > b.overheat_frac:
        over_s += dt
        overheat = over_s > b.overheat_after_s
    else:
        over_s = 0.0

    # adrénaline
    if overheat:
        adr -= b.overheat_adrenaline_per_s * dt
    elif frac >= tgt and inp.posture != ARRET:
        mult = b.adrenaline_roc_mult if inp.posture == ROC else (
            b.adrenaline_veloce_mult if inp.posture == VELOCE else 1.0)
        adr += b.adrenaline_per_s * mult * dt
    adr = min(max(adr, 0.0), b.adrenaline_max)

    # dégâts par seconde
    hp, down_s = st.enemy_hp, st.down_s_m
    crit_sec, crit_now = st.crit_second, st.crit_now
    if inp.posture != ARRET and hp > 0:
        mult = (1.0 if hacked else m_gear(gear, b)) * inp.card_mult
        if inp.posture == VELOCE and not overheat:
            if int(t) != crit_sec:
                crit_sec = int(t)
                crit_now = random.Random(f"{st.seed}|crit|{crit_sec}").random() < b.veloce_crit_chance
                if crit_now:
                    events.append("crit")
            if crit_now:
                mult *= b.crit_mult
        pad = False
        if not overheat:
            for m in room.markers:
                if (m.kind == "pad" and m.s_m <= s <= m.s_m + m.len_m and frac >= float(m.param or 0.0)
                        and gear >= b.pad_min_gear):
                    pad = True
            if pad:
                mult *= b.pad_damage_mult
        hp -= frac * mult * dt
    if hp <= 0 < st.enemy_hp:
        hp, down_s = 0.0, s

    # tunnels (Diesel) et charges de Roc (Grimpeur)
    tunnel_s, charges = st.tunnel_s, st.charges
    for m in room.markers:
        if m.kind == "tunnel" and m.s_m <= s <= m.s_m + m.len_m:
            if abs(inp.cadence_rpm - float(m.param or 0.0)) <= b.tunnel_tolerance_rpm:
                tunnel_s += dt
                if tunnel_s >= b.tunnel_charge_s:
                    tunnel_s -= b.tunnel_charge_s
                    charges = min(charges + 1, b.tunnel_max_charges)
    roc_s, roc_charges = st.roc_s, st.roc_charges
    if room.archetype == "grimpeur" and inp.posture == ROC:
        roc_s += dt
        if roc_s >= b.roc_charge_s and roc_charges < b.roc_max_charges:
            roc_s -= b.roc_charge_s
            roc_charges += 1
    else:
        roc_s = 0.0

    # bouton Z court : une seule signification selon le marqueur sous la roue
    rock_armor = dict(st.rock_armor)
    hook_until, grade_scale = st.hook_until_s, st.grade_scale
    if Z_SHORT in inp.buttons:
        used = False
        for i, m in enumerate(room.markers):
            if m.kind == "purge":
                lo, hi = _window(m, v, b.strike_window_s)
                if lo <= s <= hi:
                    if hacked:
                        hack_kind, forced, hacked = None, None, False
                    used = True
            elif m.kind == "strike_target" and ("strike", i) not in done:
                lo, hi = _window(m, v, b.strike_window_s)
                if lo <= s <= hi:
                    used = True
                    if room.archetype == "diesel":
                        if charges > 0 and not overheat:
                            hp = max(hp - charges * b.tunnel_charge_hp_frac * st.enemy_hp_max, 0.0)
                            charges = 0
                            done.add(("strike", i))
                            events.append("hit")
                    elif adr >= b.strike_cost and not overheat:
                        adr -= b.strike_cost
                        hp = max(hp - b.strike_hp_frac * st.enemy_hp_max, 0.0)
                        done.add(("strike", i))
                        events.append("hit")
            elif m.kind == "rock" and ("rock", i) not in done:
                lo, hi = _window(m, v, b.rock_window_s)
                if lo <= s <= hi:
                    used = True
                    if roc_charges > 0:
                        roc_charges -= 1
                        left = rock_armor.get(i, int(m.param or 1)) - 1
                        rock_armor[i] = left
                        if left <= 0:
                            hp = max(hp - b.rock_hp_frac * st.enemy_hp_max, 0.0)
                            done.add(("rock", i))
                            events.append("hit")
            elif m.kind == "parry_zone" and ("zone", i) not in done and m.s_m <= s <= m.s_m + m.len_m:
                used = True
                if boss:
                    done.add(("zone", i))
                    done.add(("parried", i))
                    events.append("parry")
                elif len(bins) >= 5:
                    recent = sum(bins[-2:]) / 2
                    before = sum(bins[-5:-2]) / 3
                    if recent > b.hook_power_ratio * before:
                        done.add(("parried", i))
                        events.append("parry")
            if used:
                break
        if hp <= 0 < st.enemy_hp and down_s is None:
            down_s = s

    # zones de parade terminées : coup non paré
    shield = st.shield
    for i, m in enumerate(room.markers):
        if m.kind == "parry_zone" and ("zone", i) not in done and s > m.s_m + m.len_m:
            done.add(("zone", i))
            if ("parried", i) in done:
                if not boss:
                    hook_until, grade_scale = t + b.hook_s, b.hook_grade_mult
                continue
            under = frac < tgt
            if boss or under:
                shield -= b.unparried_hit
                events.append("parry_miss")
    if grade_scale != 1.0 and t > hook_until:
        grade_scale = 1.0

    # contact du Firewall
    gold_lost = st.gold_lost
    if inp.contact:
        armor = b.roc_armor_mult if inp.posture == ROC else (
            b.veloce_armor_mult if inp.posture == VELOCE else 1.0)
        shield -= b.contact_shield_per_s * armor * dt
        gold_lost += b.contact_gold_per_s * dt
        if not st.contact_prev:
            events.append("firewall_contact")

    new = replace(
        st, t_s=t, gear=gear, prev_gear=gear, enemy_hp=hp, down_s_m=down_s, shield=min(shield, b.shield_max),
        adrenaline=adr, perfect_shifts=ps, gold_lost=gold_lost, contact_prev=inp.contact, over_s=over_s,
        overheat=overheat, tunnel_s=tunnel_s, charges=charges, roc_s=roc_s, roc_charges=roc_charges,
        hook_until_s=hook_until, grade_scale=grade_scale, hack_kind=hack_kind, forced_gear=forced, hack_t_s=hack_t,
        done_markers=frozenset(done), rock_armor=tuple(sorted(rock_armor.items())), bins=bins,
        bin_sum=bsum, bin_n=bn, crit_second=crit_sec, crit_now=crit_now)

    # défaite
    if new.shield <= 0:
        events.append("defeat")
        if boss:
            return replace(new, shield=0.0, phase=DONE, outcome="boss_fled"), tuple(events)
        return replace(new, shield=b.recovery_shield, phase=RECOVERY, recovery_s=0.0, outcome="defeat",
                       gold=0.0, gold_lost=new.gold_lost + b.defeat_run_gold_loss * inp.run_gold,
                       hack_kind=None, forced_gear=None, grade_scale=1.0), tuple(events)

    # fin de salle
    if s >= room.length_m:
        if new.enemy_hp <= 0:
            events.append("room_won")
            return replace(new, phase=DONE, outcome="won",
                           gold=b.win_gold + b.win_gold_per_ps * new.perfect_shifts), tuple(events)
        events.append("room_fled")
        return replace(new, phase=DONE, outcome="fled", gold=b.flee_gold), tuple(events)
    return new, tuple(events)
