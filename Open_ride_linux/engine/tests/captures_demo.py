#!/usr/bin/env python3
"""Captures des quatre parcours de démonstration du jeu de base (lot O37), à valider par le propriétaire.

    python3 engine/tests/captures_demo.py lancer [--out DOSSIER] [--qualites medium] [--vitesse 50]
                                                 [--parcours demo,demo-biomes-alpin] [--native] [--sans-menus]

1. Écrit les parcours tels qu'un jeu neuf les installe (`openride-core demo-biomes`, sans `--recette`, et la
   démonstration `demo` avec son terrain) dans `DOSSIER/routes`.
2. Pour chaque parcours et chaque qualité, une séance `sim_bench.py --world` tenue à `--vitesse` km/h
   (cycliste virtuel), assez longue pour aller jusqu'au sommet, avec des captures prises à des distances
   choisies (`--at-m`), scénario `nominal` : début de parcours (150 et 400 m, après le compte à rebours) et
   approche du panneau
   du sommet (80, 50 et 30 m avant, en 1920×1080 pour que son nom se lise). Le sommet est le point le plus
   haut de la route ; un parcours sans montée n'a que les captures du début.
3. `menu_bench.py --scenario parcours_demo --captures ecrans` : liste des parcours avec leurs quatre noms et
   écran « Prêt » de chacun.
4. `DOSSIER/planche.html` : toutes les captures, rangées par parcours et par qualité.

Prérequis : Godot (`--godot` ou `OPENRIDE_GODOT`, comme les bancs), compilateur installé, xvfb-run sans
`--native`. Durée : environ 45 min par qualité à 50 km/h (tour de 12 km), plus 2 min de menus.
Code de sortie : 0 si tous les bancs passent, 1 sinon.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent
REPO = ENGINE_DIR.parent
ROUTES = ("demo", "demo-biomes-tour", "demo-biomes-cote", "demo-biomes-alpin")   # tour gravel : recette seule (9 novembre)
START_MARKS_M = (150.0, 400.0)
SUMMIT_BEFORE_M = (80.0, 50.0, 30.0)
MIN_CLIMB_M = 30.0                 # dénivelé sous lequel le parcours n'a pas de sommet à montrer
LOAD_S = 90.0                      # chargement, compte à rebours et départ au pédalage
RIDE_MARGIN = 1.3                  # vitesse moyenne sous la vitesse tenue (départ, pentes) : r811b roulait 48 km/h


def _env() -> dict[str, str]:
    paths = [str(REPO / "core" / "src"), str(REPO / "compiler" / "src")]
    return {**os.environ, "PYTHONPATH": os.pathsep.join(paths + [os.environ.get("PYTHONPATH", "")])}


def write_routes(routes: Path) -> None:
    """Parcours du jeu de base, comme à l'installation : noms de parcours, aucun nom technique."""
    routes.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "openride_core.tools.fake_world", "--demo", "--terrain",
                    "--out", str(routes)], check=True, env=_env(), stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "-m", "openride_core", "demo-biomes", "--out", str(routes)],
                   check=True, env=_env(), stdout=subprocess.DEVNULL)


def marks_for(world: Path) -> tuple[list[float], float]:
    """Distances des captures et longueur à parcourir (m) : début, puis approche du sommet s'il y en a un."""
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    alt = route["alt_m"]
    top = max(range(len(alt)), key=lambda i: alt[i])
    summit = min(top * float(route["ds_m"]), float(route["length_m"]))
    marks = [m for m in START_MARKS_M if m < route["length_m"]]
    if alt[top] - min(alt) >= MIN_CLIMB_M and summit > max(START_MARKS_M) + max(SUMMIT_BEFORE_M):
        marks += [summit - d for d in SUMMIT_BEFORE_M]
    return sorted(marks), max(marks) + 20.0


