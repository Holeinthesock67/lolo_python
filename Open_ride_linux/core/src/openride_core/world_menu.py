"""Menu du monde ouvert côté core (lot W11, contrat IPC 1.5) : recherche de lieu, carte régionale, régions.

- `world_search` : liste embarquée (`data/places.json`), puis bases locales (`menu_query` du compilateur,
  lancé comme sous-processus : le core ne dépend pas de numpy), puis Nominatim si `network` est vrai,
  à la demande seulement et une requête par seconde au plus.
- `world_map`, `world_regions`, `world_pin` : réponses de `menu_query`.
Chaque méthode renvoie les messages à envoyer (déjà découpés en parties de 60 000 octets).
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .ipc_lists import build_world_messages
from .launcher import worldmenu_command

log = logging.getLogger("world_menu")

PLACES_PATH = Path(__file__).parent / "data" / "places.json"
MAX_PLACES = 50
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_PERIOD_S = 1.0
QUERY_TIMEOUT_S = 20.0
USER_AGENT = f"OpenRide/{__version__} (https://github.com/Holeinthesock67/lolo_python)"
MAX_RADIUS_M = 20_000.0


def fold(text: str) -> str:
    """Minuscules sans accents, ponctuation en espaces (même règle que la base locale)."""
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in t).split())


KINDS = ("city", "town", "village", "hamlet", "pass", "peak")
KIND_ALIASES = {"mountain_pass": "pass", "saddle": "pass", "mountain_peak": "peak", "volcano": "peak", "suburb": "town",
                "municipality": "town", "administrative": "town"}


def place_kind(raw: Any) -> str:
    """Genre du contrat `places` (`city`, `town`, `village`, `hamlet`, `pass`, `peak`, `other`)."""
    k = str(raw)
    k = KIND_ALIASES.get(k, k)
    return k if k in KINDS else "other"


def _default_fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
    req = urllib.request.Request(url, headers=headers)   # noqa: S310 (adresse fixe, https)
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
        return r.read()


class WorldMenu:
    def __init__(self, network: bool = True, config_path: Path | None = None, places_path: Path = PLACES_PATH,
                 query_cmd: list[str] | None = None, fetch: Callable[[str, dict[str, str], float], bytes] = _default_fetch,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self.network = network
        self.config_path = config_path
        self.query_cmd = query_cmd
        self.fetch = fetch
        self.clock = clock
        self.sleep = sleep
        self._last_nominatim = -1e9
        self.nominatim_requests = 0
        self._places: list[tuple[str, str, str, float, float]] = []   # (nom replié, nom, genre, lat, lon)
        try:
            doc = json.loads(Path(places_path).read_text(encoding="utf-8"))
            for name, kind, lat, lon, _country, _pop in doc["places"]:
                self._places.append((fold(name), name, kind, float(lat), float(lon)))
        except (OSError, ValueError, KeyError) as exc:
            log.warning("Liste de lieux embarquée illisible (%s) : %s", places_path, exc)

    # --- sources -------------------------------------------------------------------------------

    def embedded(self, text: str, limit: int = MAX_PLACES) -> list[dict[str, Any]]:
        q = fold(text)
        if not q:
            return []
        hits = [p for p in self._places if q in p[0]]
        hits.sort(key=lambda p: (not p[0].startswith(q), p[2] == "city"))     # début du nom, puis sommets et cols avant villes
        return [{"name": n, "kind": k, "lat": lat, "lon": lon, "cached": False, "source": "embedded"}
                for _f, n, k, lat, lon in hits[:limit]]

    def query(self, *args: str) -> dict[str, Any]:
        """Lance `menu_query` ; {} en cas d'échec (compilateur absent, délai dépassé, sortie illisible)."""
        cmd = [*(self.query_cmd or worldmenu_command()), *(["--config", str(self.config_path)] if self.config_path else []),
               *args]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=QUERY_TIMEOUT_S, check=False)   # noqa: S603
            out = json.loads(res.stdout.strip().splitlines()[-1]) if res.stdout.strip() else {}
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            log.warning("Requête du menu (%s) impossible : %s", args[0] if args else "?", exc)
            return {}
        if not isinstance(out, dict) or "error" in out:
            log.warning("Requête du menu (%s) refusée : %s", args[0] if args else "?", out.get("error") if isinstance(out, dict) else out)
            return {}
        return out

    def nominatim(self, text: str) -> list[dict[str, Any]]:
        wait = self._last_nominatim + NOMINATIM_PERIOD_S - self.clock()
        if wait > 0:
            self.sleep(wait)
        self._last_nominatim = self.clock()
        self.nominatim_requests += 1
        url = NOMINATIM_URL + "?" + urllib.parse.urlencode({"q": text, "format": "jsonv2", "limit": 10})
        try:
            rows = json.loads(self.fetch(url, {"User-Agent": USER_AGENT, "Accept-Language": "fr"}, 10.0))
            return [{"name": str(r["display_name"])[:120], "kind": place_kind(r.get("type", "")), "lat": round(float(r["lat"]), 5),
                     "lon": round(float(r["lon"]), 5), "cached": False, "source": "nominatim"} for r in rows]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("Nominatim indisponible : %s", exc)
            return []

    # --- commandes -----------------------------------------------------------------------------

    def search(self, request_cmd_id: int, text: Any) -> list[dict[str, Any]]:
        text = text.strip() if isinstance(text, str) else ""
        items: list[dict[str, Any]] = []
        if text:
            items = self.embedded(text)
            items += [{**i, "kind": place_kind(i.get("kind"))}
                      for i in self.query("search", "--text", text, "--limit", str(MAX_PLACES)).get("items", [])]
            if self.network and len(items) < MAX_PLACES:
                items += self.nominatim(text)
        seen: set[tuple[str, int, int]] = set()
        unique = []
        for it in items:
            k = (fold(it["name"]), round(it["lat"] * 20), round(it["lon"] * 20))     # même lieu à ~5 km près
            if k not in seen:
                seen.add(k)
                unique.append(it)
        return build_world_messages("places", request_cmd_id, "items", unique[:MAX_PLACES], truncated=len(unique) > MAX_PLACES)

    def world_map(self, request_cmd_id: int, args: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            lat, lon = float(args["lat"]), float(args["lon"])
            radius = min(float(args["radius_m"]), MAX_RADIUS_M)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180 and radius > 0):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            lat = lon = radius = 0.0
            roads: list[dict[str, Any]] = []
        else:
            roads = self.query("map", "--lat", repr(lat), "--lon", repr(lon), "--radius", repr(radius)).get("roads", [])
        return build_world_messages("world_map", request_cmd_id, "roads", roads,
                                    extra={"lat": lat, "lon": lon, "radius_m": radius})

    def regions(self, request_cmd_id: int, pin: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if pin is not None and isinstance(pin.get("region_id"), str) and isinstance(pin.get("pinned"), bool):
            out = self.query("pin", "--region", pin["region_id"], "--pinned", "1" if pin["pinned"] else "0")
        else:
            out = self.query("regions")
        return build_world_messages("world_regions", request_cmd_id, "items", out.get("items", []),
                                    extra={"cache_bytes": int(out.get("cache_bytes", 0)),
                                           "cache_max_bytes": int(out.get("cache_max_bytes", 0))})
