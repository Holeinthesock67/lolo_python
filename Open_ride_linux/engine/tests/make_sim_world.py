#!/usr/bin/env python3
"""Parcours d'essai « village simulé » : montée, descente, deux villages, forêts et eau, sans réseau.

Produit, avec le vrai compilateur, un `.world` complet (`route`, `terrain`, `buildings`,
`vegetation`, `poi`, `water`) à partir d'une trace et d'un relief synthétiques et d'une réponse
Overpass fabriquée ici (aucune donnée réelle) :

- profil : 700 m de plat (village du bas), 1 500 m de montée à 7 %, 300 m de replat au sommet,
  1 500 m de descente à −6 %, 1 000 m de plat (village du haut) ; route en S, vallée de part et
  d'autre ;
- bâtiments : deux villages de maisons alignées des deux côtés de la route (hauteurs, étages et
  couleurs variés, immeubles, église), fermes isolées le long de la montée ;
- végétation : forêts sur les flancs de la montée et de la descente, verger, broussailles ;
- eau : rivière qui croise la route, ruisseau, lac au sommet ; points d'intérêt : villages,
  église, belvédère, éoliennes sur le plateau du col (une près de la route pour voir son pied).

    python3 engine/tests/make_sim_world.py --out DOSSIER [--seed N]
    → DOSSIER/village-simule.world/ et DOSSIER/village-simule.json (nombres et profil attendus)
    python3 engine/tests/make_sim_world.py --out DOSSIER --live
    → DOSSIER/monde-ouvert-simule.world/ : monde vivant synthétique de 20 km (lot W15)

Sert au banc d'essai simulé (`sim_bench.py --world village`) et à l'essai visuel des bâtiments.
Origine : même point fictif que les tests du compilateur. Prérequis : compilateur installé
(`pip install -e compiler`). Code de sortie : 0 si tout est écrit.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import random
import socket
import sys
from pathlib import Path

try:
    from openride_compiler import fake_osm
except ImportError:   # dépôt sans `pip install -e compiler` : les sources du compilateur
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "compiler" / "src"))
    from openride_compiler import fake_osm
# Réponse Overpass fabriquée et route en S, communes avec les parcours de démonstration (lot O37).
from openride_compiler.fake_osm import COLOURS, Overpass, no_network, road_heading, road_x  # noqa: E402,F401

ORIGIN = (45.09, 6.06)                  # même origine que compiler/tests/conftest.py
NAME = "village-simule"
LAYERS = ("buildings", "vegetation", "poi", "water")
STEP_M = 5.0
# (début en m, fin en m, pente en %) : le profil, de bout en bout.
PROFILE = [(0.0, 700.0, 0.0), (700.0, 2200.0, 7.0), (2200.0, 2500.0, 0.0),
           (2500.0, 4000.0, -6.0), (4000.0, 5000.0, 0.0)]
LENGTH_M = PROFILE[-1][1]
BASE_ALT_M = 400.0
VILLAGES = [(80.0, 640.0, "Village du Bas"), (4100.0, 4900.0, "Village du Haut")]


def altitude(s: float) -> float:
    """Altitude de la route à l'abscisse curviligne approchée `s` (m)."""
    alt = BASE_ALT_M
    for a, b, grade in PROFILE:
        if s <= a:
            break
        alt += (min(s, b) - a) * grade / 100.0
    return alt


def terrain(x, z):
    """Relief : la route au fond d'une vallée dont les flancs montent de 12 % puis 25 %."""
    import numpy as np
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    s = np.clip(-z, 0.0, LENGTH_M)
    base = np.vectorize(altitude)(s)
    d = np.abs(x - 60.0 * np.sin(2.0 * np.pi * s / 1800.0))
    side = 0.12 * np.clip(d - 12.0, 0.0, 150.0) + 0.25 * np.clip(d - 162.0, 0.0, None)
    return base + side


class Frame(fake_osm.Frame):
    def __init__(self) -> None:
        super().__init__(ORIGIN)