def run_bench(args, routes: Path, route_id: str, quality: str, out: Path) -> int:
    world = routes / f"{route_id}.world"
    marks, ride_m = marks_for(world)
    duration = LOAD_S + RIDE_MARGIN * ride_m / (args.vitesse / 3.6)
    # Scénario « nominal » : aucun appui du Click ni changement d'effort (le scénario « demo » par défaut en a).
    cmd = [sys.executable, str(TESTS_DIR / "sim_bench.py"), "--scenario", "nominal", "--world", str(world),
           "--quality", quality,
           "--speed-kmh", str(args.vitesse), "--duration", f"{duration:.0f}", "--size", "1920x1080",
           "--at-m", ",".join(f"{m:.0f}" for m in marks), "--out", str(out), "--muet"]
    if args.godot:
        cmd += ["--godot", str(args.godot)]
    if args.native:
        cmd.append("--native")
    print(f"{route_id} ({quality}) : {duration / 60:.0f} min, captures à {', '.join(f'{m:.0f}' for m in marks)} m",
          flush=True)
    return subprocess.run(cmd, env=_env()).returncode


def run_menus(args, out: Path) -> int:
    cmd = [sys.executable, str(TESTS_DIR / "menu_bench.py"), "--scenario", "parcours_demo", "--captures", "ecrans",
           "--out", str(out)]
    if args.godot:
        cmd += ["--godot", str(args.godot)]
    if args.native:
        cmd.append("--native")
    print("menus : liste des parcours et écran Prêt de chacun", flush=True)
    return subprocess.run(cmd, env=_env()).returncode


def write_sheet(out: Path, results: dict[str, int]) -> Path:
    rows = []
    for name, code in results.items():
        pngs = sorted((out / name).rglob("*.png"))
        cells = "".join(f'<figure><a href="{html.escape(str(p.relative_to(out)))}"><img src="'
                        f'{html.escape(str(p.relative_to(out)))}" loading="lazy"></a>'
                        f"<figcaption>{html.escape(p.stem)}</figcaption></figure>" for p in pngs)
        state = "OK" if code == 0 else f"ÉCHEC (code {code})"
        rows.append(f"<h2>{html.escape(name)} — {state}</h2><div class=g>{cells or 'aucune capture'}</div>")
    page = ("<!DOCTYPE html><meta charset=utf-8><title>Parcours de démonstration (O37)</title><style>"
            "body{font-family:sans-serif;margin:1em}.g{display:flex;flex-wrap:wrap;gap:8px}"
            "figure{margin:0;width:480px}img{width:100%}figcaption{font-size:12px}</style>"
            f"<h1>Parcours de démonstration du jeu de base (lot O37)</h1><p>{time.strftime('%Y-%m-%d %H:%M')}</p>"
            + "".join(rows))
    sheet = out / "planche.html"
    sheet.write_text(page, encoding="utf-8")
    return sheet


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    run = sub.add_parser("lancer", help="parcours, séances, menus et planche")
    run.add_argument("--out", type=Path, default=Path.home() / "OpenRide" / "captures_demo" / time.strftime("%Y-%m-%d_%H%M%S"))
    run.add_argument("--godot", type=Path, help="exécutable Godot (défaut : celui des bancs)")
    run.add_argument("--qualites", default="medium", help="low, medium, high séparées par des virgules (défaut medium)")
    run.add_argument("--vitesse", type=float, default=50.0, help="vitesse tenue en km/h (défaut 50)")
    run.add_argument("--parcours", default=",".join(ROUTES), help="identifiants séparés par des virgules (défaut : les cinq)")
    run.add_argument("--native", action="store_true", help="fenêtre sur l'écran réel, sans Xvfb")
    run.add_argument("--sans-menus", action="store_true", help="sans le banc des menus")
    args = ap.parse_args(argv)

    out = args.out.resolve()
    routes = out / "routes"
    write_routes(routes)
    results: dict[str, int] = {}
    if not args.sans_menus:
        results["menus"] = run_menus(args, out / "menus")
    for quality in [q.strip() for q in args.qualites.split(",") if q.strip()]:
        for route_id in [r.strip() for r in args.parcours.split(",") if r.strip()]:
            if route_id not in ROUTES:
                print(f"parcours inconnu : {route_id} ({', '.join(ROUTES)})", file=sys.stderr)
                return 2
            name = f"{route_id}_{quality}"
            results[name] = run_bench(args, routes, route_id, quality, out / name)
    sheet = write_sheet(out, results)
    print(f"Planche : {sheet}")
    return 0 if all(code == 0 for code in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
