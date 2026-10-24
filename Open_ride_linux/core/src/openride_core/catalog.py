"""Catalogue des parcours `.world` et des traces GPX (Lot I2, SRS §7 et §11).

Recense en lecture seule les parcours de ``routes_root`` et les traces de ``gpx_dir`` :
- ``ready`` : ``.world`` valide dont le GPX source est absent ou inchangé (même SHA-256) ;
- ``outdated`` : ``.world`` valide mais le GPX source a été modifié (SHA-256 différent) ;
- ``to_compile`` : fichier ``.gpx`` sans ``.world`` correspondant ;
- ``invalid`` : dossier ``.world`` illisible ou invalide selon ``load_world``.

Le parcours de démonstration ``demo`` figure toujours en première position.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import GPX_DIR, ROUTES_DIR
from .demo_world import DEMO_LENGTH_M, DEMO_NAME
from .route import WorldError, load_world


@dataclass(frozen=True)
class RouteEntry:
    id: str                      # nom du parcours (dossier sans « .world »), ou nom du GPX
    name: str
    status: str                  # "ready", "to_compile", "outdated", "invalid"
    length_m: float | None
    route_type: str | None       # open, loop, out_and_back
    has_terrain: bool
    gpx_path: Path | None
    error: str | None = None


def _normalize_name(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return name or "parcours"


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _peek_manifest_source(world_dir: Path) -> tuple[str | None, str | None]:
    """Lit source.gpx et source.gpx_sha256 dans manifest.json même si route.json est invalide."""
    try:
        data = json.loads((world_dir / "manifest.json").read_text(encoding="utf-8"))
        if isinstance(data, dict):
            src = data.get("source")
            if isinstance(src, dict):
                gpx_name = src.get("gpx")
                gpx_sha = src.get("gpx_sha256")
                return (
                    str(gpx_name) if isinstance(gpx_name, str) and gpx_name else None,
                    str(gpx_sha) if isinstance(gpx_sha, str) and gpx_sha else None,
                )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    return None, None


def list_routes(routes_root: Path = ROUTES_DIR, gpx_dir: Path = GPX_DIR) -> list[RouteEntry]:
    """Liste tous les parcours (.world et .gpx) avec leur statut, 'demo' toujours en premier."""
    routes_root = Path(routes_root)
    gpx_dir = Path(gpx_dir)

    # Indexe les fichiers GPX disponibles : nom de fichier -> (chemin, sha256, id normalisé)
    gpx_by_name: dict[str, tuple[Path, str, str]] = {}
    gpx_by_sha: dict[str, list[Path]] = {}
    gpx_by_norm_id: dict[str, Path] = {}

    if gpx_dir.is_dir():
        for gpx_file in sorted(p for p in gpx_dir.iterdir() if p.is_file() and p.suffix.lower() == ".gpx"):
            try:
                sha = _sha256_of(gpx_file)
            except OSError:
                continue
            norm_id = _normalize_name(gpx_file.stem)
            gpx_by_name[gpx_file.name] = (gpx_file, sha, norm_id)
            gpx_by_sha.setdefault(sha, []).append(gpx_file)
            gpx_by_norm_id.setdefault(norm_id, gpx_file)

    matched_gpx: set[Path] = set()
    world_entries: list[RouteEntry] = []
    demo_entry: RouteEntry | None = None

    if routes_root.is_dir():
        world_dirs = sorted(
            p for p in routes_root.iterdir()
            if p.is_dir() and p.name.endswith(".world") and not p.name.startswith(".")
        )
        for wdir in world_dirs:
            route_id = wdir.name[: -len(".world")]
            world = None
            err_msg: str | None = None
            try:
                world = load_world(wdir)
            except WorldError as exc:
                err_msg = str(exc)
                src_gpx_name, src_gpx_sha = _peek_manifest_source(wdir)
            else:
                src = world.manifest.get("source")
                if isinstance(src, dict):
                    gn, gs = src.get("gpx"), src.get("gpx_sha256")
                    src_gpx_name = str(gn) if isinstance(gn, str) and gn else None
                    src_gpx_sha = str(gs) if isinstance(gs, str) and gs else None
                else:
                    src_gpx_name, src_gpx_sha = None, None

            # Recherche du GPX correspondant par nom de source, puis par SHA-256, puis par identifiant normalisé
            matched_path: Path | None = None
            matched_sha: str | None = None
            if src_gpx_name and src_gpx_name in gpx_by_name:
                matched_path, matched_sha, _ = gpx_by_name[src_gpx_name]
            elif src_gpx_sha and src_gpx_sha in gpx_by_sha:
                matched_path = gpx_by_sha[src_gpx_sha][0]
                matched_sha = src_gpx_sha
            elif route_id in gpx_by_norm_id:
                cand = gpx_by_norm_id[route_id]
                matched_path = cand
                matched_sha = gpx_by_name[cand.name][1]

            if matched_path is not None:
                matched_gpx.add(matched_path)

            if world is None:
                entry = RouteEntry(
                    id=route_id,
                    name=route_id,
                    status="invalid",
                    length_m=None,
                    route_type=None,
                    has_terrain=False,
                    gpx_path=matched_path,
                    error=err_msg,
                )
            else:
                layers = world.manifest.get("layers") or {}
                terrain_layer = layers.get("terrain") if isinstance(layers, dict) else None
                has_terrain = bool(isinstance(terrain_layer, dict) and terrain_layer.get("present"))

                status = "ready"
                if matched_path is not None and src_gpx_sha is not None and matched_sha != src_gpx_sha:
                    status = "outdated"
                elif matched_path is not None and src_gpx_sha is None and route_id != DEMO_NAME:
                    status = "outdated"

                entry = RouteEntry(
                    id=route_id,
                    name=world.name,
                    status=status,
                    length_m=world.route.length_m,
                    route_type=world.route.type,
                    has_terrain=has_terrain,
                    gpx_path=matched_path,
                    error=None,
                )

            if route_id == DEMO_NAME:
                demo_entry = entry
            else:
                world_entries.append(entry)

    # Le parcours de démonstration est toujours listé en premier (sans écriture disque s'il est absent).
    if demo_entry is None:
        demo_entry = RouteEntry(
            id=DEMO_NAME,
            name=DEMO_NAME,
            status="ready",
            length_m=DEMO_LENGTH_M,
            route_type="open",
            has_terrain=False,
            gpx_path=None,
            error=None,
        )

    # GPX non encore compilés
    uncompiled_entries: list[RouteEntry] = []
    for gpx_path, _sha, norm_id in gpx_by_name.values():
        if gpx_path in matched_gpx:
            continue
        uncompiled_entries.append(
            RouteEntry(
                id=norm_id,
                name=gpx_path.stem,
                status="to_compile",
                length_m=None,
                route_type=None,
                has_terrain=False,
                gpx_path=gpx_path,
                error=None,
            )
        )

    other_entries = sorted(world_entries + uncompiled_entries, key=lambda e: (e.id, e.name))
    return [demo_entry, *other_entries]
