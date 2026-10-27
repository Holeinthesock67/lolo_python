"""Recettes de parcours et construction d'un pack depuis OpenStreetMap (lot O16).

Une recette (`<id>.toml`) décrit une montée publique et célèbre par quelques points de passage
(coordonnées arrondies à 4 décimales) et des valeurs de référence ; aucune trace n'est recopiée.
`build_pack` :

1. télécharge par Overpass (cache `~/.cache/openride/osm/`, comme les couches OSM) les routes
   ouvertes aux vélos autour des points : `highway` hors autoroute, sans `bicycle=no` ni accès
   interdit, chemins non revêtus exclus sauf `unpaved = true` dans la recette ; les sens uniques
   sont respectés ;
2. accroche chaque point au nœud routier le plus proche (au plus `SNAP_MAX_M`, sinon refus) et
   relie les points successifs par le plus court chemin (Dijkstra) ;
3. ré-échantillonne tous les `STEP_M` mètres, prend l'altitude du MNT (Copernicus par défaut) et
   contrôle longueur et dénivelé positif à ± 5 % de la référence (sinon refus, point à corriger) ;
4. écrit un GPX par col et sa fiche `.toml` (crédits OpenStreetMap) dans un dossier de pack
   installable par `route-pack-install` (lot O15).

Les recettes livrées sont dans `openride_compiler/route_packs/<pack>/` (installées avec le paquet).
"""

from __future__ import annotations

import heapq
import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .cache import Log, stderr_log
from .elevation import ElevationProvider
from .errors import CompileError
from .route_stats import GAIN_THRESHOLD_M, LibraryError, check_library, gain_loss
from .writer import normalize_name

BUILTIN_PACKS_DIR = Path(__file__).resolve().parent / "route_packs"
PACK_FILE = "pack.toml"
OSM_CREDITS = "© contributeurs OpenStreetMap, ODbL ; altitude Copernicus GLO-30"
BBOX_MARGIN_M = 1500.0
SNAP_MAX_M = 250.0
STEP_M = 10.0
TOLERANCE = 0.05
EARTH_R = 6371008.8

# Routes retenues ; `track`, `path` et `cycleway` non revêtus seulement avec `unpaved = true`.
HIGHWAYS = ("trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary",
            "tertiary_link", "unclassified", "residential", "living_street", "service", "road", "cycleway",
            "track", "path")
UNPAVED = {"unpaved", "gravel", "fine_gravel", "dirt", "earth", "ground", "grass", "mud", "sand", "compacted",
           "pebblestone", "rock"}
RECIPE_KEYS = {"name", "description", "region", "country", "tags", "waypoints", "ref_length_m", "ref_gain_m",
               "side", "unpaved", "credits"}


@dataclass
class Recipe:
    id: str
    name: str
    region: str
    country: str
    waypoints: list[tuple[float, float]]
    ref_length_m: float
    ref_gain_m: float
    tags: list[str] = field(default_factory=list)
    description: str = ""
    side: str = ""
    unpaved: bool = False


