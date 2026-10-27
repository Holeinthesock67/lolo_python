"""Packs de parcours (lot O15) : installation depuis un dossier ou une archive `.zip`, liste.

Un pack contient des traces (GPX, FIT, TCX et exports Garmin compressés, mêmes extensions que
`track_formats.TRACK_SUFFIXES`), leurs fiches `<trace>.toml` facultatives et un `pack.toml`
facultatif (`name`, `description`, `license`, `credits`). Tout est contrôlé avant la moindre
écriture (même forme que les packs de thèmes du lot N10) : chemins sûrs, pas de lien
symbolique, taille maximale, fiches valides, aucun autre fichier. Le pack est copié dans
`<gpx_dir>/<pack>/`, que le catalogue lit ; `build-all` compile ensuite ses traces.
"""

from __future__ import annotations

import shutil
import stat
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any

from .errors import CompileError
from .route_stats import LibraryError, load_library, sidecar_path
from .track_formats import track_stem
from .writer import normalize_name

MAX_PACK_BYTES = 200 * 1024 * 1024   # 200 Mo décompressés
MAX_PACK_FILES = 500
PACK_FILE = "pack.toml"
PACK_KEYS = {"name": 80, "description": 500, "license": 120, "credits": 200}


def _check_pack_meta(path: Path) -> dict[str, str]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CompileError(f"{PACK_FILE} invalide : {exc}") from exc
    unknown = sorted(set(data) - set(PACK_KEYS))
    if unknown:
        raise CompileError(f"{PACK_FILE} : clé(s) inconnue(s) : {', '.join(unknown)}")
    out = {}
    for key, limit in PACK_KEYS.items():
        if key in data:
            value = data[key]
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise CompileError(f"{PACK_FILE} : {key} : texte non vide de {limit} caractères au plus attendu")
            out[key] = value.strip()
    return out


def _extract_zip(zip_path: Path, target: Path) -> None:
    try:
        zf = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise CompileError(f"archive illisible : {zip_path.name} ({exc})") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_PACK_FILES:
            raise CompileError(f"archive : {MAX_PACK_FILES} fichiers au plus")
        total = 0
        for info in infos:
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/") or ":" in name.split("/")[0]:
                raise CompileError(f"chemin interdit dans l'archive : {info.filename!r}")
            mode = info.external_attr >> 16
            if mode and stat.S_ISLNK(mode):
                raise CompileError(f"lien symbolique interdit dans l'archive : {info.filename!r}")
            total += info.file_size
            if total > MAX_PACK_BYTES:
                raise CompileError(f"archive trop volumineuse : plus de {MAX_PACK_BYTES // 2**20} Mo")
        zf.extractall(target)


def _pack_root(folder: Path) -> Path:
    """Dossier qui porte les traces : la racine, ou son unique sous-dossier."""
    visible = [p for p in folder.iterdir() if not p.name.startswith(".") and p.name != "__MACOSX"]
    if len(visible) == 1 and visible[0].is_dir():
        return visible[0]
    return folder


def _check_content(root: Path) -> tuple[list[Path], dict[str, str]]:
    """Traces et fiches contrôlées ; erreur au premier fichier refusé."""
    tracks: list[Path] = []
    meta: dict[str, str] = {}
    seen: dict[str, str] = {}
    total = 0
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_symlink():
            raise CompileError(f"lien symbolique interdit dans le pack : {rel}")
        if p.is_dir():
            if any(part.startswith(".") or part == "__MACOSX" for part in p.relative_to(root).parts):
                continue
            raise CompileError(f"sous-dossier interdit dans le pack : {rel} (traces à plat attendues)")
        if any(part.startswith(".") or part == "__MACOSX" for part in p.relative_to(root).parts):
            continue
        total += p.stat().st_size
        if total > MAX_PACK_BYTES:
            raise CompileError(f"pack trop volumineux : plus de {MAX_PACK_BYTES // 2**20} Mo")
        if p.name == PACK_FILE:
            meta = _check_pack_meta(p)
            continue
        ts = track_stem(p.name)
        if ts is not None:
            norm = normalize_name(ts[0])
            if norm in seen:
                raise CompileError(f"deux traces pour le même parcours dans le pack : {seen[norm]} et {p.name}")
            seen[norm] = p.name
            tracks.append(p)
            continue
        if p.suffix.lower() != ".toml":
            raise CompileError(f"fichier non pris en charge dans le pack : {rel}")
    stems = {track_stem(t.name)[0] for t in tracks}
    for p in sorted(root.glob("*.toml")):
        if p.name == PACK_FILE:
            continue
        if p.stem not in stems:
            raise CompileError(f"fiche sans trace dans le pack : {p.name}")
        try:
            load_library(p)
        except LibraryError as exc:
            raise CompileError(f"fiche invalide : {exc}") from exc
    if not tracks:
        raise CompileError("le pack ne contient aucune trace (GPX, FIT, TCX)")
    return tracks, meta


