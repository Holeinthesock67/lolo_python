"""Occupation du sol ESA WorldCover 2021 pour la couche biome (lot U2, décision U-Q11 du 27 octobre).

- Source : tuiles COG publiques de 3° × 3° d'ESA WorldCover 2021 (v200, 10 m, licence CC BY 4.0),
  compartiment AWS `esa-worldcover`. Seule l'emprise du parcours est lue, par fenêtre (lecture
  partielle du COG avec rasterio), jamais la tuile entière.
- Cache : `~/.cache/openride/landcover/esa_worldcover_2021/` (ou la variable d'environnement
  `OPENRIDE_LANDCOVER_CACHE`), un fichier `.npz` par carré de 0,1° ; un carré sans tuile (pleine mer)
  est noté comme tel pour ne pas être redemandé. Même politique que le MNT (`cache.py`) : réseau à la
  compilation seulement, 3 reprises à délai croissant, un carré présent n'est jamais relu sur le réseau,
  `offline` interdit tout accès.
- `classes(lats, lons)` : classe WorldCover du pixel qui contient chaque point (0 si inconnue).
"""

from __future__ import annotations

import http.client
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import numpy as np

from .cache import RETRIES, RETRY_DELAYS_S, TIMEOUT_S, Log, stderr_log
from .errors import CompileError

LANDCOVER_CACHE_ENV = "OPENRIDE_LANDCOVER_CACHE"
WORLDCOVER_NAME = "esa_worldcover_2021"
WORLDCOVER_BASE_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
WORLDCOVER_ATTRIBUTION = ("ESA WorldCover 2021 v200 © ESA WorldCover project / Contains modified Copernicus "
                          "Sentinel data (2021) processed by ESA WorldCover consortium, CC BY 4.0")
WORLDCOVER_LICENSE = "CC-BY-4.0"
TILE_DEG = 3            # tuiles WorldCover de 3° × 3°, nommées par leur coin sud-ouest
SQUARE_TENTHS = 1       # carré du cache : 0,1°


def landcover_cache_dir() -> Path:
    env = os.environ.get(LANDCOVER_CACHE_ENV)
    return Path(env) if env else Path.home() / ".cache" / "openride" / "landcover"


def worldcover_tile_name(lat_sw: int, lon_sw: int) -> str:
    """Nom de la tuile dont le coin sud-ouest est (lat_sw, lon_sw), multiples de 3°.

    Vérifié sur le service réel le 6 novembre 2026 : par exemple
    `ESA_WorldCover_10m_2021_v200_N45E006_Map` (fichier `<nom>.tif`, 404 en pleine mer).
    """
    ns = "N" if lat_sw >= 0 else "S"
    ew = "E" if lon_sw >= 0 else "W"
    return f"ESA_WorldCover_10m_2021_v200_{ns}{abs(lat_sw):02d}{ew}{abs(lon_sw):03d}_Map"


