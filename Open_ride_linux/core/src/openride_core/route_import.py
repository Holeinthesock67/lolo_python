"""Traces importées depuis le menu des parcours, compilées sans relancer OpenRide (lot O23).

Avant ce lot, ajouter un parcours demandait de déposer la trace dans `~/OpenRide/GPX/` à la main puis
de relancer OpenRide, qui la compilait au démarrage (lot N11). Comme pour les entraînements (lot N16),
le core propose les traces des dossiers habituels (`list_route_imports`), copie celle choisie
(`import_route`) et la compile dans un processus à part (invariant A3 : la boucle à 50 Hz n'attend
jamais le compilateur).

- `import_candidates()` : traces `.gpx`, `.fit`, `.tcx`, `.fit.gz`, `.tcx.gz` et `.zip` des mêmes
  dossiers que l'import d'entraînements, sans sous-dossiers, les plus récentes d'abord (30 au plus) ;
  `imported` est vrai si une trace identique (même SHA-256) est déjà dans le dossier des traces.
- `copy_track()` : copie dans le dossier des traces, jamais d'écrasement ; une trace identique déjà là
  n'est pas recopiée ; un nom déjà pris par une autre trace ou un parcours prend `_2`, `_3`…
- `compile_plan()` : ce qu'il reste à faire pour la trace copiée (rien, compiler, recompiler).
- `build_cmd()` : commande `openride-compiler build` de cette seule trace.

Module pur (fichiers seulement) : session.py lance la compilation et le branche sur l'IPC.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from .catalog import _normalize_name, list_routes, scan_tracks, track_stem
from .workout_menu import IMPORT_SOURCES, MAX_IMPORT_CANDIDATES

# Une trace d'une longue sortie fait quelques mégaoctets (FIT) à quelques dizaines (GPX bavard).
MAX_TRACK_BYTES = 64_000_000
# Délai maximal d'une compilation depuis le menu : la première dans une région télécharge l'altitude.
COMPILE_TIMEOUT_S = 900.0
# Début des messages d'erreur du compilateur (cli.py), retiré de la ligne d'état du menu.
COMPILER_ERROR_PREFIX = "openride-compiler : erreur : "


class RouteImportError(Exception):
    """Refus d'un import : `code` est le code d'erreur IPC à renvoyer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _known_tracks(gpx_dir: Path) -> dict[int, list[Path]]:
    """Traces du dossier (et de ses packs) rangées par taille : le SHA-256 n'est calculé qu'à taille égale."""
    by_size: dict[int, list[Path]] = {}
    tracks, conflicts = scan_tracks(gpx_dir)
    for p in tracks + [lost for lost, _ in conflicts]:
        try:
            by_size.setdefault(p.stat().st_size, []).append(p)
        except OSError:
            continue
    return by_size


def _same_track(src: Path, by_size: dict[int, list[Path]]) -> Path | None:
    """Trace déjà présente au contenu identique à `src`, sinon None."""
    try:
        same_size = by_size.get(src.stat().st_size, [])
        if not same_size:
            return None
        digest = _sha256(src)
        for p in same_size:
            if _sha256(p) == digest:
                return p
    except OSError:
        return None
    return None


def import_candidates(home: Path, gpx_dir: Path) -> list[dict[str, Any]]:
    """Traces importables : [{path, file, source, imported}], les plus récentes d'abord."""
    found: list[tuple[float, dict[str, Any]]] = []
    seen: set[Path] = set()
    for rel, label in IMPORT_SOURCES:
        directory = home / rel if rel else home
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for f in entries:
            if f in seen or track_stem(f.name) is None:
                continue
            try:
                if not f.is_file():
                    continue
                mtime = f.stat().st_mtime
            except OSError:
                continue
            seen.add(f)
            found.append((mtime, {"path": str(f), "file": f.name, "source": label}))
    found.sort(key=lambda t: (-t[0], t[1]["file"]))
    by_size = _known_tracks(gpx_dir)
    out = []
    for _, item in found[:MAX_IMPORT_CANDIDATES]:
        item["imported"] = _same_track(Path(item["path"]), by_size) is not None
        out.append(item)
    return out


