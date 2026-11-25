"""Lot RL1 : relief au sol nu FABDEM (tuiles lues dans les archives de 10° par requêtes partielles), repli Copernicus.

Faux serveur HTTP local (boucle locale permise par conftest) : archives `.zip` de GeoTIFF synthétiques, avec ou sans
`Range`. Aucun lieu réel : relief analytique et coordonnées entières quelconques.
"""

from __future__ import annotations

import io
import re
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

from openride_compiler import remote_zip
from openride_compiler.elevation import (FabdemProvider, fabdem_tile_name, fabdem_zip_names, provider_for)
from openride_compiler.cache import NotFoundError

PIX = 60   # pixels par degré des tuiles d'essai


def _tif(lat_sw: int, lon_sw: int, value=None) -> bytes:
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    step = 1.0 / PIX
    lats = lat_sw + 1 - (np.arange(PIX) + 0.5) * step
    lons = lon_sw + (np.arange(PIX) + 0.5) * step
    la, lo = np.meshgrid(lats, lons, indexing="ij")
    z = (100.0 + 10.0 * (la - lat_sw) + 5.0 * (lo - lon_sw)).astype(np.float32) if value is None else value(la, lo)
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", height=PIX, width=PIX, count=1, dtype="float32", crs="EPSG:4326",
                      transform=from_origin(lon_sw, lat_sw + 1, step, step), nodata=-9999.0) as ds:
            ds.write(z.astype(np.float32), 1)
        return mem.read()


def _zip(members: dict[str, bytes], method=zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=method) as zf:
        zf.writestr("readme.txt", b"FABDEM d'essai\n")
        for name, data in members.items():
            zf.writestr(f"dossier/{name}", data)
    return buf.getvalue()


class Server:
    """Archives servies sous /<nom>.zip ; `ranges` faux : le serveur renvoie toujours le fichier entier."""

    def __init__(self, files: dict[str, bytes], ranges: bool = True) -> None:
        self.files, self.ranges, self.requests = files, ranges, []
        srv = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):  # noqa: N802
                srv.requests.append((self.path, self.headers.get("Range")))
                body = srv.files.get(self.path.lstrip("/"))
                if body is None:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                rng = self.headers.get("Range")
                if rng and srv.ranges:
                    m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng)
                    a, b = m.group(1), m.group(2)
                    n = len(body)
                    start, end = (max(0, n - int(b)), n - 1) if a == "" else (int(a), min(int(b) if b else n - 1, n - 1))
                    part = body[start:end + 1]
                    self.send_response(206)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{n}")
                else:
                    part = body
                    self.send_response(200)
                self.send_header("Content-Length", str(len(part)))
                self.end_headers()
                self.wfile.write(part)

            def log_message(self, *_):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def bytes_sent_ranges(self) -> int:
        return sum(1 for _, r in self.requests if r)


class Flat:
    """Repli d'essai : altitude constante, appels comptés."""

    name = "copie"
    native_resolution_m = 30.0

    def __init__(self, value: float = 7.0) -> None:
        self.value, self.calls = value, 0

    def elevations(self, lats, lons):
        self.calls += 1
        return np.full(np.asarray(lats).shape, self.value)


@pytest.fixture
def archive():
    members = {f"{fabdem_tile_name(43, -2)}.tif": _tif(43, -2), f"{fabdem_tile_name(44, -2)}.tif": _tif(44, -2)}
    files = {fabdem_zip_names(43, -2)[0]: _zip(members)}
    srv = Server(files)
    yield srv, files
    srv.close()


def test_names():
    assert fabdem_tile_name(43, -2) == "N43W002_FABDEM_V1-2"
    assert fabdem_tile_name(-34, 18) == "S34E018_FABDEM_V1-2"
    assert fabdem_zip_names(43, -2) == ["N40W010-N50W000_FABDEM_V1-2.zip", "N40W010-N50E000_FABDEM_V1-2.zip"]
    assert fabdem_zip_names(45, 6) == ["N40E000-N50E010_FABDEM_V1-2.zip"]
    assert fabdem_zip_names(-1, -75) == ["S10W080-N00W070_FABDEM_V1-2.zip", "S10W080-S00W070_FABDEM_V1-2.zip"]
    assert provider_for("fabdem_v1_2").name == "fabdem_v1_2"


