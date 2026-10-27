"""Carrés de 1 km du monde ouvert (lot W7, `docs/2.0/PLAN_SERIE_W.md` §3.3 et §4).

Un carré est une case de la grille fixe de 1 km de la zone UTM : `IX = floor(E / 1000)`,
`IN = floor(N / 1000)`. Tout est calculé dans le **repère de zone** (`zone_frame`) : x = E, z = −N,
sans origine de séance, si bien qu'un carré est le même quelle que soit la séance qui le demande.
Une séance d'origine (E0, N0), multiples de 5 000 (W1 §4.2), lie sa tuile (ix, iz) au carré
`IX = E0/1000 + ix`, `IN = N0/1000 − iz − 1` : ses coordonnées s'en déduisent par une soustraction
exacte.

Contenu d'un carré (`genere/<zone>/<IX>_<IN>/`) :

- `near.f32` : 101 × 101 `float32` (format §5), échantillon (i, j) en E = 1000 IX + 10 i,
  N = 1000 (IN + 1) − 10 j ; relief fondu avec **toutes** les routes qui passent à moins de 50 m
  du carré (arêtes canoniques de W4, profils de W5), ponts et tunnels exceptés ;
- `buildings.json`, `vegetation.json`, `water.json`, `poi.json` : mêmes schémas que les
  `chunk_<k>.json`, coordonnées relatives au coin nord-ouest du carré (x − 1000 IX,
  z + 1000 (IN + 1)) ; un objet appartient au seul carré qui contient son centre ;
- `edges.json` : arêtes dont le premier nœud est dans le carré, avec leur profil, dans le repère
  de zone (pour la route engagée, W8) ;
- `meta.json` : versions (générateur, schéma et date de la base, relief) et nombres d'objets.

Le bord commun de deux carrés voisins est identique au bit près : mêmes coordonnées entières,
mêmes arêtes dans les deux marges (elles ne dépendent pas de l'emprise, W4), mêmes profils.
"""

from __future__ import annotations

import heapq
import json
import math
import os
import shutil
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.spatial import cKDTree

from .. import constants as C
from .. import osm_layers as L
from ..elevation import ElevationProvider
from ..frame import LocalFrame, utm_transformer
from ..terrain import blend
from .edge_profile import EdgeProfile, NodeAltitudes, edge_profile
from .graph import RoadGraph
from .osmdb import OsmDb
from .store import WorldCache

WORLDGEN_VERSION = 1
SQUARE_M = 1000
FAR_M = 5000
MARGIN_M = 50.0
NEAR_STEP_M = 10
FAR_STEP_M = 50
NARROW_CLASSES = ("c", "k")
NARROW_HALF_WIDTH_M = 2.0
AXIS_NEIGHBOURS = 8          # sommets candidats par échantillon (carrefours où se croisent plusieurs routes)
AREA_SEARCH_M = 1000.0       # une surface dont le centre est dans le carré peut déborder loin
WATER_STEP_M = 25.0
POI_KINDS = {"village": ("village", C.POI_RADIUS_VILLAGE_M), "hamlet": ("village", C.POI_RADIUS_VILLAGE_M),
             "town": ("village", C.POI_RADIUS_VILLAGE_M),
             "church_bell": ("church_bell", C.POI_RADIUS_CHURCH_BELL_M),
             "viewpoint": ("viewpoint", C.POI_RADIUS_VIEWPOINT_M)}
VEGETATION_DENSITY = {"wood": C.DENSITY_WOOD, "scrub": C.DENSITY_SCRUB, "orchard": C.DENSITY_ORCHARD}


# --- grille de la zone ------------------------------------------------------------------------

def zone_frame(zone: str) -> LocalFrame:
    """Repère de zone : UTM de la zone (« 31T »), sans translation (x = E, z = −N)."""
    number, band = int(zone[:-1]), zone[-1]
    south = band < "N"
    return LocalFrame(number, band, south, 0.0, 0.0, utm_transformer(number, south))


