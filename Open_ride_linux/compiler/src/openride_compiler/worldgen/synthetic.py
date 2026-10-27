"""Monde ouvert synthétique pour les essais sans réseau (lot W15).

- `synthetic_db` : base au schéma de W3 autour d'un point fictif en mer (golfe du Lion, aucun lieu
  réel) : grille de routes déformée par des sinusoïdes, classes variées, deux ponts, un tunnel, une
  impasse, un rond-point, quelques bâtiments, des forêts et un lac ;
- `write_live_world` : monde vivant complet (`world_format_v1.md` §13) depuis un scénario : route
  vers l'est en légère sinusoïde, carrefours scriptés (position, branches, pentes), relief
  analytique, tuiles proches et lointaines, couches par carré ;
- `openride-worldgen-fake` : faux générateur qui parle le dialogue de `worldgen_v1.md`. Il fait
  tourner le vrai générateur (W8) sur la base et le relief synthétiques, dans un cache temporaire,
  quel que soit le départ demandé, et peut simuler `offline`, `missing` et un plantage.

Tout est déterministe pour une graine donnée ; aucun accès réseau.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .. import constants as C
from ..frame import LocalFrame
from ..pipeline import _grade, _heading, sample_positions
from ..terrain import FAR, NEAR, build_level
from .edge_profile import split_parts
from .osmdb import OsmDb, OsmDbWriter
from .process import WorldSession, serve
from .squares import zone_frame
from .store import WorldCache

ORIGIN_LAT, ORIGIN_LON = 43.0, 4.6       # en mer, au large de la Camargue : aucun lieu réel
ZONE = "31T"


def _zone_xz(lat: float = ORIGIN_LAT, lon: float = ORIGIN_LON) -> tuple[float, float]:
    x, z = zone_frame(ZONE).to_xz(np.array([lat]), np.array([lon]))
    return float(x[0]), float(z[0])


def relief(x, z):
    """Relief analytique doux (pentes de quelques pour cent), en coordonnées de zone ou de séance."""
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    return 300.0 + 40.0 * np.sin(x / 900.0) * np.cos(z / 1100.0) + 15.0 * np.sin((x + z) / 450.0)


class AnalyticRelief:
    """Fournisseur d'altitude : `relief` évalué dans le repère de zone (indépendant de la séance)."""

    name = "synthetic"
    native_resolution_m = 0.0

    def __init__(self) -> None:
        self.frame = zone_frame(ZONE)
        self.calls = 0

    def elevations(self, lats, lons) -> np.ndarray:
        self.calls += 1
        x, z = self.frame.to_xz(np.asarray(lats, float), np.asarray(lons, float))
        return relief(x, z)


# --- base de routes ------------------------------------------------------------------------------

