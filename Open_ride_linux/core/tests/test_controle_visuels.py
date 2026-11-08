"""Tests du script de contrôle des visuels de cartes de collection (lot BC4).

Vérifie les critères d'acceptation du cahier LOT_BC4_visuels_gemini.md :
- Lecture du catalogue collection.toml (42 visuels)
- Validation des images conformes (PNG, 512x512, fond transparent, <= 200 Ko)
- Tests négatifs (rejet taille incorrecte, absence de transparence, fichier trop lourd, fichier corrompu)
- Détection des fichiers manquants et comportement strict / non-strict
- Normalisation automatique d'une image brute
- Interface en ligne de commande (CLI)
"""

from __future__ import annotations

import os
import sys
import types

# Compatibilité Windows pour l'environnement de test local (fcntl absent sur Windows)
if sys.platform == "win32" and "fcntl" not in sys.modules:
    _fake_fcntl = types.ModuleType("fcntl")
    _fake_fcntl.LOCK_EX = 2
    _fake_fcntl.LOCK_NB = 4
    _fake_fcntl.LOCK_UN = 8
    _fake_fcntl.flock = lambda *args, **kwargs: None
    sys.modules["fcntl"] = _fake_fcntl
    os.environ.setdefault("OPENRIDE_TESTS_VERROU", "1")

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "controle_visuels.py"
spec = importlib.util.spec_from_file_location("controle_visuels", SCRIPT)
cv = importlib.util.module_from_spec(spec)
sys.modules["controle_visuels"] = cv
spec.loader.exec_module(cv)


