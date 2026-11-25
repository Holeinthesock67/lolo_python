"""Sources d'altitude (interface ElevationProvider, SRS §7 ; lot B2 §3.1).

- `CopernicusGlo30Provider` : MNT Copernicus GLO-30, tuiles COG de 1° × 1° du compartiment
  public AWS `copernicus-dem-30m`, mises en cache puis lues avec rasterio, interpolation bilinéaire.
- `FabdemProvider` (lot RL1, 25 novembre) : FABDEM V1-2, le même GLO-30 sans bâtiments ni arbres (sol nu),
  tuiles de 1° lues une à une dans les archives de 10° de l'université de Bristol (`remote_zip`), Copernicus en
  repli pour une tuile que FABDEM n'a pas ou ne peut pas livrer. Relief du monde ouvert.
- `SyntheticProvider` : altitude analytique dans le repère d'un parcours, pour les tests.
- `IgnRgeAltiProvider` (lot RL2) : RGE ALTI de l'IGN en France (carrés de 1 km au pas de 5 m, WMS de la
  Géoplateforme), FABDEM puis Copernicus ailleurs et en repli. Relief du monde ouvert.
"""

from __future__ import annotations

import math
import os
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


# --- IGN RGE ALTI (France) -----------------------------------------------------------------------

# RGE ALTI de l'IGN (relief au sol mesuré, lidar et photogrammétrie ; licence ouverte Etalab 2.0), servi par la
# Géoplateforme en WMS raster : grille de flottants 32 bits (BIL) en Lambert 93, altitudes NGF-IGN69.
IGN_WMS_URL = "https://data.geopf.fr/wms-r/wms"
IGN_LAYER = "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES"
IGN_TILE_M = 1000.0          # carré de 1 km en Lambert 93
IGN_CELL_M = 5.0             # pas de la grille demandée (RGE ALTI 5 m ; 1 m inutile pour une maille de 10 m)
IGN_PIX = int(IGN_TILE_M / IGN_CELL_M) + 1    # 201 : bords communs aux carrés voisins
# Emprise grossière de la France métropolitaine et de la Corse (degrés) : hors de ce cadre, aucune demande. Dans le
# cadre mais hors de France (Genève, Barcelone…), le service ne renvoie que des valeurs vides : repli et marque.
IGN_BBOX = (41.2, -5.6, 51.2, 9.8)             # lat_min, lon_min, lat_max, lon_max
IGN_NODATA_BELOW = -1000.0


def ign_tile_key(e: float, n: float) -> tuple[int, int]:
    return int(math.floor(e / IGN_TILE_M)), int(math.floor(n / IGN_TILE_M))


def ign_tile_name(ke: int, kn: int) -> str:
    """Carré de 1 km de coin sud-ouest (ke km, kn km) en Lambert 93 : `L93_0337_6262`."""
    return f"L93_{ke:04d}_{kn:04d}"


def ign_bil_to_grid(raw: bytes) -> np.ndarray:
    """Grille IGN_PIX × IGN_PIX (ligne 0 au nord) d'une réponse BIL 32 bits ; ordre des octets deviné.

    Les deux ordres sont lus ; on garde celui dont les valeurs sont des altitudes plausibles (−500 à 5 000 m, pas de
    flottant minuscule, ou la valeur vide du service). Lève ValueError si la taille est fausse ou si aucun ordre n'est plausible.
    """
    want = IGN_PIX * IGN_PIX * 4
    if len(raw) != want:
        raise ValueError(f"réponse de {len(raw)} octets, {want} attendus (page d'erreur ?)")
    best = None
    for dtype in ("<f4", ">f4"):
        z = np.frombuffer(raw, dtype=dtype).astype(np.float64).reshape(IGN_PIX, IGN_PIX)
        # mauvais ordre : flottants minuscules (1e-38) ou énormes ; 0 exact (mer) et valeur vide restent permis
        ok = np.isfinite(z) & ((((z > -500.0) & (z < 5000.0)) & ((np.abs(z) >= 1e-3) | (z == 0.0)))
                               | (z <= -9999.0))
        score = float(ok.mean())
        if best is None or score > best[0]:
            best = (score, z)
    assert best is not None
    if best[0] < 0.999:
        raise ValueError("valeurs d'altitude invraisemblables dans la réponse")
    z = best[1].copy()
    z[z < IGN_NODATA_BELOW] = np.nan
    return z


