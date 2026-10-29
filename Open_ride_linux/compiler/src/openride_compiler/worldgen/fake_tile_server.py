"""Faux serveur de tuiles du monde ouvert (lot X28) : réseau lent, coupé, en erreur ou tronqué.

Sert, sur `127.0.0.1` (port libre, fil à part, `http.server`) :

- `/planet` : un TileJSON dont l'URL de tuiles pointe vers ce serveur (comme OpenFreeMap) ;
- `/t/14/<x>/<y>.pbf` : une tuile vectorielle synthétique (une route est-ouest et une route
  nord-sud par tuile, un bâtiment), donc un quadrillage d'environ 1,8 km ;
- `/dem/tileList.txt` et `/dem/<nom>/<nom>.tif` : un relief Copernicus synthétique (collines
  douces, 120 × 120 pixels par degré : léger, mais lu par le vrai fournisseur).

Le scénario (dictionnaire, lu d'un JSON par `netcheck`) dit comment le réseau se dégrade :

- `latence_s` : nombre, ou `[min, max]` tiré au hasard (graine fixe) ;
- `debit_ko_s` : débit plafonné en kilo-octets par seconde (0 : sans limite) ;
- `coupure_s` : `[début, fin]` en secondes depuis `arm()` (début du trajet) : connexion fermée
  sans réponse ;
- `erreurs` : `{"codes": [429, 500, 503], "par_chemin": 1}` : les N premières demandes de
  chaque chemin reçoivent une erreur, les codes servis à tour de rôle ;
- `tronque` : `{"par_chemin": 1, "part": 0.5}` : les N premières réponses de chaque chemin
  annoncent leur taille entière mais s'arrêtent à `part` ;
- `chemins` : sortes de chemins touchées par les pannes (`tilejson`, `tuile`, `relief`,
  `liste` ; toutes par défaut).

Chaque demande est notée (`log`) : instant depuis `arm()` (négatif avant), chemin, sorte, issue
(`200`, code d'erreur, `coupure` ou `tronque`) et octets envoyés.
"""

from __future__ import annotations

import json
import random
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import numpy as np

from . import mvt

SERVER_KEYS = {"latence_s", "debit_ko_s", "coupure_s", "erreurs", "tronque", "chemins"}
KINDS = ("tilejson", "tuile", "relief", "liste")
DEM_PIXELS = 120            # pixels par degré du relief synthétique (Copernicus : 3 600)
CHUNK = 4096                # octets envoyés d'un coup quand le débit est plafonné


class ScenarioError(ValueError):
    """Scénario de réseau mal écrit : le message nomme la clé."""


def validate_server(spec: dict[str, Any]) -> dict[str, Any]:
    """Partie `serveur` d'un scénario, vérifiée ; renvoie une copie complétée."""
    if not isinstance(spec, dict):
        raise ScenarioError("serveur : objet attendu")
    unknown = set(spec) - SERVER_KEYS
    if unknown:
        raise ScenarioError(f"serveur : clé(s) inconnue(s) {sorted(unknown)} (connues : {sorted(SERVER_KEYS)})")
    out = dict(spec)
    lat = out.get("latence_s", 0.0)
    if isinstance(lat, (int, float)):
        lat = [float(lat), float(lat)]
    if not (isinstance(lat, list) and len(lat) == 2 and all(isinstance(v, (int, float)) and v >= 0 for v in lat)
            and lat[0] <= lat[1]):
        raise ScenarioError("serveur.latence_s : nombre positif ou [min, max] attendu")
    out["latence_s"] = [float(lat[0]), float(lat[1])]
    rate = out.get("debit_ko_s", 0)
    if not isinstance(rate, (int, float)) or rate < 0:
        raise ScenarioError("serveur.debit_ko_s : nombre positif attendu (0 : sans limite)")
    out["debit_ko_s"] = float(rate)
    cut = out.get("coupure_s")
    if cut is not None and not (isinstance(cut, list) and len(cut) == 2 and 0 <= cut[0] < cut[1]):
        raise ScenarioError("serveur.coupure_s : [début, fin] en secondes attendu")
    err = out.get("erreurs")
    if err is not None:
        codes = err.get("codes") if isinstance(err, dict) else None
        if not (isinstance(codes, list) and codes and all(isinstance(c, int) and 400 <= c < 600 for c in codes)):
            raise ScenarioError("serveur.erreurs.codes : liste de codes HTTP 4xx/5xx attendue")
        if not isinstance(err.get("par_chemin", 1), int) or err.get("par_chemin", 1) < 1:
            raise ScenarioError("serveur.erreurs.par_chemin : entier ≥ 1 attendu")
    cutoff = out.get("tronque")
    if cutoff is not None:
        if not isinstance(cutoff, dict) or not 0 < float(cutoff.get("part", 0.5)) < 1:
            raise ScenarioError("serveur.tronque.part : nombre entre 0 et 1 attendu")
        if not isinstance(cutoff.get("par_chemin", 1), int) or cutoff.get("par_chemin", 1) < 1:
            raise ScenarioError("serveur.tronque.par_chemin : entier ≥ 1 attendu")
    kinds = out.get("chemins", list(KINDS))
    if not (isinstance(kinds, list) and set(kinds) <= set(KINDS)):
        raise ScenarioError(f"serveur.chemins : sous-liste de {list(KINDS)} attendue")
    out["chemins"] = list(kinds)
    return out


