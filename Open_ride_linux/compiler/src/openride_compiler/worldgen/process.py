"""Processus `openride-worldgen` (lot W8, `docs/contracts/worldgen_v1.md`, plan §3.2, §3.5, §3.6 et §5).

Le core lance `openride-worldgen --session <dossier> --config <config.toml>` et dialogue en lignes
JSON (entrée standard → `open`, `progress`, `choose`, `close` ; sortie standard → `status`,
`revision`, `error`, `closed`). Le journal, en français, va sur la sortie d'erreur.

Organisation :

- un fil lit l'entrée standard et range les lignes dans une file ; tout le calcul se fait dans le
  fil principal, qui traite les messages en priorité puis, quand il n'en a pas, un carré à la fois
  (`SquareQueue`) : la route engagée n'attend jamais un carré ;
- tout est calculé dans le repère de zone (W7 : x = E, z = −N) ; la route, les carrefours et les
  amorces sont convertis dans le repère de la séance (origine (E0, N0) sur la grille de 5 km) par
  une simple soustraction au moment de l'écriture ;
- la route engagée est une suite d'étapes (arête, sens, profil) ; la première part du point de
  départ accroché à l'arête la plus proche ; elle est prolongée par le navigateur (W6) dès qu'il
  reste moins de `horizon_m` devant le cycliste, et remplacée après un carrefour par la branche
  choisie avant `lock_s_m` ;
- relief en avance : la tuile Copernicus voisine est téléchargée dans un fil dès que la route
  engagée passe à moins de 10 km de son bord ; hors ligne, seules les arêtes dont le relief est
  sur le PC sont engagées (sinon demi-tour), et la séance ne s'arrête jamais pour attendre ;
- tuiles vectorielles en échec (X28) : la cellule reste « incomplète », ses tuiles sont redemandées
  après leur recul à chaque `progress`, et le graphe est complété dès qu'elles arrivent.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import resource
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO

import numpy as np

from .. import __version__
from .. import constants as C
from ..cache import Downloader, Log
from ..elevation import COPERNICUS_BASE_URL, CopernicusGlo30Provider, ElevationProvider, SyntheticProvider, copernicus_tile_name
from ..errors import CompileError
from ..pipeline import sample_positions
from .edge_profile import EdgeProfile, NodeAltitudes, concat, edge_profile, split_parts
from .graph import Branch, Edge, RoadGraph
from .navigator import Navigator
from .osmdb import OsmDb
from .squares import FarKey, SquareKey, SquareQueue, generate_far, generate_square, lonlat_bbox, zone_frame
from .store import WorldCache, read_open_world_config

GRID_M = 5000                 # origine de séance et cellules de chargement du graphe
GRAPH_RADIUS_M = 3000.0       # graphe chargé autour de chaque carrefour avant un choix
SNAP_MAX_M = 200.0
SQUARES_RADIUS_M = 1500.0
FAR_RADIUS_M = 12_000.0
RELIEF_AHEAD_M = 10_000.0
EXTEND_MARGIN_M = 1000.0      # prolongation d'un coup au-delà de l'horizon (moins de révisions)
REWRITE_BACK_M = 100.0        # lissage du profil : la partie qui contient s − 100 m est réécrite
EVICT_EVERY_S = 60.0
CLOSE_TIMEOUT_S = 5.0
MAX_BRANCHES = 4
OPEN_TILES_WAIT_S = 20.0      # départ sans extrait : tuiles en échec redemandées pendant au plus 20 s
PROGRESS_FAKE_DT_S = 0.5


def _zone_of(lat: float, lon: float) -> str:
    from ..frame import utm_zone_of
    number, band, _south = utm_zone_of(lat, lon)
    return f"{number}{band}"


# --- données ----------------------------------------------------------------------------------

def find_region_db(cache: WorldCache, lat: float, lon: float) -> OsmDb | None:
    """Base régionale du cache (W3) dont l'emprise contient le point."""
    for path in sorted((cache.root / "brut" / "osm").glob("*.sqlite")):
        if path.stem == "tuiles":                       # base des tuiles vectorielles (W13) : à part
            continue
        try:
            db = OsmDb(path)
        except CompileError:
            continue
        try:
            lon0, lat0, lon1, lat1 = map(float, db.meta.get("bbox", "").split(","))
        except ValueError:
            db.close()
            continue
        if lon0 <= lon <= lon1 and lat0 <= lat <= lat1:
            return db
        db.close()
    return None


def relief_has(provider: ElevationProvider, lat: float, lon: float) -> bool:
    """Le relief de ce point est-il sur le PC (sans réseau) ?"""
    has = getattr(provider, "has_data", None)
    if has is not None:
        return bool(has(lat, lon))
    if isinstance(provider, CopernicusGlo30Provider):
        la, lo = math.floor(lat), math.floor(lon)
        if provider.tile_path(la, lo).is_file():
            return True
        listing = provider.dir / "tileList.txt"            # tuile absente de la liste : la mer
        return listing.is_file() and copernicus_tile_name(la, lo) not in listing.read_text()
    return True


# --- route engagée ----------------------------------------------------------------------------