@dataclass(frozen=True, order=True)
class SquareKey:
    zone: str
    ix: int                  # IX = floor(E / 1000)
    i_n: int                 # IN = floor(N / 1000)

    size_m = SQUARE_M

    @classmethod
    def at(cls, zone: str, east: float, north: float) -> "SquareKey":
        return cls(zone, math.floor(east / cls.size_m), math.floor(north / cls.size_m))

    @classmethod
    def of_session_tile(cls, zone: str, e0: float, n0: float, ix: int, iz: int) -> "SquareKey":
        return cls(zone, *WorldCache.global_index(e0, n0, ix, iz, cls.size_m))

    @property
    def corner(self) -> tuple[int, int]:
        """Coin nord-ouest dans le repère de zone (x = E, z = −N) : origine des coordonnées relatives."""
        return self.ix * self.size_m, -(self.i_n + 1) * self.size_m

    @property
    def cache_key(self) -> str:
        return WorldCache.square_key(self.zone, self.ix, self.i_n)

    def contains(self, x: float, z: float) -> bool:
        x0, z0 = self.corner
        return x0 <= x < x0 + self.size_m and z0 <= z < z0 + self.size_m

    def center_en(self) -> tuple[float, float]:
        return (self.ix + 0.5) * self.size_m, (self.i_n + 0.5) * self.size_m


@dataclass(frozen=True, order=True)
class FarKey(SquareKey):
    """Tuile lointaine de 5 km : `IX5 = floor(E / 5000)`, `IN5 = floor(N / 5000)`."""

    size_m = FAR_M

    @property
    def cache_key(self) -> str:
        return WorldCache.far_key(self.zone, self.ix, self.i_n)


def grid_xz(key: SquareKey, step_m: int) -> tuple[np.ndarray, np.ndarray]:
    """Coordonnées de zone des 101 × 101 échantillons, tableau [ligne j, colonne i], en entiers exacts."""
    x0, z0 = key.corner
    k = np.arange(C.TILE_SAMPLES, dtype=np.int64) * step_m
    return np.meshgrid((x0 + k).astype(float), (z0 + k).astype(float))


def lonlat_bbox(frame: LocalFrame, x0: float, z0: float, x1: float, z1: float) -> tuple[float, float, float, float]:
    """Emprise géographique qui contient le rectangle de zone (coins et milieux des côtés)."""
    xs = np.array([x0, x1, x0, x1, (x0 + x1) / 2, (x0 + x1) / 2, x0, x1])
    zs = np.array([z0, z0, z1, z1, z0, z1, (z0 + z1) / 2, (z0 + z1) / 2])
    lat, lon = frame.to_latlon(xs, zs)
    return float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())


# --- axe formé par toutes les routes ------------------------------------------------------------