def synthetic_db(path: Path, size_km: float = 10.0, spacing_m: float = 400.0, seed: int = 0) -> dict[str, int]:
    """Écrit la base ; renvoie les nombres d'objets. Grille centrée sur le point fictif."""
    rng = random.Random(seed)
    frame = zone_frame(ZONE)
    cx, cz = _zone_xz()
    n = int(size_km * 1000 // spacing_m) + 1
    half = (n - 1) * spacing_m / 2

    def pos(i: float, j: float) -> tuple[float, float]:
        x = cx - half + i * spacing_m + 40.0 * math.sin(j * 0.9 + seed)
        z = cz - half + j * spacing_m + 40.0 * math.sin(i * 0.7 + 2 * seed)
        return x, z

    def ll(x: float, z: float) -> tuple[float, float]:
        lat, lon = frame.to_latlon(np.array([x]), np.array([z]))
        return float(lon[0]), float(lat[0])

    def node(i: int, j: int) -> int:
        return 1 + i * n + j

    w = OsmDbWriter(path, "synthetic", "synthetic/ocean")
    special = {("row", n // 2, 3): {"bridge": "yes", "layer": "1"},
               ("col", 2, n // 3): {"bridge": "yes", "layer": "1"},
               ("row", n // 3, n - 4): {"tunnel": "yes", "layer": "-1"}}
    for j in range(n):                                    # lignes est-ouest
        cls = "secondary" if j % 5 == 0 else "tertiary" if j % 3 == 0 else "residential"
        for i in range(n - 1):
            tags = {"highway": cls, **special.get(("row", j, i), {})}
            w.add_road(1_000_000 + j * 1000 + i, tags, [node(i, j), node(i + 1, j)],
                       [ll(*pos(i, j)), ll(*pos(i + 1, j))])
    for i in range(n):                                    # colonnes nord-sud
        if i % 7 == 3:
            tags0 = {"highway": "cycleway"}
        elif i % 4 == 1:
            tags0 = {"highway": "track", "surface": "asphalt"}
        else:
            tags0 = {"highway": "unclassified" if i % 2 else "residential"}
        for j in range(n - 1):
            w.add_road(2_000_000 + i * 1000 + j, {**tags0, **special.get(("col", i, j), {})},
                       [node(i, j), node(i, j + 1)], [ll(*pos(i, j)), ll(*pos(i, j + 1))])
    nid = n * n + 10
    # Impasse de 300 m à l'ouest, rond-point à l'est (quatre branches).
    x, z = pos(0, n // 2)
    w.add_road(3_000_001, {"highway": "residential"}, [node(0, n // 2), nid], [ll(x, z), ll(x - 300, z)])
    nid += 1
    x, z = pos(n - 1, n // 2)
    rx, rz, r = x + 200.0, z, 25.0
    ring = list(range(nid, nid + 8))
    nid += 8
    ring_xz = [(rx + r * math.sin(2 * math.pi * k / 8), rz - r * math.cos(2 * math.pi * k / 8)) for k in range(8)]
    w.add_road(3_000_002, {"highway": "tertiary", "junction": "roundabout"}, [*ring, ring[0]],
               [ll(*p) for p in ring_xz] + [ll(*ring_xz[0])])
    w.add_road(3_000_003, {"highway": "tertiary"}, [node(n - 1, n // 2), ring[6]], [ll(x, z), ll(*ring_xz[6])])
    for k, (dx, dz) in ((0, (0, -1)), (2, (1, 0)), (4, (0, 1))):
        px, pz = ring_xz[k]
        w.add_road(3_000_010 + k, {"highway": "tertiary"}, [ring[k], nid], [ll(px, pz), ll(px + 300 * dx, pz + 300 * dz)])
        nid += 1
    # Bâtiments le long de quelques routes, forêts, lac.
    counts = {"buildings": 0, "woods": 0, "lakes": 1}
    for k in range(60):
        i, j = rng.randrange(n - 1), rng.randrange(n)
        x0, z0 = pos(i + rng.uniform(0.2, 0.8), j)
        z0 += rng.choice((-1, 1)) * rng.uniform(15, 40)
        bw, bd = rng.uniform(8, 16), rng.uniform(6, 12)
        rect = [(x0, z0), (x0 + bw, z0), (x0 + bw, z0 + bd), (x0, z0 + bd), (x0, z0)]
        w.add_area(f"w{9_000_000 + k}", "building",
                   {"building": rng.choice(("house", "yes", "farm")), "building:levels": str(rng.randint(1, 3))},
                   [ll(*p) for p in rect])
        counts["buildings"] += 1
    for k in range(6):
        i, j = rng.randrange(1, n - 2), rng.randrange(1, n - 2)
        x0, z0 = pos(i + 0.15, j + 0.15)
        s = spacing_m * 0.7
        rect = [(x0, z0), (x0 + s, z0), (x0 + s, z0 + s), (x0, z0 + s), (x0, z0)]
        w.add_area(f"w{9_100_000 + k}", "wood", {"natural": "wood"}, [ll(*p) for p in rect])
        counts["woods"] += 1
    x0, z0 = pos(n // 2 + 0.2, n // 2 + 0.2)
    lake = [(x0 + 120 * math.cos(t), z0 + 90 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 17)]
    w.add_area("w9200000", "water", {"natural": "water", "water": "lake"}, [ll(*p) for p in lake])
    x0, z0 = pos(n // 2 + 0.5, n // 2 - 0.5)
    lon, lat = ll(x0, z0)
    w.add_point("n9300000", "village", "Village fictif", lon, lat)
    w.finish(osm_date="2026-10-01T00:00:00Z")
    counts["roads"] = 2 * n * (n - 1) + 4 + 1 + 3
    return counts


# --- monde vivant écrit d'un coup ----------------------------------------------------------------

def default_script(length_m: float = 20_000.0, seed: int = 0) -> dict[str, Any]:
    """Scénario par défaut : un carrefour tous les 1 200 m environ, deux ou trois branches."""
    rng = random.Random(seed)
    junctions = []
    s = 900.0
    while s < length_m - 600.0:
        n_br = rng.choice((2, 3, 3))
        angles = [0.0, -90.0, 90.0][:n_br] if n_br == 3 else [0.0, rng.choice((-60.0, 70.0))]
        junctions.append({"s_m": round(s, 1), "default": 0,
                          "branches": [{"angle_deg": a, "grade_pct": round(rng.uniform(-6, 8), 1) if a else None}
                                       for a in angles]})
        s += rng.uniform(900.0, 1500.0)
    return {"length_m": length_m, "seed": seed, "junctions": junctions}


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


class _SessionRelief:
    """Relief analytique pour `terrain.build_level`, qui interroge en latitude et longitude."""

    name = "synthetic"
    native_resolution_m = 0.0

    def __init__(self) -> None:
        self.zone = zone_frame(ZONE)

    def elevations(self, lats, lons) -> np.ndarray:
        x, z = self.zone.to_xz(np.asarray(lats, float), np.asarray(lons, float))
        return relief(x, z)


def write_live_world(folder: Path, script: dict[str, Any] | None = None) -> dict[str, Any]:
    """Écrit un monde vivant valide dans `folder` ; renvoie un résumé (longueur, tuiles, carrefours)."""
    script = script or default_script()
    folder = Path(folder)
    length = float(script["length_m"])
    zx, zz = _zone_xz()
    e0 = round(zx / 5000) * 5000
    n0 = round(-zz / 5000) * 5000
    zf = zone_frame(ZONE)
    frame = LocalFrame(zf.number, zf.band, zf.south, float(e0), float(n0), zf.transformer)
    # Route : départ 250 m à l'est et au sud de l'origine, vers l'est, sinusoïde de ± 60 m.
    s = sample_positions(length)
    u = np.linspace(0.0, length, 20_001)
    xu = 250.0 + u
    zu = 250.0 + 60.0 * np.sin(u / 1300.0)
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(xu), np.diff(zu)))])
    x = np.interp(s, cum, xu)
    z = np.interp(s, cum, zu)
    alt = relief(x + e0, z - n0)
    lat, lon = frame.to_latlon(x, z)
    route = {"s": s, "x": x, "z": z, "alt_m": alt, "lat": lat, "lon": lon,
             "grade_pct": np.clip(_grade(alt, s, False), -C.GRADE_LIMIT_PCT, C.GRADE_LIMIT_PCT),
             "heading_deg": _heading(x, z, False), "length_m": float(s[-1])}
    parts = split_parts(route)
    for k, part in enumerate(parts):
        _write(folder / "route" / f"part_{k}.json", part)
    # Terrain : relief fondu avec la route (même calcul que le compilateur), tuiles proches et lointaines.
    prov = _SessionRelief()
    near = build_level(route, frame, prov, NEAR, log=lambda _m: None)
    far = build_level(route, frame, prov, FAR, log=lambda _m: None)
    for level, tiles in (("near", near), ("far", far)):
        for (ix, iz), grid in tiles.items():
            p = folder / "terrain" / level / f"tile_{ix}_{iz}.f32"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(np.ascontiguousarray(grid, dtype="<f4").tobytes())
    # Couches par carré : un bâtiment tous les 500 m, coordonnées relatives au coin de la tuile.
    rng = random.Random(int(script.get("seed", 0)))
    layers: dict[tuple[int, int], list[dict]] = {key: [] for key in near}
    for k, sk in enumerate(np.arange(200.0, length, 500.0)):
        bx = float(np.interp(sk, s, x))
        bz = float(np.interp(sk, s, z)) + rng.choice((-1, 1)) * 25.0
        key = (math.floor(bx / 1000), math.floor(bz / 1000))
        if key not in layers:
            continue
        ox, oz = 1000 * key[0], 1000 * key[1]
        ring = [[round(bx - ox, 2), round(bz - oz, 2)], [round(bx + 12 - ox, 2), round(bz - oz, 2)],
                [round(bx + 12 - ox, 2), round(bz + 9 - oz, 2)], [round(bx - ox, 2), round(bz + 9 - oz, 2)]]
        base = float(relief(np.array([bx + e0]), np.array([bz - n0]))[0]) - 0.5
        layers[key].append({"id": f"w{8_000_000 + k}", "outer": ring, "holes": [], "base_y": round(base, 2),
                            "height_m": 6.0, "roof": "flat", "hint": {"building": "house", "colour": None}})
    for (ix, iz), items in layers.items():
        _write(folder / "buildings" / f"tile_{ix}_{iz}.json", {"version": C.BUILDINGS_VERSION, "buildings": items})
        _write(folder / "vegetation" / f"tile_{ix}_{iz}.json", {"version": C.VEGETATION_VERSION, "areas": []})
        _write(folder / "water" / f"tile_{ix}_{iz}.json", {"version": C.WATER_VERSION, "lines": [], "areas": []})
        _write(folder / "poi" / f"tile_{ix}_{iz}.json", {"version": C.POI_VERSION, "points": []})
    # Carrefours scriptés : la branche par défaut suit la route, les autres partent en ligne droite.
    junctions = []
    for k, j in enumerate(script.get("junctions", [])):
        sj = float(j["s_m"])
        if sj > length - 500.0:
            continue
        jx, jz = float(np.interp(sj, s, x)), float(np.interp(sj, s, z))
        jy = float(np.interp(sj, s, alt))
        head = float(np.interp(sj, s, route["heading_deg"]))
        branches = []
        for b, br in enumerate(j["branches"]):
            angle = float(br["angle_deg"])
            if b == int(j.get("default", 0)):
                ss = np.arange(sj, sj + 501.0, 10.0)
                px, pz, py = np.interp(ss, s, x), np.interp(ss, s, z), np.interp(ss, s, alt)
                grade = (py[-1] - py[0]) / 5.0
            else:
                h = math.radians(head + angle)
                d = np.arange(0.0, 501.0, 10.0)
                px, pz = jx + d * math.sin(h), jz - d * math.cos(h)
                grade = float(br.get("grade_pct") or 0.0)
                py = jy + d * grade / 100.0
            branches.append({"index": b, "heading_deg": round((head + angle) % 360.0, 1), "angle_deg": angle,
                             "road_class": "t" if b == 0 else "m", "grade_pct_500m": round(float(grade), 2),
                             "dead_end": False,
                             "preview": {"x": [round(float(v), 2) for v in px], "y": [round(float(v), 2) for v in py],
                                         "z": [round(float(v), 2) for v in pz]}})
        default = int(j.get("default", 0))
        junctions.append({"id": f"j{k}", "s_m": round(sj, 2), "x": round(jx, 2), "z": round(jz, 2),
                          "lock_s_m": round(sj - 30.0, 2), "default": default, "chosen": default, "locked": False,
                          "branches": branches})
    _write(folder / "junctions.json", {"version": "1.0", "revision": 1, "junctions": junctions})
    olat, olon = frame.to_latlon(np.array([0.0]), np.array([0.0]))
    manifest = {
        "format": C.FORMAT_NAME, "format_version": C.FORMAT_VERSION, "name": "Monde ouvert synthétique",
        "origin": {"lat": round(float(olat[0]), 7), "lon": round(float(olon[0]), 7),
                   "alt_m": round(float(relief(np.array([e0]), np.array([-n0]))[0]), 2), "utm_zone": ZONE},
        "projection": "utm",
        "route": {"present": True, "version": C.ROUTE_VERSION, "file": "route/", "length_m": round(float(s[-1]), 3),
                  "ds_m": C.DS_M, "n": int(len(s)), "type": "open", "alt_source": "synthetic"},
        "layers": {"terrain": {"present": True, "version": C.TERRAIN_VERSION, "sources": ["synthetic"],
                               "near_cell_m": C.NEAR_CELL_M, "far_cell_m": C.FAR_CELL_M,
                               "road_half_width_m": C.ROAD_HALF_WIDTH_M},
                   "buildings": {"present": True, "version": C.BUILDINGS_VERSION},
                   "vegetation": {"present": True, "version": C.VEGETATION_VERSION, "source": "osm"},
                   "poi": {"present": True, "version": C.POI_VERSION},
                   "water": {"present": True, "version": C.WATER_VERSION}},
        "live": True, "origin_kind": "utm_grid", "grid": {"near_m": 1000, "far_m": 5000, "e0": e0, "n0": n0},
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    near_keys = sorted([ix, iz] for ix, iz in near)
    _write(folder / "live.json", {
        "version": "1.0", "revision": 1,
        "route": {"parts": len(parts), "length_m": round(float(s[-1]), 2), "changed_from_part": 0},
        "tiles": {"near": near_keys, "far": sorted([ix, iz] for ix, iz in far)},
        "layer_tiles": near_keys, "status": "ok"})
    return {"length_m": float(s[-1]), "parts": len(parts), "near": len(near), "far": len(far),
            "junctions": len(junctions), "buildings": sum(len(v) for v in layers.values())}


# --- faux générateur ------------------------------------------------------------------------------

def fake_main(argv: list[str] | None = None) -> int:
    """`openride-worldgen-fake` : le vrai générateur sur la base et le relief synthétiques."""
    ap = argparse.ArgumentParser(prog="openride-worldgen-fake", description="Faux générateur du monde ouvert (W15)")
    ap.add_argument("--session", type=Path, help="dossier de séance")
    ap.add_argument("--config", type=Path, help="ignoré (même ligne de commande que openride-worldgen)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--size-km", type=float, default=10.0)
    ap.add_argument("--offline", action="store_true", help="annonce une séance hors ligne (data = offline)")
    ap.add_argument("--missing-after-m", type=float, help="plus de route connue au-delà de cette distance")
    ap.add_argument("--crash-after-m", type=float, help="plantage (code 3) au-delà de cette distance")
    ap.add_argument("--work-dir", type=Path, help="cache et base (par défaut un dossier temporaire)")
    args = ap.parse_args(argv)

    def log(m: str) -> None:
        print(f"[faux générateur] {m}", file=sys.stderr, flush=True)

    def send(msg: dict) -> None:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()

    work = args.work_dir or Path(tempfile.mkdtemp(prefix="openride-worldgen-fake-"))
    cache = WorldCache(work / "cache", 2 * 10**9, log=lambda _m: None)
    db_path = cache.osm_db_path("synthetic")
    if not db_path.is_file():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        synthetic_db(db_path, size_km=args.size_km, seed=args.seed)
    session = FakeSession(cache, AnalyticRelief(), send, {}, args.session, network=not args.offline,
                           log=log, db=OsmDb(db_path))
    session.missing_after_m = args.missing_after_m
    session.crash_after_m = args.crash_after_m
    log(f"prêt (base synthétique {db_path})")
    return serve(session, sys.stdin)


class FakeSession(WorldSession):
    """Vrai générateur, départ forcé sur la base fictive, avec pannes simulées."""

    missing_after_m: float | None = None
    crash_after_m: float | None = None

    def open(self, msg: dict[str, Any]) -> None:
        super().open({**msg, "lat": ORIGIN_LAT, "lon": ORIGIN_LON})

    def progress(self, s_m: float, v_mps: float = 0.0) -> None:
        if self.crash_after_m is not None and s_m >= self.crash_after_m:
            self.log("plantage simulé")
            sys.stdout.flush()
            os._exit(3)
        if self.missing_after_m is not None and s_m >= self.missing_after_m:
            self.s_m = s_m
            if self.data_state != "missing":
                self.data_state = "missing"
                self.status("ready", "plus de route connue (simulé)", "missing")
            return
        super().progress(s_m, v_mps)


if __name__ == "__main__":
    raise SystemExit(fake_main())
