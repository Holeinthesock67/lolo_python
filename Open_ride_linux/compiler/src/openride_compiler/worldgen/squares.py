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
  du carré (arêtes canoniques de W4, profils de W5), ponts et tunnels exceptés ; abaissé sous les lacs,
  étangs et réservoirs qui touchent le carré (lot EA1, `water_terrain.py`) et sous les grandes rivières
  (lot EA3, `river_surface.py` : morceaux découpés au carré, niveau qui descend le long du cours),
  chaussée gardée ; puis réglé sur la route telle que l'engine la dessine (règle unique sol / route,
  `road_ground.py` : sol sous les chaussées à ciel ouvert, ponts compris, pas dans les tunnels ; pieds des talus
  appuyés hors ponts et tunnels) ;
- `buildings.json`, `vegetation.json`, `water.json`, `poi.json`, `coast.json` : mêmes schémas que
  les `chunk_<k>.json`, coordonnées relatives au coin nord-ouest du carré (x − 1000 IX,
  z + 1000 (IN + 1)) ; un objet appartient au seul carré qui contient son centre, sauf la mer et
  la côte, découpées au carré (lot W23, `square_coast.py`) ;
- `bridges.json` (lot EA4) et `tunnels.json` (lot EA5) : ponts et tunnels des arêtes, rangés dans le carré du
  milieu de leur portion ; la colline reste au-dessus d'un tunnel (ni fondu ni entaille), l'engine ne dessine pas
  le terrain dans le tube ;
- plus d'`edges.json` (revue de code K2-08, lot RC23) : profil de chaque arête à 7 décimales, sans lecteur (la
  route engagée recalcule ses profils) ; place perdue sous le plafond et coordonnées précises écrites sans usage ;
- `meta.json` : versions (générateur, schéma et date de la base, relief) et nombres d'objets.

