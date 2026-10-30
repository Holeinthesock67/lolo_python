"""Parcours `.world` synthétiques (manifeste, couche route et couche segments) conformes au Format .world v1.

Sert au parcours de démonstration commun au core et à l'engine, et aux tests.
La ligne de commande est dans `tools/fake_world.py`.
La route est une montée sinueuse synthétique avec un lacet (deux épingles de sens opposés),
qui ne repasse jamais sur elle-même ; les coordonnées
géographiques sont obtenues par une projection locale équirectangulaire (suffisante pour
des données factices, le compilateur utilisera UTM via pyproj).

    python -m openride_core.tools.fake_world --out ../engine/demo --length 8000

Le parcours de démonstration commun au core et à l'engine (`demo`, 5 000 m) est écrit par
`write_demo_world` avec une date de création fixe, pour être identique octet pour octet :
    python -m openride_core.tools.fake_world --demo --out ../engine/demo

La couche `segments.json` (format 1.3, lot T3) porte les montées et sprints détectés
automatiquement par `segments.py`, sans segment manuel (décision du 27 octobre).
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Callable

from .segments import Profile, detect_segments

EARTH_R = 6_371_000.0
DS_M = 10.0

DEMO_NAME = "demo"
DEMO_LENGTH_M = 5000.0
DEMO_CREATED = "2026-10-23T00:00:00+02:00"   # fixe : le fichier de démo est reproductible
HAIRPIN_GAP_M = 500.0       # distance entre les deux épingles du lacet (au plus 0,15 × longueur)
HAIRPIN_GAP_MIN_M = 250.0


def build_route(length_m: float = 8000.0, origin_lat: float = 45.09, origin_lon: float = 6.06,
                origin_alt: float = 1120.0, grade: Callable[[float], float] | None = None) -> dict:
    """Route synthétique ; `grade(s)` (en %) remplace la pente de la démonstration (parcours d'essai des
    outils, `tools/bots_race.py`)."""
    n = int(length_m // DS_M) + 1
    if (n - 1) * DS_M < length_m:
        n += 1
    s_values = [min(i * DS_M, length_m) for i in range(n)]

    # Cap : dérive lente + virages, avec un lacet : deux épingles de sens opposés (rotation de
    # ~180° sur 150 m chacune), proches l'une de l'autre. La route repart ensuite dans sa direction
    # d'origine, décalée d'environ 190 m : elle ne repasse jamais sur elle-même.
    hairpin_1 = 0.45 * length_m
    hairpin_2 = hairpin_1 + min(HAIRPIN_GAP_M, max(HAIRPIN_GAP_MIN_M, 0.15 * length_m))

    lacet_zone = (hairpin_1 - HAIRPIN_GAP_M, hairpin_2 + HAIRPIN_GAP_M)

    def heading_rate(s: float) -> float:  # degrés par mètre
        rate = 0.0
        if not lacet_zone[0] <= s <= lacet_zone[1]:   # branches du lacet droites et parallèles
            rate = 0.04 * math.sin(s / 700.0) + 0.02 * math.sin(s / 230.0 + 1.0)
        for center, turn in ((hairpin_1, 1.0), (hairpin_2, -1.0)):
            if abs(s - center) < 75.0:
                rate += turn * 180.0 / 150.0
        return rate

    # Pente : montée douce de 1 à 4 % qui ondule (confortable vers 150 W), replat en milieu de parcours.
    def demo_grade(s: float) -> float:
        g = 2.5 + 1.5 * math.sin(s / 900.0) + 0.5 * math.sin(s / 170.0)
        if 0.3 * length_m < s < 0.35 * length_m:
            g = 1.0
        return g

    grade = grade or demo_grade

    xs, zs, alts, grades, headings = [0.0], [0.0], [origin_alt], [grade(0.0)], [45.0]
    h = 45.0
    for i in range(1, n):
        ds = s_values[i] - s_values[i - 1]
        h = (h + heading_rate(s_values[i]) * ds) % 360.0
        rad = math.radians(h)
        # Cap horaire depuis le nord ; x vers l'est, z vers le sud (nord = −z).
        xs.append(xs[-1] + ds * math.sin(rad))
        zs.append(zs[-1] - ds * math.cos(rad))
        g = grade(s_values[i])
        alts.append(alts[-1] + ds * g / 100.0)
        grades.append(g)
        headings.append(h)

    lat0 = math.radians(origin_lat)
    lats = [origin_lat + math.degrees(-z / EARTH_R) for z in zs]
    lons = [origin_lon + math.degrees(x / (EARTH_R * math.cos(lat0))) for x in xs]

    r = lambda v, d: [round(x, d) for x in v]  # noqa: E731
    return {
        "version": "1.0",
        "ds_m": DS_M,
        "n": n,
        "length_m": float(length_m),
        "type": "open",
        "lat": r(lats, 7),
        "lon": r(lons, 7),
        "alt_m": r(alts, 2),
        "x": r(xs, 2),
        "z": r(zs, 2),
        "grade_pct": r(grades, 2),
        "heading_deg": r(headings, 2),
    }


def build_segments(route: dict) -> list[dict]:
    """Segments détectés sur la route (abscisses s_i = i·ds_m, la dernière = length_m)."""
    s = [i * route["ds_m"] for i in range(route["n"] - 1)] + [route["length_m"]]
    return [seg.to_dict() for seg in detect_segments(Profile(s, route["alt_m"], route["grade_pct"]))]


def build_manifest(name: str, route: dict, created: str | None = None,
                   segments: list[dict] | None = None) -> dict:
    segments = build_segments(route) if segments is None else segments
    return {
        "format": "openride-world",
        "format_version": "1.3",
        "name": name,
        "created": created or datetime.now().astimezone().isoformat(timespec="seconds"),
        "compiler": {"name": "openride-fake-world", "version": "0.1.0"},
        "source": {"gpx": None, "gpx_sha256": None},
        "origin": {"lat": route["lat"][0], "lon": route["lon"][0], "alt_m": route["alt_m"][0],
                   "utm_zone": "32T"},
        "projection": "local_equirectangular",
        "route": {"present": True, "version": "1.0", "file": "route.json",
                  "length_m": route["length_m"], "ds_m": route["ds_m"], "n": route["n"],
                  "type": route["type"], "grade_clamped_points": 0},
        "layers": {
            "terrain": {"present": False},
            "buildings": {"present": False},
            "vegetation": {"present": False, "source": "none"},
            "poi": {"present": False},
            "water": {"present": False},
            "segments": {"present": True, "version": "1.0", "file": "segments.json",
                         "count": len(segments), "manual_count": 0},
        },
    }


def write_world(out_dir: Path, name: str, length_m: float, created: str | None = None,
                grade: Callable[[float], float] | None = None) -> Path:
    route = build_route(length_m, grade=grade)
    world = out_dir / f"{name}.world"
    world.mkdir(parents=True, exist_ok=True)
    segments = build_segments(route)
    (world / "route.json").write_text(json.dumps(route, separators=(",", ":")), encoding="utf-8")
    (world / "segments.json").write_text(
        json.dumps({"version": "1.0", "segments": segments}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (world / "manifest.json").write_text(
        json.dumps(build_manifest(name, route, created, segments), indent=2), encoding="utf-8")
    return world


def write_demo_world(out_dir: Path) -> Path:
    """Écrit le parcours de démonstration commun au core et à l'engine."""
    return write_world(out_dir, DEMO_NAME, DEMO_LENGTH_M, created=DEMO_CREATED)


def ensure_demo_world(routes_root: Path) -> Path:
    """Crée `<routes_root>/demo.world` s'il manque, et renvoie son chemin."""
    world = routes_root / f"{DEMO_NAME}.world"
    if not (world / "manifest.json").is_file():
        write_demo_world(routes_root)
    return world
