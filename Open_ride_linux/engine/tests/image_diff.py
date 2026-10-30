#!/usr/bin/env python3
"""Images des tests graphiques : PNG, écarts et similarité structurelle (lot X20).

    engine/tests/image_diff.py REFERENCE.png IMAGE.png [--masque X0,Y0,X1,Y1 …] [--seuil 0.97] [--carte ECARTS.png]

Lit et écrit les PNG avec la bibliothèque standard (zlib), mesure l'écart moyen, la part de pixels très
différents et la SSIM par blocs sur la luminance : la moyenne, sur des blocs de 8 × 8 pixels, de la
similarité des moyennes, des contrastes et des structures (Wang et al., 2004). Un bloc qui touche un
masque (rectangle en pixels de la référence : chiffres du HUD, zone animée) est ignoré. Les deux images
sont comparées à la taille de la référence : l'image est réduite par moyenne si elle est plus grande.

En ligne de commande : score SSIM, écart moyen et carte des écarts (`--carte`, blocs en rouge d'autant
plus vifs que la SSIM y est basse) ; code 0 si la SSIM atteint le seuil, 1 sinon, 2 si une image est
illisible ou d'un autre format (largeur sur hauteur).

Bibliothèque standard seulement : sert à `visual_check.py` (références des scènes figées) et à la main.
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

CHANGED_LEVEL = 40               # écart d'une composante au-delà duquel un pixel compte comme très différent
BLOCK = 8                        # côté des blocs de la SSIM, en pixels
C1 = (0.01 * 255) ** 2           # constantes de stabilité de la SSIM (luminance sur 0..255)
C2 = (0.03 * 255) ** 2
VIGNETTE_WIDTH = 640             # largeur des images de référence (lot X20)

Box = tuple[int, int, int, int]  # rectangle (x0, y0, x1, y1), x1 et y1 exclus


# --- PNG (bibliothèque standard) ------------------------------------------------------------------

@dataclass
class Image:
    width: int
    height: int
    rgb: bytes                    # 3 octets par pixel, ligne par ligne

    def pixel(self, x: int, y: int) -> tuple[int, int, int]:
        i = (y * self.width + x) * 3
        return self.rgb[i], self.rgb[i + 1], self.rgb[i + 2]

    def pixels(self, box: Box | None = None, step: int = 2):
        """Pixels d'un rectangle (x0, y0, x1, y1), un sur `step` dans chaque direction."""
        x0, y0, x1, y1 = box if box else (0, 0, self.width, self.height)
        x0, y0 = max(0, int(x0)), max(0, int(y0))
        x1, y1 = min(self.width, int(x1)), min(self.height, int(y1))
        for y in range(y0, y1, step):
            row = y * self.width * 3
            for x in range(x0, x1, step):
                i = row + x * 3
                yield self.rgb[i], self.rgb[i + 1], self.rgb[i + 2]


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path: Path) -> Image:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} : pas un PNG")
    pos, idat, width = 8, bytearray(), 0
    height = depth = ctype = 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype not in (2, 6) or interlace:
                raise ValueError(f"{path} : PNG non pris en charge (profondeur {depth}, type {ctype})")
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    bpp = 3 if ctype == 2 else 4
    raw = zlib.decompress(bytes(idat))
    stride = width * bpp
    out = bytearray(width * height * 3)
    prev = bytearray(stride)
    for y in range(height):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif f == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up_left = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, prev[i], up_left)) & 0xFF
        if bpp == 3:
            out[y * width * 3:(y + 1) * width * 3] = line
        else:
            o = y * width * 3
            for x in range(width):
                out[o + x * 3:o + x * 3 + 3] = line[x * 4:x * 4 + 3]
        prev = line
    return Image(width, height, bytes(out))


def write_png(path: Path, img: Image) -> None:
    stride = img.width * 3
    raw = b"".join(b"\x00" + img.rgb[y * stride:(y + 1) * stride] for y in range(img.height))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", img.width, img.height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# --- mesures -------------------------------------------------------------------------------------

def luminance(p: tuple[int, int, int]) -> float:
    return (0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]) / 255.0


def mean_abs_diff(a: Image, b: Image, box: Box | None = None, step: int = 2) -> float:
    """Écart moyen par composante, en niveaux sur 255 (images de même taille)."""
    if (a.width, a.height) != (b.width, b.height):
        return 255.0
    n = 0
    total = 0
    for pa, pb in zip(a.pixels(box, step), b.pixels(box, step)):
        n += 1
        total += abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
    return total / (3 * n) if n else 0.0


