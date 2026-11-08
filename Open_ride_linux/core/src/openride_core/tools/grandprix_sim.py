"""Simulateur d'équilibrage du Grand Prix des objets (lot GP5).

    python -m openride_core.tools.grandprix_sim [--races 200] [--seed 1] [--opponents 2,4,11]
        [--chaos soft,normal,wild] [--levels 100,90] [--values FICHIER.toml] [--report FICHIER.md]
        [--json] [--jobs N]

Courses de 10 km en ligne (rangées de boîtes tous les 1,5 km, réglage par défaut), en temps accéléré
(pas de `DT_S`), sans trainer ni engine : physique du core (`RiderPhysics`), abri en une dimension sur la voie
du coureur (`draft.draft_coefficient` derrière le plus proche devant), règles du mode (`GrandPrixMode`) et
bots du lot GP3 (`BotBrain`). Le cycliste virtuel roule à puissance constante (stratégie `constante` du
cycliste X27) et joue ses objets avec les règles d'un bot de son niveau, mené par le même cerveau au même
moment du pas : un joueur qui ne se trompe pas, ni trop tôt ni trop tard.

Chaque course tire la forme du jour de chacun (± 3 % autour de sa puissance), à partir de la graine : même
graine, même rapport à l'octet près, quel que soit `--jobs`. Le cycliste roule au niveau `--levels` (en % de la
puissance des bots : 100 à niveau égal, 90 à 10 % sous les bots).

Cibles du cahier `docs/lots/LOT_GP5_equilibrage.md` §3 (course juste, choix du propriétaire du 8 novembre) :
à niveau égal, le cycliste gagne sa part, entre 0,5/(N + 1) et 1,5/(N + 1) des courses ; plus faible que les bots,
aucune cible de victoires (pas de rattrapage fort), seulement un rapport ; aucun objet ne fait plus de 35 % du
temps total gagné ou perdu (tous coureurs, toutes courses d'une configuration).
Code 0 si les cibles sont tenues, 1 sinon, 2 pour un appel invalide.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..draft import GAP_CUTOFF_M, draft_coefficient
from ..grandprix import ITEM_IDS, ME
from ..grandprix.effects import CHAOS
from ..grandprix.items import DEFAULT_TABLE, ItemTable, load_table
from ..grandprix.mode import GpInput, GrandPrixMode, RiderIn
from ..physics import PhysicsParams, RiderPhysics, steady_speed

DT_S = 0.2
LENGTH_M = 10_000.0
BOT_POWER_W = 250.0
FORM_SPREAD = 0.03
START_ROW_M = 2.7                   # grille : un coureur tous les 2,7 m (draft.START_ROW_M)
MAX_ITEM_SHARE = 0.35
FAIR_SHARE = (0.5, 1.5)             # victoires à niveau égal, en parts de 1/(N + 1)
LANE_M = (0.68, 1.45, 2.22)        # centres des voies (mode.LANE_CENTRES_M)


def _seed(*parts: Any) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")


def race(opponents: int, chaos: str, level_pct: float, seed: int, table: ItemTable = DEFAULT_TABLE) -> dict:
    """Une course : place du cycliste, et temps gagné et perdu par objet (tous coureurs)."""
    rng = random.Random(_seed("course", opponents, chaos, level_pct, seed))
    ids = [ME, *(f"bot{i + 1}" for i in range(opponents))]
    grid = ids[:]
    rng.shuffle(grid)
    power = {rid: BOT_POWER_W * (level_pct / 100.0 if rid == ME else 1.0) * rng.uniform(1 - FORM_SPREAD, 1 + FORM_SPREAD)
             for rid in ids}
    p = PhysicsParams()
    phys = {rid: RiderPhysics(replace(p), -START_ROW_M * grid.index(rid), steady_speed(power[rid], 0.0, p))
            for rid in ids}
    v_eq = {rid: steady_speed(power[rid], 0.0, p) for rid in ids}
    mode = GrandPrixMode(ids, LENGTH_M, table=table, chaos=chaos, seed=_seed("mode", seed, opponents, chaos),
                         bots=ids, levels={ME: level_pct})

    def inputs() -> dict[str, RiderIn]:
        return {rid: RiderIn(ph.s, ph.v, v_eq[rid], LANE_M[mode.racers[rid].lane], 0.0) for rid, ph in phys.items()}

    mode.start(0.0, inputs())
    t = 0.0
    while not mode.finished and t < 3 * LENGTH_M / 5.0:
        t += DT_S
        for rid, ph in phys.items():
            r = mode.racers[rid]
            if r.finished is not None:
                continue
            gaps = [o.s - ph.s for oid, o in phys.items() if oid != rid and 0.0 < o.s - ph.s <= GAP_CUTOFF_M
                    and mode.racers[oid].lane == r.lane and mode.racers[oid].finished is None]
            alpha = draft_coefficient(min(gaps)) if gaps else 0.0
            ph.p = replace(p, wind_mps=mode.wind_mps(rid))
            ph.step(power[rid], 0.0, dt=DT_S, alpha_draft=alpha)
        out = mode.step(GpInput(t, DT_S, inputs()))
        for rid, v in out.items():
            phys[rid].v = v
    gained: dict[str, float] = {}
    for r in mode.racers.values():
        for item, s in list(r.gained_s.items()) + list(r.lost_s.items()):
            gained[item] = gained.get(item, 0.0) + abs(s)
    return {"place": mode.place(ME), "of": len(ids), "time": gained,
            "launched": sum(sum(r.launched.values()) for r in mode.racers.values())}


def _batch(task: tuple) -> dict[str, Any]:
    opponents, chaos, level, races, seed, table = task
    wins, places, launched = 0, 0, 0
    time: dict[str, float] = {}
    for i in range(races):
        out = race(opponents, chaos, level, _seed(seed, i), table)
        wins += out["place"] == 1
        places += out["place"]
        launched += out["launched"]
        for k, v in out["time"].items():
            time[k] = time.get(k, 0.0) + v
    total = sum(time.values())
    share = {k: round(v / total, 4) for k, v in sorted(time.items())} if total else {}
    return {"opponents": opponents, "chaos": chaos, "level_pct": level, "races": races, "wins": wins,
            "mean_place": round(places / races, 2), "items_per_race": round(launched / races, 1), "share": share}


def simulate(opponents: list[int], chaos: list[str], levels: list[float], races: int, seed: int,
             table: ItemTable = DEFAULT_TABLE, jobs: int = 1) -> dict[str, Any]:
    tasks = [(n, c, lv, races, seed, table) for n in opponents for c in chaos for lv in levels]
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            batches = list(ex.map(_batch, tasks))
    else:
        batches = [_batch(t) for t in tasks]
    return {"seed": seed, "races": races, "batches": batches}


def criteria(out: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    for b in out["batches"]:
        n, rate = b["opponents"], b["wins"] / b["races"]
        label = f"{n} bots, chaos {b['chaos']}, niveau {b['level_pct']:g} %"
        if b["level_pct"] == 100.0:
            lo, hi = FAIR_SHARE[0] / (n + 1), FAIR_SHARE[1] / (n + 1)
            checks.append({"ok": lo <= rate <= hi, "text": f"{label} : {100 * rate:.1f} % de victoires "
                                                          f"(part juste, cible {100 * lo:.1f} à {100 * hi:.1f} %)"})
        if b["share"]:
            item, share = max(b["share"].items(), key=lambda kv: kv[1])
            checks.append({"ok": share <= MAX_ITEM_SHARE,
                           "text": f"{label} : objet le plus lourd {item}, {100 * share:.1f} % du temps gagné ou "
                                   f"perdu (au plus {100 * MAX_ITEM_SHARE:.0f} %)"})
    return checks


def report_markdown(out: dict[str, Any], checks: list[dict[str, Any]]) -> str:
    lines = ["# Rapport d'équilibrage du Grand Prix des objets (lot GP5)", "",
             f"Produit par `python -m openride_core.tools.grandprix_sim` : {out['races']} courses par configuration, "
             f"graine {out['seed']}, courses de {LENGTH_M / 1000:g} km en ligne, bots à {BOT_POWER_W:g} W "
             f"(forme ± {100 * FORM_SPREAD:g} %), pas de {DT_S:g} s.", "",
             "| Bots | Chaos | Niveau | Victoires du cycliste | Place moyenne | Objets par course | Objet le plus lourd |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for b in out["batches"]:
        item, share = max(b["share"].items(), key=lambda kv: kv[1]) if b["share"] else ("–", 0.0)
        lines.append(f"| {b['opponents']} | {b['chaos']} | {b['level_pct']:g} % | "
                     f"{100 * b['wins'] / b['races']:.1f} % | {b['mean_place']:.2f} | {b['items_per_race']:.1f} | "
                     f"{item} ({100 * share:.1f} %) |")
    lines += ["", "## Part de chaque objet dans le temps gagné ou perdu", "",
              "| Bots | Chaos | Niveau | " + " | ".join(ITEM_IDS) + " |",
              "| --- | --- | --- | " + " | ".join("---" for _ in ITEM_IDS) + " |"]
    for b in out["batches"]:
        lines.append(f"| {b['opponents']} | {b['chaos']} | {b['level_pct']:g} % | "
                     + " | ".join(f"{100 * b['share'].get(i, 0.0):.1f}" for i in ITEM_IDS) + " |")
    lines += ["", "## Cibles", ""]
    lines += [f"- {'OK' if c['ok'] else 'ÉCART'} : {c['text']}" for c in checks]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Simulateur d'équilibrage du Grand Prix des objets (lot GP5).")
    ap.add_argument("--races", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--opponents", default="2,4,11")
    ap.add_argument("--chaos", default=",".join(CHAOS))
    ap.add_argument("--levels", default="100,90")
    ap.add_argument("--values", type=Path, help="fichier de valeurs à essayer (format de grandprix.toml)")
    ap.add_argument("--report", type=Path, help="écrit le rapport Markdown dans ce fichier")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--jobs", type=int, default=1)
    args = ap.parse_args(argv)
    try:
        opponents = [int(x) for x in args.opponents.split(",")]
        chaos = args.chaos.split(",")
        levels = [float(x) for x in args.levels.split(",")]
        if any(c not in CHAOS for c in chaos) or any(not 1 <= n <= 11 for n in opponents) or args.races < 1:
            raise ValueError
        table = load_table(args.values) if args.values else DEFAULT_TABLE
    except (ValueError, OSError) as exc:
        print(f"appel invalide : {exc}", file=sys.stderr)
        return 2
    out = simulate(opponents, chaos, levels, args.races, args.seed, table, max(args.jobs, 1))
    checks = criteria(out)
    text = report_markdown(out, checks)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1) if args.json else text)
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