Le bord commun de deux carrés voisins est identique au bit près : mêmes coordonnées entières,
mêmes arêtes dans les deux marges (elles ne dépendent pas de l'emprise, W4), mêmes profils.
"""

from __future__ import annotations

import heapq
import json
import math
import os
import re
import shutil
import threading
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.spatial import cKDTree

from .. import constants as C
from .. import osm_layers as L
from ..elevation import ElevationProvider
from ..errors import CompileError
from ..frame import LocalFrame, utm_transformer
from ..terrain import blend
from .. import river_surface as RS
from .. import road_ground as RG
from .. import water_terrain as WT
from .edge_profile import EdgeProfile, NodeAltitudes, edge_profile, with_turnaround
from .graph import RoadGraph
from .osmdb import OsmDb, WATERWAY_KINDS
from .square_coast import COAST_SQUARE_VERSION, square_coast
from .store import WorldCache

# 2 : niveau des lacs et sol abaissé sous l'eau (lot EA1) ; 3 : ponts dessinés (EA4) ; 4 : grandes rivières (EA3) ;
# 5 (20/11) : garde-fou de la chaussée (#936), ponts compris, sur la largeur du ruban de l'engine ; 8 (21/11) : règle
# unique sol / route (road_ground.py : route de l'engine, talus appuyés). Un même numéro pour
# deux contenus différents garderait un carré périmé en cache : à chaque fusion, garder un numéro plus grand que tous
# ceux déjà dans main. Carrés recalculés. 6 (EA5) jamais fusionné ; 7 (20/11) : fond des lacs fondu avec la route (rive en
# pente douce au lieu d'une chute de 7 m sous la chaussée) ; 9 (21/11) : garde-fou d'altitude du profil des arêtes
# (altitude_guard.py : trous et pics du relief, pente et changement de pente bornés, pente des nœuds) ; 10 (22/11) :
# tunnels dessinés (lot EA5, couche `tunnels` du carré) ; 11 (26/11) : relief sol nu, IGN RGE ALTI en France puis
# FABDEM ailleurs, Copernicus en secours (lots RL1 et RL2) ; 12 (27/11) : niveau des rivières borné aux nœuds, carré sur
# une grande île de rivière sans eau (RC26, K3-02, K3-03).
WORLDGEN_VERSION = 12
# Règle sol / route du carré (road_ground.fit) en SQUARE_ROUNDS paires de passes ; chaque passe ne lit que le relief à
# deux cases d'un sommet : relief proche calculé avec RING_CELLS cases de plus tout autour, bords communs identiques.
# Marges du carré (21/11) : la balade, rééchantillonnée tous les 10 m sur ses arêtes, s'écarte de quelques cm de la
# route de l'arête ; le carré dégage donc un peu plus large et un peu plus bas, la séance réglant ensuite le sol sur sa
# propre route (session_ground.py) tant que l'engine n'a pas la tuile.
SQUARE_ROUNDS = 3
RING_CELLS = 4 * SQUARE_ROUNDS + 1
SQUARE_WIDTH_MARGIN_M = 0.25
SQUARE_SINK_MARGIN_M = 0.03
FAR_WATER_VERSION = 1         # eau des tuiles lointaines (lot EA2)
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
FAR_LAKE_MIN_M2 = 1_000_000.0   # lot EA2 : lacs dessinés au loin, plus de 1 km² (tous morceaux réunis)
FAR_LAKE_SEARCH_M = 2000.0      # morceaux cherchés autour de la tuile lointaine pour réunir un lac coupé
FAR_LAKE_JOIN_M = 5.0           # deux morceaux d'un lac coupé par les tuiles vectorielles se touchent à moins de 5 m
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


def grid_xz(key: SquareKey, step_m: int, ring: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Coordonnées de zone des 101 × 101 échantillons, tableau [ligne j, colonne i], en entiers exacts ;
    `ring` cases de plus tout autour (garde-fou de la chaussée)."""
    x0, z0 = key.corner
    k = np.arange(-ring, C.TILE_SAMPLES + ring, dtype=np.int64) * step_m
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

def square_versions(db: OsmDb, provider: ElevationProvider, tiles_complete: bool = True) -> dict[str, Any]:
    """Versions d'un carré. `tiles_complete` faux (revue de code K1-04, lot RC23) : des tuiles vectorielles de
    l'emprise manquaient (coupure, 429, 503) ; le carré porte `"tiles": "partial"`, qu'une séance suivante, qui attend
    un carré complet (sans la clé, donc sans changer les versions des carrés complets déjà en cache), refait."""
    out = {"worldgen": WORLDGEN_VERSION, "osm_schema": db.meta.get("schema_version"),
           "osm_date": db.meta.get("osm_date") or None, "osm_region": db.meta.get("region"),
           "relief": getattr(provider, "name", "inconnu"),
           "coast": COAST_SQUARE_VERSION if db.has_coast else None}   # lot W23 : carré refait avec la mer
    if not tiles_complete:
        out["tiles"] = "partial"
    return out


def square_bbox(key: SquareKey, frame: LocalFrame | None = None) -> tuple[float, float, float, float]:
    """Emprise (lon, lat) des arêtes d'un carré, élargie de MARGIN_M (`square_edges`)."""
    frame = frame or zone_frame(key.zone)
    x0, z0 = key.corner
    return lonlat_bbox(frame, x0 - MARGIN_M, z0 - MARGIN_M, x0 + key.size_m + MARGIN_M, z0 + key.size_m + MARGIN_M)


def far_versions(provider: ElevationProvider, db: OsmDb | None = None,
                 water_complete: bool = True) -> dict[str, Any]:
    """Versions d'une tuile lointaine ; avec une base OSM, l'eau lointaine (lot EA2) en fait partie.

    `water_complete` faux (tuiles vectorielles absentes) : la tuile est écrite, mais une séance suivante
    qui attend `"water": "ok"` la refait.
    """
    out = {"worldgen": WORLDGEN_VERSION, "relief": getattr(provider, "name", "inconnu")}
    if db is not None:
        out.update({"far_water": FAR_WATER_VERSION, "osm_schema": db.meta.get("schema_version"),
                    "osm_date": db.meta.get("osm_date") or None, "osm_region": db.meta.get("region"),
                    "water": "ok" if water_complete else "partial"})
    return out


def square_edges(key: SquareKey, db: OsmDb, provider: ElevationProvider,
                 frame: LocalFrame | None = None) -> tuple[RoadGraph, dict[str, EdgeProfile]]:
    """Arêtes canoniques qui touchent le carré élargi de 50 m, et leur profil (repère de zone).

    Les arêtes sans longueur n'ont pas de profil : ni terrain, ni liste d'arêtes.
    """
    frame = frame or zone_frame(key.zone)
    graph = RoadGraph.build(db, square_bbox(key, frame), frame)
    node_alt = NodeAltitudes(provider, frame)
    return graph, {k: edge_profile(graph.edges[k], provider, frame, node_alt) for k in sorted(graph.edges)
                   if not graph.edges[k].degenerate}


def square_water(key: SquareKey, db: OsmDb, provider: ElevationProvider, frame: LocalFrame) -> list[dict]:
    """Plans d'eau à moins de `AREA_SEARCH_M` du carré, repère de zone, avec leur niveau (lot EA1).

    Sert au sol abaissé (toute aire qui touche le carré) et à la couche eau (aire dont le centre est
    dans le carré). Le niveau ne dépend que du polygone et du MNT : deux carrés voisins, ou deux morceaux
    d'un lac coupé par les tuiles vectorielles, trouvent le même.
    """
    x0, z0 = key.corner
    m = AREA_SEARCH_M

    def height(xs, zs):
        return L.sample_terrain_y(xs, zs, frame, None, provider)
    out = []
    rivers = []
    for a in db.areas_in(lonlat_bbox(frame, x0 - m, z0 - m, x0 + key.size_m + m, z0 + key.size_m + m),
                         kinds=("water", "river")):
        outer = _ring_xz(frame, a.outer, True)
        if outer is None:
            continue
        holes = [h for h in (_ring_xz(frame, h, False) for h in a.holes) if h is not None]
        if a.kind == "river":   # lot EA3 : niveau en chaque point
            # découpée à la fenêtre du carré élargie du rayon du niveau : dedans, mêmes points d'eau que le
            # polygone entier (une rivière peut faire des dizaines de kilomètres)
            r = C.RIVER_LEVEL_RADIUS_M + 2 * C.RIVER_SAMPLE_M
            for po, ph in RS.clip_to_rect(outer, holes, x0 - r, z0 - r, x0 + key.size_m + r, z0 + key.size_m + r):
                rivers.append({"id": a.osm_id, "kind": "river", "outer": po, "holes": ph})
            continue
        level = WT.lake_level(outer, holes, height)
        out.append({"id": a.osm_id, "kind": L.water_area_kind(a.tags) or "lake",
                    "level_y": round(0.0 if level is None else level, 2), "outer": outer, "holes": holes,
                    "centroid": L.ring_centroid(outer)})
    if rivers:
        levels = RS.RiverLevels([(a["outer"], a["holes"]) for a in rivers], height)
        for a in rivers:
            a["levels"] = levels
        out += rivers
    return out


def ring_area(ring) -> float:
    """Aire (m²) d'un anneau, formule du lacet, valeur absolue."""
    r = np.asarray([[float(p[0]), float(p[1])] for p in ring], dtype=float)
    if len(r) < 3:
        return 0.0
    x, z = r[:, 0], r[:, 1]
    return float(abs(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1))) / 2.0)


