"""Tuiles vectorielles OpenFreeMap du monde ouvert (lot W13, plan §3.1, §3.2, §4 et décision W-Q4).

Les tuiles (zoom 14, schéma OpenMapTiles) remplissent la **même** base locale qu'un extrait
régional (schéma 1 de W3), `brut/osm/tuiles.sqlite`, si bien que graphe et générateur ne voient
aucune différence.

- Source : URL lue dans le TileJSON `https://tiles.openfreemap.org/planet`, relu au plus une fois par
  jour (copie dans `brut/tuiles/tilejson.json`) ; `User-Agent` du projet ; au plus 4 requêtes à la
  fois ; fichiers `brut/tuiles/14/<x>/<y>.mvt` enregistrés dans le cache (W2).
- Géométrie : tout est ramené en pixels globaux (tuile × étendue + pixel), puis découpé au carré
  exact de la tuile (la marge des tuiles voisines se recouvre) : une route coupée entre deux tuiles
  finit des deux côtés au même point du bord, donc au même nœud.
- Nœuds : pas d'identifiant OSM dans les tuiles ; identifiant négatif tiré des coordonnées
  quantifiées à 1e-7°. Voies : identifiant négatif tiré de la tuile, de l'objet et du morceau.
- Bâtiments : gardés dans la tuile qui contient leur centre (ils sont entiers dans la marge) ;
  autres surfaces découpées au carré de la tuile (Sutherland-Hodgman).
- Une tuile versée deux fois ne crée pas de doublon (table `tiles_loaded`).
- Préchargement (W-Q4) : départs des séances passées (première partie de route de chaque séance du
  cache), classés par fréquence puis récence ; tuiles et relief à moins de `prefetch_radius_km`,
  entrées marquées `prefetch`, arrêt avant le plafond moins 10 %.

Attribution à afficher (W11, W12) : « © OpenMapTiles © contributeurs OpenStreetMap ».
"""

from __future__ import annotations

import json
import math
import sqlite3
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable

from ..cache import Log, stderr_log
from ..errors import CompileError
from . import mvt, osmdb
from .measure import Net
from .osmdb import BBox, SCHEMA_VERSION
from .store import WorldCache

ZOOM = 14
TILEJSON_URL = "https://tiles.openfreemap.org/planet"
TILEJSON_MAX_AGE_S = 86_400.0
MAX_PARALLEL = 4
DB_NAME = "tuiles"
ATTRIBUTION = "© OpenMapTiles © contributeurs OpenStreetMap"
PREFETCH_HEADROOM = 0.9
EST_TILE_BYTES = 60_000
STITCH_M = 3.0           # taille moyenne d'une tuile de zoom 14, pour le budget de préchargement

_CLASS = {"motorway": "x", "trunk": "x", "primary": "p", "secondary": "s", "tertiary": "t",
          "minor": "m", "service": "m"}
_PLACE = {"city", "town", "village", "hamlet"}
_LANDCOVER = {"wood": "wood", "forest": "wood", "scrub": "scrub", "orchard": "orchard"}
_WATER_AREA = {"lake": "lake", "pond": "pond", "reservoir": "reservoir", "basin": "reservoir"}


# --- identifiants -------------------------------------------------------------------------------

def node_id(lon: float, lat: float) -> int:
    """Identifiant négatif d'un nœud : coordonnées quantifiées à 1e-7° (unique, stable)."""
    qx = int(round(lon * 1e7)) + 1_800_000_000
    qy = int(round(lat * 1e7)) + 900_000_000
    return -((qy << 32) | qx)


def way_id(x: int, y: int, feature: int, piece: int) -> int:
    return -(((x << ZOOM | y) << 24) | ((feature & 0xFFFFF) << 4) | (piece & 0xF))


def tile_key(x: int, y: int) -> str:
    return f"tile:{ZOOM}/{x}/{y}"


