#!/usr/bin/env python3
"""Parcours de démonstration des biomes (lots U19 et O37) : ligne de commande des essais de l'engine.

Le générateur vit dans le compilateur (`openride_compiler.demo_biomes`, lot O37) pour qu'un jeu installé sans
les tests produise ses parcours de démonstration ; ce script le reprend tel quel (mêmes options, mêmes noms)
pour les bancs, les recettes et `run_engine_tests.sh`. Les bancs et les fiches de recette passent `--recette`
(noms techniques, variante jamais livrée dans le jeu de base).

    python3 engine/tests/make_biome_world.py --out DOSSIER --tour [--gravel] [--sea] [--recette]
    python3 engine/tests/make_biome_world.py --out DOSSIER --biome alpine
    python3 engine/tests/make_biome_world.py --out DOSSIER --demo-set [--recette]   # parcours du jeu de base (+ tour gravel avec --recette)

Prérequis : compilateur installé (`pip install -e compiler`), sinon pris dans `compiler/src` du dépôt.
Code de sortie : 0 si tout est écrit, 2 sans le compilateur.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from openride_compiler.demo_biomes import *  # noqa: F401,F403
    from openride_compiler.demo_biomes import main
except ImportError:   # dépôt sans `pip install -e compiler` : les sources du compilateur
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "compiler" / "src"))
    try:
        from openride_compiler.demo_biomes import *  # noqa: F401,F403
        from openride_compiler.demo_biomes import main
    except ImportError as exc:
        def main(argv: list[str] | None = None, _exc: ImportError = exc) -> int:
            print(f"make_biome_world : compilateur non installé ({_exc}) ; pip install -e compiler", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main())
