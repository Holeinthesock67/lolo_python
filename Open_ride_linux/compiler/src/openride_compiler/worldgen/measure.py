"""Mesures du monde ouvert : volumes, temps de génération, débit (lot W0).

    openride-compiler world-measure --lat LAT --lon LON [--heading DEG] [--km 10]
        [--region europe/france/…] [--out DOSSIER] [--cache-dir DOSSIER] [--offline] [--synthetic] [--yes]

Le script suit une ligne droite partant du départ au cap donné et mesure, dans l'ordre :
1. le relief Copernicus GLO-30 (cache du compilateur) ;
2. les tuiles vectorielles OpenFreeMap (zoom 14) d'un couloir de 2 km de large ;
3. l'extrait régional Geofabrik, seulement avec `--region` (pas de conversion : lot W3) ;
4. la génération de chaque carré de 1 km traversé : grille proche, routes du carré, fondu du
   terrain avec toutes ces routes, bâtiments, forêts et eau, écriture ;
5. une tuile lointaine de 5 km.

L'origine du repère est le coin de la grille de 5 km de la zone UTM le plus proche du départ
(plan §4) : les carrés mesurés sont ceux que le générateur rangera dans son cache.
Le rapport (`rapport.json`, `rapport.md`) et les fichiers générés restent dans `--out`, jamais
dans le dépôt. `--synthetic` remplace relief et routes par des données analytiques, sans réseau.
"""

from __future__ import annotations

import json
import math
import os
import platform
import shutil
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .. import __version__ as COMPILER_VERSION
from .. import constants as C
from ..cache import Log, stderr_log
from ..elevation import CopernicusGlo30Provider, ElevationProvider
from ..errors import CompileError
from ..frame import LocalFrame, utm_transformer, utm_zone_of
from ..osm import USER_AGENT
from ..terrain import FAR, NEAR, RouteAxis, blend, tile_coords
from . import mvt

OPENFREEMAP_TILEJSON = "https://tiles.openfreemap.org/planet"
GEOFABRIK_BASE = "https://download.geofabrik.de"
VT_ZOOM = 14
CORRIDOR_HALF_M = 1000.0         # couloir de 2 km de large autour de la ligne
SQUARE_MARGIN_M = 50.0           # routes lues autour d'un carré (bords partagés)
MIN_REQUEST_INTERVAL_S = 0.25    # au plus 4 requêtes par seconde
CONFIRM_BYTES = 1_000_000_000    # au-delà, confirmation avant de télécharger l'extrait
GRID_ORIGIN_M = 5000             # origine de séance sur la grille de 5 km
DENSIFY_M = 10.0
SQUARES_PER_KM = 3                # carrés proches nouveaux par km parcouru (plan §3.3)
SYNTHETIC_ROAD_SPACING_M = 400.0

# Classes OpenMapTiles qui ne sont pas des routes cyclables (autoroutes, voies rapides, rail…).
EXCLUDED_CLASSES = {"motorway", "trunk", "rail", "transit", "ferry", "aerialway", "busway",
                    "bus_guideway", "pier", "raceway"}
PAVED_ONLY_CLASSES = {"path", "track"}


def default_cache_dir() -> Path:
    return Path.home() / "OpenRide" / "Cache" / "monde"


def default_out_dir() -> Path:
    return default_cache_dir() / "mesures" / datetime.now().strftime("%Y-%m-%d_%H%M%S")


# --- réseau -----------------------------------------------------------------------------------