def tiles_for_bbox(bbox: BBox) -> list[tuple[int, int]]:
    x0, y1 = mvt.lonlat_to_tile(ZOOM, bbox[0], bbox[1])
    x1, y0 = mvt.lonlat_to_tile(ZOOM, bbox[2], bbox[3])
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


# --- découpage au carré de la tuile ---------------------------------------------------------------

def clip_line(pts: list[tuple[float, float]], x0: float, y0: float, x1: float, y1: float) -> list[list[tuple[float, float]]]:
    """Morceaux de la polyligne dans le rectangle (Liang-Barsky segment par segment)."""
    out: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        t0, t1 = 0.0, 1.0
        ok = True
        for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
            if p == 0:
                if q < 0:
                    ok = False
                    break
            else:
                r = q / p
                if p < 0:
                    t0 = max(t0, r)
                else:
                    t1 = min(t1, r)
        if not ok or t0 > t1:
            if cur:
                out.append(cur)
                cur = []
            continue
        pa = a if t0 == 0 else (a[0] + t0 * dx, a[1] + t0 * dy)
        pb = b if t1 == 1 else (a[0] + t1 * dx, a[1] + t1 * dy)
        if cur and cur[-1] != pa:
            out.append(cur)
            cur = []
        if not cur:
            cur = [pa]
        if pb != cur[-1]:
            cur.append(pb)
        if t1 < 1:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [p for p in out if len(p) >= 2]


