"""Lot B2 : fournisseurs d'altitude, cache brut et téléchargements (sans réseau, sauf `-m network`)."""

from __future__ import annotations

import io
import json
import time
import urllib.error

import numpy as np
import pytest

from openride_compiler import cache
from openride_compiler.cache import Downloader, NotFoundError, dem_cache_dir
from openride_compiler.elevation import (CopernicusGlo30Provider, IgnRgeAltiProvider,
                                         SyntheticProvider, copernicus_tile_name)
from openride_compiler.errors import CompileError

TILE_N45_E006 = "Copernicus_DSM_COG_10_N45_00_E006_00_DEM"


# Nommage et cache --------------------------------------------------------------------------------

def test_tile_names():
    assert copernicus_tile_name(45, 6) == TILE_N45_E006
    assert copernicus_tile_name(-34, 18) == "Copernicus_DSM_COG_10_S34_00_E018_00_DEM"
    assert copernicus_tile_name(0, -1) == "Copernicus_DSM_COG_10_N00_00_W001_00_DEM"
    assert copernicus_tile_name(-1, -180) == "Copernicus_DSM_COG_10_S01_00_W180_00_DEM"


def test_cache_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENRIDE_DEM_CACHE", str(tmp_path / "x"))
    assert dem_cache_dir() == tmp_path / "x"
    monkeypatch.delenv("OPENRIDE_DEM_CACHE")
    assert str(dem_cache_dir()).endswith(".cache/openride/dem")


def test_ign_is_a_placeholder():
    with pytest.raises(NotImplementedError):
        IgnRgeAltiProvider()


# Téléchargements ----------------------------------------------------------------------------------

