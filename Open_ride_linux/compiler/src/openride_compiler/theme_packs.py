"""Gestion et installation des packs de thèmes (Lot N10, SRS §10 et §11).

Commandes :
- `openride-compiler theme-list [--themes-dir D] [--json]`
- `openride-compiler theme-install SOURCE [--name NOM] [--force] [--themes-dir D]`
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import unicodedata
import uuid
import zipfile
from pathlib import Path
from typing import Any

from .errors import CompileError
from .theme import DEFAULT_THEME_DIR, Issue, check_theme

MAX_THEME_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 Mo
DEFAULT_THEMES_DIR = Path.home() / "OpenRide" / "Themes"
DEFAULT_CONFIG_PATH = Path.home() / "OpenRide" / "config.toml"


def normalize_theme_name(text: str) -> str:
    """Normalise un nom de thème en caractères alphanumériques minuscules et tirets (a-z0-9-)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return name or "theme"


def _read_current_config_theme(config_path: Path | None = None) -> str:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        return "default"
    try:
        import tomllib
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        render = data.get("render", {})
        if isinstance(render, dict) and "theme" in render:
            return str(render["theme"])
    except Exception:
        pass
    return "default"


def _dir_size_and_textures(theme_dir: Path) -> tuple[int, int]:
    total_bytes = 0
    textures_count = 0
    if not theme_dir.is_dir():
        return 0, 0
    for root, _, files in os.walk(theme_dir):
        for f in files:
            p = Path(root) / f
            try:
                st = p.stat()
                total_bytes += st.st_size
                if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    textures_count += 1
            except OSError:
                pass
    return total_bytes, textures_count


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} o"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} Ko".replace(".", ",")
    return f"{size_bytes / (1024 * 1024):.1f} Mo".replace(".", ",")


