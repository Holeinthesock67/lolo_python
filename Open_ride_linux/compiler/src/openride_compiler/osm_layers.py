"""Construction et écriture atomique des couches OSM `buildings` et `vegetation` (Lot I3, Format .world v1 §6 et §7)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from . import constants as C
from .elevation import ElevationProvider
from .frame import LocalFrame
from .terrain import NEAR, RouteAxis, read_tile, tile_filename

HEIGHT_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:m|meters|metres)?\s*$", re.IGNORECASE)


def signed_area(ring: list[list[float]]) -> float:
    """Aire algébrique 2D dans le plan (x, z) ; > 0 pour un contour extérieur antihoraire (§6, §7)."""
    m = len(ring)
    if m < 3:
        return 0.0
    acc = 0.0
    for i in range(m):
        x0, z0 = ring[i][0], ring[i][1]
        x1, z1 = ring[(i + 1) % m][0], ring[(i + 1) % m][1]
        acc += x0 * z1 - x1 * z0
    return 0.5 * acc


def _segments_intersect(
    a: list[float],
    b: list[float],
    c: list[float],
    d: list[float],
) -> bool:
    """Vrai si les segments [a, b] et [c, d] se croisent."""
    def ccw(p1: list[float], p2: list[float], p3: list[float]) -> float:
        return (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])

    d1 = ccw(a, b, c)
    d2 = ccw(a, b, d)
    d3 = ccw(c, d, a)
    d4 = ccw(c, d, b)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True
    return False


def is_self_intersecting(ring: list[list[float]]) -> bool:
    """Détecte une auto-intersection simple entre arêtes non adjacentes d'un anneau."""
    m = len(ring)
    if m < 4:
        return False
    for i in range(m):
        a, b = ring[i], ring[(i + 1) % m]
        for j in range(i + 2, m):
            if i == 0 and j == m - 1:
                continue
            c, d = ring[j], ring[(j + 1) % m]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def clean_and_orient_ring(pts_xz: list[list[float]], outer: bool = True) -> list[list[float]] | None:
    """Nettoie un anneau projeté (x, z), vérifie sa validité et l'oriente (outer: >0, hole: <0)."""
    if len(pts_xz) < 3:
        return None
    # Supprime les doublons consécutifs et le point de fermeture répété
    cleaned: list[list[float]] = []
    for pt in pts_xz:
        if not cleaned or math.hypot(pt[0] - cleaned[-1][0], pt[1] - cleaned[-1][1]) > 1e-3:
            cleaned.append([float(pt[0]), float(pt[1])])
    if len(cleaned) >= 2 and math.hypot(cleaned[0][0] - cleaned[-1][0], cleaned[0][1] - cleaned[-1][1]) <= 1e-3:
        cleaned.pop()

    if len(cleaned) < 3:
        return None

    area = signed_area(cleaned)
    if abs(area) < 0.5:
        return None
    if is_self_intersecting(cleaned):
        return None

    if outer and area < 0:
        cleaned.reverse()
    elif not outer and area > 0:
        cleaned.reverse()

    return [[round(p[0], 2), round(p[1], 2)] for p in cleaned]


def ring_centroid(ring: list[list[float]]) -> tuple[float, float]:
    xs = [p[0] for p in ring]
    zs = [p[1] for p in ring]
    return sum(xs) / len(xs), sum(zs) / len(zs)


