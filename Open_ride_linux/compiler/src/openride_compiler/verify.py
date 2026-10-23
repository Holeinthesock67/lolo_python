"""Contrôle (`verify`) et résumé (`info`) d'un dossier `.world` (format §10).

Contrôles : structure et manifeste, nombre de valeurs de chaque tableau de la route,
cohérence entre `length_m`, `n` et `ds_m`, accord manifeste / route, boucle fermée,
plages de valeurs, taille des tuiles de terrain présentes.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from . import constants as C

TILE_BYTES = 101 * 101 * 4
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


def _check_terrain(world: Path, layers: dict, problems: list[str]) -> None:
    terrain = layers.get("terrain") if isinstance(layers, dict) else None
    if not isinstance(terrain, dict) or not terrain.get("present"):
        return
    for level in ("near", "far"):
        for tile in sorted((world / "terrain" / level).glob("tile_*.f32")):
            size = tile.stat().st_size
            if size != TILE_BYTES:
                problems.append(f"terrain : {level}/{tile.name} fait {size} octets au lieu de {TILE_BYTES}")


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
        _check_route(route, mroute, problems)
    _check_terrain(world, manifest.get("layers", {}), problems)
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
    }