class RoadsAxis:
    """Distance au bord de chaussée le plus proche et altitude de la route à cet endroit.

    Comme `terrain.RouteAxis`, mais pour plusieurs polylignes (un segment ne relie que deux sommets
    d'une même polyligne) et une demi-largeur par polyligne. Renvoie `distance − demi-largeur`.
    """

    def __init__(self, pieces: list[tuple[np.ndarray, np.ndarray, np.ndarray, float]]) -> None:
        pieces = [p for p in pieces if len(p[0]) >= 2]
        self.n = sum(len(p[0]) for p in pieces)
        if not self.n:
            return
        self.x = np.concatenate([p[0] for p in pieces])
        self.z = np.concatenate([p[1] for p in pieces])
        self.alt = np.concatenate([p[2] for p in pieces])
        self.hw = np.concatenate([np.full(len(p[0]), p[3]) for p in pieces])
        piece = np.concatenate([np.full(len(p[0]), k) for k, p in enumerate(pieces)])
        self.seg_ok = np.append(piece[1:] == piece[:-1], False)          # segment (a, a + 1) valide
        self.max_hw = float(self.hw.max())
        self.tree = cKDTree(np.column_stack((self.x, self.z)))

    def nearest(self, px: np.ndarray, pz: np.ndarray, reach: float) -> tuple[np.ndarray, np.ndarray]:
        px, pz = np.asarray(px, float).ravel(), np.asarray(pz, float).ravel()
        dist = np.full(px.shape, np.inf)
        y = np.full(px.shape, np.nan)
        if not self.n:
            return dist, y
        k = min(AXIS_NEIGHBOURS, self.n)
        _, idx = self.tree.query(np.column_stack((px, pz)), k=k,
                                 distance_upper_bound=reach + self.max_hw + C.DS_M)
        idx = idx.reshape(len(px), k)
        for col in range(k):
            j = idx[:, col]
            ok = j < self.n
            if not ok.any():
                continue
            rows, jj = np.flatnonzero(ok), j[ok]
            for a in (jj - 1, jj):
                valid = (a >= 0) & self.seg_ok[np.clip(a, 0, self.n - 1)]
                if not valid.any():
                    continue
                r, aa = rows[valid], a[valid]
                d, yy = self._segment(px[r], pz[r], aa, aa + 1)
                d = d - self.hw[aa]
                better = d < dist[r]
                dist[r[better]] = d[better]
                y[r[better]] = yy[better]
        far = dist > reach
        dist[far], y[far] = np.inf, np.nan
        return dist, y

    def _segment(self, px, pz, a, b) -> tuple[np.ndarray, np.ndarray]:
        ax, az, bx, bz = self.x[a], self.z[a], self.x[b], self.z[b]
        vx, vz = bx - ax, bz - az
        ll = vx * vx + vz * vz
        with np.errstate(invalid="ignore", divide="ignore"):
            t = np.where(ll > 0, ((px - ax) * vx + (pz - az) * vz) / np.where(ll > 0, ll, 1.0), 0.0)
        t = np.clip(t, 0.0, 1.0)
        return np.hypot(px - (ax + t * vx), pz - (az + t * vz)), self.alt[a] + t * (self.alt[b] - self.alt[a])


def axis_pieces(profile: EdgeProfile, half_width: float, spans: Iterable) -> list:
    """Polylignes du profil hors ponts et tunnels (le relief n'est pas fondu sous un pont)."""
    keep = np.ones(len(profile.s), dtype=bool)
    for s0, s1, _kind in spans:
        keep &= ~((profile.s > s0) & (profile.s < s1))
    out, start = [], None
    for i, k in enumerate(np.append(keep, False)):
        if k and start is None:
            start = i
        elif not k and start is not None:
            sl = slice(start, i)
            out.append((profile.x[sl], profile.z[sl], profile.alt_m[sl], half_width))
            start = None
    return out


def half_width(road_class: str) -> float:
    return NARROW_HALF_WIDTH_M if road_class in NARROW_CLASSES else C.ROAD_HALF_WIDTH_M


# --- génération -------------------------------------------------------------------------------

def square_versions(db: OsmDb, provider: ElevationProvider) -> dict[str, Any]:
    return {"worldgen": WORLDGEN_VERSION, "osm_schema": db.meta.get("schema_version"),
            "osm_date": db.meta.get("osm_date") or None, "osm_region": db.meta.get("region"),
            "relief": getattr(provider, "name", "inconnu")}


def far_versions(provider: ElevationProvider) -> dict[str, Any]:
    return {"worldgen": WORLDGEN_VERSION, "relief": getattr(provider, "name", "inconnu")}


def square_edges(key: SquareKey, db: OsmDb, provider: ElevationProvider,
                 frame: LocalFrame | None = None) -> tuple[RoadGraph, dict[str, EdgeProfile]]:
    """Arêtes canoniques qui touchent le carré élargi de 50 m, et leur profil (repère de zone)."""
    frame = frame or zone_frame(key.zone)
    x0, z0 = key.corner
    bbox = lonlat_bbox(frame, x0 - MARGIN_M, z0 - MARGIN_M, x0 + key.size_m + MARGIN_M, z0 + key.size_m + MARGIN_M)
    graph = RoadGraph.build(db, bbox, frame)
    node_alt = NodeAltitudes(provider, frame)
    return graph, {k: edge_profile(graph.edges[k], provider, frame, node_alt) for k in sorted(graph.edges)}


