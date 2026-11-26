#!/usr/bin/env python3
"""Monde d'essai des tunnels dessinés (lot EA5), sans réseau : `sim_bench.py --world tunnel`.

Produit avec le vrai compilateur un `.world` de 3 km vers le nord sur un plan à 5 %, qui passe sous une
crête de 45 m (flancs raides de 40 m) dans un tunnel de 300 m (km 1,35 à 1,65), colline gardée au-dessus.
Réponse Overpass fabriquée (voies `highway` de la trace, dont une `tunnel=yes`), altitude synthétique.
Couches : route, terrain, tunnels. Le monde ouvert n'est pas touché (aucun cache `~/OpenRide/Cache/monde`).

    python3 engine/tests/make_tunnel_world.py --out DOSSIER   → DOSSIER/tunnel-essai.world/

Captures conseillées : `sim_bench.py --world tunnel --at-m 1150,1320,1500,1630,1800` (approche du portail,
entrée, milieu du tube, sortie vue de l'intérieur, crête vue après la sortie avec `--camera follow_far`).
Prérequis : compilateur installé (`pip install -e compiler`).
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
LAYERS = ("tunnels",)
TUNNEL = (-1650.0, -1350.0)                         # z des portails (nord, sud)
RIDGE_Z = -1500.0
RIDGE_M = 45.0                                      # hauteur de la crête au-dessus du plan
RIDGE_FOOT_HALF_M = 155.0                           # pied des flancs : juste devant les portails
RIDGE_FLANK_M = 40.0                                # flancs raides : face rocheuse au-dessus du portail


def _no_network(*_args, **_kwargs):
    raise OSError("réseau interdit pendant la génération des données de test")


def relief(x, z):
    """Plan à 5 % vers le nord et crête est-ouest de 45 m au-dessus du tunnel, flancs raides de 40 m dont le pied
    touche les portails : la route garde l'altitude du plan d'un portail à l'autre, la colline se dresse au-dessus."""
    import numpy as np
    x, z = np.asarray(x, dtype=float), np.asarray(z, dtype=float)
    base = 1000.0 - 0.05 * z + 0.0 * x
    d = RIDGE_FOOT_HALF_M - np.abs(z - RIDGE_Z)
    return base + RIDGE_M * np.clip(d / RIDGE_FLANK_M, 0.0, 1.0)


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
    elements = [road(1, 20.0, TUNNEL[1]), road(2, TUNNEL[1], TUNNEL[0], tunnel="yes", layer="-1"),
                road(3, TUNNEL[0], -ROUTE_LENGTH_M - 20.0)]
    return json.dumps({"version": 0.6, "generator": "make_tunnel_world (lot EA5)",
                       "osm3s": {"timestamp_osm_base": "2026-11-20T00:00:00Z"}, "elements": elements}).encode("utf-8")


def _write_gpx(path: Path) -> None:
    import numpy as np
    s = np.arange(0.0, ROUTE_LENGTH_M + 1e-9, 5.0)
    pts = "".join(f'<trkpt lat="{p["lat"]:.9f}" lon="{p["lon"]:.9f}"></trkpt>' for p in _latlon([(0.0, -v) for v in s]))
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<gpx version="1.1" creator="make_tunnel_world" xmlns="http://www.topografix.com/GPX/1/1">'
                    f"<trk><name>tunnel</name><trkseg>{pts}</trkseg></trk></gpx>\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="dossier de sortie (créé si besoin)")
    args = parser.parse_args(argv)
    try:
        import urllib.request

        from openride_compiler import cli
        from openride_compiler.elevation import SyntheticProvider
    except ImportError as exc:
        print(f"make_tunnel_world : compilateur non installé ({exc}) ; pip install -e compiler", file=sys.stderr)
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
    gpx = out / "tunnel_essai.gpx"
    _write_gpx(gpx)
    rc = cli.main(["build", str(gpx), "--out", str(out), "--no-horizon",
                   "--layers", "route,terrain," + ",".join(LAYERS)])
    world = out / "tunnel-essai.world"
    if rc != 0 or not world.is_dir():
        print(f"make_tunnel_world : compilation impossible (code {rc})", file=sys.stderr)
        return 1
    info = json.loads((world / "manifest.json").read_text(encoding="utf-8"))["layers"]["tunnels"]
    if not info.get("count"):
        print("make_tunnel_world : aucun tunnel trouvé sur la trace", file=sys.stderr)
        return 1
    print(f"make_tunnel_world : {world} ({info['count']} tunnel(s), portions {info['spans']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
