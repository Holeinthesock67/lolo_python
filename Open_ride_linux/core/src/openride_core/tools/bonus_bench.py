"""Banc d'équilibrage des bonus (lot TT8) : gain de chaque bonus dans son terrain idéal, gain ailleurs, refus.

    python -m openride_core.tools.bonus_bench [--passages 50] [--graine 8] [--values FICHIER.toml] [--json]

Physique du core (`physics.py`, pas de 20 ms), sans trainer, sans engine et sans bots à profil. Chaque passage
tire un cycliste virtuel du lot X27 (`sim_rider`, stratégie `pente` : puissance qui suit la pente, bruit de
± 2 %), de FTP 200 à 320 W et de 70 à 95 % de FTP sur le plat, et une masse (cycliste et vélo) de 70 à 95 kg.
Deux copies du même cycliste roulent les mêmes watts sur le même terrain, l'une avec le bonus lancé à t = 0,
l'autre sans ; le gain est l'avance prise au bout de 60 s, en secondes (mètres d'avance / vitesse moyenne
sans bonus). Repère du plan (`docs/4.0/PLAN_SERIE_TT.md` §2) : **1,5 à 2,5 s dans le terrain idéal**.

Terrain idéal tiré à chaque passage :

| Bonus | Terrain idéal | Ailleurs (contrôle) |
| --- | --- | --- |
| Plume | montée de 6 à 10 % | plat |
| Casque aéro | plat (−1 à +1 %) | montée de 8 % |
| Puissance | montée de 6 à 10 % | plat |
| Enclume | descente de −3 à −8 % | plat (effet suspendu) |
| Aspiration + | plat, roue d'un bot à vitesse égale, 0,5 à 2,5 m | bot à 20 m (hors de l'abri normal) |
| Échappée | plat, un suiveur à 0,3 à 1,5 m, à la puissance qui le garde dans la roue | suiveur à 20 m |
| Rouleau compresseur | plat, chemin compact, gravier ou terre (roulement × 2, 2,5 ou 3) | bitume |

Pour l'Échappée, le gain est ce que perd le suiveur (mètres perdus / vitesse) à la fin du bonus : il ne
reçoit plus l'abri du cycliste ; le cycliste, lui, ne va pas plus vite. Mesuré à la fin du bonus et pas à
60 s : un suiveur à puissance constante lâché ne revient jamais, alors qu'un bot de course (Y10) répond dès
qu'il revoit l'attaque.

Refus : `--passages` appuis par bonus dans des situations tirées au hasard (pente de −8 à +10 %, bots une
fois sur deux, au moins 1 km non revêtu devant une fois sur trois, arrivée à moins de 400 m une fois sur
dix, ERG une fois sur dix) ; part des refus par raison. Tirage : `--passages` tirages du jeu `tactiques` dans
les mêmes situations ; nombre de fois où chaque bonus sort.

`--values` essaie un fichier au format de `~/OpenRide/powerups.toml`. Rejouable à l'octet près : même graine,
même rapport. Code 1 si la médiane d'un bonus sort de la cible, 0 sinon.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .. import draft
from ..physics import PhysicsParams, RiderPhysics, steady_speed
from ..powerups import DEFAULT_TABLE, Context, PowerUps, PowerUpTable, load_table
from ..sim_rider import SimRider

DT = 0.02
HORIZON_S = 60.0
TARGET_S = (1.5, 2.5)
CDA, CRR = 0.32, 0.004
GRAVEL_FACTORS = (2.0, 2.5, 3.0)   # chemin compact, gravier, terre (`config.GravelSettings`)
KINDS = ("feather", "aero", "power", "anvil", "draft_plus", "breakaway", "roller")


@dataclass(frozen=True)
class Pass:
    """Un cycliste et un terrain tirés pour un passage."""

    ftp_w: float
    pct_ftp: float
    mass_kg: float
    grade_pct: float = 0.0
    gap_m: float = 0.0          # roue du bot (Aspiration +) ou du suiveur (Échappée)
    gravel: float = 1.0         # facteur de roulement du gravel (Rouleau)
    seed: int = 0


def _rider(p: Pass) -> SimRider:
    return SimRider("pente", ftp_w=p.ftp_w, pct_ftp=p.pct_ftp, seed=p.seed)


def _ideal(kind: str, rng: random.Random, seed: int) -> Pass:
    base = dict(ftp_w=rng.uniform(200, 320), pct_ftp=rng.uniform(70, 95), mass_kg=rng.uniform(70, 95), seed=seed)
    if kind in ("feather", "power"):
        return Pass(**base, grade_pct=rng.uniform(6, 10))
    if kind == "aero":
        return Pass(**base, grade_pct=rng.uniform(-1, 1))
    if kind == "anvil":
        return Pass(**base, grade_pct=rng.uniform(-8, -3))
    if kind == "draft_plus":
        return Pass(**base, gap_m=rng.uniform(0.5, 2.5))
    if kind == "breakaway":
        return Pass(**base, gap_m=rng.uniform(0.3, 1.5))
    return Pass(**base, gravel=rng.choice(GRAVEL_FACTORS))


def _elsewhere(kind: str, p: Pass) -> Pass:
    """Même cycliste hors du terrain du bonus (ligne « Ailleurs » du tableau du module)."""
    if kind in ("feather", "power", "anvil"):
        return Pass(p.ftp_w, p.pct_ftp, p.mass_kg, 0.0, seed=p.seed)
    if kind == "aero":
        return Pass(p.ftp_w, p.pct_ftp, p.mass_kg, 8.0, seed=p.seed)
    if kind in ("draft_plus", "breakaway"):
        return Pass(p.ftp_w, p.pct_ftp, p.mass_kg, 0.0, gap_m=20.0, seed=p.seed)
    return Pass(p.ftp_w, p.pct_ftp, p.mass_kg, 0.0, gravel=1.0, seed=p.seed)


def _bonus(table: PowerUpTable, kind: str, ctx: Context) -> PowerUps:
    pu = PowerUps(table=table, set_name="tactiques")
    pu.reserve = kind
    pu.activate(0.0, ctx)   # hors du terrain idéal, un refus laisse simplement le bonus en réserve
    return pu


def gain_s(table: PowerUpTable, kind: str, p: Pass) -> float:
    """Avance (s) du cycliste avec le bonus sur le même cycliste sans, 60 s après l'appui."""
    if kind == "breakaway":
        return _breakaway_s(table, p)
    base = PhysicsParams(mass_kg=p.mass_kg, cda_m2=CDA, crr=CRR * p.gravel)
    ctx = Context(grade_pct=p.grade_pct, has_bots=kind == "draft_plus", gravel_ahead=lambda: p.gravel > 1.0)
    pu = _bonus(table, kind, ctx)
    rider = _rider(p)
    alpha0 = draft.draft_coefficient(p.gap_m) if kind == "draft_plus" else 0.0
    p0 = rider.step(0.0, DT, p.grade_pct).power_w
    v0 = steady_speed(p0, p.grade_pct, base)
    a, b = RiderPhysics(base, 0.0, v0), RiderPhysics(base, 0.0, v0)
    t = 0.0
    while t < HORIZON_S - 1e-9:
        t += DT
        w = rider.step(t, DT, p.grade_pct).power_w
        alpha = alpha0
        boost = pu.draft_boost()
        if boost is not None:
            alpha = min(draft.draft_coefficient(p.gap_m, boost.reach_m) * boost.factor, boost.cap)
        params = pu.params(base)
        a.p = PhysicsParams(mass_kg=params.mass_kg, cda_m2=params.cda_m2,
                            crr=CRR * pu.surface_factor(p.gravel) if p.gravel > 1.0 else params.crr)
        s0 = a.s
        a.step(pu.power(w), p.grade_pct, 0.0, DT, alpha_draft=alpha)
        b.step(w, p.grade_pct, 0.0, DT, alpha_draft=alpha0)
        pu.step(DT, Context(grade_pct=p.grade_pct, has_bots=ctx.has_bots, ds_m=a.s - s0,
                            gravel_ahead=ctx.gravel_ahead))
    return (a.s - b.s) / (b.s / HORIZON_S)


