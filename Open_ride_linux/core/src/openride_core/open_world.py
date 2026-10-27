"""Séance en monde ouvert côté core (lot W9) : générateur, route qui s'allonge, carrefours, choix.

`OpenWorld` pilote le générateur (`worldgen_client.py`, contrat `worldgen_v1.md`), tient la route
engagée (`live_route.py`) et construit le champ `open_world` de `state`. Il ne touche ni à la machine
à états ni à l'IPC : la séance l'appelle une fois par pas (`tick`) et lit ce qu'il décide.

Choix aux carrefours (décision W-Q1) : `LEFT_SHORT` et `RIGHT_SHORT` prennent la branche voisine, `A_SHORT`
la suivante en boucle, `A_LONG` valide tout de suite ; le clavier passe par `choose_branch`. Un carrefour
est proposé à moins de `offer_m` et son choix est figé à `lock_m` avant lui.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import OpenWorldConfig
from .live_route import LiveRoute
from .route import WorldError
from .worldgen_client import WorldgenClient

log = logging.getLogger("open_world")

NAVS = ("ride", "destination", "loop")
PROGRESS_PERIOD_S = 0.5           # `progress` deux fois par seconde (contrat §3)
STATUS_PERIOD_S = 0.25            # `world_status` : quatre par seconde au plus
PAUSE_BELOW_M = 200.0             # moins de route connue devant : pause `world_data`
RESUME_ABOVE_M = 500.0            # reprise automatique à 500 m connus
MAX_RESTARTS = 1                  # une relance du générateur, puis pause `world_data`
STATUS_FIELDS = ("phase", "done_bytes", "total_bytes", "squares_ready", "squares_needed", "message")
CHOICE_EVENTS = ("LEFT_SHORT", "RIGHT_SHORT", "A_SHORT", "A_LONG")
DATA_STATES = ("cached", "downloading", "offline", "missing")


class OpenWorldError(Exception):
    """Démarrage refusé ; `code` est le code d'erreur IPC (`bad_args`, `world_unavailable`)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_start(args: Any) -> dict[str, Any]:
    """Arguments de `start_open_world` validés, sous la forme du message `open` du générateur."""
    if not isinstance(args, dict):
        raise OpenWorldError("bad_args", "start_open_world attend un objet")

    def num(key: str, lo: float, hi: float, default: float | None = None) -> float:
        v = args.get(key, default)
        if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
            raise OpenWorldError("bad_args", f"start_open_world : « {key} » attendu entre {lo:g} et {hi:g}")
        return float(v)

    nav = args.get("nav", "ride")
    if nav not in NAVS:
        raise OpenWorldError("bad_args", f"start_open_world : « nav » attendu parmi {', '.join(NAVS)}")
    msg: dict[str, Any] = {"type": "open", "lat": num("lat", -90, 90), "lon": num("lon", -180, 180),
                           "heading_deg": num("heading_deg", 0, 360, 0.0), "nav": nav, "target": None,
                           "loop_km": None, "seed": int(num("seed", 0, 2**31 - 1, 0))}
    if nav == "destination":
        t = args.get("target")
        if not isinstance(t, dict):
            raise OpenWorldError("bad_args", "start_open_world : « target » {lat, lon} attendu avec nav = destination")
        msg["target"] = {"lat": num_of(t, "lat", -90, 90), "lon": num_of(t, "lon", -180, 180)}
    if nav == "loop":
        msg["loop_km"] = num("loop_km", 1, 500)
    return msg


def num_of(d: dict, key: str, lo: float, hi: float) -> float:
    v = d.get(key)
    if v is None or isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise OpenWorldError("bad_args", f"start_open_world : target.{key} attendu entre {lo:g} et {hi:g}")
    return float(v)


