"""Couche biome du monde ouvert (lot W17, Format .world v1 §8 quater et §13).

Chaque carré de 1 km et chaque tuile lointaine de 5 km du cache reçoit sa tuile de biome, calculée par la
même règle que les parcours compilés (`biomes.classify_level`, puis `regional.assign_variants`) :
occupation du sol ESA WorldCover, climat (carte de Köppen embarquée), altitude du relief, broussailles et
vergers de la base OSM du monde ouvert, variante régionale au centre de la tuile.

- Repère : celui de la zone UTM (x = E, z = −N) ; la tuile proche du carré global `(IX, IN)` est la tuile
  `(IX, −IN − 1)` de ce repère. La grille des poids (pas de 62,5 m ou 312,5 m) tombe sur celle de toute
  séance, dont l'origine est un multiple de 5 000 m : une tuile du cache se lie telle quelle (§13).
- Cache : `genere/<zone>/biome/near/<IX>_<IN>.json` et `genere/<zone>/biome/far/<IX5>_<IN5>.json`, entrées
  de sorte `biome`, recalculables sans réseau (évincées avec les carrés).
- WorldCover : le cache du compilateur (`~/.cache/openride/landcover/`), jamais supprimé. Une tuile calculée
  sans WorldCover (hors ligne, ou carré de 0,1° pas encore arrivé) note `"landcover": "absent"` dans ses
  versions : elle est recalculée à la séance suivante dès que la donnée est là.
- Une tuile calculée seule peut différer de sa voisine sur leur bord commun seulement quand l'une des deux
  garde plus de quatre biomes (cas rare : la règle des quatre biomes par tuile s'applique tuile par tuile).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .. import biomes as B
from .. import regional
from ..elevation import ElevationProvider
from ..errors import CompileError
from ..frame import LocalFrame
from ..landcover import WORLDCOVER_NAME, square_keys
from .osmdb import OsmDb
from .squares import FarKey, SquareKey, lonlat_bbox

ABSENT = "absent"
SALT = {"near": 0, "far": 1}          # même sel du bruit de bord que le compilateur, par niveau
COVERAGE_STEP_M = 500.0               # pas des points qui listent les carrés de 0,1° à lire
MAX_LANDCOVER_WINDOWS = 24            # fenêtres de 0,1° gardées en mémoire par la séance


def level_of(key: SquareKey) -> B.BiomeLevel:
    return B.FAR if isinstance(key, FarKey) else B.NEAR


def tile_index(key: SquareKey) -> tuple[int, int]:
    """Indices de la tuile du carré dans le repère de zone."""
    return key.ix, -(key.i_n + 1)


def coverage_latlon(key: SquareKey, frame: LocalFrame) -> tuple[np.ndarray, np.ndarray]:
    """Points espacés de 500 m au plus sur l'emprise de la tuile, marge du flou comprise."""
    level = level_of(key)
    margin = B.MARGIN * level.cell_m
    n = int(np.ceil((level.tile_m + 2 * margin) / COVERAGE_STEP_M)) + 1
    t = np.linspace(-margin, level.tile_m + margin, n)
    gx, gz = np.meshgrid(t, t)
    x0, z0 = key.corner
    lat, lon = frame.to_latlon(x0 + gx.ravel(), z0 + gz.ravel())
    return np.asarray(lat, dtype=float), np.asarray(lon, dtype=float)


def landcover_squares(key: SquareKey, frame: LocalFrame) -> list[tuple[int, int]]:
    """Carrés WorldCover de 0,1° (dixièmes de degré, coin sud-ouest) qu'il faut pour cette tuile."""
    lat, lon = coverage_latlon(key, frame)
    return [(int(a), int(b)) for a, b in np.unique(square_keys(lat, lon), axis=0).tolist()]


def landcover_cached(landcover, squares: Iterable[tuple[int, int]]) -> bool:
    return landcover is not None and all(landcover.square_path(a, b).is_file() for a, b in squares)


def versions(key: SquareKey, db: OsmDb | None, provider: ElevationProvider, landcover_state: str) -> dict[str, Any]:
    """Versions d'une tuile de biome : règle des biomes, données OSM (carrés proches), relief, WorldCover."""
    from .squares import WORLDGEN_VERSION
    out: dict[str, Any] = {"worldgen": WORLDGEN_VERSION, "biome": B.BIOME_VERSION,
                           "relief": getattr(provider, "name", "inconnu"), "landcover": landcover_state}
    if not isinstance(key, FarKey) and db is not None:
        out.update({"osm_schema": db.meta.get("schema_version"), "osm_date": db.meta.get("osm_date") or None,
                    "osm_region": db.meta.get("region")})
    return out