def test_remote_zip_reads_one_member(archive, tmp_path):
    srv, files = archive
    zname = fabdem_zip_names(43, -2)[0]
    members = remote_zip.list_members(f"{srv.url}/{zname}")
    assert set(members) == {"readme.txt", "N43W002_FABDEM_V1-2.tif", "N44W002_FABDEM_V1-2.tif"}
    dest = tmp_path / "t.tif"
    got = remote_zip.fetch_member(f"{srv.url}/{zname}", members["N43W002_FABDEM_V1-2.tif"], dest)
    assert dest.read_bytes() == _tif(43, -2)
    assert got < len(files[zname])                   # seulement le fichier voulu, pas l'archive entière
    assert all(r for _, r in srv.requests)            # toutes les demandes sont partielles


def test_remote_zip_stored_member(tmp_path):
    files = {"a.zip": _zip({"x.tif": b"II*\x00" + bytes(1000)}, method=zipfile.ZIP_STORED)}
    srv = Server(files)
    try:
        m = remote_zip.list_members(f"{srv.url}/a.zip")["x.tif"]
        remote_zip.fetch_member(f"{srv.url}/a.zip", m, tmp_path / "x.tif")
        assert (tmp_path / "x.tif").read_bytes() == b"II*\x00" + bytes(1000)
    finally:
        srv.close()


def test_remote_zip_without_range_and_404(tmp_path):
    srv = Server({"a.zip": _zip({"x.tif": b"1234"})}, ranges=False)
    try:
        with pytest.raises(remote_zip.RangeUnsupported):
            remote_zip.list_members(f"{srv.url}/a.zip")
        with pytest.raises(NotFoundError):
            remote_zip.list_members(f"{srv.url}/absente.zip")
    finally:
        srv.close()


def test_provider_reads_fabdem_and_caches(archive, tmp_path):
    srv, _ = archive
    fb = Flat()
    p = FabdemProvider(cache_dir=tmp_path, base_url=srv.url, fallback=fb, log=lambda m: None)
    lat, lon = np.array([43.5, 44.25]), np.array([-1.5, -1.75])
    z = p.elevations(lat, lon)
    expect = 100.0 + 10.0 * (lat - np.floor(lat)) + 5.0 * (lon - np.floor(lon))
    assert np.allclose(z, expect, atol=0.3)
    assert fb.calls == 0
    assert p.tile_path(43, -2).is_file() and p.tile_ready(44, -2)
    n = len(srv.requests)
    # nouvelle séance, même cache : aucune demande au serveur
    q = FabdemProvider(cache_dir=tmp_path, base_url=srv.url, fallback=Flat(), log=lambda m: None)
    assert np.allclose(q.elevations(lat, lon), z)
    assert len(srv.requests) == n
    assert q.has_data(43.5, -1.5)


def test_missing_tile_marked_absent_then_fallback(archive, tmp_path):
    srv, _ = archive
    fb = Flat(7.0)
    p = FabdemProvider(cache_dir=tmp_path, base_url=srv.url, fallback=fb, log=lambda m: None)
    assert p.elevations(np.array([42.5]), np.array([-1.5]))[0] == 7.0   # tuile absente de l'archive
    assert p.absent_path(42, -2).is_file() and p.tile_ready(42, -2)
    assert p.elevations(np.array([43.5]), np.array([5.5]))[0] == 7.0    # archive absente (404) : la mer
    assert p.absent_path(43, 5).is_file()
    n = len(srv.requests)
    q = FabdemProvider(cache_dir=tmp_path, base_url=srv.url, fallback=fb, log=lambda m: None)
    q.elevations(np.array([42.5, 43.5]), np.array([-1.5, 5.5]))
    assert len(srv.requests) == n                     # marques gardées : pas de nouvelle demande


