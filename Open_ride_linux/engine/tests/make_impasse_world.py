#!/usr/bin/env python3
"""Monde vivant d'une impasse (fin de parcours du 14 novembre) : le vrai générateur du monde ouvert (W8) en
balade sur une route fictive sans autre branche, en mer au large de la Camargue (aucun lieu réel), départ
vers l'est à 2,9 km du bout de l'impasse. La route engagée y tourne dans une boucle de retournement et repart vers l'ouest.

Le dossier écrit se charge comme un parcours ordinaire (`sim_bench.py --world DOSSIER.world`) : il montre à
l'écran la boucle de retournement (captures de 2 880 à 3 040 m)."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np

from openride_compiler.worldgen import process
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
from openride_compiler.worldgen.process import WorldSession
from openride_compiler.worldgen.squares import zone_frame
from openride_compiler.worldgen.store import WorldCache
from openride_compiler.worldgen.synthetic import ZONE, AnalyticRelief, _zone_xz

IMPASSE_M = 2900.0            # distance du départ au bout de l'impasse
NAME = "impasse"


def build(out: Path, ride_m: float = 8000.0) -> Path:
    frame = zone_frame(ZONE)
    cx, cz = _zone_xz()

    def ll(x: float, z: float) -> tuple[float, float]:
        lat, lon = frame.to_latlon(np.array([x]), np.array([z]))
        return float(lon[0]), float(lat[0])

    work = Path(tempfile.mkdtemp(prefix="openride-impasse-"))
    db = work / "impasse.sqlite"
    w = OsmDbWriter(db, "synthetic", "synthetic/impasse")
    pts = list(range(-5000, 3001, 100))
    w.add_road(700, {"highway": "tertiary"}, [30_000 + k for k in range(len(pts))],
               [ll(cx + d, cz + 30.0 * np.sin(d / 700.0)) for d in pts])
    w.finish(osm_date="2026-10-20T00:00:00Z")
    lon, lat = ll(cx + 3000.0 - IMPASSE_M, cz + 30.0 * np.sin((3000.0 - IMPASSE_M) / 700.0))
    cache = WorldCache(work / "cache", 2 * 10**9, log=lambda _m: None)
    seance = work / f"{NAME}.world"
    s = WorldSession(cache, AnalyticRelief(), lambda _m: None, {}, seance, network=True,
                     clock=process.FakeClock(), log=lambda _m: None, db=OsmDb(db))
    s.handle({"type": "open", "lat": lat, "lon": lon, "heading_deg": 90.0, "nav": "ride", "target": None,
              "loop_km": None, "seed": 7, "network": True})
    k = 0
    while k * 250.0 < ride_m:
        k += 1
        s.handle({"type": "progress", "s_m": 250.0 * k, "v_mps": 8})
        if s.has_work():
            s.work()
    out.mkdir(parents=True, exist_ok=True)
    dest = out / seance.name
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(seance, dest, symlinks=False)           # tuiles du cache recopiées : dossier autonome
    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    print(f"{dest} : {s.length_m:.0f} m de route, boucle de retournement à {IMPASSE_M:.0f} m "
          f"(manifeste {manifest.get('id', NAME)})")
    shutil.rmtree(work, ignore_errors=True)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    build(ap.parse_args().out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
