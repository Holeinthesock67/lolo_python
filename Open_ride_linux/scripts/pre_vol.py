#!/usr/bin/env python3
"""Pré-vol avant une séance vélo (lot X36).

Règle du projet (28 octobre) : une séance vélo tient en 20 minutes de pédalage. Tout ce qui se vérifie
sans pédaler l'est avant, en une commande, avec un verdict « PRÊT À ROULER » :

    scripts/pre_vol.py --seance t11_j7
    scripts/pre_vol.py --seance p27 --sans-bluetooth
    scripts/pre_vol.py --liste

Étapes, dans l'ordre :
  1. git : branche, rien de non commité, à jour avec origin (`--sans-reseau` : pas de `git fetch`) ;
  2. tests : pytest du core avec la marque de la séance (`recette_sans_velo`) ;
  3. engine : `run_engine_tests.sh` avec les tests unitaires de la séance (UNIT) ;
  4. séance simulée : `sim_bench.py` sur les scénarios de la séance (lot X33 quand ils existent) ;
  5. fichiers : `config.toml` sauvegardé en `config.toml.<séance>`, parcours compilés présents,
     fichiers de la séance posés (`powerups.toml`…) ou mis de côté ;
  6. Bluetooth : trainer et Click visibles (`openride-core devices --json`) ;
  7. verdict, avec bip (guide).
`--sans-engine` saute les étapes 3 et 4 (pas de Godot), `--sans-bluetooth` l'étape 6.

Séances : `scripts/pre_vol_seances.toml`. Journal : `~/OpenRide/pre_vol/<date>_<heure>/` (un journal par
étape, `resume.txt`, `resume.json`, `guide.jsonl`). Variables : GODOT, OPENRIDE_VENV (défaut core/.venv).
Code de sortie : 0 si prêt à rouler, 1 sinon, 2 si l'appel est invalide. Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

PROJECT = Path(__file__).resolve().parents[1]          # Open_ride_linux/
REPO = PROJECT.parent
sys.path.insert(0, str(PROJECT / "core" / "src"))
from openride_core.tools.guide import Guide  # noqa: E402  (bibliothèque standard seulement)

SEANCES_FILE = PROJECT / "scripts" / "pre_vol_seances.toml"
DEFAULT_OUT = Path.home() / "OpenRide" / "pre_vol"
ROUTES_DIR = Path.home() / ".local" / "share" / "openride" / "routes"   # config.ROUTES_DIR
CONFIG = Path.home() / "OpenRide" / "config.toml"
STEPS = ("git", "tests", "engine", "simulee", "fichiers", "bluetooth")
SEANCE_KEYS = {"titre", "pytest_marque", "engine_unit", "sim_scenarios", "parcours", "appareils", "poser", "retirer"}
PYTEST_NO_TESTS = 5          # code de pytest quand aucun test ne porte la marque
BLUETOOTH_TIMEOUT_S = 8


@dataclass
class StepResult:
    name: str
    status: str            # « OK », « ÉCHEC » ou « SAUTÉ »
    detail: str
    seconds: float = 0.0
    blockers: list[str] = field(default_factory=list)   # ce qui empêche de rouler


# Une commande : (argv, dossier, variables en plus) -> (code de retour, sortie). Remplacée dans les tests.
Runner = Callable[[list[str], Path, dict[str, str]], tuple[int, str]]


def run_command(cmd: list[str], cwd: Path, extra_env: dict[str, str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, env={**os.environ, **extra_env}, capture_output=True, text=True,
                           check=False)
    except FileNotFoundError as err:
        return 127, str(err)
    return p.returncode, p.stdout + p.stderr


def python_bin() -> str:
    venv = Path(os.environ.get("OPENRIDE_VENV", PROJECT / "core" / ".venv"))
    candidate = venv / "bin" / "python"
    return str(candidate) if candidate.is_file() else sys.executable


def load_seances(path: Path = SEANCES_FILE) -> dict[str, dict[str, Any]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for name, seance in data.items():
        unknown = set(seance) - SEANCE_KEYS
        if unknown:
            raise ValueError(f"{path.name} [{name}] : clé(s) inconnue(s) {', '.join(sorted(unknown))}")
    return data


def home_path(text: str, home: Path) -> Path:
    return home / text[2:] if text.startswith("~/") else Path(text)


# --- étapes ----------------------------------------------------------------------------------------

def step_git(run: Runner, fetch: bool) -> StepResult:
    rc, out = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], REPO, {})
    if rc != 0:
        return StepResult("git", "ÉCHEC", "pas un dépôt git", blockers=["dépôt git illisible"])
    branch = out.strip().splitlines()[-1] if out.strip() else "?"
    blockers: list[str] = []
    _, status = run(["git", "status", "--porcelain", "--untracked-files=no"], REPO, {})
    changed = [ln for ln in status.splitlines() if ln.strip()]
    if changed:
        blockers.append(f"{len(changed)} fichier(s) modifié(s) non commité(s) ({changed[0].strip()}…)")
    behind_txt = "non vérifié (--sans-reseau)" if not fetch else "origin injoignable"
    if fetch:
        rc, out = run(["git", "fetch", "-q", "origin", branch], REPO, {})
        if rc != 0:
            blockers.append(f"git fetch origin {branch} impossible : {out.strip()[-120:]}")
        else:
            rc, out = run(["git", "rev-list", "--count", f"HEAD..origin/{branch}"], REPO, {})
            behind = int(out.strip() or 0) if rc == 0 and out.strip().isdigit() else None
            if behind is None:
                blockers.append(f"branche {branch} absente d'origin")
                behind_txt = "absente d'origin"
            elif behind:
                blockers.append(f"{behind} commit(s) de retard sur origin/{branch} (git pull --ff-only)")
                behind_txt = f"{behind} commit(s) de retard"
            else:
                behind_txt = "à jour"
    detail = f"branche {branch}, {behind_txt}, {'rien de non commité' if not changed else f'{len(changed)} modifié(s)'}"
    return StepResult("git", "ÉCHEC" if blockers else "OK", detail, blockers=blockers)


def step_tests(run: Runner, seance: dict[str, Any], out: Path) -> StepResult:
    marque = seance.get("pytest_marque")
    if not marque:
        return StepResult("tests", "SAUTÉ", "pas de marque pytest pour cette séance")
    rc, text = run([python_bin(), "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", marque], PROJECT / "core", {})
    (out / "tests.log").write_text(text, encoding="utf-8")
    last = next((ln for ln in reversed(text.splitlines()) if ln.strip()), "")
    if rc == PYTEST_NO_TESTS:
        return StepResult("tests", "ÉCHEC", f"aucun test marqué {marque}",
                          blockers=[f"aucun test ne porte la marque {marque} (branche trop ancienne ?)"])
    if rc != 0:
        return StepResult("tests", "ÉCHEC", last, blockers=[f"tests {marque} : {last} (tests.log)"])
    return StepResult("tests", "OK", last)


def step_engine(run: Runner, seance: dict[str, Any], out: Path, enabled: bool) -> StepResult:
    units = list(seance.get("engine_unit") or [])
    if not enabled:
        return StepResult("engine", "SAUTÉ", "--sans-engine")
    if not units:
        return StepResult("engine", "SAUTÉ", "pas de test unitaire Godot pour cette séance")
    failed, logs = [], []
    for unit in units:
        rc, text = run(["bash", str(PROJECT / "engine" / "tests" / "run_engine_tests.sh")], PROJECT, {"UNIT": unit})
        logs.append(f"== {unit} (code {rc})\n{text}")
        if rc != 0:
            failed.append(unit)
    (out / "engine.log").write_text("\n".join(logs), encoding="utf-8")
    if failed:
        return StepResult("engine", "ÉCHEC", f"{len(failed)}/{len(units)} en échec",
                          blockers=[f"test Godot {u} en échec (engine.log)" for u in failed])
    return StepResult("engine", "OK", f"{len(units)} test(s) : {', '.join(units)}")


def step_simulee(run: Runner, seance: dict[str, Any], out: Path, enabled: bool) -> StepResult:
    scenarios = list(seance.get("sim_scenarios") or [])
    if not enabled:
        return StepResult("simulee", "SAUTÉ", "--sans-engine")
    if not scenarios:
        return StepResult("simulee", "SAUTÉ", "pas de séance simulée pour cette séance (lot X33)")
    cmd = [python_bin(), str(PROJECT / "engine" / "tests" / "sim_bench.py"), "--out", str(out / "simulee"), "--muet"]
    for s in scenarios:
        cmd += ["--scenario", s]
    rc, text = run(cmd, PROJECT, {})
    (out / "simulee.log").write_text(text, encoding="utf-8")
    if rc != 0:
        return StepResult("simulee", "ÉCHEC", f"code {rc}",
                          blockers=[f"séance simulée en échec : {out / 'simulee' / 'index.html'}"])
    return StepResult("simulee", "OK", f"{len(scenarios)} scénario(s) : {', '.join(scenarios)}")


def step_fichiers(seance_name: str, seance: dict[str, Any], home: Path, routes: Path, config: Path,
                  stamp: str) -> StepResult:
    blockers: list[str] = []
    done: list[str] = []
    if config.is_file():
        backup = config.with_name(f"{config.name}.{seance_name}")
        shutil.copy2(config, backup)
        done.append(f"{config.name} sauvegardé en {backup.name}")
    else:
        done.append(f"pas de {config.name} (réglages par défaut)")
    missing = [r for r in seance.get("parcours") or [] if not any(routes.glob(f"{r}.world")) and not any(routes.glob(f"{r}.json"))]
    if missing:
        blockers += [f"parcours {r} non compilé (dans {routes})" for r in missing]
    else:
        done.append(f"{len(seance.get('parcours') or [])} parcours présent(s)")
    for item in seance.get("poser") or []:
        path = home_path(str(item["chemin"]), home)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(item["contenu"]), encoding="utf-8")
        done.append(f"{path.name} posé")
    for chemin in seance.get("retirer") or []:
        path = home_path(str(chemin), home)
        if path.exists():
            aside = path.with_name(f"{path.name}.pre_vol-{stamp}")
            path.rename(aside)
            done.append(f"{path.name} mis de côté en {aside.name}")
    return StepResult("fichiers", "ÉCHEC" if blockers else "OK", " ; ".join(done), blockers=blockers)


def step_bluetooth(run: Runner, seance: dict[str, Any], enabled: bool) -> StepResult:
    wanted = list(seance.get("appareils") or [])
    if not enabled:
        return StepResult("bluetooth", "SAUTÉ", "--sans-bluetooth")
    if not wanted:
        return StepResult("bluetooth", "SAUTÉ", "aucun appareil demandé")
    rc, text = run([python_bin(), "-m", "openride_core", "devices", "--json", "--timeout", str(BLUETOOTH_TIMEOUT_S)],
                   PROJECT / "core", {})
    try:
        data = json.loads(text[text.index("{"):]) if rc == 0 else None
    except ValueError:
        data = None
    if data is None:
        return StepResult("bluetooth", "ÉCHEC", f"code {rc}",
                          blockers=["recherche Bluetooth impossible : Bluetooth allumé ? (bluetoothctl power on)"])
    seen = {d.get("role") for d in data.get("devices", [])} | {d.get("role") for d in data.get("connected", [])}
    absent = [w for w in wanted if w not in seen]
    if absent:
        return StepResult("bluetooth", "ÉCHEC", f"vus : {', '.join(sorted(r for r in seen if r)) or 'aucun'}",
                          blockers=[f"{a} invisible en Bluetooth (réveiller l'appareil, pédaler un tour)" for a in absent])
    return StepResult("bluetooth", "OK", f"{', '.join(wanted)} visibles")


# --- résumé ----------------------------------------------------------------------------------------

def verdict(results: list[StepResult]) -> tuple[bool, list[str]]:
    blockers = [b for r in results for b in r.blockers]
    return not blockers and all(r.status != "ÉCHEC" for r in results), blockers


def summary_text(seance_name: str, title: str, results: list[StepResult], out: Path) -> str:
    ok, blockers = verdict(results)
    width = max(len(s) for s in STEPS)
    lines = [f"Pré-vol {seance_name} : {title}", ""]
    for r in results:
        timing = f"{r.seconds:>5.0f} s" if r.status != "SAUTÉ" else " " * 7
        lines.append(f"  {r.status:<6} {r.name:<{width}} {timing}  {r.detail}")
    lines.append("")
    if ok:
        lines.append("PRÊT À ROULER")
    else:
        lines.append("PAS PRÊT : à régler avant de monter sur le vélo")
        lines += [f"  - {b}" for b in blockers]
    lines.append(f"Journaux : {out}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, run: Runner = run_command, home: Path | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pré-vol avant une séance vélo (lot X36).")
    ap.add_argument("--seance", help="séance de scripts/pre_vol_seances.toml")
    ap.add_argument("--liste", action="store_true", help="énumérer les séances et quitter")
    ap.add_argument("--sans-engine", action="store_true", help="sans tests Godot ni séance simulée")
    ap.add_argument("--sans-bluetooth", action="store_true", help="sans recherche des appareils")
    ap.add_argument("--sans-reseau", action="store_true", help="sans git fetch")
    ap.add_argument("--out", type=Path, help=f"dossier de sortie (défaut : {DEFAULT_OUT}/<date>)")
    ap.add_argument("--muet", action="store_true", help="sans bips")
    args = ap.parse_args(argv)
    seances = load_seances()
    if args.liste or not args.seance:
        for name, s in seances.items():
            print(f"  {name:<12} {s.get('titre', '')}")
        return 0 if args.liste else 2
    if args.seance not in seances:
        print(f"séance inconnue : {args.seance} (connues : {', '.join(seances)})", file=sys.stderr)
        return 2
    seance = seances[args.seance]
    home = home or Path.home()
    started = datetime.now()
    stamp = started.strftime("%Y-%m-%d_%H%M%S")
    out = args.out or home / "OpenRide" / "pre_vol" / stamp
    out.mkdir(parents=True, exist_ok=True)
    guide = Guide(f"Pré-vol {args.seance}", out / "guide.jsonl", sound=sys.stdout.isatty() and not args.muet,
                  screen=False, out=io.StringIO())
    steps: dict[str, Callable[[], StepResult]] = {
        "git": lambda: step_git(run, fetch=not args.sans_reseau),
        "tests": lambda: step_tests(run, seance, out),
        "engine": lambda: step_engine(run, seance, out, not args.sans_engine),
        "simulee": lambda: step_simulee(run, seance, out, not args.sans_engine),
        "fichiers": lambda: step_fichiers(args.seance, seance, home, home / ROUTES_DIR.relative_to(Path.home()),
                                          home / CONFIG.relative_to(Path.home()), stamp),
        "bluetooth": lambda: step_bluetooth(run, seance, not args.sans_bluetooth),
    }
    print(f"Pré-vol {args.seance} : {seance.get('titre', '')}", flush=True)
    results: list[StepResult] = []
    for i, name in enumerate(STEPS, 1):
        print(f"== {name} …", flush=True)
        guide.step(name, beep=False, index=i, total=len(STEPS))
        t0 = time.monotonic()
        res = steps[name]()
        res.seconds = round(time.monotonic() - t0, 1)
        print(f"   {res.status}{' : ' + res.detail if res.detail else ''}", flush=True)
        guide.measure(name, f"{res.status} {res.detail}", ok=None if res.status == "SAUTÉ" else res.status == "OK")
        results.append(res)
    ok, blockers = verdict(results)
    text = summary_text(args.seance, str(seance.get("titre", "")), results, out)
    (out / "resume.txt").write_text(text, encoding="utf-8")
    (out / "resume.json").write_text(json.dumps({"seance": args.seance, "started": started.isoformat(timespec="seconds"),
                                                 "ok": ok, "blockers": blockers,
                                                 "steps": [asdict(r) for r in results]},
                                                ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(text, end="")
    guide.finish(ok, "PRÊT À ROULER" if ok else "PAS PRÊT")
    guide.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.path.insert(0, str(PROJECT / "scripts"))
    from isolation_tests import verrou_suite   # une seule suite de tests ou banc à la fois

    with verrou_suite("pre_vol"):
        code = main()
    sys.exit(code)
