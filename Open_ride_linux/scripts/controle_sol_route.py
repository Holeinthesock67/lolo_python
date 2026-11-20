#!/usr/bin/env python3
"""Contrôle « sol au-dessus de la route » sur les parcours réels du PC (20 novembre 2026).

Demande du propriétaire (« on ne doit retrouver cela ni dans les mondes démo ni en monde ouvert ») : le contrôle
`engine/tests/test_herbe_route.gd` de la CI (sol affiché au moins 2 cm sous la chaussée, en travers de toute la
route, au relief réel et au relief de séance ; herbe, détails, arbres et objets du bord de route hors de la
chaussée) tourne ici sur ce que le joueur roule vraiment :

- tous les parcours installés (`~/.local/share/openride/routes/*.world` : démonstrations, contenus de départ, pack
  des cols, traces importées), vélodrome excepté (piste couverte, sans terrain) ;
- les dernières balades du monde ouvert (`<cache>/seances/ow-*.world`, la plus récente d'abord) : le monde vivant
  écrit par le générateur, avec la route engagée et les carrés liés, tel que l'engine l'a affiché.

    python3 scripts/controle_sol_route.py --out DOSSIER [--godot BINAIRE] [--routes DOSSIER]
        [--seances DOSSIER] [--dernieres N] [MONDE.world ...]

Avec des mondes en arguments, seuls ceux-là sont contrôlés. Écrit `DOSSIER/controle.log` (sortie complète, pires
points listés avec s, x, z) et `DOSSIER/resume.txt`. Code de sortie : 0 si tout passe, 1 si un contrôle échoue,
2 si rien à contrôler ou Godot introuvable. Lecture seule : aucun parcours ni cache n'est modifié.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[1] / "engine"
DEFAULT_GODOT = Path.home() / "Applications/godot/Godot_v4.7.2-stable_linux.x86_64"
DEFAULT_ROUTES = Path.home() / ".local/share/openride/routes"
DEFAULT_SEANCES = Path.home() / "OpenRide/Cache/monde/seances"
SKIP_PREFIXES = ("velodrome",)
COUNT_RE = re.compile(r"^test_herbe_route : (\d+) vérifications, (\d+) échecs$", re.M)


def installed_worlds(routes: Path) -> list[Path]:
    """Parcours installés, vélodrome excepté, par nom."""
    if not routes.is_dir():
        return []
    return sorted(p for p in routes.glob("*.world")
                  if (p / "manifest.json").is_file() and not p.name.startswith(SKIP_PREFIXES))


def latest_sessions(seances: Path, n: int) -> list[Path]:
    """Les `n` dernières balades du monde ouvert qui ont une route écrite, la plus récente d'abord."""
    if n <= 0 or not seances.is_dir():
        return []
    found = [p for p in seances.glob("ow-*.world") if (p / "manifest.json").is_file() and any((p / "route").glob("part_*.json"))]
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[:n]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mondes", nargs="*", type=Path, help="mondes .world à contrôler (défaut : parcours installés et dernières balades)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--godot", type=Path, default=Path(os.environ.get("GODOT", DEFAULT_GODOT)))
    ap.add_argument("--routes", type=Path, default=DEFAULT_ROUTES)
    ap.add_argument("--seances", type=Path, default=DEFAULT_SEANCES)
    ap.add_argument("--dernieres", type=int, default=3, help="balades du monde ouvert contrôlées (défaut 3)")
    ap.add_argument("--delai-s", type=int, default=1800)
    a = ap.parse_args(argv)
    worlds = list(a.mondes) or installed_worlds(a.routes) + latest_sessions(a.seances, a.dernieres)
    a.out.mkdir(parents=True, exist_ok=True)
    if not worlds:
        (a.out / "resume.txt").write_text("rien à contrôler\n", encoding="utf-8")
        print("rien à contrôler", file=sys.stderr)
        return 2
    if not a.godot.is_file():
        print(f"Godot introuvable : {a.godot}", file=sys.stderr)
        return 2
    cmd = [str(a.godot), "--headless", "--path", str(ENGINE_DIR), "--script", "res://tests/test_herbe_route.gd", "--",
           *[str(w.resolve()) for w in worlds]]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=a.delai_s)
        out, rc = r.stdout + r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        out, rc = f"{e.stdout or ''}{e.stderr or ''}\nDÉLAI DÉPASSÉ ({a.delai_s} s)\n", 1
    (a.out / "controle.log").write_text(out, encoding="utf-8")
    m = COUNT_RE.search(out)
    failures = [line for line in out.splitlines() if line.startswith("[ÉCHEC]")]
    lines = [f"mondes contrôlés : {len(worlds)}"] + [f"  {w}" for w in worlds]
    lines.append(f"résultat : {m.group(1)} vérifications, {m.group(2)} échecs" if m else "résultat : compte absent (plantage ?)")
    lines += failures
    (a.out / "resume.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if m is None or "SCRIPT ERROR" in out:
        return 1
    return 1 if rc != 0 or int(m.group(2)) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