@dataclass
class OpenWorld:
    cfg: OpenWorldConfig
    config_path: Path | None = None
    cmd: list[str] | None = None            # commande du générateur (essais : faux générateur)
    extra_args: list[str] = field(default_factory=list)
    send_status: Callable[[dict[str, Any]], None] = lambda msg: None
    send_error: Callable[[str, str], None] = lambda code, text: None
    journal: Callable[[dict[str, Any]], None] = lambda line: None

    def __post_init__(self) -> None:
        self.id = ""
        self.folder: Path | None = None
        self.route: LiveRoute | None = None
        self.client: WorldgenClient | None = None
        self.opening = False                 # `open` envoyé, première révision pas encore reçue
        self.ready = False
        self.failed = False                  # `world_unavailable` pendant la préparation
        self.dead = False                    # générateur perdu après sa relance : plus de route nouvelle
        self.data = "cached"
        self.rev = 0
        self._open_msg: dict[str, Any] = {}
        self._restarts = 0
        self._next: LiveRoute | None = None   # route du générateur relancé, en attente de sa première révision
        self._ready_seen = False
        self._pending_status: dict[str, Any] | None = None
        self._last_status = -1e9
        self._last_progress = -1e9
        self._chosen: dict[str, int] = {}     # choix du cycliste (avant confirmation par la révision suivante)
        self._how: dict[str, str] = {}
        self._logged: set[str] = set()       # carrefours déjà écrits au journal
        self._locked_early: set[str] = set()

    # --- ouverture et fermeture ------------------------------------------------------------

    @property
    def sessions_dir(self) -> Path:
        return Path(self.cfg.cache_dir).expanduser() / "seances"

    def begin(self, args: Any, now: float | None = None) -> None:
        """Lance le générateur et lui envoie `open` ; lève `OpenWorldError` si les arguments sont refusés."""
        msg = parse_start(args)
        msg["network"] = bool(self.cfg.network)
        self._open_msg = msg
        self.id = "ow-" + time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
        self.folder = self.sessions_dir / f"{self.id}.world"
        self.client = WorldgenClient(self.folder, self.config_path, self.cmd, self.extra_args)
        self.route = LiveRoute(self.folder)
        self.opening = True
        try:
            self.client.start()
        except OSError as exc:
            raise OpenWorldError("world_unavailable", f"générateur du monde ouvert introuvable : {exc}") from exc
        self.client.send(msg)

    def close(self) -> None:
        """Fin de séance : `close` au générateur et attente de `closed` (5 s au plus)."""
        for client in (self.client,):
            if client is not None:
                client.close()
        self.client = None

    # --- pas de la séance -------------------------------------------------------------------

    def tick(self, s: float, v: float, running: bool, now: float | None = None) -> None:
        """Vide la file du générateur, relance un générateur tombé, envoie la progression."""
        now = time.monotonic() if now is None else now
        client = self.client
        if client is None:
            return
        for msg in client.drain():
            self._on_message(msg, s)
        if self._pending_status and now - self._last_status >= STATUS_PERIOD_S:
            self.send_status(self._pending_status)
            self._pending_status, self._last_status = None, now
        if not client.alive and not client.closed:
            self._lost(s, now)
            client = self.client
            if client is None:
                return
        if (running or self.ready) and now - self._last_progress >= PROGRESS_PERIOD_S and not self.opening:
            self._last_progress = now
            client.send({"type": "progress", "s_m": round(max(0.0, s - self._base()), 2), "v_mps": round(v, 3)})
        self._journal_locked(s)

    def _base(self) -> float:
        return self.route.base_m if self.route else 0.0

    def _on_message(self, msg: dict[str, Any], s: float) -> None:
        kind = msg.get("type")
        if kind == "status":
            data = msg.get("data")
            if data in DATA_STATES:
                self.data = data
            out = {k: msg[k] for k in STATUS_FIELDS if k in msg}
            out.setdefault("message", "")
            out["message"] = str(out["message"])[:200]
            if msg.get("phase") in ("ready", "error"):
                self.send_status(out)      # les changements d'étape ne sont jamais retardés
                self._pending_status = None
                self._last_status = time.monotonic()
            else:
                self._pending_status = out
            if msg.get("phase") == "ready":
                self._ready_seen = True
        elif kind == "revision":
            self._on_revision(msg, s)
        elif kind == "error":
            code = msg.get("code")
            text = str(msg.get("message") or code)
            if code == "world_unavailable":
                self.failed = True
                self.opening = False
                self.send_error("world_unavailable", text)
            elif code in ("branch_locked", "unknown_junction"):
                self.send_error(code, text)
            else:
                log.error("Erreur du générateur : %s", text)
        # `closed` : rien à faire ici (WorldgenClient.closed)

    def _on_revision(self, msg: dict[str, Any], s: float) -> None:
        rev = int(msg.get("rev", 0))
        self.rev = rev
        if self._next is not None:                 # générateur relancé : sa première route remplace l'ancienne
            try:
                self._next.load()
            except WorldError as exc:
                log.warning("Route du générateur relancé illisible : %s", exc)
                return
            self.route, self._next = self._next, None
            self.opening = False
            log.info("Générateur relancé : route reprise à %.0f m.", self.route.base_m)
            return
        assert self.route is not None
        if self.opening:
            try:
                self.route.load()
            except WorldError as exc:
                log.error("Première route illisible : %s", exc)
                self.failed = True
                self.opening = False
                self.send_error("world_unavailable", str(exc))
                return
            self.opening = False
            self.ready = True
            return
        self.route.apply_revision(rev, int(msg.get("changed_from_part", 0)))

    # --- générateur perdu ---------------------------------------------------------------------

    def _lost(self, s: float, now: float) -> None:
        if self.client:
            self.client.close(0.0)          # recueille le code de sortie et libère les fils
        code = self.client.exit_code if self.client else None
        if self.opening and not self.ready:
            self.failed = True
            self.opening = False
            log.error("Le générateur s'est arrêté pendant la préparation (code %s).", code)
            self.send_error("world_unavailable", "Le générateur du monde ouvert s'est arrêté pendant la préparation.")
            self.client = None
            return
        if self._restarts >= MAX_RESTARTS or self.route is None or not self.route.ready:
            if not self.dead:
                log.error("Le générateur est retombé : plus de route nouvelle (pause `world_data` au bout de la route connue).")
            self.dead, self.data = True, "missing"
            self.client = None
            return
        self._restarts += 1
        here = self.route.sample(s)
        log.warning("Le générateur s'est arrêté (code %s) : relance depuis %.0f m.", code, s)
        msg = {**self._open_msg, "lat": here.lat, "lon": here.lon, "heading_deg": here.heading_deg, "nav": "ride",
               "target": None, "loop_km": None}
        self.client = WorldgenClient(self.folder, self.config_path, self.cmd, self.extra_args)
        self._next = LiveRoute(self.folder, base_m=s)
        self.opening = True
        self.ready = True                       # la séance continue sur l'ancienne route pendant la relance
        try:
            self.client.start()
        except OSError:
            self.dead, self.data, self.client, self._next = True, "missing", None, None
            return
        self.client.send(msg)

    # --- pause « plus de route » ------------------------------------------------------------

    def known_ahead(self, s: float) -> float:
        return self.route.known_ahead_m(s) if self.route and self.route.ready else 0.0

    def should_pause(self, s: float) -> bool:
        """Moins de 200 m de route connue devant et générateur sans données (contrat IPC §9)."""
        return (self.data == "missing" or self.dead) and self.known_ahead(s) < PAUSE_BELOW_M

    def can_resume(self, s: float) -> bool:
        return not self.dead and self.known_ahead(s) >= RESUME_ABOVE_M

    # --- carrefours --------------------------------------------------------------------------

    def _junctions(self) -> list[dict[str, Any]]:
        return self.route.junctions if self.route and self.route.ready else []

    def _ahead(self, s: float) -> dict[str, Any] | None:
        base = self._base()
        for j in self._junctions():                       # `junctions.json` est rangé par distance croissante
            if j["s_m"] + base >= s:
                return j
        return None

    def _is_locked(self, j: dict[str, Any], s: float) -> bool:
        return (j["id"] in self._locked_early or bool(j.get("locked"))
                or s >= j.get("lock_s_m", j["s_m"] - self.cfg.lock_m) + self._base())

    def _chosen_of(self, j: dict[str, Any]) -> int:
        return self._chosen.get(j["id"], int(j.get("chosen", j.get("default", 0))))

    def state_field(self, s: float) -> dict[str, Any]:
        """Champ `open_world` de `state` (contrat IPC §4, « Monde ouvert »)."""
        j = self._ahead(s)
        nxt = None
        if j is not None:
            nxt = {"id": str(j["id"]), "d_m": round(j["s_m"] + self._base() - s, 1),
                   "default": int(j.get("default", 0)), "chosen": self._chosen_of(j), "locked": self._is_locked(j, s),
                   "b": [[int(round(b["angle_deg"])), b["road_class"], round(float(b["grade_pct_500m"]), 1)]
                         for b in j["branches"][:4]]}
        return {"rev": self.rev, "next": nxt, "data": self.data}

    def offered(self, s: float) -> dict[str, Any] | None:
        """Carrefour proposé : à moins de `offer_m` et non verrouillé."""
        j = self._ahead(s)
        if j is None or j["s_m"] + self._base() - s > self.cfg.offer_m or self._is_locked(j, s):
            return None
        return j

    # --- choix --------------------------------------------------------------------------------

    def on_input(self, event: str, s: float) -> bool:
        """Événement du Click : vrai s'il a servi de choix (un carrefour est proposé)."""
        j = self.offered(s)
        if j is None or event not in CHOICE_EVENTS:
            return False
        n = len(j["branches"])
        cur = self._chosen_of(j)
        if event == "A_LONG":
            self._set(j, cur, "validated", lock=True)
            return True
        if event == "A_SHORT":
            new = (cur + 1) % n
        else:
            order = sorted(range(n), key=lambda i: j["branches"][i]["angle_deg"])   # de gauche à droite
            pos = order.index(cur) if cur in order else 0
            pos = max(0, pos - 1) if event == "LEFT_SHORT" else min(n - 1, pos + 1)
            new = order[pos]
        if new != cur:
            self._set(j, new, "click")
        return True

    def choose_branch(self, junction_id: str, branch: Any, s: float) -> None:
        """Commande `choose_branch` (clavier) : erreurs `unknown_junction` et `branch_locked` relayées."""
        j = next((x for x in self._junctions() if x["id"] == junction_id), None)
        if j is None or isinstance(branch, bool) or not isinstance(branch, int) or not 0 <= branch < len(j["branches"]):
            self.send_error("unknown_junction", f"carrefour ou branche inconnu : {junction_id} / {branch}")
            return
        if self._is_locked(j, s):
            self.send_error("branch_locked", f"choix verrouillé à {self.cfg.lock_m:.0f} m du carrefour")
            return
        self._set(j, branch, "key")

    def _set(self, j: dict[str, Any], branch: int, how: str, lock: bool = False) -> None:
        self._chosen[j["id"]] = branch
        self._how[j["id"]] = how
        if lock:
            self._locked_early.add(j["id"])
        if self.client:
            self.client.send({"type": "choose", "junction_id": j["id"], "branch": branch})
        log.info("Carrefour %s : branche %d (%s).", j["id"], branch, how)

    def _journal_locked(self, s: float) -> None:
        """Écrit au journal la branche prise, une fois le carrefour verrouillé."""
        base = self._base()
        for j in self._junctions():
            if j["id"] in self._logged or not self._is_locked(j, s):
                continue
            self._logged.add(j["id"])
            idx = self._chosen_of(j)
            how = self._how.get(j["id"], "default" if idx == int(j.get("default", 0)) else "click")
            self.journal({"id": j["id"], "s_m": round(j["s_m"] + base, 1), "branch": idx, "of": len(j["branches"]),
                          "how": how, "road_class": j["branches"][idx]["road_class"], "ts": round(time.time(), 3)})
