"""Ligne de commande du générateur de parcours synthétiques (voir `openride_core.demo_world`).

    python -m openride_core.tools.fake_world --out ../engine/demo --length 8000
    python -m openride_core.tools.fake_world --demo --out ../engine/demo   # démo commune core/engine
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..demo_world import (  # noqa: F401  (ré-export pour les anciens imports)
    DEMO_LENGTH_M, DEMO_NAME, build_manifest, build_route, ensure_demo_world, write_demo_world,
    write_world,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("."), help="dossier de sortie")
    p.add_argument("--name", default="fake-climb")
    p.add_argument("--length", type=float, default=8000.0, help="longueur en mètres")
    p.add_argument("--demo", action="store_true", help="écrit le parcours de démonstration commun")
    args = p.parse_args(argv)
    out = write_demo_world(args.out) if args.demo else write_world(args.out, args.name, args.length)
    print(f"Écrit : {out}")


if __name__ == "__main__":
    main()