def test_server_without_range_falls_back(tmp_path):
    zname = fabdem_zip_names(43, -2)[0]
    srv = Server({zname: _zip({f"{fabdem_tile_name(43, -2)}.tif": _tif(43, -2)})}, ranges=False)
    try:
        p = FabdemProvider(cache_dir=tmp_path, base_url=srv.url, fallback=Flat(3.0), log=lambda m: None)
        assert p.elevations(np.array([43.5]), np.array([-1.5]))[0] == 3.0
        assert not p.tile_path(43, -2).exists()
    finally:
        srv.close()


def test_offline_uses_fallback_without_marking(archive, tmp_path):
    srv, _ = archive
    p = FabdemProvider(cache_dir=tmp_path, base_url=srv.url, fallback=Flat(5.0), offline=True, log=lambda m: None)
    assert p.elevations(np.array([43.5]), np.array([-1.5]))[0] == 5.0
    assert srv.requests == [] and not p.absent_path(43, -2).exists()   # réessayé avec le réseau


def test_nodata_pixels_use_fallback(tmp_path):
    def half_sea(la, lo):   # moitié est sans valeur (mer de FABDEM)
        return np.where(lo - np.floor(lo) > 0.5, -9999.0, 50.0).astype(np.float32)

    zname = fabdem_zip_names(43, -2)[0]
    srv = Server({zname: _zip({f"{fabdem_tile_name(43, -2)}.tif": _tif(43, -2, half_sea)})})
    try:
        p = FabdemProvider(cache_dir=tmp_path, base_url=srv.url, fallback=Flat(0.0), log=lambda m: None)
        z = p.elevations(np.array([43.5, 43.5]), np.array([-1.9, -1.1]))
        assert abs(z[0] - 50.0) < 0.01 and z[1] == 0.0
    finally:
        srv.close()


def test_open_world_uses_fabdem_by_default():
    """Le monde ouvert prend FABDEM par défaut ; le nom du relief entre dans les versions des carrés (refaits)."""
    import inspect

    from openride_compiler.worldgen import process, squares

    src = inspect.getsource(process.main)
    assert 'default="fabdem"' in src and "FabdemProvider(" in src
    v = squares.far_versions(FabdemProvider(fallback=Flat(), offline=True, log=lambda m: None))
    assert v["relief"] == "fabdem_v1_2"


def test_remote_zip_zip64(tmp_path, monkeypatch):
    """Archives de plus de 4 Go (ZIP64) : seuil abaissé pour écrire les champs ZIP64 sur une petite archive."""
    monkeypatch.setattr(zipfile, "ZIP64_LIMIT", 16)
    monkeypatch.setattr(zipfile, "ZIP_FILECOUNT_LIMIT", 1)
    data = _tif(43, -2)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, body in (("readme.txt", b"essai"), ("N43W002_FABDEM_V1-2.tif", data)):
            with zf.open(name, "w", force_zip64=True) as f:
                f.write(body)
    files = {"z.zip": buf.getvalue()}
    monkeypatch.undo()
    assert b"PK\x06\x06" in files["z.zip"]
    srv = Server(files)
    try:
        m = remote_zip.list_members(f"{srv.url}/z.zip")["N43W002_FABDEM_V1-2.tif"]
        remote_zip.fetch_member(f"{srv.url}/z.zip", m, tmp_path / "t.tif")
        assert (tmp_path / "t.tif").read_bytes() == data
    finally:
        srv.close()


@pytest.mark.network
def test_real_fabdem_server(tmp_path):
    """Service réel (à lancer sur le PC, `pytest -m network`) : graphie des archives et requêtes partielles."""
    logs: list[str] = []
    p = FabdemProvider(cache_dir=tmp_path, fallback=Flat(-1.0), log=logs.append)
    assert p.download_tile(45, 6), "\n".join(logs)
    z = p.elevations(np.array([45.5]), np.array([6.5]))[0]
    assert 200.0 < z < 4000.0
