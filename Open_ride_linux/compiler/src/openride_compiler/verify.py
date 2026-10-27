"""Contrôle (`verify`) et résumé (`info`) d'un dossier `.world` (format §10).

Contrôles : structure et manifeste, nombre de valeurs de chaque tableau de la route,
cohérence entre `length_m`, `n` et `ds_m`, accord manifeste / route, boucle fermée,
plages de valeurs ; terrain : taille des tuiles, présence des tuiles listées, égalité des
bords partagés, absence de NaN à moins de 25 m de la route ; segments (format 1.3) : bornes
dans le parcours, identifiants uniques, types et catégories connus.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

from . import constants as C
from . import segments_layer as SEG
from .osm_layers import nearest_chunk_and_y, ring_centroid, signed_area
from .terrain import LEVELS, NEAR, TILE_BYTES, RouteAxis, read_tile, tile_coords, tile_filename

TILE_RE = re.compile(r"tile_(-?\d+)_(-?\d+)\.f32")
CHUNK_RE = re.compile(r"chunk_(\d+)\.json")
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


def _check_ring(ring: object, outer: bool, label: str, problems: list[str]) -> bool:
    if not isinstance(ring, list) or len(ring) < 3:
        problems.append(f"{label} : anneau de moins de 3 sommets")
        return False
    for pt in ring:
        if not isinstance(pt, list) or len(pt) != 2 or not (_is_number(pt[0]) and _is_number(pt[1])):
            problems.append(f"{label} : sommet invalide {pt!r}")
            return False
    if ring[0] == ring[-1]:
        problems.append(f"{label} : premier point répété à la fin de l'anneau")
        return False
    area = signed_area(ring)
    if outer and area <= 0:
        problems.append(f"{label} : anneau extérieur non antihoraire (aire = {area:.2f})")
        return False
    if not outer and area >= 0:
        problems.append(f"{label} : trou non horaire (aire = {area:.2f})")
        return False
    return True


def _check_buildings(world: Path, layers: dict, route: dict | None, problems: list[str]) -> None:
    b_layer = layers.get("buildings") if isinstance(layers, dict) else None
    if not isinstance(b_layer, dict) or not b_layer.get("present"):
        return
    folder = world / "buildings"
    if not folder.is_dir():
        problems.append("buildings : dossier absent")
        return
    axis = RouteAxis(route["x"], route["z"], route["alt_m"]) if route is not None else None
    for chunk_file in sorted(folder.glob("chunk_*.json")):
        m = CHUNK_RE.fullmatch(chunk_file.name)
        if not m:
            continue
        k = int(m.group(1))
        data = _load(chunk_file, problems)
        if data is None:
            continue
        if not str(data.get("version", "")).startswith("1."):
            problems.append(f"buildings/{chunk_file.name} : version inattendue {data.get('version')!r}")
        items = data.get("buildings")
        if not isinstance(items, list):
            problems.append(f"buildings/{chunk_file.name} : « buildings » n'est pas une liste")
            continue
        for item in items:
            if not isinstance(item, dict):
                problems.append(f"buildings/{chunk_file.name} : élément non objet")
                continue
            bid = item.get("id", "?")
            label = f"buildings/{chunk_file.name} ({bid})"
            if not isinstance(item.get("id"), str) or not item.get("id"):
                problems.append(f"{label} : id invalide")
            if not _is_number(item.get("base_y")):
                problems.append(f"{label} : base_y invalide")
            if not (_is_number(item.get("height_m")) and float(item["height_m"]) > 0):
                problems.append(f"{label} : height_m invalide")
            outer = item.get("outer")
            holes = item.get("holes")
            if not isinstance(holes, list):
                problems.append(f"{label} : holes n'est pas une liste")
                holes = []
            outer_ok = _check_ring(outer, True, label, problems)
            for h in holes:
                _check_ring(h, False, label, problems)
            if outer_ok and route is not None and axis is not None:
                cx, cz = ring_centroid(outer)
                expected_k, _ = nearest_chunk_and_y(cx, cz, route, axis, C.OSM_BAND_M)
                if expected_k != k:
                    problems.append(f"{label} : tronçon {k} incohérent avec la position (attendu {expected_k})")


def _check_vegetation(world: Path, layers: dict, route: dict | None, problems: list[str]) -> None:
    v_layer = layers.get("vegetation") if isinstance(layers, dict) else None
    if not isinstance(v_layer, dict) or not v_layer.get("present"):
        return
    folder = world / "vegetation"
    if not folder.is_dir():
        problems.append("vegetation : dossier absent")
        return
    axis = RouteAxis(route["x"], route["z"], route["alt_m"]) if route is not None else None
    for chunk_file in sorted(folder.glob("chunk_*.json")):
        m = CHUNK_RE.fullmatch(chunk_file.name)
        if not m:
            continue
        k = int(m.group(1))
        data = _load(chunk_file, problems)
        if data is None:
            continue
        if not str(data.get("version", "")).startswith("1."):
            problems.append(f"vegetation/{chunk_file.name} : version inattendue {data.get('version')!r}")
        items = data.get("areas")
        if not isinstance(items, list):
            problems.append(f"vegetation/{chunk_file.name} : « areas » n'est pas une liste")
            continue
        for item in items:
            if not isinstance(item, dict):
                problems.append(f"vegetation/{chunk_file.name} : élément non objet")
                continue
            vid = item.get("id", "?")
            label = f"vegetation/{chunk_file.name} ({vid})"
            if not isinstance(item.get("id"), str) or not item.get("id"):
                problems.append(f"{label} : id invalide")
            if item.get("kind") not in ("wood", "scrub", "orchard"):
                problems.append(f"{label} : kind inconnu {item.get('kind')!r}")
            density = item.get("density")
            if not (_is_number(density) and 0.0 < float(density) <= 1.0):
                problems.append(f"{label} : density invalide {density!r}")
            outer = item.get("outer")
            holes = item.get("holes")
            if not isinstance(holes, list):
                problems.append(f"{label} : holes n'est pas une liste")
                holes = []
            outer_ok = _check_ring(outer, True, label, problems)
            for h in holes:
                _check_ring(h, False, label, problems)
            if outer_ok and route is not None and axis is not None:
                cx, cz = ring_centroid(outer)
                expected_k, _ = nearest_chunk_and_y(cx, cz, route, axis, C.OSM_BAND_M)
                if expected_k != k:
                    problems.append(f"{label} : tronçon {k} incohérent avec la position (attendu {expected_k})")


def _check_poi(world: Path, layers: dict, route: dict | None, problems: list[str]) -> None:
    p_layer = layers.get("poi") if isinstance(layers, dict) else None
    if not isinstance(p_layer, dict) or not p_layer.get("present"):
        return
    folder = world / "poi"
    if not folder.is_dir():
        problems.append("poi : dossier absent")
        return
    axis = RouteAxis(route["x"], route["z"], route["alt_m"]) if route is not None else None
    for chunk_file in sorted(folder.glob("chunk_*.json")):
        m = CHUNK_RE.fullmatch(chunk_file.name)
        if not m:
            continue
        k = int(m.group(1))
        data = _load(chunk_file, problems)
        if data is None:
            continue
        if not str(data.get("version", "")).startswith("1."):
            problems.append(f"poi/{chunk_file.name} : version inattendue {data.get('version')!r}")
        items = data.get("points")
        if not isinstance(items, list):
            problems.append(f"poi/{chunk_file.name} : « points » n'est pas une liste")
            continue
        for item in items:
            if not isinstance(item, dict):
                problems.append(f"poi/{chunk_file.name} : élément non objet")
                continue
            pid = item.get("id", "?")
            label = f"poi/{chunk_file.name} ({pid})"
            if not isinstance(item.get("id"), str) or not item.get("id"):
                problems.append(f"{label} : id invalide")
            if item.get("kind") not in C.POI_KINDS:
                problems.append(f"{label} : kind inconnu {item.get('kind')!r}")
            x, y, z = item.get("x"), item.get("y"), item.get("z")
            if not (_is_number(x) and _is_number(y) and _is_number(z)):
                problems.append(f"{label} : coordonnées (x, y, z) invalides")
                continue
            if not (_is_number(item.get("radius_m")) and float(item["radius_m"]) > 0):
                problems.append(f"{label} : radius_m invalide")
            if route is not None and axis is not None:
                expected_k, _ = nearest_chunk_and_y(float(x), float(z), route, axis, C.OSM_BAND_M)
                if expected_k != k:
                    problems.append(f"{label} : tronçon {k} incohérent avec la position (attendu {expected_k})")


def _check_water(world: Path, layers: dict, route: dict | None, problems: list[str]) -> None:
    w_layer = layers.get("water") if isinstance(layers, dict) else None
    if not isinstance(w_layer, dict) or not w_layer.get("present"):
        return
    folder = world / "water"
    if not folder.is_dir():
        problems.append("water : dossier absent")
        return
    axis = RouteAxis(route["x"], route["z"], route["alt_m"]) if route is not None else None
    for chunk_file in sorted(folder.glob("chunk_*.json")):
        m = CHUNK_RE.fullmatch(chunk_file.name)
        if not m:
            continue
        k = int(m.group(1))
        data = _load(chunk_file, problems)
        if data is None:
            continue
        if not str(data.get("version", "")).startswith("1."):
            problems.append(f"water/{chunk_file.name} : version inattendue {data.get('version')!r}")
        lines = data.get("lines")
        areas = data.get("areas")
        if not isinstance(lines, list):
            problems.append(f"water/{chunk_file.name} : « lines » n'est pas une liste")
            lines = []
        if not isinstance(areas, list):
            problems.append(f"water/{chunk_file.name} : « areas » n'est pas une liste")
            areas = []
        for item in lines:
            if not isinstance(item, dict):
                problems.append(f"water/{chunk_file.name} : ligne non objet")
                continue
            lid = item.get("id", "?")
            label = f"water/{chunk_file.name} ({lid})"
            if not isinstance(item.get("id"), str) or not item.get("id"):
                problems.append(f"{label} : id invalide")
            if item.get("kind") not in C.WATER_LINE_KINDS:
                problems.append(f"{label} : kind de ligne inconnu {item.get('kind')!r}")
            if not (_is_number(item.get("width_m")) and float(item["width_m"]) > 0):
                problems.append(f"{label} : width_m invalide")
            pts = item.get("points")
            if not isinstance(pts, list) or len(pts) < 2:
                problems.append(f"{label} : points de ligne invalides")
                continue
            bad_pt = False
            for pt in pts:
                if not isinstance(pt, list) or len(pt) != 3 or not all(_is_number(v) for v in pt):
                    problems.append(f"{label} : point [x, z, y] invalide {pt!r}")
                    bad_pt = True
                    break
            if not bad_pt and route is not None and axis is not None:
                mx = sum(p[0] for p in pts) / len(pts)
                mz = sum(p[1] for p in pts) / len(pts)
                expected_k, _ = nearest_chunk_and_y(mx, mz, route, axis, C.OSM_BAND_M)
                if expected_k != k:
                    problems.append(f"{label} : tronçon {k} incohérent avec la position (attendu {expected_k})")
        for item in areas:
            if not isinstance(item, dict):
                problems.append(f"water/{chunk_file.name} : zone non objet")
                continue
            aid = item.get("id", "?")
            label = f"water/{chunk_file.name} ({aid})"
            if not isinstance(item.get("id"), str) or not item.get("id"):
                problems.append(f"{label} : id invalide")
            if item.get("kind") not in C.WATER_AREA_KINDS:
                problems.append(f"{label} : kind de zone inconnu {item.get('kind')!r}")
            if not _is_number(item.get("level_y")):
                problems.append(f"{label} : level_y invalide")
            outer = item.get("outer")
            holes = item.get("holes")
            if not isinstance(holes, list):
                problems.append(f"{label} : holes n'est pas une liste")
                holes = []
            outer_ok = _check_ring(outer, True, label, problems)
            for h in holes:
                _check_ring(h, False, label, problems)
            if outer_ok and route is not None and axis is not None:
                cx, cz = ring_centroid(outer)
                expected_k, _ = nearest_chunk_and_y(cx, cz, route, axis, C.OSM_BAND_M)
                if expected_k != k:
                    problems.append(f"{label} : tronçon {k} incohérent avec la position (attendu {expected_k})")


def _check_segments(world: Path, layers: dict, route: dict | None, problems: list[str]) -> None:
    """Couche segments (format 1.3, §8 bis) : bornes dans le parcours, identifiants uniques, types."""
    s_layer = layers.get("segments") if isinstance(layers, dict) else None
    if not isinstance(s_layer, dict) or not s_layer.get("present"):
        return
    data = _load(world / str(s_layer.get("file", SEG.LAYER_FILE)), problems)
    if data is None:
        return
    if not str(data.get("version", "")).startswith("1."):
        problems.append(f"segments : version inattendue {data.get('version')!r}")
    items = data.get("segments")
    if not isinstance(items, list):
        problems.append("segments : « segments » n'est pas une liste")
        return
    if len(items) > SEG.MAX_SEGMENTS:
        problems.append(f"segments : {len(items)} segments, au plus {SEG.MAX_SEGMENTS}")
    if s_layer.get("count") is not None and s_layer.get("count") != len(items):
        problems.append(f"segments : manifeste count = {s_layer.get('count')}, fichier : {len(items)}")
    length = float(route["length_m"]) if route is not None else None
    seen: set[str] = set()
    for k, item in enumerate(items, 1):
        if not isinstance(item, dict):
            problems.append(f"segments : élément {k} non objet")
            continue
        sid = item.get("id")
        label = f"segments ({sid if isinstance(sid, str) else k})"
        if not isinstance(sid, str) or not sid:
            problems.append(f"{label} : id invalide")
        elif sid in seen:
            problems.append(f"{label} : identifiant en double")
        else:
            seen.add(sid)
        kind = item.get("type")
        if kind not in SEG.TYPES:
            problems.append(f"{label} : type inconnu {kind!r}")
        cat = item.get("category")
        if kind == "climb" and cat not in SEG.CATEGORIES:
            problems.append(f"{label} : catégorie inconnue {cat!r}")
        if kind == "sprint" and cat is not None:
            problems.append(f"{label} : un sprint n'a pas de catégorie")
        if item.get("source") not in ("auto", "manual"):
            problems.append(f"{label} : source inconnue {item.get('source')!r}")
        s0, s1 = item.get("s_start"), item.get("s_end")
        if not (_is_number(s0) and _is_number(s1)):
            problems.append(f"{label} : s_start ou s_end invalide")
            continue
        if not float(s0) < float(s1):
            problems.append(f"{label} : s_start ({s0}) doit être inférieur à s_end ({s1})")
        if float(s0) < 0 or (length is not None and float(s1) > length + 0.1):
            problems.append(f"{label} : {s0}–{s1} m hors du parcours")


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
    layers = manifest.get("layers", {})
    _check_terrain(world, layers, route, problems)
    _check_buildings(world, layers, route, problems)
    _check_vegetation(world, layers, route, problems)
    _check_poi(world, layers, route, problems)
    _check_water(world, layers, route, problems)
    _check_segments(world, layers, route, problems)
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
        "segments": _segments_for_info(world, manifest),
    }


def _segments_for_info(world: Path, manifest: dict) -> list[dict] | None:
    """Segments de la couche, ou None si elle est absente."""
    s_layer = manifest.get("layers", {}).get("segments") or {}
    if not s_layer.get("present"):
        return None
    data = json.loads((world / s_layer.get("file", SEG.LAYER_FILE)).read_text(encoding="utf-8"))
    return data["segments"]