def square_terrain(key: SquareKey, graph: RoadGraph, profiles: dict[str, EdgeProfile],
                   provider: ElevationProvider, frame: LocalFrame) -> np.ndarray:
    gx, gz = grid_xz(key, NEAR_STEP_M)
    lat, lon = frame.to_latlon(gx.ravel(), gz.ravel())
    y = np.asarray(provider.elevations(lat, lon), dtype=float)
    pieces = []
    for k in sorted(profiles):
        e = graph.edges[k]
        pieces += axis_pieces(profiles[k], half_width(e.road_class), e.spans)
    dist, y_road = RoadsAxis(pieces).nearest(gx.ravel(), gz.ravel(), C.BLEND_OUTER_M)
    y = blend(y, dist, y_road, half_width=0.0)
    return y.astype("<f4").reshape(C.TILE_SAMPLES, C.TILE_SAMPLES)


def _ring_xz(frame: LocalFrame, coords, outer: bool) -> list[list[float]] | None:
    if len(coords) < 3:
        return None
    lon = np.array([c[0] for c in coords], float)
    lat = np.array([c[1] for c in coords], float)
    xs, zs = frame.to_xz(lat, lon)
    return L.clean_and_orient_ring([[float(a), float(b)] for a, b in zip(xs, zs)], outer=outer)


def _rel(points, x0: float, z0: float) -> list[list[float]]:
    return [[round(p[0] - x0, 2), round(p[1] - z0, 2), *p[2:]] for p in points]


def square_layers(key: SquareKey, db: OsmDb, near: np.ndarray, provider: ElevationProvider,
                  frame: LocalFrame) -> dict[str, dict[str, Any]]:
    """Bâtiments, végétation, eau et points d'intérêt du carré, coordonnées relatives à son coin."""
    x0, z0 = key.corner
    near_tiles = {(key.ix, -(key.i_n + 1)): near}
    buildings: list[dict] = []
    vegetation: list[dict] = []
    water: dict[str, list[dict]] = {"lines": [], "areas": []}
    poi: list[dict] = []
    m = AREA_SEARCH_M
    for a in db.areas_in(lonlat_bbox(frame, x0 - m, z0 - m, x0 + key.size_m + m, z0 + key.size_m + m)):
        outer = _ring_xz(frame, a.outer, True)
        if outer is None:
            continue
        cx, cz = L.ring_centroid(outer)
        if not key.contains(cx, cz):
            continue
        holes = [h for h in (_ring_xz(frame, h, False) for h in a.holes) if h is not None]
        if a.kind == "building":
            colour = a.tags.get("colour")
            buildings.append({
                "id": a.osm_id, "outer": _rel(outer, x0, z0), "holes": [_rel(h, x0, z0) for h in holes],
                "base_y": L.compute_footprint_base_y(outer, frame, near_tiles, provider),
                "height_m": L.compute_building_height(a.osm_id, a.tags), "roof": "flat",
                "hint": {"building": str(a.tags.get("building")), "colour": colour}})
        elif a.kind in VEGETATION_DENSITY:
            vegetation.append({"id": a.osm_id, "kind": a.kind, "outer": _rel(outer, x0, z0),
                               "holes": [_rel(h, x0, z0) for h in holes], "density": VEGETATION_DENSITY[a.kind]})
        elif a.kind == "water":
            water["areas"].append({
                "id": a.osm_id, "kind": L.water_area_kind(a.tags) or "lake",
                "level_y": L.compute_contour_min_y(outer, frame, near_tiles, provider),
                "outer": _rel(outer, x0, z0), "holes": [_rel(h, x0, z0) for h in holes]})

    bbox = lonlat_bbox(frame, x0, z0, x0 + key.size_m, z0 + key.size_m)
    for line in db.lines_in(bbox):
        lon = np.array([c[0] for c in line.coords], float)
        lat = np.array([c[1] for c in line.coords], float)
        xs, zs = frame.to_xz(lat, lon)
        dense = L.densify_polyline_xz([(float(a), float(b)) for a, b in zip(xs, zs)], WATER_STEP_M)
        inside = [key.contains(x, z) for x, z in dense]
        pieces, cur = [], []
        for i, (x, z) in enumerate(dense):
            # un point dehors est gardé s'il touche un point dedans : pas de trou au bord du carré
            if inside[i] or (i > 0 and inside[i - 1]) or (i + 1 < len(dense) and inside[i + 1]):
                cur.append((x, z))
            elif cur:
                pieces.append(cur)
                cur = []
        if cur:
            pieces.append(cur)
        pieces = [p for p in pieces if len(p) >= 2]
        for n, pts in enumerate(pieces):
            px = np.array([p[0] for p in pts])
            pz = np.array([p[1] for p in pts])
            py = L.sample_terrain_y(px, pz, frame, near_tiles, provider)
            water["lines"].append({
                "id": line.osm_id if len(pieces) == 1 else f"{line.osm_id}_{n}", "kind": line.kind,
                "width_m": L.compute_water_width(line.kind, line.tags),
                "points": [[round(float(a) - x0, 2), round(float(b) - z0, 2), round(float(c), 2)]
                           for a, b, c in zip(px, pz, py)]})

    for p in db.points_in(bbox, kinds=POI_KINDS):
        x, z = (float(v[0]) for v in frame.to_xz(np.array([p.lat]), np.array([p.lon])))
        if not key.contains(x, z):
            continue
        kind, radius = POI_KINDS[p.kind]
        y = L.sample_terrain_y(np.array([x]), np.array([z]), frame, near_tiles, provider)
        poi.append({"id": p.osm_id, "kind": kind, "x": round(x - x0, 2), "y": round(float(y[0]), 2),
                    "z": round(z - z0, 2), "radius_m": radius, "name": p.name})

    return {
        "buildings": {"version": C.BUILDINGS_VERSION, "buildings": buildings},
        "vegetation": {"version": C.VEGETATION_VERSION, "areas": vegetation},
        "water": {"version": C.WATER_VERSION, **water},
        "poi": {"version": C.POI_VERSION, "points": poi},
    }


