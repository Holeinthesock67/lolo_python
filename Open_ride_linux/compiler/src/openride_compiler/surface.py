"""Surface de la route d'après OSM (lot U20, option « gravel », Format .world v1 §4, depuis 1.6).

- Requête Overpass des voies (`highway=*`) dans un couloir de 15 m autour de la trace, par tronçon de 1 km
  (paquets de 10 tronçons, même client et même cache que les couches OSM) ;
- pour chaque point de la route, la voie la plus proche à moins de 15 m dont le cap concorde (écart de moins
  de 30°, dans un sens ou dans l'autre) et qui passe à côté du point (pas au-delà de son bout) ; les voies
  sont échantillonnées tous les 2 m ;
- surface tirée de `surface`, sinon de `tracktype`, sinon `highway=track` → `gravel`, sinon `paved` ; un
  point sans voie concordante est `paved` ;
- lissage : une portion de moins de 50 m est rattachée à ses voisines (à la plus longue des deux quand elles
  diffèrent), jusqu'à ce qu'il n'en reste plus ;
- la colonne n'est écrite que si au moins un point n'est pas `paved` : une trace entièrement revêtue garde
  un `route.json` identique à celui d'avant U20.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.spatial import cKDTree

from . import constants as C
from .frame import LocalFrame
from .osm import CHUNKS_PER_PACKET, chunk_bboxes

SURFACES = C.SURFACES
CORRIDOR_M = 15.0
HEADING_TOL_DEG = 30.0
SAMPLE_M = 2.0
MIN_RUN_M = 50.0
_FROM_SURFACE = {
    "asphalt": "paved", "concrete": "paved", "paving_stones": "paved",
    "compacted": "compacted", "fine_gravel": "compacted",
    "gravel": "gravel", "pebblestone": "gravel",
    "dirt": "dirt", "ground": "dirt", "earth": "dirt", "grass": "dirt", "mud": "dirt", "sand": "dirt",
}
_FROM_TRACKTYPE = {"grade1": "paved", "grade2": "compacted", "grade3": "gravel", "grade4": "dirt", "grade5": "dirt"}


def way_surface(tags: dict[str, Any]) -> str:
    """Surface d'une voie OSM d'après `surface`, puis `tracktype`, puis `highway=track`, sinon `paved`."""
    s = _FROM_SURFACE.get(str(tags.get("surface", "")))
    if s is not None:
        return s
    t = _FROM_TRACKTYPE.get(str(tags.get("tracktype", "")))
    if t is not None:
        return t
    return "gravel" if tags.get("highway") == "track" else "paved"


def build_surface_query(bboxes: list[tuple[float, float, float, float]]) -> str:
    """Requête Overpass QL des voies d'un paquet de boîtes du couloir de 15 m."""
    parts = [f'  way["highway"]({s:.5f},{w:.5f},{n:.5f},{e:.5f});' for s, w, n, e in bboxes]
    return "[out:json][timeout:60];\n(\n" + "\n".join(parts) + "\n);\nout body geom;\n"


def fetch_ways(client: Any, route: dict[str, Any], frame: LocalFrame,
               chunks_per_packet: int = CHUNKS_PER_PACKET) -> list[dict[str, Any]]:
    """Voies `highway=*` du couloir de la route : éléments `way` avec `tags` et `geometry`."""
    bboxes = chunk_bboxes(route, frame, band_m=CORRIDOR_M)
    ways: dict[int, dict[str, Any]] = {}
    for i in range(0, len(bboxes), chunks_per_packet):
        resp = client.fetch_query(build_surface_query(bboxes[i:i + chunks_per_packet]))
        for el in resp.get("elements", []):
            if el.get("type") == "way" and "highway" in (el.get("tags") or {}) and el.get("geometry"):
                ways.setdefault(int(el.get("id", len(ways))), el)
    return [ways[k] for k in sorted(ways)]


