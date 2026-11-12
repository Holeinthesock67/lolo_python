"""Vent d'après la météo du jour (lot P33, exigence 3.0-VNT-1, règles R-NET-1 à R-NET-3).

Deux moitiés, séparées par un fichier de cache local :

- le **lanceur** (`refresh`, jamais le core) lit le vent du moment chez Open-Meteo (sans clé ni
  compte) pour le point de départ de chaque parcours installé, en une seule requête, avec un délai
  court (`TIMEOUT_S`, 5 s), dans un fil à part : le lancement n'attend pas la réponse ;
- le **core** (`lookup`) lit ce fichier au choix du parcours et au départ : aucune E/S réseau,
  aucune attente. Sans entrée de moins de 3 h pour le départ du parcours, la séance roule sans vent,
  exactement comme en mode `off`.

Vie privée (invariant A8 de la spécification) : chaque position est arrondie à `CELL_DEG` (0,1°,
environ 10 km) *avant* la requête, le cache et le journal ; aucune coordonnée précise ne sort du PC.

Conversion : Open-Meteo donne le vent à 10 m. Le cycliste roule vers 1,5 m, où le vent est plus faible :
`HEIGHT_FACTOR` (0,6) vient du profil logarithmique d'une campagne ouverte (rugosité 0,1 m :
ln(1,5/0,1) / ln(10/0,1) ≈ 0,59). Les rafales deviennent `gust_pct` = 100 × (rafale − vent) / vent,
borné à 0–100 ; la direction est celle d'où vient le vent, comme `[wind] from_deg`.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import BOUNDS, CACHE_DIR

log = logging.getLogger(__name__)

SOURCE = "open-meteo"
SOURCE_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_S = 5.0                  # délai de la requête (cahier P33 §3)
CACHE_TTL_S = 3 * 3600.0         # une lecture sert 3 h (cahier P33 §3)
RETRY_S = 15 * 60.0              # après un échec (hors ligne), nouvel essai au plus tôt 15 min plus tard
CELL_DEG = 0.1                   # maille d'arrondi des positions, environ 10 km
MAX_POINTS = 25                  # départs lus en une requête ; au-delà, les parcours les plus récents
HEIGHT_FACTOR = 0.6              # vent à hauteur de cycliste / vent à 10 m
CACHE_FILE = CACHE_DIR / "meteo_vent.json"
CACHE_VERSION = 1
MAX_SPEED_KMH = float(BOUNDS[("wind", "speed_kmh")][1])
USER_AGENT = "OpenRide (vent du jour, lot P33)"


class WeatherError(Exception):
    """Lecture impossible : hors ligne, délai dépassé, réponse illisible."""


@dataclass(frozen=True)
class LocalWind:
    """Vent du jour pour une maille, prêt pour `WindModel` (hauteur du cycliste)."""
    lat: float
    lon: float
    speed_kmh: float
    from_deg: float
    gust_pct: float
    fetched_at: float    # heure Unix de la lecture

    def to_dict(self) -> dict[str, float]:
        return {"lat": self.lat, "lon": self.lon, "speed_kmh": self.speed_kmh, "from_deg": self.from_deg,
                "gust_pct": self.gust_pct, "fetched_at": self.fetched_at}


# --- positions --------------------------------------------------------------------------------------

def cell(lat: float, lon: float) -> tuple[float, float]:
    """Maille de 0,1° qui contient le point ; la seule forme de position gardée ou envoyée."""
    return (round(round(lat / CELL_DEG) * CELL_DEG, 1), round(round(lon / CELL_DEG) * CELL_DEG, 1))


def _valid(lat: Any, lon: Any) -> bool:
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not isinstance(lat, bool)
            and not isinstance(lon, bool) and math.isfinite(lat) and math.isfinite(lon)
            and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0)


def route_cells(routes_dir: Path, limit: int = MAX_POINTS) -> list[tuple[float, float]]:
    """Mailles des départs des parcours installés (`origin` du manifeste `.world`), les plus récents d'abord."""
    worlds: list[tuple[float, tuple[float, float]]] = []
    try:
        entries = list(routes_dir.glob("*.world"))
    except OSError:
        return []
    for world in entries:
        manifest = world / "manifest.json"
        try:
            origin = json.loads(manifest.read_text(encoding="utf-8")).get("origin") or {}
            mtime = manifest.stat().st_mtime
        except (OSError, ValueError, AttributeError):
            continue
        lat, lon = origin.get("lat"), origin.get("lon")
        if _valid(lat, lon):
            worlds.append((mtime, cell(float(lat), float(lon))))
    out: list[tuple[float, float]] = []
    for _, c in sorted(worlds, key=lambda w: -w[0]):
        if c not in out:
            out.append(c)
    return out[:limit]


# --- Open-Meteo --------------------------------------------------------------------------------------

def request_url(cells: list[tuple[float, float]]) -> str:
    """Une requête pour toutes les mailles (listes de latitudes et de longitudes séparées par des virgules)."""
    query = {
        "latitude": ",".join(f"{c[0]:.1f}" for c in cells),
        "longitude": ",".join(f"{c[1]:.1f}" for c in cells),
        "current": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "wind_speed_unit": "kmh",
        "timezone": "GMT",
    }
    return f"{SOURCE_URL}?{urllib.parse.urlencode(query, safe=',')}"


