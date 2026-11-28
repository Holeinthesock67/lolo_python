"""Monde d'essai des tunnels (lot EA5, `engine/tests/make_tunnel_world.py`, `sim_bench.py --world tunnel`) : un
tunnel de 300 m, route au niveau du plan d'un portail à l'autre, crête gardée au-dessus, `.world` valide."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from openride_compiler import constants as C
from openride_compiler.terrain import load_terrain_tiles
from openride_compiler.verify import verify_world

SCRIPT = Path(__file__).resolve().parents[2] / "engine" / "tests" / "make_tunnel_world.py"


def test_make_tunnel_world(tmp_path: Path) -> None:
    subprocess.run([sys.executable, str(SCRIPT), "--out", str(tmp_path)], check=True, capture_output=True)
    world = tmp_path / "tunnel-essai.world"
    info = json.loads((world / "manifest.json").read_text(encoding="utf-8"))["layers"]["tunnels"]
    assert info["count"] == 1
    (s0, s1), = info["spans"]
    assert abs(s0 - 1350.0) <= 10.0 and abs(s1 - 1650.0) <= 10.0
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    s = np.arange(len(route["alt_m"])) * route["ds_m"]
    assert np.allclose(np.asarray(route["alt_m"]), 1000.0 + 0.05 * s, atol=0.5)   # ni montée ni descente au tunnel
    tiles = load_terrain_tiles(world)["near"]
    iz = int(np.floor(-1500.0 / C.NEAR_TILE_M))
    j = int(round((-1500.0 - iz * C.NEAR_TILE_M) / C.NEAR_CELL_M))
    assert float(tiles[(0, iz)][j, 0]) > 1075.0 + 40.0                               # crête gardée au-dessus
    assert verify_world(world) == []
