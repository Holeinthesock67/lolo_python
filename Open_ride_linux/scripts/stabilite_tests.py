#!/usr/bin/env python3
"""Instabilité et durée des tests (lot X3) : chaque suite lancée N fois, tableau par test.

    scripts/stabilite_tests.py [--fois 5] [--suites core,compiler,engine] [--out DOSSIER] [--godot GODOT]
    scripts/stabilite_tests.py --analyse DOSSIER

Chaque passage lance les suites choisies l'une après l'autre, sous le verrou commun des suites
(`isolation_tests.verrou_suite`) : pytest avec `--junitxml` et `--durations=0` pour le core et le
compilateur, `engine/tests/run_engine_tests.sh` avec `ENGINE_JUNIT` pour l'engine (une entrée par fichier
de test ou étape). Sortie dans `~/OpenRide/stabilite/<date>_<heure>/` :

- `junit/<suite>_<passage>.xml` et `journaux/<suite>_<passage>.log` (bruts) ; `passages.json` (code de
  sortie et durée de chaque suite à chaque passage) ;
- `tests.csv` : suite, test, passages, échecs, absences, durée médiane, durée maximale ;
- `resume.txt` et `resume.json` : tests instables (au moins un échec et une réussite), tests toujours
  en échec, les 20 plus lents (durée médiane), durée totale médiane de chaque suite.

`--analyse DOSSIER` refait l'analyse d'un dossier sans relancer. Code de sortie : 0 sans test instable ni
toujours en échec, 1 sinon. Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
SUITES = ("core", "compiler", "engine")
DEFAULT_OUT = Path.home() / "OpenRide" / "stabilite"
DEFAULT_GODOT = Path.home() / "Applications" / "godot" / "Godot_v4.3-stable_linux.x86_64"
SLOWEST = 20


# --- lancement -----------------------------------------------------------------------------

def command(suite: str, junit: Path, godot: str) -> tuple[list[str], Path, dict[str, str]]:
    """Commande, dossier et variables d'environnement d'une suite."""
    env = dict(os.environ)
    if suite == "engine":
        env.update({"ENGINE_JUNIT": str(junit), "GODOT": godot})
        return ["bash", str(PROJECT / "engine" / "tests" / "run_engine_tests.sh")], PROJECT, env
    src = str(PROJECT / suite / "src")   # sources du dépôt même sans installation (pip install -e)
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return ([sys.executable, "-m", "pytest", "-q", f"--junitxml={junit}", "--durations=0", "-p", "no:cacheprovider"],
            PROJECT / suite, env)


def run_passes(suites: list[str], times: int, out: Path, godot: str) -> list[dict[str, Any]]:
    (out / "junit").mkdir(parents=True, exist_ok=True)
    (out / "journaux").mkdir(parents=True, exist_ok=True)
    passes: list[dict[str, Any]] = []
    for n in range(1, times + 1):
        for suite in suites:
            junit = out / "junit" / f"{suite}_{n}.xml"
            cmd, cwd, env = command(suite, junit, godot)
            print(f"[stabilité] passage {n}/{times} : {suite} …", flush=True)
            t0 = time.monotonic()
            with (out / "journaux" / f"{suite}_{n}.log").open("w", encoding="utf-8") as log:
                rc = subprocess.run(cmd, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, check=False).returncode
            secs = time.monotonic() - t0
            passes.append({"suite": suite, "pass": n, "code": rc, "seconds": round(secs, 1)})
            print(f"[stabilité]   {suite} : code {rc} en {secs / 60:.1f} min", flush=True)
            (out / "passages.json").write_text(json.dumps(passes, indent=2), encoding="utf-8")
    return passes


# --- analyse -------------------------------------------------------------------------------

def read_junit(path: Path) -> dict[str, tuple[str, float]]:
    """Tests d'un rapport JUnit : nom (classe::test) → (statut pass|fail|skip, durée en s)."""
    out: dict[str, tuple[str, float]] = {}
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return out
    for case in root.iter("testcase"):
        cls, name = case.get("classname", ""), case.get("name", "")
        key = f"{cls}::{name}" if cls else name
        if case.find("failure") is not None or case.find("error") is not None:
            st = "fail"
        elif case.find("skipped") is not None:
            st = "skip"
        else:
            st = "pass"
        out[key] = (st, float(case.get("time") or 0.0))
    return out


def suite_time(path: Path) -> float | None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    return sum(float(s.get("time") or 0.0) for s in suites) if suites else None


