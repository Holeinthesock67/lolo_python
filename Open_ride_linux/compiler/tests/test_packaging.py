"""Paquet installable hors du dépôt (lot J4) : copies embarquées, import sans extras, roue.

- `data/theme.schema.json` et `data/default_theme.json` sont des copies, identiques octet pour octet,
  de `docs/contracts/world/theme.schema.json` et `engine/themes/default/theme.json` (les références) ;
- `openride_compiler.cli` s'importe sans les extras `dev` ;
- test `slow` : la roue construite sans réseau, installée dans un environnement neuf, donne un
  `openride-compiler theme-check` qui marche depuis un dossier hors du dépôt.
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import essai_roue  # scripts/ (chemin posé par conftest.py)

COMPILER_DIR = Path(__file__).resolve().parents[1]
ROOT = COMPILER_DIR.parent
DATA_DIR = COMPILER_DIR / "src" / "openride_compiler" / "data"

# copie embarquée -> référence
COPIES = {
    DATA_DIR / "theme.schema.json": ROOT / "docs" / "contracts" / "world" / "theme.schema.json",
    DATA_DIR / "default_theme.json": ROOT / "engine" / "themes" / "default" / "theme.json",
}
# fichiers propres au paquet, sans référence ailleurs dans le dépôt
ORIGINAUX = {
    DATA_DIR / "regional_variants.toml",   # table des variantes régionales (lot U4)
    DATA_DIR / "koppen_1986_2010.u8.xz",   # carte des climats de Köppen-Geiger (lot U24)
    DATA_DIR / "koppen_LISEZMOI.md",       # sa provenance et sa licence
    DATA_DIR / "volcanic_areas.toml",      # paysages volcaniques (lot U24)
    DATA_DIR / "japan_zone.toml",          # zone du biome japan (lot JP2)
}


@pytest.mark.parametrize("copie", sorted(COPIES), ids=lambda p: p.name)
def test_copie_embarquee_identique_a_sa_reference(copie: Path) -> None:
    reference = COPIES[copie]
    assert copie.is_file() and filecmp.cmp(copie, reference, shallow=False), (
        f"{copie.relative_to(ROOT)} diffère de sa référence {reference.relative_to(ROOT)}. "
        f"Recopier depuis Open_ride_linux/ : cp {reference.relative_to(ROOT)} {copie.relative_to(ROOT)}"
    )


def test_aucune_copie_orpheline() -> None:
    assert set(DATA_DIR.iterdir()) == set(COPIES) | ORIGINAUX


def test_theme_lit_les_copies_embarquees() -> None:
    from openride_compiler import theme

    assert theme.SCHEMA_PATH in COPIES and theme.DEFAULT_THEME_PATH in COPIES


def test_cli_s_importe_sans_les_extras_dev() -> None:
    """Critère 4 : pytest, hypothesis et Pillow (extras `dev`) masqués."""
    code = ("import sys\n"
            "for m in ('pytest', 'hypothesis', 'PIL'): sys.modules[m] = None\n"
            "import openride_compiler.cli\n")
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr


@pytest.mark.slow
def test_roue_installee_hors_du_depot(tmp_path: Path) -> None:
    pytest.importorskip("setuptools", reason="construction sans réseau : `pip install \"setuptools>=68\"` dans le venv")
    bin_dir = essai_roue.construire_et_installer(COMPILER_DIR, tmp_path / "roue")
    dehors = tmp_path / "dehors"
    shutil.copytree(ROOT / "engine" / "themes" / "default", dehors / "default")

    res = essai_roue.lancer(bin_dir, ["python", "-c", "import openride_compiler; print(openride_compiler.__file__)"],
                            cwd=dehors)
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()).is_relative_to(tmp_path / "roue" / "venv"), res.stdout

    res = essai_roue.lancer(bin_dir, ["openride-compiler", "theme-check", str(dehors / "default")], cwd=dehors)
    assert res.returncode == 0, res.stdout + res.stderr