def load_recipe(path: Path) -> Recipe:
    """Lit et contrôle une recette ; `CompileError` avec le nom du fichier sinon."""
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CompileError(f"recette {path.name} illisible : {exc}") from exc

    def bad(msg: str) -> CompileError:
        return CompileError(f"recette {path.name} : {msg}")

    unknown = sorted(set(data) - RECIPE_KEYS)
    if unknown:
        raise bad(f"clé(s) inconnue(s) : {', '.join(unknown)}")
    for key in ("name", "region", "country"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise bad(f"{key} : texte non vide attendu")
    wps = data.get("waypoints")
    if not isinstance(wps, list) or len(wps) < 2:
        raise bad("waypoints : au moins deux points [lat, lon] (départ et sommet)")
    points = []
    for wp in wps:
        if (not isinstance(wp, list) or len(wp) != 2 or not all(isinstance(v, (int, float)) for v in wp)
                or not (-90 <= wp[0] <= 90 and -180 <= wp[1] <= 180)):
            raise bad(f"waypoints : point invalide {wp!r}")
        if any(round(v, 4) != v for v in wp):
            raise bad(f"waypoints : coordonnées arrondies à 4 décimales attendues, pas {wp!r}")
        points.append((float(wp[0]), float(wp[1])))
    for key in ("ref_length_m", "ref_gain_m"):
        if not isinstance(data.get(key), (int, float)) or data[key] <= 0:
            raise bad(f"{key} : nombre positif attendu")
    tags = data.get("tags", [])
    try:
        check_library({"tags": tags, "region": f"{data['region']}, {data['country']}"})
    except LibraryError as exc:
        raise bad(str(exc)) from exc
    return Recipe(id=normalize_name(path.stem), name=data["name"].strip(), region=data["region"].strip(),
                  country=data["country"].strip(), waypoints=points, ref_length_m=float(data["ref_length_m"]),
                  ref_gain_m=float(data["ref_gain_m"]), tags=sorted({t.lower() for t in tags}),
                  description=str(data.get("description", "")).strip(), side=str(data.get("side", "")).strip(),
                  unpaved=bool(data.get("unpaved", False)))


def pack_dir(name_or_path: str | Path) -> Path:
    """Dossier de recettes : chemin existant, sinon pack livré `route_packs/<nom>/`."""
    p = Path(name_or_path)
    if p.is_dir():
        return p
    builtin = BUILTIN_PACKS_DIR / str(name_or_path)
    if builtin.is_dir():
        return builtin
    known = sorted(d.name for d in BUILTIN_PACKS_DIR.iterdir() if d.is_dir()) if BUILTIN_PACKS_DIR.is_dir() else []
    raise CompileError(f"pack de recettes introuvable : {name_or_path} (livrés : {', '.join(known) or 'aucun'})")


def load_recipes(folder: Path) -> list[Recipe]:
    return [load_recipe(p) for p in sorted(Path(folder).glob("*.toml")) if p.name != PACK_FILE]


# --- Géométrie ---------------------------------------------------------------------------------

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(a)))


def bbox_around(points: list[tuple[float, float]], margin_m: float = BBOX_MARGIN_M) -> tuple[float, ...]:
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    dlat = math.degrees(margin_m / EARTH_R)
    dlon = dlat / max(0.05, math.cos(math.radians(sum(lats) / len(lats))))
    return (round(min(lats) - dlat, 4), round(min(lons) - dlon, 4),
            round(max(lats) + dlat, 4), round(max(lons) + dlon, 4))


def roads_query(bbox: tuple[float, ...]) -> str:
    s, w, n, e = bbox
    return (f'[out:json][timeout:120];\nway["highway"~"^({"|".join(HIGHWAYS)})$"]'
            f"({s:.4f},{w:.4f},{n:.4f},{e:.4f});\nout body geom;\n")


# --- Graphe routier ----------------------------------------------------------------------------

def way_allowed(tags: dict[str, str], unpaved_ok: bool) -> bool:
    hw = tags.get("highway", "")
    if hw not in HIGHWAYS:
        return False
    bicycle = tags.get("bicycle", "")
    if bicycle == "no" or bicycle == "use_sidepath":
        return False
    if tags.get("access") in ("no", "private") and bicycle not in ("yes", "designated", "permissive"):
        return False
    if tags.get("motorroad") == "yes" and bicycle not in ("yes", "designated"):
        return False
    surface = tags.get("surface", "")
    if not unpaved_ok:
        if surface in UNPAVED:
            return False
        if hw in ("track", "path") and surface not in ("asphalt", "paved", "concrete"):
            return False
    return True


def _oneway(tags: dict[str, str]) -> int:
    """1 : sens de la voie seulement, -1 : sens inverse, 0 : deux sens (vélos)."""
    if tags.get("oneway:bicycle") == "no" or tags.get("cycleway") == "opposite":
        return 0
    ow = tags.get("oneway", "")
    if ow in ("yes", "true", "1") or tags.get("junction") == "roundabout":
        return 1
    return -1 if ow == "-1" else 0


