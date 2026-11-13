"""Classification des biomes (couche `biome`, Format .world v1 §8 quater ; lot U2). Numpy seul, sans entrée-sortie.

Les données arrivent par des fonctions (projection, occupation du sol, altitude) et une liste de polygones
OSM déjà projetés ; le module rend les tuiles de biome (dictionnaires de `biome/<niveau>/tile_<ix>_<iz>.json`)
et la part de chaque biome le long de la route.

Méthode, point par point de la grille 17 × 17 de chaque tuile (cases de 62,5 m en proche, 312,5 m en lointain) :

1. **Échantillons :** 5 × 5 points par case autour du point de grille (pas de la case / 5). Chacun prend sa
   classe ESA WorldCover (pixel de 10 m), corrigée par les polygones OSM qui le contiennent
   (`landuse=vineyard|farmland|orchard` → cultures, `natural=sand|wetland|glacier|scrub|heath`).
   Sans WorldCover (repli), ou sur un pixel sans donnée, la classe « prairie » est prise.
2. **Zone climatique d'après la carte de Köppen-Geiger embarquée** (module `koppen`, pixels de 3 km, lot
   U24) : tropicale, aride, tempérée chaude (été chaud et sec, Csa), tempérée, boréale, polaire, en parts
   fondues sur un voisinage de 5 × 5 pixels ; en pleine mer, bandes de latitude fondues sur 2°. Chaque
   classe donne un biome par zone (`CLASS_BIOME`) : arbres → forêt tempérée ou boréale, cultures → `farmland`,
   prairie → prairie ou steppe, sol nu → désert de sable ou de roche, neige → `polar` ou `alpine`, etc. ; eau
   et bâti ne votent pas. Dans un paysage volcanique connu (`data/volcanic_areas.toml`), le sol nu et le
   sable OSM (`natural=sand` : cendres, lapilli) donnent `volcanic`. Dans un rectangle d'un biome régional
   (`data/biome_zones.toml`, lot AT2 : Atlantique et landes), sous un climat de Köppen de sa liste, les classes de
   sa liste donnent ce biome (classe propre au compilateur, 203 pour `atlantic_heath`).
3. **Bruit de bord déterministe** (hachage des indices globaux du point, donc de `ix`, `iz`) puis **flou de
   2 cases** (noyau binomial 5 × 5) : pas de frontière droite. Un point sans vote reçoit le biome de prairie
   de sa zone.
4. **Altitude :** au-dessus d'un seuil qui dépend de la latitude (1 800 m à 45°), part `alpine` croissante,
   nulle 300 m sous le seuil, complète 600 m au-dessus. **Hauts plateaux** (lot HP1) : sous 40° de latitude,
   le terrain ouvert (prairie, arbustes, sol nu, mousses, sable) vote `high_plateau` pour une part `p`
   croissante de 3 300 à 3 800 m (`plateau_part`, à l'étape 1, échantillon par échantillon) ; la part
   `alpine` de l'altitude devient `a × (1 − p)`. Neige et glaciers restent `alpine`, forêts, cultures,
   zones humides et laves gardent leur biome. Même règle pour les parcours et le monde ouvert.
5. **Quatre biomes au plus par tuile** (les plus forts de la tuile) ; un point commun à plusieurs tuiles ne
   garde que les biomes admis par toutes, puis ses poids sont renormalisés à 255 (plus forts restes).

Tout est calculé une seule fois par point global (indices `ix·16 + i`, `iz·16 + j`) : les bords communs à deux
tuiles voisines sont identiques par construction, et deux compilations donnent les mêmes tuiles au bit près.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources
from typing import Callable, Sequence

import numpy as np

from . import koppen

BIOME_VERSION = "1.0"
# Identifiants du lot U0, dans l'ordre de la liste définitive, puis `japan` (lot JP1, 6.0) et `atlantic_heath`
# (lot AT1, 6.0) et `high_plateau` (lot HP1, 6.0) (Format .world v1 §8 quater).
BIOMES = ("temperate_grassland", "temperate_forest", "farmland", "boreal_forest", "alpine", "tundra",
          "polar", "mediterranean", "steppe", "savanna", "sand_desert", "rock_desert", "jungle",
          "wetland", "coast", "volcanic", "japan", "atlantic_heath",
          "high_plateau")
INDEX = {b: k for k, b in enumerate(BIOMES)}
NB = len(BIOMES)
DEFAULT_BIOME = "temperate_grassland"
MAX_BIOMES_PER_TILE = 4
MAX_FIX_ROUNDS = 20
TOTAL = 255

GRID = 17
CELLS = GRID - 1
SUB = 5                 # échantillons par case et par axe
MARGIN = 2              # rayon du flou, en cases
KERNEL = np.array([1.0, 4.0, 6.0, 4.0, 1.0]) / 16.0
NOISE_AMPLITUDE = 0.6   # poids bruts multipliés par 1 ± 0,3

# --- zones climatiques ---------------------------------------------------------------------------------
ZONES = koppen.ZONES   # ("tropical", "arid", "warm", "temperate", "boreal", "polar")
ZONE_LIMITS_DEG = (15.0, 30.0, 44.0, 55.0, 66.5)   # |latitude| entre deux zones, en pleine mer seulement
ZONE_RAMP_DEG = 2.0

# --- classes ESA WorldCover 2021 (et classes OSM) → biome par zone --------------------------------------
TREES, SHRUB, GRASS, CROP, BUILT, BARE, SNOW, WATER, WETLAND, MANGROVE, MOSS = 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100
OSM_SAND = 200          # classe propre au compilateur : `natural=sand`
VOLCANIC_BARE = 201     # classe propre au compilateur : sol nu dans un paysage volcanique
# Classes 202 et suivantes : biomes régionaux de `data/biome_zones.toml` (ajoutées à CLASS_BIOME plus bas).
CLASS_BIOME: dict[int, tuple[str | None, ...]] = {
    TREES: ("jungle", "savanna", "mediterranean", "temperate_forest", "boreal_forest", "tundra"),
    SHRUB: ("savanna", "steppe", "mediterranean", "temperate_grassland", "tundra", "tundra"),
    GRASS: ("savanna", "steppe", "mediterranean", "temperate_grassland", "temperate_grassland", "tundra"),
    CROP: ("farmland",) * 6,
    BUILT: (None,) * 6,          # bâti : ne vote pas, pris des voisins
    BARE: ("sand_desert", "sand_desert", "rock_desert", "rock_desert", "tundra", "polar"),
    SNOW: ("alpine", "alpine", "alpine", "alpine", "polar", "polar"),
    WATER: (None,) * 6,          # eau : ignorée (côte et mer : lot U3)
    WETLAND: ("wetland",) * 6,
    MANGROVE: ("wetland",) * 6,
    MOSS: ("tundra",) * 6,
    OSM_SAND: ("sand_desert",) * 6,
    VOLCANIC_BARE: ("volcanic",) * 6,
}
NODATA_CLASS = GRASS    # pixel sans donnée, ou pas de WorldCover (repli OSM et altitude)


# --- biomes régionaux (lot AT2) -------------------------------------------------------------------------

@dataclass(frozen=True)
class RegionalBiome:
    """Biome régional de `data/biome_zones.toml` : classe propre au compilateur, codes de Köppen et classes
    WorldCover qui le donnent dans ses rectangles."""
    biome: str
    cls: int
    koppen: frozenset[str]
    worldcover: tuple[int, ...]


@dataclass(frozen=True)
class RegionalZone:
    biome: str
    name: str
    lat: tuple[int, int]
    lon: tuple[int, int]


@lru_cache(maxsize=1)
def biome_zones() -> tuple[tuple[RegionalBiome, ...], tuple[RegionalZone, ...]]:
    """Biomes régionaux et rectangles de la table embarquée `data/biome_zones.toml`."""
    text = resources.files("openride_compiler").joinpath("data", "biome_zones.toml").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    rules = tuple(RegionalBiome(b, int(r["class"]), frozenset(r["koppen"]), tuple(int(c) for c in r["worldcover"]))
                  for b, r in data.get("biome", {}).items())
    zones = tuple(RegionalZone(str(z["biome"]), str(z["name"]), (int(z["lat"][0]), int(z["lat"][1])),
                               (int(z["lon"][0]), int(z["lon"][1]))) for z in data.get("zone", []))
    return rules, zones


def regional_rule(lat: np.ndarray, lon: np.ndarray, codes: Sequence[str | None] | None = None) -> np.ndarray:
    """Indice (n,) dans `biome_zones()[0]` du biome régional de chaque point, −1 sinon : premier rectangle qui
    contient le point, et code de Köppen du point (`codes`, carte embarquée par défaut) dans la liste du biome."""
    rules, zones = biome_zones()
    la = np.asarray(lat, dtype=float).ravel()
    lo = np.asarray(lon, dtype=float).ravel()
    out = np.full(len(la), -1, dtype=np.int64)
    if not len(la):
        return out
    index = {r.biome: k for k, r in enumerate(rules)}
    for z in zones:
        inside = (out < 0) & (la >= z.lat[0]) & (la < z.lat[1]) & (lo >= z.lon[0]) & (lo < z.lon[1])
        out[inside] = index[z.biome]
    if (out >= 0).any():
        code = codes if codes is not None else koppen.codes(la, lo)
        ok = np.array([k >= 0 and code[i] in rules[k].koppen for i, k in enumerate(out.tolist())], dtype=bool)
        out[~ok] = -1
    return out


def regional_class(rule: int, classes: np.ndarray) -> np.ndarray:
    """Classes d'échantillons d'un point du biome régional `rule` : celles de sa liste prennent sa classe."""
    if rule < 0:
        return classes
    r = biome_zones()[0][rule]
    return np.where(np.isin(classes, r.worldcover), r.cls, classes)


for _rule in biome_zones()[0]:
    CLASS_BIOME[_rule.cls] = (_rule.biome,) * len(ZONES)

# Corrections OSM : (clé, valeur) → classe, par priorité croissante (le dernier polygone posé l'emporte).
OSM_RULES: tuple[tuple[str, str, int], ...] = (
    ("natural", "scrub", SHRUB),
    ("natural", "heath", SHRUB),
    ("landuse", "farmland", CROP),
    ("landuse", "orchard", CROP),
    ("landuse", "vineyard", CROP),
    ("natural", "sand", OSM_SAND),
    ("natural", "wetland", WETLAND),
    ("natural", "glacier", SNOW),
)
OSM_PRIORITY = {cls: k for k, (_, _, cls) in enumerate(OSM_RULES)}

# --- altitude ------------------------------------------------------------------------------------------
ALPINE_LINE_45_M = 1800.0
ALPINE_LINE_PER_DEG_M = 75.0     # le seuil monte de 75 m par degré vers l'équateur
ALPINE_LINE_MIN_M, ALPINE_LINE_MAX_M = 600.0, 4200.0
ALPINE_BELOW_M, ALPINE_ABOVE_M = 300.0, 600.0
# Hauts plateaux (lot HP1) : terrain ouvert au-dessus de 3 300 à 3 800 m, sous 38 à 42° de latitude.
PLATEAU_LOW_M, PLATEAU_FULL_M = 3300.0, 3800.0
PLATEAU_LAT_FULL_DEG, PLATEAU_LAT_ZERO_DEG = 38.0, 42.0
PLATEAU_CLASSES = (GRASS, SHRUB, BARE, MOSS, OSM_SAND)


@dataclass(frozen=True)
class BiomeLevel:
    name: str
    tile_m: float

    @property
    def cell_m(self) -> float:
        return self.tile_m / CELLS


NEAR = BiomeLevel("near", 1000.0)
FAR = BiomeLevel("far", 5000.0)
LEVELS = (NEAR, FAR)


@dataclass(frozen=True)
class OsmArea:
    """Polygone OSM projeté dans le repère du parcours : classe, anneau extérieur et trous ([[x, z], …])."""
    cls: int
    outer: Sequence[Sequence[float]]
    holes: Sequence[Sequence[Sequence[float]]] = ()


@dataclass
class Inputs:
    """Sources de la classification. `landcover(lats, lons)` → classes uint8 ; `elevation` → altitudes (m) ;
    `zones(lats, lons)` → parts (n, 6) des zones climatiques (carte de Köppen par défaut) ; `volcanic(lats,
    lons)` → booléens « paysage volcanique » (table embarquée par défaut) ; `regional(lats, lons)` → indice du
    biome régional de chaque point, −1 sinon (`regional_rule`, table `data/biome_zones.toml` par défaut)."""
    to_latlon: Callable[[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]
    landcover: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None
    elevation: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None
    osm: Sequence[OsmArea] = ()
    zones: Callable[[np.ndarray, np.ndarray], np.ndarray] = field(default=lambda lat, lon: zone_weights(lat, lon))
    volcanic: Callable[[np.ndarray, np.ndarray], np.ndarray] = field(default=lambda lat, lon: in_volcanic_area(lat, lon))
    regional: Callable[[np.ndarray, np.ndarray], np.ndarray] = field(default=lambda lat, lon: regional_rule(lat, lon))


@dataclass
class BiomeLayer:
    tiles: dict[str, dict[tuple[int, int], dict]]
    shares: dict[str, float]
    forced: str | None = None
    sources: list[str] = field(default_factory=list)
    forced_variant: dict | None = None     # option --variant (lot U4)


def osm_class(tags: dict) -> int | None:
    """Classe de correction d'un élément OSM d'après ses étiquettes, ou None."""
    found = None
    for key, value, cls in OSM_RULES:
        if tags.get(key) == value:
            found = cls
    return found


# --- fonctions ponctuelles -----------------------------------------------------------------------------

def latitude_zone_weights(lat: np.ndarray) -> np.ndarray:
    """Part (n, 6) de chaque zone climatique d'après |latitude|, fondue sur ZONE_RAMP_DEG à chaque limite
    (repli en pleine mer, où la carte de Köppen n'a pas de climat)."""
    a = np.abs(np.asarray(lat, dtype=float)).ravel()
    s = [np.clip((a - b) / ZONE_RAMP_DEG + 0.5, 0.0, 1.0) for b in ZONE_LIMITS_DEG]
    w = np.empty((len(a), len(ZONES)))
    w[:, 0] = 1.0 - s[0]
    for k in range(1, len(ZONES) - 1):
        w[:, k] = s[k - 1] - s[k]
    w[:, -1] = s[-1]
    return w


def zone_weights(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Part (n, 6) de chaque zone climatique : carte de Köppen, bandes de latitude en pleine mer."""
    w, sea = koppen.zone_weights(lat, lon)
    if sea.any():
        w[sea] = latitude_zone_weights(np.asarray(lat, dtype=float).ravel()[sea])
    return w


@dataclass(frozen=True)
class VolcanicArea:
    name: str
    lat: float
    lon: float
    radius_km: float


@lru_cache(maxsize=1)
def volcanic_areas() -> tuple[VolcanicArea, ...]:
    """Paysages volcaniques de la table embarquée `data/volcanic_areas.toml`."""
    text = resources.files("openride_compiler").joinpath("data", "volcanic_areas.toml").read_text(encoding="utf-8")
    return tuple(VolcanicArea(str(a["name"]), float(a["lat"]), float(a["lon"]), float(a["radius_km"]))
                 for a in tomllib.loads(text)["area"])


EARTH_RADIUS_KM = 6371.0


def in_volcanic_area(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Booléens (n,) : point à l'intérieur d'un paysage volcanique de la table (distance du grand cercle)."""
    la = np.radians(np.asarray(lat, dtype=float).ravel())
    lo = np.radians(np.asarray(lon, dtype=float).ravel())
    out = np.zeros(len(la), dtype=bool)
    for a in volcanic_areas():
        la0, lo0 = math.radians(a.lat), math.radians(a.lon)
        h = np.sin((la - la0) / 2) ** 2 + np.cos(la) * math.cos(la0) * np.sin((lo - lo0) / 2) ** 2
        out |= 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0))) <= a.radius_km
    return out