def _samples(ways: list[dict[str, Any]], frame: LocalFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Points tous les 2 m le long des voies : positions (x, z), cap de leur segment (0–180°), direction
    unitaire du segment, surface."""
    pts: list[np.ndarray] = []
    caps: list[np.ndarray] = []
    dirs: list[np.ndarray] = []
    surf: list[str] = []
    for w in ways:
        geom = [g for g in w["geometry"] if isinstance(g, dict) and "lat" in g and "lon" in g]
        if len(geom) < 2:
            continue
        x, z = frame.to_xz(np.array([g["lat"] for g in geom], dtype=float), np.array([g["lon"] for g in geom], dtype=float))
        s = way_surface(w.get("tags") or {})
        for k in range(len(x) - 1):
            dx, dz = x[k + 1] - x[k], z[k + 1] - z[k]
            seg = math.hypot(dx, dz)
            if seg < 1e-6:
                continue
            m = max(1, int(math.ceil(seg / SAMPLE_M)))
            t = np.arange(m + 1) / m
            pts.append(np.column_stack([x[k] + dx * t, z[k] + dz * t]))
            caps.append(np.full(m + 1, math.degrees(math.atan2(dx, -dz)) % 180.0))
            dirs.append(np.tile([dx / seg, dz / seg], (m + 1, 1)))
            surf.extend([s] * (m + 1))
    if not pts:
        return np.zeros((0, 2)), np.zeros(0), np.zeros((0, 2)), []
    return np.vstack(pts), np.concatenate(caps), np.vstack(dirs), surf


def match_surface(route: dict[str, Any], ways: list[dict[str, Any]], frame: LocalFrame) -> list[str]:
    """Surface brute de chaque point : voie concordante la plus proche à moins de 15 m, sinon `paved`."""
    n = int(route["n"])
    out = ["paved"] * n
    xy, caps, dirs, surf = _samples(ways, frame)
    if not surf:
        return out
    tree = cKDTree(xy)
    rx = np.asarray(route["x"], dtype=float)
    rz = np.asarray(route["z"], dtype=float)
    heading = np.asarray(route["heading_deg"], dtype=float) % 180.0
    near = tree.query_ball_point(np.column_stack([rx, rz]), r=CORRIDOR_M)
    for i, cand in enumerate(near):
        best, best_d = None, math.inf
        for j in cand:
            diff = abs(caps[j] - heading[i]) % 180.0
            if min(diff, 180.0 - diff) >= HEADING_TOL_DEG:
                continue
            ox, oz = rx[i] - xy[j, 0], rz[i] - xy[j, 1]
            if abs(ox * dirs[j, 0] + oz * dirs[j, 1]) > SAMPLE_M:   # point au-delà du bout de la voie
                continue
            d = math.hypot(ox, oz)
            if d < best_d:
                best, best_d = j, d
        if best is not None:
            out[i] = surf[best]
    return out


def _runs(values: list[str]) -> list[list[Any]]:
    runs: list[list[Any]] = []
    for v in values:
        if runs and runs[-1][0] == v:
            runs[-1][1] += 1
        else:
            runs.append([v, 1])
    return runs


def smooth(values: list[str], ds_m: float, min_run_m: float = MIN_RUN_M) -> list[str]:
    """Rattache chaque portion de moins de `min_run_m` à ses voisines, la plus courte d'abord."""
    runs = _runs(values)
    while len(runs) > 1:
        short = [k for k, (_, cnt) in enumerate(runs) if cnt * ds_m < min_run_m]
        if not short:
            break
        k = min(short, key=lambda i: (runs[i][1], i))
        prev = runs[k - 1] if k > 0 else None
        nxt = runs[k + 1] if k + 1 < len(runs) else None
        target = prev if nxt is None or (prev is not None and prev[1] >= nxt[1]) else nxt
        target[1] += runs[k][1]
        del runs[k]
        merged: list[list[Any]] = []
        for v, cnt in runs:   # deux voisines de même surface se rejoignent
            if merged and merged[-1][0] == v:
                merged[-1][1] += cnt
            else:
                merged.append([v, cnt])
        runs = merged
    return [v for v, cnt in runs for _ in range(cnt)]


def route_surface(route: dict[str, Any], ways: list[dict[str, Any]], frame: LocalFrame) -> list[str] | None:
    """Colonne `surface` lissée, ou None si toute la route est `paved`."""
    values = smooth(match_surface(route, ways, frame), float(route["ds_m"]))
    return values if any(v != "paved" for v in values) else None


def apply_surface(route: dict[str, Any], manifest: dict[str, Any], client: Any, frame: LocalFrame) -> list[str] | None:
    """Cherche la surface, écrit la colonne et `route.surface_source` si un point n'est pas revêtu."""
    values = route_surface(route, fetch_ways(client, route, frame), frame)
    if values is None:
        return None
    route["surface"] = values
    manifest["route"]["surface_source"] = "osm"
    return values


def surface_summary(values: list[str] | None) -> str:
    if values is None:
        return "surface : tout revêtu (colonne omise)"
    n = len(values)
    parts = ", ".join(f"{s} {100.0 * values.count(s) / n:.0f} %" for s in SURFACES if s in values)
    return f"surface : {parts}"


__all__ = ["SURFACES", "CORRIDOR_M", "HEADING_TOL_DEG", "MIN_RUN_M", "way_surface", "build_surface_query",
           "fetch_ways", "match_surface", "smooth", "route_surface", "apply_surface", "surface_summary"]
