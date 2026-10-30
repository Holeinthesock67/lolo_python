"""Gestion et installation des packs de thèmes (Lot N10, SRS §10 et §11 ; adresses et bibliothèque : lot U15).

Commandes :
- `openride-compiler theme-list [--themes-dir D] [--json]` : taille et dernière utilisation de chaque pack ;
- `openride-compiler theme-install SOURCE [--name NOM] [--force] [--themes-dir D]` : SOURCE est un dossier,
  une archive .zip ou une adresse `https://` d'archive .zip (téléchargée dans un dossier temporaire, contrôlée
  par `theme-check` avant toute copie ; HTTPS seulement, jamais pendant une séance).

Bibliothèque (U-Q3) : les packs installés restent dans `~/OpenRide/Themes/`. Le lanceur du core écrit la date
de dernière utilisation du thème choisi dans `.utilisation.json` (`{nom: date ISO}`) au démarrage d'une séance.
Au-delà de `[render] theme_library_gb` (5 Go par défaut, 1 à 50), `theme-install` retire les packs utilisés le
moins récemment, jamais le thème choisi, le thème intégré ni celui qu'il vient d'installer.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import CompileError
from .theme import DEFAULT_THEME_DIR, check_theme

MAX_THEME_UNCOMPRESSED_BYTES = 500 * 1024 * 1024  # 500 Mo
DEFAULT_THEMES_DIR = Path.home() / "OpenRide" / "Themes"
DEFAULT_CONFIG_PATH = Path.home() / "OpenRide" / "config.toml"
USE_FILE = ".utilisation.json"           # écrit par openride_core.launcher.record_theme_use
DEFAULT_LIBRARY_GB = 5.0
LIBRARY_GB_RANGE = (1.0, 50.0)
DOWNLOAD_TIMEOUT_S = 60.0
DOWNLOAD_CHUNK = 1024 * 1024


def normalize_theme_name(text: str) -> str:
    """Normalise un nom de thème en caractères alphanumériques minuscules et tirets (a-z0-9-)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return name or "theme"


def _read_render_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        return {}
    try:
        import tomllib
        render = tomllib.loads(path.read_text(encoding="utf-8")).get("render", {})
    except (OSError, ValueError):   # config illisible ou TOML invalide : valeurs par défaut
        return {}
    return render if isinstance(render, dict) else {}


def _read_current_config_theme(config_path: Path | None = None) -> str:
    return str(_read_render_config(config_path).get("theme", "default"))


def library_limit_bytes(config_path: Path | None = None) -> int:
    """Plafond de la bibliothèque : `[render] theme_library_gb` (5 Go, ramené entre 1 et 50)."""
    gb = _read_render_config(config_path).get("theme_library_gb", DEFAULT_LIBRARY_GB)
    if isinstance(gb, bool) or not isinstance(gb, (int, float)):
        gb = DEFAULT_LIBRARY_GB
    gb = min(max(float(gb), LIBRARY_GB_RANGE[0]), LIBRARY_GB_RANGE[1])
    return int(gb * 1024 ** 3)