@dataclass
class RoadGraph:
    coords: dict[int, tuple[float, float]] = field(default_factory=dict)
    adj: dict[int, list[tuple[int, float]]] = field(default_factory=dict)

    def add_edge(self, a: int, b: int) -> None:
        d = haversine_m(*self.coords[a], *self.coords[b])
        self.adj.setdefault(a, []).append((b, d))
        self.adj.setdefault(b, [])


def build_graph(responses: list[dict[str, Any]], unpaved_ok: bool = False) -> RoadGraph:
    """Graphe orienté des routes permises, depuis des réponses Overpass `out body geom`."""
    g = RoadGraph()
    for resp in responses:
        for el in resp.get("elements", []):
            if el.get("type") != "way" or not way_allowed(el.get("tags") or {}, unpaved_ok):
                continue
            nodes, geom = el.get("nodes") or [], el.get("geometry") or []
            if len(nodes) != len(geom) or len(nodes) < 2:
                continue
            for nid, pt in zip(nodes, geom):
                g.coords[int(nid)] = (float(pt["lat"]), float(pt["lon"]))
            direction = _oneway(el.get("tags") or {})
            for a, b in zip(nodes, nodes[1:]):
                if direction >= 0:
                    g.add_edge(int(a), int(b))
                if direction <= 0:
                    g.add_edge(int(b), int(a))
    return g


def snap(g: RoadGraph, lat: float, lon: float, max_m: float = SNAP_MAX_M) -> int:
    best, best_d = None, math.inf
    for nid, (a, o) in g.coords.items():
        d = haversine_m(lat, lon, a, o)
        if d < best_d:
            best, best_d = nid, d
    if best is None or best_d > max_m:
        where = f"{best_d:.0f} m" if best is not None else "aucune route chargée"
        raise CompileError(f"point de passage ({lat:.4f}, {lon:.4f}) hors de toute route permise "
                           f"(route la plus proche : {where}, au plus {max_m:.0f} m)")
    return best


def shortest_path(g: RoadGraph, start: int, goal: int) -> list[int]:
    dist, prev = {start: 0.0}, {}
    heap = [(0.0, start)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == goal:
            break
        if d > dist.get(u, math.inf):
            continue
        for v, w in g.adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, math.inf):
                dist[v], prev[v] = nd, u
                heapq.heappush(heap, (nd, v))
    if goal not in dist:
        raise CompileError("aucun chemin routier permis entre deux points de passage successifs")
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    return path[::-1]


