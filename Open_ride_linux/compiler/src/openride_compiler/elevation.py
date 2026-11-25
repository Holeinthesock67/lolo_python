"""Sources d'altitude (interface ElevationProvider, SRS §7 ; lot B2 §3.1).

- `CopernicusGlo30Provider` : MNT Copernicus GLO-30, tuiles COG de 1° × 1° du compartiment
  public AWS `copernicus-dem-30m`, mises en cache puis lues avec rasterio, interpolation bilinéaire.
- `FabdemProvider` (lot RL1, 25 novembre) : FABDEM V1-2, le même GLO-30 sans bâtiments ni arbres (sol nu),
  tuiles de 1° lues une à une dans les archives de 10° de l'université de Bristol (`remote_zip`), Copernicus en
  repli pour une tuile que FABDEM n'a pas ou ne peut pas livrer. Relief du monde ouvert.
- `SyntheticProvider` : altitude analytique dans le repère d'un parcours, pour les tests.
- IGN RGE ALTI : emplacement réservé (`IgnRgeAltiProvider`), non implémenté en v1.
"""

from __future__ import annotations

import math
import re
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


# Contrôles du contenu téléchargé (revue de code K1-01, 24 novembre) : une page d'erreur servie en 200
# ou une liste coupée ne doivent pas entrer dans le cache, où elles resteraient pour toujours.
TIFF_MAGIC = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
TILE_NAME_RE = re.compile(r"^Copernicus_DSM_COG_10_[NS]\d{2}_00_[EW]\d{3}_00_DEM$")


def check_tiff(path: Path) -> None:
    """Lève ValueError si le fichier ne commence pas comme un GeoTIFF (TIFF ou BigTIFF)."""
    with open(path, "rb") as f:
        head = f.read(4)
    if head not in TIFF_MAGIC:
        raise ValueError(f"pas un fichier TIFF (début {head!r})")


def check_tile_list(path: Path) -> None:
    """Lève ValueError si `tileList.txt` est vide ou contient une ligne qui n'est pas un nom de tuile."""
    try:
        lines = [line.strip() for line in Path(path).read_text().splitlines() if line.strip()]
    except UnicodeDecodeError as exc:
        raise ValueError(f"liste illisible ({exc})") from exc
    if not lines:
        raise ValueError("liste vide")
    bad = next((line for line in lines if not TILE_NAME_RE.match(line)), None)
    if bad is not None:
        raise ValueError(f"ligne inattendue {bad[:60]!r} (liste coupée ou page d'erreur)")


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
                                         "liste des tuiles Copernicus", validate=check_tile_list)
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
            url = f"{self.base_url}/{name}/{name}.tif"
            try:
                self.downloader.fetch(url, path, name, validate=check_tiff)
                try:
                    tile = self._read(path)
                except CompileError:
                    if self.downloader.offline:
                        raise
                    # tuile qui commence bien mais illisible (coupée sans taille annoncée) : une reprise
                    self.downloader.log(f"tuile {name} illisible dans le cache : supprimée, nouveau téléchargement")
                    path.unlink(missing_ok=True)
                    self.downloader.fetch(url, path, name, validate=check_tiff)
                    tile = self._read(path)
            except NotFoundError as exc:
                raise CompileError(f"tuile {name} annoncée par tileList.txt mais absente : {exc}") from exc
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


# --- FABDEM (sol nu) ----------------------------------------------------------------------------

# Hawker et al. (2022), FABDEM V1-2, université de Bristol, CC BY-NC-SA 4.0 (usage non commercial : OpenRide est
# un logiciel personnel). Archives `<bloc 10°>_FABDEM_V1-2.zip` contenant les tuiles `<coin SO>_FABDEM_V1-2.tif`.
FABDEM_BASE_URL = "https://data.bris.ac.uk/datasets/s5hqmjcdj8yo2ibzi9b4ew3sn"
FABDEM_VERSION = "V1-2"


def _corner(lat: int, lon: int, lat_digits: int = 2) -> str:
    return f"{'N' if lat >= 0 else 'S'}{abs(lat):0{lat_digits}d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}"