def _ids_taken(gpx_dir: Path, routes_root: Path) -> set[str]:
    """Identifiants déjà pris : traces du dossier (et de ses packs) et parcours compilés."""
    tracks, conflicts = scan_tracks(gpx_dir)
    taken = {_normalize_name(track_stem(p.name)[0]) for p in tracks + [lost for lost, _ in conflicts]}
    if routes_root.is_dir():
        taken |= {p.name[: -len(".world")] for p in routes_root.iterdir() if p.name.endswith(".world")}
    return taken


def copy_track(src: Path, gpx_dir: Path, routes_root: Path) -> dict[str, Any]:
    """Copie `src` dans `gpx_dir` ; renvoie {path, file, created} (`created` faux : trace identique déjà là)."""
    ts = track_stem(src.name)
    if ts is None:
        raise RouteImportError("route_invalid", f"{src.name} : format inconnu (.gpx, .fit, .tcx, .zip)")
    stem = ts[0]
    suffix = src.name[len(stem):]
    try:
        size = src.stat().st_size
    except OSError as exc:
        raise RouteImportError("route_invalid", f"{src.name} illisible : {exc}") from exc
    if size > MAX_TRACK_BYTES:
        raise RouteImportError("route_invalid", f"{src.name} : fichier trop gros")
    if size == 0:
        raise RouteImportError("route_invalid", f"{src.name} : fichier vide")
    same = _same_track(src, _known_tracks(gpx_dir))
    if same is not None:
        return {"path": str(same), "file": same.name, "created": False}
    taken = _ids_taken(gpx_dir, routes_root)
    name, n = stem, 1
    while _normalize_name(name) in taken or (gpx_dir / f"{name}{suffix}").exists():
        n += 1
        name = f"{stem}_{n}"
    target = gpx_dir / f"{name}{suffix}"
    try:
        data = src.read_bytes()
        gpx_dir.mkdir(parents=True, exist_ok=True)
        tmp = gpx_dir / f".{target.name}.tmp"
        tmp.write_bytes(data)
        os.replace(tmp, target)
    except OSError as exc:
        raise RouteImportError("route_invalid", f"copie impossible : {exc}") from exc
    return {"path": str(target), "file": target.name, "created": True}


def route_entry(track: Path, gpx_dir: Path, routes_root: Path) -> Any:
    """Entrée du catalogue de la trace `track` (None si le catalogue ne la voit pas)."""
    norm = _normalize_name(track_stem(track.name)[0])
    entries = list_routes(routes_root=routes_root, gpx_dir=gpx_dir)
    for e in entries:
        if e.gpx_path is not None and Path(e.gpx_path) == track:
            return e
    for e in entries:
        if e.id == norm:
            return e
    return None


def compile_plan(track: Path, gpx_dir: Path, routes_root: Path) -> tuple[str, Any]:
    """(« ready », entrée) si rien à faire ; (« build » ou « rebuild », entrée ou None) sinon."""
    entry = route_entry(track, gpx_dir, routes_root)
    if entry is None or entry.status == "to_compile":
        return "build", entry
    if entry.status == "ready":
        return "ready", entry
    return "rebuild", entry   # modifiée depuis la compilation, ou parcours illisible


def compiler_prefix() -> list[str] | None:
    """Commande du compilateur, sans sous-commande ; None s'il n'est pas installé."""
    from .launch_compile import compiler_base_cmd

    return compiler_base_cmd()


def build_cmd(prefix: list[str], track: Path, routes_root: Path, force: bool) -> list[str]:
    """`openride-compiler build <trace> --out <parcours>` (`--force` : remplace un .world existant)."""
    cmd = [*prefix, "build", str(track), "--out", str(routes_root)]
    if force:
        cmd.append("--force")
    return cmd


def last_error_line(output: str) -> str:
    """Dernière ligne utile de la sortie du compilateur, pour la ligne d'état du menu."""
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line and not line.startswith("Traceback") and not line.startswith("File "):
            return line.removeprefix(COMPILER_ERROR_PREFIX)[:200]
    return "compilation refusée (voir le journal)"
