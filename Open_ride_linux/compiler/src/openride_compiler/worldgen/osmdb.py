"""Base locale OpenStreetMap du monde ouvert (lot W3, schéma version 1, partagé avec W13).

Une base SQLite par région (`brut/osm/<region>.sqlite` du cache, W2) ne garde que ce dont le
graphe (W4) et le générateur (W7) ont besoin :

    meta(key, value)                     schema_version, source, region, osm_date, bbox, created
    roads(id, osm_id, highway, road_class, surface, bridge, tunnel, layer, oneway, name, nodes, coords)
    areas(id, osm_id, kind, tags, geom)  building, wood, scrub, orchard, water
    lines(id, osm_id, kind, tags, coords) river, stream, canal
    points(id, osm_id, kind, name, lon, lat)
    roads_rt, areas_rt, lines_rt, points_rt : index R-tree (id, min_lon, max_lon, min_lat, max_lat)

`nodes` : identifiants de nœuds int64 petit-boutistes ; `coords` : paires (lon, lat) float64
petit-boutistes. Les voies exclues du monde ouvert (`road_class` = `x`) sont gardées pour la carte
du menu, jamais pour le graphe.
"""

from __future__ import annotations

import json
import math
import sqlite3
import struct
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..errors import CompileError

SCHEMA_VERSION = 1
BATCH_ROWS = 10_000

# --- classes de route (contrat W1, LOT_W1 §4.5) ---------------------------------------------------

ROAD_CLASSES = ("p", "s", "t", "m", "c", "k")
EXCLUDED = "x"
_HIGHWAY_CLASS = {
    "primary": "p", "primary_link": "p",
    "secondary": "s", "secondary_link": "s",
    "tertiary": "t", "tertiary_link": "t",
    "unclassified": "m", "residential": "m", "living_street": "m", "road": "m", "service": "m",
    "cycleway": "c",
}
_EXCLUDED_HIGHWAYS = {"motorway", "motorway_link", "trunk", "trunk_link"}
_MAYBE_HIGHWAYS = {"path", "track"}
PAVED = {"asphalt", "concrete", "concrete:plates", "concrete:lanes", "paving_stones", "sett", "paved",
         "chipseal", "metal", "bricks"}
UNPAVED = {"unpaved", "gravel", "fine_gravel", "compacted", "dirt", "earth", "ground", "grass", "sand",
           "mud", "pebblestone", "rock", "woodchips", "grass_paver", "unhewn_cobblestone", "cobblestone"}
_SERVICE_EXCLUDED = {"parking_aisle", "driveway", "drive-through", "emergency_access"}
_NO_ACCESS = {"no", "private"}

AREA_KINDS = ("building", "wood", "scrub", "orchard", "water")
LINE_KINDS = ("river", "stream", "canal")
PLACE_KINDS = ("city", "town", "village", "hamlet")
SEARCH_KINDS = (*PLACE_KINDS, "mountain_pass")
AREA_TAGS = ("height", "building:levels", "building", "colour", "natural", "landuse", "water", "name")


def road_class(tags: dict[str, Any]) -> str | None:
    """Classe d'une voie OSM : `p`, `s`, `t`, `m`, `c`, `k`, `x` (exclue) ou None (pas une route)."""
    hw = tags.get("highway")
    if hw in _EXCLUDED_HIGHWAYS:
        return EXCLUDED
    if hw not in _HIGHWAY_CLASS and hw not in _MAYBE_HIGHWAYS:
        return None
    if tags.get("access") in _NO_ACCESS or tags.get("bicycle") in _NO_ACCESS:
        return EXCLUDED
    surface = tags.get("surface")
    if surface in UNPAVED:
        return EXCLUDED
    if hw == "service" and tags.get("service") in _SERVICE_EXCLUDED:
        return EXCLUDED
    if hw == "path":
        cyclable = tags.get("bicycle") in ("designated", "yes")
        return "c" if cyclable and surface in PAVED else EXCLUDED
    if hw == "track":
        return "k" if surface in PAVED or tags.get("tracktype") == "grade1" else EXCLUDED
    return _HIGHWAY_CLASS[hw]


