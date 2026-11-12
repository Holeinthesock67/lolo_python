"""Carte des climats de Köppen-Geiger embarquée (lot U24) et zones climatiques des biomes. Numpy seul.

La carte `data/koppen_1986_2010.u8.xz` est une grille équirectangulaire de 12 960 × 6 480 pixels de
100 secondes d'arc (environ 3 km), un octet par pixel, rangée du nord au sud puis d'ouest en est, compressée
en xz : codes 1 à 31 dans l'ordre de `CODES`, 32 pour la mer. Provenance et licence :
`data/koppen_LISEZMOI.md` ; elle se refait avec `scripts/prepare_koppen.py`. Aucun accès réseau.

Chaque code donne une des six zones des biomes (`ZONE_OF`) ; la part de chaque zone en un point est la
moyenne des pixels de terre d'un voisinage de 5 × 5 pixels (noyau binomial, une quinzaine de kilomètres),
ce qui fond les limites ; la toundra de montagne compte comme boréale (`MOUNTAIN_POLAR_LAT`). Un point dont tout le voisinage est en mer garde les bandes de latitude d'avant.
"""

from __future__ import annotations

import lzma
from functools import lru_cache
from importlib import resources

import numpy as np

DATA_FILE = "koppen_1986_2010.u8.xz"
SOURCE = "koppen_1986_2010"
WIDTH, HEIGHT = 12960, 6480           # 100″ d'arc
CODES = ("Af", "Am", "As", "Aw", "BSh", "BSk", "BWh", "BWk", "Cfa", "Cfb", "Cfc", "Csa", "Csb", "Csc",
         "Cwa", "Cwb", "Cwc", "Dfa", "Dfb", "Dfc", "Dfd", "Dsa", "Dsb", "Dsc", "Dsd", "Dwa", "Dwb", "Dwc",
         "Dwd", "EF", "ET")
OCEAN = 32

ZONES = ("tropical", "arid", "warm", "temperate", "boreal", "polar")
# Zone des biomes de chaque climat. `warm` (biome méditerranéen) ne prend que l'été chaud et sec (Csa) :
# les étés secs plus frais (Csb, Csc : Galice, Asturies, Oregon, hauts de Tenerife) ont une végétation
# atlantique et vont en `temperate`, comme les climats continentaux à été chaud ou tiède (Dfa, Dfb…).
ZONE_OF = {
    "Af": "tropical", "Am": "tropical", "As": "tropical", "Aw": "tropical",
    "BSh": "arid", "BSk": "arid", "BWh": "arid", "BWk": "arid",
    "Csa": "warm",
    "Cfa": "temperate", "Cfb": "temperate", "Csb": "temperate", "Csc": "temperate", "Cwa": "temperate",
    "Cwb": "temperate", "Dfa": "temperate", "Dfb": "temperate", "Dsa": "temperate", "Dsb": "temperate",
    "Dwa": "temperate", "Dwb": "temperate",
    "Cfc": "boreal", "Cwc": "boreal", "Dfc": "boreal", "Dfd": "boreal", "Dsc": "boreal", "Dsd": "boreal",
    "Dwc": "boreal", "Dwd": "boreal",
    "ET": "polar", "EF": "polar",
}
# Toundra et glace (ET, EF) hors des régions polaires : ce sont les hauts des montagnes, que l'étage alpin
# des biomes rend déjà d'après l'altitude ; ces pixels comptent comme boréaux sous 58° de latitude, comme
# polaires au-dessus de 62°, avec une rampe entre les deux.
MOUNTAIN_POLAR_LAT = (58.0, 62.0)
KERNEL = np.array([1.0, 4.0, 6.0, 4.0, 1.0]) / 16.0
RADIUS = len(KERNEL) // 2


def _zone_table() -> np.ndarray:
    """Table (256,) code → indice de zone (−1 : mer ou code inconnu)."""
    table = np.full(256, -1, dtype=np.int64)
    for k, code in enumerate(CODES, start=1):
        table[k] = ZONES.index(ZONE_OF[code])
    return table


ZONE_TABLE = _zone_table()


@lru_cache(maxsize=1)
def grid() -> np.ndarray:
    """Carte entière (HEIGHT, WIDTH), lue une fois par processus (environ 0,2 s, 84 Mo)."""
    raw = lzma.decompress(resources.files("openride_compiler").joinpath("data", DATA_FILE).read_bytes())
    if len(raw) != WIDTH * HEIGHT:
        raise ValueError(f"{DATA_FILE} : {len(raw)} octets, {WIDTH * HEIGHT} attendus")
    return np.frombuffer(raw, dtype=np.uint8).reshape(HEIGHT, WIDTH)


def pixel(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ligne et colonne du pixel qui contient chaque point (longitude repliée, latitude bornée)."""
    lat = np.asarray(lat, dtype=float).ravel()
    lon = np.asarray(lon, dtype=float).ravel()
    col = np.floor((lon + 180.0) * WIDTH / 360.0).astype(np.int64) % WIDTH
    row = np.clip(np.floor((90.0 - lat) * HEIGHT / 180.0).astype(np.int64), 0, HEIGHT - 1)
    return row, col


def codes(lat: np.ndarray, lon: np.ndarray) -> list[str | None]:
    """Code Köppen de chaque point (None en mer)."""
    row, col = pixel(lat, lon)
    v = grid()[row, col]
    return [CODES[c - 1] if 1 <= c <= len(CODES) else None for c in v.tolist()]


def zone_weights(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Part (n, 6) de chaque zone d'après la carte, et masque (n,) des points sans terre dans le voisinage."""
    row, col = pixel(lat, lon)
    g = grid()
    w = np.zeros((len(row), len(ZONES)))
    idx = np.arange(len(row))
    for dj in range(-RADIUS, RADIUS + 1):
        r = np.clip(row + dj, 0, HEIGHT - 1)
        for di in range(-RADIUS, RADIUS + 1):
            z = ZONE_TABLE[g[r, (col + di) % WIDTH]]
            land = z >= 0
            np.add.at(w, (idx[land], z[land]), KERNEL[dj + RADIUS] * KERNEL[di + RADIUS])
    a = np.abs(np.asarray(lat, dtype=float).ravel())
    lo, hi = MOUNTAIN_POLAR_LAT
    move = w[:, -1] * (1.0 - np.clip((a - lo) / (hi - lo), 0.0, 1.0))
    w[:, -1] -= move
    w[:, ZONES.index("boreal")] += move
    total = w.sum(axis=1)
    sea = total <= 0
    w[~sea] /= total[~sea, None]
    return w, sea
