#!/usr/bin/env python3
"""Rapport des budgets de l'engine par machine (lot X19).

    python3 engine/tests/perf_budget_report.py [FICHIER ...] [--json] [--strict]

Lit les lignes `[PERF] nom : valeur ms|Ko|%, budget limite ms|Ko|%` écrites par `perf_budget.gd` (sortie de
`run_engine_tests.sh`, ou le fichier `PERF_LINES` qu'il remplit) ou un fichier `PERF_CSV`
(`date;nom;valeur;budget;dépassé;unité`) ; sans fichier, l'entrée standard. Pour chaque budget de
`perf_budgets.json` : la dernière mesure, le budget appliqué sur cette machine (celui de la ligne, qui
tient compte de `CI` et de `~/OpenRide/perf_budgets.json`), la marge en pourcentage du budget, ou
« non mesuré ». Les mesures sans entrée dans `perf_budgets.json` sont listées à part.

Code 0 ; avec `--strict`, 1 si une mesure dépasse son budget.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

BUDGETS = Path(__file__).resolve().parent / "perf_budgets.json"
PERF_RE = re.compile(r"^\[PERF\] (\S+) : ([0-9.]+|inf) (ms|Ko|%), budget ([0-9.]+|inf) (ms|Ko|%)( \(DÉPASSÉ\))?\s*$")
CSV_RE = re.compile(r"^[^;]*;(\S+);([0-9.]+|inf);([0-9.]+|inf);(oui|non)(?:;(ms|Ko|%))?\s*$")


def parse(lines) -> dict[str, dict]:
    """Dernière mesure par nom : {"valeur", "budget", "unite"}."""
    out: dict[str, dict] = {}
    for line in lines:
        m = PERF_RE.match(line.strip())
        if m:
            out[m[1]] = {"valeur": float(m[2]), "budget": float(m[4]), "unite": m[3]}
            continue
        m = CSV_RE.match(line.strip())
        if m:
            out[m[1]] = {"valeur": float(m[2]), "budget": float(m[3]), "unite": m[5] or "ms"}
    return out


def declared(path: Path = BUDGETS) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}


def report(measures: dict[str, dict], budgets: dict[str, dict]) -> list[dict]:
    rows = []
    for name, entry in budgets.items():
        unit = "Ko" if "budget_kb" in entry else entry.get("unite", "ms")
        m = measures.get(name)
        if m is None:
            rows.append({"nom": name, "etat": "non mesuré", "unite": unit, "lot": entry.get("lot", "")})
            continue
        rows.append(_row(name, m, entry.get("lot", "")))
    rows += [_row(name, m, "", unknown=True) for name, m in sorted(measures.items()) if name not in budgets]
    return rows


def _row(name: str, m: dict, lot: str, unknown: bool = False) -> dict:
    budget, value = m["budget"], m["valeur"]
    margin = None if math.isinf(budget) or budget <= 0 else 100.0 * (budget - value) / budget
    state = "sans budget" if unknown or math.isinf(budget) else ("DÉPASSÉ" if value > budget else "OK")
    return {"nom": name, "etat": state, "valeur": value, "budget": budget, "unite": m["unite"],
            "marge_pct": margin, "lot": lot}


def format_rows(rows: list[dict]) -> str:
    measured = [r for r in rows if r["etat"] != "non mesuré"]
    over = [r for r in rows if r["etat"] == "DÉPASSÉ"]
    lines = [f"Budgets de l'engine : {len(measured)} mesurés sur {len(rows)}, {len(over)} dépassement(s)"]
    for r in sorted(measured, key=lambda r: (r["marge_pct"] is None, r["marge_pct"] or 0.0)):
        margin = "" if r["marge_pct"] is None else f", marge {r['marge_pct']:+.0f} %"
        lines.append(f"  [{r['etat']}] {r['nom']} : {r['valeur']:.2f} {r['unite']}, "
                     f"budget {r['budget']:.2f} {r['unite']}{margin}")
    missing = [r["nom"] for r in rows if r["etat"] == "non mesuré"]
    if missing:
        lines.append("Non mesurés : " + ", ".join(missing))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rapport des budgets de l'engine par machine (lot X19).")
    ap.add_argument("files", nargs="*", type=Path, help="sortie de run_engine_tests.sh, PERF_LINES ou PERF_CSV")
    ap.add_argument("--budgets", type=Path, default=BUDGETS, help="perf_budgets.json (défaut : celui des tests)")
    ap.add_argument("--json", action="store_true", help="rapport en JSON")
    ap.add_argument("--strict", action="store_true", help="code 1 si une mesure dépasse son budget")
    args = ap.parse_args(argv)
    lines: list[str] = []
    for f in args.files:
        lines += f.read_text(encoding="utf-8", errors="replace").splitlines()
    if not args.files:
        lines = sys.stdin.read().splitlines()
    rows = report(parse(lines), declared(args.budgets))
    print(json.dumps(rows, ensure_ascii=False, indent=2) if args.json else format_rows(rows))
    return 1 if args.strict and any(r["etat"] == "DÉPASSÉ" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
