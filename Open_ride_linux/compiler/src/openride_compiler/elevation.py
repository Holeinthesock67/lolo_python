"""Sources d'altitude (interface ElevationProvider, SRS §7 ; lot B2 §3.1).

- `CopernicusGlo30Provider` : MNT Copernicus GLO-30, tuiles COG de 1° × 1° du compartiment
  public AWS `copernicus-dem-30m`, mises en cache puis lues avec rasterio, interpolation bilinéaire.
- `SyntheticProvider` : altitude analytique dans le repère d'un parcours, pour les tests.
- IGN RGE ALTI : emplacement réservé (`IgnRgeAltiProvider`), non implémenté en v1.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

import numpy as np

from .cache import Downloader, Log, NotFoundError, dem_cache_dir, stderr_log
from .errors import CompileError
from .frame import LocalFrame


class ElevationProvider(Protocol):
    name: str                    # « copernicus_glo30 », « synthetic », …
    native_resolution_m: float

    def elevations(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """Altitudes en mètres aux points donnés ; NaN si inconnue."""
        ...


# --- fournisseur synthétique ----------------------------------------------------------------

def default_relief(x: np.ndarray, z: np.ndarray) -> np.ndarray:
    return 1000.0 + 200.0 * np.sin(x / 700.0) * np.cos(z / 900.0)


class SyntheticProvider:
    """Altitude analytique `func(x, z)` dans le repère local d'origine (lat0, lon0)."""

    name = "synthetic"
    native_resolution_m = 0.0

    def __init__(self, origin_lat: float, origin_lon: float,
                 func: Callable[[np.ndarray, np.ndarray], np.ndarray] = default_relief) -> None:
        self.frame = LocalFrame.at(origin_lat, origin_lon)
        self.func = func
        self.calls = 0

    def elevations(self, lats, lons) -> np.ndarray:
        self.calls += 1
        x, z = self.frame.to_xz(lats, lons)
        return np.asarray(self.func(x, z), dtype=float) * np.ones_like(x, dtype=float)


# --- Copernicus GLO-30 ------------------------------------------------------------------------

COPERNICUS_BASE_URL = "https://copernicus-dem-30m.s3.amazonaws.com"


def copernicus_tile_name(lat_sw: int, lon_sw: int) -> str:
    """Nom de la tuile dont le coin sud-ouest est (lat_sw, lon_sw), en degrés entiers.

    Vérifié sur le service réel le 23 octobre 2026 : par exemple
    `Copernicus_DSM_COG_10_N45_00_E006_00_DEM` (fichier `<nom>/<nom>.tif`).
    """
    ns = "N" if lat_sw >= 0 else "S"
    ew = "E" if lon_sw >= 0 else "W"
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat_sw):02d}_00_{ew}{abs(lon_sw):03d}_00_DEM"


