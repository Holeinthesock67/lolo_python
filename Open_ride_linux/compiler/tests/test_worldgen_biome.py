"""Couche biome du monde ouvert (lot W17) : tuiles par carré et par tuile lointaine, cache, WorldCover."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from openride_compiler import biomes as B
from openride_compiler.landcover import WORLDCOVER_NAME, Window, WorldCoverSource
from openride_compiler.verify import biome_tile_problems
from openride_compiler.worldgen import biome_tiles
from openride_compiler.worldgen.osmdb import OsmDb
from openride_compiler.worldgen.squares import FarKey, SquareKey
from openride_compiler.worldgen.store import WorldCache
from test_worldgen_process import (E_REF, FRAME, N_REF, ZONE, Relief, grid_db, open_msg, session, validator)


@pytest.fixture(scope="module")
def grid(tmp_path_factory) -> Path:
    return grid_db(tmp_path_factory.mktemp("grille_biome") / "grille.sqlite")


def forest_reader(calls: list | None = None):
    """WorldCover factice : arbres partout (classe 10), sans réseau."""
    def read(url, south, west, north, east):
        if calls is not None:
            calls.append((south, west))
        return Window(np.full((8, 8), B.TREES, dtype=np.uint8), west, north, (east - west) / 8, (north - south) / 8)
    return read


def worldcover(tmp_path: Path, offline: bool = False, calls: list | None = None) -> WorldCoverSource:
    return WorldCoverSource(cache_dir=tmp_path / "landcover", offline=offline, reader=forest_reader(calls),
                            sleep=lambda s: None, log=lambda m: None)


def test_session_links_one_biome_tile_per_terrain_tile(grid, tmp_path) -> None:
    s, _rec = session(tmp_path, grid)
    s.handle(open_msg())
    d = tmp_path / "seance.world"
    manifest = json.loads((d / "manifest.json").read_text())
    validator("manifest.schema.json").validate(manifest)
    layer = manifest["layers"]["biome"]
    assert layer["present"] and layer["forced"] is None and layer["default_biome"] == B.DEFAULT_BIOME
    assert "osm" in layer["sources"] and "koppen_1986_2010" in layer["sources"]
    live = json.loads((d / "live.json").read_text())
    tile_schema = validator("biome.schema.json")
    for level in ("near", "far"):
        for ix, iz in live["tiles"][level]:
            link = d / "biome" / level / f"tile_{ix}_{iz}.json"
            assert link.is_symlink(), link
            tile = json.loads(link.read_text())
            tile_schema.validate(tile)
            assert biome_tile_problems(tile) == []
    # Sans WorldCover ni forêt OSM, en zone tempérée : prairie tempérée (le biome de la zone).
    ix, iz = live["tiles"]["near"][0]
    tile = json.loads((d / "biome" / "near" / f"tile_{ix}_{iz}.json").read_text())
    assert tile["biomes"][0] == "temperate_grassland"


def test_tile_matches_the_compiler_rule_and_neighbours_share_edges(tmp_path) -> None:
    """Même règle que le compilateur : la tuile d'un carré seul vaut celle d'un calcul d'ensemble ; les bords
    communs de deux carrés calculés séparément sont identiques (moins de cinq biomes par tuile)."""
    provider = Relief()
    a = SquareKey.at(ZONE, E_REF + 10, N_REF + 10)
    b = SquareKey(ZONE, a.ix + 1, a.i_n)

    def lc(lat, lon):   # forêt à l'ouest d'une longitude, cultures à l'est : une lisière dans le carré a
        _, lon_cut = FRAME.to_latlon(np.array([a.corner[0] + 700.0]), np.array([a.corner[1] + 500.0]))
        return np.where(np.asarray(lon) < float(lon_cut[0]), B.TREES, B.CROP).astype(np.uint8)

    class Source:
        name = WORLDCOVER_NAME
        classes = staticmethod(lc)

    ta = biome_tiles.compute_tile(a, FRAME, provider, Source())
    tb = biome_tiles.compute_tile(b, FRAME, provider, Source())
    inputs = B.Inputs(to_latlon=FRAME.to_latlon, landcover=lc, elevation=provider.elevations)
    batch = B.classify_level([biome_tiles.tile_index(a), biome_tiles.tile_index(b)], B.NEAR, inputs, salt=0)
    for key, tile in ((a, ta), (b, tb)):
        ref = batch[biome_tiles.tile_index(key)]
        assert tile["biomes"] == ref["biomes"] and tile["weights"] == ref["weights"]
    assert set(ta["biomes"]) >= {"temperate_forest", "farmland"}
    ga = {n: np.asarray(g).reshape(17, 17) for n, g in zip(ta["biomes"], ta["weights"])}
    gb = {n: np.asarray(g).reshape(17, 17) for n, g in zip(tb["biomes"], tb["weights"])}
    for n in set(ga) | set(gb):
        east_a = ga[n][:, -1] if n in ga else np.zeros(17)
        west_b = gb[n][:, 0] if n in gb else np.zeros(17)
        assert np.array_equal(east_a, west_b), n
    assert ta["variant"] is not None    # variante régionale au centre de la tuile (lot U4)


def test_far_tile_and_cache_entries(tmp_path) -> None:
    cache = WorldCache(tmp_path / "cache", 10**10, log=lambda m: None)
    key = FarKey.at(ZONE, E_REF, N_REF)
    path = biome_tiles.generate(key, FRAME, Relief(), cache)
    tile = json.loads(path.read_text())
    assert biome_tile_problems(tile) == []
    entry = cache.get(cache.biome_key(ZONE, "far", key.ix, key.i_n))
    assert entry.kind == "biome" and entry.versions["landcover"] == biome_tiles.ABSENT
    assert path == cache.biome_path(ZONE, "far", key.ix, key.i_n)
    # Index reconstruit depuis le disque : l'entrée revient ; nettoyage des données générées : elle part.
    cache.db.execute("DELETE FROM entries")
    assert cache.rebuild() == 1 and cache.get(cache.biome_key(ZONE, "far", key.ix, key.i_n)) is not None
    assert cache.clean() == [cache.biome_key(ZONE, "far", key.ix, key.i_n)] and not path.exists()


def test_worldcover_at_opening_then_cache_only(grid, tmp_path) -> None:
    """À l'ouverture, WorldCover se lit (réseau) ; ensuite seul le cache sert, et une tuile faite sans
    WorldCover est refaite dès que la donnée est là."""
    calls: list = []
    lc = worldcover(tmp_path, calls=calls)
    s, _rec = session(tmp_path, grid)
    s.landcover = lc
    s.handle(open_msg())
    assert calls, "WorldCover lu pour le départ"
    d = tmp_path / "seance.world"
    manifest = json.loads((d / "manifest.json").read_text())
    assert manifest["layers"]["biome"]["sources"][0] == WORLDCOVER_NAME
    assert "attribution" in manifest["layers"]["biome"]
    live = json.loads((d / "live.json").read_text())
    ix, iz = live["tiles"]["near"][0]
    tile = json.loads((d / "biome" / "near" / f"tile_{ix}_{iz}.json").read_text())
    assert tile["biomes"][0] == "temperate_forest"

    # Après l'ouverture : un carré dont le WorldCover manque est fait sans lui, sans téléchargement.
    cache = s.cache
    far_away = SquareKey.at(ZONE, E_REF + 60_000, N_REF)
    before = len(calls)
    path = biome_tiles.generate(far_away, FRAME, Relief(), cache, worldcover(tmp_path, offline=True), network=False)
    assert len(calls) == before
    ckey = cache.biome_key(ZONE, "near", far_away.ix, far_away.i_n)
    assert cache.get(ckey).versions["landcover"] == biome_tiles.ABSENT
    assert json.loads(path.read_text())["biomes"][0] == "temperate_grassland"
    # Le fil de préchargement apporte la donnée : la tuile est refaite avec la forêt.
    worldcover(tmp_path, calls=calls).prepare(*biome_tiles.coverage_latlon(far_away, FRAME))
    biome_tiles.generate(far_away, FRAME, Relief(), cache, worldcover(tmp_path, offline=True), network=False)
    assert cache.get(ckey).versions["landcover"] == WORLDCOVER_NAME
    assert json.loads(path.read_text())["biomes"][0] == "temperate_forest"


def test_osm_orchard_corrects_the_landcover(tmp_path) -> None:
    from openride_compiler.worldgen.osmdb import OsmDbWriter
    from test_worldgen_process import lonlat
    key = SquareKey.at(ZONE, E_REF + 10, N_REF + 10)
    e0, n0 = key.ix * 1000, key.i_n * 1000
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/vergers")
    ring = [lonlat(e0 - 300, n0 - 300), lonlat(e0 + 1300, n0 - 300), lonlat(e0 + 1300, n0 + 1300),
            lonlat(e0 - 300, n0 + 1300), lonlat(e0 - 300, n0 - 300)]
    w.add_area("w1", "orchard", {"landuse": "orchard"}, ring)
    w.finish(osm_date="2026-10-20T00:00:00Z")
    db = OsmDb(tmp_path / "osm.sqlite")
    assert [a.cls for a in biome_tiles.osm_areas(key, db, FRAME)] == [B.CROP]
    tile = biome_tiles.compute_tile(key, FRAME, Relief(), None, db)
    assert tile["biomes"] == ["farmland"]
    assert biome_tiles.compute_tile(key, FRAME, Relief(), None, None)["biomes"] == ["temperate_grassland"]
