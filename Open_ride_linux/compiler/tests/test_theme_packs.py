"""Tests des packs de thèmes : theme-list et theme-install (Lot N10)."""

from __future__ import annotations

import io
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest

from openride_compiler.cli import main
from openride_compiler.errors import CompileError
from openride_compiler.theme import DEFAULT_THEME_PATH
from openride_compiler.theme_packs import (
    MAX_THEME_UNCOMPRESSED_BYTES,
    install_theme,
    list_themes,
    normalize_theme_name,
)

THEME_LIST_JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "array",
    "items": {
        "type": "object",
        "required": [
            "name",
            "status",
            "builtin",
            "active",
            "textures_count",
            "size_bytes",
            "size_text",
            "path",
            "issues",
        ],
        "properties": {
            "name": {"type": "string"},
            "status": {"type": "string", "enum": ["ok", "avertissements", "erreurs"]},
            "builtin": {"type": "boolean"},
            "active": {"type": "boolean"},
            "textures_count": {"type": "integer", "minimum": 0},
            "size_bytes": {"type": "integer", "minimum": 0},
            "size_text": {"type": "string"},
            "path": {"type": "string"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["severity", "message"],
                    "properties": {
                        "severity": {"type": "string", "enum": ["error", "warning"]},
                        "message": {"type": "string"},
                    },
                },
            },
        },
    },
}


def _create_minimal_valid_theme(target_dir: Path, name: str = "Mon Super Thème") -> dict:
    target_dir.mkdir(parents=True, exist_ok=True)
    theme = json.loads(DEFAULT_THEME_PATH.read_text(encoding="utf-8"))
    theme["name"] = name
    (target_dir / "theme.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")
    return theme


def test_normalize_theme_name() -> None:
    assert normalize_theme_name("Essai Textures 2048") == "essai-textures-2048"
    assert normalize_theme_name("Éléphant Noir!") == "elephant-noir"
    assert normalize_theme_name("---Test---") == "test"
    assert normalize_theme_name("") == "theme"


def test_install_valid_dir_and_list(tmp_path: Path) -> None:
    themes_dir = tmp_path / "Themes"
    source_dir = tmp_path / "source_pack"
    _create_minimal_valid_theme(source_dir, name="Mon Theme Test")

    # Installation depuis dossier
    name, warnings = install_theme(source_dir, themes_dir=themes_dir)
    assert name == "mon-theme-test"
    assert (themes_dir / "mon-theme-test" / "theme.json").is_file()

    # Liste
    themes = list_themes(themes_dir=themes_dir)
    # default + mon-theme-test
    assert len(themes) == 2
    assert themes[0]["name"] == "default"
    assert themes[0]["builtin"] is True
    assert themes[1]["name"] == "mon-theme-test"
    assert themes[1]["status"] == "ok"
    assert themes[1]["builtin"] is False

    # Validation du schéma JSON de sortie
    jsonschema.validate(themes, THEME_LIST_JSON_SCHEMA)


def test_install_zipped_make_texture_theme(tmp_path: Path) -> None:
    # Utilise le script make_texture_theme du repo pour générer un vrai pack avec textures
    from openride_compiler.theme import REPO_ROOT
    make_script = REPO_ROOT / "engine" / "tests" / "make_texture_theme.py"
    assert make_script.is_file()

    pack_dir = tmp_path / "raw_pack"
    # Création du pack via l'utilitaire make_texture_theme
    import subprocess
    subprocess.run([sys.executable, str(make_script), "--out", str(pack_dir), "--size", "64"], check=True)
    assert (pack_dir / "theme.json").is_file()
    assert (pack_dir / "textures" / "grass.png").is_file()

    # Création de l'archive zip
    zip_path = tmp_path / "theme_pack.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for root, _, files in os.walk(pack_dir):
            for f in files:
                full_p = Path(root) / f
                rel_p = full_p.relative_to(pack_dir)
                zf.write(full_p, arcname=str(rel_p))

    themes_dir = tmp_path / "Themes"
    name, warnings = install_theme(zip_path, themes_dir=themes_dir)
    assert name == "essai-textures-64"
    assert (themes_dir / "essai-textures-64" / "theme.json").is_file()
    assert (themes_dir / "essai-textures-64" / "textures" / "grass.png").is_file()

    # Vérifie dans list_themes
    themes = list_themes(themes_dir=themes_dir)
    found = [t for t in themes if t["name"] == "essai-textures-64"]
    assert len(found) == 1
    assert found[0]["status"] == "ok"
    assert found[0]["textures_count"] == 3


