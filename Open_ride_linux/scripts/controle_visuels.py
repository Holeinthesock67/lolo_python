#!/usr/bin/env python3
"""Contrôle des visuels de cartes de collection (lot BC4).

Vérifie la conformité des images générées pour les cartes du catalogue
`core/src/openride_core/data/collection.toml` :
- Fichiers au format PNG 512 × 512 pixels
- Canal alpha avec transparence effective (fond transparent)
- Poids de chaque image inférieur ou égal à 200 Ko
- Correspondance avec les noms de la colonne `visual` du catalogue
- Liste des visuels manquants (qui s'affichent avec un pictogramme neutre en jeu)
- Option de réduction / normalisation d'une image brute 1024 × 1024 vers 512 × 512

Usage :
    python3 scripts/controle_visuels.py [--dir DOSSIER] [--catalog FICHIER] [--strict] [--json]
    python3 scripts/controle_visuels.py --file CHEMIN_IMAGE
    python3 scripts/controle_visuels.py --normalize SOURCE --out DESTINATION
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "core" / "src" / "openride_core" / "data" / "collection.toml"
DEFAULT_ASSETS_DIR = ROOT / "engine" / "assets" / "collection"

EXPECTED_WIDTH = 512
EXPECTED_HEIGHT = 512
MAX_SIZE_BYTES = 200 * 1024  # 200 Ko = 204 800 octets


def inspect_png_bytes(data: bytes) -> tuple[bool, str, dict[str, Any]]:
    """Analyse bas niveau de la signature et des morceaux IHDR / tRNS du PNG sans dépendance externe.

    Retourne (ok, message_erreur, infos).
    """
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return False, "Signature PNG invalide (le fichier n'est pas un PNG)", {}

    offset = 8
    width = height = color_type = bit_depth = None
    has_trns = False

    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = offset + 8

        if chunk_type == b"IHDR" and length >= 13:
            width, height = struct.unpack(">II", data[chunk_data : chunk_data + 8])
            bit_depth = data[chunk_data + 8]
            color_type = data[chunk_data + 9]
        elif chunk_type == b"tRNS":
            has_trns = True

        offset += 12 + length

    if width is None or height is None:
        return False, "Morceau IHDR introuvable dans le fichier PNG", {}

    has_alpha = color_type in (4, 6) or (color_type == 3 and has_trns)
    return True, "", {
        "width": width,
        "height": height,
        "color_type": color_type,
        "bit_depth": bit_depth,
        "has_alpha_type": has_alpha,
    }


def check_image(path: Path | str) -> list[str]:
    """Contrôle un fichier d'image selon les critères d'acceptation du lot BC4.

    Retourne la liste des anomalies trouvées (liste vide si le fichier est conforme).
    """
    p = Path(path)
    errors: list[str] = []

    if not p.is_file():
        return [f"Fichier introuvable : {p.name}"]

    if p.suffix.lower() != ".png":
        errors.append(f"Extension invalide ({p.suffix}) : seul le format .png est accepté")

    size = p.stat().st_size
    if size > MAX_SIZE_BYTES:
        errors.append(
            f"Poids excessif : {size / 1024:.1f} Ko (limite maximale : {MAX_SIZE_BYTES // 1024} Ko)"
        )

    try:
        raw = p.read_bytes()
    except Exception as exc:
        return [f"Impossible de lire le fichier : {exc}"]

    ok, err_sig, info = inspect_png_bytes(raw)
    if not ok:
        errors.append(err_sig)
        return errors

    w, h = info["width"], info["height"]
    if w != EXPECTED_WIDTH or h != EXPECTED_HEIGHT:
        errors.append(
            f"Dimensions invalides : {w}x{h} px (attendu : {EXPECTED_WIDTH}x{EXPECTED_HEIGHT} px)"
        )

    if not info["has_alpha_type"]:
        errors.append("Canal alpha absent (l'image doit avoir un fond transparent)")

    # Contrôle de la présence effective de pixels transparents (avec Pillow si installé)
    try:
        from PIL import Image

        with Image.open(p) as im:
            if "A" in im.getbands():
                alpha = im.getchannel("A")
                extrema = alpha.getextrema()
                if extrema[0] >= 255:
                    errors.append("Transparence absente : aucun pixel transparent (alpha < 255) trouvé")
            elif not info["has_alpha_type"]:
                pass
    except ImportError:
        pass
    except Exception as exc:
        errors.append(f"Erreur au décodage de l'image : {exc}")

    return errors


def get_expected_visuals(catalog_path: Path | str = DEFAULT_CATALOG) -> list[str]:
    """Extrait la liste ordonnée et dédupliquée des identifiants `visual` du catalogue TOML."""
    cat = Path(catalog_path)
    if not cat.is_file():
        raise FileNotFoundError(f"Catalogue introuvable : {cat}")
    data = tomllib.loads(cat.read_text(encoding="utf-8"))
    cards = data.get("cards", [])
    seen = set()
    visuals: list[str] = []
    for c in cards:
        v = c.get("visual")
        if v and v not in seen:
            seen.add(v)
            visuals.append(v)
    return sorted(visuals)


def check_collection(
    assets_dir: Path | str = DEFAULT_ASSETS_DIR,
    catalog_path: Path | str = DEFAULT_CATALOG,
    strict: bool = False,
) -> dict[str, Any]:
    """Contrôle tous les visuels du catalogue dans le dossier des assets.

    Retourne un compte-rendu sous forme de dictionnaire.
    """
    directory = Path(assets_dir)
    expected = get_expected_visuals(catalog_path)

    valid: list[str] = []
    missing: list[str] = []
    invalid: dict[str, list[str]] = {}

    if not directory.is_dir():
        return {
            "total_expected": len(expected),
            "expected": expected,
            "valid": [],
            "missing": expected,
            "invalid": {},
            "extra": [],
            "ok": False if strict else True,
            "assets_dir": str(directory),
        }

    for v in expected:
        img_path = directory / f"{v}.png"
        if not img_path.exists():
            missing.append(v)
        else:
            errs = check_image(img_path)
            if errs:
                invalid[v] = errs
            else:
                valid.append(v)

    # Détection des fichiers PNG surnuméraires non référencés
    present_pngs = {p.stem for p in directory.glob("*.png")}
    extra = sorted(present_pngs - set(expected))

    ok = (len(invalid) == 0) and (not strict or len(missing) == 0)

    return {
        "total_expected": len(expected),
        "expected": expected,
        "valid": valid,
        "missing": missing,
        "invalid": invalid,
        "extra": extra,
        "ok": ok,
        "assets_dir": str(directory),
    }


def normalize_image(
    src: Path | str,
    dst: Path | str,
    target_size: int = EXPECTED_WIDTH,
    max_kb: int = 200,
) -> None:
    """Normalise une image brute (p. ex. 1024x1024 livrée par Gemini) :

    - Redimensionne en 512 × 512 avec filtre Lanczos
    - Applique un masque circulaire si l'image n'est pas transparente
    - Optimise la compression PNG sous max_kb (200 Ko)
    """
    from PIL import Image, ImageDraw

    src_p = Path(src)
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src_p) as im:
        im = im.convert("RGBA")
        w, h = im.size

        # Si l'image n'a pas de canal alpha effectif, découpe circulaire automatique
        alpha_min = im.getchannel("A").getextrema()[0]
        if alpha_min >= 255:
            mask = Image.new("L", (w, h), 0)
            draw = ImageDraw.Draw(mask)
            # Cercle centré d'environ 85-88% de la taille
            margin = int(w * 0.06)
            draw.ellipse((margin, margin, w - margin, h - margin), fill=255)
            im.putalpha(mask)

        im_resized = im.resize((target_size, target_size), Image.Resampling.LANCZOS)

        # Sauvegarde optimisée
        im_resized.save(dst_p, format="PNG", optimize=True)

        # Si le fichier dépasse max_kb, quantisation 256 couleurs préservant l'alpha
        if dst_p.stat().st_size > max_kb * 1024:
            q = im_resized.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
            q.save(dst_p, format="PNG", optimize=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contrôle des visuels de cartes OpenRide (lot BC4)")
    parser.add_argument("--dir", default=DEFAULT_ASSETS_DIR, type=Path, help="Dossier des visuels PNG")
    parser.add_argument("--catalog", default=DEFAULT_CATALOG, type=Path, help="Catalogue collection.toml")
    parser.add_argument("--strict", action="store_true", help="Échoue si un ou plusieurs visuels sont manquants")
    parser.add_argument("--file", type=Path, help="Contrôle un fichier image unique")
    parser.add_argument("--json", action="store_true", help="Affiche le compte-rendu en JSON")
    parser.add_argument("--normalize", type=Path, help="Image source à normaliser en 512x512 transparent")
    parser.add_argument("--out", type=Path, help="Destination de l'image normalisée")

    args = parser.parse_args(argv)

    if args.normalize:
        if not args.out:
            sys.stderr.write("Erreur : --out requis avec --normalize\n")
            return 2
        normalize_image(args.normalize, args.out)
        errs = check_image(args.out)
        if errs:
            sys.stderr.write(f"Image normalisée invalide : {', '.join(errs)}\n")
            return 1
        print(f"Image normalisée et validée : {args.out}")
        return 0

    if args.file:
        errs = check_image(args.file)
        if args.json:
            print(json.dumps({"file": str(args.file), "errors": errs, "valid": len(errs) == 0}, indent=2))
        else:
            if errs:
                print(f"[ERREUR] {args.file.name} :")
                for e in errs:
                    print(f"  - {e}")
            else:
                print(f"[OK] {args.file.name} : conforme aux critères BC4 (512x512, alpha, <= 200 Ko)")
        return 1 if errs else 0

    report = check_collection(assets_dir=args.dir, catalog_path=args.catalog, strict=args.strict)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1

    print("=== Contrôle des visuels de la Collection (Lot BC4) ===")
    print(f"Catalogue : {args.catalog}")
    print(f"Dossier   : {args.dir}")
    print(f"Total attendu : {report['total_expected']} visuels")
    print(f"  - Valides   : {len(report['valid'])}")
    print(f"  - Invalides : {len(report['invalid'])}")
    print(f"  - Manquants : {len(report['missing'])}")

    if report["invalid"]:
        print("\nDétail des visuels invalides :")
        for v, errs in sorted(report["invalid"].items()):
            print(f"  * {v}.png :")
            for e in errs:
                print(f"      - {e}")

    if report["missing"]:
        print(f"\nVisuels manquants ({len(report['missing'])}) :")
        for v in report["missing"][:10]:
            print(f"  - {v}.png")
        if len(report["missing"]) > 10:
            print(f"  ... et {len(report['missing']) - 10} autres.")

    if report["extra"]:
        print(f"\nVisuels surnuméraires hors catalogue ({len(report['extra'])}) :")
        for v in report["extra"]:
            print(f"  - {v}.png")

    if report["ok"]:
        print("\nVerdict : SUCCÈS (aucun fichier invalide détecté)")
        return 0
    else:
        print("\nVerdict : ÉCHEC (fichiers non conformes ou manquants en mode strict)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