def _round(a: np.ndarray, digits: int) -> list[float]:
    return [round(float(v), digits) for v in a]


def edges_payload(key: SquareKey, graph: RoadGraph, profiles: dict[str, EdgeProfile]) -> dict[str, Any]:
    out = []
    for k in sorted(profiles):
        e, p = graph.edges[k], profiles[k]
        if not key.contains(*e.points[0]):
            continue
        out.append({
            "id": e.id, "raw_a": e.raw_a, "raw_b": e.raw_b, "road_class": e.road_class, "oneway": e.oneway,
            "name": e.name, "roundabout": e.roundabout, "length_m": round(e.length_m, 3), "spans": e.spans,
            "osm_nodes": e.osm_nodes,
            "profile": {"s": _round(p.s, 2), "x": _round(p.x, 2), "z": _round(p.z, 2), "alt_m": _round(p.alt_m, 2),
                        "grade_pct": _round(p.grade_pct, 2), "heading_deg": _round(p.heading_deg, 1),
                        "lat": _round(p.lat, 7), "lon": _round(p.lon, 7)}})
    return {"version": WORLDGEN_VERSION, "frame": "zone", "edges": out}


def _write_atomic(final: Path, files: dict[str, bytes]) -> None:
    """Écrit les fichiers dans un dossier temporaire voisin, puis le renomme à la place de `final`."""
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = final.parent / f".{final.name}.tmp-{os.getpid()}"
    old = final.parent / f".{final.name}.old-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        tmp.mkdir()
        for name, data in files.items():
            (tmp / name).write_bytes(data)
        if final.exists():
            final.rename(old)
            tmp.rename(final)
            shutil.rmtree(old, ignore_errors=True)
        else:
            tmp.rename(final)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def generate_square(key: SquareKey, db: OsmDb, provider: ElevationProvider, cache: WorldCache) -> Path:
    """Carré dans le cache ; rien n'est recalculé s'il y est déjà avec les mêmes versions."""
    versions = square_versions(db, provider)
    final = cache.square_dir(key.zone, key.ix, key.i_n)
    if cache.is_valid(key.cache_key, versions):
        cache.touch(key.cache_key)
        return final
    frame = zone_frame(key.zone)
    graph, profiles = square_edges(key, db, provider, frame)
    near = square_terrain(key, graph, profiles, provider, frame)
    layers = square_layers(key, db, near, provider, frame)
    counts = {"edges": len(profiles), "buildings": len(layers["buildings"]["buildings"]),
              "vegetation": len(layers["vegetation"]["areas"]), "water_lines": len(layers["water"]["lines"]),
              "water_areas": len(layers["water"]["areas"]), "poi": len(layers["poi"]["points"])}
    meta = {"zone": key.zone, "ix": key.ix, "in": key.i_n, "corner": list(key.corner), "versions": versions,
            "counts": counts}
    files = {"near.f32": np.ascontiguousarray(near, dtype="<f4").tobytes(),
             "edges.json": _json(edges_payload(key, graph, profiles)),
             "meta.json": _json(meta)}
    files.update({f"{name}.json": _json(payload) for name, payload in layers.items()})
    _write_atomic(final, files)
    cache.add(key.cache_key, "square", final, versions, region=db.meta.get("region") or None)
    return final