def changed_fraction(a: Image, b: Image, level: int = CHANGED_LEVEL, step: int = 2) -> float:
    """Part des pixels dont une composante change de plus de `level` niveaux (défaut localisé)."""
    if (a.width, a.height) != (b.width, b.height):
        return 1.0
    n = hit = 0
    for pa, pb in zip(a.pixels(None, step), b.pixels(None, step)):
        n += 1
        if max(abs(pa[0] - pb[0]), abs(pa[1] - pb[1]), abs(pa[2] - pb[2])) > level:
            hit += 1
    return hit / n if n else 0.0


def diff_image(a: Image, b: Image) -> Image:
    """Écarts amplifiés ×4, en rouge sur l'image de référence assombrie."""
    out = bytearray(len(a.rgb))
    for i in range(0, len(a.rgb), 3):
        d = (abs(a.rgb[i] - b.rgb[i]) + abs(a.rgb[i + 1] - b.rgb[i + 1]) + abs(a.rgb[i + 2] - b.rgb[i + 2])) // 3
        base = (a.rgb[i] + a.rgb[i + 1] + a.rgb[i + 2]) // 12
        out[i] = min(255, base + 4 * d)
        out[i + 1] = base
        out[i + 2] = base
    return Image(a.width, a.height, bytes(out))


