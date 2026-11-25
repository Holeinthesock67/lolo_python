"""Lot RL2 : relief IGN RGE ALTI en France (carrés de 1 km au pas de 5 m, WMS en BIL 32 bits), FABDEM ailleurs.

Faux service WMS local : la grille rendue est une fonction analytique des coordonnées Lambert 93 de la demande,
pour vérifier l'interpolation. Aucun lieu réel : points quelconques dans et hors du cadre de la France.
"""

from __future__ import annotations

import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

from openride_compiler.elevation import (IGN_PIX, IgnRgeAltiProvider, ign_bil_to_grid, ign_tile_key, ign_tile_name,
                                         provider_for)


def relief(e, n):
    return 200.0 + 0.01 * (e % 100_000.0) + 0.005 * (n % 100_000.0)


class Flat:
    name = "repli"
    native_resolution_m = 30.0

    def __init__(self, value=-5.0):
        self.value, self.calls = value, 0

    def elevations(self, lats, lons):
        self.calls += 1
        return np.full(np.asarray(lats).shape, self.value)


class Wms:
    """`mode` : « ok », « vide » (hors de France), « moitie » (moitié est vide), « grand » (octets inversés)."""

    def __init__(self, mode="ok"):
        self.mode, self.requests = mode, []
        srv = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                srv.requests.append(q)
                e0, n0, e1, n1 = map(float, q["BBOX"][0].split(","))
                w, h = int(q["WIDTH"][0]), int(q["HEIGHT"][0])
                ce = e0 + (np.arange(w) + 0.5) * (e1 - e0) / w
                cn = n1 - (np.arange(h) + 0.5) * (n1 - n0) / h
                E, N = np.meshgrid(ce, cn)
                z = relief(E, N)
                if srv.mode == "vide":
                    z[:] = -99999.0
                elif srv.mode == "moitie":
                    z[:, w // 2:] = -99999.0
                body = z.astype(">f4" if srv.mode == "grand" else "<f4").tobytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/x-bil;bits=32")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/wms-r/wms"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def wms():
    srv = Wms()
    yield srv
    srv.close()


LAT, LON = np.array([45.5012, 45.5047]), np.array([4.5031, 4.5106])   # quelconques, dans le cadre de la France


def _prov(tmp_path, url, **kw):
    kw.setdefault("fallback", Flat())
    return IgnRgeAltiProvider(cache_dir=tmp_path, base_url=url, log=lambda m: None, **kw)


def test_names_and_url(tmp_path):
    assert ign_tile_name(337, 6262) == "L93_0337_6262"
    assert ign_tile_key(337_999.0, 6_262_000.0) == (337, 6262)
    p = _prov(tmp_path, "http://x/wms")
    url = p.tile_url(337, 6262)
    assert "LAYERS=ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES" in url and "CRS=EPSG:2154" in url
    assert "BBOX=336997.5,6261997.5,338002.5,6263002.5" in url and f"WIDTH={IGN_PIX}" in url
    assert provider_for("ign_rge_alti").name == "ign_rge_alti"


def test_bil_byte_order_and_errors():
    z = np.full((IGN_PIX, IGN_PIX), 321.5)
    assert np.allclose(ign_bil_to_grid(z.astype("<f4").tobytes()), 321.5)
    assert np.allclose(ign_bil_to_grid(z.astype(">f4").tobytes()), 321.5)
    with pytest.raises(ValueError):
        ign_bil_to_grid(b"<html>erreur</html>")
    z[0, 0] = -99999.0
    assert np.isnan(ign_bil_to_grid(z.astype("<f4").tobytes())[0, 0])


@pytest.mark.parametrize("mode", ["ok", "grand"])
def test_france_point_reads_ign_grid(tmp_path, mode):
    srv = Wms(mode)
    try:
        fb = Flat()
        p = _prov(tmp_path, srv.url, fallback=fb)
        z = p.elevations(LAT, LON)
        e, n = p._to_l93.transform(LON, LAT)
        assert np.allclose(z, relief(np.asarray(e), np.asarray(n)), atol=0.02)
        assert fb.calls == 0
        n_req = len(srv.requests)
        q = _prov(tmp_path, srv.url, fallback=fb)            # nouvelle séance : cache relu, aucune demande
        assert np.allclose(q.elevations(LAT, LON), z) and len(srv.requests) == n_req
        assert q.has_data(float(LAT[0]), float(LON[0]))
    finally:
        srv.close()


def test_outside_france_frame_no_request(tmp_path, wms):
    fb = Flat(12.0)
    p = _prov(tmp_path, wms.url, fallback=fb)
    assert np.all(p.elevations(np.array([36.8, 60.0]), np.array([-2.4, 10.7])) == 12.0)
    assert wms.requests == []


def test_empty_square_marked_absent(tmp_path):
    srv = Wms("vide")
    try:
        p = _prov(tmp_path, srv.url, fallback=Flat(9.0))
        assert np.all(p.elevations(LAT, LON) == 9.0)
        n = len(srv.requests)
        q = _prov(tmp_path, srv.url, fallback=Flat(9.0))
        q.elevations(LAT, LON)
        assert len(srv.requests) == n                         # marque d'absence gardée
    finally:
        srv.close()


def test_partial_square_uses_fallback_on_empty_pixels(tmp_path):
    srv = Wms("moitie")
    try:
        p = _prov(tmp_path, srv.url, fallback=Flat(-7.0))
        ke, kn = 337, 6262
        e = np.array([ke * 1000.0 + 100.0, ke * 1000.0 + 900.0])
        n = np.array([kn * 1000.0 + 500.0] * 2)
        lon, lat = p._to_l93.transform(e, n, direction="INVERSE")
        z = p.elevations(np.asarray(lat), np.asarray(lon))
        assert abs(z[0] - relief(e[0], n[0])) < 0.05 and z[1] == -7.0
    finally:
        srv.close()


def test_offline_and_network_failure_fall_back_without_mark(tmp_path, wms):
    p = _prov(tmp_path, wms.url, fallback=Flat(4.0), offline=True)
    assert np.all(p.elevations(LAT, LON) == 4.0) and wms.requests == []
    q = _prov(tmp_path, "http://127.0.0.1:9/wms", fallback=Flat(4.0), timeout_s=2.0)   # port fermé
    assert np.all(q.elevations(LAT, LON) == 4.0)
    assert not list((tmp_path / "ign_rge_alti").glob("*.absent")) if (tmp_path / "ign_rge_alti").exists() else True


def test_open_world_default_is_ign_then_fabdem():
    import inspect

    from openride_compiler.elevation import FabdemProvider
    from openride_compiler.worldgen import process, squares

    src = inspect.getsource(process.main)
    assert 'default="ign"' in src and "IgnRgeAltiProvider(" in src
    p = IgnRgeAltiProvider(offline=True, log=lambda m: None)
    assert isinstance(p.fallback, FabdemProvider)
    assert squares.far_versions(p)["relief"] == "ign_rge_alti"


@pytest.mark.network
def test_real_ign_service(tmp_path):
    """Service réel (sur le PC, `pytest -m network`) : couche, format BIL et ordre des octets."""
    logs: list[str] = []
    p = IgnRgeAltiProvider(cache_dir=tmp_path, fallback=Flat(-1.0), log=logs.append)
    z = p.elevations(np.array([45.0]), np.array([5.0]))[0]
    assert z != -1.0 and 100.0 < z < 3000.0, "\n".join(logs)