def convert(speed10_kmh: float, from_deg: float, gusts10_kmh: float | None) -> tuple[float, float, float]:
    """(vitesse, direction, rafales %) à hauteur de cycliste depuis les valeurs à 10 m."""
    speed = min(max(speed10_kmh, 0.0) * HEIGHT_FACTOR, MAX_SPEED_KMH)
    gust_pct = 0.0
    if gusts10_kmh is not None and speed10_kmh > 0.5:
        gust_pct = min(max(100.0 * (gusts10_kmh - speed10_kmh) / speed10_kmh, 0.0), 100.0)
    return round(speed, 1), round(from_deg % 360.0, 0), round(gust_pct, 0)


def parse_response(data: Any, cells: list[tuple[float, float]], now: float) -> list[LocalWind]:
    """Réponse JSON d'Open-Meteo (objet pour un point, liste pour plusieurs) vers une entrée par maille."""
    items = data if isinstance(data, list) else [data]
    if len(items) != len(cells):
        raise WeatherError(f"réponse pour {len(items)} points, {len(cells)} demandés")
    out: list[LocalWind] = []
    for c, item in zip(cells, items):
        cur = item.get("current") if isinstance(item, dict) else None
        if not isinstance(cur, dict):
            raise WeatherError("réponse sans valeurs « current »")
        speed, direction, gusts = (cur.get("wind_speed_10m"), cur.get("wind_direction_10m"),
                                   cur.get("wind_gusts_10m"))
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (speed, direction)):
            raise WeatherError("vitesse ou direction du vent absente")
        g = float(gusts) if isinstance(gusts, (int, float)) and not isinstance(gusts, bool) else None
        s, d, gp = convert(float(speed), float(direction), g)
        out.append(LocalWind(c[0], c[1], s, d, gp, now))
    return out


Opener = Callable[..., Any]


def fetch(cells: list[tuple[float, float]], now: float, opener: Opener | None = None,
          timeout_s: float = TIMEOUT_S) -> list[LocalWind]:
    """Lit le vent du moment pour `cells` ; lève `WeatherError` (hors ligne, délai, réponse illisible)."""
    if not cells:
        return []
    req = urllib.request.Request(request_url(cells), headers={"User-Agent": USER_AGENT})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=timeout_s) as resp:
            body = resp.read(1_000_000)
        data = json.loads(body.decode("utf-8"))
    except WeatherError:
        raise
    except (OSError, ValueError, UnicodeDecodeError) as exc:   # URLError, délai, JSON illisible
        raise WeatherError(f"{type(exc).__name__} : {exc}") from None
    return parse_response(data, cells, now)


# --- cache -------------------------------------------------------------------------------------------

def read_cache(path: Path | None = None) -> list[LocalWind]:
    """Entrées du cache ; liste vide si le fichier manque, est illisible ou d'une autre version."""
    path = path or CACHE_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return []
    out: list[LocalWind] = []
    for e in data.get("cells") or []:
        try:
            out.append(LocalWind(float(e["lat"]), float(e["lon"]), float(e["speed_kmh"]),
                                 float(e["from_deg"]), float(e["gust_pct"]), float(e["fetched_at"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def write_cache(entries: Iterable[LocalWind], path: Path | None = None) -> None:
    """Écriture atomique (fichier voisin puis renommage) : le core ne lit jamais un cache à moitié écrit."""
    path = path or CACHE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": CACHE_VERSION, "source": SOURCE, "cells": [e.to_dict() for e in entries]}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def fresh(entry: LocalWind, now: float) -> bool:
    return 0.0 <= now - entry.fetched_at <= CACHE_TTL_S


def lookup(lat: float, lon: float, path: Path | None = None, now: float | None = None) -> LocalWind | None:
    """Côté core : vent du jour de la maille du point, s'il a moins de 3 h ; None sinon (séance sans vent)."""
    if not _valid(lat, lon):
        return None
    now = time.time() if now is None else now
    want = cell(lat, lon)
    for e in read_cache(path):
        if (e.lat, e.lon) == want and fresh(e, now):
            return e
    return None


def status(path: Path | None = None, now: float | None = None) -> str:
    """Phrase du menu (aide du réglage Vent) : dernière lecture, ou pourquoi il n'y en a pas."""
    now = time.time() if now is None else now
    entries = [e for e in read_cache(path) if fresh(e, now)]
    if not entries:
        return ("Aucune lecture de moins de 3 h (hors ligne ou pas encore lue) : "
                "la séance roule sans vent.")
    last = max(e.fetched_at for e in entries)
    hhmm = time.strftime("%H h %M", time.localtime(last))
    n = len(entries)
    return f"Lue à {hhmm} pour {n} départ{'s' if n > 1 else ''} de parcours."


# --- côté lanceur ------------------------------------------------------------------------------------

def refresh(routes_dir: Path, path: Path | None = None, now: float | None = None,
            opener: Opener | None = None, timeout_s: float = TIMEOUT_S) -> str | None:
    """Lit les mailles sans entrée de moins de 3 h et réécrit le cache ; renvoie la ligne du journal,
    ou None s'il n'y avait rien à lire (aucun départ connu, cache encore frais).

    Lève `WeatherError` hors ligne : le lanceur l'écrit au journal, le cache existant est gardé.
    """
    now = time.time() if now is None else now
    wanted = route_cells(routes_dir)
    kept = {(e.lat, e.lon): e for e in read_cache(path) if fresh(e, now)}
    missing = [c for c in wanted if c not in kept]
    if not missing:
        return None
    for e in fetch(missing, now, opener, timeout_s):
        kept[(e.lat, e.lon)] = e
    write_cache(kept.values(), path)
    return (f"vent du jour lu chez Open-Meteo pour {len(missing)} départ(s) de parcours "
            "(positions arrondies à 10 km).")
