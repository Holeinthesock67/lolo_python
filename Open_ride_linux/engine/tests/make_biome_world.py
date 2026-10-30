#!/usr/bin/env python3
"""Parcours de démonstration fictifs par biome (lot U19) : un biome partout, ou les six du premier jalon à la suite.

Produit, avec le vrai compilateur, un `.world` complet (`route`, `terrain`, `buildings`, `vegetation`,
`poi`, `water`) à partir d'une trace et d'un relief synthétiques et d'une réponse Overpass fabriquée ici
(aucune donnée réelle, aucun réseau), puis ajoute ce que le compilateur ne sait pas encore écrire (lots U2,
U9, U20) : la couche `biome` (§8 quater), la colonne `surface` de la route et, avec `--sea`, la couche
`coast` (§8 quinquies) et des aires d'eau `sea`. Format 1.6.

- `--biome ID` : un biome sur 6 km (trois blocs de 2 km) ; `--tour` : les six biomes du premier jalon à
  la suite (côte, méditerranéen, prairie, cultures, forêt, alpin), 2 km chacun, transitions de 300 m ;
- relief analytique par biome, mélangé par les poids : bord de mer presque plat, collines de cultures,
  vallée boisée, montée de 7,5 % entre des pentes de montagne pour `alpine` ;
- bâtiments, végétation et points d'intérêt fictifs, de densité propre à chaque biome ;
- `--gravel` : un tiers de chaque bloc de 2 km en `gravel` ou `dirt` (en alternance), le reste `paved` ;
- `--sea` : côte fictive à gauche de la route le long du biome `coast` : terrain sous le niveau 0, ligne
  de côte, plage de sable puis côte rocheuse, aires `sea` (`level_y` = 0) de 300 m de large.

    python3 engine/tests/make_biome_world.py --out DOSSIER --tour [--gravel] [--sea]
    python3 engine/tests/make_biome_world.py --out DOSSIER --biome alpine
    python3 engine/tests/make_biome_world.py --out DOSSIER --demo-set   # les quatre parcours de demo-biomes
    → DOSSIER/<nom>.world/ et DOSSIER/<nom>.json (parts des biomes et des surfaces)

Origine fictive au degré entier (45° N, 2° E : latitude tempérée de l'hémisphère nord, aucune ville au
point), date de création fixe : deux générations donnent des fichiers identiques au bit près.
Sert à la recette U18 et aux essais de rendu des biomes (`openride-core demo-biomes` range les quatre
parcours dans le dossier des parcours). Prérequis : compilateur installé (`pip install -e compiler`).
Code de sortie : 0 si tout est écrit.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import random
import shutil
import socket
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_sim_world as sim  # noqa: E402  (Overpass fabriqué, route en S)

ORIGIN = (45.0, 2.0)                    # degrés entiers, fictifs
CREATED = "2026-10-30T00:00:00+00:00"   # fixe : parcours reproductibles
OSM_DATE = "2026-10-30T00:00:00Z"
FORMAT_VERSION = "1.6"
LAYERS = ("buildings", "vegetation", "poi", "water")
BLOCK_M = 2000.0                        # longueur d'un biome
TRANSITION_M = 300.0                    # fondu entre deux biomes
STEP_M = 5.0
BASE_ALT_M = 6.0
TOUR = ("coast", "mediterranean", "temperate_grassland", "farmland", "temperate_forest", "alpine")
FIRST_MILESTONE = frozenset(TOUR)
DEFAULT_BIOME = "temperate_grassland"
UNPAVED = (700.0, 700.0 + BLOCK_M / 3.0)   # portion non revêtue de chaque bloc (--gravel)
SEA_SIDE = -1                           # la mer à gauche du sens de marche (à l'ouest)
SEA_BAND_M = (70.0, 370.0)              # aires `sea` : de 70 à 370 m de l'axe
BEACH_M = (36.0, 70.0)
NEAR_T, FAR_T, GRID = 1000.0, 5000.0, 17
DEMO_SET = (("demo-biomes-tour", "tour", False, False), ("demo-biomes-gravel", "tour", True, False),
            ("demo-biomes-cote", "coast", False, True), ("demo-biomes-alpin", "alpine", False, False))

# Pente de la route (%) dans un bloc, selon la position u (m) dans le bloc.
GRADE = {
    "coast": lambda u: 0.3 * math.sin(u / 260.0),
    "mediterranean": lambda u: 3.0 + 2.0 * math.sin(u / 300.0),
    "temperate_grassland": lambda u: 1.0 + 1.5 * math.sin(u / 250.0),
    "farmland": lambda u: 2.5 * math.sin(2.0 * math.pi * u / 700.0),
    "temperate_forest": lambda u: 4.0 + 1.0 * math.sin(u / 200.0),
    "alpine": lambda u: 7.5 + 1.5 * math.sin(u / 350.0),
}
# Relief de part et d'autre de la route : (pente des flancs, pente au-delà de 160 m, amplitude des collines).
SIDES = {
    "coast": (0.03, 0.02, 4.0),
    "mediterranean": (0.10, 0.08, 40.0),
    "temperate_grassland": (0.04, 0.03, 15.0),
    "farmland": (0.06, 0.04, 25.0),
    "temperate_forest": (0.12, 0.15, 30.0),
    "alpine": (0.25, 0.45, 80.0),
}


class Plan:
    """Suite de biomes le long de la route et tout ce qui en découle (poids, altitude, surface)."""

    def __init__(self, biomes: tuple[str, ...], gravel: bool, sea: bool) -> None:
        self.biomes = biomes
        self.gravel = gravel
        self.sea = sea and "coast" in biomes
        self.length_m = BLOCK_M * len(biomes)
        self._alt = [BASE_ALT_M]
        n = int(self.length_m / STEP_M)
        for k in range(n):
            s = (k + 0.5) * STEP_M
            self._alt.append(self._alt[-1] + STEP_M * self.grade(s) / 100.0)

    def weights(self, s: float) -> dict[str, float]:
        """Part (0 à 1) de chaque biome à l'abscisse `s` : fondu linéaire de 300 m centré sur chaque limite."""
        s = min(max(s, 0.0), self.length_m)
        out: dict[str, float] = {}
        for i, b in enumerate(self.biomes):
            lo, hi = i * BLOCK_M, (i + 1) * BLOCK_M
            w_in = 1.0 if i == 0 else _ramp((s - (lo - TRANSITION_M / 2)) / TRANSITION_M)
            w_out = 1.0 if i == len(self.biomes) - 1 else 1.0 - _ramp((s - (hi - TRANSITION_M / 2)) / TRANSITION_M)
            w = min(w_in, w_out)
            if w > 0.0:
                out[b] = out.get(b, 0.0) + w
        return out

    def weights_np(self, s):
        """`weights` sur un tableau d'abscisses : {biome: tableau de parts}."""
        import numpy as np
        s = np.clip(np.asarray(s, dtype=float), 0.0, self.length_m)
        out: dict = {}
        last = len(self.biomes) - 1
        for i, b in enumerate(self.biomes):
            lo, hi = i * BLOCK_M, (i + 1) * BLOCK_M
            w_in = 1.0 if i == 0 else np.clip((s - (lo - TRANSITION_M / 2)) / TRANSITION_M, 0.0, 1.0)
            w_out = 1.0 if i == last else 1.0 - np.clip((s - (hi - TRANSITION_M / 2)) / TRANSITION_M, 0.0, 1.0)
            out[b] = out.get(b, 0.0) + np.minimum(w_in, w_out) * np.ones_like(s)
        return out

    def grade(self, s: float) -> float:
        u = s % BLOCK_M
        return sum(w * GRADE[b](u) for b, w in self.weights(s).items())

    def altitude(self, s: float) -> float:
        s = min(max(s, 0.0), self.length_m)
        k = min(int(s / STEP_M), len(self._alt) - 2)
        t = (s - k * STEP_M) / STEP_M
        return self._alt[k] * (1.0 - t) + self._alt[k + 1] * t

    def surface(self, s: float) -> str:
        if not self.gravel:
            return "paved"
        block = min(int(s // BLOCK_M), len(self.biomes) - 1)
        u = s - block * BLOCK_M
        if UNPAVED[0] <= u < UNPAVED[1]:
            return "gravel" if block % 2 == 0 else "dirt"
        return "paved"


def _ramp(t: float) -> float:
    return min(1.0, max(0.0, t))


def make_terrain(plan: Plan):
    """Relief `f(x, z)` : altitude de la route, flancs et collines des biomes, fond marin côté mer."""
    import numpy as np

    def terrain(x, z):
        x = np.asarray(x, dtype=float)
        z = np.asarray(z, dtype=float)
        s = np.clip(-z, 0.0, plan.length_m)
        base = np.interp(s, np.arange(len(plan._alt)) * STEP_M, plan._alt)
        weights = plan.weights_np(s)
        dx = x - 60.0 * np.sin(2.0 * np.pi * s / 1800.0)
        d = np.abs(dx)
        side = np.zeros_like(base)
        for b, (slope, far_slope, hills) in SIDES.items():
            w = weights.get(b)
            if w is None or not np.any(w):
                continue
            ramp = np.clip((d - 40.0) / 260.0, 0.0, 1.0)
            bump = hills * ramp * (0.5 + 0.5 * np.sin(x / 310.0) * np.cos(z / 270.0))
            side += w * (slope * np.clip(d - 12.0, 0.0, 150.0) + far_slope * np.clip(d - 162.0, 0.0, None) + bump)
        if plan.sea:
            sea = weights.get("coast", 0.0) * (np.sign(dx) == SEA_SIDE)
            # Plage de la route au niveau 0 entre 36 et 70 m de l'axe, puis fond marin jusqu'à −25 m.
            t = d - BEACH_M[0]
            shore = np.where(d < BEACH_M[1], base * (1.0 - t / (BEACH_M[1] - BEACH_M[0])), -0.1 * (d - BEACH_M[1]))
            shore = np.where(d < BEACH_M[0], base, np.maximum(shore, -25.0))
            return np.where(sea > 0.0, (1.0 - sea) * (base + side) + sea * shore, base + side)
        return base + side

    return terrain


def build_overpass(frame, plan: Plan, seed: int) -> sim.Overpass:
    """Éléments OSM fictifs par bloc de 2 km, selon le biome du bloc."""
    rng = random.Random(seed)
    op = sim.Overpass(frame, rng)
    for i, biome in enumerate(plan.biomes):
        s0 = i * BLOCK_M
        BLOCKS[biome](op, rng, s0, s0 + BLOCK_M, plan, i)
    return op


def _veg(op: sim.Overpass, s0: float, s1: float, side: int, near: float, far: float, tags: dict) -> None:
    lo, hi = (near, far) if side > 0 else (-far, -near)
    op.way(op.band(s0, s1, lo, hi), tags)
    op.counts["vegetation"] += 1


def _houses(op: sim.Overpass, rng: random.Random, s0: float, s1: float, sides: tuple[int, ...], colours: list[str],
            name: str, gap: tuple[float, float] = (20.0, 28.0), church: bool = True) -> None:
    s = s0
    while s < s1:
        for side in sides:
            if rng.random() < 0.15:
                continue
            tags: dict = {"building": rng.choice(["house", "house", "house", "garage", "yes"]),
                          "building:colour": rng.choice(colours)}
            length, depth = (rng.uniform(5, 7), rng.uniform(5, 6)) if tags["building"] == "garage" \
                else (rng.uniform(9, 14), rng.uniform(7, 10))
            tags["building:levels"] = str(rng.randint(1, 3))
            op.building(s, side * (rng.uniform(13.0, 17.0) + depth / 2), tags, length, depth)
        s += rng.uniform(*gap)
    mid = (s0 + s1) / 2
    if church:
        side = sides[-1]
        op.building(mid, side * 34.0, {"building": "church", "amenity": "place_of_worship", "height": "15 m"}, 26.0, 13.0)
    op.node(sim.road_x(mid) + sides[0] * 30.0, -mid, {"place": "village", "name": name})


def _farms(op: sim.Overpass, spots: tuple[float, ...], colour: str) -> None:
    for k, s in enumerate(spots):
        side = 1 if k % 2 else -1
        op.building(s, side * 32.0, {"building": "farm", "building:levels": "2", "building:colour": colour}, 16.0, 11.0)
        op.building(s + 22.0, side * 38.0, {"building": "barn", "height": "8 m"}, 22.0, 13.0)


def _coast(op, rng, s0, s1, plan, i):
    land = -SEA_SIDE
    _houses(op, rng, s0 + 250.0, s0 + 650.0, (land,), ["#f0e6d2", "#ffffff", "#e8dcc4", "#d4e4ee"], "Port Fictif")
    _veg(op, s0 + 700.0, s1 - 100.0, land, 22.0, 200.0, {"landuse": "grass"})
    if not plan.sea:
        _veg(op, s0 + 100.0, s1 - 100.0, -land, 22.0, 140.0, {"natural": "scrub"})
    op.node(sim.road_x(s0 + 1200.0) + land * 25.0, -(s0 + 1200.0), {"tourism": "viewpoint", "name": "Pointe Fictive"})


def _mediterranean(op, rng, s0, s1, plan, i):
    _veg(op, s0 + 150.0, s1 - 150.0, -1, 22.0, 220.0, {"natural": "scrub"})
    _veg(op, s0 + 150.0, s0 + 900.0, 1, 22.0, 160.0, {"landuse": "orchard"})
    _veg(op, s0 + 1500.0, s1 - 150.0, 1, 22.0, 200.0, {"natural": "scrub"})
    _houses(op, rng, s0 + 1000.0, s0 + 1400.0, (1, -1), ["#f0e6d2", "#e3c9a8", "#f5efe0", "#e8b98a"], "Mas Fictif")


def _grassland(op, rng, s0, s1, plan, i):
    _veg(op, s0 + 100.0, s1 - 100.0, 1, 22.0, 250.0, {"landuse": "meadow"})
    _veg(op, s0 + 100.0, s0 + 1100.0, -1, 22.0, 250.0, {"landuse": "meadow", "animal": "cattle"})
    _veg(op, s0 + 1300.0, s1 - 100.0, -1, 22.0, 120.0, {"natural": "scrub"})
    _farms(op, (s0 + 400.0, s0 + 1600.0), "#d9cfc1")
    _houses(op, rng, s0 + 900.0, s0 + 1200.0, (-1, 1), sim.COLOURS, "Hameau Fictif", gap=(30.0, 45.0), church=False)
    mid = s0 + 1450.0
    hx, hz = sim.road_heading(mid)
    nx, nz = -hz, hx
    op.way([(sim.road_x(mid) + nx * d, -mid + nz * d) for d in range(-250, 251, 25)],
           {"waterway": "stream"}, close=False)
    op.counts["water_lines"] += 1


def _farmland(op, rng, s0, s1, plan, i):
    for side in (-1, 1):
        _veg(op, s0 + 100.0, s0 + 950.0, side, 22.0, 300.0, {"landuse": "farmland"})
        _veg(op, s0 + 1050.0, s1 - 100.0, side, 22.0, 300.0, {"landuse": "farmland"})
    _veg(op, s0 + 950.0, s0 + 1050.0, 1, 22.0, 180.0, {"landuse": "orchard"})
    _farms(op, (s0 + 300.0, s0 + 800.0, s0 + 1300.0, s0 + 1750.0), "#c9b59a")
    for s, off in ((s0 + 600.0, 260.0), (s0 + 1100.0, 320.0), (s0 + 1550.0, 280.0)):
        op.node(sim.road_x(s) + off, -s, {"power": "generator", "generator:source": "wind", "height": "95"})


def _forest(op, rng, s0, s1, plan, i):
    _veg(op, s0 + 50.0, s1 - 50.0, 1, 20.0, 300.0, {"landuse": "forest"})
    _veg(op, s0 + 50.0, s0 + 900.0, -1, 20.0, 300.0, {"natural": "wood"})
    _veg(op, s0 + 1250.0, s1 - 50.0, -1, 20.0, 300.0, {"landuse": "forest"})
    lake_s = s0 + 1080.0
    c = (sim.road_x(lake_s) - 110.0, -lake_s)
    op.way([(c[0] + 60.0 * math.cos(a / 12 * 2 * math.pi), c[1] + 40.0 * math.sin(a / 12 * 2 * math.pi))
            for a in range(12)], {"natural": "water", "water": "lake", "name": "Étang Fictif"})
    op.counts["water_areas"] += 1
    op.building(s0 + 1500.0, -28.0, {"building": "house", "building:levels": "2", "building:colour": "#b9a48a"}, 11.0, 8.0)


def _alpine(op, rng, s0, s1, plan, i):
    _veg(op, s0 + 50.0, s0 + 700.0, 1, 20.0, 260.0, {"natural": "wood"})
    _veg(op, s0 + 700.0, s1 - 50.0, 1, 20.0, 260.0, {"natural": "heath"})
    _veg(op, s0 + 50.0, s1 - 50.0, -1, 20.0, 200.0, {"natural": "grassland"})
    _veg(op, s0 + 1100.0, s0 + 1500.0, -1, 200.0, 320.0, {"natural": "scrub"})
    for s in (s0 + 450.0, s0 + 1250.0, s0 + 1800.0):
        op.building(s, 26.0, {"building": "house", "height": "9 m", "building:colour": "#8a6a4a"}, 12.0, 10.0)
        op.building(s + 18.0, -30.0, {"building": "barn", "height": "7 m", "building:colour": "#7a5a3a"}, 14.0, 10.0)
    op.node(sim.road_x(s1 - 150.0) - 25.0, -(s1 - 150.0), {"tourism": "viewpoint", "name": "Col Fictif"})


BLOCKS = {"coast": _coast, "mediterranean": _mediterranean, "temperate_grassland": _grassland,
          "farmland": _farmland, "temperate_forest": _forest, "alpine": _alpine}


class Frame(sim.Frame):
    def __init__(self) -> None:
        from openride_compiler.pipeline import utm_transformer, utm_zone_of
        number, _, south = utm_zone_of(*ORIGIN)
        self.tr = utm_transformer(number, south)
        self.e0, self.n0 = self.tr.transform(ORIGIN[1], ORIGIN[0])


def write_gpx(path: Path, frame: Frame, plan: Plan, name: str) -> None:
    pts = []
    for k in range(int(plan.length_m / STEP_M) + 1):
        s = k * STEP_M
        lat, lon = frame.latlon(sim.road_x(s), -s)
        pts.append(f'<trkpt lat="{lat:.10f}" lon="{lon:.10f}"><ele>{plan.altitude(s):.3f}</ele></trkpt>')
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<gpx version="1.1" creator="make_biome_world" xmlns="http://www.topografix.com/GPX/1/1">'
                    f"<trk><name>{name}</name><trkseg>{''.join(pts)}</trkseg></trk></gpx>\n", encoding="utf-8")


# --- Couches ajoutées après la compilation (format 1.6) ----------------------------------------------------

def _int_weights(parts: dict[str, float]) -> dict[str, int]:
    """Poids entiers dont la somme vaut 255 (le reste de l'arrondi va au biome le plus lourd)."""
    total = sum(parts.values())
    out = {b: int(round(255 * w / total)) for b, w in parts.items()}
    top = max(out, key=lambda b: (out[b], b))
    out[top] += 255 - sum(out.values())
    return out


def biome_tile(plan: Plan, size: float, ix: int, iz: int) -> dict:
    points = []
    for j in range(GRID):
        for i in range(GRID):
            z = iz * size + j * size / (GRID - 1)
            points.append(_int_weights(plan.weights(-z)))
    used = [b for b in plan.biomes if any(p.get(b, 0) > 0 for p in points)]
    used = list(dict.fromkeys(used))
    if len(used) > 4:
        raise ValueError(f"tuile {ix}_{iz} : {len(used)} biomes (4 au plus)")
    return {"version": "1.0", "biomes": used, "grid": GRID,
            "weights": [[p.get(b, 0) for p in points] for b in used], "variant": None}


def write_biome_layer(world: Path, plan: Plan, manifest: dict, route: dict) -> dict[str, float]:
    tiles = manifest["layers"]["terrain"]["tiles"]
    for level, size in (("near", NEAR_T), ("far", FAR_T)):
        folder = world / "biome" / level
        folder.mkdir(parents=True, exist_ok=True)
        for ix, iz in tiles[level]:
            data = biome_tile(plan, size, ix, iz)
            (folder / f"tile_{ix}_{iz}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    shares: dict[str, float] = {}
    for z in route["z"]:
        for b, w in _int_weights(plan.weights(-z)).items():
            shares[b] = shares.get(b, 0.0) + w / 255.0
    shares = {b: round(100.0 * v / route["n"], 1) for b, v in shares.items() if v > 0}
    forced = plan.biomes[0] if len(set(plan.biomes)) == 1 else None
    manifest["layers"]["biome"] = {"present": True, "version": "1.0",
                                   "default_biome": forced or DEFAULT_BIOME, "forced": None,
                                   "sources": ["synthetic"], "shares": shares,
                                   "tiles": {"near": tiles["near"], "far": tiles["far"]}}
    return shares


def write_surface(plan: Plan, manifest: dict, route: dict) -> dict[str, float]:
    # Abscisse de la trace fabriquée : la route compilée suit la trace, sa distance −z suffit à 1 % près.
    route["surface"] = [plan.surface(-z) for z in route["z"]]
    pct: dict[str, float] = {}
    for v in route["surface"]:
        pct[v] = pct.get(v, 0.0) + 1.0
    pct = {k: round(100.0 * v / route["n"], 1) for k, v in sorted(pct.items())}
    manifest["route"]["surface_source"] = "osm"
    if isinstance(manifest.get("stats"), dict):
        manifest["stats"]["surface_pct"] = pct
    return pct


def write_sea(world: Path, plan: Plan, manifest: dict, route: dict) -> dict[str, int]:
    """Couche côte et aires `sea` le long du biome `coast` (tronçons de 1 km de la route)."""
    from openride_compiler.constants import CHUNK_LENGTH_M
    coast_s = [i * BLOCK_M for i, b in enumerate(plan.biomes) if b == "coast"]
    chunks: dict[int, dict] = {}
    water_dir = world / "water"
    water_dir.mkdir(exist_ok=True)
    areas_added = 0

    def side_pt(s: float, d: float) -> list[float]:
        hx, hz = sim.road_heading(s)
        nx, nz = -hz, hx
        return [round(sim.road_x(s) + SEA_SIDE * nx * d, 2), round(-s + SEA_SIDE * nz * d, 2)]

    for b0 in coast_s:
        for k in range(int(b0 // CHUNK_LENGTH_M), int((b0 + BLOCK_M) // CHUNK_LENGTH_M)):
            c0, c1 = k * CHUNK_LENGTH_M, (k + 1) * CHUNK_LENGTH_M
            if k == 0:
                c0 = 0.0
            sandy = k % 2 == 0
            # Côte parcourue du nord au sud (z croissant) : la mer, à l'ouest, est à droite du sens des points.
            line = [side_pt(s, BEACH_M[1]) for s in _frange(c1, c0, -25.0)]
            entry = chunks.setdefault(k, {"version": "1.0", "lines": [], "beaches": []})
            entry["lines"].append({"id": f"c{k}", "shore": "sand" if sandy else "rock", "points": line})
            if sandy:
                inner = [side_pt(s, BEACH_M[0]) for s in _frange(c0 + 50.0, c1 - 50.0, 25.0)]
                outer = [side_pt(s, BEACH_M[1]) for s in _frange(c1 - 50.0, c0 + 50.0, -25.0)]
                entry["beaches"].append({"id": f"b{k}", "kind": "sand", "outer": _ccw(inner + outer), "holes": []})
            water_file = water_dir / f"chunk_{k}.json"
            water = json.loads(water_file.read_text(encoding="utf-8")) if water_file.is_file() \
                else {"version": "1.0", "lines": [], "areas": []}
            for a0 in [c0 + 250.0 * m for m in range(int(math.ceil((c1 - c0) / 250.0)))]:
                a1 = min(a0 + 250.0, c1)
                near = [side_pt(s, SEA_BAND_M[0]) for s in _frange(a0, a1, 25.0)]
                far = [side_pt(s, SEA_BAND_M[1]) for s in _frange(a1, a0, -25.0)]
                water["areas"].append({"id": f"s{k}_{int(a0 - c0)}", "kind": "sea", "level_y": 0.0,
                                       "outer": _ccw(near + far), "holes": []})
                areas_added += 1
            water_file.write_text(json.dumps(water, separators=(",", ":")), encoding="utf-8")
    folder = world / "coast"
    folder.mkdir(exist_ok=True)
    for k, data in sorted(chunks.items()):
        (folder / f"chunk_{k}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    lines = sum(len(c["lines"]) for c in chunks.values())
    beaches = sum(len(c["beaches"]) for c in chunks.values())
    manifest["layers"]["coast"] = {"present": True, "version": "1.0", "lines_count": lines,
                                   "beaches_count": beaches, "osm_date": OSM_DATE}
    w = manifest["layers"]["water"]
    w["present"] = True
    w["areas_count"] = int(w.get("areas_count", 0)) + areas_added
    w.setdefault("version", "1.0")
    w.setdefault("lines_count", 0)
    return {"lines": lines, "beaches": beaches, "sea_areas": areas_added}


def _ccw(ring: list[list[float]]) -> list[list[float]]:
    """Anneau extérieur dans le sens antihoraire du format (aire signée positive, comme `verify`)."""
    from openride_compiler.osm_layers import signed_area
    return ring if signed_area(ring) > 0 else ring[::-1]


def _frange(a: float, b: float, step: float) -> list[float]:
    """De `a` à `b` inclus par pas de `step` (positif ou négatif)."""
    n = max(1, int(round(abs(b - a) / abs(step))))
    return [a + (b - a) * k / n for k in range(n + 1)]


# --- Génération ------------------------------------------------------------------------------------------

@contextlib.contextmanager
def _offline_compiler(payload: bytes, terrain, cache: Path):
    """Compilateur sans réseau : réponse Overpass et relief fabriqués ; tout est rétabli à la sortie."""
    import urllib.request

    from openride_compiler import cli
    from openride_compiler.elevation import SyntheticProvider
    saved = (socket.socket.connect, socket.create_connection, urllib.request.urlopen, cli.make_provider,
             {k: os.environ.get(k) for k in ("OPENRIDE_DEM_CACHE", "OPENRIDE_OSM_CACHE")})
    os.environ["OPENRIDE_DEM_CACHE"] = str(cache / "dem-cache")
    os.environ["OPENRIDE_OSM_CACHE"] = str(cache / "osm-cache")
    socket.socket.connect = sim.no_network              # type: ignore[method-assign]
    socket.create_connection = sim.no_network           # type: ignore[assignment]
    urllib.request.urlopen = lambda *_a, **_k: io.BytesIO(payload)   # type: ignore[assignment]
    cli.make_provider = lambda offline, log=None: SyntheticProvider(*ORIGIN, terrain)   # type: ignore[assignment]
    try:
        yield cli
    finally:
        socket.socket.connect, socket.create_connection, urllib.request.urlopen, cli.make_provider = saved[:4]
        for k, v in saved[4].items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def generate(out: Path, name: str, biomes: tuple[str, ...], gravel: bool = False, sea: bool = False,
             seed: int = 0) -> dict:
    """Écrit `out/<name>.world` et `out/<name>.json` ; renvoie le résumé (parts des biomes et des surfaces)."""
    unknown = [b for b in biomes if b not in FIRST_MILESTONE]
    if unknown:
        raise ValueError(f"biome hors du premier jalon : {', '.join(unknown)} ({', '.join(TOUR)})")
    plan = Plan(biomes, gravel, sea)
    out.mkdir(parents=True, exist_ok=True)
    frame = Frame()
    op = build_overpass(frame, plan, seed)
    payload = json.dumps({"version": 0.6, "generator": "OpenRide make_biome_world",
                          "osm3s": {"timestamp_osm_base": OSM_DATE}, "elements": op.elements}).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="make_biome_world_") as tmp:
        work = Path(tmp)
        gpx = work / f"{name}.gpx"
        write_gpx(gpx, frame, plan, name)
        with _offline_compiler(payload, make_terrain(plan), work) as cli:
            log = io.StringIO()
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                rc = cli.main(["build", str(gpx), "--out", str(work), "--force",
                               "--layers", "route,terrain," + ",".join(LAYERS)])
        built = work / f"{name}.world"
        if rc != 0 or not built.is_dir():
            raise RuntimeError(f"compilation impossible (code {rc}) : {log.getvalue()[-400:]}")
        world = out / f"{name}.world"
        if world.exists():
            shutil.rmtree(world)
        shutil.move(str(built), str(world))
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    shares = write_biome_layer(world, plan, manifest, route)
    surface = write_surface(plan, manifest, route) if gravel else None
    coast = write_sea(world, plan, manifest, route) if plan.sea else None
    manifest["format_version"] = FORMAT_VERSION
    manifest["created"] = CREATED
    manifest["compiler"] = {"name": "make_biome_world", "version": manifest["compiler"]["version"]}
    (world / "route.json").write_text(json.dumps(route, separators=(",", ":")), encoding="utf-8")
    (world / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    info = {"route": name, "length_m": route["length_m"], "biomes": list(biomes), "shares": shares,
            "surface_pct": surface, "coast": coast, "generated": op.counts,
            "layers": sorted(k for k, v in manifest["layers"].items() if isinstance(v, dict) and v.get("present"))}
    (out / f"{name}.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return info


def write_demo_set(out: Path, seed: int = 0) -> list[dict]:
    """Les quatre parcours de `openride-core demo-biomes` : tour, tour gravel, côte avec mer, alpin."""
    infos = []
    for name, which, gravel, sea in DEMO_SET:
        biomes = TOUR if which == "tour" else (which,) * 3
        infos.append(generate(out, name, biomes, gravel=gravel, sea=sea, seed=seed))
    return infos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="dossier de sortie (créé si besoin)")
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--biome", choices=TOUR, help="un seul biome sur 6 km")
    what.add_argument("--tour", action="store_true", help="les six biomes du premier jalon, 2 km chacun")
    what.add_argument("--demo-set", action="store_true", help="les quatre parcours de demo-biomes")
    parser.add_argument("--gravel", action="store_true", help="un tiers de la route en gravel ou dirt")
    parser.add_argument("--sea", action="store_true", help="côte fictive et mer le long du biome coast")
    parser.add_argument("--name", help="nom du parcours (défaut : biomes-tour ou biomes-<ID>)")
    parser.add_argument("--seed", type=int, default=0, help="graine du placement des bâtiments (défaut 0)")
    args = parser.parse_args(argv)
    try:
        import openride_compiler  # noqa: F401
    except ImportError as exc:
        print(f"make_biome_world : compilateur non installé ({exc}) ; pip install -e compiler", file=sys.stderr)
        return 2
    try:
        if args.demo_set:
            infos = write_demo_set(args.out, args.seed)
        else:
            biomes = TOUR if args.tour else (args.biome,) * 3
            name = args.name or ("biomes-tour" if args.tour else f"biomes-{args.biome}")
            infos = [generate(args.out, name, biomes, gravel=args.gravel, sea=args.sea, seed=args.seed)]
    except (RuntimeError, ValueError) as exc:
        print(f"make_biome_world : {exc}", file=sys.stderr)
        return 1
    for info in infos:
        shares = ", ".join(f"{b} {v:.1f} %" for b, v in info["shares"].items())
        extra = f" ; surfaces {info['surface_pct']}" if info["surface_pct"] else ""
        print(f"make_biome_world : {args.out / (info['route'] + '.world')} ({shares}{extra})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
