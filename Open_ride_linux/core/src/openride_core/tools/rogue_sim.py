"""Runs Cyber-Rogue simulées avec des cyclistes types, pour vérifier l'équilibrage (lot R7).

    python -m openride_core.tools.rogue_sim --objective threshold --duration 45 --runs 200
        [--profiles moyen,debutant] [--all-objectives] [--json FICHIER] [--sensitivity] [--jobs N]
        [--balance FICHIER.toml] [--seed N]

Chaque run est jouée en temps accéléré (pas d'une seconde), sans trainer ni engine, avec le vrai moteur de
run (`RunEngine`) et un cycliste simulé : il suit la cible de la salle à son niveau de précision, rate ou
réussit les Perfect Shifts et les appuis sur Z selon son profil, choisit ses cartes dans les couloirs.
Le rapport compare les mesures aux cibles du cahier R7 §4.3 ; pour chaque cible manquée, `--sensitivity`
essaie ±20 % sur chaque constante et nomme celles qui la font le plus bouger. Aucune règle n'est changée.
Le même `--seed` donne le même rapport, quel que soit `--jobs`.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, fields, replace
from pathlib import Path

from ..physics import PhysicsParams, RiderPhysics
from ..rogue import cards as cardlib
from ..rogue.balance import DEFAULT_BALANCE, BalanceError, RogueBalance, balance_hash, load_balance
from ..rogue.combat import _window, target_at
from ..rogue.rooms import OBJECTIVES, RoomRider
from ..rogue.run import RunEngine, RunInputs
from ..rogue.scenario import compose_run

DT = 1.0
PHYSICS = PhysicsParams(mass_kg=84.0, cda_m2=0.32)
BASE_CADENCE = 88.0
ESCAPE_GAP_M = 40.0                     # écart sous lequel le cycliste relance pour décoller du mur
ESCAPE_MULT = 1.10
ESCAPE_WBAL_FRAC = 0.15
REVERT_S = 5                            # secondes avant de revenir au braquet de base après un Perfect Shift
PERF_MULT = 1.3                         # pic de puissance avant un appui de parade
FATIGUE_LOSS = 0.15
CARD_RANK = ("shifter", "roller", "overdrive", "springboard", "siphon", "heal", "polarity", "cursed")
RELIC_RANK = ("relic_shield", "relic_window", "relic_gold")
GOOD_CARDS = 3                          # une offre sans carte parmi les 3 premières du rang est relancée


@dataclass(frozen=True)
class Profile:
    name: str
    ftp_w: float
    w_prime_j: float
    precision: float                    # écart type relatif de la puissance autour de la cible
    ps_rate: float                      # part des Perfect Shifts réussis
    z_rate: float                       # part des appuis sur Z faits à temps
    fatigue_after_s: float | None = None


PROFILES = {p.name: p for p in (
    Profile("debutant", 150.0, 12000.0, 0.04, 0.30, 0.50),
    Profile("moyen", 250.0, 20000.0, 0.025, 0.60, 0.75),
    Profile("confirme", 330.0, 25000.0, 0.015, 0.90, 0.95),
    Profile("fatigue", 250.0, 20000.0, 0.025, 0.60, 0.75, fatigue_after_s=1800.0),
)}

TARGETS = (
    # (clé, libellé, profil, bas, haut)
    ("rooms_won_pct", "Salles gagnées, Moyen (%)", "moyen", 60.0, 80.0),
    ("defeats", "Défaites par run, Moyen", "moyen", 0.0, 1.0),
    ("defeats", "Défaites par run, Débutant", "debutant", 0.0, 2.0),
    ("rerolls", "Relances de cartes par run, Moyen", "moyen", 1.0, 2.0),
    ("boss_won_pct", "Boss battu, Moyen (%)", "moyen", 50.0, 70.0),
    ("if", "IF de la run, Moyen", "moyen", None, None),          # bornes selon l'objectif
    ("min_over_110", "Minutes au-delà de 1,10 FTP, Moyen (VO2max)", "moyen", 8.0, None),
)
IF_RANGE = {"endurance": (0.62, 0.72), "threshold": (0.80, 0.88), "vo2max": (0.80, 0.90)}
GAP_MAX_PTS = 25.0


class Bot:
    """Cycliste simulé : produit les entrées de `RunEngine` pas à pas."""

    def __init__(self, engine: RunEngine, profile: Profile, seed: int) -> None:
        self.e, self.p = engine, profile
        self.rng = random.Random(f"{seed}|bot|{profile.name}")
        self.body = RiderPhysics(PHYSICS)
        self.room_id: int | None = None
        self.noise = 0.0
        self.gear = DEFAULT_BALANCE.gear_ref
        self.decided: dict = {}
        self.boost = 0
        self.queue: deque = deque()
        self.plan_key: tuple | None = None
        self.rerolls = 0
        self.pending_shift: list = []
        self.roc_room = False

    # --- décisions ---------------------------------------------------------------------------

    def _chance(self, key, p: float) -> bool:
        if key not in self.decided:
            self.decided[key] = self.rng.random() < p
        return self.decided[key]

    def _power(self, fight: bool) -> float:
        e, p = self.e, self.p
        self.noise = 0.7 * self.noise + 0.714 * self.rng.gauss(0.0, 1.0)
        mult = 1.0 + max(min(p.precision * self.noise, 3 * p.precision), -3 * p.precision)
        b = e.b
        if fight and e.room is not None:
            frac = target_at(e.room, self.body.s)
        elif e.phase == "WARMUP":
            step = e._step
            frac = b.warmup_frac_from + (b.warmup_frac_to - b.warmup_frac_from) * min(e.t_phase / step.nominal_s, 1.0)
        elif e.phase == "COOLDOWN":
            frac = b.cooldown_frac
        else:
            frac = 0.5
        if fight and e.firewall is not None and e.firewall.state.gap_m < ESCAPE_GAP_M \
                and e.wbal.w_bal_j > ESCAPE_WBAL_FRAC * e.w_prime_j:
            frac *= ESCAPE_MULT                 # le mur est sur la roue : relance tant qu'il reste du W'
        power = frac * p.ftp_w * mult
        if p.fatigue_after_s is not None and e.t_total > p.fatigue_after_s:
            power *= 1.0 - FATIGUE_LOSS
        return power * (PERF_MULT if self.boost >= 1 else 1.0)

    def _corridor_buttons(self) -> frozenset:
        e = self.e
        if not e.stage:
            self.queue.clear()
            self.plan_key = None
            return frozenset()
        key = (e.stage, e.loot_id, e.rerolls, e.offer, e.door_steps)
        if key != self.plan_key:
            self.plan_key = key
            self.queue.clear()
            if e.stage == "card":
                relics = e.phase == "WARMUP"
                rank = RELIC_RANK if relics else CARD_RANK
                order = sorted(range(len(e.offer)), key=lambda i: rank.index(e.offer[i]) if e.offer[i] in rank else 99)
                best = order[0]
                cost = e.b.reroll_cost + e.b.reroll_step * e.rerolls
                if (not relics and rank.index(e.offer[best]) >= GOOD_CARDS and e.gold >= cost
                        and self._chance(("reroll", e.loot_id, e.rerolls), 0.6)):
                    self.queue.append("Z_SHORT")
                    self.rerolls += 1
                elif self._chance(("card", e.loot_id, e.phase), 0.5 + 0.5 * self.p.z_rate):
                    self.queue.extend(["A_SHORT"] * (best + 1) + ["A_LONG"])
            else:
                right = self.rng.random() < 0.5
                self.queue.extend(["A_SHORT"] * (2 if right else 1) + ["A_LONG"])
        return frozenset([self.queue.popleft()]) if self.queue else frozenset()

    def _fight_buttons(self, s: float, v: float) -> frozenset:
        e = self.e
        room, cs, b = e.room, e.combat, e.b
        buttons = set()
        gear = self.gear
        # Perfect Shifts : l'arche passe sous la roue au prochain pas, ou on rate (décalage de 3 s)
        for i, m in enumerate(room.markers):
            if m.kind == "arch" and ("arch", i) not in self.decided:
                if m.s_m - 0.5 * v * DT <= s:
                    hit = self._chance(("ps", e.room_id, i), self.p.ps_rate)
                    self.decided[("arch", i)] = True
                    when = 0 if hit else 3
                    delta = 1 if m.param == "up" else -1
                    self.pending_shift += [[when, delta], [when + REVERT_S, -delta]]    # puis retour au braquet de base
        for sh in list(self.pending_shift):
            if sh[0] <= 0:
                gear = min(max(gear + sh[1], b.gear_min), b.gear_max)
                self.pending_shift.remove(sh)
            else:
                sh[0] -= 1
        # Sprinteur : braquet haut sur les pavés
        on_pad = any(m.kind == "pad" and m.s_m - 8.0 <= s <= m.s_m + m.len_m
                     and self._chance(("pad", e.room_id, i), self.p.z_rate) for i, m in enumerate(room.markers))
        if on_pad:
            gear = max(gear, b.pad_min_gear)
        elif gear >= b.pad_min_gear and not self.pending_shift:
            gear = b.gear_ref
        self.gear = gear
        # boutons Z
        press_boost = 0
        for i, m in enumerate(room.markers):
            if m.kind not in ("strike_target", "rock", "parry_zone", "purge"):
                continue
            lo, hi = _window(m, v, b.strike_window_s if m.kind != "rock" else b.rock_window_s)
            if m.kind == "parry_zone":
                lo, hi = m.s_m, m.s_m + m.len_m
                if self._chance(("z", e.room_id, i), self.p.z_rate) and ("pressed", i) not in self.decided:
                    if m.s_m - 2.2 * max(v, 1.0) * DT <= s <= hi:
                        press_boost = 1
                    if lo <= s <= hi and self.boost >= 2:
                        buttons.add("Z_SHORT")
                        self.decided[("pressed", i)] = True
                continue
            if lo <= s <= hi and ("pressed", i) not in self.decided and self._chance(("z", e.room_id, i), self.p.z_rate):
                ready = True
                if m.kind == "strike_target":
                    ready = cs.charges > 0 if room.archetype == "diesel" else cs.adrenaline >= b.strike_cost
                elif m.kind == "rock":
                    ready = cs.roc_charges > 0
                if m.kind == "purge" and not cs.hack_kind:
                    ready = False
                if ready:
                    buttons.add("Z_SHORT")
                    self.decided[("pressed", i)] = True
        self.boost = self.boost + 1 if press_boost else 0
        return frozenset(buttons)

    def _cadence(self, s: float) -> float:
        e = self.e
        room = e.room
        if room is None:
            return BASE_CADENCE
        for i, m in enumerate(room.markers):
            if m.kind == "tunnel" and m.s_m <= s <= m.s_m + m.len_m and self._chance(("tun", e.room_id, i), self.p.z_rate):
                return float(m.param)
        if room.archetype == "grimpeur" and self._chance(("roc", e.room_id), self.p.z_rate):
            return 66.0
        return BASE_CADENCE

    # --- un pas ------------------------------------------------------------------------------

    def step(self):
        e = self.e
        if e.room is not None and e.room_id != self.room_id:
            self.room_id = e.room_id
            self.body = RiderPhysics(PHYSICS)
            self.pending_shift.clear()
            self.boost = 0
        fight = e.room is not None and e.phase in ("ROOM", "BOSS")
        s = self.body.s if e.room is not None else 0.0
        v = self.body.v
        buttons = self._fight_buttons(s, v) if fight else self._corridor_buttons()
        power = self._power(fight)
        inp = RunInputs(power_w=power, cadence_rpm=self._cadence(s) if fight else BASE_CADENCE, gear=self.gear,
                        ftp_w=self.p.ftp_w, s_m=s, v_mps=v, buttons=buttons)
        out = e.step(DT, inp)
        if out.force_gear:
            self.gear = out.force_gear
        self.body.step(power, out.grade_sent, 0.0, DT)
        return out, power


# --- une run ---------------------------------------------------------------------------------

def simulate(objective: str, duration_min: int, seed: int, profile: Profile,
             balance: RogueBalance = DEFAULT_BALANCE) -> dict:
    rider = RoomRider(ftp_w=profile.ftp_w, params=PHYSICS)
    sc = compose_run(objective, duration_min, seed, rider, balance)
    e = RunEngine(sc, rider, profile.w_prime_j, profile.ftp_w, balance)
    bot = Bot(e, profile, seed)
    powers: list = []
    limit = 3 * duration_min * 60.0
    out = None
    while e.t_total < limit:
        out, p = bot.step()
        powers.append(p)
        if out.finished:
            break
    summ = e.summary()
    # puissance normalisée : moyenne mobile de 30 s, puissance 4, racine 4
    win, acc, q, fourth = 30, 0.0, deque(), []
    for p in powers:
        q.append(p)
        acc += p
        if len(q) > win:
            acc -= q.popleft()
        if len(q) == win:
            fourth.append((acc / win) ** 4)
    npw = (sum(fourth) / len(fourth)) ** 0.25 if fourth else 0.0
    return {
        "seed": seed, "result": summ["result"], "boss": summ["boss"], "rooms_total": summ["rooms_total"],
        "rooms_won": summ["rooms_won"], "rooms_fled": summ["rooms_fled"], "rooms_skipped": summ["rooms_skipped"],
        "defeats": summ["defeats"], "gold": summ["gold"], "cards": len(summ["cards"]),
        "perfect_shifts": summ["perfect_shifts"], "rerolls": bot.rerolls,
        "duration_s": round(e.t_total, 1), "if": npw / profile.ftp_w,
        "min_over_110": sum(1 for p in powers if p > 1.10 * profile.ftp_w) * DT / 60.0,
        "finished": bool(out and out.finished),
    }


def _job(args: tuple) -> dict:
    objective, duration, seed, profile_name, balance = args
    return simulate(objective, duration, seed, PROFILES[profile_name], balance)


def run_batch(objective: str, duration: int, runs: int, seed0: int, profile_name: str,
              balance: RogueBalance, jobs: int = 1) -> dict:
    tasks = [(objective, duration, seed0 + i, profile_name, balance) for i in range(runs)]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(_job, tasks, chunksize=max(runs // (jobs * 4), 1)))
    else:
        results = [_job(t) for t in tasks]
    return aggregate(results)


def aggregate(results: list) -> dict:
    n = len(results)
    total = sum(max(r["rooms_total"], 1) for r in results)

    def mean(k):
        return sum(r[k] for r in results) / n

    return {
        "runs": n,
        "rooms_won_pct": 100.0 * sum(r["rooms_won"] for r in results) / total,
        "rooms_fled_pct": 100.0 * sum(r["rooms_fled"] for r in results) / total,
        "rooms_skipped": mean("rooms_skipped"),
        "defeats": mean("defeats"), "rerolls": mean("rerolls"), "gold": mean("gold"), "cards": mean("cards"),
        "perfect_shifts": mean("perfect_shifts"), "if": mean("if"), "min_over_110": mean("min_over_110"),
        "boss_won_pct": 100.0 * sum(1 for r in results if r["boss"] == "won") / n,
        "victory_pct": 100.0 * sum(1 for r in results if r["result"] == "victory") / n,
        "duration_min": mean("duration_s") / 60.0,
        "unfinished": sum(1 for r in results if not r["finished"]),
    }


# --- cibles et rapport -------------------------------------------------------------------------

def check_targets(report: dict, objective: str) -> list:
    """Liste de {label, value, low, high, ok, key, profile} pour les profils présents dans `report`."""
    out = []
    prof = report["profiles"]

    def add(label, key, pname, value, low, high):
        ok = (low is None or value >= low) and (high is None or value <= high)
        out.append({"label": label, "key": key, "profile": pname, "value": round(value, 3),
                    "low": low, "high": high, "ok": ok})

    for key, label, pname, low, high in TARGETS:
        if pname not in prof:
            continue
        if key == "if":
            low, high = IF_RANGE[objective]
        if key == "min_over_110":
            if objective != "vo2max":
                continue
        add(label, key, pname, prof[pname][key], low, high)
    if "debutant" in prof and "confirme" in prof:
        gap = abs(prof["confirme"]["rooms_won_pct"] - prof["debutant"]["rooms_won_pct"])
        add("Écart de salles gagnées Débutant / Confirmé (points)", "gap", "debutant+confirme", gap, None, GAP_MAX_PTS)
    return out


def sensitivity(objective: str, duration: int, runs: int, seed0: int, balance: RogueBalance,
                targets: list, jobs: int, constants: list | None = None) -> dict:
    """Pour chaque cible manquée : les constantes dont ±20 % font le plus bouger la mesure."""
    names = constants or [f.name for f in fields(RogueBalance) if isinstance(getattr(balance, f.name), float)]
    need = {t["profile"] for t in targets if not t["ok"]}
    profiles = sorted({p for n in need for p in n.split("+")})
    cache: dict = {}

    def measure(bal: RogueBalance) -> dict:
        return {p: run_batch(objective, duration, runs, seed0, p, bal, jobs) for p in profiles}

    base = measure(balance)
    for name in names:
        for sign in (-1, 1):
            v = getattr(balance, name) * (1 + 0.2 * sign)
            cache[(name, sign)] = measure(replace(balance, **{name: v}))
    out = {}
    for t in targets:
        if t["ok"]:
            continue
        def val(rep):
            if t["key"] == "gap":
                return abs(rep["confirme"]["rooms_won_pct"] - rep["debutant"]["rooms_won_pct"])
            return rep[t["profile"]][t["key"]]
        b0 = val(base)
        effects = []
        for name in names:
            lo, hi = val(cache[(name, -1)]), val(cache[(name, 1)])
            effects.append((max(abs(lo - b0), abs(hi - b0)), name, round(lo - b0, 3), round(hi - b0, 3)))
        effects.sort(reverse=True)
        out[t["label"]] = [{"constant": n, "value": round(getattr(balance, n), 4), "minus20": a, "plus20": c}
                           for d, n, a, c in effects[:3] if d > 0]
    return out


def build_report(objective: str, duration: int, runs: int, seed0: int, profile_names: list,
                 balance: RogueBalance, jobs: int, with_sensitivity: bool, sens_runs: int) -> dict:
    report = {"objective": objective, "duration_min": duration, "runs": runs, "seed": seed0,
              "balance_hash": balance_hash(balance),
              "profiles": {p: run_batch(objective, duration, runs, seed0, p, balance, jobs) for p in profile_names}}
    report["targets"] = check_targets(report, objective)
    if with_sensitivity and any(not t["ok"] for t in report["targets"]):
        report["sensitivity"] = sensitivity(objective, duration, sens_runs, seed0, balance, report["targets"], jobs)
    return report


def _fmt_range(t: dict) -> str:
    lo, hi = t["low"], t["high"]
    if lo is not None and hi is not None:
        return f"{lo:g} à {hi:g}"
    return f"au moins {lo:g}" if lo is not None else f"au plus {hi:g}"


def format_report(r: dict) -> str:
    lines = [f"Cyber-Rogue : {r['objective']}, {r['duration_min']} min, {r['runs']} runs par profil "
             f"(graine {r['seed']}, table {r['balance_hash']})", ""]
    head = f"{'profil':<10}{'salles ok %':>12}{'fuites %':>10}{'défaites':>10}{'relances':>10}{'IF':>7}{'>110 min':>10}" \
           f"{'boss %':>8}{'or':>7}{'durée':>8}"
    lines.append(head)
    for name, m in r["profiles"].items():
        lines.append(f"{name:<10}{m['rooms_won_pct']:>12.1f}{m['rooms_fled_pct']:>10.1f}{m['defeats']:>10.2f}"
                     f"{m['rerolls']:>10.2f}{m['if']:>7.2f}{m['min_over_110']:>10.1f}{m['boss_won_pct']:>8.0f}"
                     f"{m['gold']:>7.0f}{m['duration_min']:>8.1f}")
    lines += ["", "Cibles :"]
    for t in r["targets"]:
        lines.append(f"  [{'OK ' if t['ok'] else 'NON'}] {t['label']} : {t['value']:g} (cible {_fmt_range(t)})")
    sens = r.get("sensitivity", {})
    for label, rows in sens.items():
        lines.append(f"\nCible manquée : {label}. Constantes qui la font le plus bouger (−20 % / +20 %) :")
        for c in rows:
            lines.append(f"  {c['constant']} (= {c['value']:g}) : {c['minus20']:+g} / {c['plus20']:+g}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m openride_core.tools.rogue_sim",
                                description="Runs Cyber-Rogue simulées pour vérifier l'équilibrage.")
    p.add_argument("--objective", choices=OBJECTIVES, default="threshold")
    p.add_argument("--all-objectives", action="store_true", help="les trois objectifs l'un après l'autre")
    p.add_argument("--duration", type=int, default=45, help="durée de la run en minutes (30, 45, 60 ou 90)")
    p.add_argument("--runs", type=int, default=200)
    p.add_argument("--profiles", default="debutant,moyen,confirme,fatigue")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--jobs", type=int, default=1, help="processus en parallèle")
    p.add_argument("--sensitivity", action="store_true", help="essai ±20 %% sur chaque constante pour les cibles manquées")
    p.add_argument("--sens-runs", type=int, default=20, help="runs par essai de sensibilité")
    p.add_argument("--json", type=Path, help="écrit aussi le rapport JSON dans ce fichier")
    p.add_argument("--balance", type=Path, help="surcharge de la table (défaut : ~/OpenRide/rogue_balance.toml)")
    a = p.parse_args(argv)
    names = [n.strip() for n in a.profiles.split(",") if n.strip()]
    bad = [n for n in names if n not in PROFILES]
    if bad:
        print(f"profil inconnu : {', '.join(bad)} (profils : {', '.join(PROFILES)})", file=sys.stderr)
        return 2
    try:
        balance = load_balance(a.balance, required=a.balance is not None)
    except BalanceError as exc:
        print(f"table d'équilibrage refusée : {exc}", file=sys.stderr)
        return 2
    objectives = list(OBJECTIVES) if a.all_objectives else [a.objective]
    reports = [build_report(o, a.duration, a.runs, a.seed, names, balance, max(a.jobs, 1), a.sensitivity, a.sens_runs)
               for o in objectives]
    print("\n\n".join(format_report(r) for r in reports))
    if a.json:
        a.json.write_text(json.dumps(reports if a.all_objectives else reports[0], indent=2, sort_keys=True,
                                     ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