def square_keys(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Carrés de 0,1° (en dixièmes de degré, coin sud-ouest) des points : tableau (n, 2) d'entiers."""
    a = np.floor(np.asarray(lats, dtype=float) * 10.0 + 1e-9).astype(np.int64)
    o = np.floor(np.asarray(lons, dtype=float) * 10.0 + 1e-9).astype(np.int64)
    return np.stack((a.ravel(), o.ravel()), axis=1)


def square_filename(lat10: int, lon10: int) -> str:
    ns = "N" if lat10 >= 0 else "S"
    ew = "E" if lon10 >= 0 else "W"
    return f"sq_{ns}{abs(lat10):03d}_{ew}{abs(lon10):04d}.npz"


class LandcoverSource(Protocol):
    name: str

    def prepare(self, lats: np.ndarray, lons: np.ndarray) -> None:
        """Rend disponibles (cache ou réseau) les données de ces points ; lève CompileError."""
        ...

    def classes(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """Classe WorldCover (uint8) de chaque point ; 0 si inconnue."""
        ...


@dataclass
class Window:
    """Fenêtre lue : classes (lignes vers le sud), coin nord-ouest et taille du pixel en degrés."""
    data: np.ndarray
    left: float
    top: float
    xres: float
    yres: float

    def lookup(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        h, w = self.data.shape
        if h == 0 or w == 0:
            return np.zeros(np.shape(lats), dtype=np.uint8)
        col = np.clip(np.floor((lons - self.left) / self.xres).astype(np.int64), 0, w - 1)
        row = np.clip(np.floor((self.top - lats) / self.yres).astype(np.int64), 0, h - 1)
        return self.data[row, col]


# Lecteur d'une fenêtre : (adresse de la tuile, sud, ouest, nord, est) → fenêtre, ou None si la tuile
# n'existe pas (pleine mer). Remplaçable dans les tests (petites grilles générées).
Reader = Callable[[str, float, float, float, float], "Window | None"]


def _exists(url: str, timeout_s: float) -> bool:
    """La tuile existe-t-elle ? Adresse https : requête HEAD (404 → non) ; sinon chemin local."""
    if not url.startswith(("http://", "https://")):
        return Path(url).is_file()
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s):
            return True
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):     # S3 répond 403 ou 404 pour un objet absent
            return False
        raise


def rasterio_reader(timeout_s: float = TIMEOUT_S) -> Reader:
    """Lecture par fenêtre d'un COG (local ou https, par GDAL /vsicurl/) avec rasterio."""

    def read(url: str, south: float, west: float, north: float, east: float) -> Window | None:
        if not _exists(url, timeout_s):
            return None
        import rasterio   # importé ici : seule la lecture réelle en a besoin
        from rasterio.windows import Window as RioWindow
        from rasterio.windows import from_bounds

        path = f"/vsicurl/{url}" if url.startswith(("http://", "https://")) else url
        env = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
               "GDAL_HTTP_TIMEOUT": str(int(timeout_s)), "GDAL_HTTP_MAX_RETRY": "0"}
        try:
            with rasterio.Env(**env), rasterio.open(path) as ds:
                win = from_bounds(west, south, east, north, ds.transform)
                col0, row0 = int(round(win.col_off)), int(round(win.row_off))
                col1 = int(round(win.col_off + win.width))
                row1 = int(round(win.row_off + win.height))
                col0, row0 = max(col0, 0), max(row0, 0)
                col1, row1 = min(col1, ds.width), min(row1, ds.height)
                data = ds.read(1, window=RioWindow(col0, row0, max(col1 - col0, 0), max(row1 - row0, 0)))
                t = ds.transform
        except Exception as exc:  # noqa: BLE001 - réseau ou fichier : erreur de lecture, reprise possible
            raise OSError(f"lecture de {url} impossible : {exc}") from exc
        left = t.c + col0 * t.a
        top = t.f + row0 * t.e
        return Window(np.ascontiguousarray(data, dtype=np.uint8), left, top, t.a, -t.e)

    return read