def resize(img: Image, width: int, height: int) -> Image:
    """Réduction par moyenne des pixels de chaque case (agrandissement : pixel le plus proche)."""
    if (img.width, img.height) == (width, height):
        return img
    out = bytearray(width * height * 3)
    src = img.rgb
    for y in range(height):
        y0 = y * img.height // height
        y1 = max(y0 + 1, (y + 1) * img.height // height)
        for x in range(width):
            x0 = x * img.width // width
            x1 = max(x0 + 1, (x + 1) * img.width // width)
            r = g = b = 0
            for yy in range(y0, y1):
                row = yy * img.width * 3
                for xx in range(x0, x1):
                    i = row + xx * 3
                    r += src[i]
                    g += src[i + 1]
                    b += src[i + 2]
            n = (y1 - y0) * (x1 - x0)
            o = (y * width + x) * 3
            out[o], out[o + 1], out[o + 2] = r // n, g // n, b // n
    return Image(width, height, bytes(out))


def vignette(img: Image, width: int = VIGNETTE_WIDTH) -> Image:
    """Image réduite à `width` pixels de large, proportions gardées (images de référence du dépôt)."""
    if img.width <= width:
        return img
    return resize(img, width, max(1, round(img.height * width / img.width)))


def scale_box(box: Box, sx: float, sy: float) -> Box:
    x0, y0, x1, y1 = box
    return int(x0 * sx), int(y0 * sy), int(x1 * sx + 0.999), int(y1 * sy + 0.999)


@dataclass
class SsimResult:
    score: float                  # moyenne des blocs comptés, de −1 à 1 (1 : images identiques)
    width: int
    height: int
    blocks: list[tuple[int, int, float]] = field(default_factory=list)   # (x0, y0, SSIM) des blocs comptés
    masked: int = 0               # blocs ignorés (masques)

    @property
    def worst(self) -> float:
        return min((v for _, _, v in self.blocks), default=1.0)


def _luma(img: Image) -> list[float]:
    rgb = img.rgb
    return [0.2126 * rgb[i] + 0.7152 * rgb[i + 1] + 0.0722 * rgb[i + 2] for i in range(0, len(rgb), 3)]


def ssim(a: Image, b: Image, masks: list[Box] | tuple[Box, ...] = (), block: int = BLOCK) -> SsimResult:
    """SSIM par blocs de `block` × `block` sur la luminance de deux images de même taille ; les blocs qui
    touchent un masque sont ignorés."""
    if (a.width, a.height) != (b.width, b.height):
        raise ValueError(f"tailles différentes : {a.width}x{a.height} et {b.width}x{b.height}")
    la, lb = _luma(a), _luma(b)
    w = a.width
    res = SsimResult(1.0, a.width, a.height)
    total = 0.0
    n = block * block
    for y0 in range(0, a.height - block + 1, block):
        for x0 in range(0, w - block + 1, block):
            if any(x0 < mx1 and x0 + block > mx0 and y0 < my1 and y0 + block > my0 for mx0, my0, mx1, my1 in masks):
                res.masked += 1
                continue
            sa = sb = saa = sbb = sab = 0.0
            for y in range(y0, y0 + block):
                row = y * w
                for i in range(row + x0, row + x0 + block):
                    pa, pb = la[i], lb[i]
                    sa += pa
                    sb += pb
                    saa += pa * pa
                    sbb += pb * pb
                    sab += pa * pb
            ma, mb = sa / n, sb / n
            va, vb = saa / n - ma * ma, sbb / n - mb * mb
            cov = sab / n - ma * mb
            v = ((2 * ma * mb + C1) * (2 * cov + C2)) / ((ma * ma + mb * mb + C1) * (va + vb + C2))
            res.blocks.append((x0, y0, v))
            total += v
    res.score = total / len(res.blocks) if res.blocks else 1.0
    return res


def ssim_map(ref: Image, res: SsimResult, masks: list[Box] | tuple[Box, ...] = (), block: int = BLOCK) -> Image:
    """Carte des écarts : référence assombrie, blocs en rouge d'autant plus vifs que leur SSIM est basse,
    masques en bleu."""
    out = bytearray(len(ref.rgb))
    for i in range(0, len(ref.rgb), 3):
        base = (ref.rgb[i] + ref.rgb[i + 1] + ref.rgb[i + 2]) // 9
        out[i] = out[i + 1] = out[i + 2] = base
    w = ref.width
    for x0, y0, v in res.blocks:
        red = min(255, int(max(0.0, 1.0 - v) * 4 * 255))
        if red < 8:
            continue
        for y in range(y0, y0 + block):
            for x in range(x0, x0 + block):
                i = (y * w + x) * 3
                out[i] = min(255, out[i] + red)
    for mx0, my0, mx1, my1 in masks:
        for y in range(max(0, my0), min(ref.height, my1)):
            for x in range(max(0, mx0), min(w, mx1)):
                i = (y * w + x) * 3
                out[i + 2] = min(255, out[i + 2] + 90)
    return Image(ref.width, ref.height, bytes(out))


def same_format(a: Image, b: Image) -> bool:
    """Même rapport largeur sur hauteur, à 1 % près (une référence réduite reste comparable)."""
    return abs(a.width / a.height - b.width / b.height) <= 0.01 * a.width / a.height


def compare(ref: Image, img: Image, masks: list[Box] | tuple[Box, ...] = ()) -> SsimResult:
    """SSIM de `img` face à la référence `ref`, à la taille de la référence (masques en pixels de `ref`)."""
    if not same_format(ref, img):
        raise ValueError(f"format différent : référence {ref.width}x{ref.height}, image {img.width}x{img.height}")
    return ssim(ref, resize(img, ref.width, ref.height), masks)


def _box(text: str) -> Box:
    parts = [int(v) for v in text.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f"masque attendu X0,Y0,X1,Y1 : {text}")
    return parts[0], parts[1], parts[2], parts[3]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Similarité structurelle (SSIM) de deux images PNG (lot X20).")
    ap.add_argument("reference", type=Path)
    ap.add_argument("image", type=Path)
    ap.add_argument("--masque", type=_box, action="append", default=[], help="rectangle ignoré X0,Y0,X1,Y1 (pixels de la référence)")
    ap.add_argument("--seuil", type=float, default=0.97, help="SSIM minimale (défaut 0,97)")
    ap.add_argument("--carte", type=Path, help="carte des écarts en PNG")
    args = ap.parse_args(argv)
    try:
        ref, img = read_png(args.reference), read_png(args.image)
        res = compare(ref, img, args.masque)
    except (OSError, ValueError, zlib.error) as exc:
        print(f"ÉCHEC : {exc}", file=sys.stderr)
        return 2
    small = resize(img, ref.width, ref.height)
    if args.carte:
        write_png(args.carte, ssim_map(ref, res, args.masque))
    ok = res.score >= args.seuil
    print(f"[{'OK' if ok else 'ÉCHEC'}] SSIM {res.score:.4f} (seuil {args.seuil:g}, pire bloc {res.worst:.3f}, "
          f"{len(res.blocks)} blocs, {res.masked} masqués) ; écart moyen {mean_abs_diff(ref, small):.2f} niveaux"
          + (f" ; carte : {args.carte}" if args.carte else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
