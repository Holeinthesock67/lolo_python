#!/usr/bin/env python3
"""Recette du PC en une commande (lot X4).

Règle du projet : les tests tournent sur le PC cible, pas sur GitHub Actions. Ce script enchaîne
les suites, garde chaque journal et écrit un résumé, comparé au passage précédent :

    scripts/recette_pc.py                    # tout : core, compilateur, engine, bout en bout, graphiques, menus,
                                             # séances simulées (série T, boutons ERG, course), confidentialité
    scripts/recette_pc.py --rapide           # core sans les tests lents, sans tests graphiques, banc des menus ni séances
    scripts/recette_pc.py --seulement core,engine
    scripts/recette_pc.py --sans visual
    scripts/recette_pc.py --seulement deps    # étape facultative : audit des dépendances (lot X24), réseau

Sortie : `~/OpenRide/recettes/<date>_<heure>/` (`--out` pour un autre dossier) avec un journal par
étape, `resume.txt`, `resume.json` et `perf.csv` (budgets de temps de l'engine, lot X2).
Variables : GODOT (exécutable Godot 4.7), OPENRIDE_VENV (défaut core/.venv).
Code de sortie : 0 si toutes les étapes passent, 1 sinon, 2 si l'appel est invalide.
Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]          # Open_ride_linux/
REPO = PROJECT.parent
sys.path.insert(0, str(PROJECT / "core" / "src"))
from openride_core.tools.guide import Guide  # noqa: E402  (bibliothèque standard seulement)

DEFAULT_OUT = Path.home() / "OpenRide" / "recettes"
STEPS = ("core", "compiler", "engine", "e2e", "visual", "menus", "seances", "privacy", "deps")
OPTIONAL_STEPS = ("deps",)    # lancées seulement si nommées dans --seulement
SEANCES = ("serie_t", "erg_boutons", "course_bots")   # scénarios du banc (engine/tests/sim_bench_scenarios/)
EXIT_SKIPPED = 75             # code d'une étape impossible ici (sans réseau) : SAUTÉ


@dataclass
class StepResult:
    name: str
    status: str            # « OK », « ÉCHEC » ou « SAUTÉ »
    seconds: float
    detail: str
    log: str


def python_bin() -> str:
    venv = Path(os.environ.get("OPENRIDE_VENV", PROJECT / "core" / ".venv"))
    candidate = venv / "bin" / "python"
    return str(candidate) if candidate.is_file() else sys.executable


def step_commands(rapide: bool, out: Path) -> dict[str, tuple[list[str], Path]]:
    py = python_bin()
    core_cmd = [py, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + (["-m", "not slow"] if rapide else [])
    return {
        "core": (core_cmd, PROJECT / "core"),
        "compiler": ([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"], PROJECT / "compiler"),
        "engine": (["bash", str(PROJECT / "engine" / "tests" / "run_engine_tests.sh")], PROJECT),
        "e2e": (["bash", str(PROJECT / "engine" / "tests" / "run_e2e.sh")], PROJECT),
        "visual": (["bash", str(PROJECT / "engine" / "tests" / "run_visual_tests.sh")], PROJECT),
        "menus": ([py, str(PROJECT / "engine" / "tests" / "menu_bench.py"), "--out", str(out / "menus")], PROJECT),
        # Séances simulées de la recette T11 et de l'essai J7 (lots X33 et Z2) : ce qui se vérifie sans pédaler.
        "seances": ([py, str(PROJECT / "engine" / "tests" / "sim_bench.py")]
                    + [arg for name in SEANCES for arg in ("--scenario", name)] + ["--out", str(out / "seances")], PROJECT),
        "privacy": ([py, str(PROJECT / "scripts" / "privacy" / "privacy_scan.py"), "--all"], REPO),
        "deps": ([py, str(PROJECT / "scripts" / "audit_dependances.py"), "--out", str(out / "deps")], PROJECT),
    }


def detail_of(name: str, text: str) -> str:
    """Ligne utile de la sortie d'une étape (compte de tests ou résultat)."""
    if name in ("core", "compiler"):
        m = re.findall(r"^=*\s*(\d+ (?:passed|failed).*?) in [\d.]+s", text, re.M)
        return m[-1] if m else ""
    patterns = {
        "engine": r"^(RÉSULTAT : .*|Budgets de temps .*)$",
        "e2e": r"^(RÉSULTAT.*|.*vérifications.*)$",
        "visual": r"^(.*vérifications réussies.*|RÉSULTAT.*)$",
        "menus": r"^(OK|\d+ passage\(s\) en échec.*|xvfb-run introuvable.*)$",
        "seances": r"^(RÉSULTAT : .*)$",
        "privacy": r"^(privacy_scan : .*)$",
        "deps": r"^(Vulnérabilités connues : .*|Actions GitHub : .*|audit_dependances : .*)$",
    }
    found = re.findall(patterns.get(name, r"$^"), text, re.M)
    return " ; ".join(found[-2:])


def run_step(name: str, cmd: list[str], cwd: Path, out: Path, env: dict[str, str]) -> StepResult:
    log = out / f"{name}.log"
    t0 = time.monotonic()
    with log.open("w", encoding="utf-8") as fh:
        fh.write(f"$ {' '.join(cmd)}\n")
        fh.flush()
        try:
            rc = subprocess.run(cmd, cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT, check=False).returncode
        except FileNotFoundError as err:
            fh.write(f"{err}\n")
            rc = 127
    seconds = time.monotonic() - t0
    text = log.read_text(encoding="utf-8", errors="replace")
    status = "OK" if rc == 0 else "SAUTÉ" if rc == EXIT_SKIPPED else "ÉCHEC"
    detail = detail_of(name, text) or f"code {rc}"
    return StepResult(name, status, round(seconds, 1), detail, log.name)