class WorldCoverSource:
    """ESA WorldCover 2021, lu par fenêtres de 0,1° et gardé en cache."""

    name = WORLDCOVER_NAME

    def __init__(self, cache_dir: Path | None = None, offline: bool = False, log: Log = stderr_log,
                 base_url: str = WORLDCOVER_BASE_URL, reader: Reader | None = None,
                 sleep: Callable[[float], None] = time.sleep, timeout_s: float = TIMEOUT_S) -> None:
        self.dir = Path(cache_dir or landcover_cache_dir()) / self.name
        self.offline = offline
        self.log = log
        self.base_url = base_url.rstrip("/")
        self.reader = reader or rasterio_reader(timeout_s)
        self.sleep = sleep
        self.squares: dict[tuple[int, int], Window] = {}
        self.downloads = 0

    # --- cache --------------------------------------------------------------------------------

    def square_path(self, lat10: int, lon10: int) -> Path:
        return self.dir / square_filename(lat10, lon10)

    @staticmethod
    def _read_square(path: Path) -> Window:
        try:
            with np.load(path) as f:
                geo = f["geo"]
                return Window(f["data"].astype(np.uint8), float(geo[0]), float(geo[1]),
                              float(geo[2]), float(geo[3]))
        except Exception as exc:  # noqa: BLE001 - fichier de cache corrompu
            raise CompileError(f"carré WorldCover illisible {path} ({exc}) : le supprimer du cache") from exc

    def _write_square(self, path: Path, win: Window) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        try:
            with open(tmp, "wb") as out:
                np.savez_compressed(out, data=win.data,
                                    geo=np.array([win.left, win.top, win.xres, win.yres], dtype=float))
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)

    def _fetch(self, lat10: int, lon10: int) -> Window:
        south, west = lat10 / 10.0, lon10 / 10.0
        north, east = (lat10 + SQUARE_TENTHS) / 10.0, (lon10 + SQUARE_TENTHS) / 10.0
        lat_sw = int(np.floor((lat10 + 0.5) / 10.0 / TILE_DEG)) * TILE_DEG
        lon_sw = int(np.floor((lon10 + 0.5) / 10.0 / TILE_DEG)) * TILE_DEG
        tile = worldcover_tile_name(lat_sw, lon_sw)
        url = f"{self.base_url}/{tile}.tif"
        label = f"WorldCover {square_filename(lat10, lon10)[3:-4]}"
        last_error: Exception | None = None
        for attempt in range(RETRIES + 1):
            if attempt:
                delay = RETRY_DELAYS_S[min(attempt - 1, len(RETRY_DELAYS_S) - 1)]
                self.log(f"  nouvelle tentative dans {delay:.0f} s ({attempt}/{RETRIES}) : {last_error}")
                self.sleep(delay)
            try:
                t0 = time.monotonic()
                self.log(f"lecture de {label} (tuile {tile})…")
                win = self.reader(url, south, west, north, east)
                if win is None:   # pas de tuile : pleine mer, classe 0 partout
                    win = Window(np.zeros((0, 0), dtype=np.uint8), west, north, 1.0, 1.0)
                self.downloads += 1
                self.log(f"  {label} : {win.data.size / 1e6:.1f} Mpx en {time.monotonic() - t0:.1f} s")
                return win
            except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException) as exc:
                last_error = exc
        raise CompileError(f"échec de la lecture de {label} après {RETRIES} reprises : {last_error}")

    def _load(self, lat10: int, lon10: int) -> Window:
        key = (lat10, lon10)
        if key in self.squares:
            return self.squares[key]
        path = self.square_path(lat10, lon10)
        if path.is_file():
            win = self._read_square(path)
        else:
            if self.offline:
                raise CompileError(f"occupation du sol WorldCover absente du cache ({path}) et réseau "
                                   "interdit (--offline) : relancer sans --offline pour la télécharger, "
                                   "imposer un biome avec --biome, ou retirer biome de --layers")
            win = self._fetch(lat10, lon10)
            self._write_square(path, win)
        self.squares[key] = win
        return win

    # --- interface ----------------------------------------------------------------------------

    def prepare(self, lats, lons) -> None:
        keys = np.unique(square_keys(lats, lons), axis=0)
        for lat10, lon10 in keys.tolist():
            self._load(int(lat10), int(lon10))

    def classes(self, lats, lons) -> np.ndarray:
        lats = np.asarray(lats, dtype=float)
        lons = np.asarray(lons, dtype=float)
        out = np.zeros(lats.shape, dtype=np.uint8)
        keys = square_keys(lats, lons)
        flat_lat, flat_lon = lats.ravel(), lons.ravel()
        flat = out.ravel()
        uniq, inverse = np.unique(keys, axis=0, return_inverse=True)
        inverse = inverse.ravel()
        for k, (lat10, lon10) in enumerate(uniq.tolist()):
            sel = inverse == k
            flat[sel] = self._load(int(lat10), int(lon10)).lookup(flat_lat[sel], flat_lon[sel])
        return flat.reshape(lats.shape)
