"""Couche biome synthétique du parcours de démonstration « Col du lacet » (lot W17 ; Format .world v1 §8 quater).

Le parcours de démonstration n'a pas de vraie trace : sa couche biome se dessine comme son relief, par une
fonction de la position. Le col, vers 1 200 m dans les Alpes, alterne forêt tempérée et alpages (`alpine`, le
biome au look du parcours de démonstration : sapins, herbe et roche d'avant la couche biome) en grandes taches ;
la part de forêt suit `forest_share(x, z)`, et la route passe en alpage : pas de forêt à moins de 60 m d'elle,
pleine forêt possible au-delà de 150 m (vue dégagée sur le col, comme avant, et ciel visible au-dessus de la
route). Comme tout le dessin dépend de la seule position (et de la route, la même pour toutes les tuiles), deux
tuiles voisines ont des bords identiques. Bibliothèque standard seulement.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable

from .synthetic_terrain import SyntheticTerrain

GRID = 17                       # points par côté d'une tuile de biome (format §8 quater)
TOTAL = 255
FOREST = "temperate_forest"
MEADOW = "alpine"              # look d'avant la couche biome autour de la route (validé le 30 octobre)
LEVEL_SIZE_M = {"near": 1000.0, "far": 5000.0}
BIOME_VERSION = "1.0"
CLEAR_M = (60.0, 150.0)         # forêt écartée de la route : nulle en deçà, entière au-delà


def _smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def forest_share(x: float, z: float) -> float:
    """Part de forêt (0 à 1) : grandes taches de forêt et d'alpage, lisières progressives sur 100 à 200 m."""
    v = (math.sin(x / 450.0 + 1.1) * math.cos(z / 520.0 - 0.4)
         + 0.35 * math.sin((x - z) / 230.0) + 0.15)
    return _smoothstep(0.5 + 1.4 * v)


def clearing(distance_m: float) -> float:
    """Part de la forêt gardée à `distance_m` de la route (0 près d'elle, 1 loin)."""
    return _smoothstep((distance_m - CLEAR_M[0]) / (CLEAR_M[1] - CLEAR_M[0]))


def tile(level: str, ix: int, iz: int, road_distance: Callable[[float, float], float] | None = None) -> dict:
    """Tuile de biome `(ix, iz)` du niveau `near` ou `far` (dictionnaire prêt pour JSON) ; `road_distance(x, z)` :
    distance à la route (sans elle, aucune clairière)."""
    size = LEVEL_SIZE_M[level]
    step = size / (GRID - 1)
    forest = []
    for j in range(GRID):
        for i in range(GRID):
            x, z = ix * size + i * step, iz * size + j * step
            share = forest_share(x, z) * (clearing(road_distance(x, z)) if road_distance is not None else 1.0)
            forest.append(int(round(TOTAL * share)))
    grids = {FOREST: forest, MEADOW: [TOTAL - w for w in forest]}
    used = sorted((b for b in grids if any(grids[b])), key=lambda b: (-sum(grids[b]), b))
    return {"version": BIOME_VERSION, "biomes": used, "grid": GRID, "weights": [grids[b] for b in used],
            "variant": None}


def route_shares(route: dict) -> dict[str, float]:
    """Part (%) de chaque biome le long de la route (`layers.biome.shares`) : alpage, la route y passe toujours."""
    return {MEADOW: 100.0} if route["x"] else {}


def add_biome_layer(world: Path) -> Path:
    """Écrit biome/near et biome/far pour toutes les tuiles du terrain du manifeste, puis `layers.biome`."""
    manifest_path = world / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    tiles = manifest["layers"]["terrain"]["tiles"]
    terrain = SyntheticTerrain(route)
    for level in ("near", "far"):
        folder = world / "biome" / level
        folder.mkdir(parents=True, exist_ok=True)
        for ix, iz in tiles[level]:
            (folder / f"tile_{ix}_{iz}.json").write_text(
                json.dumps(tile(level, ix, iz, terrain._lattice_distance), separators=(",", ":")), encoding="utf-8")
    manifest["layers"]["biome"] = {
        "present": True, "version": BIOME_VERSION, "default_biome": MEADOW, "forced": None,
        "sources": ["synthetic"], "shares": route_shares(route),
        "tiles": {"near": tiles["near"], "far": tiles["far"]},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return world