@dataclass
class Leg:
    edge_id: str
    forward: bool
    to_node: int
    profile: EdgeProfile          # orienté dans le sens de marche, repère de zone
    s0: float = 0.0

    @property
    def key(self) -> tuple[str, bool]:
        return self.edge_id, self.forward

    @property
    def s1(self) -> float:
        return self.s0 + self.profile.length_m


def tail_profile(p: EdgeProfile, t: float) -> EdgeProfile:
    """Fin du profil à partir de l'abscisse `t` (départ au milieu d'une arête)."""
    s = sample_positions(p.length_m - t)
    cols = {k: np.interp(t + s, p.s, getattr(p, k)) for k in ("x", "z", "alt_m", "grade_pct", "lat", "lon")}
    heading = np.interp(t + s, p.s, np.unwrap(np.radians(p.heading_deg)))
    return EdgeProfile(p.edge_id, s, cols["x"], cols["z"], cols["alt_m"], cols["grade_pct"],
                       np.degrees(heading) % 360.0, cols["lat"], cols["lon"], 0, p.versions, p.forward)


def project_on(points: list[tuple[float, float]], x: float, z: float) -> tuple[float, float, float]:
    """(distance, abscisse le long de la polyligne, cap du segment) du point le plus proche."""
    p = np.asarray(points, dtype=float)
    a, b = p[:-1], p[1:]
    v = b - a
    ll = (v ** 2).sum(axis=1)
    t = np.clip(((x - a[:, 0]) * v[:, 0] + (z - a[:, 1]) * v[:, 1]) / np.where(ll > 0, ll, 1.0), 0.0, 1.0)
    cx, cz = a[:, 0] + t * v[:, 0], a[:, 1] + t * v[:, 1]
    d = np.hypot(cx - x, cz - z)
    k = int(np.argmin(d))
    cum = np.concatenate([[0.0], np.cumsum(np.sqrt(ll))])
    heading = math.degrees(math.atan2(v[k, 0], -v[k, 1])) % 360.0
    return float(d[k]), float(cum[k] + t[k] * math.sqrt(ll[k])), heading


@dataclass
class Junction:
    id: str
    leg: int                      # carrefour au bout de l'étape `leg`
    node: int
    s_m: float
    branches: list[Branch]
    default: int
    previews: list[dict[str, Any]] = field(default_factory=list)


