"""Cache local du monde ouvert (lot W2), sans réseau."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from openride_compiler import cli
from openride_compiler.errors import CompileError
from openride_compiler.worldgen.store import WorldCache, read_open_world_config


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def write(path: Path, nbytes: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * nbytes)
    return path


def square(cache: WorldCache, ix: int, nbytes: int = 300_000, **kw):
    d = cache.square_dir("31T", ix, 4890)
    write(d / "near.f32", nbytes)
    return cache.add(cache.square_key("31T", ix, 4890), "square", d, {"worldgen": 1}, **kw)


@pytest.fixture
def cache(tmp_path) -> WorldCache:
    return WorldCache(tmp_path / "monde", 1_000_000, clock=Clock(), dem_dir=tmp_path / "dem", log=lambda _: None)


def test_eviction_lru_sous_le_plafond(cache) -> None:
    keys = [square(cache, ix).key for ix in range(5)]
    assert cache.total_bytes() == 1_500_000
    removed = cache.evict()
    assert removed == keys[:2]
    assert cache.total_bytes() == 900_000 <= cache.max_bytes
    assert not cache.square_dir("31T", 0, 4890).exists() and cache.square_dir("31T", 4, 4890).exists()


def test_epingle_et_en_cours_d_usage_jamais_supprimes(cache) -> None:
    cache.pin("provence", True)
    a = square(cache, 0, region="provence").key          # épinglé (région épinglée)
    b = square(cache, 1).key                              # utilisé par la séance
    c = square(cache, 2).key
    d = square(cache, 3).key
    removed = cache.evict(in_use=[b])
    assert a not in removed and b not in removed
    assert removed == [c]
    assert cache.get(d) is not None and cache.total_bytes() == 900_000


def test_ordre_d_eviction(cache) -> None:
    raw = write(cache.root / "brut" / "tuiles" / "14" / "1" / "2.mvt", 300_000)
    tile = cache.add("tile:14/1/2", "tile", raw).key                       # le plus ancien, mais brut
    pre = square(cache, 0, prefetch=True).key                              # préchargé : en dernier
    sq1 = square(cache, 1).key
    sq2 = square(cache, 2).key
    far = write(cache.far_path("31T", 135, 978), 300_000)
    far_key = cache.add(cache.far_key("31T", 135, 978), "far", far).key
    cache.max_bytes = 0
    removed = cache.evict()
    assert removed == [sq1, sq2, far_key, tile, pre]


def test_mark_used_retire_le_prechargement(cache) -> None:
    k = square(cache, 0, prefetch=True).key
    cache.mark_used(k)
    assert cache.get(k).prefetch is False


def test_relief_du_compilateur_relu_sans_copie(cache, tmp_path) -> None:
    shared = write(tmp_path / "dem" / "Copernicus_DSM_COG_10_N44_00_E005_00_DEM.tif", 1000)
    assert cache.dem_path(44, 5) == shared
    assert cache.dem_path(45, 5).parent == cache.root / "brut" / "dem"
    assert not (cache.root / "brut" / "dem").exists()
    for ix in range(5):
        square(cache, ix)
    cache.max_bytes = 0
    cache.evict()
    assert shared.is_file()
    with pytest.raises(ValueError):
        cache.add("dem:externe", "dem", shared)


def test_versions_et_reconstruction(tmp_path) -> None:
    root = tmp_path / "monde"
    c = WorldCache(root, 10**9, clock=Clock(), log=lambda _: None)
    d = c.square_dir("31T", 7, 4890)
    write(d / "near.f32", 40_804)
    (d / "meta.json").write_text(json.dumps({"versions": {"worldgen": 1, "osm": "2026-10-25"}}))
    k = c.add(c.square_key("31T", 7, 4890), "square", d, {"worldgen": 1, "osm": "2026-10-25"}).key
    write(root / "brut" / "tuiles" / "14" / "8443" / "5843.mvt", 1234)
    c.add("tile:14/8443/5843", "tile", root / "brut" / "tuiles" / "14" / "8443" / "5843.mvt")
    assert c.is_valid(k, {"worldgen": 1, "osm": "2026-10-25"})
    assert not c.is_valid(k, {"worldgen": 2, "osm": "2026-10-25"})
    sizes = {e.key: e.bytes for e in c.entries()}
    c.close()

    for suffix in ("", "-wal", "-shm"):
        Path(f"{root / 'index.sqlite'}{suffix}").unlink(missing_ok=True)
    c2 = WorldCache(root, 10**9, log=lambda _: None)
    assert {e.key: e.bytes for e in c2.entries()} == sizes
    assert c2.is_valid(k, {"worldgen": 1, "osm": "2026-10-25"})
    c2.close()

    (root / "index.sqlite").write_bytes(b"pas une base sqlite" * 100)
    for suffix in ("-wal", "-shm"):
        Path(f"{root / 'index.sqlite'}{suffix}").unlink(missing_ok=True)
    c3 = WorldCache(root, 10**9, log=lambda _: None)
    assert {e.key: e.bytes for e in c3.entries()} == sizes


def test_liens_vers_la_seance(cache, tmp_path) -> None:
    e0, n0 = 675_000.0, 4_890_000.0
    gx, gn = WorldCache.global_index(e0, n0, 2, -1)
    assert (gx, gn) == (677, 4890)
    d = cache.square_dir("31T", gx, gn)
    write(d / "near.f32", 40_804)
    (d / "buildings.json").write_text('{"version": "1.0", "buildings": []}')
    session = tmp_path / "seance.world"
    links = cache.link_square(session, "31T", e0, n0, 2, -1)
    assert sorted(str(p.relative_to(session)) for p in links) == ["buildings/tile_2_-1.json",
                                                                  "terrain/near/tile_2_-1.f32"]
    assert (session / "terrain" / "near" / "tile_2_-1.f32").resolve() == (d / "near.f32").resolve()
    far = write(cache.far_path("31T", *WorldCache.global_index(e0, n0, 0, -1, 5000)), 40_804)
    link = cache.link_far(session, "31T", e0, n0, 0, -1)
    assert link is not None and os.path.realpath(link) == os.path.realpath(far)
    assert cache.link_far(session, "31T", e0, n0, 3, 3) is None


def test_regions(cache) -> None:
    cache.set_region("provence", "Provence-Alpes-Côte d'Azur", [4.2, 42.9, 7.7, 45.2])
    square(cache, 0, region="provence")
    cache.pin("provence")
    (r,) = cache.regions()
    assert r == {"id": "provence", "name": "Provence-Alpes-Côte d'Azur", "pinned": True,
                 "bbox": [4.2, 42.9, 7.7, 45.2], "bytes": 300_000, "last_used": r["last_used"]}
    cache.pin("provence", False)
    assert cache.regions()[0]["pinned"] is False and not any(e.pinned for e in cache.entries())


def test_configuration(tmp_path) -> None:
    cfg = tmp_path / "config.toml"
    assert read_open_world_config(cfg)["cache_max_gb"] == 5.0
    cfg.write_text('[open_world]\ncache_dir = "/tmp/x"\ncache_max_gb = 2\n')
    assert read_open_world_config(cfg)["cache_dir"] == "/tmp/x"
    cfg.write_text("[open_world]\ncache_max_gb = -1\n")
    with pytest.raises(CompileError, match="cache_max_gb"):
        read_open_world_config(cfg)


def test_cache_info_et_clean_en_ligne_de_commande(tmp_path, capsys) -> None:
    root = tmp_path / "monde"
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[open_world]\ncache_dir = "{root}"\ncache_max_gb = 1\n')
    c = WorldCache(root, 10**9, log=lambda _: None)
    for ix in range(3):
        square(c, ix)
    raw = write(root / "brut" / "osm" / "provence.sqlite", 5000)
    c.add("osm:provence", "osm", raw, region="provence")
    c.close()

    assert cli.main(["cache-info", "--config", str(cfg)]) == 0
    out = capsys.readouterr().out
    assert "carrés générés" in out and "région provence" in out and "sur 1.00 Go" in out
    assert cli.main(["cache-info", "--config", str(cfg), "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["count"]["square"] == 3 and info["by_kind"]["osm"] == 5000

    assert cli.main(["cache-clean", "--config", str(cfg), "--yes"]) == 0
    assert "3 entrée(s) supprimée(s)" in capsys.readouterr().out
    assert raw.is_file() and not any((root / "genere").rglob("near.f32"))
