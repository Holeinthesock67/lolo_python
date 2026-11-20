#!/usr/bin/env python3
"""Monde d'essai des ponts dessinés (lot EA4), sans réseau : `sim_bench.py --world pont`.

Produit avec le vrai compilateur un `.world` de 3 km vers le nord sur un plateau à 5 %, qui passe :
- un ruisseau sur un petit pont de 20 m (km 0,6, tablier sans pile) ;
- une vallée de 40 m de fond et 400 m de large, rivière au fond, sur un grand pont de 400 m (km 1,3 à 1,7, piles).
Réponse Overpass fabriquée (voies `highway` de la trace, dont deux `bridge=yes`, rivière et ruisseau),
altitude synthétique. Couches : route, terrain, water, bridges.

    python3 engine/tests/make_bridge_world.py --out DOSSIER   → DOSSIER/pont-essai.world/

Captures conseillées : `sim_bench.py --world pont --at-m 450,1100,1500,1900` (petit pont, arrivée sur le
grand, milieu du grand, vue arrière). Prérequis : compilateur installé (`pip install -e compiler`).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import socket
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]          # Open_ride_linux/
ORIGIN = (45.09, 6.06)                              # même origine que compiler/tests/conftest.py
ROUTE_LENGTH_M = 3000.0
LAYERS = ("water", "bridges")
VALLEY = (-1700.0, -1300.0)                         # z des bords de la grande vallée
VALLEY_DEPTH_M = 40.0
STREAM_Z = -600.0


def _no_network(*_args, **_kwargs):
    raise OSError("réseau interdit pendant la génération des données de test")


def relief(x, z):
    """Plan à 5 % vers le nord, vallée en auge (flancs de 80 m) et ravine de 6 m sous le ruisseau."""
    import numpy as np
    x, z = np.asarray(x, dtype=float), np.asarray(z, dtype=float)
    base = 1000.0 - 0.05 * z + 0.0 * x
    d = np.minimum(np.clip(z - VALLEY[0], 0.0, None), np.clip(VALLEY[1] - z, 0.0, None))
    valley = np.clip(d / 80.0, 0.0, 1.0) * VALLEY_DEPTH_M
    ravine = np.clip(1.0 - np.abs(z - STREAM_Z) / 12.0, 0.0, 1.0) * 6.0
    return base - valley - ravine


def _latlon(points):
    from openride_compiler.pipeline import utm_transformer, utm_zone_of
    number, _, south = utm_zone_of(*ORIGIN)
    tr = utm_transformer(number, south)
    e0, n0 = tr.transform(ORIGIN[1], ORIGIN[0])
    out = []
    for x, z in points:
        lon, lat = tr.transform(x + e0, n0 - z, direction="INVERSE")
        out.append({"lat": round(lat, 9), "lon": round(lon, 9)})
    return out


def _overpass() -> bytes:
    def road(wid, z0, z1, **tags):
        return {"type": "way", "id": wid, "tags": {"highway": "secondary", **tags},
                "geometry": _latlon([(0.0, z0), (0.0, z1)])}
    stream_z0, stream_z1 = STREAM_Z + 10.0, STREAM_Z - 10.0
    elements = [
        road(1, 20.0, stream_z0), road(2, stream_z0, stream_z1, bridge="yes", layer="1"),
        road(3, stream_z1, VALLEY[1]), road(4, VALLEY[1], VALLEY[0], bridge="viaduct", layer="1"),
        road(5, VALLEY[0], -ROUTE_LENGTH_M - 20.0),
        {"type": "way", "id": 4001, "tags": {"waterway": "river", "name": "Rivière d'essai", "width": "12"},
         "geometry": _latlon([(-1500.0, -1500.0), (0.0, -1500.0), (1500.0, -1500.0)])},
        {"type": "way", "id": 4002, "tags": {"waterway": "stream"},
         "geometry": _latlon([(-800.0, STREAM_Z), (0.0, STREAM_Z), (800.0, STREAM_Z)])},
    ]
    return json.dumps({"version": 0.6, "generator": "make_bridge_world (lot EA4)",
                       "osm3s": {"timestamp_osm_base": "2026-11-16T00:00:00Z"}, "elements": elements}).encode("utf-8")


def _write_gpx(path: Path) -> None:
    import numpy as np
    s = np.arange(0.0, ROUTE_LENGTH_M + 1e-9, 5.0)
    pts = "".join(f'<trkpt lat="{p["lat"]:.9f}" lon="{p["lon"]:.9f}"></trkpt>' for p in _latlon([(0.0, -v) for v in s]))
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<gpx version="1.1" creator="make_bridge_world" xmlns="http://www.topografix.com/GPX/1/1">'
                    f"<trk><name>pont</name><trkseg>{pts}</trkseg></trk></gpx>\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="dossier de sortie (créé si besoin)")
    args = parser.parse_args(argv)
    try:
        import urllib.request

        from openride_compiler import cli
        from openride_compiler.elevation import SyntheticProvider
    except ImportError as exc:
        print(f"make_bridge_world : compilateur non installé ({exc}) ; pip install -e compiler", file=sys.stderr)
        return 2
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    os.environ["OPENRIDE_DEM_CACHE"] = str(out / "dem-cache")
    os.environ["OPENRIDE_OSM_CACHE"] = str(out / "osm-cache")
    socket.socket.connect = _no_network          # type: ignore[method-assign]
    socket.create_connection = _no_network       # type: ignore[assignment]
    payload = _overpass()
    urllib.request.urlopen = lambda *_a, **_k: io.BytesIO(payload)   # type: ignore[assignment]
    cli.make_provider = lambda offline, log=None: SyntheticProvider(*ORIGIN, relief)   # type: ignore[assignment]
    gpx = out / "pont_essai.gpx"
    _write_gpx(gpx)
    rc = cli.main(["build", str(gpx), "--out", str(out), "--no-horizon",
                   "--layers", "route,terrain," + ",".join(LAYERS)])
    world = out / "pont-essai.world"
    if rc != 0 or not world.is_dir():
        print(f"make_bridge_world : compilation impossible (code {rc})", file=sys.stderr)
        return 1
    info = json.loads((world / "manifest.json").read_text(encoding="utf-8"))["layers"]["bridges"]
    print(f"make_bridge_world : {world} ({info['count']} pont(s), {info['piers']} pile(s), portions {info['spans']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
