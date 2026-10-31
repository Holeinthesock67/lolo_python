"""Traces importées depuis le menu des parcours, compilées sans relancer (lot O23, contrat IPC révision 1.5).

Le core reste seul à écrire le dossier des traces : l'engine choisit un fichier dans la liste que le core lui
a donnée (`list_route_imports`, puis `import_route`). Même dossiers et même règles que l'import des
entraînements (`workout_menu.py`, lot N16).

- `import_candidates()` : traces (`catalog.TRACK_SUFFIXES` : GPX, FIT, TCX, archives Garmin) des dossiers
  habituels, sans sous-dossiers, les plus récentes d'abord (30 au plus).
- `copy_track()` : copie dans `~/OpenRide/GPX/` ; une trace identique déjà là n'est pas recopiée, une
  autre du même nom prend le suffixe `_2`, `_3`…
- `compile_command()` et `route_after_compile()` : la compilation tourne dans un processus à part
  (`openride-compiler build-all`, invariant A3), puis le catalogue dit si le parcours est prêt.

Module pur (fichiers seulement) : session.py le branche sur l'IPC.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from .catalog import TRACK_SUFFIXES, _normalize_name, _track_files, list_routes, track_stem
from .workout_menu import IMPORT_SOURCES, MAX_IMPORT_CANDIDATES

MAX_TRACK_BYTES = 50_000_000      # une archive Garmin de plusieurs heures reste bien en dessous
COMPILE_TIMEOUT_S = 600.0         # première compilation d'une région : relief et OSM téléchargés


class RouteImportError(Exception):
    """Refus d'un import : `code` est le code d'erreur IPC à renvoyer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _suffix(name: str) -> str | None:
    stem = track_stem(name)
    return None if stem is None else TRACK_SUFFIXES[stem[1]]


def _digest(path: Path) -> bytes:
    return hashlib.sha256(path.read_bytes()).digest()


def _tracks_in(gpx_dir: Path) -> list[Path]:
    """Traces du dossier et de ses packs (sous-dossiers directs), comme le catalogue."""
    return [f for f in _track_files(gpx_dir) if not f.name.startswith(".") and _suffix(f.name) is not None]


def import_candidates(home: Path, gpx_dir: Path) -> list[dict[str, Any]]:
    """Traces importables : [{path, file, source, imported}], les plus récentes d'abord."""
    found: list[tuple[float, dict[str, Any]]] = []
    seen: set[Path] = set()
    taken = {f.name.lower() for f in _tracks_in(gpx_dir)}
    for rel, label in IMPORT_SOURCES:
        directory = home / rel if rel else home
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for f in entries:
            if _suffix(f.name) is None or f in seen or not f.is_file():
                continue
            seen.add(f)
            found.append((f.stat().st_mtime, {"path": str(f), "file": f.name, "source": label,
                                               "imported": f.name.lower() in taken}))
    found.sort(key=lambda t: (-t[0], t[1]["file"]))
    return [item for _, item in found[:MAX_IMPORT_CANDIDATES]]


def copy_track(src: Path, gpx_dir: Path) -> dict[str, Any]:
    """Copie de `src` dans `gpx_dir` ; renvoie {path, file, created}."""
    suffix = _suffix(src.name)
    if suffix is None:
        raise RouteImportError("route_invalid", f"{src.name} : format inconnu (GPX, FIT, TCX ou archive Garmin)")
    try:
        if src.stat().st_size > MAX_TRACK_BYTES:
            raise RouteImportError("route_invalid", f"{src.name} : fichier trop gros")
        data = src.read_bytes()
    except OSError as exc:
        raise RouteImportError("route_invalid", f"{src.name} illisible : {exc}") from exc
    if not data:
        raise RouteImportError("route_invalid", f"{src.name} : fichier vide")
    digest = hashlib.sha256(data).digest()
    tracks = _tracks_in(gpx_dir)
    for f in tracks:
        if f.stat().st_size == len(data) and _digest(f) == digest:
            return {"path": str(f), "file": f.name, "created": False}
    # Identifiant du parcours = nom normalisé de la trace (catalog.py) : deux noms qui donnent le même
    # identifiant se feraient écarter l'un l'autre.
    taken = {_normalize_name(track_stem(f.name)[0]) for f in tracks}
    stem = src.name[: -len(suffix)]
    name, n = stem, 1
    while _normalize_name(name) in taken:
        n += 1
        name = f"{stem}_{n}"
    target = gpx_dir / f"{name}{suffix}"
    try:
        gpx_dir.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name("." + target.name + ".tmp")   # caché : le catalogue ne le voit pas
        tmp.write_bytes(data)
        os.replace(tmp, target)
    except OSError as exc:
        raise RouteImportError("route_invalid", f"écriture impossible : {exc}") from exc
    return {"path": str(target), "file": target.name, "created": True}


def compile_command(base: list[str], routes_dir: Path, gpx_dir: Path) -> list[str]:
    """`openride-compiler build-all` limité aux dossiers de la séance (compile aussi les autres traces en attente)."""
    return [*base, "--routes-dir", str(routes_dir), "--gpx-dir", str(gpx_dir)]


def route_for(track: Path, routes_dir: Path, gpx_dir: Path) -> Any:
    """Entrée du catalogue issue de la trace `track`, ou None."""
    for e in list_routes(routes_root=routes_dir, gpx_dir=gpx_dir):
        if e.gpx_path is not None and Path(e.gpx_path).resolve() == track.resolve():
            return e
    return None


def route_after_compile(track: Path, routes_dir: Path, gpx_dir: Path, compiler_output: str) -> dict[str, Any]:
    """Résultat de l'import une fois le compilateur fini : {route_id, name} ou RouteImportError."""
    e = route_for(track, routes_dir, gpx_dir)
    if e is not None and e.status == "ready":
        return {"route_id": e.id, "name": e.name}
    lines = [ln.strip() for ln in compiler_output.splitlines() if track.name in ln or "erreur" in ln.lower()]
    why = (e.error if e is not None and e.error else None) or (lines[-1] if lines else "compilation impossible")
    raise RouteImportError("route_invalid", f"{track.name} : {why}")