def area_kind(tags: dict[str, Any]) -> str | None:
    """Sorte d'une surface gardée dans `areas` (mêmes règles que les couches du compilateur, I3 et I4)."""
    if tags.get("building", "no") != "no":
        return "building"
    if tags.get("natural") == "wood" or tags.get("landuse") == "forest":
        return "wood"
    if tags.get("natural") == "scrub":
        return "scrub"
    if tags.get("landuse") == "orchard":
        return "orchard"
    if tags.get("landuse") == "reservoir":
        return "water"
    if tags.get("natural") == "water" and tags.get("water") not in ("river", "stream", "canal", "ditch", "drain"):
        return "water"
    return None


def line_kind(tags: dict[str, Any]) -> str | None:
    w = tags.get("waterway")
    return w if w in LINE_KINDS else None


def point_kind(tags: dict[str, Any]) -> str | None:
    """Points d'intérêt du format (§8) et lieux de la recherche du menu."""
    if tags.get("place") in PLACE_KINDS:
        return tags["place"]
    if tags.get("mountain_pass") == "yes":
        return "mountain_pass"
    if tags.get("amenity") == "place_of_worship" and tags.get("building") in ("church", "chapel"):
        return "church_bell"
    if tags.get("tourism") == "viewpoint":
        return "viewpoint"
    return None


def useful_tags(tags: dict[str, Any]) -> dict[str, str]:
    return {k: str(tags[k]) for k in AREA_TAGS if k in tags}


def fold(text: str) -> str:
    """Minuscules sans accents ni ponctuation (recherche « evian » → « Évian-les-Bains »)."""
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in s).split())


def _int(v: Any, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def _flag(v: Any) -> int:
    return 0 if v in (None, "", "no", "0", "false") else 1


def _oneway(tags: dict[str, Any]) -> int:
    v = tags.get("oneway")
    if v in ("yes", "true", "1"):
        return 1
    if v == "-1":
        return -1
    return 1 if tags.get("junction") == "roundabout" else 0


# --- encodage ----------------------------------------------------------------------------------

def pack_ids(ids: Sequence[int]) -> bytes:
    return struct.pack(f"<{len(ids)}q", *ids)


def unpack_ids(blob: bytes) -> list[int]:
    return list(struct.unpack(f"<{len(blob) // 8}q", blob))


def pack_coords(coords: Sequence[tuple[float, float]]) -> bytes:
    return struct.pack(f"<{2 * len(coords)}d", *(v for p in coords for v in p))


def unpack_coords(blob: bytes) -> list[tuple[float, float]]:
    flat = struct.unpack(f"<{len(blob) // 8}d", blob)
    return list(zip(flat[0::2], flat[1::2]))


def bbox_of(coords: Iterable[tuple[float, float]]) -> tuple[float, float, float, float]:
    lons, lats = zip(*coords)
    return min(lons), min(lats), max(lons), max(lats)


# --- géométrie : « touche l'emprise » ------------------------------------------------------------

BBox = tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat


def _inside(p: tuple[float, float], b: BBox) -> bool:
    return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def segment_touches(a: tuple[float, float], c: tuple[float, float], b: BBox) -> bool:
    """Découpage de Liang-Barsky : le segment [a, c] a-t-il un point dans l'emprise (bords compris) ?"""
    t0, t1 = 0.0, 1.0
    dx, dy = c[0] - a[0], c[1] - a[1]
    for p, q in ((-dx, a[0] - b[0]), (dx, b[2] - a[0]), (-dy, a[1] - b[1]), (dy, b[3] - a[1])):
        if p == 0:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                return False
    return True


def polyline_touches(coords: Sequence[tuple[float, float]], b: BBox) -> bool:
    if len(coords) == 1:
        return _inside(coords[0], b)
    return any(segment_touches(coords[i], coords[i + 1], b) for i in range(len(coords) - 1))


def _point_in_ring(p: tuple[float, float], ring: Sequence[Sequence[float]]) -> bool:
    x, y = p
    inside = False
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def polygon_touches(geom: dict[str, Any], b: BBox) -> bool:
    """Le polygone (anneau extérieur, trous ignorés à cette échelle) touche-t-il l'emprise ?"""
    outer = [tuple(p) for p in geom["outer"]]
    ring = outer if outer[0] == outer[-1] else [*outer, outer[0]]
    if polyline_touches(ring, b):
        return True
    return _point_in_ring((b[0], b[1]), outer)


# --- écriture ----------------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE roads (id INTEGER PRIMARY KEY, osm_id INTEGER, highway TEXT, road_class TEXT, surface TEXT,
                    bridge INTEGER, tunnel INTEGER, layer INTEGER, oneway INTEGER, name TEXT,
                    nodes BLOB, coords BLOB);