def write_gpx(path: Path, frame: Frame) -> None:
    pts = []
    n = int(LENGTH_M / STEP_M)
    for k in range(n + 1):
        s = k * STEP_M
        lat, lon = frame.latlon(road_x(s), -s)
        pts.append(f'<trkpt lat="{lat:.10f}" lon="{lon:.10f}"><ele>{altitude(s):.3f}</ele></trkpt>')
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<gpx version="1.1" creator="make_sim_world" xmlns="http://www.topografix.com/GPX/1/1">'
                    f"<trk><name>{NAME}</name><trkseg>{''.join(pts)}</trkseg></trk></gpx>\n",
                    encoding="utf-8")


def build_overpass(frame: Frame, seed: int) -> Overpass:
    rng = random.Random(seed)
    op = Overpass(frame, rng)
    for s0, s1, name in VILLAGES:
        s = s0
        while s < s1:
            for side in (-1, 1):
                if rng.random() < 0.12:
                    continue                    # parcelle vide
                kind = rng.choices(["house", "house", "house", "apartments", "garage", "yes"], k=1)[0]
                tags: dict = {"building": kind}
                if kind == "apartments":
                    tags["building:levels"] = str(rng.randint(3, 5))
                    length, depth = rng.uniform(18, 26), rng.uniform(11, 14)
                elif kind == "garage":
                    length, depth = rng.uniform(5, 7), rng.uniform(5, 6)
                else:
                    if rng.random() < 0.5:
                        tags["height"] = f"{rng.uniform(6.0, 9.5):.1f} m"
                    else:
                        tags["building:levels"] = str(rng.randint(1, 2))
                    length, depth = rng.uniform(9, 14), rng.uniform(7, 10)
                if rng.random() < 0.6:
                    tags["building:colour"] = rng.choice(COLOURS)
                offset = side * (rng.uniform(13.0, 17.0) + depth / 2)
                op.building(s, offset, tags, length, depth)
                # Seconde rangée, plus loin de la route, une fois sur deux.
                if rng.random() < 0.5:
                    op.building(s + rng.uniform(-4, 4), side * (offset * side + depth + rng.uniform(8, 14)),
                                {"building": "house", "building:levels": str(rng.randint(1, 2))},
                                rng.uniform(8, 12), rng.uniform(7, 9))
            s += rng.uniform(20.0, 28.0)
        mid = (s0 + s1) / 2
        op.building(mid, 34.0, {"building": "church", "amenity": "place_of_worship",
                                "name": f"Église du {name.split(' du ')[1]}", "height": "16 m"}, 28.0, 14.0)
        op.node(road_x(mid) - 30.0, -mid, {"place": "village", "name": name})
    # Fermes isolées le long de la montée et de la descente.
    for s in (950.0, 1500.0, 2050.0, 2800.0, 3400.0, 3900.0):
        side = 1 if int(s) % 2 else -1
        op.building(s, side * 32.0, {"building": "farm", "building:levels": "2", "building:colour": "#c9b59a"},
                    16.0, 11.0)
        op.building(s + 22.0, side * 38.0, {"building": "barn", "height": "8 m"}, 22.0, 13.0)
    # Végétation : forêts sur les flancs, verger, broussailles.
    for s0, s1, side, tags in ((750.0, 2150.0, 1, {"landuse": "forest"}),
                               (900.0, 2100.0, -1, {"natural": "wood"}),
                               (2550.0, 3950.0, -1, {"landuse": "forest"}),
                               (2600.0, 3300.0, 1, {"natural": "scrub"}),
                               (3500.0, 3950.0, 1, {"landuse": "orchard"})):
        lo, hi = (22.0, 180.0) if side > 0 else (-180.0, -22.0)
        op.way(op.band(s0, s1, lo, hi), tags)
        op.counts["vegetation"] += 1
    # Eau : rivière qui croise la route au pied de la descente, ruisseau dans la montée, lac au sommet.
    sx = 3980.0
    hx, hz = road_heading(sx)
    nx, nz = -hz, hx
    river = [(road_x(sx) + nx * d, -sx + nz * d) for d in range(-300, 301, 25)]
    op.way(river, {"waterway": "river", "name": "La Rivière", "width": "9"}, close=False)
    op.counts["water_lines"] += 1
    stream = [(road_x(1300.0) + 15.0 + 8.0 * math.sin(k / 3), -1300.0 + k * 20.0) for k in range(-10, 11)]
    op.way(stream, {"waterway": "stream"}, close=False)
    op.counts["water_lines"] += 1
    lake_c = (road_x(2350.0) - 110.0, -2350.0)
    lake = [(lake_c[0] + 55.0 * math.cos(a / 12 * 2 * math.pi), lake_c[1] + 35.0 * math.sin(a / 12 * 2 * math.pi))
            for a in range(12)]
    op.way(lake, {"natural": "water", "water": "lake", "name": "Lac du Sommet"})
    op.counts["water_areas"] += 1
    op.node(road_x(2350.0) + 25.0, -2350.0, {"tourism": "viewpoint", "name": "Belvédère du Col"})
    # Éoliennes sur le plateau du col (Lot P12, habillage Y8 étape 4) : une rangée au loin, une près de la route.
    for s, off in ((2250.0, 150.0), (2420.0, 210.0), (2590.0, 170.0), (2460.0, 60.0)):
        op.node(road_x(s) + off, -s, {"power": "generator", "generator:source": "wind", "height": "95"})
    return op