def alpine_line_m(lat: np.ndarray) -> np.ndarray:
    a = np.abs(np.asarray(lat, dtype=float))
    return np.clip(ALPINE_LINE_45_M + ALPINE_LINE_PER_DEG_M * (45.0 - a), ALPINE_LINE_MIN_M, ALPINE_LINE_MAX_M)


def alpine_part(alt_m: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Part `alpine` (0 à 1) : nulle sous seuil − 300 m, complète au-dessus de seuil + 600 m ; 0 si altitude inconnue."""
    alt = np.asarray(alt_m, dtype=float)
    line = alpine_line_m(lat)
    t = (alt - (line - ALPINE_BELOW_M)) / (ALPINE_BELOW_M + ALPINE_ABOVE_M)
    return np.where(np.isfinite(t), np.clip(t, 0.0, 1.0), 0.0)


def plateau_part(alt_m: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Part `high_plateau` (0 à 1) du terrain ouvert : altitude de PLATEAU_LOW_M à PLATEAU_FULL_M, fois latitude
    de PLATEAU_LAT_ZERO_DEG à PLATEAU_LAT_FULL_DEG ; 0 si altitude inconnue."""
    alt = np.asarray(alt_m, dtype=float)
    a = np.abs(np.asarray(lat, dtype=float))
    t_alt = (alt - PLATEAU_LOW_M) / (PLATEAU_FULL_M - PLATEAU_LOW_M)
    t_lat = np.clip((PLATEAU_LAT_ZERO_DEG - a) / (PLATEAU_LAT_ZERO_DEG - PLATEAU_LAT_FULL_DEG), 0.0, 1.0)
    return np.where(np.isfinite(t_alt), np.clip(t_alt, 0.0, 1.0), 0.0) * t_lat


def _class_table() -> np.ndarray:
    """Table (256, 6) classe → indice de biome par zone (−1 : ne vote pas)."""
    table = np.full((256, len(ZONES)), -1, dtype=np.int64)
    for cls, row in CLASS_BIOME.items():
        table[cls] = [INDEX[b] if b else -1 for b in row]
    table[0] = table[NODATA_CLASS]
    return table


CLASS_TABLE = _class_table()


def _hash01(gx: np.ndarray, gz: np.ndarray, salt: int) -> np.ndarray:
    """Valeur pseudo-aléatoire déterministe dans [0, 1) par point global (mélange de type splitmix64)."""
    with np.errstate(over="ignore"):
        h = (gx.astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15)
             ^ gz.astype(np.uint64) * np.uint64(0xC2B2AE3D27D4EB4F)
             ^ np.uint64(salt) * np.uint64(0x165667B19E3779F9))
        h ^= h >> np.uint64(30)
        h *= np.uint64(0xBF58476D1CE4E5B9)
        h ^= h >> np.uint64(27)
        h *= np.uint64(0x94D049BB133111EB)
        h ^= h >> np.uint64(31)
    return (h >> np.uint64(11)).astype(np.float64) / float(1 << 53)