def far_lakes(key: "FarKey", db: OsmDb, provider: ElevationProvider, frame: LocalFrame) -> list[dict]:
    """Grands lacs (lot EA2) qui touchent la tuile lointaine, repère de zone, avec leur niveau (règle EA1).

    Un lac compte s'il dépasse `FAR_LAKE_MIN_M2`, ses morceaux réunis : les tuiles vectorielles coupent un
    lac en morceaux qui se touchent au bord des tuiles (sommets à moins de `FAR_LAKE_JOIN_M`) ; ils sont
    cherchés jusqu'à `FAR_LAKE_SEARCH_M` autour de la tuile. Lacs, étangs, réservoirs : pas la mer.
    Le niveau de chaque morceau est celui des carrés proches (`lake_level`, même polygone, même MNT).
    """
    x0, z0 = key.corner
    m = FAR_LAKE_SEARCH_M
    pieces = []
    for a in db.areas_in(lonlat_bbox(frame, x0 - m, z0 - m, x0 + key.size_m + m, z0 + key.size_m + m),
                         kinds=("water",)):
        kind = L.water_area_kind(a.tags) or "lake"
        if kind not in C.INLAND_WATER_KINDS:
            continue
        outer = _ring_xz(frame, a.outer, True)
        if outer is None:
            continue
        holes = [h for h in (_ring_xz(frame, h, False) for h in a.holes) if h is not None]
        area = max(0.0, ring_area(outer) - sum(ring_area(h) for h in holes))
        pieces.append({"id": a.osm_id, "kind": kind, "outer": outer, "holes": holes, "area": area})
    if not pieces:
        return []
    # morceaux qui se touchent : union-find sur les sommets proches des contours
    parent = list(range(len(pieces)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    pts = np.array([p[:2] for pc in pieces for p in pc["outer"]], dtype=float)
    owner = np.array([k for k, pc in enumerate(pieces) for _ in pc["outer"]], dtype=int)
    for i, j in cKDTree(pts).query_pairs(FAR_LAKE_JOIN_M, output_type="ndarray"):
        a, b = find(int(owner[i])), find(int(owner[j]))
        if a != b:
            parent[max(a, b)] = min(a, b)
    total: dict[int, float] = {}
    for k, pc in enumerate(pieces):
        total[find(k)] = total.get(find(k), 0.0) + pc["area"]

    def height(xs, zs):
        return L.sample_terrain_y(xs, zs, frame, None, provider)
    out = []
    for k, pc in enumerate(pieces):
        if total[find(k)] < FAR_LAKE_MIN_M2:
            continue
        o = np.asarray([p[:2] for p in pc["outer"]], dtype=float)
        if o[:, 0].max() < x0 or o[:, 0].min() > x0 + key.size_m or o[:, 1].max() < z0 or o[:, 1].min() > z0 + key.size_m:
            continue
        level = WT.lake_level(pc["outer"], pc["holes"], height)
        if level is None:
            continue
        out.append({"id": pc["id"], "kind": pc["kind"], "level_y": round(level, 2),
                    "outer": pc["outer"], "holes": pc["holes"]})
    return out


def far_water_grid(key: "FarKey", y: np.ndarray, lakes: list[dict]) -> np.ndarray | None:
    """Abaisse (sur place) le relief lointain `y` (101 × 101) sous les lacs et rend la grille de leur niveau.

    Échantillon dans un lac : niveau de ce lac, et sol à `level_y − WATER_SINK_M` au plus (règle EA1) ;
    ailleurs NaN. None si aucun échantillon n'est dans l'eau.
    """
    if not lakes:
        return None
    gx, gz = grid_xz(key, FAR_STEP_M)
    areas = WT.inland_areas(lakes)
    WT.sink_grid(gx, gz, y, areas)
    level = np.full(gx.size, np.nan)
    fx, fz = gx.ravel(), gz.ravel()
    for a in areas:
        bx0, bz0, bx1, bz1 = a["bbox"]
        sel = np.flatnonzero((fx >= bx0) & (fx <= bx1) & (fz >= bz0) & (fz <= bz1))
        if not len(sel):
            continue
        sel = sel[WT.rings_contain(fx[sel], fz[sel], a["rings"])]
        level[sel] = np.fmax(level[sel], a["level_y"])
    if not np.isfinite(level).any():
        return None
    return level.reshape(C.TILE_SAMPLES, C.TILE_SAMPLES)


def square_terrain(key: SquareKey, graph: RoadGraph, profiles: dict[str, EdgeProfile],
                   provider: ElevationProvider, frame: LocalFrame, water: list[dict] | None = None) -> np.ndarray:
    """Relief du carré fondu avec ses routes, abaissé sous les lacs (EA1), puis réglé sur la route (règle sol / route,
    `road_ground.py`) ; calculé sur RING_CELLS cases de plus tout autour : les sommets des bords communs reçoivent la
    même valeur dans les deux carrés."""
    return square_relief(key, graph, profiles, provider, frame, water)[1]


def square_relief(key: SquareKey, graph: RoadGraph, profiles: dict[str, EdgeProfile],
                  provider: ElevationProvider, frame: LocalFrame,
                  water: list[dict] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(relief avant le garde-fou de la chaussée, relief final) du carré, 101 × 101 chacun. Le premier sert à poser
    les bâtiments (20/11) : une maison du bord de route garde le pied qu'elle avait, au lieu de descendre au fond de
    l'entaille du garde-fou et de disparaître dans le talus (banc #936, lac d'Annecy)."""
    gx, gz = grid_xz(key, NEAR_STEP_M, ring=RING_CELLS)
    lat, lon = frame.to_latlon(gx.ravel(), gz.ravel())
    y = np.asarray(provider.elevations(lat, lon), dtype=float)
    pieces = []
    for k in sorted(profiles):
        e = graph.edges[k]
        pieces += axis_pieces(profiles[k], half_width(e.road_class), e.spans)
    dist, y_road = RoadsAxis(pieces).nearest(gx.ravel(), gz.ravel(), C.BLEND_OUTER_M)
    y = blend(y, dist, y_road, half_width=0.0).reshape(gx.shape)
    if water:   # lot EA1 : sol sous les lacs ; près d'une route (hors ponts : ils ne sont pas dans l'axe), fond fondu
        # avec la route comme le relief : chaussée gardée, puis rive en pente douce (20/11, route en surplomb d'une
        # chute de 7 m au bord d'un lac)
        WT.sink_grid(gx, gz, y, WT.inland_areas(water), road=(dist, y_road))
    # Fondu hors ponts et tunnels (la vallée reste sous un pont), garde-fou sur toute la chaussée à ciel ouvert, ponts
    # compris (20/11, « herbe au-dessus de la route »). Pas dans les tunnels : sous 40 m de colline, l'entaille faisait
    # une gorge aux parois grises (banc #936, Sevrier) ; un tunnel se dessinera (lot à venir) au lieu d'être taillé.
    # Largeur dégagée : au moins la chaussée de l'engine (ROAD_HALF_WIDTH_M, ruban de 6 m du thème par défaut), même
    # pour une piste ou un chemin fondus sur 2 m : la route engagée est dessinée à la largeur du thème quelle que soit
    # sa classe, et le talus d'une piste cyclable passait sur le bord du ruban.
    # Règle unique sol / route (21/11, road_ground.py) : route telle que l'engine la dessine (Catmull-Rom, cap
    # interpolé), sol sous la chaussée et les bas-côtés à ciel ouvert (ponts compris, pas dans les tunnels : la colline
    # reste, choix du 20/11), pieds des talus appuyés où la route repose sur le sol (hors ponts et tunnels). Largeur
    # au moins celle du ruban de l'engine, quelle que soit la classe de la route.
    upper, lower = [], []
    for k in sorted(profiles):
        e, p = graph.edges[k], profiles[k]
        up, lo = RG.corridor_s(p.x, p.z, p.alt_m, p.heading_deg, s=p.s,
                             open_spans=[sp for sp in e.spans if sp[2] == "tunnel"], ground_spans=e.spans,
                             half_width=half_width(e.road_class) + SQUARE_WIDTH_MARGIN_M,
                             sink=C.ROAD_SINK_M + SQUARE_SINK_MARGIN_M)
        upper.append(up)
        lower.append(lo)
    for up, lo in turnaround_corridors(graph, profiles, provider, frame):
        upper.append(up)
        lower.append(lo)
    s = RING_CELLS
    ground = y[s:-s, s:-s].astype("<f4")
    # abscisses des points, décalées de 1e7 m par route (arête ou boucle) : pieds de talus au bord d'une autre route
    for n, (u, lo) in enumerate(zip(upper, lower)):
        upper[n] = (*u[:3], u[3] + 1e7 * n)
        lower[n] = (*lo[:3], lo[3] + 1e7 * n)
    up_all = [np.concatenate([u[c] for u in upper]) if upper else np.empty(0) for c in range(4)]
    lo_all = [np.concatenate([lo[c] for lo in lower]) if lower else np.empty(0) for c in range(4)]
    RG.fit_grid(y, float(gx[0, 0]), float(gz[0, 0]), NEAR_STEP_M, up_all[:3],
                RG.drop_covered_feet(up_all, lo_all, up_all[3], lo_all[3], keep_compatible=False),
                rounds=SQUARE_ROUNDS)
    return ground, y[s:-s, s:-s].astype("<f4")


def turnaround_corridors(graph: RoadGraph, profiles: dict[str, EdgeProfile], provider: ElevationProvider,
                         frame: LocalFrame):
    """Points de la règle sol / route des boucles de retournement (21/11) : au bout de chaque impasse du carré, la
    balade tourne dans une boucle (`edge_profile.with_turnaround`) qu'aucune arête ne décrit. Même boucle, même
    altitude que celle que la séance tracera, si bien que le sol du carré la porte déjà (la séance la reprend sur la
    route qu'elle dessine, `session_ground.py`)."""
    out = []
    for k in sorted(profiles):
        e, p = graph.edges[k], profiles[k]
        if len(p.s) < 2:
            continue
        for node, forward in ((e.b, True), (e.a, False)):
            n = graph.nodes.get(node)
            if n is None or n.frontier or len(graph._adj.get(node, [])) != 1 or e.a == e.b:
                continue
            arrive = p if forward else p.reversed()
            loop = with_turnaround(arrive.reversed(), (float(arrive.x[-2]), float(arrive.z[-2])), provider, frame)
            m = int(np.searchsorted(loop.s, loop.length_m - arrive.length_m + 30.0))   # la boucle et 30 m d'arête
            out.append(RG.corridor_s(loop.x[:m + 1], loop.z[:m + 1], loop.alt_m[:m + 1], loop.heading_deg[:m + 1],
                                     s=loop.s[:m + 1], half_width=C.ROAD_HALF_WIDTH_M + SQUARE_WIDTH_MARGIN_M,
                                     sink=C.ROAD_SINK_M + SQUARE_SINK_MARGIN_M))
    return out


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
                  frame: LocalFrame, water_areas: list[dict] | None = None,
                  ground: np.ndarray | None = None) -> dict[str, dict[str, Any]]:
    """Bâtiments, végétation, eau (mer comprise), côte et points d'intérêt du carré, coordonnées
    relatives à son coin. `ground` : relief avant le garde-fou de la chaussée (square_relief), pour le pied
    des bâtiments ; sinon `near`."""
    x0, z0 = key.corner
    near_tiles = {(key.ix, -(key.i_n + 1)): near}
    ground_tiles = near_tiles if ground is None else {(key.ix, -(key.i_n + 1)): ground}
    buildings: list[dict] = []
    vegetation: list[dict] = []
    water: dict[str, list[dict]] = {"lines": [], "areas": []}
    poi: list[dict] = []
    m = AREA_SEARCH_M
    if water_areas is None:
        water_areas = square_water(key, db, provider, frame)
    river_levels = None
    river_pieces: dict[str, int] = {}
    for a in water_areas:
        if a["kind"] == "river":   # lot EA3 : morceaux dans le carré, altitude de chaque sommet
            river_levels = a["levels"]
            for po, ph in RS.clip_to_rect(a["outer"], a["holes"], x0, z0, x0 + key.size_m, z0 + key.size_m):
                o, hs = RS.piece_rings(po, ph)
                n = river_pieces.get(a["id"], 0)
                river_pieces[a["id"]] = n + 1
                area = RS.river_area(f"{a['id']}_c{key.ix}_{key.i_n}_{n}", o, hs, river_levels)
                if area is not None:
                    area["outer"] = _rel(area["outer"], x0, z0)
                    area["holes"] = [_rel(h, x0, z0) for h in area["holes"]]
                    water["areas"].append(area)
            continue
        if key.contains(*a["centroid"]):
            water["areas"].append({"id": a["id"], "kind": a["kind"], "level_y": a["level_y"],
                                   "outer": _rel(a["outer"], x0, z0), "holes": [_rel(h, x0, z0) for h in a["holes"]]})
    for a in db.areas_in(lonlat_bbox(frame, x0 - m, z0 - m, x0 + key.size_m + m, z0 + key.size_m + m),
                         kinds=("building", *VEGETATION_DENSITY)):
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
                "base_y": L.compute_footprint_base_y(outer, frame, ground_tiles, provider),
                "height_m": L.compute_building_height(a.osm_id, a.tags), "roof": "flat",
                "hint": {"building": str(a.tags.get("building")), "colour": colour}})
        elif a.kind in VEGETATION_DENSITY:
            vegetation.append({"id": a.osm_id, "kind": a.kind, "outer": _rel(outer, x0, z0),
                               "holes": [_rel(h, x0, z0) for h in holes], "density": VEGETATION_DENSITY[a.kind]})

    bbox = lonlat_bbox(frame, x0, z0, x0 + key.size_m, z0 + key.size_m)
    for line in db.lines_in(bbox, kinds=WATERWAY_KINDS):
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

    if river_levels is not None:   # lot EA3 : plus de ruban dans la surface d'une grande rivière
        water["lines"] = RS.trim_lines(water["lines"], river_levels, x0, z0)

    for p in db.points_in(bbox, kinds=POI_KINDS):
        x, z = (float(v[0]) for v in frame.to_xz(np.array([p.lat]), np.array([p.lon])))
        if not key.contains(x, z):
            continue
        kind, radius = POI_KINDS[p.kind]
        y = L.sample_terrain_y(np.array([x]), np.array([z]), frame, near_tiles, provider)
        poi.append({"id": p.osm_id, "kind": kind, "x": round(x - x0, 2), "y": round(float(y[0]), 2),
                    "z": round(z - z0, 2), "radius_m": radius, "name": p.name})

    def height_fn(xs: np.ndarray, zs: np.ndarray) -> np.ndarray:
        return L.sample_terrain_y(np.asarray(xs, float), np.asarray(zs, float), frame, near_tiles, provider)

    sea, coast = square_coast(x0, z0, key.size_m, db, frame,
                              lambda a, b, c, d: lonlat_bbox(frame, a, b, c, d), height_fn, f"{key.ix}_{key.i_n}")
    for a in sea:
        water["areas"].append({**a, "outer": _rel(a["outer"], x0, z0), "holes": [_rel(h, x0, z0) for h in a["holes"]]})
    coast["lines"] = [{**c, "points": _rel(c["points"], x0, z0)} for c in coast["lines"]]
    coast["beaches"] = [{**b, "outer": _rel(b["outer"], x0, z0), "holes": [_rel(h, x0, z0) for h in b["holes"]]}
                        for b in coast["beaches"]]

    return {
        "buildings": {"version": C.BUILDINGS_VERSION, "buildings": buildings},
        "vegetation": {"version": C.VEGETATION_VERSION, "areas": vegetation},
        "water": {"version": C.WATER_VERSION, **water},
        "poi": {"version": C.POI_VERSION, "points": poi},
        "coast": coast,
    }