def route_through(g: RoadGraph, waypoints: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Suite de (lat, lon) passant par les points de passage dans l'ordre."""
    ids = [snap(g, *wp) for wp in waypoints]
    nodes: list[int] = [ids[0]]
    for a, b in zip(ids, ids[1:]):
        nodes.extend(shortest_path(g, a, b)[1:])
    return [g.coords[n] for n in nodes]


def resample(points: list[tuple[float, float]], step_m: float = STEP_M) -> list[tuple[float, float]]:
    out = [points[0]]
    carry = 0.0
    for (la0, lo0), (la1, lo1) in zip(points, points[1:]):
        seg = haversine_m(la0, lo0, la1, lo1)
        if seg <= 0:
            continue
        pos = step_m - carry
        while pos <= seg:
            t = pos / seg
            out.append((la0 + (la1 - la0) * t, lo0 + (lo1 - lo0) * t))
            pos += step_m
        carry = seg - (pos - step_m)
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def path_length_m(points: list[tuple[float, float]]) -> float:
    return sum(haversine_m(*a, *b) for a, b in zip(points, points[1:]))


# --- Construction ------------------------------------------------------------------------------

@dataclass
class BuiltClimb:
    recipe: Recipe
    points: list[tuple[float, float]]
    alt_m: list[float]
    length_m: float
    gain_m: float


def check_reference(recipe: Recipe, length_m: float, gain_m: float, tolerance: float = TOLERANCE) -> None:
    problems = []
    for label, got, ref in (("longueur", length_m, recipe.ref_length_m), ("dénivelé", gain_m, recipe.ref_gain_m)):
        if abs(got - ref) > tolerance * ref:
            problems.append(f"{label} {got:.0f} m au lieu de {ref:.0f} m ± {tolerance * 100:.0f} %")
    if problems:
        raise CompileError(f"{recipe.id} : trace refusée ({' ; '.join(problems)}) : point de passage à corriger")


def build_climb(recipe: Recipe, fetch: Callable[[str], dict[str, Any]], provider: ElevationProvider) -> BuiltClimb:
    response = fetch(roads_query(bbox_around(recipe.waypoints)))
    g = build_graph([response], unpaved_ok=recipe.unpaved)
    pts = resample(route_through(g, recipe.waypoints))
    alt = [float(a) for a in provider.elevations(np.array([p[0] for p in pts]), np.array([p[1] for p in pts]))]
    if not all(math.isfinite(a) for a in alt):
        raise CompileError(f"{recipe.id} : altitude absente du MNT sur une partie du parcours")
    length = path_length_m(pts)
    gain = gain_loss(alt, GAIN_THRESHOLD_M)[0]
    check_reference(recipe, length, gain)
    return BuiltClimb(recipe, pts, alt, length, gain)


def gpx_text(climb: BuiltClimb) -> str:
    pts = "".join(f'<trkpt lat="{la:.6f}" lon="{lo:.6f}"><ele>{a:.1f}</ele></trkpt>'
                  for (la, lo), a in zip(climb.points, climb.alt_m))
    name = climb.recipe.name.replace("&", "&amp;").replace("<", "&lt;")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<gpx version="1.1" creator="openride-compiler route-pack-build" '
            'xmlns="http://www.topografix.com/GPX/1/1">'
            f"<metadata><copyright author=\"OpenStreetMap contributors\"><license>"
            f"https://opendatacommons.org/licenses/odbl/</license></copyright></metadata>"
            f"<trk><name>{name}</name><trkseg>{pts}</trkseg></trk></gpx>\n")


def _toml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def library_toml(recipe: Recipe) -> str:
    lines = [f"name = {_toml_str(recipe.name)}"]
    desc = recipe.description or (f"Versant {recipe.side}." if recipe.side else "")
    if desc:
        lines.append(f"description = {_toml_str(desc[:500])}")
    lines.append(f"region = {_toml_str(f'{recipe.region}, {recipe.country}'[:80])}")
    lines.append("tags = [" + ", ".join(_toml_str(t) for t in recipe.tags) + "]")
    lines.append(f"credits = {_toml_str(OSM_CREDITS)}")
    return "\n".join(lines) + "\n"


def build_pack(source: Path, out_dir: Path, fetch: Callable[[str], dict[str, Any]],
               provider: ElevationProvider, only: list[str] | None = None,
               log: Log = stderr_log) -> tuple[Path, list[str], list[str]]:
    """Construit le pack dans `out_dir/<pack>/` ; renvoie son dossier, les cols faits et les refus."""
    recipes = load_recipes(source)
    if only:
        wanted = {normalize_name(o) for o in only}
        unknown = wanted - {r.id for r in recipes}
        if unknown:
            raise CompileError(f"col(s) inconnu(s) dans le pack : {', '.join(sorted(unknown))}")
        recipes = [r for r in recipes if r.id in wanted]
    if not recipes:
        raise CompileError(f"aucune recette dans {source}")
    target = Path(out_dir) / normalize_name(Path(source).name)
    target.mkdir(parents=True, exist_ok=True)
    meta = Path(source) / PACK_FILE
    if meta.is_file():
        (target / PACK_FILE).write_text(meta.read_text(encoding="utf-8"), encoding="utf-8")
    done, refused = [], []
    for r in recipes:
        try:
            climb = build_climb(r, fetch, provider)
        except CompileError as exc:
            refused.append(str(exc))
            log(f"  refusé : {exc}")
            continue
        (target / f"{r.id}.gpx").write_text(gpx_text(climb), encoding="utf-8")
        (target / f"{r.id}.toml").write_text(library_toml(r), encoding="utf-8")
        done.append(r.id)
        log(f"  {r.id} : {climb.length_m / 1000:.1f} km, {climb.gain_m:.0f} m de dénivelé positif")
    return target, done, refused