def install_pack(source: Path, gpx_dir: Path, name: str | None = None,
                 force: bool = False) -> tuple[str, int, Path]:
    """Contrôle puis installe un pack ; renvoie son nom, son nombre de traces et son dossier."""
    source = Path(source)
    if not source.exists():
        raise CompileError(f"source introuvable : {source}")
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "pack"
        staging.mkdir()
        if source.is_file() and source.suffix.lower() == ".zip":
            _extract_zip(source, staging)
            root = _pack_root(staging)
        elif source.is_dir():
            if source.is_symlink():
                raise CompileError(f"lien symbolique refusé : {source}")
            root = source
        else:
            raise CompileError(f"source non prise en charge (dossier ou archive .zip attendu) : {source}")
        tracks, meta = _check_content(root)
        pack_id = normalize_name(name or meta.get("name") or (source.stem if source.is_file() else source.name))
        target = Path(gpx_dir) / pack_id
        if target.exists() and not force:
            raise CompileError(f"le pack {pack_id} est déjà installé (utiliser --force pour le remplacer)")
        tmp_target = Path(gpx_dir) / f".{pack_id}.install"
        if tmp_target.exists():
            shutil.rmtree(tmp_target)
        tmp_target.mkdir(parents=True)
        try:
            for t in tracks:
                shutil.copy2(t, tmp_target / t.name)
                side = sidecar_path(t, track_stem(t.name)[0])
                if side.is_file():
                    shutil.copy2(side, tmp_target / side.name)
            if (root / PACK_FILE).is_file():
                shutil.copy2(root / PACK_FILE, tmp_target / PACK_FILE)
        except OSError as exc:
            shutil.rmtree(tmp_target, ignore_errors=True)
            raise CompileError(f"installation du pack impossible : {exc}") from exc
        # Remplacement : l'ancien pack n'est effacé qu'une fois le nouveau en place.
        backup = Path(gpx_dir) / f".{pack_id}.old"
        if backup.exists():
            shutil.rmtree(backup)
        try:
            if target.exists():
                target.rename(backup)
            tmp_target.rename(target)
        except OSError as exc:
            if backup.exists() and not target.exists():
                backup.rename(target)
            shutil.rmtree(tmp_target, ignore_errors=True)
            raise CompileError(f"installation du pack impossible : {exc}") from exc
        shutil.rmtree(backup, ignore_errors=True)
    return pack_id, len(tracks), target


def list_packs(gpx_dir: Path) -> list[dict[str, Any]]:
    """Packs installés : sous-dossiers de `gpx_dir` avec leur `pack.toml` (s'il est lisible)."""
    out = []
    gpx_dir = Path(gpx_dir)
    if not gpx_dir.is_dir():
        return out
    for d in sorted(p for p in gpx_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
        info: dict[str, Any] = {"id": d.name,
                                "tracks": sum(1 for f in d.iterdir() if f.is_file() and track_stem(f.name))}
        if (d / PACK_FILE).is_file():
            try:
                info.update(_check_pack_meta(d / PACK_FILE))
            except CompileError as exc:
                info["error"] = str(exc)
        out.append(info)
    return out