def square_bridges(key: SquareKey, graph: RoadGraph, profiles: dict[str, EdgeProfile],
                   provider: ElevationProvider, frame: LocalFrame) -> dict[str, Any]:
    """Ponts du carré (lot EA4, `bridges.py`) : portions « bridge » des arêtes, rangées dans le carré qui
    contient le milieu du pont ; tablier au profil de l'arête (celui de la route engagée), pied des piles sur
    le MNT. Coordonnées horizontales relatives au coin du carré, comme les autres couches."""
    from .. import bridges as BR

    x0, z0 = key.corner

    def ground(xs, zs):
        lat, lon = frame.to_latlon(np.asarray(xs, float), np.asarray(zs, float))
        return np.asarray(provider.elevations(lat, lon), dtype=float)
    out = []
    for k in sorted(profiles):
        e, p = graph.edges[k], profiles[k]
        for n, (s0, s1, kind) in enumerate(e.spans):
            if kind != "bridge":
                continue
            sm = 0.5 * (float(s0) + float(s1))
            if not key.contains(float(np.interp(sm, p.s, p.x)), float(np.interp(sm, p.s, p.z))):
                continue
            item = BR.bridge_item(f"{e.id}_{n}", p.s, p.x, p.z, p.alt_m, s0, s1, ground, C.ROAD_HALF_WIDTH_M)
            if item is None:
                continue
            item["points"] = [[round(a - x0, 2), round(b - z0, 2), c] for a, b, c in item["points"]]
            item["piers"] = [[round(a - x0, 2), round(b - z0, 2), c, d] for a, b, c, d in item["piers"]]
            out.append(item)
    return {"version": BR.BRIDGES_VERSION, "bridges": out}