def _follower_power(v: float, alpha: float, params: PhysicsParams) -> float:
    """Puissance qui garde un suiveur abrité (`alpha`) à la vitesse `v` du cycliste."""
    probe = RiderPhysics(params, 0.0, v)
    lo, hi = 20.0, 600.0
    for _ in range(40):
        mid = (lo + hi) / 2
        probe.v = v
        probe.step(mid, 0.0, 0.0, 1.0, alpha_draft=alpha)
        lo, hi = (mid, hi) if probe.v < v else (lo, mid)
    return (lo + hi) / 2


def _breakaway_s(table: PowerUpTable, p: Pass) -> float:
    """Mètres perdus par un suiveur pendant l'Échappée (abri du cycliste coupé), en secondes."""
    base = PhysicsParams(mass_kg=p.mass_kg, cda_m2=CDA, crr=CRR)
    rider = _rider(p)
    v = steady_speed(rider.step(0.0, DT, 0.0).power_w, 0.0, base)
    spacing = p.gap_m + draft.BIKE_LENGTH_M

    def run(with_bonus: bool) -> float:
        rider_copy = _rider(p)
        rider_copy.step(0.0, DT, 0.0)
        pu = _bonus(table, "breakaway", Context(has_bots=True)) if with_bonus else None
        alpha = draft.draft_coefficient(p.gap_m)
        p_follow = _follower_power(v, alpha, base)
        bot = SimpleNamespace(id="b1", kind="constant", s=-spacing, v=v, params=base, draft=alpha,
                              wheel=None, push=0.0)
        me, phys = RiderPhysics(base, 0.0, v), RiderPhysics(base, -spacing, v)
        t, end = 0.0, table.specs["breakaway"].duration_s
        while t < end - 1e-9:
            t += DT
            hidden = pu is not None and pu.active == "breakaway"
            draft.update_bots([bot], draft.Source(me.s, me.v, shelters=not hidden), DT)
            me.step(rider_copy.step(t, DT, 0.0).power_w, 0.0, 0.0, DT)
            phys.step(p_follow, 0.0, 0.0, DT, alpha_draft=bot.draft)
            bot.s, bot.v = phys.s, phys.v
            if pu is not None:
                pu.step(DT, Context(has_bots=True))
        return me.s - bot.s

    return (run(True) - run(False)) / v


