"""Manifeste et écriture atomique d'un dossier `.world` (format §2 et §11)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import __version__
from . import constants as C
from .errors import CompileError
from .pipeline import CompiledRoute
from .route_stats import compute_stats


def normalize_name(text: str) -> str:
    """Nom de parcours : minuscules et tirets ASCII (« Col du Galibier » → « col-du-galibier »)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return name or "parcours"


def build_manifest(name: str, compiled: CompiledRoute, gpx_name: str, gpx_sha256: str,
                   created: str | None = None, terrain: dict | None = None) -> dict:
    """Manifeste (format §2 et §11). `terrain` : bloc `layers.terrain` si la couche est produite.

    Il porte la fiche calculée du parcours (`stats`, lot O15, champ facultatif du format)."""
    route = compiled.route
    return {
        "format": C.FORMAT_NAME,
        "format_version": C.FORMAT_VERSION,
        "name": name,
        "created": created or datetime.now().astimezone().isoformat(timespec="seconds"),
        "compiler": {"name": C.COMPILER_NAME, "version": __version__},
        "source": {"gpx": gpx_name, "gpx_sha256": gpx_sha256},
        "origin": {"lat": route["lat"][0], "lon": route["lon"][0], "alt_m": route["alt_m"][0],
                   "utm_zone": compiled.utm_zone},
        "projection": "utm",
        "route": {"present": True, "version": C.ROUTE_VERSION, "file": "route.json",
                  "length_m": route["length_m"], "ds_m": route["ds_m"], "n": route["n"],
                  "type": route["type"], "grade_clamped_points": compiled.grade_clamped_points,
                  "alt_source": compiled.alt_source},
        "layers": {
            "terrain": terrain or {"present": False},
            "buildings": {"present": False},
            "vegetation": {"present": False, "source": "none"},
            "poi": {"present": False},
            "water": {"present": False},
        },
        "stats": compute_stats(route),
    }


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest_text(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, ensure_ascii=False)


def _write_files(folder: Path, manifest: dict, route: dict,
                 extra: Callable[[Path], None] | None = None) -> None:
    (folder / "route.json").write_text(json.dumps(route, separators=(",", ":")), encoding="utf-8")
    if extra is not None:
        extra(folder)
    (folder / "manifest.json").write_text(manifest_text(manifest), encoding="utf-8")


def replace_manifest(world: Path, manifest: dict) -> None:
    """Réécrit `manifest.json` de façon atomique (fichier temporaire puis os.replace)."""
    tmp = Path(world) / f".manifest.json.tmp-{os.getpid()}"
    try:
        tmp.write_text(manifest_text(manifest), encoding="utf-8")
        os.replace(tmp, Path(world) / "manifest.json")
    finally:
        tmp.unlink(missing_ok=True)


def write_world(out_dir: Path, name: str, manifest: dict, route: dict, force: bool = False,
                extra: Callable[[Path], None] | None = None) -> Path:
    """Écrit `<out_dir>/<name>.world` de façon atomique : dossier temporaire voisin puis renommage.

    Un dossier existant n'est remplacé qu'avec `force` ; sinon CompileError, sans rien toucher.
    `extra(dossier)` écrit les autres couches (terrain) dans le dossier temporaire.
    """
    out_dir = Path(out_dir)
    final = out_dir / f"{name}.world"
    if final.exists() and not force:
        raise CompileError(f"{final} existe déjà (utiliser --force pour le remplacer)")
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / f".{name}.world.tmp-{os.getpid()}"
    old = out_dir / f".{name}.world.old-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        tmp.mkdir()
        _write_files(tmp, manifest, route, extra)
        if final.exists():
            final.rename(old)
            try:
                tmp.rename(final)
            except BaseException:
                old.rename(final)
                raise
            shutil.rmtree(old, ignore_errors=True)
        else:
            tmp.rename(final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return final