CREATE TABLE areas (id INTEGER PRIMARY KEY, osm_id TEXT, kind TEXT, tags TEXT, geom TEXT);
CREATE TABLE lines (id INTEGER PRIMARY KEY, osm_id TEXT, kind TEXT, tags TEXT, coords BLOB);
CREATE TABLE points (id INTEGER PRIMARY KEY, osm_id TEXT, kind TEXT, name TEXT, lon REAL, lat REAL);
CREATE VIRTUAL TABLE roads_rt USING rtree(id, min_lon, max_lon, min_lat, max_lat);
CREATE VIRTUAL TABLE areas_rt USING rtree(id, min_lon, max_lon, min_lat, max_lat);
CREATE VIRTUAL TABLE lines_rt USING rtree(id, min_lon, max_lon, min_lat, max_lat);
CREATE VIRTUAL TABLE points_rt USING rtree(id, min_lon, max_lon, min_lat, max_lat);
"""
_INDEXES = """
CREATE INDEX roads_class ON roads(road_class);
CREATE INDEX areas_kind ON areas(kind);
CREATE INDEX points_kind ON points(kind);
"""


class OsmDbWriter:
    """Remplit une base neuve par lots de 10 000 lignes ; `finish()` crée les index et écrit `meta`."""

    def __init__(self, path: Path, source: str, region: str) -> None:
        self.path = Path(path)
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.db.execute("PRAGMA journal_mode = OFF")
        self.db.execute("PRAGMA synchronous = OFF")
        self.db.executescript(_SCHEMA)
        self.meta = {"schema_version": str(SCHEMA_VERSION), "source": source, "region": region}
        self.counts = {t: 0 for t in ("roads", "areas", "lines", "points")}
        self._rows: dict[str, list[tuple]] = {t: [] for t in self.counts}
        self._rt: dict[str, list[tuple]] = {t: [] for t in self.counts}
        self._bbox = [math.inf, math.inf, -math.inf, -math.inf]

    def _add(self, table: str, row: tuple, box: BBox) -> int:
        self.counts[table] += 1
        rid = self.counts[table]
        self._rows[table].append((rid, *row))
        self._rt[table].append((rid, box[0], box[2], box[1], box[3]))
        bb = self._bbox
        bb[0], bb[1] = min(bb[0], box[0]), min(bb[1], box[1])
        bb[2], bb[3] = max(bb[2], box[2]), max(bb[3], box[3])
        if len(self._rows[table]) >= BATCH_ROWS:
            self._flush(table)
        return rid

    def _flush(self, table: str) -> None:
        rows = self._rows[table]
        if not rows:
            return
        marks = ",".join("?" * len(rows[0]))
        self.db.execute("BEGIN")
        self.db.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
        self.db.executemany(f"INSERT INTO {table}_rt VALUES (?,?,?,?,?)", self._rt[table])
        self.db.execute("COMMIT")
        rows.clear()
        self._rt[table].clear()

    def add_road(self, osm_id: int, tags: dict[str, Any], nodes: Sequence[int],
                 coords: Sequence[tuple[float, float]], cls: str | None = None) -> int | None:
        cls = cls or road_class(tags)
        if cls is None or len(coords) < 2:
            return None
        return self._add("roads", (
            osm_id, tags.get("highway"), cls, tags.get("surface"), _flag(tags.get("bridge")),
            _flag(tags.get("tunnel")), _int(tags.get("layer")), _oneway(tags), tags.get("name"),
            pack_ids(nodes), pack_coords(coords)), bbox_of(coords))

    def add_area(self, osm_id: str, kind: str, tags: dict[str, Any], outer: Sequence[tuple[float, float]],
                 holes: Sequence[Sequence[tuple[float, float]]] = ()) -> int | None:
        if len(outer) < 3:
            return None
        geom = {"outer": [list(p) for p in outer], "holes": [[list(p) for p in h] for h in holes]}
        return self._add("areas", (osm_id, kind, json.dumps(useful_tags(tags), ensure_ascii=False),
                                   json.dumps(geom)), bbox_of(outer))

    def add_line(self, osm_id: str, kind: str, tags: dict[str, Any], coords: Sequence[tuple[float, float]]) -> int | None:
        if len(coords) < 2:
            return None
        keep = {k: str(tags[k]) for k in ("name", "width", "intermittent") if k in tags}
        return self._add("lines", (osm_id, kind, json.dumps(keep, ensure_ascii=False), pack_coords(coords)),
                         bbox_of(coords))

    def add_point(self, osm_id: str, kind: str, name: str | None, lon: float, lat: float) -> int:
        return self._add("points", (osm_id, kind, name, lon, lat), (lon, lat, lon, lat))

    def finish(self, osm_date: str | None = None, created: str | None = None) -> dict[str, int]:
        for t in self.counts:
            self._flush(t)
        self.db.executescript(_INDEXES)
        bbox = ",".join(f"{v:.7f}" for v in self._bbox) if math.isfinite(self._bbox[0]) else ""
        self.meta.update({"osm_date": osm_date or "", "bbox": bbox,
                          "created": created or time.strftime("%Y-%m-%dT%H:%M:%S")})
        self.db.execute("BEGIN")
        self.db.executemany("INSERT INTO meta VALUES (?, ?)", sorted(self.meta.items()))
        self.db.execute("COMMIT")
        self.db.execute("VACUUM")
        self.db.close()
        return dict(self.counts)

    def abort(self) -> None:
        try:
            self.db.close()
        except sqlite3.Error:
            pass


# --- lecture -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class Road:
    id: int
    osm_id: int
    highway: str
    road_class: str
    surface: str | None
    bridge: bool
    tunnel: bool
    layer: int
    oneway: int
    name: str | None
    nodes: list[int]
    coords: list[tuple[float, float]]


@dataclass(frozen=True)
class Area:
    id: int
    osm_id: str
    kind: str
    tags: dict[str, str]
    outer: list[tuple[float, float]]
    holes: list[list[tuple[float, float]]]


@dataclass(frozen=True)
class Line:
    id: int
    osm_id: str
    kind: str
    tags: dict[str, str]
    coords: list[tuple[float, float]]


@dataclass(frozen=True)
class Point:
    id: int
    osm_id: str
    kind: str
    name: str | None
    lon: float
    lat: float


_RT_JOIN = "JOIN {t}_rt rt ON rt.id = o.id WHERE rt.max_lon >= ? AND rt.min_lon <= ? AND rt.max_lat >= ? AND rt.min_lat <= ?"


class OsmDb:
    """Base régionale en lecture seule ; requêtes par emprise (min_lon, min_lat, max_lon, max_lat)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise CompileError(f"base OpenStreetMap absente : {self.path}")
        self.db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        self.db.create_function("fold", 1, lambda s: fold(s) if s else "", deterministic=True)
        try:
            self.meta = dict(self.db.execute("SELECT key, value FROM meta"))
        except sqlite3.DatabaseError as exc:
            raise CompileError(f"{self.path} : base OpenStreetMap illisible ({exc})") from exc
        if self.meta.get("schema_version") != str(SCHEMA_VERSION):
            raise CompileError(f"{self.path} : schéma {self.meta.get('schema_version')} "
                               f"au lieu de {SCHEMA_VERSION}, refaire `region-add`")

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "OsmDb":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _query(self, table: str, cols: str, bbox: BBox, extra: str = "", args: tuple = ()) -> list[tuple]:
        min_lon, min_lat, max_lon, max_lat = bbox
        sql = f"SELECT {cols} FROM {table} o " + _RT_JOIN.format(t=table) + extra + " ORDER BY o.id"
        return self.db.execute(sql, (min_lon, max_lon, min_lat, max_lat, *args)).fetchall()

    def count(self, table: str) -> int:
        return self.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def roads_in(self, bbox: BBox, include_excluded: bool = False) -> list[Road]:
        extra = "" if include_excluded else " AND o.road_class != 'x'"
        out = []
        for r in self._query("roads", "o.*", bbox, extra):
            coords = unpack_coords(r[11])
            if polyline_touches(coords, bbox):
                out.append(Road(r[0], r[1], r[2], r[3], r[4], bool(r[5]), bool(r[6]), r[7], r[8], r[9],
                                unpack_ids(r[10]), coords))
        return out

    def areas_in(self, bbox: BBox, kinds: Iterable[str] | None = None) -> list[Area]:
        extra, args = "", ()
        if kinds is not None:
            kinds = tuple(kinds)
            extra, args = f" AND o.kind IN ({','.join('?' * len(kinds))})", kinds
        out = []
        for r in self._query("areas", "o.*", bbox, extra, args):
            geom = json.loads(r[4])
            if polygon_touches(geom, bbox):
                out.append(Area(r[0], r[1], r[2], json.loads(r[3]), [tuple(p) for p in geom["outer"]],
                                [[tuple(p) for p in h] for h in geom["holes"]]))
        return out

    def lines_in(self, bbox: BBox) -> list[Line]:
        out = []
        for r in self._query("lines", "o.*", bbox):
            coords = unpack_coords(r[4])
            if polyline_touches(coords, bbox):
                out.append(Line(r[0], r[1], r[2], json.loads(r[3]), coords))
        return out

    def points_in(self, bbox: BBox, kinds: Iterable[str] | None = None) -> list[Point]:
        extra, args = "", ()
        if kinds is not None:
            kinds = tuple(kinds)
            extra, args = f" AND o.kind IN ({','.join('?' * len(kinds))})", kinds
        return [Point(*r) for r in self._query("points", "o.*", bbox, extra, args)]

    def search_places(self, text: str, limit: int = 50) -> list[Point]:
        """Lieux (villes, villages, cols) dont le nom contient `text`, sans tenir compte des accents.

        Ordre : nom qui commence par le texte d'abord, puis par importance (ville, bourg, village,
        hameau, col), puis par nom.
        """
        q = fold(text)
        if not q:
            return []
        rank = " ".join(f"WHEN '{k}' THEN {i}" for i, k in enumerate(SEARCH_KINDS))
        rows = self.db.execute(
            f"SELECT id, osm_id, kind, name, lon, lat FROM points "
            f"WHERE kind IN ({','.join('?' * len(SEARCH_KINDS))}) AND instr(fold(name), ?) > 0 "
            f"ORDER BY instr(fold(name), ?) != 1, CASE kind {rank} END, name LIMIT ?",
            (*SEARCH_KINDS, q, q, limit)).fetchall()
        return [Point(*r) for r in rows]