# --- refus et tirage ------------------------------------------------------------------------------

def _situation(rng: random.Random) -> tuple[Context, bool]:
    grade = rng.uniform(-8, 10)
    gravel = rng.random() < 1 / 3
    ctx = Context(grade_pct=grade, has_bots=rng.random() < 0.5, near_finish=rng.random() < 0.1,
                  descent_ahead=lambda: grade <= -1.5 or rng.random() < 0.3, gravel_ahead=lambda: gravel)
    return ctx, rng.random() < 0.1


def refusals(table: PowerUpTable, passes: int, seed: int) -> dict[str, dict[str, int]]:
    rng = random.Random(seed)
    out: dict[str, dict[str, int]] = {}
    for kind in KINDS:
        reasons: Counter[str] = Counter()
        for _ in range(passes):
            ctx, erg = _situation(rng)
            pu = PowerUps(table=table, set_name="tactiques", erg=erg)
            pu.reserve = kind
            reasons["accepté" if pu.activate(0.0, ctx) else pu.refused.reason] += 1
        out[kind] = dict(sorted(reasons.items()))
    return out


def draws(table: PowerUpTable, passes: int, seed: int) -> dict[str, int]:
    rng = random.Random(seed)
    pu = PowerUps(table=table, set_name="tactiques", seed=seed)
    got: Counter[str] = Counter()
    for _ in range(passes):
        ctx, _erg = _situation(rng)
        got[pu.award("arch", ctx) or "aucun"] += 1
    return {k: got[k] for k in (*KINDS, "aucun")}


# --- rapport --------------------------------------------------------------------------------------

def bench(table: PowerUpTable, passes: int = 50, seed: int = 8) -> dict[str, Any]:
    rng = random.Random(seed)
    rows: dict[str, Any] = {}
    for kind in KINDS:
        ideal, away = [], []
        for i in range(passes):
            p = _ideal(kind, rng, seed * 1000 + i)
            ideal.append(gain_s(table, kind, p))
            away.append(gain_s(table, kind, _elsewhere(kind, p)))
        spec = table.specs[kind]
        inside = sum(TARGET_S[0] <= g <= TARGET_S[1] for g in ideal)
        rows[kind] = {"label": spec.label, "factor": spec.factor, "duration_s": spec.duration_s,
                      "median_s": round(statistics.median(ideal), 2), "min_s": round(min(ideal), 2),
                      "max_s": round(max(ideal), 2), "in_target_pct": round(100 * inside / passes),
                      "elsewhere_median_s": round(statistics.median(away), 2)}
    return {"passes": passes, "seed": seed, "target_s": list(TARGET_S), "gains": rows,
            "refusals": refusals(table, passes, seed), "draws": draws(table, passes, seed)}


def verdict(report: dict[str, Any]) -> list[str]:
    lo, hi = TARGET_S
    return [k for k, r in report["gains"].items() if not lo <= r["median_s"] <= hi]


def markdown(report: dict[str, Any]) -> str:
    lines = [f"Banc des bonus : {report['passes']} passages par bonus, graine {report['seed']}.", "",
             "| Bonus | Facteur | Durée | Gain médian | Min – max | Dans la cible | Ailleurs |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in report["gains"].values():
        lines.append(f"| {r['label']} | {r['factor']:g} | {r['duration_s']:g} s | {r['median_s']:.2f} s | "
                     f"{r['min_s']:.2f} – {r['max_s']:.2f} s | {r['in_target_pct']} % | "
                     f"{r['elsewhere_median_s']:.2f} s |")
    lines += ["", "| Bonus | Refus (sur les appuis) |", "| --- | --- |"]
    for kind, reasons in report["refusals"].items():
        text = ", ".join(f"{k} {v}" for k, v in reasons.items())
        lines.append(f"| {report['gains'][kind]['label']} | {text} |")
    lines += ["", "Tirage du jeu `tactiques` : " + ", ".join(f"{k} {v}" for k, v in report["draws"].items()) + "."]
    out = verdict(report)
    lines += ["", "Verdict : " + ("toutes les médianes dans la cible." if not out
                                  else "hors de la cible : " + ", ".join(out) + ".")]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bonus_bench", description=__doc__.split("\n", 1)[0])
    ap.add_argument("--passages", type=int, default=50)
    ap.add_argument("--graine", type=int, default=8)
    ap.add_argument("--values", type=Path, default=None, help="fichier au format de powerups.toml")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    table = load_table(args.values) if args.values else DEFAULT_TABLE   # défauts du plan, sans le fichier du joueur
    report = bench(table, args.passages, args.graine)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else markdown(report))
    return 1 if verdict(report) else 0


if __name__ == "__main__":
    sys.exit(main())