def fabdem_tile_name(lat_sw: int, lon_sw: int) -> str:
    """Tuile d'un degré de coin sud-ouest (lat_sw, lon_sw) : `N43W002_FABDEM_V1-2`."""
    return f"{_corner(lat_sw, lon_sw)}_FABDEM_{FABDEM_VERSION}"


def fabdem_zip_names(lat_sw: int, lon_sw: int) -> list[str]:
    """Archives de 10° candidates pour la tuile, la plus probable d'abord : `N40W010-N50W000_FABDEM_V1-2.zip`.

    Le coin nord-est d'un bloc qui touche l'équateur ou le méridien d'origine peut s'écrire N00 ou S00, E000 ou
    W000 : non vérifiable depuis le cloud (serveur hors de la liste du réseau), les deux graphies sont essayées.
    """
    la, lo = (lat_sw // 10) * 10, (lon_sw // 10) * 10
    sw = _corner(la, lo)
    ns = ["N"] if la + 10 > 0 else (["S"] if la + 10 < 0 else ["N", "S"])
    ew = ["E"] if lo + 10 > 0 else (["W"] if lo + 10 < 0 else ["W", "E"])
    return [f"{sw}-{a}{abs(la + 10):02d}{b}{abs(lo + 10):03d}_FABDEM_{FABDEM_VERSION}.zip" for a in ns for b in ew]


class FabdemProvider:
    """Relief au sol nu FABDEM, Copernicus GLO-30 en repli tuile par tuile.

    GLO-30 est un modèle de SURFACE (toits, arbres) : en ville, la route y « monte » sur les maisons, d'où des
    pentes de 20 % sur quelques dizaines de mètres (Biarritz, 22 novembre). FABDEM en retire bâtiments et forêts.
    - Tuile en cache (`<cache>/fabdem_v1_2/<nom>.tif`) : lue telle quelle ; pixels sans valeur (mer) : repli.
    - Tuile absente de son archive, archive absente (404) ou serveur sans requêtes partielles : marque
      `<nom>.absent` dans le cache, et la tuile Copernicus sert à sa place (même maille de 30 m).
    - Hors ligne sans la tuile : repli Copernicus (son propre cache), sans marque (réessayé avec le réseau).
    """

    name = "fabdem_v1_2"
    native_resolution_m = 30.0

    def __init__(self, cache_dir: Path | None = None, offline: bool = False, log: Log = stderr_log,
                 base_url: str = FABDEM_BASE_URL, fallback: ElevationProvider | None = None,
                 timeout_s: float = 60.0) -> None:
        self.dir = Path(cache_dir or dem_cache_dir()) / self.name
        self.offline = offline
        self.log = log
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.fallback = fallback if fallback is not None else CopernicusGlo30Provider(cache_dir=cache_dir,
                                                                                     offline=offline, log=log)
        self._tiles: dict[tuple[int, int], _Tile | None] = {}
        self._members: dict[str, dict | None] = {}   # None : archive absente (404)
        self.downloads = 0

    def tile_path(self, lat_sw: int, lon_sw: int) -> Path:
        return self.dir / f"{fabdem_tile_name(lat_sw, lon_sw)}.tif"

    def absent_path(self, lat_sw: int, lon_sw: int) -> Path:
        return self.dir / f"{fabdem_tile_name(lat_sw, lon_sw)}.absent"

    def tile_ready(self, lat_sw: int, lon_sw: int) -> bool:
        """Tuile FABDEM sur le PC, ou connue absente (le repli décide alors)."""
        return self.tile_path(lat_sw, lon_sw).is_file() or self.absent_path(lat_sw, lon_sw).is_file()

    def has_data(self, lat: float, lon: float) -> bool:
        """Le relief de ce point est-il sur le PC (sans réseau) ?"""
        la, lo = math.floor(lat), math.floor(lon)
        if self.tile_path(la, lo).is_file():
            return True
        fb = getattr(self.fallback, "has_data", None)
        if fb is not None:
            return bool(fb(lat, lon))
        if isinstance(self.fallback, CopernicusGlo30Provider):
            if self.fallback.tile_path(la, lo).is_file():
                return True
            listing = self.fallback.dir / "tileList.txt"
            return listing.is_file() and copernicus_tile_name(la, lo) not in listing.read_text()
        return True

    def download_tile(self, lat_sw: int, lon_sw: int) -> bool:
        """Télécharge la tuile si besoin (fil de préchargement compris). Vrai si elle est en cache ensuite."""
        if self.tile_path(lat_sw, lon_sw).is_file():
            return True
        if self.absent_path(lat_sw, lon_sw).is_file() or self.offline:
            return False
        from . import remote_zip

        tname = fabdem_tile_name(lat_sw, lon_sw)
        try:
            zname, members = self._archive(fabdem_zip_names(lat_sw, lon_sw))
            url = f"{self.base_url}/{zname}"
            member = members.get(f"{tname}.tif")
            if member is None:
                self._mark_absent(lat_sw, lon_sw, f"{tname} absente de {zname}")
                return False
            self.log(f"FABDEM : téléchargement de {tname}…")
            got = remote_zip.fetch_member(url, member, self.tile_path(lat_sw, lon_sw), self.timeout_s)
            check_tiff(self.tile_path(lat_sw, lon_sw))
            self.downloads += 1
            self.log(f"  {tname} : {got / 1e6:.1f} Mo")
            return True
        except (NotFoundError, remote_zip.RangeUnsupported) as exc:
            self._mark_absent(lat_sw, lon_sw, str(exc))
        except ValueError as exc:   # check_tiff
            self.tile_path(lat_sw, lon_sw).unlink(missing_ok=True)
            self.log(f"FABDEM : {tname} illisible ({exc}) : Copernicus pour cette séance")
        except Exception as exc:  # noqa: BLE001 - réseau : Copernicus pour cette séance, réessayé ensuite
            self.log(f"FABDEM : {tname} non téléchargée ({exc}) : Copernicus pour cette séance")
        return False

    def _archive(self, names: list[str]) -> tuple[str, dict]:
        """(nom, sommaire) de la première archive candidate qui existe ; NotFoundError si aucune."""
        from . import remote_zip

        last: Exception | None = None
        for zname in names:
            if zname in self._members:
                if self._members[zname] is not None:
                    return zname, self._members[zname]
                continue
            try:
                self.log(f"FABDEM : lecture du sommaire de {zname}…")
                self._members[zname] = remote_zip.list_members(f"{self.base_url}/{zname}", self.timeout_s)
                return zname, self._members[zname]
            except NotFoundError as exc:
                self._members[zname] = None
                last = exc
        raise NotFoundError(f"aucune archive FABDEM pour cette tuile ({last})")

    def _mark_absent(self, lat_sw: int, lon_sw: int, why: str) -> None:
        self.log(f"FABDEM : {why} : relief Copernicus pour cette tuile")
        p = self.absent_path(lat_sw, lon_sw)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(why + "\n", encoding="utf-8")

    def _load(self, lat_sw: int, lon_sw: int) -> _Tile | None:
        key = (lat_sw, lon_sw)
        if key in self._tiles:
            return self._tiles[key]
        tile = None
        if self.download_tile(lat_sw, lon_sw):
            try:
                tile = CopernicusGlo30Provider._read(self.tile_path(lat_sw, lon_sw))
            except CompileError as exc:
                self.tile_path(lat_sw, lon_sw).unlink(missing_ok=True)
                self.log(f"FABDEM : {exc} : Copernicus pour cette séance")
        if tile is not None and tile.data.size:
            tile.data[tile.data < -1000.0] = np.nan      # -9999 si la tuile ne déclare pas sa valeur vide
        self._tiles[key] = tile
        return tile

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
            if tile is not None:
                out[mask] = tile.bilinear(lats[mask], lons[mask])
        miss = np.isnan(out)
        if miss.any():   # tuile sans FABDEM, ou pixels sans valeur (mer, bord) : Copernicus
            out[miss] = np.asarray(self.fallback.elevations(lats[miss], lons[miss]), dtype=float)
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
    if name == FabdemProvider.name:
        return FabdemProvider(offline=offline, log=log)
    raise CompileError(f"source d'altitude inconnue : {name}")