def osm_areas(key: SquareKey, db: OsmDb, frame: LocalFrame) -> list[B.OsmArea]:
    """Polygones de la base qui corrigent l'occupation du sol (broussailles, vergers…), dans le repère de zone."""
    from .squares import _ring_xz
    level = level_of(key)
    m = B.MARGIN * level.cell_m
    x0, z0 = key.corner
    out = []
    for a in db.areas_in(lonlat_bbox(frame, x0 - m, z0 - m, x0 + key.size_m + m, z0 + key.size_m + m)):
        cls = B.osm_class(a.tags)
        if cls is None:
            continue
        outer = _ring_xz(frame, a.outer, True)
        if outer is None:
            continue
        holes = [h for h in (_ring_xz(frame, h, False) for h in a.holes) if h is not None]
        out.append(B.OsmArea(cls, outer, holes))
    return out


def compute_tile(key: SquareKey, frame: LocalFrame, provider: ElevationProvider, landcover=None,
                 db: OsmDb | None = None) -> dict:
    """Tuile de biome (dictionnaire prêt pour JSON, variante régionale comprise)."""
    level = level_of(key)
    inputs = B.Inputs(to_latlon=frame.to_latlon,
                      landcover=landcover.classes if landcover is not None else None,
                      elevation=provider.elevations,
                      osm=osm_areas(key, db, frame) if db is not None and level is B.NEAR else ())
    idx = tile_index(key)
    tiles = {level.name: B.classify_level([idx], level, inputs, salt=SALT[level.name])}
    regional.assign_variants(tiles, {lv.name: lv.tile_m for lv in B.LEVELS}, frame.to_latlon,
                             near=B.NEAR.name, far=B.FAR.name)
    return tiles[level.name][idx]


def generate(key: SquareKey, frame: LocalFrame, provider: ElevationProvider, cache, landcover=None,
             db: OsmDb | None = None, network: bool = False, log=None) -> Path:
    """Tuile de biome dans le cache ; rien n'est recalculé si elle y est avec les mêmes versions.

    `landcover` : source WorldCover (ou None). Hors ligne, seule une donnée déjà en cache sert ; avec le
    réseau, `landcover.prepare` peut la télécharger (à l'ouverture de la séance seulement : ensuite le fil
    de préchargement l'apporte en avance et le calcul ne lit que le cache).
    """
    level = level_of(key)
    squares = landcover_squares(key, frame)
    have = landcover_cached(landcover, squares)
    expected = WORLDCOVER_NAME if have or (network and landcover is not None) else ABSENT
    ckey = cache.biome_key(key.zone, level.name, key.ix, key.i_n)
    path = cache.biome_path(key.zone, level.name, key.ix, key.i_n)
    if cache.is_valid(ckey, versions(key, db, provider, expected)):
        cache.touch(ckey)
        return path
    state = ABSENT
    source = None
    if landcover is not None and (have or network):
        lat, lon = coverage_latlon(key, frame)
        try:
            landcover.prepare(lat, lon)
            source, state = landcover, WORLDCOVER_NAME
        except CompileError as exc:
            if log is not None:
                log(f"biome {key.ix}_{key.i_n} sans occupation du sol : {exc}")
    tile = compute_tile(key, frame, provider, source, db)
    if len(getattr(landcover, "squares", ())) > MAX_LANDCOVER_WINDOWS:
        landcover.squares.clear()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(tile, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    cache.add(ckey, "biome", path, versions(key, db, provider, state),
              region=(db.meta.get("region") or None) if db is not None and level is B.NEAR else None)
    return path


def manifest_block(sources: list[str]) -> dict:
    """Bloc `layers.biome` du manifeste d'un monde vivant : tuiles listées par `live.json` (§13)."""
    from ..landcover import WORLDCOVER_ATTRIBUTION
    block = {"present": True, "version": B.BIOME_VERSION, "default_biome": B.DEFAULT_BIOME, "forced": None,
             "sources": list(sources), "shares": {}, "tiles": {"near": [], "far": []}}
    if WORLDCOVER_NAME in sources:
        block["attribution"] = WORLDCOVER_ATTRIBUTION
    return block
