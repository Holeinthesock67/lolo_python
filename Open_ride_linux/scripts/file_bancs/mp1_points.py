#!/usr/bin/env python3
"""Lot MP1 : distances des captures (départ + villages du rapport), pour sim_bench.py --at-m.

    python3 -I mp1_points.py MONDE.world [--max 4] [--max-km 16]
Lit MONDE.world/route.json et MONDE.world/buildings/rapport_maisons.json (branche MP1). Affiche « 150,s1,s2… » :
le départ, puis 60 m avant le point de route le plus proche de chaque village (les plus touchés d'abord).
Bibliothèque standard seulement.
"""
import argparse, json, math, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("world", type=Path)
ap.add_argument("--max", type=int, default=4)
ap.add_argument("--max-km", type=float, default=6.0)
a = ap.parse_args()
route = json.loads((a.world / "route.json").read_text(encoding="utf-8"))
rep = json.loads((a.world / "buildings" / "rapport_maisons.json").read_text(encoding="utf-8"))
xs, zs, ss = route["x"], route["z"], route["s"]
pts = []
for v in sorted(rep["villages"], key=lambda v: (-v["retirees"], v["id"])):
    i = min(range(len(xs)), key=lambda i: (xs[i] - v["x"]) ** 2 + (zs[i] - v["z"]) ** 2)
    s = max(150.0, ss[i] - 60.0)
    if s <= a.max_km * 1000 and all(abs(s - p) > 300 for p in pts):
        pts.append(round(s))
    if len(pts) >= a.max:
        break
print(",".join(str(p) for p in [150] + sorted(pts)))
sys.stderr.write(f"{a.world.name} : {rep['maisons']} maisons, {rep['retirees_total']} retirées, "
                 f"{rep['villages_en_alerte']} village(s) en alerte\n")
