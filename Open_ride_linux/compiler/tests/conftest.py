"""Outils communs : GPX synthétiques générés à partir de coordonnées calculées."""

from __future__ import annotations

import importlib
import math
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from isolation_tests import brancher_pytest  # noqa: E402  (HOME temporaire avant les imports ci-dessous)

globals().update(brancher_pytest())

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from openride_compiler import cli
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.pipeline import utm_transformer, utm_zone_of

ORIGIN = (45.09, 6.06)          # près de Bourg-d'Oisans, zone 32T
REPO = Path(__file__).resolve().parents[2]
WORLD_CONTRACTS = REPO / "docs" / "contracts" / "world"


def require_core(module: str):
    """Module d'openride-core pour un test de vérification croisée (lot M9, constat S2).

    `pip install -e "compiler[dev]"` seul n'installe pas le core : ces tests sont alors sautés.
    En intégration continue (variable `CI`), les deux paquets sont installés : l'absence du
    core y est une erreur, jamais un saut silencieux.
    """
    if os.environ.get("CI"):
        return importlib.import_module(module)
    return pytest.importorskip(module, reason="openride-core absent : `pip install -e ../core` pour ce test")


def to_latlon(x, z, origin=ORIGIN):
    """Repère du monde (x vers l'est, z vers le sud) → (lat, lon), dans la zone UTM de l'origine."""
    number, _, south = utm_zone_of(*origin)
    tr = utm_transformer(number, south)
    e0, n0 = tr.transform(origin[1], origin[0])
    lon, lat = tr.transform(np.asarray(x, float) + e0, n0 - np.asarray(z, float), direction="INVERSE")
    return np.atleast_1d(lat), np.atleast_1d(lon)


def gpx_text(lat, lon, ele=None, version="1.1", tag="trkpt") -> str:
    ns = "http://www.topografix.com/GPX/1/1" if version == "1.1" else "http://www.topografix.com/GPX/1/0"
    pts = []
    for k, (a, o) in enumerate(zip(lat, lon)):
        e = "" if ele is None or ele[k] is None else f"<ele>{ele[k]:.4f}</ele>"
        pts.append(f'<{tag} lat="{a:.10f}" lon="{o:.10f}">{e}</{tag}>')
    body = "".join(pts)
    if tag == "trkpt":
        body = f"<trk><name>essai</name><trkseg>{body}</trkseg></trk>"
    else:
        body = f"<rte>{body}</rte>"
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<gpx version="{version}" creator="tests" xmlns="{ns}">{body}</gpx>\n')


def write_gpx(path: Path, x, z, alt=None, **kw) -> Path:
    lat, lon = to_latlon(x, z)
    path.write_text(gpx_text(lat, lon, None if alt is None else list(alt), **kw), encoding="utf-8")
    return path


def straight_north(length=2000.0, step=5.0, grade=5.0):
    s = np.arange(0.0, length + 1e-9, step)
    return np.zeros_like(s), -s, 1000.0 + grade / 100.0 * s


def circle(radius=1000.0, n_points=1000):
    a = np.linspace(0.0, 2 * math.pi, n_points, endpoint=False)
    x, z = radius * np.sin(a), -radius * (1 - np.cos(a))         # départ en (0, 0)
    alt = 500.0 + 20.0 * np.sin(a)
    return x, z, alt


@pytest.fixture
def make_gpx(tmp_path):
    def make(name, x, z, alt=None, **kw):
        return write_gpx(tmp_path / name, x, z, alt, **kw)
    return make


def plane(x, z):
    """MNT de test par défaut : plan qui monte de 5 % vers le nord, égal à l'altitude de
    `straight_north` sur son tracé (l'altitude GPX y est donc jugée correcte)."""
    return 1000.0 - 0.05 * np.asarray(z, dtype=float) + 0.0 * np.asarray(x, dtype=float)


@pytest.fixture(autouse=True)
def offline_and_synthetic(request, monkeypatch, tmp_path):
    """Réseau coupé (sauf tests `network` et boucle locale : faux serveur de tuiles X28), cache MNT/OSM
    temporaire, MNT synthétique pour la CLI."""
    monkeypatch.setenv("OPENRIDE_DEM_CACHE", str(tmp_path / "dem-cache"))
    monkeypatch.setenv("OPENRIDE_OSM_CACHE", str(tmp_path / "osm-cache"))
    if request.node.get_closest_marker("network"):
        return
    connect, create_connection = socket.socket.connect, socket.create_connection

    def local(address) -> bool:
        return isinstance(address, tuple) and address[0] in ("127.0.0.1", "localhost", "::1")

    def no_network_connect(sock, address, *args, **kwargs):
        if local(address):
            return connect(sock, address, *args, **kwargs)
        raise OSError("réseau interdit pendant les tests")

    def no_network_create(address, *args, **kwargs):
        if local(address):
            return create_connection(address, *args, **kwargs)
        raise OSError("réseau interdit pendant les tests")
    monkeypatch.setattr(socket.socket, "connect", no_network_connect)
    monkeypatch.setattr(socket, "create_connection", no_network_create)
    monkeypatch.setattr(cli, "make_provider", lambda offline, log=None: SyntheticProvider(*ORIGIN, plane))