class Net:
    """Accès HTTP du script (remplacé par une doublure dans les tests)."""

    def __init__(self, timeout_s: float = 60.0, sleep: Callable[[float], None] = time.sleep) -> None:
        self.timeout_s = timeout_s
        self.sleep = sleep
        self.requests = 0
        self._last = 0.0

    def _wait(self) -> None:
        delay = MIN_REQUEST_INTERVAL_S - (time.monotonic() - self._last)
        if delay > 0:
            self.sleep(delay)
        self._last = time.monotonic()

    def _open(self, url: str, method: str = "GET"):
        self._wait()
        self.requests += 1
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            return urllib.request.urlopen(req, timeout=self.timeout_s)
        except urllib.error.HTTPError as exc:
            raise CompileError(f"{url} : erreur HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise CompileError(f"{url} : {exc}") from exc

    def get(self, url: str) -> bytes:
        with self._open(url) as resp:
            return resp.read()

    def head_size(self, url: str) -> int | None:
        with self._open(url, "HEAD") as resp:
            size = resp.headers.get("Content-Length")
        return int(size) if size and size.isdigit() else None

    def download(self, url: str, dest: Path) -> int:
        """Écrit `dest` de façon atomique (fichier temporaire voisin puis renommage)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.tmp-{os.getpid()}")
        try:
            with self._open(url) as resp, open(tmp, "wb") as out:
                shutil.copyfileobj(resp, out, length=1 << 20)
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
        return dest.stat().st_size


class OfflineNet:
    """Toute requête est refusée (`--offline`)."""

    requests = 0

    def _refuse(self, url: str, *_: Any) -> Any:
        raise CompileError(f"réseau interdit (--offline) : {url}")

    get = head_size = download = _refuse


# --- relief et repère -------------------------------------------------------------------------

def session_frame(lat: float, lon: float) -> tuple[LocalFrame, tuple[float, float]]:
    """Repère dont l'origine est le coin de la grille de 5 km le plus proche du départ.

    Renvoie aussi la position (x, z) du départ dans ce repère.
    """
    number, band, south = utm_zone_of(lat, lon)
    tr = utm_transformer(number, south)
    e, n = tr.transform(lon, lat)
    e0 = round(e / GRID_ORIGIN_M) * GRID_ORIGIN_M
    n0 = round(n / GRID_ORIGIN_M) * GRID_ORIGIN_M
    frame = LocalFrame(number, band, south, float(e0), float(n0), tr)
    return frame, (float(e - e0), float(-(n - n0)))


def analytic_relief(x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Relief synthétique : vallées et collines de 150 m sur un plateau à 600 m."""
    return 600.0 + 150.0 * np.sin(x / 900.0) * np.cos(z / 1300.0) + 40.0 * np.sin((x + z) / 310.0)


class FrameRelief:
    """Source d'altitude analytique exprimée dans le repère de la séance."""

    name = "synthetic"
    native_resolution_m = 0.0

    def __init__(self, frame: LocalFrame, func=analytic_relief) -> None:
        self.frame = frame
        self.func = func
        self.calls = 0

    def elevations(self, lats, lons) -> np.ndarray:
        self.calls += 1
        x, z = self.frame.to_xz(lats, lons)
        return np.asarray(self.func(np.asarray(x), np.asarray(z)), dtype=float)


class MultiAxis(RouteAxis):
    """Axe formé de plusieurs routes : les segments qui relient deux routes différentes sont ignorés."""

    def __init__(self, x, z, alt, line_id) -> None:
        super().__init__(x, z, alt)
        self.line_id = np.asarray(line_id)

    def _segment(self, px, pz, a, b):
        d, y = super()._segment(px, pz, a, b)
        cut = self.line_id[a] != self.line_id[b]
        return np.where(cut, np.inf, d), y


# --- objets mesurés ---------------------------------------------------------------------------

@dataclass
class Line:
    xz: np.ndarray              # (n, 2)


@dataclass
class Polygon:
    kind: str                   # « building », « wood », « water »
    outer: np.ndarray           # (n, 2)
    holes: list[np.ndarray] = field(default_factory=list)
    height_m: float | None = None


@dataclass
class Sources:
    roads: list[Line] = field(default_factory=list)
    polygons: list[Polygon] = field(default_factory=list)


@dataclass
class MeasureConfig:
    lat: float
    lon: float
    heading_deg: float = 0.0
    km: float = 10.0
    region: str | None = None
    out: Path | None = None
    cache_dir: Path | None = None
    offline: bool = False
    synthetic: bool = False
    yes: bool = False


# --- géométrie de la mesure -------------------------------------------------------------------

def path_points(start_xz: tuple[float, float], heading_deg: float, length_m: float,
                step_m: float = DENSIFY_M) -> np.ndarray:
    """Ligne droite depuis le départ au cap donné (x vers l'est, z vers le sud)."""
    s = np.arange(0.0, length_m + 1e-9, step_m)
    h = math.radians(heading_deg)
    return np.column_stack((start_xz[0] + s * math.sin(h), start_xz[1] - s * math.cos(h)))


def squares_along(points: np.ndarray, size_m: int = 1000) -> list[tuple[int, int]]:
    """Carrés de la grille traversés par la ligne, dans l'ordre du parcours."""
    out: list[tuple[int, int]] = []
    for x, z in points:
        key = (int(math.floor(x / size_m)), int(math.floor(z / size_m)))
        if not out or out[-1] != key:
            if key not in out:
                out.append(key)
    return out


def corridor_points(points: np.ndarray, heading_deg: float, half_m: float = CORRIDOR_HALF_M,
                    step_m: float = 100.0) -> np.ndarray:
    """Points qui couvrent le couloir (ligne décalée de part et d'autre, pas de 100 m)."""
    h = math.radians(heading_deg)
    nx, nz = math.cos(h), math.sin(h)              # normale à la ligne (vers la droite)
    sel = points[:: max(1, int(step_m / DENSIFY_M))]
    rows = [sel + np.array([o * nx, o * nz]) for o in np.arange(-half_m, half_m + 1e-9, step_m)]
    return np.vstack(rows)


def densify(xz: np.ndarray, step_m: float = DENSIFY_M) -> np.ndarray:
    out = [xz[0]]
    for a, b in zip(xz[:-1], xz[1:]):
        d = float(np.hypot(*(b - a)))
        k = max(1, int(math.ceil(d / step_m)))
        for t in np.arange(1, k + 1) / k:
            out.append(a + (b - a) * t)
    return np.asarray(out)


def synthetic_sources(points: np.ndarray, heading_deg: float) -> Sources:
    """Routes en grille légèrement ondulée, quelques bâtiments et une forêt, autour du couloir."""
    cor = corridor_points(points, heading_deg)
    x0, z0 = cor.min(axis=0) - SYNTHETIC_ROAD_SPACING_M
    x1, z1 = cor.max(axis=0) + SYNTHETIC_ROAD_SPACING_M
    sp = SYNTHETIC_ROAD_SPACING_M
    src = Sources()
    for x in np.arange(math.floor(x0 / sp) * sp, x1, sp):
        z = np.arange(z0, z1, 50.0)
        src.roads.append(Line(np.column_stack((x + 30.0 * np.sin(z / 170.0), z))))
    for z in np.arange(math.floor(z0 / sp) * sp, z1, sp):
        x = np.arange(x0, x1, 50.0)
        src.roads.append(Line(np.column_stack((x, z + 25.0 * np.cos(x / 210.0)))))
    rng = np.random.default_rng(7)
    for _ in range(int((x1 - x0) * (z1 - z0) / 20_000)):      # environ 50 bâtiments par km²
        cx, cz = rng.uniform(x0, x1), rng.uniform(z0, z1)
        w, d = rng.uniform(6, 14), rng.uniform(6, 12)
        ring = np.array([[cx, cz], [cx + w, cz], [cx + w, cz + d], [cx, cz + d]])
        src.polygons.append(Polygon("building", ring, height_m=float(rng.uniform(4, 10))))
    cx, cz = points[len(points) // 2]
    ang = np.linspace(0, 2 * math.pi, 40, endpoint=False)
    src.polygons.append(Polygon("wood", np.column_stack((cx + 300 + 250 * np.cos(ang), cz + 250 * np.sin(ang)))))
    return src


def _road_kept(tags: dict[str, Any]) -> bool:
    cls = str(tags.get("class", ""))
    if cls in EXCLUDED_CLASSES or cls.endswith("_construction"):
        return False
    if cls in PAVED_ONLY_CLASSES and tags.get("surface") != "paved":
        return False
    return tags.get("surface") != "unpaved"


def vector_tile_sources(tiles: dict[tuple[int, int], dict[str, mvt.Layer]], frame: LocalFrame) -> Sources:
    """Routes, bâtiments, forêts et eau des tuiles vectorielles, projetés dans le repère."""
    src = Sources()

    def to_xz(tx: int, ty: int, extent: int, ring) -> np.ndarray:
        pts = [mvt.tile_to_lonlat(VT_ZOOM, tx, ty, extent, px, py) for px, py in ring]
        lon = np.array([p[0] for p in pts])
        lat = np.array([p[1] for p in pts])
        x, z = frame.to_xz(lat, lon)
        return np.column_stack((x, z))

    for (tx, ty), layers in tiles.items():
        tr = layers.get("transportation")
        if tr:
            for f in tr.features:
                if f.kind == "line" and _road_kept(f.tags):
                    for line in f.geometry:
                        if len(line) >= 2:
                            src.roads.append(Line(to_xz(tx, ty, tr.extent, line)))
        for name, kind in (("building", "building"), ("water", "water"), ("landcover", "wood")):
            layer = layers.get(name)
            if not layer:
                continue
            for f in layer.features:
                if f.kind != "polygon" or (kind == "wood" and f.tags.get("class") not in ("wood", "forest")):
                    continue
                h = f.tags.get("render_height")
                for poly in f.geometry:
                    if len(poly["outer"]) >= 3:
                        src.polygons.append(Polygon(
                            kind, to_xz(tx, ty, layer.extent, poly["outer"]),
                            [to_xz(tx, ty, layer.extent, r) for r in poly["holes"] if len(r) >= 3],
                            float(h) if isinstance(h, (int, float)) else None))
    return src


# --- mesure -----------------------------------------------------------------------------------

def _stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"median": None, "p95": None, "max": None, "mean": None}
    arr = np.asarray(values, dtype=float)
    return {"median": float(np.median(arr)), "p95": float(np.percentile(arr, 95)),
            "max": float(arr.max()), "mean": float(arr.mean())}


def _rate_mb_s(nbytes: int, seconds: float) -> float | None:
    return round(nbytes / 1e6 / seconds, 3) if seconds > 0 and nbytes > 0 else None


class Measure:
    """Une campagne de mesure. `net` et `provider` sont remplaçables (tests)."""

    def __init__(self, cfg: MeasureConfig, net=None, provider: ElevationProvider | None = None,
                 log: Log = stderr_log, confirm: Callable[[str], bool] | None = None) -> None:
        self.cfg = cfg
        self.log = log
        self.out = Path(cfg.out or default_out_dir())
        self.cache = Path(cfg.cache_dir or default_cache_dir())
        self.frame, self.start_xz = session_frame(cfg.lat, cfg.lon)
        self.net = OfflineNet() if cfg.offline else (net or Net())
        if provider is not None:
            self.provider = provider
        elif cfg.synthetic:
            self.provider = FrameRelief(self.frame)
        else:
            self.provider = CopernicusGlo30Provider(offline=cfg.offline, log=log)
        self.confirm = confirm or _ask
        self.report: dict[str, Any] = {}
        self.points = path_points(self.start_xz, cfg.heading_deg, cfg.km * 1000.0)

    # -- rapport --------------------------------------------------------------------------------

    def _save(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        tmp = self.out / ".rapport.json.tmp"
        tmp.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.out / "rapport.json")

    def run(self) -> dict[str, Any]:
        cfg = self.cfg
        self.report = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "parametres": {"heading_deg": cfg.heading_deg, "km": cfg.km, "region": cfg.region,
                           "offline": cfg.offline, "synthetic": cfg.synthetic},
            "machine": {"python": platform.python_version(), "numpy": np.__version__,
                        "compilateur": COMPILER_VERSION, "coeurs": os.cpu_count(),
                        "systeme": platform.platform()},
            "repere": {"utm_zone": self.frame.zone, "grille_origine_m": GRID_ORIGIN_M},
        }
        self._save()
        self.report["relief"] = self.measure_dem()
        self._save()
        sources, self.report["tuiles_vectorielles"] = self.measure_vector_tiles()
        self._save()
        self.report["extrait_regional"] = self.measure_region()
        self._save()
        self.report["generation"] = self.measure_generation(sources)
        self._save()
        self.report["tuile_lointaine"] = far = self.measure_far()
        gen = self.report["generation"]
        if gen["secondes_par_km"] is not None:
            per_km = gen["secondes_par_km"] + far["secondes"]
            gen["secondes_par_km"] = round(per_km, 4)
            # Temps disponible pour 1 km : 120 s à 30 km/h, 51 s à 70 km/h (plan §3.3).
            gen["marge_30_kmh"] = round(120.0 / per_km, 1) if per_km > 0 else None
            gen["marge_70_kmh"] = round(3600.0 / 70.0 / per_km, 1) if per_km > 0 else None
        self._save()
        (self.out / "rapport.md").write_text(render_markdown(self.report), encoding="utf-8")
        self.log(f"rapport écrit dans {self.out}")
        return self.report

    # -- 1. relief ------------------------------------------------------------------------------

    def measure_dem(self) -> dict[str, Any]:
        if not isinstance(self.provider, CopernicusGlo30Provider):
            t0 = time.perf_counter()
            self.provider.elevations(np.array([self.cfg.lat]), np.array([self.cfg.lon]))
            return {"source": getattr(self.provider, "name", "synthetic"), "tuiles": [],
                    "secondes": round(time.perf_counter() - t0, 4)}
        cor = corridor_points(self.points, self.cfg.heading_deg)
        lat, lon = self.frame.to_latlon(cor[:, 0], cor[:, 1])
        keys = sorted({(int(math.floor(a)), int(math.floor(o))) for a, o in zip(lat, lon)})
        tiles = []
        for la, lo in keys:
            path = self.provider.tile_path(la, lo)
            cached = path.is_file()
            t0 = time.perf_counter()
            self.provider.elevations(np.array([la + 0.5]), np.array([lo + 0.5]))
            dt = time.perf_counter() - t0
            size = path.stat().st_size if path.is_file() else 0
            tiles.append({"tuile": path.name, "en_cache": cached, "octets": size,
                          "secondes": round(dt, 3), "mo_par_s": None if cached else _rate_mb_s(size, dt)})
            self.log(f"relief {path.name} : {size / 1e6:.1f} Mo, {'en cache' if cached else f'{dt:.1f} s'}")
        return {"source": self.provider.name, "tuiles": tiles}

    # -- 2. tuiles vectorielles -----------------------------------------------------------------

    def tile_url_template(self) -> str:
        cached = self.cache / "brut" / "tuiles" / "tilejson.json"
        try:
            data = self.net.get(OPENFREEMAP_TILEJSON)
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)
        except CompileError:
            if not cached.is_file():
                raise
            data = cached.read_bytes()
        try:
            tiles = json.loads(data)["tiles"]
            return str(tiles[0])
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise CompileError(f"TileJSON OpenFreeMap illisible : {exc}") from exc

    def vector_tile_keys(self) -> list[tuple[int, int]]:
        cor = corridor_points(self.points, self.cfg.heading_deg)
        lat, lon = self.frame.to_latlon(cor[:, 0], cor[:, 1])
        return sorted({mvt.lonlat_to_tile(VT_ZOOM, float(o), float(a)) for a, o in zip(lat, lon)})

    def measure_vector_tiles(self) -> tuple[Sources, dict[str, Any]]:
        if self.cfg.synthetic:
            src = synthetic_sources(self.points, self.cfg.heading_deg)
            return src, {"source": "synthetic", "routes": len(src.roads), "polygones": len(src.polygons)}
        keys = self.vector_tile_keys()
        template: str | None = None
        sizes: list[int] = []
        downloaded = cached = missing = 0
        dl_bytes = 0
        dl_time = decode_time = 0.0
        counts: dict[str, int] = {}
        decoded: dict[tuple[int, int], dict[str, mvt.Layer]] = {}
        for x, y in keys:
            path = self.cache / "brut" / "tuiles" / str(VT_ZOOM) / str(x) / f"{y}.mvt"
            if path.is_file():
                cached += 1
            elif self.cfg.offline:
                missing += 1
                continue
            else:
                if template is None:
                    template = self.tile_url_template()
                url = template.replace("{z}", str(VT_ZOOM)).replace("{x}", str(x)).replace("{y}", str(y))
                t0 = time.perf_counter()
                size = self.net.download(url, path)
                dl_time += time.perf_counter() - t0
                dl_bytes += size
                downloaded += 1
            data = path.read_bytes()
            sizes.append(len(data))
            t0 = time.perf_counter()
            try:
                layers = mvt.decode_tile(data)
            except mvt.MvtError as exc:
                self.log(f"tuile {x}/{y} illisible : {exc}")
                continue
            decode_time += time.perf_counter() - t0
            decoded[(x, y)] = layers
            for name, layer in layers.items():
                counts[name] = counts.get(name, 0) + len(layer.features)
        self.log(f"tuiles vectorielles : {len(keys)} ({downloaded} téléchargées, {cached} en cache, "
                 f"{missing} absentes), {sum(sizes) / 1e6:.1f} Mo")
        src = vector_tile_sources(decoded, self.frame)
        return src, {
            "source": "openfreemap", "zoom": VT_ZOOM, "tuiles": len(keys), "telechargees": downloaded,
            "en_cache": cached, "absentes": missing, "octets_total": int(sum(sizes)),
            "octets_moyen": round(statistics.mean(sizes)) if sizes else None,
            "octets_max": max(sizes) if sizes else None,
            "secondes_telechargement": round(dl_time, 3), "mo_par_s": _rate_mb_s(dl_bytes, dl_time),
            "secondes_decodage": round(decode_time, 3), "objets_par_couche": counts,
            "routes_gardees": len(src.roads), "polygones": len(src.polygons),
        }

    # -- 3. extrait régional --------------------------------------------------------------------

    def measure_region(self) -> dict[str, Any] | None:
        region = self.cfg.region
        if not region:
            return None
        region = region.strip("/")
        url = f"{GEOFABRIK_BASE}/{region}-latest.osm.pbf"
        dest = self.cache / "brut" / "osm" / f"{region.replace('/', '_')}-latest.osm.pbf"
        if dest.is_file():
            return {"region": region, "en_cache": True, "octets": dest.stat().st_size}
        if self.cfg.offline:
            return {"region": region, "en_cache": False, "octets": None, "note": "hors ligne"}
        announced = self.net.head_size(url)
        if announced and announced > CONFIRM_BYTES and not self.cfg.yes:
            if not self.confirm(f"L'extrait {region} pèse {announced / 1e9:.1f} Go. Télécharger ? [o/N] "):
                return {"region": region, "en_cache": False, "octets_annonces": announced, "note": "refusé"}
        t0 = time.perf_counter()
        size = self.net.download(url, dest)
        dt = time.perf_counter() - t0
        self.log(f"extrait {region} : {size / 1e6:.0f} Mo en {dt:.0f} s")
        return {"region": region, "en_cache": False, "octets_annonces": announced, "octets": size,
                "secondes": round(dt, 2), "mo_par_s": _rate_mb_s(size, dt), "fichier": str(dest)}

    # -- 4. génération --------------------------------------------------------------------------

    def _square_roads(self, ix: int, iz: int, roads: list[Line]) -> tuple[np.ndarray, np.ndarray]:
        """Points densifiés à 10 m des routes qui touchent le carré (marge comprise) et leur numéro."""
        lo = np.array([ix * 1000.0, iz * 1000.0]) - SQUARE_MARGIN_M - DENSIFY_M
        hi = lo + 1000.0 + 2 * (SQUARE_MARGIN_M + DENSIFY_M)
        pts, ids = [], []
        for k, road in enumerate(roads):
            xz = road.xz
            if (xz.max(axis=0) < lo).any() or (xz.min(axis=0) > hi).any():
                continue
            d = densify(xz)
            inside = ((d >= lo) & (d <= hi)).all(axis=1)
            if not inside.any():
                continue
            # Une route qui sort puis rentre donne plusieurs morceaux : chacun a son numéro.
            run = np.concatenate(([0], np.cumsum(np.diff(inside.astype(int)) == 1)))
            pts.append(d[inside])
            ids.append(k * 1000 + run[inside])
        if not pts:
            return np.zeros((0, 2)), np.zeros(0, dtype=int)
        return np.vstack(pts), np.concatenate(ids)

    def _altitudes(self, x: np.ndarray, z: np.ndarray) -> np.ndarray:
        lat, lon = self.frame.to_latlon(x, z)
        return np.asarray(self.provider.elevations(lat, lon), dtype=float)

    def generate_square(self, ix: int, iz: int, src: Sources, folder: Path) -> dict[str, Any]:
        t: dict[str, float] = {}
        t0 = time.perf_counter()
        gx, gz = tile_coords(ix, iz, NEAR)
        y = self._altitudes(gx.ravel(), gz.ravel())
        t["relief"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        rpts, rids = self._square_roads(ix, iz, src.roads)
        ralt = self._altitudes(rpts[:, 0], rpts[:, 1]) if len(rpts) else np.zeros(0)
        t["routes"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        if len(rpts) >= 2:
            axis = MultiAxis(rpts[:, 0], rpts[:, 1], ralt, rids)
            dist, y_route = axis.nearest(gx.ravel(), gz.ravel(), C.ROAD_HALF_WIDTH_M + C.BLEND_OUTER_M)
            y = blend(y, dist, y_route)
        grid = y.astype("<f4").reshape(gx.shape)
        t["fondu"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        corner = np.array([ix * 1000.0, iz * 1000.0])
        layers: dict[str, list[dict[str, Any]]] = {"buildings": [], "vegetation": [], "water": []}
        for poly in src.polygons:
            c = poly.outer.mean(axis=0)
            if not (corner <= c).all() or not (c < corner + 1000.0).all():
                continue
            rel = {"outer": np.round(poly.outer - corner, 2).tolist(),
                   "holes": [np.round(h - corner, 2).tolist() for h in poly.holes]}
            if poly.kind == "building":
                gi = np.clip(((poly.outer - corner) / NEAR.cell_m).round().astype(int), 0, 100)
                rel["base_y"] = round(float(np.nanmin(grid[gi[:, 1], gi[:, 0]])), 2)
                rel["height_m"] = poly.height_m or 6.0
                layers["buildings"].append(rel)
            elif poly.kind == "wood":
                layers["vegetation"].append({**rel, "kind": "wood", "density": C.DENSITY_WOOD})
            else:
                layers["water"].append({**rel, "kind": "lake"})
        t["couches"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        tmp = folder.with_name(f".{folder.name}.tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        (tmp / "near.f32").write_bytes(grid.tobytes())
        for name, items in layers.items():
            (tmp / f"{name}.json").write_text(json.dumps({"version": "1.0", "items": items}), encoding="utf-8")
        shutil.rmtree(folder, ignore_errors=True)
        os.replace(tmp, folder)
        t["ecriture"] = time.perf_counter() - t0

        size = sum(p.stat().st_size for p in folder.iterdir())
        return {"carre": [ix, iz], "secondes": {k: round(v, 4) for k, v in t.items()},
                "total_s": round(sum(t.values()), 4), "octets": size, "points_de_route": int(len(rpts)),
                "batiments": len(layers["buildings"]), "forets": len(layers["vegetation"]),
                "eau": len(layers["water"])}

    def measure_generation(self, src: Sources) -> dict[str, Any]:
        keys = squares_along(self.points)
        root = self.out / "carres"
        root.mkdir(parents=True, exist_ok=True)
        squares = []
        for ix, iz in keys:
            res = self.generate_square(ix, iz, src, root / f"{ix}_{iz}")
            squares.append(res)
            self.log(f"carré {ix},{iz} : {res['total_s'] * 1000:.0f} ms, {res['octets'] / 1e3:.0f} Ko")
        totals = [s["total_s"] for s in squares]
        steps = {k: _stats([s["secondes"][k] for s in squares])
                 for k in ("relief", "routes", "fondu", "couches", "ecriture")}
        # Besoin par kilomètre parcouru (plan §3.3) : environ 3 nouveaux carrés proches et une
        # tuile lointaine ; la tuile lointaine est mesurée à part (§5) et ajoutée dans run().
        med = _stats(totals)["median"]
        return {
            "carres": squares, "nombre": len(squares), "total_s": _stats(totals), "etapes_s": steps,
            "octets_total": int(sum(s["octets"] for s in squares)),
            "carres_par_km": SQUARES_PER_KM, "secondes_par_km": None if med is None else SQUARES_PER_KM * med,
        }

    # -- 5. tuile lointaine ---------------------------------------------------------------------

    def measure_far(self) -> dict[str, Any]:
        sx, sz = self.start_xz
        ix, iz = int(math.floor(sx / FAR.tile_m)), int(math.floor(sz / FAR.tile_m))
        t0 = time.perf_counter()
        gx, gz = tile_coords(ix, iz, FAR)
        grid = self._altitudes(gx.ravel(), gz.ravel()).astype("<f4")
        path = self.out / "carres" / f"far_{ix}_{iz}.f32"
        path.write_bytes(grid.tobytes())
        return {"tuile": [ix, iz], "secondes": round(time.perf_counter() - t0, 4), "octets": path.stat().st_size}


def _ask(question: str) -> bool:
    try:
        return input(question).strip().lower() in ("o", "oui", "y", "yes")
    except EOFError:
        return False


# --- rapport lisible --------------------------------------------------------------------------

def _fmt(v: Any, unit: str = "", digits: int = 1) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{digits}f}{unit}".replace(".", ",")
    return f"{v}{unit}"


def render_markdown(r: dict[str, Any]) -> str:
    p = r["parametres"]
    lines = [f"# Mesures du monde ouvert (lot W0) – {r['date']}", "",
             f"Couloir de {_fmt(float(p['km']))} km au cap {_fmt(float(p['heading_deg']), '°', 0)}, "
             f"zone UTM {r['repere']['utm_zone']}"
             + (" (données synthétiques)" if p["synthetic"] else "") + ". "
             f"Machine : {r['machine']['coeurs']} cœurs, Python {r['machine']['python']}, numpy {r['machine']['numpy']}.",
             "", "## Volumes", "", "| Donnée | Valeur |", "| --- | --- |"]
    dem = r.get("relief") or {}
    if not dem.get("tuiles"):
        lines.append(f"| Relief | {dem.get('source', '—')} (aucun téléchargement) |")
    for t in dem.get("tuiles", []):
        lines.append(f"| Relief {t['tuile']} | {_fmt(t['octets'] / 1e6, ' Mo')}"
                     + (" (en cache)" if t["en_cache"] else f", {_fmt(t['secondes'], ' s')}, {_fmt(t['mo_par_s'], ' Mo/s')}")
                     + " |")
    vt = r.get("tuiles_vectorielles") or {}
    if vt.get("source") == "synthetic":
        lines.append(f"| Routes et décor | synthétiques : {vt['routes']} routes, {vt['polygones']} polygones |")
    if vt.get("source") == "openfreemap":
        lines += [f"| Tuiles vectorielles (zoom {vt['zoom']}) | {vt['tuiles']} tuiles, "
                  f"{_fmt(vt['octets_total'] / 1e6, ' Mo')} (moyenne {_fmt((vt['octets_moyen'] or 0) / 1e3, ' Ko')}, "
                  f"maximum {_fmt((vt['octets_max'] or 0) / 1e3, ' Ko')}) |",
                  f"| Débit des tuiles | {_fmt(vt['mo_par_s'], ' Mo/s')} |",
                  f"| Tuiles par km | {_fmt(vt['tuiles'] / float(p['km']))} |"]
    reg = r.get("extrait_regional")
    if reg:
        lines.append(f"| Extrait {reg['region']} | {_fmt((reg.get('octets') or 0) / 1e6, ' Mo', 0)}"
                     + (f", {_fmt(reg.get('secondes'), ' s', 0)}, {_fmt(reg.get('mo_par_s'), ' Mo/s')}" if reg.get("secondes") else "")
                     + " |")
    gen = r.get("generation") or {}
    tot = gen.get("total_s") or {}
    lines += ["", "## Génération par carré de 1 km", "",
              "| Étape | Médiane | 95e centile | Maximum |", "| --- | --- | --- | --- |"]
    for name, st in (gen.get("etapes_s") or {}).items():
        lines.append(f"| {name} | {_fmt((st['median'] or 0) * 1000, ' ms', 0)} | "
                     f"{_fmt((st['p95'] or 0) * 1000, ' ms', 0)} | {_fmt((st['max'] or 0) * 1000, ' ms', 0)} |")
    lines.append(f"| **Total** | {_fmt((tot.get('median') or 0) * 1000, ' ms', 0)} | "
                 f"{_fmt((tot.get('p95') or 0) * 1000, ' ms', 0)} | {_fmt((tot.get('max') or 0) * 1000, ' ms', 0)} |")
    far = r.get("tuile_lointaine") or {}
    lines += ["", f"{gen.get('nombre', 0)} carrés, {_fmt((gen.get('octets_total') or 0) / 1e6, ' Mo', 2)} écrits ; "
              f"tuile lointaine de 5 km : {_fmt((far.get('secondes') or 0) * 1000, ' ms', 0)}.", "",
              f"Calcul par kilomètre de route ({gen.get('carres_par_km', 3)} carrés proches et une tuile lointaine) : "
              f"{_fmt(gen.get('secondes_par_km'), ' s', 2)}. "
              f"Marge (temps disponible / temps de calcul) : {_fmt(gen.get('marge_30_kmh'), ' fois', 0)} à 30 km/h, "
              f"{_fmt(gen.get('marge_70_kmh'), ' fois', 0)} à 70 km/h (plan §3.3 : environ 50 fois attendu).", ""]
    return "\n".join(lines)


# --- ligne de commande ------------------------------------------------------------------------

def add_arguments(p) -> None:
    p.add_argument("--lat", type=float, required=True, help="latitude du départ")
    p.add_argument("--lon", type=float, required=True, help="longitude du départ")
    p.add_argument("--heading", type=float, default=0.0, help="cap de la ligne mesurée, en degrés (défaut : 0)")
    p.add_argument("--km", type=float, default=10.0, help="longueur du couloir en km (défaut : 10)")
    p.add_argument("--region", help="extrait Geofabrik à mesurer, par exemple europe/france/provence-alpes-cote-d-azur")
    p.add_argument("--out", type=Path, default=None,
                   help="dossier du rapport (défaut : ~/OpenRide/Cache/monde/mesures/<date>)")
    p.add_argument("--cache-dir", type=Path, default=None, help="cache du monde (défaut : ~/OpenRide/Cache/monde)")
    p.add_argument("--offline", action="store_true", help="aucune requête : tout depuis le cache")
    p.add_argument("--synthetic", action="store_true", help="relief et routes synthétiques, sans réseau")
    p.add_argument("--yes", action="store_true", help="pas de confirmation avant un gros téléchargement")


def run_from_args(args, log: Log = stderr_log) -> int:
    if not 0.0 < args.km <= 100.0:
        raise CompileError("--km doit être compris entre 0 et 100")
    cfg = MeasureConfig(lat=args.lat, lon=args.lon, heading_deg=args.heading % 360.0, km=args.km,
                        region=args.region, out=args.out, cache_dir=args.cache_dir,
                        offline=args.offline, synthetic=args.synthetic, yes=args.yes)
    m = Measure(cfg, log=log)
    m.run()
    print(m.out / "rapport.md")
    return 0
