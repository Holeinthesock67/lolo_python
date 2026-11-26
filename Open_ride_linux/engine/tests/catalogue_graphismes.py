#!/usr/bin/env python3
"""Catalogue des graphismes de départ (lot PG1) : parcours de démonstration roulés par le tour visuel à chaque
préréglage, l'engine écrivant la recette de chaque objet vu dans `engine/data/graphismes/` (graphics_catalog.gd).
Le catalogue est le même pour toutes les cartes graphiques ; il est rejoué une fois au premier lancement
(graphics_prep.gd).

    python3 engine/tests/catalogue_graphismes.py --godot GODOT [--world demo --world DOSSIER.world] [--quality low]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = ENGINE_DIR / "data" / "graphismes"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--godot", type=Path, default=Path(os.environ.get(
        "GODOT", str(Path.home() / "Applications" / "godot" / "Godot_v4.7.2-stable_linux.x86_64"))))
    ap.add_argument("--world", action="append", default=[], help="demo, village, ou dossier .world (répétable)")
    ap.add_argument("--quality", action="append", default=[], help="préréglage (répétable ; défaut les trois)")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--work", type=Path, default=Path("/tmp") / "catalogue_graphismes")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    before = len(list(a.out.glob("*.scn")))
    failed = 0
    for world in a.world or ["demo"]:
        for q in a.quality or ["low", "medium", "high"]:
            name = Path(world).stem
            print(f"== {name}, {q}", flush=True)
            r = subprocess.run([sys.executable, str(ENGINE_DIR / "tests" / "tour_visuel.py"), "--godot", str(a.godot),
                                "--world", world, "--auto", "--quality", q, "--out", str(a.work / f"{name}_{q}"),
                                f"--engine-arg=--graphics-catalog-dir={a.out}"], check=False)
            failed += r.returncode != 0
    after = len(list(a.out.glob("*.scn")))
    size = sum(p.stat().st_size for p in a.out.glob("*.scn"))
    print(f"Catalogue : {after} recettes ({after - before} nouvelles), {size // 1024} Ko dans {a.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