def read_theme_use(themes_dir: Path) -> dict[str, str]:
    """Dates de dernière utilisation (`.utilisation.json`) ; fichier absent ou illisible : aucune."""
    try:
        data = json.loads((Path(themes_dir) / USE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _last_used(theme_dir: Path, uses: dict[str, str]) -> str:
    """Date de dernière utilisation, sinon date d'installation (dossier), au format ISO."""
    if theme_dir.name in uses:
        return uses[theme_dir.name]
    try:
        return datetime.fromtimestamp(theme_dir.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return ""


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
    uses = read_theme_use(t_dir)
    out.append({
        "name": "default",
        "status": "ok",
        "builtin": True,
        "active": (active_theme == "default"),
        "textures_count": def_tex,
        "size_bytes": def_size,
        "size_text": _format_size(def_size),
        "path": str(DEFAULT_THEME_DIR),
        "last_used": uses.get("default", ""),
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
                "last_used": uses.get(d.name, ""),
                "issues": [{"severity": i.severity, "message": i.message} for i in issues]
            })

    return out


def format_themes_text(themes: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for t in themes:
        mark = "* " if t["active"] else "  "
        builtin_tag = " [intégré]" if t["builtin"] else ""
        used = t.get("last_used", "")
        lines.append(
            f"{mark}{t['name']}{builtin_tag} : {t['status']}, "
            f"{t['textures_count']} texture(s), {t['size_text']}, "
            f"dernière utilisation : {used[:10] if used else 'jamais'}"
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
            if filename.startswith(("/", "\\")) or ".." in filename.replace("\\", "/").split("/"):
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


def is_url(source: Path | str) -> bool:
    return isinstance(source, str) and "://" in source


def download_pack(url: str, dest_dir: Path, ssl_context: Any = None,
                  timeout_s: float = DOWNLOAD_TIMEOUT_S) -> Path:
    """Télécharge l'archive d'un pack (HTTPS seulement) dans `dest_dir/pack.zip`, au plus
    MAX_THEME_UNCOMPRESSED_BYTES ; réseau absent ou adresse injoignable : CompileError lisible."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() != "https" or not parts.netloc:
        raise CompileError(f"Adresse refusée (https:// seulement) : {url}")
    target = Path(dest_dir) / "pack.zip"
    total = 0
    try:
        with urllib.request.urlopen(url, timeout=timeout_s, context=ssl_context) as resp, target.open("wb") as out:
            while chunk := resp.read(DOWNLOAD_CHUNK):
                total += len(chunk)
                if total > MAX_THEME_UNCOMPRESSED_BYTES:
                    raise CompileError(
                        f"Archive trop volumineuse : dépasse {MAX_THEME_UNCOMPRESSED_BYTES // (1024 * 1024)} Mo")
                out.write(chunk)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        raise CompileError(f"Téléchargement impossible (réseau absent ou adresse injoignable) : {url} ({reason})") from None
    if not zipfile.is_zipfile(target):
        raise CompileError(f"L'adresse ne donne pas une archive .zip : {url}")
    return target


def enforce_library_limit(themes_dir: Path, limit_bytes: int, keep: set[str]) -> list[str]:
    """Retire les packs utilisés le moins récemment tant que la bibliothèque dépasse `limit_bytes` ;
    jamais ceux de `keep` (thème choisi, pack qu'on vient d'installer) ni le thème intégré. Renvoie les retirés."""
    t_dir = Path(themes_dir)
    if not t_dir.is_dir():
        return []
    uses = read_theme_use(t_dir)
    packs = []
    for d in t_dir.iterdir():
        if d.is_dir() and not d.name.startswith(".") and d.name != "default":
            packs.append((_last_used(d, uses), d.name, _dir_size_and_textures(d)[0], d))
    total = sum(p[2] for p in packs)
    removed: list[str] = []
    for _used, name, size, d in sorted(packs):
        if total <= limit_bytes:
            break
        if name in keep:
            continue
        shutil.rmtree(d, ignore_errors=True)
        total -= size
        removed.append(name)
    return removed


def install_theme(
    source: Path | str,
    name: str | None = None,
    force: bool = False,
    themes_dir: Path | None = None,
    config_path: Path | None = None,
    ssl_context: Any = None,
) -> tuple[str, list[str]]:
    """Installe un pack de thème depuis un dossier, un fichier .zip ou une adresse https:// d'archive .zip.

    Effectue tous les contrôles de sécurité et de conformité avant toute copie, puis tient la bibliothèque sous
    son plafond (`enforce_library_limit`). Renvoie le nom normalisé du thème installé et la liste des
    avertissements (dont les packs retirés de la bibliothèque).
    """
    t_dir = Path(themes_dir) if themes_dir is not None else DEFAULT_THEMES_DIR

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_path = Path(tmp_str)
        extracted_theme_dir: Path
        url = str(source) if is_url(source) else ""
        if url:
            dl_dir = tmp_path / "telechargement"
            dl_dir.mkdir()
            source = download_pack(url, dl_dir, ssl_context=ssl_context)
            tmp_path = tmp_path / "pack"
            tmp_path.mkdir()
        source = Path(source)
        if not source.exists():
            raise CompileError(f"Source introuvable : {source}")

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
            except (OSError, ValueError):   # theme.json déjà validé par check_theme ; repli sur le dossier
                theme_name = ""
            if not theme_name:
                stem = Path(urllib.parse.urlsplit(url).path).stem if url else source.stem
                theme_name = normalize_theme_name(stem)

        if theme_name == "default":
            raise CompileError("Le nom de thème 'default' est réservé au thème intégré.")

        target_path = t_dir / theme_name
        if target_path.exists() and not force:
            raise CompileError(f"Le thème '{theme_name}' existe déjà dans {t_dir} (utiliser --force)")

        # Installation atomique : copie dans un dossier temporaire du dossier des thèmes, puis renommage.
        # En cas d'échec, l'ancien thème est remis en place et le dossier temporaire supprimé.
        t_dir.mkdir(parents=True, exist_ok=True)
        staging_dir = t_dir / f".staging_{theme_name}_{uuid.uuid4().hex}"
        backup_dir = t_dir / f".backup_{theme_name}_{uuid.uuid4().hex}"

        try:
            shutil.copytree(extracted_theme_dir, staging_dir, symlinks=False)
            if target_path.exists():
                target_path.rename(backup_dir)
                try:
                    staging_dir.rename(target_path)
                except BaseException:
                    backup_dir.rename(target_path)
                    raise
                shutil.rmtree(backup_dir, ignore_errors=True)
            else:
                staging_dir.rename(target_path)
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    messages = [w.message for w in warnings]
    keep = {theme_name, _read_current_config_theme(config_path)}
    for gone in enforce_library_limit(t_dir, library_limit_bytes(config_path), keep):
        messages.append(f"bibliothèque des thèmes au-delà de son plafond : pack « {gone} » retiré "
                        "(le moins récemment utilisé)")
    return theme_name, messages