def square_tunnels(key: SquareKey, graph: RoadGraph, profiles: dict[str, EdgeProfile]) -> dict[str, Any]:
    """Tunnels du carré (lot EA5, `tunnels.py`) : portions « tunnel » des arêtes, rangées dans le carré qui contient
    le milieu du tunnel ; axe au profil de l'arête (celui de la route engagée). Coordonnées horizontales relatives
    au coin du carré, comme les ponts."""
    from .. import tunnels as TU

    x0, z0 = key.corner
    out = []
    for k in sorted(profiles):
        e, p = graph.edges[k], profiles[k]
        for n, (s0, s1, kind) in enumerate(e.spans):
            if kind != "tunnel":
                continue
            sm = 0.5 * (float(s0) + float(s1))
            if not key.contains(float(np.interp(sm, p.s, p.x)), float(np.interp(sm, p.s, p.z))):
                continue
            item = TU.tunnel_item(f"{e.id}_{n}", p.s, p.x, p.z, p.alt_m, s0, s1, C.ROAD_HALF_WIDTH_M)
            if item is None:
                continue
            item["points"] = [[round(a - x0, 2), round(b - z0, 2), c] for a, b, c in item["points"]]
            out.append(item)
    return {"version": TU.TUNNELS_VERSION, "tunnels": out}