class WorldSession:
    """Une séance de monde ouvert : état, calculs et fichiers ; aucun accès à l'entrée standard."""

    def __init__(self, cache: WorldCache, provider: ElevationProvider, send: Callable[[dict], None],
                 config: dict[str, Any] | None = None, session_dir: Path | None = None,
                 network: bool = True, clock: Callable[[], float] = time.time, log: Log | None = None,
                 db: OsmDb | None = None) -> None:
        cfg = dict(config or {})
        self.horizon_m = float(cfg.get("horizon_m", 3000.0))
        self.offer_m = float(cfg.get("offer_m", 300.0))
        self.lock_m = float(cfg.get("lock_m", 30.0))
        self.preview_m = float(cfg.get("preview_m", 500.0))
        self.cache = cache
        self.provider = provider
        self.send = send
        self.network_cfg = network
        self.network = network
        self.clock = clock
        self.log = log or (lambda m: print(m, file=sys.stderr, flush=True))
        self.session_dir = Path(session_dir) if session_dir else None
        self._db = db
        self.db: OsmDb | None = None
        self.tiles = None                 # TileSource (W13) quand il n'y a pas d'extrait régional
        self.tile_net = None              # accès HTTP des tuiles (doublure dans les tests)
        self.tilejson_url: str | None = None   # autre serveur de tuiles (`--tiles-url`, X28)
        self.partial_cells: dict[tuple[int, int], tuple[float, float, float, float]] = {}
        self.opened = False
        self.closed = False
        self.legs: list[Leg] = []
        self.s_m = 0.0
        self.rev = 0
        self.profiles: dict[str, EdgeProfile] = {}
        self.nav_default: dict[int, tuple[str, bool]] = {}
        self.user_choice: dict[int, tuple[str, bool]] = {}
        self.junctions: dict[str, Junction] = {}
        self._preview_cache: dict[tuple, dict[str, Any]] = {}
        self.cells: set[tuple[int, int]] = set()
        self.queue = SquareQueue()
        self.ready: set[SquareKey] = set()
        self.failed: set[SquareKey] = set()
        self.far_ready: set[FarKey] = set()
        self.far_wanted: list[FarKey] = []
        self.dirty_tiles = False
        self.offline_reported = False
        self.relief_jobs: dict[str, threading.Thread] = {}
        self.stats = {"squares_generated": 0, "squares_cached": 0, "far_generated": 0, "downloads": 0,
                      "bad_lines": 0}
        self._last_evict = -math.inf
        self.data_state = "cached"

    # --- messages -----------------------------------------------------------------------------

    def handle(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        try:
            if kind == "open":
                self.open(msg)
            elif kind == "progress":
                self.progress(float(msg["s_m"]), float(msg.get("v_mps", 0.0)))
            elif kind == "choose":
                self.choose(str(msg["junction_id"]), int(msg["branch"]))
            elif kind == "close":
                self.close()
            else:
                self.stats["bad_lines"] += 1
                self.log(f"message inconnu ignoré : {kind!r}")
        except (KeyError, TypeError, ValueError) as exc:
            self.stats["bad_lines"] += 1
            self.log(f"message {kind!r} illisible ignoré : {exc}")
        except Exception as exc:  # noqa: BLE001 - le processus ne doit pas tomber sur une séance
            self.log(f"erreur interne sur {kind!r} : {exc!r}")
            self.send({"type": "error", "code": "internal", "message": str(exc)})

    def status(self, phase: str, message: str = "", data: str | None = None) -> None:
        needed = len(self.ready) + len(self.queue)
        self.send({"type": "status", "phase": phase, "done_bytes": 0, "total_bytes": None,
                   "squares_ready": len(self.ready), "squares_needed": needed, "message": message,
                   "data": data or self.data_state})

    # --- ouverture ----------------------------------------------------------------------------

    def open(self, msg: dict[str, Any]) -> None:
        if self.opened:
            self.log("open reçu deux fois : ignoré")
            return
        lat, lon = float(msg["lat"]), float(msg["lon"])
        self.network = bool(msg.get("network", True)) and self.network_cfg
        if not self.network:
            self.data_state = "offline"
        self.zone = _zone_of(lat, lon)
        self.frame = zone_frame(self.zone)
        x, z = (float(v[0]) for v in self.frame.to_xz(np.array([lat]), np.array([lon])))
        self.e0 = float(round(x / GRID_M) * GRID_M)
        self.n0 = float(round(-z / GRID_M) * GRID_M)
        self.status("osm", "recherche de la région")
        self.db = self._db or find_region_db(self.cache, lat, lon)
        if self.db is None:
            self.db = self._open_tiles(lat, lon)
        if self.db is None:
            self._unavailable("aucune région OpenStreetMap du cache ne contient le départ "
                              "(openride-compiler region-add) et aucune tuile vectorielle n'est disponible")
            return
        self.status("dem", "relief du départ", "cached" if self.network else "offline")
        self.node_alt = NodeAltitudes(self.provider, self.frame)
        self.graph = RoadGraph(self.frame)
        self._ensure_graph(x, z)
        if not self._snap_start(x, z, float(msg.get("heading_deg", 0.0))):
            return
        mode = str(msg.get("nav") or "ride")
        target = msg.get("target")
        target_xz = None
        if target:
            tx, tz = self.frame.to_xz(np.array([float(target["lat"])]), np.array([float(target["lon"])]))
            target_xz = (float(tx[0]), float(tz[0]))
        loop_km = msg.get("loop_km")
        self.nav = Navigator(self.graph, mode, (x, z), float(msg.get("heading_deg", 0.0)), int(msg.get("seed", 0)),
                             target_xz=target_xz, loop_m=float(loop_km) * 1000.0 if loop_km else None,
                             allowed=None if self.network else self._edge_available)
        self._make_session_dir()
        self._extend()
        self._write_manifest()
        self._request_squares()
        self._request_far()
        total = len(self.queue)
        self.status("generate", f"{total} carré(s) à préparer")
        while self.work(publish=False):
            if len(self.ready) % 8 == 0:
                self.status("generate")
        self.opened = True
        self.status("ready")
        self._publish(0)

    def _open_tiles(self, lat: float, lon: float) -> OsmDb | None:
        """Sans extrait régional : tuiles vectorielles OpenFreeMap (W13) versées dans `tuiles.sqlite`."""
        from .vector_tiles import TileSource
        self.status("tiles", "tuiles vectorielles du départ", "downloading" if self.network else "offline")
        self.tiles = TileSource(self.cache, self.tile_net, self.network, self.clock, self.log, self.tilejson_url)
        d = 0.02
        if self.tiles.ensure((lon - d * 1.5, lat - d, lon + d * 1.5, lat + d), wait_s=OPEN_TILES_WAIT_S) == 0:
            return None
        return OsmDb(self.tiles.db_path)

    def _unavailable(self, message: str) -> None:
        self.log(message)
        self.send({"type": "error", "code": "world_unavailable", "message": message})

    def _snap_start(self, x: float, z: float, heading: float) -> bool:
        best = None
        for e in self.graph.edges.values():
            d, t, h = project_on(e.points, x, z)
            if best is None or (d, e.id) < (best[0], best[1].id):
                best = (d, e, t, h)
        if best is None or best[0] > SNAP_MAX_M:
            self._unavailable(f"aucune route admise à moins de {SNAP_MAX_M:.0f} m du départ")
            return False
        _, e, t, h = best
        dev = abs((heading - h + 180.0) % 360.0 - 180.0)
        forward = dev <= 90.0
        if not e.allows(forward):
            forward = not forward
        p = self._profile(e, forward)
        tt = t if forward else e.length_m - t
        if p.length_m - tt >= C.DS_M:
            p = tail_profile(p, tt)
        self.legs = [Leg(e.id, forward, e.b if forward else e.a, p, 0.0)]
        self.log(f"départ accroché à l'arête {e.id} ({best[0]:.0f} m), sens {'direct' if forward else 'inverse'}")
        return True

    def _make_session_dir(self) -> None:
        if self.session_dir is None:
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(self.clock()))
            self.session_dir = self.cache.sessions_dir() / f"ow-{stamp}.world"
        for sub in ("route", "terrain/near", "terrain/far", "buildings", "vegetation", "water", "poi"):
            (self.session_dir / sub).mkdir(parents=True, exist_ok=True)

    def _write_manifest(self) -> None:
        lat, lon = self.frame.to_latlon(np.array([self.e0]), np.array([-self.n0]))
        alt = float(np.nan_to_num(self.provider.elevations(lat, lon)[0]))
        n = len(sample_positions(self.length_m))
        manifest = {
            "format": C.FORMAT_NAME, "format_version": C.FORMAT_VERSION, "name": "Monde ouvert",
            "created": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.clock())),
            "compiler": {"name": "openride-worldgen", "version": __version__},
            "origin": {"lat": round(float(lat[0]), 7), "lon": round(float(lon[0]), 7), "alt_m": round(alt, 2),
                       "utm_zone": self.zone},
            "projection": "utm",
            "route": {"present": True, "version": C.ROUTE_VERSION, "file": "route/", "length_m": round(self.length_m, 3),
                      "ds_m": C.DS_M, "n": n, "type": "open", "alt_source": getattr(self.provider, "name", "inconnu")},
            "layers": {
                "terrain": {"present": True, "version": C.TERRAIN_VERSION,
                            "sources": [getattr(self.provider, "name", "inconnu")],
                            "near_cell_m": C.NEAR_CELL_M, "far_cell_m": C.FAR_CELL_M,
                            "road_half_width_m": C.ROAD_HALF_WIDTH_M},
                "buildings": {"present": True, "version": C.BUILDINGS_VERSION},
                "vegetation": {"present": True, "version": C.VEGETATION_VERSION, "source": "osm"},
                "poi": {"present": True, "version": C.POI_VERSION},
                "water": {"present": True, "version": C.WATER_VERSION},
            },
            "live": True, "origin_kind": "utm_grid",
            "grid": {"near_m": 1000, "far_m": 5000, "e0": self.e0, "n0": self.n0},
        }
        _write_json(self.session_dir / "manifest.json", manifest, indent=2)

    # --- graphe et profils --------------------------------------------------------------------

    def _ensure_graph(self, x: float, z: float, radius: float = GRAPH_RADIUS_M) -> None:
        """Charge les cellules de 5 km du graphe à moins de `radius` du point (repère de zone)."""
        assert self.db is not None
        for cx in range(math.floor((x - radius) / GRID_M), math.floor((x + radius) / GRID_M) + 1):
            for cz in range(math.floor((z - radius) / GRID_M), math.floor((z + radius) / GRID_M) + 1):
                if (cx, cz) in self.cells:
                    continue
                self.cells.add((cx, cz))
                bbox = lonlat_bbox(self.frame, cx * GRID_M, cz * GRID_M, (cx + 1) * GRID_M, (cz + 1) * GRID_M)
                if self.tiles is not None:
                    self.tiles.ensure(bbox)
                    if self.tiles.missing(bbox):
                        self.partial_cells[(cx, cz)] = bbox
                self.graph.extend(self.db, bbox)

    def _retry_tiles(self) -> None:
        """Cellules incomplètes : tuiles redemandées une fois leur recul écoulé, graphe complété (X28)."""
        if self.tiles is None or not self.network:
            return
        for cell, bbox in list(self.partial_cells.items()):
            left = self.tiles.missing(bbox)
            if left and not any(self.tiles.due(k) for k in left):
                continue
            self.tiles.ensure(bbox)
            now_left = self.tiles.missing(bbox)
            if not now_left:
                del self.partial_cells[cell]
            if len(now_left) < len(left):
                self.graph.extend(self.db, bbox)

    def _ensure_around_node(self, node: int) -> None:
        n = self.graph.nodes[node]
        self._ensure_graph(n.x, n.z)

    def _profile(self, e: Edge, forward: bool = True) -> EdgeProfile:
        p = self.profiles.get(e.id)
        if p is None:
            p = self.profiles[e.id] = edge_profile(e, self.provider, self.frame, self.node_alt)
        return p if forward else p.reversed()

    def _edge_available(self, e: Edge) -> bool:
        pts = e.points if len(e.points) <= 3 else [e.points[0], e.points[len(e.points) // 2], e.points[-1]]
        xs = np.array([p[0] for p in pts])
        zs = np.array([p[1] for p in pts])
        lat, lon = self.frame.to_latlon(xs, zs)
        ok = all(relief_has(self.provider, float(a), float(b)) for a, b in zip(lat, lon))
        if not ok and not self.offline_reported:
            self.offline_reported = True
            self.data_state = "offline"
            self.log("hors ligne : la route reste dans la zone dont le relief est sur le PC")
            if self.opened:
                self.status("ready", "hors ligne : route limitée à la zone en cache", "offline")
        return ok

    # --- route ----------------------------------------------------------------------------------

    @property
    def length_m(self) -> float:
        return self.legs[-1].s1 if self.legs else 0.0

    def _history(self, upto: int) -> list[str]:
        return [leg.edge_id for leg in self.legs[:upto + 1]]

    def _append_leg(self, edge_id: str, forward: bool, to_node: int) -> None:
        e = self.graph.edges[edge_id]
        self.legs.append(Leg(edge_id, forward, to_node, self._profile(e, forward), self.length_m))

    def _extend(self) -> bool:
        """Prolonge la route engagée jusqu'à l'horizon (plus une marge) ; vrai si elle a changé."""
        if self.length_m - self.s_m >= self.horizon_m:
            return False
        goal = self.s_m + self.horizon_m + EXTEND_MARGIN_M
        while self.length_m < goal:
            i = len(self.legs) - 1
            last = self.legs[i]
            self._ensure_around_node(last.to_node)
            c = self.nav.choose(last.to_node, last.edge_id, self._history(i))
            self.nav_default[i] = (c.branch_edge_id, c.forward)
            if c.phase == "u_turn" and not self.graph.edges[c.branch_edge_id].allows(c.forward):
                self.data_state = "missing"
                self.status("ready", "plus de route connue", "missing")
                break
            self._append_leg(c.branch_edge_id, c.forward, c.to_node)
        return True

    def _route_columns(self) -> dict[str, Any]:
        route = concat([leg.profile for leg in self.legs])
        route["x"] = route["x"] - self.e0
        route["z"] = route["z"] + self.n0
        return route

    # --- carrefours -----------------------------------------------------------------------------

    def _branches_at(self, i: int) -> list[Branch]:
        leg = self.legs[i]
        arr = self.nav.arriving_heading(leg.to_node, leg.edge_id)
        brs = self.graph.out_edges(leg.to_node, arr, leg.edge_id)
        if not self.network:
            brs = [b for b in brs if self._edge_available(b.edge)]
        return brs

    def _junctions(self) -> list[Junction]:
        out = []
        for i in range(len(self.legs) - 1):
            leg = self.legs[i]
            if leg.s1 < self.s_m - self.lock_m or leg.s1 > self.s_m + self.horizon_m:
                continue
            brs = self._branches_at(i)
            if len(brs) < 2:
                continue
            keys = [(b.edge.id, b.forward) for b in brs]
            must = {self.legs[i + 1].key, self.nav_default.get(i, self.legs[i + 1].key)}
            if len(brs) > MAX_BRANCHES:
                keep = [k for k in range(len(brs)) if keys[k] in must]
                keep += [k for k in range(len(brs)) if k not in keep][:MAX_BRANCHES - len(keep)]
                brs = [brs[k] for k in sorted(keep)]
                keys = [keys[k] for k in sorted(keep)]
            default_key = self.nav_default.get(i, self.legs[i + 1].key)
            default = keys.index(default_key) if default_key in keys else keys.index(self.legs[i + 1].key)
            j = Junction(f"j{leg.to_node}-{i}", i, leg.to_node, leg.s1, brs, default)
            j.previews = [self._preview(i, b) for b in brs]
            out.append(j)
        return out

    def _preview(self, i: int, br: Branch) -> dict[str, Any]:
        """Amorce de 500 m de la branche (navigateur par défaut au-delà), repère de séance."""
        key = (i, tuple(self._history(i)), br.edge.id, br.forward)
        if key in self._preview_cache:
            return self._preview_cache[key]
        profiles = [self._profile(br.edge, br.forward)]
        history = self._history(i) + [br.edge.id]
        node, edge_id, total = br.to_node, br.edge.id, profiles[0].length_m
        while total < self.preview_m:
            self._ensure_around_node(node)
            c = self.nav.choose(node, edge_id, history)
            p = self._profile(self.graph.edges[c.branch_edge_id], c.forward)
            profiles.append(p)
            history.append(c.branch_edge_id)
            node, edge_id, total = c.to_node, c.branch_edge_id, total + p.length_m
        joined = concat(profiles)
        keep = joined["s"] <= self.preview_m + 1e-6
        x, y, z = joined["x"][keep] - self.e0, joined["alt_m"][keep], joined["z"][keep] + self.n0
        s_end = float(joined["s"][keep][-1])
        out = {"x": [round(float(v), 2) for v in x], "y": [round(float(v), 2) for v in y],
               "z": [round(float(v), 2) for v in z],
               "grade_pct_500m": round(float((y[-1] - y[0]) / s_end * 100.0) if s_end > 0 else 0.0, 2)}
        self._preview_cache[key] = out
        return out

    def _junctions_payload(self, junctions: list[Junction]) -> dict[str, Any]:
        items = []
        for j in junctions:
            chosen_key = self.legs[j.leg + 1].key
            keys = [(b.edge.id, b.forward) for b in j.branches]
            items.append({
                "id": j.id, "s_m": round(j.s_m, 2),
                "x": round(self.graph.nodes[j.node].x - self.e0, 2), "z": round(self.graph.nodes[j.node].z + self.n0, 2),
                "lock_s_m": round(j.s_m - self.lock_m, 2), "default": j.default,
                "chosen": keys.index(chosen_key) if chosen_key in keys else j.default,
                "locked": self.s_m >= j.s_m - self.lock_m,
                "branches": [{
                    "index": k, "heading_deg": round(b.heading_deg % 360.0, 1), "angle_deg": round(b.angle_deg, 1),
                    "road_class": b.edge.road_class, "grade_pct_500m": pv["grade_pct_500m"],
                    "dead_end": bool(self.graph.dead_end(b.edge, forward=b.forward)),
                    "preview": {"x": pv["x"], "y": pv["y"], "z": pv["z"]}}
                    for k, (b, pv) in enumerate(zip(j.branches, j.previews))]})
        return {"version": "1.0", "revision": self.rev, "junctions": items}

    # --- publication ----------------------------------------------------------------------------

    def _publish(self, changed_from_part: int) -> None:
        """Parties de route, carrefours, puis `live.json` ; enfin le message `revision`."""
        self.rev += 1
        route = self._route_columns()
        parts = split_parts(route)
        for k in range(changed_from_part, len(parts)):
            _write_json(self.session_dir / "route" / f"part_{k}.json", parts[k])
        junctions = self._junctions()
        self.junctions = {j.id: j for j in junctions}
        _write_json(self.session_dir / "junctions.json", self._junctions_payload(junctions))
        self._write_live(len(parts), changed_from_part)
        for stale in (self.session_dir / "route").glob("part_*.json"):
            try:
                if int(stale.stem.split("_")[1]) >= len(parts):
                    stale.unlink()
            except (ValueError, OSError):
                pass
        self.dirty_tiles = False
        self.send({"type": "revision", "rev": self.rev, "length_m": round(self.length_m, 2),
                   "changed_from_part": changed_from_part, "junctions": len(junctions)})

    def _write_live(self, parts: int, changed_from_part: int) -> None:
        near = sorted([k.ix - int(self.e0) // 1000, int(self.n0) // 1000 - k.i_n - 1] for k in self.ready)
        far = sorted([k.ix - int(self.e0) // 5000, int(self.n0) // 5000 - k.i_n - 1] for k in self.far_ready)
        state = {"downloading": "downloading", "offline": "offline", "missing": "missing"}.get(self.data_state, "ok")
        _write_json(self.session_dir / "live.json", {
            "version": "1.0", "revision": self.rev,
            "route": {"parts": parts, "length_m": round(self.length_m, 2), "changed_from_part": changed_from_part},
            "tiles": {"near": near, "far": far}, "layer_tiles": near, "status": state})

    # --- progression et choix -------------------------------------------------------------------

    def progress(self, s_m: float, v_mps: float = 0.0) -> None:
        if not self.opened:
            return
        self.s_m = max(0.0, s_m)
        self._retry_tiles()
        old = self.length_m
        if self._extend():
            self._request_squares()
            self._request_far()
            self._prefetch_relief()
            self._publish(_part_of(old - REWRITE_BACK_M))
        self._maybe_evict()

    def choose(self, junction_id: str, branch: int) -> None:
        j = self.junctions.get(junction_id)
        if j is None or not 0 <= branch < len(j.branches):
            self.send({"type": "error", "code": "unknown_junction", "message": f"carrefour inconnu : {junction_id}"})
            return
        if self.s_m >= j.s_m - self.lock_m:
            self.send({"type": "error", "code": "branch_locked",
                       "message": f"choix verrouillé à {self.lock_m:.0f} m du carrefour"})
            return
        br = j.branches[branch]
        self.user_choice[j.leg] = (br.edge.id, br.forward)
        if self.legs[j.leg + 1].key == (br.edge.id, br.forward):
            self._publish(_part_of(j.s_m - self.lock_m))
            return
        del self.legs[j.leg + 1:]
        for k in [k for k in self.nav_default if k > j.leg]:
            del self.nav_default[k]
        self._preview_cache = {k: v for k, v in self._preview_cache.items() if k[0] <= j.leg}
        self._append_leg(br.edge.id, br.forward, br.to_node)
        self._extend()
        self._request_squares()
        self._publish(_part_of(j.s_m - REWRITE_BACK_M))

    # --- carrés et tuiles lointaines ------------------------------------------------------------

    def _route_points_ahead(self, step_m: float = 100.0) -> Iterable[tuple[float, float, float]]:
        for leg in self.legs:
            if leg.s1 < self.s_m - 500.0:
                continue
            p = leg.profile
            for k in range(0, len(p.s), int(step_m // C.DS_M)):
                yield leg.s0 + float(p.s[k]), float(p.x[k]), float(p.z[k])
            yield leg.s1, float(p.x[-1]), float(p.z[-1])

    def _rider_xz(self) -> tuple[float, float]:
        for leg in self.legs:
            if leg.s1 >= self.s_m:
                t = self.s_m - leg.s0
                return float(np.interp(t, leg.profile.s, leg.profile.x)), float(np.interp(t, leg.profile.s, leg.profile.z))
        return float(self.legs[-1].profile.x[-1]), float(self.legs[-1].profile.z[-1])

    def _request_squares(self) -> None:
        rx, rz = self._rider_xz()
        r = SQUARES_RADIUS_M
        for s, x, z in self._route_points_ahead():
            for ix in range(math.floor((x - r) / 1000), math.floor((x + r) / 1000) + 1):
                for jn in range(math.floor((-z - r) / 1000), math.floor((-z + r) / 1000) + 1):
                    key = SquareKey(self.zone, ix, jn)
                    if key in self.ready or key in self.failed:
                        continue
                    x0, z0 = key.corner
                    dx = max(x0 - x, 0.0, x - (x0 + 1000))
                    dz = max(z0 - z, 0.0, z - (z0 + 1000))
                    if math.hypot(dx, dz) > r:
                        continue
                    cx, cz = x0 + 500.0, z0 + 500.0
                    self.queue.request(key, math.hypot(cx - rx, cz - rz), max(0.0, s - self.s_m))
        self.queue.cancel_beyond(SQUARES_RADIUS_M + 3000.0)

    def _request_far(self) -> None:
        rx, rz = self._rider_xz()
        r = FAR_RADIUS_M
        wanted = []
        for ix in range(math.floor((rx - r) / 5000), math.floor((rx + r) / 5000) + 1):
            for jn in range(math.floor((-rz - r) / 5000), math.floor((-rz + r) / 5000) + 1):
                key = FarKey(self.zone, ix, jn)
                x0, z0 = key.corner
                dx = max(x0 - rx, 0.0, rx - (x0 + 5000))
                dz = max(z0 - rz, 0.0, rz - (z0 + 5000))
                if math.hypot(dx, dz) <= r and key not in self.far_ready:
                    wanted.append((math.hypot(x0 + 2500 - rx, z0 + 2500 - rz), key))
        self.far_wanted = [k for _, k in sorted(wanted)]

    def has_work(self) -> bool:
        return self.opened and (len(self.queue) > 0 or bool(self.far_wanted) or self.dirty_tiles)

    def work(self, publish: bool = True) -> bool:
        """Une unité de travail de fond (un carré, une tuile lointaine ou une publication)."""
        assert self.db is not None
        key = self.queue.pop()
        if key is not None:
            if not self.network and not relief_has(self.provider, *self._latlon_of_square(key)):
                self.failed.add(key)
                return True
            had = self.cache.is_valid(key.cache_key, _square_versions(self.db, self.provider))
            try:
                generate_square(key, self.db, self.provider, self.cache)
            except CompileError as exc:
                self.log(f"carré {key.ix}_{key.i_n} non généré : {exc}")
                self.failed.add(key)
                return True
            self.stats["squares_cached" if had else "squares_generated"] += 1
            ix, iz = key.ix - int(self.e0) // 1000, int(self.n0) // 1000 - key.i_n - 1
            self.cache.link_square(self.session_dir, self.zone, self.e0, self.n0, ix, iz)
            self.ready.add(key)
            self.dirty_tiles = True
            return True
        if self.far_wanted:
            fk = self.far_wanted.pop(0)
            if not self.network and not relief_has(self.provider, *self._latlon_of_square(fk)):
                return True
            had = self.cache.get(fk.cache_key) is not None
            try:
                generate_far(fk, self.provider, self.cache)
            except CompileError as exc:
                self.log(f"tuile lointaine {fk.ix}_{fk.i_n} non générée : {exc}")
                return True
            if not had:
                self.stats["far_generated"] += 1
            fx, fz = fk.ix - int(self.e0) // 5000, int(self.n0) // 5000 - fk.i_n - 1
            self.cache.link_far(self.session_dir, self.zone, self.e0, self.n0, fx, fz)
            self.far_ready.add(fk)
            self.dirty_tiles = True
            return True
        if self.dirty_tiles and publish:
            self._publish(_part_of(self.length_m))
            return True
        return False

    def _latlon_of_square(self, key: SquareKey) -> tuple[float, float]:
        e, n = key.center_en()
        lat, lon = self.frame.to_latlon(np.array([e]), np.array([-n]))
        return float(lat[0]), float(lon[0])

    # --- relief en avance -----------------------------------------------------------------------

    def _prefetch_relief(self) -> None:
        if not self.network or not isinstance(self.provider, CopernicusGlo30Provider):
            return
        end = self.legs[-1].profile
        lat, lon = float(end.lat[-1]), float(end.lon[-1])
        dlat = RELIEF_AHEAD_M / 111_000.0
        dlon = dlat / max(0.1, math.cos(math.radians(lat)))
        for la in {math.floor(lat - dlat), math.floor(lat), math.floor(lat + dlat)}:
            for lo in {math.floor(lon - dlon), math.floor(lon), math.floor(lon + dlon)}:
                name = copernicus_tile_name(la, lo)
                if name in self.relief_jobs or self.provider.tile_path(la, lo).is_file():
                    continue
                th = threading.Thread(target=self._download_tile, args=(la, lo), daemon=True)
                self.relief_jobs[name] = th
                self.log(f"relief en avance : {name}")
                th.start()

    def _download_tile(self, la: int, lo: int) -> None:
        prov = self.provider
        assert isinstance(prov, CopernicusGlo30Provider)
        name = copernicus_tile_name(la, lo)
        dl = Downloader(log=self.log)
        try:
            listing = dl.fetch(f"{prov.base_url}/tileList.txt", prov.dir / "tileList.txt", "liste des tuiles")
            if name in listing.read_text():
                dl.fetch(f"{prov.base_url}/{name}/{name}.tif", prov.tile_path(la, lo), name)
                self.stats["downloads"] += 1
        except Exception as exc:  # noqa: BLE001 - réessayé au prochain passage
            self.log(f"relief {name} non téléchargé : {exc}")
            self.relief_jobs.pop(name, None)

    # --- cache et fermeture ---------------------------------------------------------------------

    def in_use(self) -> set[str]:
        return {k.cache_key for k in self.ready} | {k.cache_key for k in self.far_ready}

    def _maybe_evict(self) -> None:
        now = self.clock()
        if now - self._last_evict < EVICT_EVERY_S:
            return
        self._last_evict = now
        removed = self.cache.evict(in_use=self.in_use())
        if removed:
            self.log(f"cache : {len(removed)} entrée(s) supprimée(s)")

    def close(self) -> None:
        deadline = time.monotonic() + CLOSE_TIMEOUT_S
        for th in list(self.relief_jobs.values()):
            th.join(timeout=max(0.0, deadline - time.monotonic()))
        for key in self.in_use():
            self.cache.touch(key)
        downloads = self.stats["downloads"] + (self.tiles.downloads if self.tiles is not None else 0)
        self.log(f"bilan : carrés générés {self.stats['squares_generated']}, repris du cache "
                 f"{self.stats['squares_cached']}, tuiles lointaines générées {self.stats['far_generated']}, "
                 f"téléchargements {downloads}, lignes illisibles {self.stats['bad_lines']}, "
                 f"mémoire max {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} Mo")
        self.closed = True
        self.send({"type": "closed"})


def _square_versions(db: OsmDb, provider: ElevationProvider) -> dict[str, Any]:
    from .squares import square_versions
    return square_versions(db, provider)


def _part_of(s: float) -> int:
    return max(0, int(math.floor(s / 1000.0)))


def _write_json(path: Path, obj: Any, indent: int | None = None) -> None:
    """Fichier temporaire voisin puis renommage : un lecteur ne voit jamais un JSON partiel."""
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    text = json.dumps(obj, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# --- processus ------------------------------------------------------------------------------------

class FakeClock:
    """Horloge des tests : avance d'une demi-seconde à chaque `progress`."""

    def __init__(self, start: float = 1_793_000_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t


def serve(session: WorldSession, inp: TextIO, fake_clock: FakeClock | None = None) -> int:
    lines: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        for line in inp:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=reader, name="lecture-stdin", daemon=True).start()
    while not session.closed:
        try:
            line = lines.get_nowait() if session.has_work() else lines.get()
        except queue.Empty:
            session.work()
            continue
        if line is None:
            session.log("entrée standard fermée : fin de séance")
            session.close()
            break
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            if not isinstance(msg, dict):
                raise ValueError("objet attendu")
        except ValueError:
            session.stats["bad_lines"] += 1
            session.log(f"ligne illisible ignorée : {line[:80]!r}")
            continue
        if fake_clock is not None and msg.get("type") == "progress":
            fake_clock.t += PROGRESS_FAKE_DT_S
        session.handle(msg)
    return 0


def _synthetic(spec: str) -> SyntheticProvider:
    lat, lon = (float(v) for v in spec.split(","))
    return SyntheticProvider(lat, lon)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="openride-worldgen", description="Générateur du monde ouvert (lot W8)")
    ap.add_argument("--session", type=Path, help="dossier de séance (sinon seances/ow-<date>.world du cache)")
    ap.add_argument("--config", type=Path, help="config.toml (section [open_world])")
    ap.add_argument("--no-network", action="store_true", help="aucun téléchargement : cache seulement")
    ap.add_argument("--fake-clock", action="store_true", help="horloge simulée (tests)")
    ap.add_argument("--synthetic-relief", metavar="LAT,LON", help="relief analytique (tests, sans réseau)")
    ap.add_argument("--tiles-url", metavar="URL", help="TileJSON d'un autre serveur de tuiles (tests, X28)")
    ap.add_argument("--dem-url", metavar="URL", help="autre serveur du relief Copernicus (tests, X28)")
    args = ap.parse_args(argv)

    def log(m: str) -> None:
        print(m, file=sys.stderr, flush=True)

    def send(msg: dict) -> None:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()

    try:
        cfg = read_open_world_config(args.config)
        cache = WorldCache.from_config(args.config, log=log)
    except CompileError as exc:
        log(str(exc))
        send({"type": "error", "code": "world_unavailable", "message": str(exc)})
        return 2
    network = bool(cfg.get("network", True)) and not args.no_network
    provider: ElevationProvider = (_synthetic(args.synthetic_relief) if args.synthetic_relief
                                   else CopernicusGlo30Provider(offline=not network, log=log,
                                                                base_url=args.dem_url or COPERNICUS_BASE_URL))
    fake = FakeClock() if args.fake_clock else None
    session = WorldSession(cache, provider, send, cfg, args.session, network=network,
                           clock=fake or time.time, log=log)
    session.tilejson_url = args.tiles_url
    log(f"openride-worldgen {__version__} prêt ({'réseau autorisé' if network else 'hors ligne'})")
    return serve(session, sys.stdin, fake)


if __name__ == "__main__":
    raise SystemExit(main())