def test_refuse_path_traversal_zip(tmp_path: Path) -> None:
    zip_path = tmp_path / "evil.zip"
    themes_dir = tmp_path / "Themes"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", "evil content")
        zf.writestr("theme.json", "{}")

    with pytest.raises(CompileError, match="Chemin interdit"):
        install_theme(zip_path, themes_dir=themes_dir)

    # Rien écrit dans themes_dir
    assert not themes_dir.exists() or not list(themes_dir.iterdir())


def test_refuse_symlink_zip(tmp_path: Path) -> None:
    zip_path = tmp_path / "symlink.zip"
    themes_dir = tmp_path / "Themes"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zi = zipfile.ZipInfo("link_file")
        zi.create_system = 3  # Unix
        zi.external_attr = stat.S_IFLNK << 16  # Symlink
        zf.writestr(zi, "/etc/passwd")
        zf.writestr("theme.json", "{}")

    with pytest.raises(CompileError, match="Lien symbolique interdit"):
        install_theme(zip_path, themes_dir=themes_dir)
    assert not themes_dir.exists() or not list(themes_dir.iterdir())


def test_refuse_exceeding_size(tmp_path: Path) -> None:
    zip_path = tmp_path / "huge.zip"
    themes_dir = tmp_path / "Themes"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("theme.json", "{}")
        # 501 Mo de zéros se compressent en quelques Ko
        zf.writestr("huge_empty.bin", b"\x00" * (MAX_THEME_UNCOMPRESSED_BYTES + 1000))

    with pytest.raises(CompileError, match="Archive trop volumineuse"):
        install_theme(zip_path, themes_dir=themes_dir)
    assert not themes_dir.exists() or not list(themes_dir.iterdir())


def test_refuse_invalid_theme_json(tmp_path: Path) -> None:
    pack_dir = tmp_path / "broken_theme"
    pack_dir.mkdir()
    (pack_dir / "theme.json").write_text('{"version": "1.0", "terrain": "not_an_object"}', encoding="utf-8")

    themes_dir = tmp_path / "Themes"
    with pytest.raises(CompileError, match="Thème invalide"):
        install_theme(pack_dir, themes_dir=themes_dir)

    assert not themes_dir.exists() or not list(themes_dir.iterdir())


def test_force_and_atomic_rollback(tmp_path: Path) -> None:
    themes_dir = tmp_path / "Themes"
    pack_v1 = tmp_path / "v1"
    _create_minimal_valid_theme(pack_v1, name="MyTheme")
    (pack_v1 / "tag.txt").write_text("version 1")

    # 1ère installation
    install_theme(pack_v1, themes_dir=themes_dir)
    assert (themes_dir / "mytheme" / "tag.txt").read_text() == "version 1"

    # Réinstallation sans force -> refus
    pack_v2 = tmp_path / "v2"
    _create_minimal_valid_theme(pack_v2, name="MyTheme")
    (pack_v2 / "tag.txt").write_text("version 2")

    with pytest.raises(CompileError, match="existe déjà"):
        install_theme(pack_v2, themes_dir=themes_dir, force=False)
    assert (themes_dir / "mytheme" / "tag.txt").read_text() == "version 1"

    # Réinstallation avec force -> remplacé
    install_theme(pack_v2, themes_dir=themes_dir, force=True)
    assert (themes_dir / "mytheme" / "tag.txt").read_text() == "version 2"


def test_cli_theme_list_and_install(tmp_path: Path, monkeypatch, capsys) -> None:
    themes_dir = tmp_path / "Themes"
    pack_dir = tmp_path / "pack_cli"
    _create_minimal_valid_theme(pack_dir, name="Theme CLI")

    # CLI theme-install
    rc = main(["theme-install", str(pack_dir), "--themes-dir", str(themes_dir)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Thème « theme-cli » installé avec succès" in captured.out
    assert 'theme = "theme-cli"' in captured.out

    # CLI theme-list
    rc_list = main(["theme-list", "--themes-dir", str(themes_dir)])
    assert rc_list == 0
    captured_list = capsys.readouterr()
    assert "default [intégré] : ok" in captured_list.out
    assert "theme-cli : ok" in captured_list.out

    # CLI theme-list --json
    rc_json = main(["theme-list", "--themes-dir", str(themes_dir), "--json"])
    assert rc_json == 0
    captured_json = capsys.readouterr()
    parsed = json.loads(captured_json.out)
    assert isinstance(parsed, list)
    jsonschema.validate(parsed, THEME_LIST_JSON_SCHEMA)
