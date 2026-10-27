"""Extrait régional Geofabrik converti en base SQLite (lot W3, `docs/2.0/PLAN_SERIE_W.md` §3.1).

    openride-compiler region-add europe/france/provence-alpes-cote-d-azur [--keep-pbf]
    openride-compiler region-update europe/france/provence-alpes-cote-d-azur
    openride-compiler region-list [--json]

Le fichier `.osm.pbf` est téléchargé une fois (reprise possible, somme MD5 vérifiée), lu en un
passage par pyosmium (extra `worldgen` du paquet), converti en `brut/osm/<region>.sqlite` du cache
(schéma de `osmdb.py`), puis supprimé. La base est écrite à côté puis renommée : une conversion
interrompue ne laisse ni base partielle ni fichier temporaire.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..cache import Log, stderr_log
from ..errors import CompileError
from ..osm import USER_AGENT
from . import osmdb
from .store import WorldCache

GEOFABRIK_URL = "https://download.geofabrik.de"
CHUNK = 1 << 20
RETRIES = 3

Opener = Callable[[str, dict[str, str], str], Any]


def _urllib_opener(url: str, headers: dict[str, str], method: str = "GET"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT, **headers})
    try:
        return urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code == 416:      # reprise demandée au-delà de la fin : le fichier est complet
            return exc
        raise CompileError(f"{url} : erreur HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise ConnectionError(f"{url} : {exc}") from exc


class Downloader:
    """Téléchargement avec reprise (`Range`), fichier `.part` voisin et somme MD5.

    `opener(url, headers, method)` renvoie une réponse avec `status`, `headers` et `read(n)` ;
    elle est remplacée par un faux serveur dans les tests.
    """

    def __init__(self, opener: Opener = _urllib_opener, log: Log = stderr_log,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.opener = opener
        self.log = log
        self.sleep = sleep

    def text(self, url: str) -> str:
        with self.opener(url, {}, "GET") as resp:
            return resp.read().decode("utf-8", "replace")

    def last_modified(self, url: str) -> str | None:
        with self.opener(url, {}, "HEAD") as resp:
            return resp.headers.get("Last-Modified")

    def download(self, url: str, dest: Path, md5: str | None = None) -> dict[str, str]:
        """Écrit `dest` seulement si le fichier est complet et que sa somme MD5 est la bonne."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        info: dict[str, str] = {}
        for attempt in range(1, RETRIES + 1):
            have = part.stat().st_size if part.is_file() else 0
            headers = {"Range": f"bytes={have}-"} if have else {}
            try:
                with self.opener(url, headers, "GET") as resp:
                    status = getattr(resp, "status", 200)
                    info = {"last_modified": resp.headers.get("Last-Modified") or ""}
                    if status != 416:
                        mode = "ab" if status == 206 else "wb"
                        with open(part, mode) as out:
                            while chunk := resp.read(CHUNK):
                                out.write(chunk)
                break
            except ConnectionError as exc:
                if attempt == RETRIES:
                    raise CompileError(f"téléchargement interrompu ({exc}) ; relancer la commande pour reprendre") from exc
                self.log(f"téléchargement interrompu ({exc}), reprise ({attempt}/{RETRIES - 1})")
                self.sleep(2.0 * attempt)
        if md5:
            got = _md5(part)
            if got != md5.lower():
                part.unlink(missing_ok=True)
                raise CompileError(f"{url} : somme MD5 fausse ({got} au lieu de {md5}) ; fichier supprimé")
        os.replace(part, dest)
        return info


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


# --- conversion par pyosmium ----------------------------------------------------------------------

def _osmium():
    try:
        import osmium  # noqa: PLC0415 - dépendance facultative (extra `worldgen`)
    except ImportError as exc:
        raise CompileError("pyosmium n'est pas installé : pip install -e \"compiler[worldgen]\"") from exc
    return osmium


def _tags(obj) -> dict[str, str]:
    return {t.k: t.v for t in obj.tags}


def _ring(ring) -> list[tuple[float, float]]:
    return [(n.lon, n.lat) for n in ring]


