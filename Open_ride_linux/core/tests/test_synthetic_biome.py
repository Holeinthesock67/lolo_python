"""Couche biome synthétique de « Col du lacet » (lot W17) : tuiles valides, bords communs, embarquée par l'engine."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from openride_core import synthetic_biome as SB
from openride_core.demo_world import write_demo_world

ROOT = Path(__file__).resolve().parents[2]
ENGINE_DEMO = ROOT / "engine" / "demo" / "demo.world"
SCHEMA = json.loads((ROOT / "docs" / "contracts" / "world" / "biome.schema.json").read_text(encoding="utf-8"))


def test_tiles_sum_to_255_and_share_edges() -> None:
    for level in ("near", "far"):
        a, b = SB.tile(level, 0, 0), SB.tile(level, 1, 0)
        for t in (a, b):
            jsonschema.validate(t, SCHEMA)
            assert all(sum(g[p] for g in t["weights"]) == 255 for p in range(17 * 17))
        ga, gb = dict(zip(a["biomes"], a["weights"])), dict(zip(b["biomes"], b["weights"]))
        for name in set(ga) | set(gb):
            east = [ga.get(name, [0] * 289)[j * 17 + 16] for j in range(17)]
            west = [gb.get(name, [0] * 289)[j * 17] for j in range(17)]
            assert east == west, (level, name)


def test_demo_has_forest_away_from_the_road_and_engine_copy_is_identical(tmp_path) -> None:
    world = write_demo_world(tmp_path)
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    layer = manifest["layers"]["biome"]
    assert layer["present"] and layer["tiles"] == manifest["layers"]["terrain"]["tiles"]
    assert layer["shares"] == {"alpine": 100.0}   # la route passe en alpage
    forest = [t for t in (json.loads(p.read_text()) for p in (world / "biome").rglob("*.json"))
              if "temperate_forest" in t["biomes"]]
    assert forest, "forêt à l'écart de la route"
    for path in sorted((world / "biome").rglob("*.json")):
        assert path.read_bytes() == (ENGINE_DEMO / path.relative_to(world)).read_bytes(), path.name
