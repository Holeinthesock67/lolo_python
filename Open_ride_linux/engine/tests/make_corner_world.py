#!/usr/bin/env python3
"""Parcours d'essai des virages serrés (lot CY1) : `essai-virages.world`, plat, couche terrain synthétique.

Usage :
    make_corner_world.py [--out DOSSIER]     (défaut : ~/.local/share/openride/routes)

Escalier de cinq côtés de 200 m à angles droits, alternativement à droite et à gauche, avec 3 points par coin
(le coin et un point à 3 m de part et d'autre), comme un parcours dessiné à la main tel que « essai-vent-carre ».
Ré-échantillonné tous les 10 m et cap calculé comme le compilateur (`pipeline._heading` : écart des voisins puis
moyenne circulaire sur 3 points, environ 30 m) : c'est l'écart entre ce cap moyenné et la courbe tracée par les
points qui faisait rouler le vélo en crabe avant le lot CY1. Sert au tour `engine/tests/tours/virages.json`.
Bibliothèque standard et openride_core seulement (ni numpy, ni scipy, ni pyproj).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_DIR.parent / "core" / "src"))

from openride_core.demo_world import build_manifest, build_segments  # noqa: E402
from openride_core.synthetic_terrain import add_terrain_layer  # noqa: E402

NAME = "essai-virages"
CREATED = "2026-11-08T00:00:00+01:00"
SIDE_M = 200.0
CORNER_M = 3.0
DS_M = 10.0
ORIGIN = (45.09, 6.06, 400.0)     # même zone fictive que la démonstration
EARTH_R = 6371008.8
# Cap des côtés (degrés, sens horaire depuis le nord) : est, sud (virage à droite), est (à gauche), sud, est.
SIDES = (90.0, 180.0, 90.0, 180.0, 90.0)


def polyline() -> list[tuple[float, float]]:
    """Points (x, z) du tracé : départ, 3 points par coin, arrivée ; x vers l'est, z vers le sud."""
    corners = [(0.0, 0.0)]
    for h in SIDES:
        x, z = corners[-1]
        corners.append((x + SIDE_M * math.sin(math.radians(h)), z - SIDE_M * math.cos(math.radians(h))))
    pts = [corners[0]]
    for k in range(1, len(corners) - 1):
        (px, pz), (cx, cz), (nx, nz) = corners[k - 1], corners[k], corners[k + 1]
        dp = math.hypot(px - cx, pz - cz)
        dn = math.hypot(nx - cx, nz - cz)
        pts.append((cx + (px - cx) / dp * CORNER_M, cz + (pz - cz) / dp * CORNER_M))
        pts.append((cx, cz))
        pts.append((cx + (nx - cx) / dn * CORNER_M, cz + (nz - cz) / dn * CORNER_M))
    pts.append(corners[-1])
    return pts


def compiler_heading(xs: list[float], zs: list[float]) -> list[float]:
    """Cap du compilateur pour un tracé ouvert (pipeline._heading)."""
    n = len(xs)
    raw = []
    for i in range(n):
        a, b = max(i - 1, 0), min(i + 1, n - 1)
        raw.append(math.atan2(xs[b] - xs[a], -(zs[b] - zs[a])))
    out = []
    for i in range(n):
        sx = sum(math.sin(raw[j]) for j in range(i - 1, i + 2) if 0 <= j < n)
        sy = sum(math.cos(raw[j]) for j in range(i - 1, i + 2) if 0 <= j < n)
        out.append(math.degrees(math.atan2(sx, sy)) % 360.0)
    return out


def build_route() -> dict:
    pts = polyline()
    cum = [0.0]
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.hypot(bx - ax, bz - az))
    length = cum[-1]
    n = int(length // DS_M) + 1
    if length - (n - 1) * DS_M > 1e-3:
        n += 1
    xs, zs = [], []
    j = 0
    for i in range(n):
        s = min(i * DS_M, length)
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        u = (s - cum[j]) / (cum[j + 1] - cum[j])
        xs.append(pts[j][0] + (pts[j + 1][0] - pts[j][0]) * u)
        zs.append(pts[j][1] + (pts[j + 1][1] - pts[j][1]) * u)
    lat0, lon0, alt0 = ORIGIN
    r = lambda v, d: [round(x, d) for x in v]  # noqa: E731
    return {
        "version": "1.0", "ds_m": DS_M, "n": n, "length_m": round(length, 3), "type": "open",
        "lat": r([lat0 + math.degrees(-z / EARTH_R) for z in zs], 7),
        "lon": r([lon0 + math.degrees(x / (EARTH_R * math.cos(math.radians(lat0)))) for x in xs], 7),
        "alt_m": [alt0] * n, "x": r(xs, 2), "z": r(zs, 2), "grade_pct": [0.0] * n,
        "heading_deg": r(compiler_heading(xs, zs), 2),
    }


def write(out_dir: Path) -> Path:
    route = build_route()
    world = out_dir / f"{NAME}.world"
    world.mkdir(parents=True, exist_ok=True)
    segments = build_segments(route)
    (world / "route.json").write_text(json.dumps(route, separators=(",", ":")), encoding="utf-8")
    (world / "segments.json").write_text(json.dumps({"version": "1.0", "segments": segments}) + "\n", encoding="utf-8")
    (world / "manifest.json").write_text(json.dumps(build_manifest(NAME, route, CREATED, segments), indent=2),
                                         encoding="utf-8")
    return add_terrain_layer(world)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path.home() / ".local/share/openride/routes")
    args = ap.parse_args(argv)
    print(write(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
