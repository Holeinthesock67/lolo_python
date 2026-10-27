"""Requêtes du menu du monde ouvert (lot W11) : recherche de lieu, carte régionale, régions du cache.

Le core ne dépend pas du compilateur : il lance `python -m openride_compiler.worldgen.menu_query <commande>`
et lit une ligne JSON sur la sortie standard (`docs/contracts/ipc_v1.md`, messages `places`, `world_map`
et `world_regions`). Commandes :

    search  --text T [--limit N]            lieux des bases locales dont le nom contient T
    map     --lat A --lon B --radius R      routes autour d'un point, simplifiées à 20 m
    regions                                 régions du cache (taille, épinglage, boîte)
    pin     --region ID --pinned 0|1        épingle ou libère une région

Options communes : `--config chemin` (config.toml du cœur). Une erreur donne `{"error": "..."}` et le code 1.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ..errors import CompileError
from .osmdb import OsmDb
from .store import WorldCache

SIMPLIFY_M = 20.0
M_PER_DEG = 111_320.0
MAX_ROADS = 4000
MAX_PLACES = 50


def to_xz(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """Mètres depuis (lat0, lon0) : x vers l'est, z vers le sud (repère de la séance)."""
    return (lon - lon0) * M_PER_DEG * math.cos(math.radians(lat0)), -(lat - lat0) * M_PER_DEG


def simplify(points: Sequence[tuple[float, float]], tol: float = SIMPLIFY_M) -> list[tuple[float, float]]:
    """Douglas-Peucker : aucun point supprimé ne s'écarte de plus de `tol` mètres de la ligne gardée."""
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, az = points[a]
        bx, bz = points[b]
        dx, dz = bx - ax, bz - az
        norm = math.hypot(dx, dz)
        worst, at = -1.0, -1
        for i in range(a + 1, b):
            px, pz = points[i]
            if norm < 1e-9:
                d = math.hypot(px - ax, pz - az)
            else:
                d = abs(dx * (az - pz) - (ax - px) * dz) / norm
            if d > worst:
                worst, at = d, i
        if worst > tol:
            keep[at] = True
            stack += [(a, at), (at, b)]
    return [p for p, k in zip(points, keep) if k]


def _databases(cache: WorldCache, lat: float | None = None, lon: float | None = None) -> list[tuple[str, Path]]:
    """Bases locales présentes ; avec un point, seulement celles dont la boîte le contient (ou sans boîte)."""
    out = []
    for r in cache.regions():
        path = cache.osm_db_path(r["id"])
        if not path.is_file():
            continue
        box = r.get("bbox")
        if lat is not None and lon is not None and box and len(box) == 4 \
                and not (box[0] <= lon <= box[2] and box[1] <= lat <= box[3]):
            continue
        out.append((r["id"], path))
    return out


def search(cache: WorldCache, text: str, limit: int = MAX_PLACES) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for _region, path in _databases(cache):
        with OsmDb(path) as db:
            for p in db.search_places(text, limit):
                items.append({"name": p.name, "kind": p.kind, "lat": round(p.lat, 5), "lon": round(p.lon, 5),
                              "cached": True, "source": "base"})
        if len(items) >= limit:
            break
    return items[:limit]


def world_map(cache: WorldCache, lat: float, lon: float, radius_m: float) -> list[dict[str, Any]]:
    """Routes de la base dans le rayon : `{c, xz}`, `xz` = suite plate x, z en mètres entiers depuis le point."""
    dlat = radius_m / M_PER_DEG
    dlon = radius_m / (M_PER_DEG * max(math.cos(math.radians(lat)), 0.01))
    bbox = (lon - dlon, lat - dlat, lon + dlon, lat + dlat)
    roads: list[dict[str, Any]] = []
    for _region, path in _databases(cache, lat, lon):
        with OsmDb(path) as db:
            for r in db.roads_in(bbox):
                pts = simplify([to_xz(lat, lon, la, lo) for lo, la in r.coords])
                flat = [round(v) for p in pts for v in p]
                if len(flat) >= 4:
                    roads.append({"c": r.road_class, "xz": flat})
                if len(roads) >= MAX_ROADS:
                    return roads
    return roads


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(float(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def regions(cache: WorldCache) -> dict[str, Any]:
    items = [{"id": r["id"], "name": r["name"], "bytes": r["bytes"], "pinned": r["pinned"],
              "last_used": _iso(r["last_used"]), "bbox": r["bbox"]} for r in cache.regions()]
    return {"cache_bytes": cache.total_bytes(), "cache_max_bytes": cache.max_bytes, "items": items}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="menu_query", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("--text", required=True)
    s.add_argument("--limit", type=int, default=MAX_PLACES)
    m = sub.add_parser("map")
    m.add_argument("--lat", type=float, required=True)
    m.add_argument("--lon", type=float, required=True)
    m.add_argument("--radius", type=float, required=True)
    sub.add_parser("regions")
    p = sub.add_parser("pin")
    p.add_argument("--region", required=True)
    p.add_argument("--pinned", type=int, choices=(0, 1), required=True)
    args = ap.parse_args(argv)
    try:
        cache = WorldCache.from_config(args.config)
        try:
            if args.cmd == "search":
                out: dict[str, Any] = {"items": search(cache, args.text, args.limit)}
            elif args.cmd == "map":
                out = {"roads": world_map(cache, args.lat, args.lon, args.radius)}
            elif args.cmd == "pin":
                cache.pin(args.region, bool(args.pinned))
                out = regions(cache)
            else:
                out = regions(cache)
        finally:
            cache.close()
    except (CompileError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