def grid_tile(x: int, y: int) -> bytes:
    """Tuile synthétique : une ligne est-ouest, une ligne nord-sud (marge de 64 pixels) et un bâtiment."""
    def road(fid: int, pts: list[tuple[int, int]], cls: str) -> dict:
        return {"id": fid, "type": 2, "tags": {"class": cls}, "paths": [(pts, False)]}
    return mvt.encode_tile({
        "transportation": [road(1, [(-64, 2048), (4160, 2048)], "tertiary"),
                           road(2, [(2048, -64), (2048, 4160)], "minor")],
        "building": [{"id": 3, "type": 3, "tags": {"render_height": 9},
                      "paths": [([(2200, 2200), (2260, 2200), (2260, 2240), (2200, 2240)], True)]}],
    })


def relief_tif(lat_sw: int, lon_sw: int) -> bytes:
    """Tuile de relief GeoTIFF d'un degré : collines douces (100 à 400 m)."""
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    step = 1.0 / DEM_PIXELS
    lats = lat_sw + 1 - (np.arange(DEM_PIXELS) + 0.5) * step
    lons = lon_sw + (np.arange(DEM_PIXELS) + 0.5) * step
    la, lo = np.meshgrid(np.radians(lats), np.radians(lons), indexing="ij")
    z = (250.0 + 120.0 * np.sin(la * 300.0) * np.cos(lo * 220.0) + 30.0 * np.sin(lo * 900.0)).astype(np.float32)
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", height=DEM_PIXELS, width=DEM_PIXELS, count=1, dtype="float32",
                      crs="EPSG:4326", transform=from_origin(lon_sw, lat_sw + 1, step, step)) as ds:
            ds.write(z, 1)
        return mem.read()