# --- points globaux ------------------------------------------------------------------------------------

def _keys(gx: np.ndarray, gz: np.ndarray) -> np.ndarray:
    """Clé entière unique d'un point global (tri lexicographique (gz, gx))."""
    return (gz.astype(np.int64) << 32) + (gx.astype(np.int64) + (1 << 31))


class _Points:
    """Ensemble trié de points globaux et recherche de leur rang."""

    def __init__(self, gx: np.ndarray, gz: np.ndarray) -> None:
        keys = np.unique(_keys(gx, gz))
        self.keys = keys
        self.gz = (keys >> 32).astype(np.int64)
        self.gx = (keys - (self.gz << 32) - (1 << 31)).astype(np.int64)

    def __len__(self) -> int:
        return len(self.keys)

    def find(self, gx: np.ndarray, gz: np.ndarray) -> np.ndarray:
        k = _keys(gx, gz)
        idx = np.searchsorted(self.keys, k)
        idx = np.minimum(idx, len(self.keys) - 1)
        if not np.array_equal(self.keys[idx], k):
            raise ValueError("point global hors de l'ensemble")
        return idx


def _tile_grid(keys: Sequence[tuple[int, int]], margin: int) -> tuple[np.ndarray, np.ndarray]:
    r = np.arange(-margin, GRID + margin, dtype=np.int64)
    gx, gz = [], []
    for ix, iz in keys:
        mx, mz = np.meshgrid(ix * CELLS + r, iz * CELLS + r)
        gx.append(mx.ravel())
        gz.append(mz.ravel())
    return np.concatenate(gx), np.concatenate(gz)


