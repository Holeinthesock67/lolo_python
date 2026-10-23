"""Contrôle (`verify`) et résumé (`info`) d'un dossier `.world` (format §10).

Contrôles : structure et manifeste, nombre de valeurs de chaque tableau de la route,
cohérence entre `length_m`, `n` et `ds_m`, accord manifeste / route, boucle fermée,
plages de valeurs ; terrain : taille des tuiles, présence des tuiles listées, égalité des
bords partagés, absence de NaN à moins de 25 m de la route.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

from . import constants as C
from .terrain import LEVELS, NEAR, TILE_BYTES, RouteAxis, read_tile, tile_coords, tile_filename

TILE_RE = re.compile(r"tile_(-?\d+)_(-?\d+)\.f32")
RANGES = {
    "lat": (-90.0, 90.0),
    "lon": (-180.0, 180.0),
    "grade_pct": (-C.GRADE_LIMIT_PCT, C.GRADE_LIMIT_PCT),
}


def _load(path: Path, problems: list[str]) -> dict | None:
    if not path.is_file():
        problems.append(f"{path.name} absent")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        problems.append(f"{path.name} illisible : {exc}")
        return None
    if not isinstance(data, dict):
        problems.append(f"{path.name} n'est pas un objet JSON")
        return None
    return data


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _check_manifest(m: dict, problems: list[str]) -> None:
    if m.get("format") != C.FORMAT_NAME:
        problems.append(f"manifest : format inattendu {m.get('format')!r}")
    version = str(m.get("format_version", ""))
    try:
        major = int(version.split(".")[0])
        if major > C.SUPPORTED_MAJOR:
            problems.append(f"manifest : format_version {version} trop récent")
    except ValueError:
        problems.append(f"manifest : format_version illisible {version!r}")
    if not isinstance(m.get("name"), str) or not m.get("name"):
        problems.append("manifest : name absent")
    origin = m.get("origin")
    if not isinstance(origin, dict) or not all(_is_number(origin.get(k)) for k in ("lat", "lon", "alt_m")):
        problems.append("manifest : origin incomplet (lat, lon, alt_m)")
    if not isinstance(m.get("projection"), str):
        problems.append("manifest : projection absente")
    route = m.get("route")
    if not isinstance(route, dict) or route.get("present") is not True:
        problems.append("manifest : couche route absente")


def _check_route(r: dict, mroute: dict, problems: list[str]) -> None:
    n, ds, length, kind = r.get("n"), r.get("ds_m"), r.get("length_m"), r.get("type")
    if not str(r.get("version", "")).startswith("1."):
        problems.append(f"route : version inattendue {r.get('version')!r}")
    if not (isinstance(n, int) and not isinstance(n, bool) and n >= 2):
        problems.append(f"route : n invalide {n!r}")
        return
    if not (_is_number(ds) and ds > 0 and _is_number(length) and length > 0):
        problems.append("route : ds_m ou length_m invalide")
        return
    if kind not in ("open", "loop", "out_and_back"):
        problems.append(f"route : type inconnu {kind!r}")
    for key in ("n", "ds_m", "length_m", "type"):
        if key in mroute and mroute[key] != r.get(key):
            problems.append(f"manifest et route.json en désaccord sur {key} ({mroute[key]!r} ≠ {r.get(key)!r})")

    last_regular = (n - 2) * ds
    if not last_regular < length <= last_regular + ds + 0.01:
        problems.append(f"route : length_m = {length} incohérent avec n = {n} et ds_m = {ds}")

    cols: dict[str, list] = {}
    for key in C.ROUTE_FIELDS + ("alt_raw_m",):
        col = r.get(key)
        if col is None and key == "alt_raw_m":
            continue
        if not isinstance(col, list):
            problems.append(f"route : tableau « {key} » absent")
            continue
        if len(col) != n:
            problems.append(f"route : « {key} » a {len(col)} valeurs au lieu de {n}")
        bad = sum(1 for v in col if not _is_number(v))
        if bad:
            problems.append(f"route : « {key} » contient {bad} valeur(s) non numérique(s)")
            continue
        cols[key] = col
        lo_hi = RANGES.get(key)
        if lo_hi and any(not lo_hi[0] <= v <= lo_hi[1] for v in col):
            problems.append(f"route : « {key} » sort de [{lo_hi[0]}, {lo_hi[1]}]")
    if "heading_deg" in cols and any(not 0.0 <= v < 360.0 for v in cols["heading_deg"]):
        problems.append("route : « heading_deg » sort de [0, 360)")

    if kind == "loop" and "x" in cols and "z" in cols and len(cols["x"]) == len(cols["z"]) == n:
        gap = math.hypot(cols["x"][-1] - cols["x"][0], cols["z"][-1] - cols["z"][0])
        if gap > 1.0:
            problems.append(f"route : boucle non fermée ({gap:.1f} m entre la fin et le départ)")
        if "alt_m" in cols and len(cols["alt_m"]) == n and abs(cols["alt_m"][-1] - cols["alt_m"][0]) > 0.01:
            problems.append("route : boucle dont l'altitude finale diffère de celle du départ")


def _check_terrain(world: Path, layers: dict, route: dict | None, problems: list[str]) -> None:
    """Tuiles de terrain : taille, présence des tuiles listées, bords partagés, pas de NaN près de la route."""
    terrain = layers.get("terrain") if isinstance(layers, dict) else None
    if not isinstance(terrain, dict) or not terrain.get("present"):
        return
    listed = terrain.get("tiles") if isinstance(terrain.get("tiles"), dict) else {}
    grids: dict[str, dict[tuple[int, int], np.ndarray]] = {}
    for level in LEVELS:
        level_grids: dict[tuple[int, int], np.ndarray] = {}
        folder = world / "terrain" / level.name
        for tile in sorted(folder.glob("tile_*.f32")):
            size = tile.stat().st_size
            if size != TILE_BYTES:
                problems.append(f"terrain : {level.name}/{tile.name} fait {size} octets au lieu de {TILE_BYTES}")
                continue
            m = TILE_RE.fullmatch(tile.name)
            if m:
                level_grids[(int(m.group(1)), int(m.group(2)))] = read_tile(tile)
        for entry in listed.get(level.name, []) or []:
            try:
                ix, iz = int(entry[0]), int(entry[1])
            except (TypeError, ValueError, IndexError):
                problems.append(f"terrain : entrée de tuile illisible {entry!r}")
                continue
            if not (folder / tile_filename(ix, iz)).is_file():
                problems.append(f"terrain : tuile listée absente {level.name}/{tile_filename(ix, iz)}")
        grids[level.name] = level_grids

        # Bords partagés : colonne 100 = colonne 0 de la voisine à l'est, ligne 100 = ligne 0 au sud.
        bad_edges = 0
        for (ix, iz), g in level_grids.items():
            east = level_grids.get((ix + 1, iz))
            if east is not None and g[:, -1].tobytes() != east[:, 0].tobytes():
                bad_edges += 1
            south = level_grids.get((ix, iz + 1))
            if south is not None and g[-1, :].tobytes() != south[0, :].tobytes():
                bad_edges += 1
        if bad_edges:
            problems.append(f"terrain : {bad_edges} bord(s) partagé(s) différent(s) au niveau {level.name}")

    # Pas de NaN à moins de BLEND_OUTER_M de l'axe de la route (niveau proche).
    if route is None or not grids.get(NEAR.name):
        return
    try:
        axis = RouteAxis(route["x"], route["z"], route["alt_m"])
    except (KeyError, TypeError, ValueError):
        return
    nan_samples = 0
    for (ix, iz), g in grids[NEAR.name].items():
        nan = np.isnan(g)
        if not nan.any():
            continue
        gx, gz = tile_coords(ix, iz, NEAR)
        dist, _ = axis.nearest(gx[nan], gz[nan], C.BLEND_OUTER_M)
        nan_samples += int(np.isfinite(dist).sum())
    if nan_samples:
        problems.append(f"terrain : {nan_samples} échantillon(s) NaN à moins de "
                        f"{C.BLEND_OUTER_M:.0f} m de la route")


def verify_world(world: Path) -> list[str]:
    """Liste des problèmes d'un `.world` ; liste vide si le parcours est valide."""
    world = Path(world)
    if not world.is_dir():
        return [f"dossier introuvable : {world}"]
    problems: list[str] = []
    manifest = _load(world / "manifest.json", problems)
    if manifest is None:
        return problems
    _check_manifest(manifest, problems)
    mroute = manifest.get("route") if isinstance(manifest.get("route"), dict) else {}
    route = _load(world / str(mroute.get("file", "route.json")), problems)
    if route is not None:
        before = len(problems)
        _check_route(route, mroute, problems)
        if len(problems) > before:
            route = None                      # route invalide : pas de contrôle de bande
    _check_terrain(world, manifest.get("layers", {}), route, problems)
    return problems


def world_info(world: Path) -> dict:
    """Résumé d'un `.world` valide : nom, longueur, type, pentes extrêmes, D+, points limités."""
    world = Path(world)
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    mroute = manifest.get("route", {})
    route = json.loads((world / mroute.get("file", "route.json")).read_text(encoding="utf-8"))
    alt = route["alt_m"]
    climb = sum(max(b - a, 0.0) for a, b in zip(alt, alt[1:]))
    return {
        "name": manifest.get("name"),
        "length_m": route["length_m"],
        "type": route["type"],
        "grade_max_pct": max(route["grade_pct"]),
        "grade_min_pct": min(route["grade_pct"]),
        "climb_m": round(climb, 1),
        "grade_clamped_points": mroute.get("grade_clamped_points", 0),
        "alt_source": mroute.get("alt_source", "gpx"),
        "terrain": manifest.get("layers", {}).get("terrain", {"present": False}),
    }
