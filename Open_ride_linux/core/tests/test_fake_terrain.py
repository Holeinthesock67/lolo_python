"""Couche terrain synthétique du générateur de parcours (lot E1, §4.5 ; Format .world v1, §5)."""

from __future__ import annotations

import json
import math
import struct

import pytest

from openride_core.demo_world import build_route, write_world
from openride_core.tools import fake_world
from openride_core.tools.fake_world import (
    FAR, NEAR, TERRAIN_BELOW_ROAD_M, TILE_SAMPLES, SyntheticTerrain, add_terrain_layer,
)

TILE_BYTES = TILE_SAMPLES * TILE_SAMPLES * 4


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("routes")
    w = write_world(out, "court", 1500.0)
    add_terrain_layer(w)
    return w


def _read_tile(path):
    data = path.read_bytes()
    assert len(data) == TILE_BYTES == 40804
    return struct.unpack(f"<{TILE_SAMPLES * TILE_SAMPLES}f", data)


def test_manifest_declares_terrain(world):
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    terrain = manifest["layers"]["terrain"]
    assert terrain["present"] is True
    assert terrain["near_cell_m"] == 10 and terrain["far_cell_m"] == 50
    for level in ("near", "far"):
        files = sorted(p.name for p in (world / "terrain" / level).glob("tile_*.f32"))
        assert files == sorted(f"tile_{ix}_{iz}.f32" for ix, iz in terrain["tiles"][level])
        assert files


def test_tiles_are_valid_and_share_edges(world):
    for level in ("near", "far"):
        tiles = {}
        for p in (world / "terrain" / level).glob("tile_*.f32"):
            _, ix, iz = p.stem.split("_")
            tiles[(int(ix), int(iz))] = _read_tile(p)
        for (ix, iz), v in tiles.items():
            assert not any(math.isnan(a) for a in v)
            right = tiles.get((ix + 1, iz))
            if right is not None:
                for j in range(TILE_SAMPLES):
                    assert v[j * TILE_SAMPLES + 100] == right[j * TILE_SAMPLES]
            below = tiles.get((ix, iz + 1))
            if below is not None:
                assert v[100 * TILE_SAMPLES:] == below[:TILE_SAMPLES]


def test_terrain_follows_road_then_blends():
    route = build_route(1500.0)
    terrain = SyntheticTerrain(route)
    for i in (5, 40, 90, 140):
        x, z, alt = route["x"][i], route["z"][i], route["alt_m"][i]
        h = math.radians(route["heading_deg"][i])
        right = (math.cos(h), math.sin(h))
        for side in (-1.0, 1.0):
            # À 2 m du bord du ruban (5 m de l'axe) : 5 cm sous la route.
            y = terrain.height(x + side * 5.0 * right[0], z + side * 5.0 * right[1])
            assert y == pytest.approx(alt - TERRAIN_BELOW_ROAD_M, abs=0.05)


def test_relief_is_about_300_m():
    route = build_route(1500.0)
    terrain = SyntheticTerrain(route)
    far_values = [terrain.height(x, z) for x in range(-5000, 6000, 250) for z in range(-6000, 5000, 250)]
    assert 250.0 <= max(far_values) - min(far_values) <= 400.0


def test_tile_selection_matches_extent():
    route = build_route(1500.0)
    terrain = SyntheticTerrain(route)
    near = terrain.tiles_for(NEAR)
    far = terrain.tiles_for(FAR)
    # La route part de (0, 0) : la tuile proche (0, -1) et la lointaine (0, -1) la contiennent.
    assert (0, -1) in near and (0, -1) in far
    # Aucune tuile proche à plus de 400 m de la route.
    for ix, iz in near:
        d = min(math.hypot(max(ix * 1000 - px, 0, px - (ix + 1) * 1000),
                           max(iz * 1000 - pz, 0, pz - (iz + 1) * 1000))
                for px, pz in zip(route["x"], route["z"]))
        assert d <= 400.0


def test_cli_terrain_option(tmp_path):
    fake_world.main(["--out", str(tmp_path), "--name", "cli", "--length", "1200", "--terrain"])
    manifest = json.loads((tmp_path / "cli.world" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["layers"]["terrain"]["present"] is True
    assert list((tmp_path / "cli.world" / "terrain" / "near").glob("tile_*.f32"))


def _mesh_height(tiles, x, z, cell=NEAR[1]):
    """Hauteur du maillage proche en (x, z), découpage de terrain_tiles.gd `mesh_height_at`."""
    cells = TILE_SAMPLES - 1
    gi, gj = math.floor(x / cell), math.floor(z / cell)
    u, v = x / cell - gi, z / cell - gj
    ti, tj = gi // cells, gj // cells
    g = tiles[(ti, tj)]
    i, j = gi - ti * cells, gj - tj * cells
    h = lambda a, b: g[b * TILE_SAMPLES + a]
    if u + v <= 1.0:
        return h(i, j) + u * (h(i + 1, j) - h(i, j)) + v * (h(i, j + 1) - h(i, j))
    return h(i + 1, j + 1) + (1.0 - u) * (h(i, j + 1) - h(i + 1, j + 1)) + (1.0 - v) * (h(i + 1, j) - h(i + 1, j + 1))


def test_near_mesh_stays_under_road_where_grade_changes():
    """7 novembre 2026 : au km 1,74 de la démonstration, la pente passe de 1 % à 3,5 % ; les triangles de 10 m,
    dont les sommets sont 5 cm sous la route, passaient jusqu'à 1 cm au-dessus et le sol recouvrait la chaussée.
    Après `clear_road`, tout point de la chaussée est au moins à 5 cm au-dessus du maillage proche."""
    from openride_core.demo_world import DEMO_LENGTH_M
    from openride_core.synthetic_terrain import build_tiles, road_samples

    route = build_route(DEMO_LENGTH_M)
    samples = road_samples(route)
    terrain = SyntheticTerrain(route)
    raw = {k: terrain.tile_values(NEAR, *k) for k in terrain.tiles_for(NEAR)}
    kink = [(x, z, a) for x, z, a in samples if 1555.0 < x < 1575.0 and -615.0 < z < -600.0]
    assert kink and max(_mesh_height(raw, x, z) - a for x, z, a in kink) > 0.0   # défaut d'avant le garde-fou
    tiles = build_tiles(route, NEAR)
    worst = max(_mesh_height(tiles, x, z) - a for x, z, a in samples)
    assert worst <= -TERRAIN_BELOW_ROAD_M + 1e-3


def test_clear_road_lowers_only_what_is_needed():
    """Sur la démonstration, le garde-fou ne touche que les sommets des triangles qui dépassent (environ 650 sur
    plus de 130 000), de 13 cm au plus."""
    from openride_core.demo_world import DEMO_LENGTH_M
    from openride_core.synthetic_terrain import clear_road

    route = build_route(DEMO_LENGTH_M)
    terrain = SyntheticTerrain(route)
    n = TILE_SAMPLES * TILE_SAMPLES
    before = {k: list(struct.unpack(f"<{n}f", struct.pack(f"<{n}f", *terrain.tile_values(NEAR, *k))))
              for k in terrain.tiles_for(NEAR)}
    after = {k: list(v) for k, v in before.items()}
    lowered = clear_road(after, route)
    assert 0 < lowered < 1000
    drops = [b - a for k in before for b, a in zip(before[k], after[k])]
    assert min(drops) >= 0.0 and max(drops) < 0.2
