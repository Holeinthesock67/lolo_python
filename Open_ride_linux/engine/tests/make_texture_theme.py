#!/usr/bin/env python3
"""Thème d'essai à trois textures pour mesurer le coût du shader triplanaire (lot E2, critère 6).

Copie le thème `default` en remplaçant herbe, roche et neige par des images PNG carrées
(2 048 × 2 048 par défaut) : couleur du thème plus un grain aléatoire, assez marqué pour voir la
répétition et le scintillement au loin. Seule la bibliothèque standard de Python est utilisée.

    python3 engine/tests/make_texture_theme.py                  # ~/OpenRide/Themes/essai_textures
    python3 engine/tests/make_texture_theme.py --out DOSSIER --size 1024

Puis : `THEME=essai_textures scripts/openride-dev.sh` (ou `render.theme` dans `config.toml`).
Code de sortie : 0 si le thème est écrit.
"""

from __future__ import annotations

import argparse
import json
import random
import struct
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]          # Open_ride_linux/
DEFAULT_THEME = REPO / "engine" / "themes" / "default" / "theme.json"
DEFAULT_OUT = Path.home() / "OpenRide" / "Themes" / "essai_textures"
LAYERS = ("grass", "rock", "snow")
GRAIN = {"grass": 40, "rock": 60, "snow": 16}       # amplitude du grain, en niveaux sur 255


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def noise_png(size: int, color: str, grain: int, seed: int) -> bytes:
    """Image RVB `size` × `size` : `color` (« #rrggbb ») plus un grain de ± `grain` / 2 niveaux."""
    rng = random.Random(seed)
    base = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    tables = [bytes(max(0, min(255, c + (n * grain) // 256 - grain // 2)) for n in range(256)) for c in base]
    rows = bytearray()
    for _ in range(size):
        noise = rng.randbytes(size)
        row = bytearray(3 * size)
        for ch in range(3):
            row[ch::3] = noise.translate(tables[ch])
        rows += b"\x00" + row                        # filtre PNG « None » en tête de ligne
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", header)
            + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + _png_chunk(b"IEND", b""))


def write_theme(out: Path, size: int) -> dict:
    theme = json.loads(DEFAULT_THEME.read_text(encoding="utf-8"))
    theme["name"] = f"Essai textures {size}"
    (out / "textures").mkdir(parents=True, exist_ok=True)
    for i, layer in enumerate(LAYERS):
        rel = f"textures/{layer}.png"
        (out / rel).write_bytes(noise_png(size, theme["terrain"][layer]["color"], GRAIN[layer], seed=i))
        theme["terrain"][layer]["texture"] = rel
    (out / "theme.json").write_text(json.dumps(theme, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return theme


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="dossier du thème (créé au besoin)")
    parser.add_argument("--size", type=int, default=2048, help="côté des images, puissance de 2 (défaut 2048)")
    args = parser.parse_args(argv)
    if args.size < 1 or args.size & (args.size - 1):
        print(f"--size doit être une puissance de 2 : {args.size}", file=sys.stderr)
        return 2
    write_theme(args.out, args.size)
    print(f"Thème écrit : {args.out} (3 textures {args.size} × {args.size})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