def generate_far(key: FarKey, provider: ElevationProvider, cache: WorldCache) -> Path:
    """Tuile lointaine de 5 km : 101 × 101 à 50 m, relief seul (niveau `far` du compilateur)."""
    versions = far_versions(provider)
    path = cache.far_path(key.zone, key.ix, key.i_n)
    if cache.is_valid(key.cache_key, versions):
        cache.touch(key.cache_key)
        return path
    frame = zone_frame(key.zone)
    gx, gz = grid_xz(key, FAR_STEP_M)
    lat, lon = frame.to_latlon(gx.ravel(), gz.ravel())
    y = np.asarray(provider.elevations(lat, lon), dtype=float).astype("<f4")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_bytes(y.tobytes())
    tmp.replace(path)
    cache.add(key.cache_key, "far", path, versions)
    return path


# --- file de priorités --------------------------------------------------------------------------

class SquareQueue:
    """Demandes de carrés, la plus urgente d'abord, sans doublon.

    Priorité : distance au cycliste le long de la route engagée (infinie hors de la route), puis
    distance à vol d'oiseau. Une nouvelle demande d'un carré déjà en file garde la meilleure
    priorité. `cancel_beyond` retire les demandes devenues lointaines. W8 exécute les demandes dans
    un `ProcessPoolExecutor` de `workers()` processus.
    """

    def __init__(self) -> None:
        self._heap: list[tuple[float, float, int, SquareKey]] = []
        self._prio: dict[SquareKey, tuple[float, float]] = {}
        self._seq = count()

    def __len__(self) -> int:
        return len(self._prio)

    def __contains__(self, key: SquareKey) -> bool:
        return key in self._prio

    def request(self, key: SquareKey, crow_m: float, route_m: float | None = None) -> bool:
        """Ajoute ou rend plus urgente une demande ; vrai si la file a changé."""
        prio = (math.inf if route_m is None else float(route_m), float(crow_m))
        old = self._prio.get(key)
        if old is not None and old <= prio:
            return False
        self._prio[key] = prio
        heapq.heappush(self._heap, (*prio, next(self._seq), key))
        return True

    def pop(self) -> SquareKey | None:
        while self._heap:
            r, c, _, key = heapq.heappop(self._heap)
            if self._prio.get(key) == (r, c):
                del self._prio[key]
                return key
        return None

    def discard(self, key: SquareKey) -> None:
        self._prio.pop(key, None)

    def cancel_beyond(self, max_crow_m: float) -> list[SquareKey]:
        """Retire les demandes hors de la route engagée et à plus de `max_crow_m` à vol d'oiseau."""
        gone = sorted(k for k, (r, c) in self._prio.items() if math.isinf(r) and c > max_crow_m)
        for k in gone:
            del self._prio[k]
        return gone

    @staticmethod
    def workers(cpus: int | None = None) -> int:
        return max(1, min(4, (cpus or os.cpu_count() or 2) - 1))