def clip_polygon(ring: list[tuple[float, float]], x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    """Sutherland-Hodgman sur le rectangle ; anneau vide s'il est dehors."""
    def cut(poly, inside, inter):
        out = []
        for i, cur in enumerate(poly):
            prev = poly[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(inter(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(inter(prev, cur))
        return out

    def ix(a, b, x):
        t = (x - a[0]) / (b[0] - a[0])
        return (x, a[1] + t * (b[1] - a[1]))

    def iy(a, b, y):
        t = (y - a[1]) / (b[1] - a[1])
        return (a[0] + t * (b[0] - a[0]), y)

    poly = list(ring)
    for inside, inter in ((lambda p: p[0] >= x0, lambda a, b: ix(a, b, x0)),
                          (lambda p: p[0] <= x1, lambda a, b: ix(a, b, x1)),
                          (lambda p: p[1] >= y0, lambda a, b: iy(a, b, y0)),
                          (lambda p: p[1] <= y1, lambda a, b: iy(a, b, y1))):
        if not poly:
            break
        poly = cut(poly, inside, inter)
    return poly if len(poly) >= 3 else []


# --- base des tuiles --------------------------------------------------------------------------------

class TileDb:
    """Base `tuiles.sqlite` au schéma de W3, remplie tuile par tuile."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        fresh = not self.path.is_file()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.db.execute("PRAGMA journal_mode = WAL")
        if fresh:
            self.db.executescript(osmdb._SCHEMA + osmdb._INDEXES)
            meta = {"schema_version": str(SCHEMA_VERSION), "source": "openfreemap", "region": DB_NAME,
                    "osm_date": "", "bbox": "", "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
            self.db.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
        self.db.execute("CREATE TABLE IF NOT EXISTS tiles_loaded (z INTEGER, x INTEGER, y INTEGER, "
                        "PRIMARY KEY (z, x, y))")

    def close(self) -> None:
        self.db.close()

    def loaded(self, x: int, y: int) -> bool:
        return self.db.execute("SELECT 1 FROM tiles_loaded WHERE z = ? AND x = ? AND y = ?",
                               (ZOOM, x, y)).fetchone() is not None

    def counts(self) -> dict[str, int]:
        return {t: self.db.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("roads", "areas", "lines", "points")}

    def _next_id(self, table: str) -> int:
        return int(self.db.execute(f"SELECT coalesce(max(id), 0) FROM {table}").fetchone()[0]) + 1

    def _stitch(self, row: list, edge: list[bool]) -> list:
        """Bout de route au bord de la tuile : reprend le nœud d'une route voisine déjà versée à moins de 3 m.

        Les deux tuiles découpent la même route, mais chacune avec ses propres sommets quantifiés
        (et une marge limitée) : les points de bord peuvent différer d'un pixel ou deux.
        """
        nodes, coords = list(row[-2]), list(row[-1])
        for end, on in ((0, edge[0]), (-1, edge[1])):
            if not on:
                continue
            lon, lat = coords[end]
            eps = STITCH_M / 111_000.0
            best = None
            for nb, cb in self.db.execute(
                    "SELECT o.nodes, o.coords FROM roads o JOIN roads_rt rt ON rt.id = o.id "
                    "WHERE rt.max_lon >= ? AND rt.min_lon <= ? AND rt.max_lat >= ? AND rt.min_lat <= ?",
                    (lon - 2 * eps, lon + 2 * eps, lat - eps, lat + eps)):
                ids, pts = osmdb.unpack_ids(nb), osmdb.unpack_coords(cb)
                for k in (0, -1):
                    d = math.hypot((pts[k][0] - lon) * 111_000.0 * math.cos(math.radians(lat)),
                                   (pts[k][1] - lat) * 111_000.0)
                    if d <= STITCH_M and (best is None or d < best[0]):
                        best = (d, ids[k], pts[k])
            if best is not None:
                nodes[end], coords[end] = best[1], tuple(best[2])
        return [*row[:-2], nodes, coords]

    def load(self, x: int, y: int, data: bytes) -> dict[str, int]:
        """Verse une tuile ; rien si elle l'est déjà. Renvoie les nombres de lignes ajoutées."""
        if self.loaded(x, y):
            return {}
        rows = convert_tile(x, y, mvt.decode_tile(data))
        added: dict[str, int] = {}
        bb = [math.inf, math.inf, -math.inf, -math.inf]
        self.db.execute("BEGIN")
        try:
            for table, items in rows.items():
                rid = self._next_id(table)
                for item in items:
                    row, box = item[0], item[1]
                    if table == "roads":
                        row = self._stitch(row, item[2])
                        box = osmdb.bbox_of(row[-1])
                        row = (*row[:-2], osmdb.pack_ids(row[-2]), osmdb.pack_coords(row[-1]))
                    self.db.execute(f"INSERT INTO {table} VALUES ({','.join('?' * (len(row) + 1))})", (rid, *row))
                    self.db.execute(f"INSERT INTO {table}_rt VALUES (?,?,?,?,?)", (rid, box[0], box[2], box[1], box[3]))
                    bb = [min(bb[0], box[0]), min(bb[1], box[1]), max(bb[2], box[2]), max(bb[3], box[3])]
                    rid += 1
                added[table] = len(items)
            # emprise : celle de la tuile (même vide), réunie à l'emprise déjà connue
            w, s = mvt.tile_to_lonlat(ZOOM, x, y + 1, 1, 0, 0)
            e, n = mvt.tile_to_lonlat(ZOOM, x + 1, y, 1, 0, 0)
            old = self.db.execute("SELECT value FROM meta WHERE key = 'bbox'").fetchone()
            box = [w, s, e, n]
            if old and old[0]:
                o = [float(v) for v in old[0].split(",")]
                box = [min(o[0], w), min(o[1], s), max(o[2], e), max(o[3], n)]
            self.db.execute("INSERT OR REPLACE INTO meta VALUES ('bbox', ?)", (",".join(f"{v:.7f}" for v in box),))
            self.db.execute("INSERT INTO tiles_loaded VALUES (?, ?, ?)", (ZOOM, x, y))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return added


def _road_tags(t: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    cls, sub = str(t.get("class", "")), str(t.get("subclass", ""))
    surface = t.get("surface")
    if cls == "path":
        rc = "c" if sub == "cycleway" and surface != "unpaved" else "x"
    elif cls == "track":
        rc = "k" if surface == "paved" else "x"
    elif cls in _CLASS:
        rc = _CLASS[cls]
    elif cls.endswith("_construction") or cls in ("rail", "transit", "ferry", "aerialway", "busway", "raceway"):
        return None
    else:
        return None
    if surface == "unpaved":
        rc = "x"
    oneway = t.get("oneway")
    tags = {"highway": sub if cls == "path" and sub else cls, "surface": surface,
            "bridge": "yes" if t.get("brunnel") == "bridge" else None,
            "tunnel": "yes" if t.get("brunnel") == "tunnel" else None,
            "layer": t.get("layer"), "oneway": {1: "yes", -1: "-1"}.get(oneway if isinstance(oneway, int) else None),
            "name": t.get("name")}
    return tags, rc


def convert_tile(x: int, y: int, layers: dict[str, mvt.Layer]) -> dict[str, list[tuple[tuple, BBox]]]:
    """Lignes à insérer (sans identifiant de ligne) pour chaque table, avec leur emprise."""
    out: dict[str, list[tuple[tuple, BBox]]] = {"roads": [], "areas": [], "lines": [], "points": []}

    def lonlat(gx: float, gy: float, extent: int) -> tuple[float, float]:
        return mvt.tile_to_lonlat(ZOOM, 0, 0, extent, gx, gy)

    for lname, layer in layers.items():
        E = layer.extent
        X0, Y0 = x * E, y * E
        box = (X0, Y0, X0 + E, Y0 + E)

        def glob(p) -> tuple[float, float]:
            return (X0 + p[0], Y0 + p[1])

        for fi, f in enumerate(layer.features):
            t = f.tags
            if lname == "transportation" and f.kind == "line":
                conv = _road_tags(t)
                if conv is None:
                    continue
                tags, rc = conv
                piece = 0
                for line in f.geometry:
                    for part in clip_line([glob(p) for p in line], *box):
                        coords = [lonlat(px, py, E) for px, py in part]
                        nodes = [node_id(lo, la) for lo, la in coords]
                        keep = [0] + [k for k in range(1, len(nodes)) if nodes[k] != nodes[k - 1]]
                        coords = [coords[k] for k in keep]
                        nodes = [nodes[k] for k in keep]
                        if len(coords) < 2:
                            continue
                        row = [way_id(x, y, fi, piece), tags.get("highway"), rc, tags.get("surface"),
                               osmdb._flag(tags.get("bridge")), osmdb._flag(tags.get("tunnel")),
                               osmdb._int(tags.get("layer")), osmdb._oneway(tags), tags.get("name"), None,
                               nodes, coords]
                        edge = [_on_edge(part[0], box), _on_edge(part[-1], box)]
                        out["roads"].append((row, osmdb.bbox_of(coords), edge))
                        piece += 1
            elif lname == "waterway" and f.kind == "line" and t.get("class") in osmdb.LINE_KINDS:
                piece = 0
                for line in f.geometry:
                    for part in clip_line([glob(p) for p in line], *box):
                        coords = [lonlat(px, py, E) for px, py in part]
                        keep = {k: str(t[k]) for k in ("name", "intermittent") if k in t}
                        out["lines"].append(((f"v{x}_{y}_{fi}_{piece}", str(t["class"]),
                                              json.dumps(keep, ensure_ascii=False), osmdb.pack_coords(coords)),
                                             osmdb.bbox_of(coords)))
                        piece += 1
            elif f.kind == "polygon" and lname in ("building", "landcover", "landuse", "water"):
                if lname == "building":
                    kind, tags = "building", {"building": "yes"}
                    if t.get("render_height") is not None:
                        tags["height"] = str(t["render_height"])
                    if t.get("colour"):
                        tags["colour"] = str(t["colour"])
                elif lname in ("landcover", "landuse"):
                    kind = _LANDCOVER.get(str(t.get("subclass", ""))) or _LANDCOVER.get(str(t.get("class", "")))
                    if kind is None:
                        continue
                    tags = {"natural": "wood"} if kind == "wood" else {"natural": "scrub"} if kind == "scrub" \
                        else {"landuse": "orchard"}
                else:
                    water = _WATER_AREA.get(str(t.get("class", "")))
                    if water is None or t.get("intermittent") == 1:
                        continue
                    kind, tags = "water", {"natural": "water", "water": water}
                for k, poly in enumerate(f.geometry):
                    outer = [glob(p) for p in poly["outer"]]
                    holes = [[glob(p) for p in h] for h in poly["holes"]]
                    if kind == "building":
                        cx = sum(p[0] for p in outer) / len(outer)
                        cy = sum(p[1] for p in outer) / len(outer)
                        if not (box[0] <= cx < box[2] and box[1] <= cy < box[3]):
                            continue
                    else:
                        outer = clip_polygon(outer, *box)
                        holes = [h2 for h2 in (clip_polygon(h, *box) for h in holes) if h2]
                        if not outer:
                            continue
                    o = [lonlat(px, py, E) for px, py in outer]
                    hs = [[lonlat(px, py, E) for px, py in h] for h in holes]
                    geom = {"outer": [list(p) for p in o], "holes": [[list(p) for p in h] for h in hs]}
                    out["areas"].append(((f"v{x}_{y}_{fi}_{k}", kind, json.dumps(osmdb.useful_tags(tags), ensure_ascii=False),
                                          json.dumps(geom)), osmdb.bbox_of(o)))
            elif f.kind == "point" and lname in ("place", "poi", "mountain_peak"):
                cls, sub = str(t.get("class", "")), str(t.get("subclass", ""))
                if lname == "place":
                    kind = cls if cls in _PLACE else None
                elif lname == "poi":
                    kind = "church_bell" if cls == "place_of_worship" else "viewpoint" if sub == "viewpoint" else None
                else:
                    kind = "mountain_pass" if cls == "saddle" else None
                if kind is None:
                    continue
                for p in f.geometry:
                    gx, gy = glob(p)
                    if not (box[0] <= gx < box[2] and box[1] <= gy < box[3]):
                        continue
                    lo, la = lonlat(gx, gy, E)
                    name = t.get("name:fr") or t.get("name")
                    out["points"].append(((f"v{x}_{y}_{fi}", kind, str(name) if name else None, lo, la),
                                          (lo, la, lo, la)))
    return out


def _on_edge(p: tuple[float, float], box: tuple[int, int, int, int]) -> bool:
    return p[0] in (box[0], box[2]) or p[1] in (box[1], box[3])


# --- téléchargement ---------------------------------------------------------------------------------

class TileSource:
    """Tuiles OpenFreeMap vers le cache, puis versées dans `tuiles.sqlite`."""

    def __init__(self, cache: WorldCache, net: Any | None = None, network: bool = True,
                 clock: Callable[[], float] = time.time, log: Log = stderr_log) -> None:
        self.cache = cache
        self.net = net or Net()
        self.network = network
        self.clock = clock
        self.log = log
        self.db_path = cache.osm_db_path(DB_NAME)
        self.db = TileDb(self.db_path)
        self.downloads = 0
        self._template: str | None = None

    def path(self, x: int, y: int) -> Path:
        return self.cache.vector_tile_path(x, y, ZOOM)

    def template(self) -> str:
        """URL des tuiles d'après le TileJSON (relu au plus une fois par jour)."""
        if self._template:
            return self._template
        cached = self.cache.root / "brut" / "tuiles" / "tilejson.json"
        fresh = cached.is_file() and self.clock() - cached.stat().st_mtime < TILEJSON_MAX_AGE_S
        data = cached.read_bytes() if fresh else None
        if data is None:
            if not self.network:
                if not cached.is_file():
                    raise CompileError("TileJSON OpenFreeMap absent du cache et réseau coupé")
                data = cached.read_bytes()
            else:
                try:
                    data = self.net.get(TILEJSON_URL)
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    cached.write_bytes(data)
                except CompileError as exc:
                    if not cached.is_file():
                        raise CompileError(f"TileJSON OpenFreeMap indisponible ({exc}) : "
                                           "seules les tuiles déjà sur le PC servent") from exc
                    self.log(f"TileJSON OpenFreeMap indisponible ({exc}) : dernière copie gardée")
                    data = cached.read_bytes()
        try:
            self._template = str(json.loads(data)["tiles"][0])
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise CompileError(f"TileJSON OpenFreeMap illisible : {exc}") from exc
        return self._template

    def fetch(self, keys: Iterable[tuple[int, int]], prefetch: bool = False) -> list[tuple[int, int]]:
        """Télécharge les tuiles absentes (4 à la fois) ; renvoie celles qui sont sur le PC."""
        keys = sorted(set(keys))
        missing = [k for k in keys if not self.path(*k).is_file()]
        if missing and self.network:
            try:
                tpl = self.template()
            except CompileError as exc:
                self.log(str(exc))
                tpl = None
            if tpl:
                def one(k: tuple[int, int]) -> tuple[int, int] | None:
                    url = tpl.replace("{z}", str(ZOOM)).replace("{x}", str(k[0])).replace("{y}", str(k[1]))
                    try:
                        self.net.download(url, self.path(*k))
                        return k
                    except CompileError as exc:
                        self.log(f"tuile {ZOOM}/{k[0]}/{k[1]} non téléchargée : {exc}")
                        return None
                with ThreadPoolExecutor(MAX_PARALLEL) as pool:
                    done = [k for k in pool.map(one, missing) if k is not None]
                for k in done:
                    self.downloads += 1
                    self.cache.add(tile_key(*k), "tile", self.path(*k), {"zoom": ZOOM}, prefetch=prefetch)
        have = [k for k in keys if self.path(*k).is_file()]
        for k in have:
            if not prefetch:
                self.cache.mark_used(tile_key(*k))
        return have

    def ensure(self, bbox: BBox, prefetch: bool = False) -> int:
        """Tuiles de l'emprise téléchargées si possible et versées dans la base ; renvoie leur nombre."""
        n = 0
        for x, y in self.fetch(tiles_for_bbox(bbox), prefetch=prefetch):
            try:
                self.db.load(x, y, self.path(x, y).read_bytes())
                n += 1
            except mvt.MvtError as exc:
                self.log(f"tuile {ZOOM}/{x}/{y} illisible, supprimée : {exc}")
                self.path(x, y).unlink(missing_ok=True)
        return n


# --- préchargement (W-Q4) ---------------------------------------------------------------------------

def past_starts(cache: WorldCache) -> list[tuple[float, float, float]]:
    """(lat, lon, date) du départ de chaque séance passée du cache."""
    out = []
    for d in sorted(cache.sessions_dir().glob("*.world")):
        part = d / "route" / "part_0.json"
        try:
            p = json.loads(part.read_text(encoding="utf-8"))
            out.append((float(p["lat"][0]), float(p["lon"][0]), part.stat().st_mtime))
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue
    return out


def prefetch_plan(starts: Iterable[tuple[float, float, float]], radius_km: float = 10.0) -> list[dict[str, Any]]:
    """Lieux de départ regroupés (au km près), les plus fréquents puis les plus récents d'abord."""
    groups: dict[tuple[int, int], list[tuple[float, float, float]]] = {}
    for lat, lon, t in starts:
        groups.setdefault((round(lat * 100), round(lon * 100)), []).append((lat, lon, t))
    order = sorted(groups.values(), key=lambda g: (-len(g), -max(s[2] for s in g)))
    plan = []
    for g in order:
        lat = sum(s[0] for s in g) / len(g)
        lon = sum(s[1] for s in g) / len(g)
        dlat = radius_km / 111.0
        dlon = dlat / max(0.1, math.cos(math.radians(lat)))
        bbox = (lon - dlon, lat - dlat, lon + dlon, lat + dlat)
        tiles = [k for k in tiles_for_bbox(bbox)
                 if _tile_distance_km(k, lat, lon) <= radius_km]
        dem = sorted({(math.floor(a), math.floor(o)) for a in (lat - dlat, lat, lat + dlat)
                      for o in (lon - dlon, lon, lon + dlon)})
        plan.append({"lat": lat, "lon": lon, "count": len(g), "tiles": tiles, "dem": dem})
    return plan


def _tile_distance_km(k: tuple[int, int], lat: float, lon: float) -> float:
    w, s = mvt.tile_to_lonlat(ZOOM, k[0], k[1] + 1, 1, 0, 0)
    e, n = mvt.tile_to_lonlat(ZOOM, k[0] + 1, k[1], 1, 0, 0)
    clat = min(max(lat, s), n)
    clon = min(max(lon, w), e)
    return math.hypot((clat - lat) * 111.0, (clon - lon) * 111.0 * math.cos(math.radians(lat)))


def prefetch(source: TileSource, plan: list[dict[str, Any]], dem_fetch: Callable[[int, int], None] | None = None,
             tile_bytes: int = EST_TILE_BYTES) -> dict[str, int]:
    """Exécute le plan dans l'ordre ; s'arrête avant de dépasser le plafond moins 10 %."""
    cache = source.cache
    budget = int(cache.max_bytes * PREFETCH_HEADROOM)
    got = {"tiles": 0, "dem": 0, "places": 0}
    for place in plan:
        todo = [k for k in place["tiles"] if not source.path(*k).is_file()]
        stop = False
        for start in range(0, len(todo), MAX_PARALLEL * 4):
            batch = todo[start:start + MAX_PARALLEL * 4]
            if cache.total_bytes() + tile_bytes * len(batch) > budget:
                stop = True
                break
            got["tiles"] += len([k for k in source.fetch(batch, prefetch=True) if k in batch])
        if stop:
            source.log("préchargement arrêté : plafond du cache presque atteint")
            break
        if dem_fetch is not None:
            for la, lo in place["dem"]:
                try:
                    dem_fetch(la, lo)
                    got["dem"] += 1
                except CompileError as exc:
                    source.log(f"relief {la} {lo} non préchargé : {exc}")
        got["places"] += 1
    return got


# --- ligne de commande ---------------------------------------------------------------------------

def add_prefetch_arguments(p) -> None:
    p.add_argument("--config", type=Path, help="config.toml (section [open_world])")
    p.add_argument("--force", action="store_true", help="même si prefetch_history est faux")


def cmd_world_prefetch(args) -> int:
    """Préchargement autour des départs habituels, lancé en tâche de fond au démarrage d'OpenRide."""
    from ..elevation import CopernicusGlo30Provider
    from .store import read_open_world_config

    cfg = read_open_world_config(args.config)
    if not (cfg["prefetch_history"] or args.force) or not cfg["network"]:
        print("préchargement désactivé ([open_world] prefetch_history ou network)")
        return 0
    cache = WorldCache.from_config(args.config)
    source = TileSource(cache)
    plan = prefetch_plan(past_starts(cache), float(cfg["prefetch_radius_km"]))
    dem = CopernicusGlo30Provider()

    def dem_fetch(la: int, lo: int) -> None:
        dem.elevations([la + 0.5], [lo + 0.5])

    got = prefetch(source, plan, dem_fetch)
    print(f"préchargement : {got['places']} lieu(x), {got['tiles']} tuile(s), {got['dem']} tuile(s) de relief")
    return 0