# --- polygones OSM (balayage par lignes du réseau d'échantillons) ---------------------------------------

def _rings_crossings(rings: list[np.ndarray], z: float) -> np.ndarray:
    xs = []
    for ring in rings:
        x1, z1 = ring[:, 0], ring[:, 1]
        x2, z2 = np.roll(x1, -1), np.roll(z1, -1)
        cross = (z1 > z) != (z2 > z)
        if cross.any():
            t = (z - z1[cross]) / (z2[cross] - z1[cross])
            xs.append(x1[cross] + t * (x2[cross] - x1[cross]))
    return np.sort(np.concatenate(xs)) if xs else np.empty(0)


def _apply_osm(classes: np.ndarray, skeys: np.ndarray, step: float, areas: Sequence[OsmArea]) -> None:
    """Pose sur place la classe des polygones (règle pair-impair, trous compris) sur les échantillons du
    réseau de pas `step` ; `skeys` : clés triées des échantillons (même codage que `_keys`)."""
    if len(skeys) == 0:
        return
    zmin_s = int(skeys[0] >> 32)
    zmax_s = int(skeys[-1] >> 32)
    order = sorted(range(len(areas)), key=lambda k: OSM_PRIORITY.get(areas[k].cls, -1))
    for k in order:
        area = areas[k]
        rings = [np.asarray(area.outer, dtype=float)] + [np.asarray(h, dtype=float) for h in area.holes]
        rings = [r for r in rings if r.ndim == 2 and len(r) >= 3]
        if not rings:
            continue
        outer = rings[0]
        mz0 = max(int(np.ceil(outer[:, 1].min() / step)), zmin_s)
        mz1 = min(int(np.floor(outer[:, 1].max() / step)), zmax_s)
        for mz in range(mz0, mz1 + 1):
            xs = _rings_crossings(rings, mz * step)
            for a, b in zip(xs[0::2], xs[1::2]):
                m0, m1 = int(np.ceil(a / step)), int(np.floor(b / step))
                if m1 < m0:
                    continue
                lo = np.searchsorted(skeys, (np.int64(mz) << 32) + (m0 + (1 << 31)), side="left")
                hi = np.searchsorted(skeys, (np.int64(mz) << 32) + (m1 + (1 << 31)), side="right")
                classes[lo:hi] = area.cls