def _make_png(
    path: Path,
    size: tuple[int, int] = (512, 512),
    mode: str = "RGBA",
    transparent: bool = True,
    fill_bytes: int | None = None,
) -> Path:
    """Fabrique une image PNG de test avec des caractéristiques précises."""
    if mode == "RGBA":
        base_color = (200, 100, 50, 0 if transparent else 255)
        im = Image.new("RGBA", size, base_color)
        if transparent:
            # Dessine un disque opaque au centre pour avoir des pixels opaques et transparents
            for x in range(size[0] // 4, 3 * size[0] // 4):
                for y in range(size[1] // 4, 3 * size[1] // 4):
                    im.putpixel((x, y), (150, 80, 40, 255))
    else:
        im = Image.new("RGB", size, (200, 100, 50))

    im.save(path, format="PNG")

    if fill_bytes and fill_bytes > path.stat().st_size:
        # Gonfle artificiellement le fichier en ajoutant un morceau auxiliaire pour tester la limite de poids
        extra = b"\x00" * (fill_bytes - path.stat().st_size)
        with open(path, "ab") as f:
            f.write(extra)

    return path


def test_catalog_reads_all_42_visuals():
    """Le catalogue collection.toml est lu et contient exactement 42 visuels distincts."""
    visuals = cv.get_expected_visuals()
    assert len(visuals) == 42
    assert "pedale" in visuals
    assert "everest" in visuals
    assert "coq" in visuals
    assert "soleil_haut" in visuals
    assert "citrouille" in visuals
    assert "bougie_2" in visuals


def test_valid_image_passes_all_checks(tmp_path):
    """Une image 512x512 transparente de moins de 200 Ko est déclarée valide sans erreur."""
    img_path = _make_png(tmp_path / "pedale.png", size=(512, 512), mode="RGBA", transparent=True)
    assert img_path.stat().st_size <= cv.MAX_SIZE_BYTES
    errs = cv.check_image(img_path)
    assert errs == []


def test_refuse_wrong_dimensions(tmp_path):
    """Les images qui ne font pas exactement 512x512 pixels sont rejetées."""
    too_large = _make_png(tmp_path / "large.png", size=(1024, 1024))
    errs_large = cv.check_image(too_large)
    assert any("Dimensions invalides" in e and "1024x1024" in e for e in errs_large)

    too_small = _make_png(tmp_path / "small.png", size=(256, 256))
    errs_small = cv.check_image(too_small)
    assert any("Dimensions invalides" in e and "256x256" in e for e in errs_small)


def test_refuse_no_transparency(tmp_path):
    """Une image sans canal alpha ou entièrement opaque est rejetée."""
    # 1. Image en mode RGB pur (pas de canal alpha)
    img_rgb = _make_png(tmp_path / "rgb.png", size=(512, 512), mode="RGB")
    errs_rgb = cv.check_image(img_rgb)
    assert any("Canal alpha absent" in e for e in errs_rgb)

    # 2. Image RGBA mais avec alpha=255 partout (opaque)
    img_opaque = _make_png(tmp_path / "opaque.png", size=(512, 512), mode="RGBA", transparent=False)
    errs_opaque = cv.check_image(img_opaque)
    assert any("Transparence absente" in e for e in errs_opaque)


def test_refuse_too_heavy(tmp_path):
    """Une image dépassant le plafond de 200 Ko est rejetée."""
    heavy_path = _make_png(
        tmp_path / "heavy.png",
        size=(512, 512),
        fill_bytes=220 * 1024,  # 220 Ko > 200 Ko
    )
    errs = cv.check_image(heavy_path)
    assert any("Poids excessif" in e for e in errs)


def test_refuse_not_png_or_corrupt(tmp_path):
    """Les fichiers corrompus, inexistants ou non-PNG sont rejetés."""
    missing = tmp_path / "nonexistent.png"
    assert any("Fichier introuvable" in e for e in cv.check_image(missing))

    fake_ext = tmp_path / "image.jpg"
    fake_ext.write_bytes(b"dummy")
    assert any("Extension invalide" in e for e in cv.check_image(fake_ext))

    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"NOT A PNG FILE DATA")
    assert any("Signature PNG invalide" in e for e in cv.check_image(corrupt))


def test_check_collection_missing_and_valid(tmp_path):
    """check_collection identifie les visuels présents valides, invalides et manquants."""
    assets = tmp_path / "assets"
    assets.mkdir()

    # On crée 2 images valides, 1 image invalide, et 1 image hors catalogue
    _make_png(assets / "pedale.png", size=(512, 512), transparent=True)
    _make_png(assets / "coq.png", size=(512, 512), transparent=True)
    _make_png(assets / "everest.png", size=(1024, 1024))  # mauvaise taille
    _make_png(assets / "inconnu.png", size=(512, 512), transparent=True)  # extra

    rep = cv.check_collection(assets_dir=assets)
    assert rep["total_expected"] == 42
    assert "pedale" in rep["valid"]
    assert "coq" in rep["valid"]
    assert "everest" in rep["invalid"]
    assert "citrouille" in rep["missing"]
    assert rep["extra"] == ["inconnu"]

    # En mode non-strict, rep["ok"] est False car 'everest' est invalide
    assert rep["ok"] is False

    # Si on supprime l'invalide, en mode non-strict c'est True (les manquants sont tolérés)
    (assets / "everest.png").unlink()
    rep2 = cv.check_collection(assets_dir=assets, strict=False)
    assert rep2["ok"] is True
    assert len(rep2["invalid"]) == 0
    assert len(rep2["missing"]) == 40

    # Mais en mode strict, les manquants provoquent ok = False
    rep_strict = cv.check_collection(assets_dir=assets, strict=True)
    assert rep_strict["ok"] is False


def test_normalize_raw_image(tmp_path):
    """normalize_image transforme une image 1024x1024 brute en PNG 512x512 transparent conforme."""
    raw = tmp_path / "raw.png"
    out = tmp_path / "out.png"

    # Création d'une image brute 1024x1024
    im = Image.new("RGBA", (1024, 1024), (200, 150, 100, 255))
    im.save(raw, format="PNG")

    cv.normalize_image(raw, out, target_size=512, max_kb=200)

    assert out.is_file()
    errs = cv.check_image(out)
    assert errs == []
    with Image.open(out) as im_out:
        assert im_out.size == (512, 512)
        assert im_out.mode == "RGBA"


def test_cli_execution(tmp_path):
    """Exécution du script via CLI (--file, --json, code de retour)."""
    valid_png = _make_png(tmp_path / "test_cli.png", size=(512, 512), transparent=True)

    # 1. Contrôle unitaire valide
    res = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(valid_png)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "[OK]" in res.stdout

    # 2. Contrôle unitaire invalide
    bad_png = _make_png(tmp_path / "bad_cli.png", size=(200, 200))
    res_bad = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(bad_png)],
        capture_output=True,
        text=True,
    )
    assert res_bad.returncode == 1
    assert "[ERREUR]" in res_bad.stdout

    # 3. Contrôle collection en sortie JSON
    res_json = subprocess.run(
        [sys.executable, str(SCRIPT), "--dir", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
    )
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data["total_expected"] == 42
    assert "missing" in data