def _round(a: np.ndarray, digits: int) -> list[float]:
    return [round(float(v), digits) for v in a]


def _write_atomic(final: Path, files: dict[str, bytes]) -> None:
    """Écrit les fichiers dans un dossier temporaire voisin, puis le renomme à la place de `final`.

    Revue de code K2-07 (lot RC23) : les restes `.<nom>.tmp-*` et `.<nom>.old-*` d'un arrêt forcé entre deux
    renommages sont supprimés à l'écriture suivante (ils n'étaient ni comptés ni retirés) ; un autre processus
    qui pose le même carré au même moment (séance et préchargement) ne fait plus échouer celui-ci : son carré,
    calculé des mêmes données, est gardé."""
    final.parent.mkdir(parents=True, exist_ok=True)
    tag = f"{os.getpid()}-{threading.get_ident()}"
    tmp = final.parent / f".{final.name}.tmp-{tag}"
    old = final.parent / f".{final.name}.old-{tag}"
    for stale in [*final.parent.glob(f".{final.name}.tmp-*"), *final.parent.glob(f".{final.name}.old-*")]:
        m = re.search(r"\.(?:tmp|old)-(\d+)(?:-\d+)?$", stale.name)
        if m is None or int(m.group(1)) == os.getpid() or _pid_alive(int(m.group(1))):
            continue                                   # écriture en cours (ce processus ou un autre, vivant)
        shutil.rmtree(stale, ignore_errors=True)
    try:
        tmp.mkdir()
        for name, data in files.items():
            (tmp / name).write_bytes(data)
        try:
            if final.exists():
                final.rename(old)
                tmp.rename(final)
            else:
                tmp.rename(final)
        except OSError:
            if not final.is_dir():
                raise CompileError(f"carré {final.name} non écrit (renommage refusé)")
            # posé entre-temps par un autre processus : le sien est gardé
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def generate_square(key: SquareKey, db: OsmDb, provider: ElevationProvider, cache: WorldCache,
                    tiles_complete: bool = True) -> Path:
    """Carré dans le cache ; rien n'est recalculé s'il y est déjà avec les mêmes versions.

    `tiles_complete` faux (tuiles vectorielles manquantes, K1-04) : un carré complet déjà en cache est gardé ; sinon le
    carré est écrit marqué partiel (`square_versions`)."""
    versions = square_versions(db, provider, tiles_complete)
    final = cache.square_dir(key.zone, key.ix, key.i_n)
    if cache.is_valid(key.cache_key, versions) or (
            not tiles_complete and cache.is_valid(key.cache_key, square_versions(db, provider))):
        cache.touch(key.cache_key)
        return final
    frame = zone_frame(key.zone)
    graph, profiles = square_edges(key, db, provider, frame)
    water = square_water(key, db, provider, frame)
    ground, near = square_relief(key, graph, profiles, provider, frame, water)
    layers = square_layers(key, db, near, provider, frame, water, ground)
    layers["bridges"] = square_bridges(key, graph, profiles, provider, frame)
    layers["tunnels"] = square_tunnels(key, graph, profiles)
    counts = {"edges": len(profiles), "buildings": len(layers["buildings"]["buildings"]),
              "vegetation": len(layers["vegetation"]["areas"]), "water_lines": len(layers["water"]["lines"]),
              "water_areas": len(layers["water"]["areas"]), "poi": len(layers["poi"]["points"]),
              "bridges": len(layers["bridges"]["bridges"]), "tunnels": len(layers["tunnels"]["tunnels"]),
              "sea": sum(1 for a in layers["water"]["areas"] if a["kind"] == "sea"),
              "coast_lines": len(layers["coast"]["lines"]), "beaches": len(layers["coast"]["beaches"])}
    meta = {"zone": key.zone, "ix": key.ix, "in": key.i_n, "corner": list(key.corner), "versions": versions,
            "counts": counts}
    files = {"near.f32": np.ascontiguousarray(near, dtype="<f4").tobytes(),
             "meta.json": _json(meta)}
    files.update({f"{name}.json": _json(payload) for name, payload in layers.items()})
    _write_atomic(final, files)
    cache.add(key.cache_key, "square", final, versions, region=db.meta.get("region") or None)
    return final