class FakeHttp:
    """Remplace urllib.request.urlopen : liste de réponses (octets ou exception) consommées dans l'ordre."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, url, timeout=None):
        self.calls.append((url, timeout))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(answer)


def http_error(code):
    return urllib.error.HTTPError("http://x", code, "erreur", {}, None)


@pytest.fixture
def fake_http(monkeypatch):
    def install(answers):
        fake = FakeHttp(answers)
        monkeypatch.setattr(cache.urllib.request, "urlopen", fake)
        return fake
    return install


def downloader(**kw):
    sleeps = []
    d = Downloader(log=lambda m: None, sleep=sleeps.append, **kw)
    return d, sleeps


def test_download_retries_with_growing_delay(fake_http, tmp_path):
    fake = fake_http([urllib.error.URLError("coupure"), TimeoutError("lent"), http_error(503), b"donnees"])
    d, sleeps = downloader()
    dest = tmp_path / "a" / "f.tif"
    assert d.fetch("http://x/f.tif", dest) == dest
    assert dest.read_bytes() == b"donnees"
    assert sleeps == [2.0, 4.0, 8.0]
    assert all(timeout == 60.0 for _, timeout in fake.calls)
    assert d.downloads == 1 and d.bytes == 7
    assert [p.name for p in dest.parent.iterdir()] == ["f.tif"]


def test_download_gives_up_after_3_retries(fake_http, tmp_path):
    fake_http([urllib.error.URLError("coupure")] * 4)
    d, sleeps = downloader()
    with pytest.raises(CompileError, match="après 3 reprises"):
        d.fetch("http://x/f.tif", tmp_path / "f.tif")
    assert len(sleeps) == 3
    assert list(tmp_path.iterdir()) == []


def test_download_404_not_retried(fake_http, tmp_path):
    fake = fake_http([http_error(404)])
    d, sleeps = downloader()
    with pytest.raises(NotFoundError):
        d.fetch("http://x/f.tif", tmp_path / "f.tif")
    assert len(fake.calls) == 1 and sleeps == []


def test_cached_file_never_downloaded_again(fake_http, tmp_path):
    fake = fake_http([])
    (tmp_path / "f.tif").write_bytes(b"deja")
    d, _ = downloader()
    d.fetch("http://x/f.tif", tmp_path / "f.tif")
    assert fake.calls == []


def test_offline_refuses_missing_file(fake_http, tmp_path):
    fake = fake_http([])
    d, _ = downloader(offline=True)
    with pytest.raises(CompileError, match="--offline"):
        d.fetch("http://x/f.tif", tmp_path / "f.tif", "tuile X")
    assert fake.calls == []


# Copernicus avec une tuile factice locale -----------------------------------------------------------

def write_fake_tile(path, lat_sw, lon_sw, size=361, func=None):
    """GeoTIFF au même géoréférencement que Copernicus (pixels centrés sur la grille), maille réduite."""
    import rasterio
    from rasterio.transform import Affine

    res = 1.0 / (size - 1)
    rows, cols = np.mgrid[0:size - 1, 0:size - 1]
    lat = lat_sw + 1.0 - rows * res
    lon = lon_sw + cols * res
    data = (func or (lambda la, lo: 1000.0 + 100.0 * (la - lat_sw) + 50.0 * (lo - lon_sw)))(lat, lon)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=size - 1, width=size - 1, count=1,
                       dtype="float32", crs="EPSG:4326",
                       transform=Affine(res, 0.0, lon_sw - res / 2, 0.0, -res, lat_sw + 1.0 + res / 2)) as ds:
        ds.write(data.astype("float32"), 1)


@pytest.fixture
def copernicus_cache(tmp_path):
    root = tmp_path / "dem"
    d = root / "copernicus_glo30"
    write_fake_tile(d / f"{TILE_N45_E006}.tif", 45, 6)
    (d / "tileList.txt").write_text(f"{TILE_N45_E006}\nCopernicus_DSM_COG_10_N46_00_E006_00_DEM\n")
    return root


def test_copernicus_bilinear_on_plane(copernicus_cache):
    p = CopernicusGlo30Provider(cache_dir=copernicus_cache, offline=True, log=lambda m: None)
    lats = np.array([45.09, 45.5, 45.123456, 45.9])
    lons = np.array([6.06, 6.5, 6.987654, 6.01])
    expected = 1000.0 + 100.0 * (lats - 45) + 50.0 * (lons - 6)
    assert np.allclose(p.elevations(lats, lons), expected, atol=1e-3)


def test_copernicus_sea_tile_is_zero_and_missing_tile_offline(copernicus_cache):
    p = CopernicusGlo30Provider(cache_dir=copernicus_cache, offline=True, log=lambda m: None)
    assert p.elevations(np.array([44.5]), np.array([6.5]))[0] == 0.0          # absente de la liste : mer
    with pytest.raises(CompileError, match="--offline"):
        p.elevations(np.array([46.5]), np.array([6.5]))                       # listée, pas en cache


def test_copernicus_downloads_once(copernicus_cache, fake_http, tmp_path):
    other = tmp_path / "src.tif"
    write_fake_tile(other, 46, 6, func=lambda la, lo: 0 * la + 1234.0)
    fake = fake_http([other.read_bytes()])
    p = CopernicusGlo30Provider(cache_dir=copernicus_cache, log=lambda m: None,
                                downloader=Downloader(log=lambda m: None, sleep=lambda s: None))
    assert p.elevations(np.array([46.5]), np.array([6.5]))[0] == pytest.approx(1234.0)
    name = "Copernicus_DSM_COG_10_N46_00_E006_00_DEM"
    assert fake.calls[0][0].endswith(f"/{name}/{name}.tif")
    p2 = CopernicusGlo30Provider(cache_dir=copernicus_cache, offline=True, log=lambda m: None)
    assert p2.elevations(np.array([46.5]), np.array([6.5]))[0] == pytest.approx(1234.0)
    assert len(fake.calls) == 1


def test_corrupt_cached_tile(copernicus_cache):
    (copernicus_cache / "copernicus_glo30" / f"{TILE_N45_E006}.tif").write_bytes(b"pas un tiff")
    p = CopernicusGlo30Provider(cache_dir=copernicus_cache, offline=True, log=lambda m: None)
    with pytest.raises(CompileError, match="illisible"):
        p.elevations(np.array([45.5]), np.array([6.5]))


def test_synthetic_provider_in_route_frame():
    p = SyntheticProvider(45.09, 6.06, lambda x, z: x - 2 * z)
    from openride_compiler.frame import LocalFrame
    lat, lon = LocalFrame.at(45.09, 6.06).to_latlon(np.array([100.0]), np.array([-50.0]))
    assert p.elevations(lat, lon)[0] == pytest.approx(200.0, abs=1e-6)


def test_tests_have_no_network():
    import socket
    with pytest.raises(OSError):
        socket.create_connection(("copernicus-dem-30m.s3.amazonaws.com", 443), timeout=1)


# Intégration réseau (Copernicus réel) : `pytest -m network` -------------------------------------------

@pytest.mark.network
def test_real_copernicus_build_then_offline(tmp_path, monkeypatch):
    from conftest import gpx_text
    from openride_compiler import cli

    monkeypatch.setenv("OPENRIDE_DEM_CACHE", str(tmp_path / "dem"))
    # 3 km au nord de Bourg-d'Oisans (tuile N45E006, loin de ses bords), sans altitude.
    lat = np.linspace(45.40, 45.427, 200)
    lon = np.full(200, 6.40)
    gpx = tmp_path / "reel.gpx"
    gpx.write_text(gpx_text(lat, lon), encoding="utf-8")
    t0 = time.monotonic()
    assert cli.main(["build", str(gpx), "--out", str(tmp_path / "routes")]) == 0
    first = time.monotonic() - t0
    world = tmp_path / "routes" / "reel.world"
    assert cli.main(["verify", str(world)]) == 0
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["route"]["alt_source"] == "copernicus_glo30"
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    assert 200.0 < min(route["alt_m"]) and max(route["alt_m"]) < 4000.0

    t0 = time.monotonic()
    assert cli.main(["build", str(gpx), "--out", str(tmp_path / "routes"), "--force", "--offline"]) == 0
    print(f"première passe {first:.1f} s, seconde (hors ligne) {time.monotonic() - t0:.1f} s")