def point_in_ring(x: float, z: float, ring: list[list[float]]) -> bool:
    inside = False
    m = len(ring)
    j = m - 1
    for i in range(m):
        xi, zi = ring[i][0], ring[i][1]
        xj, zj = ring[j][0], ring[j][1]
        if ((zi > z) != (zj > z)) and (x < (xj - xi) * (z - zi) / ((zj - zi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def compute_building_height(obj_id: str, tags: dict[str, Any]) -> float:
    """Hauteur d'un bâtiment (§6) : height, sinon building:levels * 3, sinon hachage stable dans [4, 10]."""
    raw_h = tags.get("height")
    if isinstance(raw_h, (int, float)) and raw_h > 0:
        return round(float(raw_h), 2)
    if isinstance(raw_h, str):
        m = HEIGHT_RE.match(raw_h)
        if m:
            val = float(m.group(1).replace(",", "."))
            if val > 0:
                return round(val, 2)

    raw_lv = tags.get("building:levels")
    if raw_lv is not None:
        try:
            lv = float(str(raw_lv).strip().replace(",", "."))
            if lv > 0:
                return round(lv * 3.0, 2)
        except ValueError:
            pass

    digest = hashlib.sha256(obj_id.encode("utf-8")).digest()
    u = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    return round(4.0 + u * 6.0, 2)


def _assemble_rings_latlon(segments: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Assemble des chemins (ways) bout à bout pour former des anneaux fermés (lat, lon)."""
    closed: list[list[tuple[float, float]]] = []
    open_segs: list[list[tuple[float, float]]] = []

    def same_pt(a: tuple[float, float], b: tuple[float, float]) -> bool:
        return abs(a[0] - b[0]) <= 1e-6 and abs(a[1] - b[1]) <= 1e-6

    for seg in segments:
        if len(seg) < 2:
            continue
        if len(seg) >= 4 and same_pt(seg[0], seg[-1]):
            closed.append(seg[:-1])
        else:
            open_segs.append(list(seg))

    while open_segs:
        curr = open_segs.pop(0)
        changed = True
        while changed and not same_pt(curr[0], curr[-1]):
            changed = False
            for idx, other in enumerate(open_segs):
                if same_pt(curr[-1], other[0]):
                    curr.extend(other[1:])
                    open_segs.pop(idx)
                    changed = True
                    break
                if same_pt(curr[-1], other[-1]):
                    curr.extend(reversed(other[:-1]))
                    open_segs.pop(idx)
                    changed = True
                    break
                if same_pt(curr[0], other[-1]):
                    curr = other[:-1] + curr
                    open_segs.pop(idx)
                    changed = True
                    break
                if same_pt(curr[0], other[0]):
                    curr = list(reversed(other[1:])) + curr
                    open_segs.pop(idx)
                    changed = True
                    break
        if len(curr) >= 4 and same_pt(curr[0], curr[-1]):
            closed.append(curr[:-1])

    return closed


def _project_ring(latlon_ring: list[tuple[float, float]], frame: LocalFrame, outer: bool) -> list[list[float]] | None:
    lats = np.array([p[0] for p in latlon_ring], dtype=float)
    lons = np.array([p[1] for p in latlon_ring], dtype=float)
    xs, zs = frame.to_xz(lats, lons)
    pts_xz = [[float(x), float(z)] for x, z in zip(xs, zs)]
    return clean_and_orient_ring(pts_xz, outer=outer)


def _extract_polygons(
    el: dict[str, Any],
    frame: LocalFrame,
) -> tuple[list[tuple[list[list[float]], list[list[list[float]]]]], int]:
    """Extrait les polygones (outer, holes) d'un élément Overpass (way ou relation).

    Renvoie (liste de (outer, holes), nombre de polygones dégénérés ignorés).
    """
    el_type = el.get("type")
    if el_type == "way":
        geom = el.get("geometry") or []
        if len(geom) < 4:
            return [], 1
        pts = [(float(p["lat"]), float(p["lon"])) for p in geom if "lat" in p and "lon" in p]
        if len(pts) < 4 or (abs(pts[0][0] - pts[-1][0]) > 1e-6 or abs(pts[0][1] - pts[-1][1]) > 1e-6):
            return [], 1
        ring = _project_ring(pts[:-1], frame, outer=True)
        if ring is None:
            return [], 1
        return [(ring, [])], 0

    if el_type == "relation":
        members = el.get("members") or []
        outer_segs: list[list[tuple[float, float]]] = []
        inner_segs: list[list[tuple[float, float]]] = []
        for m in members:
            if m.get("type") != "way":
                continue
            geom = m.get("geometry") or []
            pts = [(float(p["lat"]), float(p["lon"])) for p in geom if "lat" in p and "lon" in p]
            if len(pts) < 2:
                continue
            role = m.get("role", "outer") or "outer"
            if role == "inner":
                inner_segs.append(pts)
            elif role == "outer":
                outer_segs.append(pts)

        outer_latlons = _assemble_rings_latlon(outer_segs)
        inner_latlons = _assemble_rings_latlon(inner_segs)
        if not outer_latlons:
            return [], 1

        ignored = 0
        outers: list[list[list[float]]] = []
        for ol in outer_latlons:
            r = _project_ring(ol, frame, outer=True)
            if r is None:
                ignored += 1
            else:
                outers.append(r)

        holes: list[list[list[float]]] = []
        for il in inner_latlons:
            h = _project_ring(il, frame, outer=False)
            if h is None:
                ignored += 1
            else:
                holes.append(h)

        if not outers:
            return [], max(ignored, 1)

        if len(outers) == 1:
            return [(outers[0], holes)], ignored

        # Rattache chaque trou à l'anneau extérieur qui contient son premier sommet
        result: list[tuple[list[list[float]], list[list[list[float]]]]] = []
        for o in outers:
            my_holes = [h for h in holes if point_in_ring(h[0][0], h[0][1], o)]
            result.append((o, my_holes))
        return result, ignored

    return [], 0


def _sample_near_tiles_at(
    xs: np.ndarray,
    zs: np.ndarray,
    near_tiles: dict[tuple[int, int], np.ndarray],
) -> np.ndarray | None:
    """Interpolation bilinéaire sur les tuiles de terrain proche (maille 10 m, tuile 1000 m)."""
    if not near_tiles:
        return None
    out = np.full(len(xs), np.nan, dtype=float)
    tile_m = float(NEAR.tile_m)
    cell_m = float(NEAR.cell_m)
    max_idx = C.TILE_SAMPLES - 1

    for idx in range(len(xs)):
        x, z = float(xs[idx]), float(zs[idx])
        ix = math.floor(x / tile_m)
        iz = math.floor(z / tile_m)
        grid = near_tiles.get((ix, iz))
        if grid is None:
            return None
        u = (x - ix * tile_m) / cell_m
        v = (z - iz * tile_m) / cell_m
        i0 = min(max(int(math.floor(u)), 0), max_idx - 1)
        j0 = min(max(int(math.floor(v)), 0), max_idx - 1)
        du = min(max(u - i0, 0.0), 1.0)
        dv = min(max(v - j0, 0.0), 1.0)
        y00 = float(grid[j0, i0])
        y10 = float(grid[j0, i0 + 1])
        y01 = float(grid[j0 + 1, i0])
        y11 = float(grid[j0 + 1, i0 + 1])
        y = (
            (1.0 - du) * (1.0 - dv) * y00
            + du * (1.0 - dv) * y10
            + (1.0 - du) * dv * y01
            + du * dv * y11
        )
        out[idx] = y
    if np.isnan(out).any():
        return None
    return out


def compute_footprint_base_y(
    outer: list[list[float]],
    frame: LocalFrame,
    near_tiles: dict[tuple[int, int], np.ndarray] | None = None,
    provider: ElevationProvider | None = None,
    fallback_y: float = 0.0,
) -> float:
    """Minimum d'altitude du terrain sous l'empreinte du bâtiment (§6, critère 4)."""
    pts: list[tuple[float, float]] = [(p[0], p[1]) for p in outer]
    cx, cz = ring_centroid(outer)
    pts.append((cx, cz))

    # Ajoute des points intérieurs sur une grille de 5 m pour capter la pente sous l'empreinte
    xs_ring = [p[0] for p in outer]
    zs_ring = [p[1] for p in outer]
    x_min, x_max = min(xs_ring), max(xs_ring)
    z_min, z_max = min(zs_ring), max(zs_ring)
    if (x_max - x_min) <= 200.0 and (z_max - z_min) <= 200.0:
        gx = np.arange(x_min, x_max + 0.1, 5.0)
        gz = np.arange(z_min, z_max + 0.1, 5.0)
        for x in gx:
            for z in gz:
                if point_in_ring(float(x), float(z), outer):
                    pts.append((float(x), float(z)))

    px = np.array([p[0] for p in pts], dtype=float)
    pz = np.array([p[1] for p in pts], dtype=float)

    if near_tiles:
        ys = _sample_near_tiles_at(px, pz, near_tiles)
        if ys is not None and len(ys) > 0:
            return round(float(np.min(ys)), 2)

    if provider is not None:
        lats, lons = frame.to_latlon(px, pz)
        ys = np.asarray(provider.elevations(lats, lons), dtype=float)
        finite = ys[np.isfinite(ys)]
        if len(finite) > 0:
            return round(float(np.min(finite)), 2)

    return round(float(fallback_y), 2)


def nearest_chunk_and_y(
    cx: float,
    cz: float,
    route: dict[str, Any],
    axis: RouteAxis,
    max_dist_m: float = C.OSM_BAND_M,
) -> tuple[int | None, float]:
    """Renvoie (indice de tronçon k, altitude de la route) ou (None, nan) si à plus de max_dist_m."""
    dist, y_route = axis.nearest(np.array([cx]), np.array([cz]), max_dist_m)
    if not np.isfinite(dist[0]):
        return None, float("nan")
    _, idx = axis.tree.query([cx, cz])
    i = int(idx)
    n = int(route["n"])
    ds_m = float(route["ds_m"])
    length_m = float(route["length_m"])
    s = length_m if i >= n - 1 else i * ds_m
    k = int(s // C.CHUNK_LENGTH_M)
    return k, float(y_route[0])


def _vegetation_kind_and_density(tags: dict[str, Any]) -> tuple[str, float] | None:
    if tags.get("natural") == "wood" or tags.get("landuse") == "forest":
        return "wood", C.DENSITY_WOOD
    if tags.get("natural") == "scrub":
        return "scrub", C.DENSITY_SCRUB
    if tags.get("landuse") == "orchard":
        return "orchard", C.DENSITY_ORCHARD
    return None


@dataclass
class OsmLayersResult:
    buildings_chunks: dict[int, list[dict[str, Any]]]
    vegetation_chunks: dict[int, list[dict[str, Any]]]
    buildings_count: int
    buildings_ignored: int
    vegetation_count: int
    vegetation_ignored: int
    osm_date: str | None


def extract_osm_date(responses: list[dict[str, Any]]) -> str | None:
    dates: list[str] = []
    for resp in responses:
        osm3s = resp.get("osm3s")
        if isinstance(osm3s, dict):
            ts = osm3s.get("timestamp_osm_base") or osm3s.get("timestamp_areas_base")
            if isinstance(ts, str) and ts:
                dates.append(ts)
    return min(dates) if dates else None


def build_osm_layers(
    route: dict[str, Any],
    frame: LocalFrame,
    responses: list[dict[str, Any]],
    near_tiles: dict[tuple[int, int], np.ndarray] | None = None,
    provider: ElevationProvider | None = None,
) -> OsmLayersResult:
    """Construit les couches `buildings` et `vegetation` à partir des réponses Overpass."""
    axis = RouteAxis(route["x"], route["z"], route["alt_m"])
    buildings_chunks: dict[int, list[dict[str, Any]]] = {}
    vegetation_chunks: dict[int, list[dict[str, Any]]] = {}

    buildings_count = 0
    buildings_ignored = 0
    vegetation_count = 0
    vegetation_ignored = 0

    seen_ids: set[str] = set()
    prefix_map = {"node": "n", "way": "w", "relation": "r"}

    for resp in responses:
        for el in resp.get("elements") or []:
            el_type = str(el.get("type", ""))
            raw_id = el.get("id")
            if el_type not in ("way", "relation") or raw_id is None:
                continue
            obj_id = f"{prefix_map[el_type]}{raw_id}"
            if obj_id in seen_ids:
                continue
            seen_ids.add(obj_id)

            tags = el.get("tags") or {}
            if not isinstance(tags, dict):
                continue

            is_building = bool(tags.get("building") and tags.get("building") != "no")
            veg_info = _vegetation_kind_and_density(tags)
            if not is_building and veg_info is None:
                continue

            polys, deg_count = _extract_polygons(el, frame)
            if is_building:
                buildings_ignored += deg_count
            if veg_info is not None:
                vegetation_ignored += deg_count

            for poly_idx, (outer, holes) in enumerate(polys):
                item_id = obj_id if len(polys) == 1 else f"{obj_id}_{poly_idx}"
                cx, cz = ring_centroid(outer)
                k, y_route = nearest_chunk_and_y(cx, cz, route, axis, C.OSM_BAND_M)
                if k is None:
                    continue

                if is_building:
                    base_y = compute_footprint_base_y(outer, frame, near_tiles, provider, fallback_y=y_route)
                    height_m = compute_building_height(item_id, tags)
                    colour = tags.get("building:colour") or tags.get("colour")
                    b_obj = {
                        "id": item_id,
                        "outer": outer,
                        "holes": holes,
                        "base_y": base_y,
                        "height_m": height_m,
                        "roof": "flat",
                        "hint": {
                            "building": str(tags.get("building")),
                            "colour": str(colour) if colour is not None else None,
                        },
                    }
                    buildings_chunks.setdefault(k, []).append(b_obj)
                    buildings_count += 1

                if veg_info is not None:
                    kind, density = veg_info
                    v_obj = {
                        "id": item_id,
                        "kind": kind,
                        "outer": outer,
                        "holes": holes,
                        "density": density,
                    }
                    vegetation_chunks.setdefault(k, []).append(v_obj)
                    vegetation_count += 1

    return OsmLayersResult(
        buildings_chunks=buildings_chunks,
        vegetation_chunks=vegetation_chunks,
        buildings_count=buildings_count,
        buildings_ignored=buildings_ignored,
        vegetation_count=vegetation_count,
        vegetation_ignored=vegetation_ignored,
        osm_date=extract_osm_date(responses),
    )


def buildings_manifest(res: OsmLayersResult) -> dict[str, Any]:
    return {
        "present": True,
        "version": C.BUILDINGS_VERSION,
        "count": res.buildings_count,
        "ignored_count": res.buildings_ignored,
        "osm_date": res.osm_date,
    }


def vegetation_manifest(res: OsmLayersResult) -> dict[str, Any]:
    return {
        "present": True,
        "version": C.VEGETATION_VERSION,
        "source": "osm" if res.vegetation_count > 0 else "none",
        "count": res.vegetation_count,
        "ignored_count": res.vegetation_ignored,
        "osm_date": res.osm_date,
    }


def write_buildings_dir(folder: Path, chunks: dict[int, list[dict[str, Any]]]) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for k in sorted(chunks):
        payload = {"version": C.BUILDINGS_VERSION, "buildings": chunks[k]}
        (folder / f"chunk_{k}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def write_vegetation_dir(folder: Path, chunks: dict[int, list[dict[str, Any]]]) -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for k in sorted(chunks):
        payload = {"version": C.VEGETATION_VERSION, "areas": chunks[k]}
        (folder / f"chunk_{k}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def replace_layer_dir(
    world: Path,
    layer_name: str,
    writer_fn: Any,
    chunks: dict[int, list[dict[str, Any]]],
) -> None:
    """Remplace atomiquement `world/<layer_name>` sans toucher aux autres couches."""
    world = Path(world)
    final = world / layer_name
    tmp = world / f".{layer_name}.tmp-{os.getpid()}"
    old = world / f".{layer_name}.old-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        writer_fn(tmp, chunks)
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


def load_existing_near_tiles(world: Path) -> dict[tuple[int, int], np.ndarray]:
    """Charge les tuiles near existantes d'un .world pour calculer base_y lors d'un add-layer."""
    near_dir = Path(world) / "terrain" / NEAR.name
    if not near_dir.is_dir():
        return {}
    out: dict[tuple[int, int], np.ndarray] = {}
    tile_re = re.compile(r"tile_(-?\d+)_(-?\d+)\.f32")
    for p in sorted(near_dir.glob("tile_*.f32")):
        m = tile_re.fullmatch(p.name)
        if m:
            try:
                out[(int(m.group(1)), int(m.group(2)))] = read_tile(p)
            except Exception:
                continue
    return out