class IgnRgeAltiProvider:
    """Relief au sol IGN RGE ALTI en France (carrés de 1 km au pas de 5 m), un autre fournisseur ailleurs.

    - Point hors du cadre de la France (IGN_BBOX) : repli direct, sans demande.
    - Carré en cache (`<cache>/ign_rge_alti/<nom>.f32`) : lu tel quel ; carré entièrement vide (hors de France) :
      marque `<nom>.absent`, repli sans nouvelle demande. Pixels vides (mer, frontière) : repli.
    - Échec réseau : repli pour cette séance, sans marque ; hors ligne : repli, sans marque.
    - Altitudes NGF-IGN69 ; FABDEM et Copernicus sont en EGM2008 : écart de quelques décimètres à la frontière,
      que le garde-fou d'altitude du monde ouvert absorbe (changement de pente borné).
    """

    name = "ign_rge_alti"
    native_resolution_m = IGN_CELL_M

    def __init__(self, cache_dir: Path | None = None, offline: bool = False, log: Log = stderr_log,
                 base_url: str = IGN_WMS_URL, fallback: ElevationProvider | None = None,
                 timeout_s: float = 30.0) -> None:
        from pyproj import Transformer

        self.dir = Path(cache_dir or dem_cache_dir()) / self.name
        self.offline = offline
        self.log = log
        self.base_url = base_url
        self.timeout_s = timeout_s
        self.fallback = fallback if fallback is not None else FabdemProvider(cache_dir=cache_dir, offline=offline,
                                                                            log=log)
        self._to_l93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)
        self._grids: dict[tuple[int, int], np.ndarray | None] = {}
        self.downloads = 0

    def tile_path(self, ke: int, kn: int) -> Path:
        return self.dir / f"{ign_tile_name(ke, kn)}.f32"

    def absent_path(self, ke: int, kn: int) -> Path:
        return self.dir / f"{ign_tile_name(ke, kn)}.absent"

    @staticmethod
    def in_frame(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        a0, o0, a1, o1 = IGN_BBOX
        return (lats >= a0) & (lats <= a1) & (lons >= o0) & (lons <= o1)

    def tile_url(self, ke: int, kn: int) -> str:
        e0, n0 = ke * IGN_TILE_M, kn * IGN_TILE_M
        h = IGN_CELL_M / 2.0     # centres des pixels sur la grille de 5 m, bords compris
        bbox = f"{e0 - h:.1f},{n0 - h:.1f},{e0 + IGN_TILE_M + h:.1f},{n0 + IGN_TILE_M + h:.1f}"
        return (f"{self.base_url}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS={IGN_LAYER}&STYLES="
                f"&CRS=EPSG:2154&BBOX={bbox}&WIDTH={IGN_PIX}&HEIGHT={IGN_PIX}&FORMAT=image/x-bil;bits=32")

    def download_tile(self, ke: int, kn: int) -> bool:
        """Carré en cache après l'appel ? (faux : hors de France, hors ligne ou échec réseau)."""
        if self.tile_path(ke, kn).is_file():
            return True
        if self.absent_path(ke, kn).is_file() or self.offline:
            return False
        import urllib.request

        name = ign_tile_name(ke, kn)
        try:
            with urllib.request.urlopen(self.tile_url(ke, kn), timeout=self.timeout_s) as resp:
                raw = resp.read()
            grid = ign_bil_to_grid(raw)
        except ValueError as exc:
            self.log(f"IGN : carré {name} illisible ({exc}) : relief de repli pour cette séance")
            return False
        except Exception as exc:  # noqa: BLE001 - réseau : repli pour cette séance, réessayé ensuite
            self.log(f"IGN : carré {name} non téléchargé ({exc}) : relief de repli pour cette séance")
            return False
        self.dir.mkdir(parents=True, exist_ok=True)
        if np.isnan(grid).all():
            self.absent_path(ke, kn).write_text("hors de la couverture du RGE ALTI\n", encoding="utf-8")
            return False
        tmp = self.tile_path(ke, kn).with_suffix(f".tmp-{os.getpid()}")
        grid.astype("<f4").tofile(tmp)
        os.replace(tmp, self.tile_path(ke, kn))
        self.downloads += 1
        return True

    def _grid(self, ke: int, kn: int) -> np.ndarray | None:
        key = (ke, kn)
        if key not in self._grids:
            g = None
            if self.download_tile(ke, kn):
                raw = np.fromfile(self.tile_path(ke, kn), dtype="<f4")
                if raw.size == IGN_PIX * IGN_PIX:
                    g = raw.astype(np.float64).reshape(IGN_PIX, IGN_PIX)
                else:
                    self.tile_path(ke, kn).unlink(missing_ok=True)
            self._grids[key] = g
        return self._grids[key]

    def elevations(self, lats, lons) -> np.ndarray:
        lats = np.asarray(lats, dtype=float)
        lons = np.asarray(lons, dtype=float)
        out = np.full(lats.shape, np.nan)
        inside = self.in_frame(lats, lons)
        if inside.any():
            e, n = self._to_l93.transform(lons[inside], lats[inside])
            e, n = np.asarray(e, dtype=float), np.asarray(n, dtype=float)
            ke = np.floor(e / IGN_TILE_M).astype(int)
            kn = np.floor(n / IGN_TILE_M).astype(int)
            vals = np.full(e.shape, np.nan)
            for a, b in np.unique(np.stack((ke, kn), axis=1), axis=0):
                g = self._grid(int(a), int(b))
                if g is None:
                    continue
                m = (ke == a) & (kn == b)
                col = (e[m] - a * IGN_TILE_M) / IGN_CELL_M
                row = ((b + 1) * IGN_TILE_M - n[m]) / IGN_CELL_M
                c0 = np.clip(np.floor(col).astype(int), 0, IGN_PIX - 2)
                r0 = np.clip(np.floor(row).astype(int), 0, IGN_PIX - 2)
                fc, fr = np.clip(col - c0, 0, 1), np.clip(row - r0, 0, 1)
                top = g[r0, c0] * (1 - fc) + g[r0, c0 + 1] * fc
                bot = g[r0 + 1, c0] * (1 - fc) + g[r0 + 1, c0 + 1] * fc
                vals[m] = top * (1 - fr) + bot * fr          # un pixel vide voisin donne NaN : repli
            out[inside] = vals
        miss = np.isnan(out)
        if miss.any():
            out[miss] = np.asarray(self.fallback.elevations(lats[miss], lons[miss]), dtype=float)
        return out

    def has_data(self, lat: float, lon: float) -> bool:
        """Relief de ce point sur le PC (sans réseau) : carré IGN en cache, sinon celui du repli."""
        if self.in_frame(np.array([lat]), np.array([lon]))[0]:
            e, n = self._to_l93.transform(lon, lat)
            if self.tile_path(*ign_tile_key(float(e), float(n))).is_file():
                return True
        fb = getattr(self.fallback, "has_data", None)
        return bool(fb(lat, lon)) if fb is not None else True


def provider_for(name: str, offline: bool = False, log: Log = stderr_log) -> ElevationProvider:
    if name == CopernicusGlo30Provider.name:
        return CopernicusGlo30Provider(offline=offline, log=log)
    if name == FabdemProvider.name:
        return FabdemProvider(offline=offline, log=log)
    if name == IgnRgeAltiProvider.name:
        return IgnRgeAltiProvider(offline=offline, log=log)
    raise CompileError(f"source d'altitude inconnue : {name}")