def summarize(world: Path) -> dict:
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    layers = manifest.get("layers", {})
    return {k: {kk: vv for kk, vv in v.items() if kk.endswith("count")}
            for k, v in layers.items() if isinstance(v, dict) and k in LAYERS}


def write_live(out: Path, seed: int) -> int:
    """Monde vivant synthétique de 20 km (format §13), pour mesurer le rendu du monde ouvert (W10)."""
    try:
        from openride_compiler.worldgen.synthetic import default_script, write_live_world
    except ImportError as exc:
        print(f"make_sim_world : compilateur non installé ({exc}) ; pip install -e compiler", file=sys.stderr)
        return 2
    world = out / "monde-ouvert-simule.world"
    info = write_live_world(world, default_script(20_000.0, seed))
    (out / "monde-ouvert-simule.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"make_sim_world : {world} ({', '.join(f'{k} {v}' for k, v in sorted(info.items()))})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="dossier de sortie (créé si besoin)")
    parser.add_argument("--seed", type=int, default=0, help="graine du placement des bâtiments (défaut 0)")
    parser.add_argument("--live", action="store_true",
                        help="monde ouvert : monde vivant synthétique de 20 km (lot W15) au lieu du village")
    args = parser.parse_args(argv)
    if args.live:
        return write_live(args.out, args.seed)
    try:
        import urllib.request

        from openride_compiler import cli
        from openride_compiler.elevation import SyntheticProvider
    except ImportError as exc:
        print(f"make_sim_world : compilateur non installé ({exc}) ; pip install -e compiler", file=sys.stderr)
        return 2

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    os.environ["OPENRIDE_DEM_CACHE"] = str(out / "dem-cache")
    os.environ["OPENRIDE_OSM_CACHE"] = str(out / "osm-cache")
    socket.socket.connect = no_network          # type: ignore[method-assign]
    socket.create_connection = no_network       # type: ignore[assignment]
    frame = Frame()
    op = build_overpass(frame, args.seed)
    payload = json.dumps({"version": 0.6, "generator": "OpenRide make_sim_world",
                          "osm3s": {"timestamp_osm_base": "2026-10-25T00:00:00Z"},
                          "elements": op.elements}).encode("utf-8")
    urllib.request.urlopen = lambda *_a, **_k: io.BytesIO(payload)   # type: ignore[assignment]
    cli.make_provider = lambda offline, log=None: SyntheticProvider(*ORIGIN, terrain)   # type: ignore[assignment]
    gpx = out / f"{NAME}.gpx"
    write_gpx(gpx, frame)
    rc = cli.main(["build", str(gpx), "--out", str(out), "--force",
                   "--layers", "route,terrain," + ",".join(LAYERS)])
    world = out / f"{NAME}.world"
    if rc != 0 or not world.is_dir():
        print(f"make_sim_world : compilation impossible (code {rc})", file=sys.stderr)
        return 1
    info = {"route": NAME, "length_m": LENGTH_M, "profile": PROFILE, "villages": VILLAGES,
            "generated": op.counts, "manifest": summarize(world)}
    (out / f"{NAME}.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = ", ".join(f"{k} {v}" for k, v in sorted(info["manifest"].items()))
    print(f"make_sim_world : {world} ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
