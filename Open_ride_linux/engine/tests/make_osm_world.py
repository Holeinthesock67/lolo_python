#!/usr/bin/env python3
"""Données du test de lecture des couches OSM dans l'engine (lot K4), sans réseau.

Produit, avec le vrai compilateur, un `.world` à cinq couches (`buildings`, `vegetation`, `poi`,
`water` et, depuis le lot P22, `roads`) à partir des réponses Overpass enregistrées des tests du compilateur
(`compiler/tests/data/osm/`) et de l'altitude synthétique de ces tests (plan à 5 % vers le nord),
puis relit le résultat et écrit les nombres attendus dans `expected.json`.

    python3 engine/tests/make_osm_world.py --out DOSSIER
    → DOSSIER/osm-test.world/ et DOSSIER/expected.json

Prérequis : compilateur installé (`pip install -e compiler`). Code de sortie : 0 si tout est écrit.
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
DATA_DIR = REPO / "compiler" / "tests" / "data" / "osm"
ORIGIN = (45.09, 6.06)                              # même origine que compiler/tests/conftest.py
ROUTE_LENGTH_M = 3000.0
LAYERS = ("buildings", "vegetation", "poi", "water", "roads")


def _no_network(*_args, **_kwargs):
    raise OSError("réseau interdit pendant la génération des données de test")


def _merged_overpass() -> bytes:
    """Les trois réponses enregistrées fusionnées en une seule (identifiants distincts)."""
    elements: list[dict] = []
    first: dict | None = None
    for name in ("sample_overpass.json", "sample_poi_water.json", "sample_open_roads.json"):
        doc = json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
        first = first or doc
        elements.extend(doc["elements"])
    merged = dict(first or {})
    merged["elements"] = elements
    return json.dumps(merged).encode("utf-8")


def _write_gpx(path: Path) -> None:
    """Ligne droite vers le nord de 3 km, 5 % de pente (comme `straight_north` des tests)."""
    import numpy as np
    from openride_compiler.pipeline import utm_transformer, utm_zone_of

    s = np.arange(0.0, ROUTE_LENGTH_M + 1e-9, 5.0)
    x, z, alt = np.zeros_like(s), -s, 1000.0 + 0.05 * s
    number, _, south = utm_zone_of(*ORIGIN)
    tr = utm_transformer(number, south)
    e0, n0 = tr.transform(ORIGIN[1], ORIGIN[0])
    lon, lat = tr.transform(x + e0, n0 - z, direction="INVERSE")
    pts = "".join(f'<trkpt lat="{a:.10f}" lon="{o:.10f}"><ele>{e:.4f}</ele></trkpt>'
                  for a, o, e in zip(lat, lon, alt))
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<gpx version="1.1" creator="make_osm_world" xmlns="http://www.topografix.com/GPX/1/1">'
                    f"<trk><name>essai</name><trkseg>{pts}</trkseg></trk></gpx>\n", encoding="utf-8")


def _expected(world: Path) -> dict:
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    layers = manifest["layers"]
    out: dict = {"manifest": {}, "files": {}}
    keys = {"buildings": ["buildings"], "vegetation": ["areas"], "poi": ["points"], "water": ["lines", "areas"], "roads": ["lines"]}
    for layer in LAYERS:
        out["manifest"][layer] = {k: v for k, v in layers[layer].items() if k.endswith("count")}
        per_chunk = {}
        for f in sorted((world / layer).glob("chunk_*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            k = int(f.stem.split("_")[1])
            per_chunk[str(k)] = {key: len(doc[key]) for key in keys[layer]}
        out["files"][layer] = per_chunk
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="dossier de sortie (créé si besoin)")
    args = parser.parse_args(argv)
    try:
        import urllib.request

        from openride_compiler import cli
        from openride_compiler.elevation import SyntheticProvider
    except ImportError as exc:
        print(f"make_osm_world : compilateur non installé ({exc}) ; pip install -e compiler", file=sys.stderr)
        return 2

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    os.environ["OPENRIDE_DEM_CACHE"] = str(out / "dem-cache")
    os.environ["OPENRIDE_OSM_CACHE"] = str(out / "osm-cache")
    socket.socket.connect = _no_network          # type: ignore[method-assign]
    socket.create_connection = _no_network       # type: ignore[assignment]
    payload = _merged_overpass()
    urllib.request.urlopen = lambda *_a, **_k: io.BytesIO(payload)   # type: ignore[assignment]

    def plane(x, z):
        import numpy as np
        return 1000.0 - 0.05 * np.asarray(z, dtype=float) + 0.0 * np.asarray(x, dtype=float)

    cli.make_provider = lambda offline, log=None: SyntheticProvider(*ORIGIN, plane)   # type: ignore[assignment]
    gpx = out / "osm_test.gpx"
    _write_gpx(gpx)
    rc = cli.main(["build", str(gpx), "--out", str(out), "--layers", "route,terrain," + ",".join(LAYERS)])
    world = out / "osm-test.world"
    if rc != 0 or not world.is_dir():
        print(f"make_osm_world : compilation impossible (code {rc})", file=sys.stderr)
        return 1
    expected = _expected(world)
    (out / "expected.json").write_text(json.dumps(expected, indent=2, sort_keys=True), encoding="utf-8")
    counts = ", ".join(f"{k} {v}" for k, v in sorted(expected["manifest"].items()))
    print(f"make_osm_world : {world} ({counts})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