def analyse(folder: Path) -> dict[str, Any]:
    """Tableau par test des rapports `junit/<suite>_<passage>.xml` du dossier."""
    runs: dict[str, dict[int, Path]] = {}
    for f in sorted((folder / "junit").glob("*_*.xml")):
        suite, _, n = f.stem.rpartition("_")
        if suite and n.isdigit():
            runs.setdefault(suite, {})[int(n)] = f
    passes = []
    if (folder / "passages.json").is_file():
        passes = json.loads((folder / "passages.json").read_text(encoding="utf-8"))
    tests: list[dict[str, Any]] = []
    totals: dict[str, dict[str, Any]] = {}
    for suite, files in runs.items():
        results = {n: read_junit(p) for n, p in files.items()}
        names = sorted({k for r in results.values() for k in r})
        for name in names:
            seen = [r[name] for r in results.values() if name in r]
            ran = [(st, t) for st, t in seen if st != "skip"]
            if not ran:
                continue
            durations = [t for _, t in ran]
            tests.append({"suite": suite, "test": name, "passages": len(ran),
                          "echecs": sum(st == "fail" for st, _ in ran),
                          "absences": len(files) - len(seen),
                          "duree_mediane_s": round(statistics.median(durations), 3),
                          "duree_max_s": round(max(durations), 3)})
        walls = [p["seconds"] for p in passes if p["suite"] == suite]
        if not walls:
            walls = [t for t in (suite_time(p) for p in files.values()) if t is not None]
        totals[suite] = {"passages": len(files),
                         "duree_mediane_s": round(statistics.median(walls), 1) if walls else None,
                         "codes": [p["code"] for p in passes if p["suite"] == suite]}
    unstable = [t for t in tests if 0 < t["echecs"] < t["passages"]]
    always = [t for t in tests if t["echecs"] == t["passages"]]
    slowest = sorted(tests, key=lambda t: -t["duree_mediane_s"])[:SLOWEST]
    return {"suites": totals, "tests": tests, "instables": unstable, "toujours_en_echec": always,
            "plus_lents": slowest}


def summary_text(res: dict[str, Any]) -> str:
    lines = ["Instabilité et durée des tests (lot X3)", ""]
    for suite, s in res["suites"].items():
        d = s["duree_mediane_s"]
        lines.append(f"  {suite:<9} {s['passages']} passage(s), durée médiane "
                     f"{f'{d / 60:.1f} min' if d is not None else '?'}"
                     + (f", codes {s['codes']}" if s["codes"] else ""))
    lines += ["", f"Tests instables (au moins un échec et une réussite) : {len(res['instables'])}"]
    for t in res["instables"]:
        lines.append(f"  {t['suite']} {t['test']} : {t['echecs']} échec(s) sur {t['passages']}"
                     + (f", absent {t['absences']} fois" if t["absences"] else ""))
    lines += ["", f"Tests toujours en échec : {len(res['toujours_en_echec'])}"]
    for t in res["toujours_en_echec"]:
        lines.append(f"  {t['suite']} {t['test']} : {t['echecs']} échec(s) sur {t['passages']}")
    lines += ["", f"Les {len(res['plus_lents'])} tests les plus lents (durée médiane, maximale) :"]
    for t in res["plus_lents"]:
        lines.append(f"  {t['duree_mediane_s']:>8.2f} s {t['duree_max_s']:>8.2f} s  {t['suite']} {t['test']}")
    return "\n".join(lines) + "\n"


def write(folder: Path, res: dict[str, Any]) -> str:
    cols = ["suite", "test", "passages", "echecs", "absences", "duree_mediane_s", "duree_max_s"]
    with (folder / "tests.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter=";")
        w.writeheader()
        w.writerows(res["tests"])
    text = summary_text(res)
    (folder / "resume.txt").write_text(text, encoding="utf-8")
    (folder / "resume.json").write_text(json.dumps({k: v for k, v in res.items() if k != "tests"},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Instabilité et durée des tests (lot X3).")
    ap.add_argument("--fois", type=int, default=5, help="nombre de passages (défaut 5)")
    ap.add_argument("--suites", default=",".join(SUITES), help="suites, séparées par des virgules")
    ap.add_argument("--out", type=Path, help=f"dossier de sortie (défaut {DEFAULT_OUT}/<date>_<heure>)")
    ap.add_argument("--godot", default=os.environ.get("GODOT", str(DEFAULT_GODOT)), help="Godot 4.3 (suite engine)")
    ap.add_argument("--analyse", type=Path, metavar="DOSSIER", help="refaire l'analyse d'un dossier sans relancer")
    args = ap.parse_args(argv)
    if args.analyse is not None:
        if not (args.analyse / "junit").is_dir():
            print(f"Pas de dossier junit/ dans {args.analyse}")
            return 2
        folder = args.analyse
    else:
        suites = [s.strip() for s in args.suites.split(",") if s.strip()]
        unknown = [s for s in suites if s not in SUITES]
        if unknown or not suites or args.fois < 1:
            print(f"Suites possibles : {', '.join(SUITES)} ; --fois au moins 1")
            return 2
        folder = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H%M%S")
        sys.path.insert(0, str(PROJECT / "scripts"))
        from isolation_tests import verrou_suite   # une seule suite de tests ou banc à la fois

        with verrou_suite("stabilite_tests"):
            run_passes(suites, args.fois, folder, args.godot)
    res = analyse(folder)
    print(write(folder, res), end="")
    print(f"Résultats : {folder}")
    return 0 if not res["instables"] and not res["toujours_en_echec"] else 1


if __name__ == "__main__":
    sys.exit(main())
