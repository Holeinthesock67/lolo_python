#!/usr/bin/env python3
"""Prépare la carte de Köppen-Geiger embarquée du compilateur (lot U24). Non exécuté à l'installation : le
fichier produit est dans le dépôt (`compiler/src/openride_compiler/data/koppen_1986_2010.u8.xz`).

    pip download --no-deps kgcpy==1.1.8 && unzip kgcpy-1.1.8-py3-none-any.whl kgcpy/kmz_int_reshape.png
    python3 scripts/prepare_koppen.py kgcpy/kmz_int_reshape.png

Entrée : image en niveaux de gris de 12 960 × 6 480 pixels du paquet `kgcpy` (codes 1 à 32, provenance et
licence dans `data/koppen_LISEZMOI.md`). Sortie : les mêmes octets, ligne par ligne, compressés en xz.
Demande Pillow (`pip install Pillow`).
"""

from __future__ import annotations

import argparse
import lzma
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "compiler" / "src" / "openride_compiler" / "data" / "koppen_1986_2010.u8.xz"
WIDTH, HEIGHT = 12960, 6480


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("png", type=Path, help="kmz_int_reshape.png du paquet kgcpy 1.1.8")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    Image.MAX_IMAGE_PIXELS = None
    grid = np.asarray(Image.open(args.png))
    if grid.shape != (HEIGHT, WIDTH) or grid.dtype != np.uint8:
        raise SystemExit(f"{args.png} : {grid.shape} {grid.dtype}, ({HEIGHT}, {WIDTH}) uint8 attendu")
    if not set(np.unique(grid).tolist()) <= set(range(1, 33)):
        raise SystemExit(f"{args.png} : codes hors de 1 à 32")
    args.out.write_bytes(lzma.compress(grid.tobytes(), preset=9 | lzma.PRESET_EXTREME))
    print(f"{args.out} : {args.out.stat().st_size} octets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