def previous_summary(root: Path, current: Path) -> dict | None:
    if not root.is_dir():
        return None
    runs = sorted(p for p in root.iterdir() if p.is_dir() and p != current and (p / "resume.json").is_file())
    if not runs:
        return None
    return json.loads((runs[-1] / "resume.json").read_text(encoding="utf-8"))


def compare(results: list[StepResult], prev: dict | None) -> list[str]:
    if not prev:
        return ["Premier passage : rien à comparer."]
    before = {s["name"]: s for s in prev.get("steps", [])}
    lines = [f"Comparaison avec le passage du {prev.get('started', '?')} :"]
    for r in results:
        old = before.get(r.name)
        if old is None:
            lines.append(f"  {r.name} : nouvelle étape")
        elif old["status"] != r.status:
            lines.append(f"  {r.name} : {old['status']} → {r.status}")
        elif old.get("detail") != r.detail and r.status != "SAUTÉ":
            lines.append(f"  {r.name} : {old.get('detail')} → {r.detail}")
    if len(lines) == 1:
        lines.append("  aucun changement")
    return lines


def parse_steps(value: str) -> list[str]:
    names = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [n for n in names if n not in STEPS]
    if unknown:
        raise argparse.ArgumentTypeError(f"étape inconnue : {', '.join(unknown)} (connues : {', '.join(STEPS)})")
    return names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recette du PC en une commande (lot X4).")
    ap.add_argument("--out", type=Path, help=f"dossier de sortie (défaut : {DEFAULT_OUT}/<date>)")
    ap.add_argument("--rapide", action="store_true", help="core sans les tests lents, sans tests graphiques, banc des menus ni séances simulées")
    ap.add_argument("--seulement", type=parse_steps, help=f"étapes à lancer parmi {','.join(STEPS)}")
    ap.add_argument("--sans", type=parse_steps, default=[], help="étapes à sauter")
    ap.add_argument("--perf-strict", action="store_true", help="un budget de temps dépassé fait échouer l'engine")
    ap.add_argument("--muet", action="store_true", help="sans bip de fin")
    args = ap.parse_args(argv)

    started = datetime.now()
    root = DEFAULT_OUT if args.out is None else args.out.parent
    out = args.out or DEFAULT_OUT / started.strftime("%Y-%m-%d_%H%M%S")
    out.mkdir(parents=True, exist_ok=True)

    wanted = list(args.seulement or [s for s in STEPS if s not in OPTIONAL_STEPS])
    if args.rapide and not args.seulement:
        wanted.remove("visual")
        wanted.remove("menus")
        wanted.remove("seances")
    wanted = [s for s in wanted if s not in args.sans]

    env = dict(os.environ)
    venv_bin = Path(python_bin()).parent
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
    env["PERF_CSV"] = str(out / "perf.csv")
    env["OPENRIDE_PERF"] = "strict" if args.perf_strict else env.get("OPENRIDE_PERF", "report")
    env.setdefault("VISUAL_OUT", str(out / "visual"))

    commands = step_commands(args.rapide, out)
    guide = Guide("Recette du PC", out / "guide.jsonl", sound=sys.stdout.isatty() and not args.muet,
                  screen=False, out=io.StringIO())   # lignes déjà affichées par le script : son et journal
    results: list[StepResult] = []
    for name in STEPS:
        if name not in wanted:
            results.append(StepResult(name, "SAUTÉ", 0.0, "", ""))
            continue
        cmd, cwd = commands[name]
        print(f"== {name} …", flush=True)
        guide.step(name, beep=False, index=wanted.index(name) + 1, total=len(wanted))
        res = run_step(name, cmd, cwd, out, env)
        print(f"   {res.status} en {res.seconds:.0f} s{' : ' + res.detail if res.detail else ''}", flush=True)
        guide.measure(name, f"{res.status} en {res.seconds:.0f} s", ok=res.status == "OK")
        results.append(res)

    ran = [r for r in results if r.status != "SAUTÉ"]
    ok = all(r.status == "OK" for r in ran)
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                                text=True, check=False).stdout.strip()
    except FileNotFoundError:
        commit = ""
    summary = {"started": started.isoformat(timespec="seconds"), "commit": commit, "ok": ok,
               "steps": [asdict(r) for r in results]}
    prev = previous_summary(root, out)
    lines = [f"Recette du PC, {started:%d/%m/%Y %H:%M}, commit {commit or '?'}", ""]
    width = max(len(s) for s in STEPS)
    for r in results:
        timing = f"{r.seconds:>6.0f} s" if r.status != "SAUTÉ" else " " * 8
        lines.append(f"  {r.status:<6} {r.name:<{width}} {timing}  {r.detail}")
    lines += ["", *compare(results, prev), "", f"RÉSULTAT : {'tout passe' if ok else 'ÉCHEC'}",
              f"Journaux : {out}"]
    text = "\n".join(lines) + "\n"
    (out / "resume.txt").write_text(text, encoding="utf-8")
    (out / "resume.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(text, end="")
    guide.finish(ok, "tout passe" if ok else "ÉCHEC")   # bip de fin (son seulement : déjà affiché)
    guide.close()
    if shutil.which("notify-send") and sys.stdout.isatty():
        subprocess.run(["notify-send", "OpenRide : recette du PC", "tout passe" if ok else "ÉCHEC"], check=False)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT / "scripts"))
    from isolation_tests import verrou_suite   # une seule suite de tests ou banc à la fois

    with verrou_suite("recette_pc"):
        code = main()
    sys.exit(code)