def list_themes(
    themes_dir: Path | None = None,
    config_path: Path | None = None
) -> list[dict[str, Any]]:
    """Recense les thèmes disponibles (le thème intégré 'default' et ceux de themes_dir)."""
    t_dir = Path(themes_dir) if themes_dir is not None else DEFAULT_THEMES_DIR
    active_theme = _read_current_config_theme(config_path)

    out: list[dict[str, Any]] = []

    # 1. Thème intégré 'default'
    def_size, def_tex = _dir_size_and_textures(DEFAULT_THEME_DIR)
    out.append({
        "name": "default",
        "status": "ok",
        "builtin": True,
        "active": (active_theme == "default"),
        "textures_count": def_tex,
        "size_bytes": def_size,
        "size_text": _format_size(def_size),
        "path": str(DEFAULT_THEME_DIR),
        "issues": []
    })

    # 2. Thèmes utilisateur
    if t_dir.is_dir():
        for d in sorted(t_dir.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            if d.name == "default":
                continue

            issues = check_theme(d)
            errors = [i for i in issues if i.severity == "error"]
            warnings = [i for i in issues if i.severity == "warning"]

            status = "ok"
            if errors:
                status = "erreurs"
            elif warnings:
                status = "avertissements"

            size_bytes, textures = _dir_size_and_textures(d)

            out.append({
                "name": d.name,
                "status": status,
                "builtin": False,
                "active": (active_theme == d.name),
                "textures_count": textures,
                "size_bytes": size_bytes,
                "size_text": _format_size(size_bytes),
                "path": str(d),
                "issues": [{"severity": i.severity, "message": i.message} for i in issues]
            })

    return out


def format_themes_text(themes: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for t in themes:
        mark = "* " if t["active"] else "  "
        builtin_tag = " [intégré]" if t["builtin"] else ""
        lines.append(
            f"{mark}{t['name']}{builtin_tag} : {t['status']}, "
            f"{t['textures_count']} texture(s), {t['size_text']}"
        )
    return "\n".join(lines)


def _check_no_symlinks(path: Path) -> None:
    if path.is_symlink():
        raise CompileError(f"Refus des liens symboliques dans le pack : {path}")
    if path.is_dir():
        for entry in path.iterdir():
            _check_no_symlinks(entry)


def _extract_zip_securely(zip_path: Path, target_dir: Path) -> Path:
    total_uncompressed = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        for info in infos:
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_THEME_UNCOMPRESSED_BYTES:
                raise CompileError(
                    f"Archive trop volumineuse : dépasse {MAX_THEME_UNCOMPRESSED_BYTES // (1024 * 1024)} Mo"
                )

            # Refus des chemins absolus ou contenant ..
            filename = info.filename
            if filename.startswith("/") or filename.startswith("\\") or ".." in filename.replace("\\", "/").split("/"):
                raise CompileError(f"Chemin interdit dans l'archive zip : {filename!r}")

            # Refus des liens symboliques (attribut UNIX S_IFLNK)
            mode = info.external_attr >> 16
            if mode != 0 and stat.S_ISLNK(mode):
                raise CompileError(f"Lien symbolique interdit dans l'archive zip : {filename!r}")

        zf.extractall(target_dir)

    # Détecte si l'archive contient un dossier racine unique ou les fichiers directement
    entries = [p for p in target_dir.iterdir() if not p.name.startswith(".")]
    if len(entries) == 1 and entries[0].is_dir() and not (target_dir / "theme.json").is_file():
        return entries[0]
    return target_dir


def install_theme(
    source: Path,
    name: str | None = None,
    force: bool = False,
    themes_dir: Path | None = None
) -> tuple[str, list[str]]:
    """Installe un pack de thème depuis un dossier ou un fichier .zip.

    Effectue tous les contrôles de sécurité et de conformité avant toute copie.
    Renvoie le nom normalisé du thème installé et la liste des avertissements.
    """
    source = Path(source)
    if not source.exists():
        raise CompileError(f"Source introuvable : {source}")

    t_dir = Path(themes_dir) if themes_dir is not None else DEFAULT_THEMES_DIR
    t_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_path = Path(tmp_str)
        extracted_theme_dir: Path

        if source.is_file() and source.suffix.lower() == ".zip":
            extracted_theme_dir = _extract_zip_securely(source, tmp_path)
        elif source.is_dir():
            _check_no_symlinks(source)
            size, _ = _dir_size_and_textures(source)
            if size > MAX_THEME_UNCOMPRESSED_BYTES:
                raise CompileError(
                    f"Dossier source trop volumineux : dépasse {MAX_THEME_UNCOMPRESSED_BYTES // (1024 * 1024)} Mo"
                )
            copy_dst = tmp_path / source.name
            shutil.copytree(source, copy_dst, symlinks=False)
            extracted_theme_dir = copy_dst
        else:
            raise CompileError(f"Source non prise en charge (dossier ou archive .zip attendu) : {source}")

        # Si le dossier extrait ne contient pas theme.json, cherchons dans un éventuel sous-dossier
        if not (extracted_theme_dir / "theme.json").is_file():
            subdirs = [p for p in extracted_theme_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]
            for sub in subdirs:
                if (sub / "theme.json").is_file():
                    extracted_theme_dir = sub
                    break

        theme_json_path = extracted_theme_dir / "theme.json"
        if not theme_json_path.is_file():
            raise CompileError(f"theme.json absent dans le pack {source.name}")

        # Validation par check_theme avant installation
        issues = check_theme(extracted_theme_dir)
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        if errors:
            msgs = "\n  - ".join(e.message for e in errors)
            raise CompileError(f"Thème invalide selon theme.schema.json :\n  - {msgs}")

        # Détermination du nom de thème normalisé
        theme_name = ""
        if name:
            theme_name = normalize_theme_name(name)
        else:
            try:
                theme_data = json.loads(theme_json_path.read_text(encoding="utf-8"))
                if isinstance(theme_data, dict) and "name" in theme_data:
                    theme_name = normalize_theme_name(str(theme_data["name"]))
            except Exception:
                pass
            if not theme_name:
                theme_name = normalize_theme_name(source.stem)

        if theme_name == "default":
            raise CompileError("Le nom de thème 'default' est réservé au thème intégré.")

        target_path = t_dir / theme_name
        if target_path.exists() and not force:
            raise CompileError(f"Le thème '{theme_name}' existe déjà dans {t_dir} (utiliser --force)")

        # Installation atomique
        staging_dir = t_dir / f".staging_{theme_name}_{uuid.uuid4().hex}"
        backup_dir = t_dir / f".backup_{theme_name}_{uuid.uuid4().hex}"

        try:
            shutil.copytree(extracted_theme_dir, staging_dir, symlinks=False)
            if target_path.exists():
                staging_dir.rename(backup_dir)  # vérifie le renommage atomique
                backup_dir.rename(staging_dir)
                target_path.rename(backup_dir)
                try:
                    staging_dir.rename(target_path)
                except Exception:
                    if backup_dir.exists():
                        backup_dir.rename(target_path)
                    raise
                finally:
                    if backup_dir.exists():
                        shutil.rmtree(backup_dir, ignore_errors=True)
            else:
                staging_dir.rename(target_path)
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    return theme_name, [w.message for w in warnings]
