#!/usr/bin/env python3
"""Compare deux séries de captures du banc simulé, image par image (lot S1, critère 4).

Usage :
    compare_captures.py AVANT_DOSSIER APRES_DOSSIER [--out DOSSIER] [--max-diff 3.0]

Les captures de même nom (`NNN_étiquette.png`, écrites par `sim_bench.py`) sont appariées. Pour chaque
paire : écart moyen de luminosité (0 à 255) et part des pixels qui changent nettement, mesurés par les
fonctions de `visual_check.py` sur la moitié haute et le centre de l'image (le HUD, dont les images/s
changent d'un essai à l'autre, est en bas et sur les côtés). Une image des écarts (rouge) est écrite
dans `--out` pour chaque paire. Code de sortie 0 si toutes les paires restent sous `--max-diff`, 1 sinon,
2 si aucune paire n'est trouvée.

Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import visual_check as vc  # noqa: E402


def scene_box(img: vc.Image) -> tuple[int, int, int, int]:
    """Zone du décor : de 15 % à 85 % de la largeur, du haut jusqu'à 70 % de la hauteur."""
    return (int(img.width * 0.15), 0, int(img.width * 0.85), int(img.height * 0.70))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--max-diff", type=float, default=3.0, help="écart moyen maximal admis (0 à 255)")
    a = ap.parse_args(argv)
    pairs = [(a.before / p.relative_to(a.before), a.after / p.relative_to(a.before))
             for p in sorted(a.before.rglob("*.png")) if (a.after / p.relative_to(a.before)).exists()]
    if not pairs:
        print("Aucune capture appariée entre", a.before, "et", a.after)
        return 2
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
    worst = 0.0
    failed = 0
    for pb, pa in pairs:
        ib, ia = vc.read_png(pb), vc.read_png(pa)
        if (ib.width, ib.height) != (ia.width, ia.height):
            print(f"[ÉCHEC] {pb.name} : tailles différentes {ib.width}x{ib.height} et {ia.width}x{ia.height}")
            failed += 1
            continue
        box = scene_box(ib)
        diff = vc.mean_abs_diff(ib, ia, box)
        changed = vc.changed_fraction(ib, ia)
        worst = max(worst, diff)
        ok = diff <= a.max_diff
        failed += 0 if ok else 1
        print(f"[{'OK' if ok else 'ÉCHEC'}] {pb.name} : écart moyen {diff:.2f}, pixels changés {changed * 100:.1f} %")
        if a.out:
            vc.write_png(a.out / f"ecart_{pb.name}", vc.diff_image(ib, ia))
    print(f"compare_captures : {len(pairs)} paires, écart moyen maximal {worst:.2f}, {failed} au-dessus de {a.max_diff}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
