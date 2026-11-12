"""Couche biome synthétique du parcours de démonstration « Col du lacet » (lot W17 ; Format .world v1 §8 quater).

Le parcours de démonstration n'a pas de vraie trace : sa couche biome se dessine comme son relief, par une
fonction de la position. Le col, vers 1 200 m dans les Alpes, alterne forêt tempérée et prairies d'alpage
(`temperate_grassland`) en grandes taches ; la part de forêt suit `forest_share(x, z)`. Comme tout le dessin
dépend de la seule position, deux tuiles voisines ont des bords identiques. Bibliothèque standard seulement.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

GRID = 17                       # points par côté d'une tuile de biome (format §8 quater)
TOTAL = 255
FOREST = "temperate_forest"
MEADOW = "temperate_grassland"
LEVEL_SIZE_M = {"near": 1000.0, "far": 5000.0}
BIOME_VERSION = "1.0"


def _smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def forest_share(x: float, z: float) -> float:
    """Part de forêt (0 à 1) : grandes taches de forêt et d'alpage, lisières progressives sur 100 à 200 m."""
    v = (math.sin(x / 450.0 + 1.1) * math.cos(z / 520.0 - 0.4)
         + 0.35 * math.sin((x - z) / 230.0) + 0.15)
    return _smoothstep(0.5 + 1.4 * v)


def tile(level: str, ix: int, iz: int) -> dict:
    """Tuile de biome `(ix, iz)` du niveau `near` ou `far` (dictionnaire prêt pour JSON)."""
    size = LEVEL_SIZE_M[level]
    step = size / (GRID - 1)
    forest = []
    for j in range(GRID):
        for i in range(GRID):
            forest.append(int(round(TOTAL * forest_share(ix * size + i * step, iz * size + j * step))))
    grids = {FOREST: forest, MEADOW: [TOTAL - w for w in forest]}
    used = sorted((b for b in grids if any(grids[b])), key=lambda b: (-sum(grids[b]), b))
    return {"version": BIOME_VERSION, "biomes": used, "grid": GRID, "weights": [grids[b] for b in used],
            "variant": None}


def route_shares(route: dict) -> dict[str, float]:
    """Part (%) de chaque biome le long de la route (`layers.biome.shares`)."""
    xs, zs = route["x"], route["z"]
    if not xs:
        return {}
    f = sum(forest_share(x, z) for x, z in zip(xs, zs)) / len(xs)
    return {b: round(100.0 * p, 1) for b, p in ((FOREST, f), (MEADOW, 1.0 - f)) if p >= 0.0005}


def add_biome_layer(world: Path) -> Path:
    """Écrit biome/near et biome/far pour toutes les tuiles du terrain du manifeste, puis `layers.biome`."""
    manifest_path = world / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    tiles = manifest["layers"]["terrain"]["tiles"]
    for level in ("near", "far"):
        folder = world / "biome" / level
        folder.mkdir(parents=True, exist_ok=True)
        for ix, iz in tiles[level]:
            (folder / f"tile_{ix}_{iz}.json").write_text(
                json.dumps(tile(level, ix, iz), separators=(",", ":")), encoding="utf-8")
    manifest["layers"]["biome"] = {
        "present": True, "version": BIOME_VERSION, "default_biome": MEADOW, "forced": None,
        "sources": ["synthetic"], "shares": route_shares(route),
        "tiles": {"near": tiles["near"], "far": tiles["far"]},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return world
