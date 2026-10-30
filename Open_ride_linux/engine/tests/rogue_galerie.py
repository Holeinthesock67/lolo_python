#!/usr/bin/env python3
"""Galerie du Cyber-Rogue en low, medium et high côte à côte (lot X51), pour le contrôle visuel R10 à R13 et la charte R17.

    engine/tests/rogue_galerie.py --godot GODOT [--objective threshold] [--seed 5] [--size 1280x720]
                                  [--qualites low,medium,high] [--native] [--out DOSSIER]

Une seule run est jouée dans la vraie séance du core (`rogue_bout_en_bout --trace`, lot X40), puis le banc visuel
du mode (rogue_bench.py, lot X41) la rejoue à chaque qualité : mêmes moments, mêmes salles. La page
`galerie.html` met les captures d'un même moment sur une ligne (une colonne par qualité), avec le verdict du banc
de chaque qualité et les questions du contrôle visuel. Les vérifications automatiques restent celles du banc ;
la page sert au regard du propriétaire. Code 0 si chaque banc passe, 1 sinon, 2 si Godot ou xvfb-run manque.
Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parent
CORE_SRC = TESTS.parents[1] / "core" / "src"
SHOT = re.compile(r"^(\d+)_(.+)\.png$")
QUESTIONS = (
    "Néons, route et grille lisibles d'un coup d'œil, à l'effort, dans chaque salle (R10).",
    "Hologramme et jauges lisibles et jamais l'un sur l'autre ; rien ne cache la route (R11).",
    "Ennemi, Firewall et boss reconnaissables à leur forme et leur couleur (R12).",
    "Menu, pause, couloir et bilan clairs, avec le texte entier à l'écran (R13).",
    "Couleurs, formes et effets fidèles à la charte (R17) ; même ambiance d'une qualité à l'autre.",
)


def bench_ok(out: Path) -> tuple[bool, str]:
    """Verdict d'un banc d'après sa sortie (« N/M vérifications réussies »)."""
    log = (out / "banc.log").read_text("utf-8", errors="replace") if (out / "banc.log").exists() else ""
    m = re.search(r"(\d+)/(\d+) vérifications réussies", log)
    if not m:
        return False, "banc interrompu"
    return m.group(1) == m.group(2), f"{m.group(1)}/{m.group(2)}"


def shots(out: Path) -> dict[str, Path]:
    """Captures d'un banc, par moment (le numéro d'ordre retiré)."""
    found = {}
    for p in sorted(out.glob("*.png")):
        m = SHOT.match(p.name)
        if m:
            found.setdefault(m.group(2), p)
    return found


def write_page(root: Path, qualities: list[str], verdicts: dict[str, tuple[bool, str]]) -> Path:
    per_q = {q: shots(root / q) for q in qualities}
    order: list[str] = []
    for q in qualities:
        for name in per_q[q]:
            if name not in order:
                order.append(name)
    head = "".join(f"<th>{q} — {'OK' if verdicts[q][0] else 'ÉCHEC'} {html.escape(verdicts[q][1])}</th>" for q in qualities)
    rows = []
    for name in order:
        cells = []
        for q in qualities:
            p = per_q[q].get(name)
            cells.append(f"<td><a href='{q}/{p.name}'><img loading='lazy' src='{q}/{p.name}' alt='{name} {q}'></a></td>"
                         if p else "<td>absente</td>")
        rows.append(f"<tr><th class='row'>{html.escape(name)}</th>{''.join(cells)}</tr>")
    questions = "".join(f"<li>{html.escape(q)}</li>" for q in QUESTIONS)
    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Galerie Cyber-Rogue</title>
<style>
:root {{ --bg:#fff; --fg:#1d1d1f; --line:#ddd; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#16171a; --fg:#eee; --line:#333; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.45 system-ui, sans-serif; margin:0; padding:16px; }}
.wrap {{ overflow-x:auto; }} table {{ border-collapse:collapse; }} td, th {{ border-bottom:1px solid var(--line); padding:6px; }}
th.row {{ text-align:left; white-space:nowrap; }} img {{ width:420px; max-width:80vw; display:block; }}
</style></head><body>
<h1>Galerie du Cyber-Rogue</h1>
<p>Même run, mêmes moments, une colonne par qualité. Clique une image pour la voir en grand.</p>
<p>À regarder :</p><ol>{questions}</ol>
<div class="wrap"><table><tr><th></th>{head}</tr>{''.join(rows)}</table></div>
</body></html>
"""
    dest = root / "galerie.html"
    dest.write_text(page, encoding="utf-8")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Galerie du Cyber-Rogue en low, medium et high (lot X51).")
    ap.add_argument("--godot", required=True)
    ap.add_argument("--objective", default="threshold")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--qualites", default="low,medium,high")
    ap.add_argument("--native", action="store_true", help="écran réel (GTX 1060), sans Xvfb")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    if not (Path(args.godot).is_file() and os.access(args.godot, os.X_OK)):
        print(f"Godot introuvable : {args.godot}", file=sys.stderr)
        return 2
    if not args.native and shutil.which("xvfb-run") is None:
        print("xvfb-run introuvable (paquet xvfb) ; ou --native", file=sys.stderr)
        return 2
    root = args.out or Path(tempfile.mkdtemp(prefix="openride-rogue-galerie-"))
    root.mkdir(parents=True, exist_ok=True)
    trace = root / "trace.jsonl"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(CORE_SRC), os.environ.get("PYTHONPATH")]))}
    subprocess.run([sys.executable, "-m", "openride_core.tools.rogue_bout_en_bout", "--objective", args.objective,
                    "--seed", str(args.seed), "--trace", str(trace)], env=env, check=False, capture_output=True)
    if not trace.exists():
        print("trace de la run non écrite (rogue_bout_en_bout)", file=sys.stderr)
        return 2
    qualities = [q.strip() for q in args.qualites.split(",") if q.strip()]
    verdicts = {}
    for q in qualities:
        out = root / q
        out.mkdir(exist_ok=True)
        cmd = [sys.executable, str(TESTS / "rogue_bench.py"), "--godot", args.godot, "--trace", str(trace),
               "--size", args.size, "--quality", q, "--out", str(out)] + (["--native"] if args.native else [])
        print(f"== {q} ==", flush=True)
        with (out / "banc.log").open("w", encoding="utf-8") as log:
            subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        verdicts[q] = bench_ok(out)
        print(f"   {q} : {'OK' if verdicts[q][0] else 'ÉCHEC'} {verdicts[q][1]}", flush=True)
    print(f"Galerie : {write_page(root, qualities, verdicts)}")
    return 0 if all(v[0] for v in verdicts.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