def convert(source: Path, out: Path, region: str, source_name: str = "geofabrik",
            node_index: str = "flex_mem", log: Log = stderr_log) -> dict[str, int]:
    """Convertit un fichier OSM (`.osm.pbf` ou `.osm`) en base `out`, de façon atomique."""
    osmium = _osmium()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.tmp-{os.getpid()}")
    tmp.unlink(missing_ok=True)
    writer = osmdb.OsmDbWriter(tmp, source_name, region)
    newest = [0.0]

    def stamp(obj) -> None:
        ts = obj.timestamp
        if ts is not None and ts.year >= 2000:
            newest[0] = max(newest[0], ts.timestamp())

    class Handler(osmium.SimpleHandler):
        def node(self, n) -> None:
            stamp(n)
            if not n.tags:
                return
            tags = _tags(n)
            kind = osmdb.point_kind(tags)
            if kind and n.location.valid():
                writer.add_point(f"n{n.id}", kind, tags.get("name"), n.location.lon, n.location.lat)

        def way(self, w) -> None:
            stamp(w)
            tags = _tags(w)
            cls = osmdb.road_class(tags)
            lkind = osmdb.line_kind(tags)
            if cls is None and lkind is None:
                return
            if not all(nr.location.valid() for nr in w.nodes):
                return
            coords = [(nr.lon, nr.lat) for nr in w.nodes]
            if cls is not None:
                writer.add_road(w.id, tags, [nr.ref for nr in w.nodes], coords, cls)
            if lkind is not None:
                writer.add_line(f"w{w.id}", lkind, tags, coords)

        def relation(self, r) -> None:
            stamp(r)

        def area(self, a) -> None:
            tags = _tags(a)
            kind = osmdb.area_kind(tags)
            if kind is None:
                return
            osm_id = f"{'w' if a.from_way() else 'r'}{a.orig_id()}"
            for outer in a.outer_rings():
                holes = [_ring(inner) for inner in a.inner_rings(outer)]
                writer.add_area(osm_id, kind, tags, _ring(outer), holes)

    t0 = time.monotonic()
    try:
        Handler().apply_file(str(source), locations=True, idx=node_index)
        date = (datetime.fromtimestamp(newest[0], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if newest[0] else None)
        counts = writer.finish(osm_date=date)
        os.replace(tmp, out)
    except BaseException:
        writer.abort()
        tmp.unlink(missing_ok=True)
        for suffix in ("-journal", "-wal", "-shm"):
            Path(f"{tmp}{suffix}").unlink(missing_ok=True)
        raise
    log(f"{region} : {counts['roads']} routes, {counts['areas']} surfaces, {counts['lines']} cours d'eau, "
        f"{counts['points']} points en {time.monotonic() - t0:.0f} s ({out.stat().st_size / 1e6:.1f} Mo)")
    return counts


# --- régions du cache ------------------------------------------------------------------------------

def region_id(region: str) -> str:
    """`europe/france/provence-alpes-cote-d-azur` → `provence-alpes-cote-d-azur`."""
    rid = region.strip("/").rsplit("/", 1)[-1]
    if not rid or rid.startswith(".") or region.startswith("http"):
        raise CompileError(f"région Geofabrik invalide : {region!r} (exemple : europe/france/alsace)")
    return rid


def pbf_url(region: str) -> str:
    return f"{GEOFABRIK_URL}/{region.strip('/')}-latest.osm.pbf"


def region_add(region: str, cache: WorldCache, downloader: Downloader | None = None, keep_pbf: bool = False,
               node_index: str = "flex_mem", log: Log = stderr_log) -> dict[str, Any]:
    """Télécharge, vérifie, convertit et enregistre la région dans le cache ; renvoie l'entrée."""
    _osmium()
    downloader = downloader or Downloader(log=log)
    rid = region_id(region)
    url = pbf_url(region)
    md5_text = downloader.text(url + ".md5").split()
    if not md5_text:
        raise CompileError(f"{url}.md5 : somme MD5 absente")
    pbf = cache.root / "brut" / "osm" / f"{rid}.osm.pbf"
    log(f"téléchargement de {url}")
    info = downloader.download(url, pbf, md5_text[0])
    db_path = cache.osm_db_path(rid)
    try:
        counts = convert(pbf, db_path, region.strip("/"), log=log)
    finally:
        if not keep_pbf:
            pbf.unlink(missing_ok=True)
    with osmdb.OsmDb(db_path) as db:
        meta = db.meta
    bbox = [float(v) for v in meta["bbox"].split(",")] if meta.get("bbox") else None
    cache.set_region(rid, bbox=bbox)
    versions = {"schema_version": osmdb.SCHEMA_VERSION, "osm_date": meta.get("osm_date", ""),
                "last_modified": info.get("last_modified", "")}
    entry = cache.add(f"osm:{rid}", "osm", db_path, versions, region=rid)
    return {"region": rid, "path": str(db_path), "bytes": entry.bytes, "counts": counts, "versions": versions}


def region_update(region: str, cache: WorldCache, downloader: Downloader | None = None,
                  log: Log = stderr_log, **kw) -> dict[str, Any] | None:
    """Retélécharge seulement si Geofabrik publie un fichier plus récent ; None si déjà à jour."""
    downloader = downloader or Downloader(log=log)
    rid = region_id(region)
    entry = cache.get(f"osm:{rid}")
    remote = downloader.last_modified(pbf_url(region))
    if entry and remote and entry.versions.get("last_modified") == remote \
            and entry.versions.get("schema_version") == osmdb.SCHEMA_VERSION:
        log(f"{rid} : déjà à jour ({remote})")
        return None
    return region_add(region, cache, downloader, log=log, **kw)


def region_list(cache: WorldCache) -> list[dict[str, Any]]:
    osm = {e.region: e for e in cache.entries() if e.kind == "osm"}
    out = []
    for r in cache.regions():
        e = osm.get(r["id"])
        out.append({**r, "osm_date": e.versions.get("osm_date") if e else None,
                    "database": bool(e and (cache.root / e.path).is_file())})
    return out


# --- ligne de commande -----------------------------------------------------------------------------

def _cache(args) -> WorldCache:
    return WorldCache.from_config(args.config, log=lambda _: None)


def cmd_region_add(args) -> int:
    res = region_add(args.region, _cache(args), keep_pbf=args.keep_pbf, node_index=args.node_index)
    print(f"Région {res['region']} prête : {res['path']} ({res['bytes'] / 1e6:.1f} Mo, "
          f"données OSM du {res['versions']['osm_date'] or 'date inconnue'})")
    return 0


def cmd_region_update(args) -> int:
    res = region_update(args.region, _cache(args), node_index=args.node_index)
    print("Déjà à jour." if res is None else f"Région {res['region']} mise à jour ({res['bytes'] / 1e6:.1f} Mo).")
    return 0


def cmd_region_list(args) -> int:
    rows = region_list(_cache(args))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("Aucune région dans le cache.")
    for r in rows:
        state = f"OSM du {r['osm_date']}" if r["database"] else "sans base"
        pin = ", épinglée" if r["pinned"] else ""
        print(f"{r['id']:<40} {r['bytes'] / 1e6:>9.1f} Mo  {state}{pin}")
    return 0


def add_arguments(p, command: str) -> None:
    p.add_argument("--config", type=Path, default=None, help="config.toml (défaut : ~/OpenRide/config.toml)")
    if command == "region-list":
        p.add_argument("--json", action="store_true", help="sortie au format JSON")
        return
    p.add_argument("region", help="chemin Geofabrik, par exemple europe/france/provence-alpes-cote-d-azur")
    p.add_argument("--node-index", default="flex_mem",
                   help="index des positions de nœuds de pyosmium (sparse_file_array,<fichier> pour économiser la mémoire)")
    if command == "region-add":
        p.add_argument("--keep-pbf", action="store_true", help="garde le fichier .osm.pbf téléchargé")
