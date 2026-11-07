"""Lot U2 : occupation du sol ESA WorldCover (lecture par fenêtre, cache par carré de 0,1°, hors ligne)."""

from __future__ import annotations

import numpy as np
import pytest

from openride_compiler.errors import CompileError
from openride_compiler.landcover import (
    WORLDCOVER_BASE_URL,
    Window,
    WorldCoverSource,
    square_filename,
    square_keys,
    worldcover_tile_name,
)

RES = 0.01   # pixel de la petite tuile de test (la vraie : 1/12 000 de degré)


def write_test_tile(folder, lat_sw=45, lon_sw=6, func=None):
    """Petite tuile WorldCover de 3° × 3° générée ici (GeoTIFF, 300 × 300 pixels de 0,01°)."""
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    n = int(round(3 / RES))
    rows, cols = np.mgrid[0:n, 0:n]
    lat = lat_sw + 3 - (rows + 0.5) * RES
    lon = lon_sw + (cols + 0.5) * RES
    data = (func or (lambda la, lo: np.where(lo < lon_sw + 1.5, 10, 40)))(lat, lon).astype(np.uint8)
    path = folder / f"{worldcover_tile_name(lat_sw, lon_sw)}.tif"
    folder.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", width=n, height=n, count=1, dtype="uint8", crs="EPSG:4326",
                       transform=from_origin(lon_sw, lat_sw + 3, RES, RES), tiled=True,
                       blockxsize=64, blockysize=64) as ds:
        ds.write(data, 1)
    return path


def no_sleep(_s: float) -> None:
    pass


def test_tile_and_square_names() -> None:
    assert worldcover_tile_name(45, 6) == "ESA_WorldCover_10m_2021_v200_N45E006_Map"
    assert worldcover_tile_name(-3, -72) == "ESA_WorldCover_10m_2021_v200_S03W072_Map"
    keys = square_keys(np.array([45.09, -0.05, 45.0]), np.array([6.06, -72.31, 6.0]))
    assert keys.tolist() == [[450, 60], [-1, -724], [450, 60]]
    assert square_filename(450, 60) == "sq_N450_E0060.npz"
    assert square_filename(-1, -724) == "sq_S001_W0724.npz"
    assert WORLDCOVER_BASE_URL.startswith("https://")


def test_window_reads_only_the_square_and_is_cached(tmp_path) -> None:
    tiles = tmp_path / "tuiles"
    write_test_tile(tiles)
    src = WorldCoverSource(cache_dir=tmp_path / "cache", base_url=str(tiles), log=lambda m: None)
    lat = np.array([45.05, 45.05, 46.25])
    lon = np.array([6.05, 7.95, 7.49])
    src.prepare(lat, lon)
    assert src.downloads == 3
    files = sorted(p.name for p in (tmp_path / "cache" / "esa_worldcover_2021").iterdir())
    assert files == ["sq_N450_E0060.npz", "sq_N450_E0079.npz", "sq_N462_E0074.npz"]
    win = src.squares[(450, 60)]
    assert win.data.shape == (10, 10)          # 0,1° seulement, pas la tuile de 3°
    assert src.classes(lat, lon).tolist() == [10, 40, 10]

    # Hors ligne, sans la tuile d'origine : tout vient du cache, aucun accès.
    for p in tiles.iterdir():
        p.unlink()
    again = WorldCoverSource(cache_dir=tmp_path / "cache", base_url=str(tiles), offline=True, log=lambda m: None)
    assert again.classes(lat, lon).tolist() == [10, 40, 10]
    assert again.downloads == 0


def test_missing_tile_is_open_sea_and_remembered(tmp_path) -> None:
    src = WorldCoverSource(cache_dir=tmp_path / "cache", base_url=str(tmp_path / "vide"), log=lambda m: None)
    lat, lon = np.array([40.05]), np.array([-30.05])
    assert src.classes(lat, lon).tolist() == [0]
    assert (tmp_path / "cache" / "esa_worldcover_2021" / "sq_N400_W0301.npz").is_file()
    offline = WorldCoverSource(cache_dir=tmp_path / "cache", offline=True, log=lambda m: None)
    assert offline.classes(lat, lon).tolist() == [0]


def test_offline_without_cache_refuses_clearly(tmp_path) -> None:
    src = WorldCoverSource(cache_dir=tmp_path / "cache", offline=True, log=lambda m: None)
    with pytest.raises(CompileError, match=r"WorldCover absente du cache .*--offline"):
        src.prepare(np.array([45.05]), np.array([6.05]))


def test_network_failure_retries_then_raises(tmp_path) -> None:
    calls = []

    def failing(url, s, w, n, e):
        calls.append(url)
        raise OSError("réseau coupé")

    delays = []
    src = WorldCoverSource(cache_dir=tmp_path / "cache", reader=failing, sleep=delays.append, log=lambda m: None)
    with pytest.raises(CompileError, match="après 3 reprises"):
        src.prepare(np.array([45.05]), np.array([6.05]))
    assert len(calls) == 4 and delays == [2.0, 4.0, 8.0]
    assert calls[0].endswith("/ESA_WorldCover_10m_2021_v200_N45E006_Map.tif")
    assert not (tmp_path / "cache" / "esa_worldcover_2021").exists() or \
        not any((tmp_path / "cache" / "esa_worldcover_2021").iterdir())


def test_reader_gets_the_square_bounds(tmp_path) -> None:
    seen = []

    def reader(url, s, w, n, e):
        seen.append((round(s, 6), round(w, 6), round(n, 6), round(e, 6)))
        return Window(np.full((4, 4), 90, dtype=np.uint8), w, n, 0.025, 0.025)

    src = WorldCoverSource(cache_dir=tmp_path / "cache", reader=reader, sleep=no_sleep, log=lambda m: None)
    assert src.classes(np.array([-0.05]), np.array([-0.05])).tolist() == [90]
    assert seen == [(-0.1, -0.1, 0.0, 0.0)]


@pytest.mark.network
def test_real_worldcover_square(tmp_path) -> None:
    """Lecture réelle d'un carré de 0,1° (Alpes, 45° N 6° E) sur le compartiment public d'ESA."""
    src = WorldCoverSource(cache_dir=tmp_path / "cache")
    lat = np.linspace(45.01, 45.09, 50)
    lon = np.linspace(6.01, 6.09, 50)
    cls = src.classes(lat, lon)
    assert src.squares[(450, 60)].data.shape == (1200, 1200)
    assert set(np.unique(cls).tolist()) <= {0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}
    assert np.count_nonzero(cls) > 40