class FakeTileServer:
    """Serveur dans un fil à part ; `url` est sa racine, `log` la liste des demandes."""

    def __init__(self, scenario: dict[str, Any] | None = None, seed: int = 0) -> None:
        self.scenario = validate_server(scenario or {})
        self.rng = random.Random(seed)
        self.lock = threading.Lock()
        self.log: list[dict[str, Any]] = []
        self.counts: dict[str, int] = {}
        self.errors_served = 0
        self.armed = False
        self.t0 = time.monotonic()
        self.dem_tiles: set[tuple[int, int]] = set()     # tuiles annoncées par tileList.txt
        self._tif: dict[tuple[int, int], bytes] = {}
        self._httpd: ThreadingHTTPServer | None = None

    # --- cycle de vie ---------------------------------------------------------------------------

    def start(self) -> "FakeTileServer":
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802 - nom imposé par http.server
                server._serve(self)

            def log_message(self, *_: Any) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        threading.Thread(target=self._httpd.serve_forever, name="faux-serveur-tuiles", daemon=True).start()
        return self

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def __enter__(self) -> "FakeTileServer":
        return self.start()

    def __exit__(self, *_: Any) -> None:
        self.stop()

    @property
    def url(self) -> str:
        assert self._httpd is not None, "serveur non démarré"
        return f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def arm(self) -> None:
        """Origine des instants du scénario (`coupure_s`, sans effet avant) et du journal : le début du trajet."""
        with self.lock:
            t0 = time.monotonic()
            for r in self.log:
                r["t"] = round(r["t"] - (t0 - self.t0), 3)
            self.t0 = t0
            self.armed = True

    def now(self) -> float:
        return time.monotonic() - self.t0

    # --- réponses -------------------------------------------------------------------------------

    def _body(self, path: str) -> tuple[str, bytes | None, str]:
        """(sorte, contenu ou None pour 404, type) du chemin demandé."""
        if path == "/planet":
            return "tilejson", json.dumps({"tiles": [f"{self.url}/t/{{z}}/{{x}}/{{y}}.pbf"],
                                           "minzoom": 0, "maxzoom": 14}).encode(), "application/json"
        m = re.fullmatch(r"/t/14/(\d+)/(\d+)\.pbf", path)
        if m:
            return "tuile", grid_tile(int(m.group(1)), int(m.group(2))), "application/x-protobuf"
        if path == "/dem/tileList.txt":
            names = "\n".join(_dem_name(la, lo) for la in range(-60, 61) for lo in range(-20, 31))
            return "liste", names.encode(), "text/plain"
        m = re.fullmatch(r"/dem/([^/]+)/([^/]+)\.tif", path)
        if m and m.group(1) == m.group(2):
            key = _dem_key(m.group(1))
            if key is None:
                return "relief", None, "image/tiff"
            with self.lock:
                if key not in self._tif:
                    self._tif[key] = relief_tif(*key)
                return "relief", self._tif[key], "image/tiff"
        return "autre", None, "text/plain"

    def _serve(self, h: BaseHTTPRequestHandler) -> None:
        path = h.path.split("?")[0]
        kind, body, ctype = self._body(path)
        sc = self.scenario
        with self.lock:
            n = self.counts[path] = self.counts.get(path, 0) + 1
            lo, hi = sc["latence_s"]
            delay = self.rng.uniform(lo, hi) if hi > lo else lo
        if delay > 0:
            time.sleep(delay)
        t = self.now()
        touched = kind in sc["chemins"]
        cut = sc.get("coupure_s")
        err = sc.get("erreurs")
        trunc = sc.get("tronque")
        if touched and cut and self.armed and cut[0] <= t < cut[1]:
            self._note(t, path, kind, "coupure", 0)
            h.close_connection = True
            return
        if body is None:
            self._note(t, path, kind, 404, 0)
            self._send(h, 404, b"absent", "text/plain")
            return
        if touched and err and n <= int(err.get("par_chemin", 1)):
            with self.lock:
                code = err["codes"][self.errors_served % len(err["codes"])]
                self.errors_served += 1
            self._note(t, path, kind, code, 0)
            self._send(h, code, f"erreur {code}".encode(), "text/plain")
            return
        if touched and trunc and n <= int(trunc.get("par_chemin", 1)):
            part = body[:max(1, int(len(body) * float(trunc.get("part", 0.5))))]
            self._note(t, path, kind, "tronque", len(part))
            self._send(h, 200, part, ctype, announced=len(body))
            h.close_connection = True
            return
        self._note(t, path, kind, 200, len(body))
        self._send(h, 200, body, ctype)

    def _send(self, h: BaseHTTPRequestHandler, code: int, body: bytes, ctype: str,
              announced: int | None = None) -> None:
        try:
            h.send_response(code)
            h.send_header("Content-Type", ctype)
            h.send_header("Content-Length", str(announced if announced is not None else len(body)))
            if code == 429:
                h.send_header("Retry-After", "1")
            h.end_headers()
            rate = self.scenario["debit_ko_s"] * 1000.0
            if rate <= 0:
                h.wfile.write(body)
            else:
                for i in range(0, len(body), CHUNK):
                    h.wfile.write(body[i:i + CHUNK])
                    h.wfile.flush()
                    time.sleep(min(CHUNK, len(body) - i) / rate)
            h.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _note(self, t: float, path: str, kind: str, outcome: Any, size: int) -> None:
        with self.lock:
            self.log.append({"t": round(t, 3), "path": path, "kind": kind, "outcome": outcome, "bytes": size})


def _dem_name(lat_sw: int, lon_sw: int) -> str:
    from ..elevation import copernicus_tile_name
    return copernicus_tile_name(lat_sw, lon_sw)


def _dem_key(name: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"Copernicus_DSM_COG_10_([NS])(\d+)_00_([EW])(\d+)_00_DEM", name)
    if not m:
        return None
    lat = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
    lon = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
    return lat, lon

