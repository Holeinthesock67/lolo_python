"""Client Overpass et cache brut OpenStreetMap (Lot I3, SRS §7 et §10, Format .world v1 §6 et §7).

- Découpe la route en boîtes englobantes par tronçon de 1 km élargies de 400 m,
  regroupées par paquets pour limiter le nombre d'appels HTTP.
- Cache brut : ``~/.cache/openride/osm/<sha256_de_la_requete>.json`` (ou ``OPENRIDE_OSM_CACHE``).
- Une requête présente en cache n'appelle jamais le réseau ; ``--offline`` interdit tout appel.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

import numpy as np

from . import constants as C
from .cache import RETRIES, RETRY_DELAYS_S, TIMEOUT_S, Log, stderr_log
from .errors import CompileError
from .frame import LocalFrame

OSM_CACHE_ENV = "OPENRIDE_OSM_CACHE"
DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "OpenRideCompiler/0.1 (+https://github.com/Holeinthesock67/lolo_python)"
CHUNKS_PER_PACKET = 10


def osm_cache_dir() -> Path:
    env = os.environ.get(OSM_CACHE_ENV)
    return Path(env) if env else Path.home() / ".cache" / "openride" / "osm"


def chunk_bboxes(
    route: dict[str, Any],
    frame: LocalFrame,
    band_m: float = C.OSM_BAND_M,
) -> list[tuple[float, float, float, float]]:
    """Renvoie une boîte (south, west, north, east) en degrés par tronçon de 1 km."""
    xs = np.asarray(route["x"], dtype=float)
    zs = np.asarray(route["z"], dtype=float)
    n = int(route["n"])
    ds_m = float(route["ds_m"])
    length_m = float(route["length_m"])
    s_arr = np.array([i * ds_m for i in range(n - 1)] + [length_m], dtype=float)
    chunk_ids = (s_arr // C.CHUNK_LENGTH_M).astype(int)

    bboxes: list[tuple[float, float, float, float]] = []
    for k in range(int(chunk_ids.max()) + 1):
        mask = chunk_ids == k
        if not mask.any():
            continue
        x_min, x_max = float(xs[mask].min() - band_m), float(xs[mask].max() + band_m)
        z_min, z_max = float(zs[mask].min() - band_m), float(zs[mask].max() + band_m)
        corners_x = np.array([x_min, x_max, x_min, x_max], dtype=float)
        corners_z = np.array([z_min, z_min, z_max, z_max], dtype=float)
        lats, lons = frame.to_latlon(corners_x, corners_z)
        south = round(float(np.min(lats)), 5)
        north = round(float(np.max(lats)), 5)
        west = round(float(np.min(lons)), 5)
        east = round(float(np.max(lons)), 5)
        bboxes.append((south, west, north, east))
    return bboxes


def build_overpass_query(bboxes: list[tuple[float, float, float, float]]) -> str:
    """Construit la requête Overpass QL pour un paquet de boîtes englobantes (Lots I3 et I4)."""
    parts: list[str] = []
    for south, west, north, east in bboxes:
        b = f"({south:.5f},{west:.5f},{north:.5f},{east:.5f})"
        parts.extend([
            f'  way["building"]{b};',
            f'  relation["building"]{b};',
            f'  way["landuse"="forest"]{b};',
            f'  relation["landuse"="forest"]{b};',
            f'  way["natural"="wood"]{b};',
            f'  relation["natural"="wood"]{b};',
            f'  way["natural"="scrub"]{b};',
            f'  relation["natural"="scrub"]{b};',
            f'  way["landuse"="orchard"]{b};',
            f'  relation["landuse"="orchard"]{b};',
            f'  node["amenity"="place_of_worship"]{b};',
            f'  way["amenity"="place_of_worship"]{b};',
            f'  relation["amenity"="place_of_worship"]{b};',
            f'  node["place"~"^(village|hamlet|town)$"]{b};',
            f'  way["place"~"^(village|hamlet|town)$"]{b};',
            f'  node["tourism"="viewpoint"]{b};',
            f'  way["tourism"="viewpoint"]{b};',
            f'  way["landuse"="farmyard"]{b};',
            f'  relation["landuse"="farmyard"]{b};',
            f'  way["landuse"="meadow"]["animal"]{b};',
            f'  relation["landuse"="meadow"]["animal"]{b};',
            f'  way["waterway"~"^(river|stream|canal)$"]{b};',
            f'  way["natural"="water"]{b};',
            f'  relation["natural"="water"]{b};',
            f'  way["landuse"="reservoir"]{b};',
            f'  relation["landuse"="reservoir"]{b};',
        ])
    union_body = "\n".join(parts)
    return f"[out:json][timeout:60];\n(\n{union_body}\n);\nout body geom;\n"


def query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


class OverpassClient:
    """Client Overpass avec cache sur disque et reprises à délai croissant (429 respecté)."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        offline: bool = False,
        endpoint: str = DEFAULT_OVERPASS_URL,
        log: Log = stderr_log,
        sleep: Callable[[float], None] = time.sleep,
        timeout_s: float = TIMEOUT_S,
        urlopen: Callable[..., Any] | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir is not None else osm_cache_dir()
        self.offline = offline
        self.endpoint = endpoint
        self.log = log
        self.sleep = sleep
        self.timeout_s = timeout_s
        self._urlopen = urlopen
        self.downloads = 0

    def cache_path_for(self, query: str) -> Path:
        return self.cache_dir / f"{query_hash(query)}.json"

    def fetch_bbox(self, bbox: tuple[float, float, float, float]) -> dict[str, Any]:
        return self.fetch_query(build_overpass_query([bbox]))

    def fetch_query(self, query: str) -> dict[str, Any]:
        dest = self.cache_path_for(query)
        if dest.is_file():
            try:
                return json.loads(dest.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CompileError(f"cache OSM illisible ({dest}) : {exc}") from exc

        if self.offline:
            raise CompileError(
                f"réponse Overpass absente du cache ({dest.name}) et réseau interdit (--offline)"
            )

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.tmp-{os.getpid()}")
        payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
        last_error: Exception | None = None

        for attempt in range(RETRIES + 1):
            if attempt:
                delay = RETRY_DELAYS_S[min(attempt - 1, len(RETRY_DELAYS_S) - 1)]
                self.log(f"  Overpass : nouvelle tentative dans {delay:.0f} s ({attempt}/{RETRIES}) : {last_error}")
                self.sleep(delay)
            try:
                self.log(f"requête Overpass ({dest.name[:10]}…)…")
                req = urllib.request.Request(
                    self.endpoint,
                    data=payload,
                    headers={"User-Agent": USER_AGENT},
                    method="POST",
                )
                urlopen_fn = self._urlopen or urllib.request.urlopen
                with urlopen_fn(req, timeout=self.timeout_s) as resp:
                    raw = resp.read()
                parsed = json.loads(raw.decode("utf-8"))
                if not isinstance(parsed, dict) or "elements" not in parsed:
                    raise CompileError("réponse Overpass invalide (champ 'elements' absent)")
                tmp.write_bytes(raw)
                os.replace(tmp, dest)
                self.downloads += 1
                return parsed
            except urllib.error.HTTPError as exc:
                tmp.unlink(missing_ok=True)
                last_error = exc
                if exc.code == 429:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    if retry_after:
                        try:
                            wait_s = float(retry_after)
                            if wait_s > 0:
                                self.sleep(wait_s)
                        except ValueError:
                            pass
            except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
                tmp.unlink(missing_ok=True)
                last_error = exc

        raise CompileError(
            f"échec de la requête Overpass après {RETRIES} reprises : {last_error}"
        )

    def fetch_for_route(
        self,
        route: dict[str, Any],
        frame: LocalFrame,
        chunks_per_packet: int = CHUNKS_PER_PACKET,
    ) -> list[dict[str, Any]]:
        bboxes = chunk_bboxes(route, frame)
        responses: list[dict[str, Any]] = []
        for i in range(0, len(bboxes), chunks_per_packet):
            packet = bboxes[i:i + chunks_per_packet]
            q = build_overpass_query(packet)
            responses.append(self.fetch_query(q))
        return responses