def generate_far(key: FarKey, provider: ElevationProvider, cache: WorldCache, db: OsmDb | None = None,
                 water_complete: bool = True) -> Path:
    """Tuile lointaine de 5 km : 101 × 101 à 50 m (niveau `far` du compilateur).

    Avec une base OSM (lot EA2) : relief abaissé sous les grands lacs (`far_lakes`, règle EA1) et grille
    de leur niveau écrite à côté (`<IX5>_<IN5>.water`, 101 × 101 float32, NaN hors de l'eau), seulement
    s'il y a de l'eau ; `water_complete` faux quand des tuiles vectorielles de l'emprise manquent.
    """
    versions = far_versions(provider, db, water_complete)
    path = cache.far_path(key.zone, key.ix, key.i_n)
    if cache.is_valid(key.cache_key, versions):
        cache.touch(key.cache_key)
        return path
    frame = zone_frame(key.zone)
    gx, gz = grid_xz(key, FAR_STEP_M)
    lat, lon = frame.to_latlon(gx.ravel(), gz.ravel())
    y = np.asarray(provider.elevations(lat, lon), dtype=float)
    level = far_water_grid(key, y, far_lakes(key, db, provider, frame)) if db is not None else None
    path.parent.mkdir(parents=True, exist_ok=True)
    water = cache.far_water_path(key.zone, key.ix, key.i_n)
    if level is None:
        water.unlink(missing_ok=True)
    else:
        tmp_w = water.with_name(f".{water.name}.tmp-{os.getpid()}")
        tmp_w.write_bytes(level.astype("<f4").tobytes())
        tmp_w.replace(water)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_bytes(y.astype("<f4").tobytes())
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