class _Tile:
    """Grille d'une tuile en mémoire ; pixels centrés (transformée affine de rasterio)."""

    def __init__(self, data: np.ndarray, left: float, top: float, xres: float, yres: float) -> None:
        self.data = data
        self.left, self.top, self.xres, self.yres = left, top, xres, yres

    def bilinear(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        h, w = self.data.shape
        # Coordonnées en pixels, l'entier k désignant le centre du pixel k.
        col = np.clip((lons - self.left) / self.xres - 0.5, 0.0, w - 1.0)
        row = np.clip((self.top - lats) / self.yres - 0.5, 0.0, h - 1.0)
        c0 = np.minimum(np.floor(col).astype(int), w - 2)
        r0 = np.minimum(np.floor(row).astype(int), h - 2)
        fc, fr = col - c0, row - r0
        d = self.data
        top = d[r0, c0] * (1 - fc) + d[r0, c0 + 1] * fc
        bottom = d[r0 + 1, c0] * (1 - fc) + d[r0 + 1, c0 + 1] * fc
        return top * (1 - fr) + bottom * fr


class CopernicusGlo30Provider:
    """MNT Copernicus GLO-30 (30 m, mondial, libre).

    - Tuiles absentes de `tileList.txt` : la mer, altitude 0.
    - Les tuiles et la liste sont mises en cache dans `<cache>/copernicus_glo30/`.
    - Un point situé dans la demi-maille de bord d'une tuile (entre le dernier centre de
      pixel et la tuile voisine) prend la valeur bornée du bord : écart d'au plus une maille.
    """

    name = "copernicus_glo30"
    native_resolution_m = 30.0

    def __init__(self, cache_dir: Path | None = None, offline: bool = False, log: Log = stderr_log,
                 downloader: Downloader | None = None, base_url: str = COPERNICUS_BASE_URL) -> None:
        self.dir = Path(cache_dir or dem_cache_dir()) / self.name
        self.downloader = downloader or Downloader(offline=offline, log=log)
        self.base_url = base_url.rstrip("/")
        self._tiles: dict[tuple[int, int], _Tile | None] = {}
        self._tile_list: set[str] | None = None

    def _list(self) -> set[str]:
        if self._tile_list is None:
            path = self.downloader.fetch(f"{self.base_url}/tileList.txt", self.dir / "tileList.txt",
                                         "liste des tuiles Copernicus")
            self._tile_list = {line.strip() for line in path.read_text().splitlines() if line.strip()}
        return self._tile_list

    def tile_path(self, lat_sw: int, lon_sw: int) -> Path:
        return self.dir / f"{copernicus_tile_name(lat_sw, lon_sw)}.tif"

    def _load(self, lat_sw: int, lon_sw: int) -> _Tile | None:
        key = (lat_sw, lon_sw)
        if key in self._tiles:
            return self._tiles[key]
        name = copernicus_tile_name(lat_sw, lon_sw)
        path = self.tile_path(lat_sw, lon_sw)
        tile = None
        if not path.is_file() and name not in self._list():
            tile = None                                   # mer : pas de tuile
        else:
            try:
                self.downloader.fetch(f"{self.base_url}/{name}/{name}.tif", path, name)
            except NotFoundError as exc:
                raise CompileError(f"tuile {name} annoncée par tileList.txt mais absente : {exc}") from exc
            tile = self._read(path)
        self._tiles[key] = tile
        return tile

    @staticmethod
    def _read(path: Path) -> _Tile:
        import rasterio   # importé ici : seul ce fournisseur en a besoin

        try:
            with rasterio.open(path) as ds:
                data = ds.read(1).astype(np.float32)
                nodata = ds.nodata
                t = ds.transform
        except Exception as exc:  # noqa: BLE001 - fichier de cache corrompu
            raise CompileError(f"tuile illisible {path} ({exc}) : la supprimer du cache") from exc
        if nodata is not None:
            data[data == nodata] = np.nan
        return _Tile(data, left=t.c, top=t.f, xres=t.a, yres=-t.e)

    def elevations(self, lats, lons) -> np.ndarray:
        lats = np.asarray(lats, dtype=float)
        lons = np.asarray(lons, dtype=float)
        out = np.full(lats.shape, np.nan)
        lat_sw = np.floor(lats).astype(int)
        lon_sw = np.floor(lons).astype(int)
        keys = np.unique(np.stack((lat_sw.ravel(), lon_sw.ravel()), axis=1), axis=0)
        for la, lo in keys:
            mask = (lat_sw == la) & (lon_sw == lo)
            tile = self._load(int(la), int(lo))
            out[mask] = 0.0 if tile is None else tile.bilinear(lats[mask], lons[mask])
        return out


class IgnRgeAltiProvider:
    """Emplacement réservé : RGE ALTI de l'IGN (France, résolution plus fine). Non implémenté en v1."""

    name = "ign_rge_alti"
    native_resolution_m = 1.0

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("source IGN RGE ALTI non disponible en v1 (hors périmètre du lot B2)")


def provider_for(name: str, offline: bool = False, log: Log = stderr_log) -> ElevationProvider:
    if name == CopernicusGlo30Provider.name:
        return CopernicusGlo30Provider(offline=offline, log=log)
    raise CompileError(f"source d'altitude inconnue : {name}")