# --- classification d'un niveau ------------------------------------------------------------------------

def _raw_weights(pts: _Points, level: BiomeLevel, inputs: Inputs) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Poids bruts (n, 16) : part de chaque biome parmi les 25 échantillons de chaque point (0 : pas de vote),
    parts des zones climatiques (n, 6) et latitude de chaque point."""
    n = len(pts)
    step = level.cell_m / SUB
    off = np.arange(SUB, dtype=np.int64) - SUB // 2
    # Échantillons : réseau de pas `step`, chaque position appartient à un seul point (5 par case).
    sx = (pts.gx[:, None, None] * SUB + off[None, None, :]) + 0 * off[None, :, None]
    sz = (pts.gz[:, None, None] * SUB + off[None, :, None]) + 0 * off[None, None, :]
    sx, sz = sx.reshape(n, SUB * SUB), sz.reshape(n, SUB * SUB)
    classes = np.full(sx.shape, NODATA_CLASS if inputs.landcover is None else 0, dtype=np.int64)
    if inputs.landcover is not None:
        lat, lon = inputs.to_latlon((sx * step).ravel().astype(float), (sz * step).ravel().astype(float))
        classes = np.asarray(inputs.landcover(np.asarray(lat), np.asarray(lon)), dtype=np.int64).reshape(sx.shape)
    if inputs.osm:
        skeys = _keys(sx.ravel(), sz.ravel())
        order = np.argsort(skeys, kind="stable")
        sorted_classes = classes.ravel()[order]
        _apply_osm(sorted_classes, skeys[order], step, inputs.osm)
        flat = classes.ravel().copy()
        flat[order] = sorted_classes
        classes = flat.reshape(sx.shape)
    lat_p, lon_p = inputs.to_latlon((pts.gx * level.cell_m).astype(float), (pts.gz * level.cell_m).astype(float))
    lat_p, lon_p = np.asarray(lat_p, dtype=float), np.asarray(lon_p, dtype=float)
    volcanic = np.asarray(inputs.volcanic(lat_p, lon_p), dtype=bool).ravel()
    if volcanic.any():   # sol nu ou sable OSM d'un paysage volcanique : laves, scories, cendres
        sub = classes[volcanic]
        sub[(sub == BARE) | (sub == OSM_SAND)] = VOLCANIC_BARE
        classes[volcanic] = sub
    regional = np.asarray(inputs.regional(lat_p, lon_p), dtype=np.int64).ravel()
    for rule in np.unique(regional[regional >= 0]).tolist():   # biomes régionaux (lot AT2)
        rows_r = regional == rule
        classes[rows_r] = regional_class(int(rule), classes[rows_r])
    classes = np.clip(classes, 0, 255)
    zw = np.asarray(inputs.zones(lat_p, lon_p), dtype=float).reshape(n, len(ZONES))
    raw = np.zeros(n * NB)
    rows = np.repeat(np.arange(n, dtype=np.int64), SUB * SUB)
    # Hauts plateaux : part `p` des votes du terrain ouvert donnée à `high_plateau`, le reste à son biome.
    keep = np.ones(n * SUB * SUB)
    if inputs.elevation is not None:
        p = plateau_part(np.asarray(inputs.elevation(lat_p, lon_p), dtype=float).ravel(), lat_p)
        if p.any():
            open_ = np.isin(classes.ravel(), PLATEAU_CLASSES)
            share = np.repeat(p, SUB * SUB) * open_
            keep -= share
            raw[np.arange(n) * NB + INDEX["high_plateau"]] += share.reshape(n, SUB * SUB).sum(axis=1) / (SUB * SUB)
    for z in range(len(ZONES)):
        b = CLASS_TABLE[classes.ravel(), z]
        ok = b >= 0
        w = (np.repeat(zw[:, z], SUB * SUB) * keep)[ok] / (SUB * SUB)
        raw += np.bincount(rows[ok] * NB + b[ok], weights=w, minlength=n * NB)
    return raw.reshape(n, NB), zw, lat_p


def _blur(raw: np.ndarray, ext: _Points, core: _Points) -> np.ndarray:
    out = np.zeros((len(core), NB))
    for dj in range(-MARGIN, MARGIN + 1):
        for di in range(-MARGIN, MARGIN + 1):
            idx = ext.find(core.gx + di, core.gz + dj)
            out += (KERNEL[dj + MARGIN] * KERNEL[di + MARGIN]) * raw[idx]
    return out


def _round_255(w: np.ndarray) -> np.ndarray:
    """Poids réels positifs (n, k) → entiers de somme 255 par ligne (plus forts restes, égalités à l'indice)."""
    total = w.sum(axis=1, keepdims=True)
    scaled = np.where(total > 0, w * TOTAL / np.where(total > 0, total, 1.0), 0.0)
    base = np.floor(scaled + 1e-9).astype(np.int64)
    rest = TOTAL - base.sum(axis=1)
    frac = scaled - base
    order = np.argsort(-frac, axis=1, kind="stable")
    rank = np.empty_like(order)
    np.put_along_axis(rank, order, np.arange(w.shape[1])[None, :].repeat(len(w), axis=0), axis=1)
    base += (rank < rest[:, None]).astype(np.int64)
    return base


def _owners(gx: np.ndarray, gz: np.ndarray, tile_index: dict[tuple[int, int], int]) -> np.ndarray:
    """Rang des tuiles présentes qui contiennent chaque point global (1, 2 ou 4 sur les bords), −1 sinon."""
    keys = sorted(tile_index, key=lambda t: tile_index[t])
    tk = _keys(np.array([t[0] for t in keys]), np.array([t[1] for t in keys]))
    order = np.argsort(tk)
    tk_sorted = tk[order]
    out = np.full((len(gx), 4), -1, dtype=np.int64)
    tx, tz = np.floor_divide(gx, CELLS), np.floor_divide(gz, CELLS)
    on_x, on_z = (gx % CELLS) == 0, (gz % CELLS) == 0
    for c, (dx, dz) in enumerate(((0, 0), (-1, 0), (0, -1), (-1, -1))):
        valid = (on_x | (dx == 0)) & (on_z | (dz == 0))
        k = _keys(tx + dx, tz + dz)
        idx = np.minimum(np.searchsorted(tk_sorted, k), len(tk_sorted) - 1)
        found = valid & (tk_sorted[idx] == k)
        out[found, c] = order[idx[found]]
    return out


def classify_level(keys: Sequence[tuple[int, int]], level: BiomeLevel, inputs: Inputs,
                   salt: int = 0) -> dict[tuple[int, int], dict]:
    """Tuiles de biome d'un niveau (dictionnaires prêts pour JSON), pour les tuiles `keys`."""
    keys = sorted({(int(a), int(b)) for a, b in keys})
    if not keys:
        return {}
    ext = _Points(*_tile_grid(keys, MARGIN))
    core = _Points(*_tile_grid(keys, 0))
    raw, _, _ = _raw_weights(ext, level, inputs)
    # Bruit de bord : poids bruts multipliés par 1 ± NOISE_AMPLITUDE / 2, par point et par biome.
    for b in range(NB):
        raw[:, b] *= 1.0 + NOISE_AMPLITUDE * (_hash01(ext.gx, ext.gz, salt * NB + b + 1) - 0.5)
    w = _blur(raw, ext, core)
    lat_c, lon_c = inputs.to_latlon((core.gx * level.cell_m).astype(float), (core.gz * level.cell_m).astype(float))
    lat_c, lon_c = np.asarray(lat_c), np.asarray(lon_c)
    total = w.sum(axis=1)
    empty = total <= 1e-9
    if empty.any():   # aucun vote dans le rayon du flou (eau, bâti) : prairie de la zone
        zw = np.asarray(inputs.zones(lat_c[empty], lon_c[empty]), dtype=float).reshape(-1, len(ZONES))
        fill = np.zeros((int(empty.sum()), NB))
        for z in range(len(ZONES)):
            fill[np.arange(len(fill)), CLASS_TABLE[NODATA_CLASS, z]] += zw[:, z]
        w[empty] = fill
        total = w.sum(axis=1)
    w = w / total[:, None]
    if inputs.elevation is not None:
        alt = np.asarray(inputs.elevation(lat_c, lon_c), dtype=float)
        a = alpine_part(alt, lat_c) * (1.0 - plateau_part(alt, lat_c))   # hauts plateaux : pas d'alpage
        w *= (1.0 - a)[:, None]
        w[:, INDEX["alpine"]] += a

    # Quatre biomes au plus par tuile : les plus forts de la tuile.
    tile_index = {key: k for k, key in enumerate(keys)}
    pos = {key: core.find(*_tile_grid([key], 0)) for key in keys}
    allowed = np.zeros((len(keys), NB), dtype=bool)
    for key, k in tile_index.items():
        sums = w[pos[key]].sum(axis=0)
        top = sorted(range(NB), key=lambda b: (-sums[b], b))[:MAX_BIOMES_PER_TILE]
        allowed[k, [b for b in top if sums[b] > 0] or top[:1]] = True
    owners = _owners(core.gx, core.gz, tile_index)          # (n, 4), −1 : pas de tuile
    tile_sums = {key: w[pos[key]].sum(axis=0) for key in keys}
    for _ in range(MAX_FIX_ROUNDS):
        mask = np.ones((len(core), NB), dtype=bool)
        for c in range(owners.shape[1]):
            has = owners[:, c] >= 0
            mask[has] &= allowed[owners[has, c]]
        bad = np.flatnonzero(~mask.any(axis=1))
        if len(bad) == 0:
            break
        # Point d'un coin dont les tuiles n'ont aucun biome commun (cas d'école) : son biome le plus fort
        # entre dans chacune de ses tuiles, à la place du plus faible si la tuile en a déjà quatre.
        for p in bad.tolist():
            best = int(np.argmax(w[p]))
            for k in owners[p][owners[p] >= 0].tolist():
                if allowed[k, best]:
                    continue
                if allowed[k].sum() >= MAX_BIOMES_PER_TILE:
                    sums = tile_sums[keys[k]]
                    weakest = min(np.flatnonzero(allowed[k]).tolist(), key=lambda b: (sums[b], -b))
                    allowed[k, weakest] = False
                allowed[k, best] = True
    else:
        raise ValueError("couche biome : quatre biomes par tuile impossibles à tenir")
    wm = np.where(mask, w, 0.0)
    zero = wm.sum(axis=1) <= 0
    if zero.any():   # biomes admis tous nuls en ce point : le premier admis prend tout
        first = np.argmax(mask[zero], axis=1)
        wm[np.flatnonzero(zero), first] = 1.0
    ints = _round_255(wm)

    tiles: dict[tuple[int, int], dict] = {}
    for key in keys:
        g = ints[pos[key]]                      # (289, 16), rangé par ligne (j × 17 + i)
        sums = g.sum(axis=0)
        used = sorted((b for b in range(NB) if sums[b] > 0), key=lambda b: (-sums[b], b))
        tiles[key] = {"version": BIOME_VERSION, "biomes": [BIOMES[b] for b in used], "grid": GRID,
                      "weights": [g[:, b].tolist() for b in used], "variant": None}
    return tiles


def forced_tiles(keys: Sequence[tuple[int, int]], biome: str) -> dict[tuple[int, int], dict]:
    """Tuiles d'un biome imposé (`--biome`) : 255 partout."""
    if biome not in INDEX:
        raise ValueError(f"biome inconnu : {biome}")
    return {(int(a), int(b)): {"version": BIOME_VERSION, "biomes": [biome], "grid": GRID,
                               "weights": [[TOTAL] * (GRID * GRID)], "variant": None}
            for a, b in sorted({(int(a), int(b)) for a, b in keys})}


def route_shares(tiles: dict[tuple[int, int], dict], x: Sequence[float], z: Sequence[float],
                 level: BiomeLevel = NEAR) -> dict[str, float]:
    """Part (%) de chaque biome le long de la route : poids des tuiles interpolés en chaque point de route."""
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    acc = np.zeros(NB)
    count = 0
    cell = level.cell_m
    ix = np.floor(x / level.tile_m).astype(np.int64)
    iz = np.floor(z / level.tile_m).astype(np.int64)
    for key in sorted(set(zip(ix.tolist(), iz.tolist()))):
        tile = tiles.get(key)
        if tile is None:
            continue
        sel = (ix == key[0]) & (iz == key[1])
        fx = np.clip((x[sel] - key[0] * level.tile_m) / cell, 0.0, CELLS - 1e-9)
        fz = np.clip((z[sel] - key[1] * level.tile_m) / cell, 0.0, CELLS - 1e-9)
        i0, j0 = np.floor(fx).astype(np.int64), np.floor(fz).astype(np.int64)
        u, v = fx - i0, fz - j0
        for name, grid in zip(tile["biomes"], tile["weights"]):
            g = np.asarray(grid, dtype=float).reshape(GRID, GRID)
            val = (g[j0, i0] * (1 - u) * (1 - v) + g[j0, i0 + 1] * u * (1 - v)
                   + g[j0 + 1, i0] * (1 - u) * v + g[j0 + 1, i0 + 1] * u * v)
            acc[INDEX[name]] += val.sum() / TOTAL
        count += int(sel.sum())
    if count == 0:
        return {}
    return {BIOMES[b]: round(float(100.0 * acc[b] / count), 1) for b in range(NB) if acc[b] / count >= 0.0005}


def build_biome_layer(keys: dict[str, Sequence[tuple[int, int]]], route_x: Sequence[float],
                      route_z: Sequence[float], inputs: Inputs | None = None,
                      forced: str | None = None, sources: Sequence[str] = (),
                      to_latlon: Callable[[np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]] | None = None,
                      forced_variant: dict | None = None) -> BiomeLayer:
    """Couche biome complète (niveaux proche et lointain), variante régionale de chaque tuile (lot U4) et
    parts le long de la route.

    La variante vient de `forced_variant` (option `--variant`), sinon de la table régionale au centre de chaque
    tuile (`to_latlon`, ou celui de `inputs`) ; sans projection ni variante imposée, elle reste `null`.
    """
    from . import regional
    tiles: dict[str, dict[tuple[int, int], dict]] = {}
    for k, level in enumerate(LEVELS):
        level_keys = keys.get(level.name, [])
        if forced is not None:
            tiles[level.name] = forced_tiles(level_keys, forced)
        else:
            assert inputs is not None
            tiles[level.name] = classify_level(level_keys, level, inputs, salt=k)
    project = to_latlon or (inputs.to_latlon if inputs is not None else None)
    if forced_variant is not None or project is not None:
        regional.assign_variants(tiles, {level.name: level.tile_m for level in LEVELS}, project,
                                 forced=forced_variant, near=NEAR.name, far=FAR.name)
    shares = route_shares(tiles.get(NEAR.name, {}), route_x, route_z)
    return BiomeLayer(tiles=tiles, shares=shares, forced=forced,
                      sources=["forced"] if forced is not None else list(sources),
                      forced_variant=forced_variant)
