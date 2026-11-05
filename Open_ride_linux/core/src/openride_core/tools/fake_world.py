"""Ligne de commande du générateur de parcours synthétiques (voir `openride_core.demo_world`).

    python -m openride_core.tools.fake_world --out ../engine/demo --length 8000
    python -m openride_core.tools.fake_world --demo --out ../engine/demo   # démo commune core/engine
    python -m openride_core.tools.fake_world --demo --terrain --out ~/.local/share/openride/routes

L'option `--terrain` ajoute la couche terrain synthétique (`openride_core.synthetic_terrain`) à un
parcours d'essai ; le parcours de démonstration (`--demo`) la porte toujours.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..demo_world import (  # noqa: F401  (ré-export pour les anciens imports)
    DEMO_CREATED, DEMO_LENGTH_M, DEMO_NAME, build_manifest, build_route, ensure_demo_world,
    write_demo_world, write_world,
)
from ..synthetic_terrain import (  # noqa: F401  (ré-export pour les anciens imports)
    BLEND_END_M, BLEND_START_M, FAR, NEAR, ROAD_HALF_WIDTH_M, TERRAIN_BELOW_ROAD_M, TILE_SAMPLES,
    SyntheticTerrain, add_terrain_layer, hills, write_terrain,
)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("."), help="dossier de sortie")
    p.add_argument("--name", default="fake-climb")
    p.add_argument("--length", type=float, default=8000.0, help="longueur en mètres")
    p.add_argument("--demo", action="store_true", help="écrit le parcours de démonstration commun")
    p.add_argument("--terrain", action="store_true",
                   help="ajoute une couche terrain synthétique (tuiles proches et lointaines)")
    args = p.parse_args(argv)
    out = write_demo_world(args.out) if args.demo else write_world(args.out, args.name, args.length)
    if args.terrain and not args.demo:   # la démonstration porte déjà son terrain
        add_terrain_layer(out)
    print(f"Écrit : {out}")


if __name__ == "__main__":
    main()
