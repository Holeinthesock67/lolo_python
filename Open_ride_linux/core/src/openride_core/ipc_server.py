"""Serveur IPC UDP localhost core ↔ engine (SRS §3, Contrat IPC v1).

- Écoute sur port_commands (5006 par défaut) pour recevoir hello, heartbeat, cmd, bye.
- Émet vers port_state (5005 par défaut) les trames state (30 Hz), input, hello_ack, error, shutdown.
- Gère la détection de perte de heartbeat engine (> 2 s) et les accusés de réception de commandes (cmd_id -> last_cmd_id).
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from . import __version__, latency_log
from .ipc_budget import encode, fit_state

log = logging.getLogger("ipc_server")

CONTRACT_VERSION = 1
# Limite de tout datagramme hors messages en parties (contrat §2, révision 1.5, décision du propriétaire
# du 27 octobre ; 127.0.0.1, sans fragmentation). Une trame state plus grande est allégée, les autres jetées.
MAX_DATAGRAM_SIZE = 4096
# Révision du contrat annoncée dans hello_ack (champ facultatif rev, révision 1.3).
CONTRACT_REV = "1.5"
# Modes de jeu que ce core sait lancer (hello_ack.config.modes, révision 1.3).
CORE_MODES = ("ride", "erg", "open_world", "rogue", "wtf")   # monde ouvert : révision 1.5, lot W9 ; rogue : lot R8 ; wtf : lot WTF2
MAX_LIST_DATAGRAM_SIZE = 60000
# Messages en parties (`part`, `parts`), `plans` et `settings` : 60 000 octets au plus par datagramme (contrat §2,
# même liste que le contrat ; `garage` et `room` depuis la révision 1.4, le monde ouvert depuis la 1.5,
# `settings` depuis le 30 octobre : 26 réglages et les thèmes installés passaient 4 096 octets).
LIST_MESSAGE_TYPES = ("routes", "workouts", "imports", "plans", "settings", "garage", "room",
                      "places", "world_map", "world_regions", "route_imports")
INVALID_LOG_PERIOD_S = 10.0   # au plus un avertissement « datagramme rejeté » par période


# Décimales gardées dans la trame state : 1 cm, 1 mm/s, 0,01 %, 0,1 W, 0,1 tr/min, 6 décimales de degré (11 cm).
STATE_ROUNDING = {
    "t": 2, "s": 2, "v": 3, "grade": 2, "grade_sent": 2, "power": 1, "power_3s": 1, "cadence": 1,
    "lat": 6, "lon": 6, "alt": 2, "route_length_m": 1,
}


@dataclass
class IpcState:
    seq: int = 0
    t: float = 0.0
    session_state: str = "IDLE"
    pause_reason: str | None = None
    trainer_status: str = "MOCK"
    input_status: str = "KEYBOARD"
    mode: str = "SIM"
    route_id: str | None = None
    route_length_m: float | None = None
    s: float = 0.0
    v: float = 0.0
    grade: float = 0.0
    grade_sent: float = 0.0
    difficulty_pct: int = 50
    power: float = 0.0
    power_3s: float = 0.0
    cadence: float = 0.0
    hr: int | None = None
    gear: int = 12
    gears_total: int = 24
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    erg: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    devices: dict[str, Any] | None = None
    bots: list[dict[str, Any]] | None = None
    wind: dict[str, float] | None = None   # révision 1.3 (lot P2) : 2 fois par seconde, jamais avec devices
    draft: float | None = None             # révision 1.3 (lot P3) : présent dès qu'il y a un bot
    draft_bot: str | None = None
    open_world: dict[str, Any] | None = None   # révision 1.5 (lot W9) : jamais dans une trame avec devices
    # Révision 1.4 (série T, lot T7) : absents sans segment, hors bonus ou sans bot.
    segment: dict[str, Any] | None = None
    powerup: dict[str, Any] | None = None
    jerseys: dict[str, Any] | None = None
    bot_ahead: str | None = None           # présents (éventuellement null) dès qu'il y a un bot
    bot_behind: str | None = None
    rogue: dict[str, Any] | None = None    # révision 1.4 (série R, lot R8) : présent seulement en mode ROGUE
    wtf: dict[str, Any] | None = None      # révision 1.5 (lot WTF2) : présent seulement en mode WTF
    last_cmd_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = {
            "type": "state",
            "v": CONTRACT_VERSION,
            **asdict(self),
        }
        # Flottants arrondis pour tenir dans 1 400 octets (audit IPC du 26 octobre, décision D1) :
        # un float Python s'écrit sur 15 à 18 caractères, soit environ 90 octets de trop par trame.
        for key, ndigits in STATE_ROUNDING.items():
            if isinstance(d.get(key), float):
                d[key] = round(d[key], ndigits)
        if self.devices is None:
            d.pop("devices", None)
        if self.bots is None:
            d.pop("bots", None)
        if self.wind is None:
            d.pop("wind", None)
        if self.draft is None:
            d.pop("draft", None)
        if self.draft_bot is None:
            d.pop("draft_bot", None)
        if self.open_world is None or self.devices is not None:
            d.pop("open_world", None)
        for key in ("segment", "powerup", "jerseys", "rogue", "wtf"):
            if d[key] is None:
                d.pop(key)
        if self.bots is None:
            d.pop("bot_ahead")
            d.pop("bot_behind")
        return d


class IpcServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port_state: int = 5005,
        port_commands: int = 5006,
        on_command: Callable[[str, dict[str, Any], int], None] | None = None,
        on_engine_lost: Callable[[], None] | None = None,
        on_engine_returned: Callable[[], None] | None = None,
        hello_config: dict[str, Any] | None = None,
    ) -> None:
        self.host = host
        self.port_state = port_state
        self.port_commands = port_commands
        self.on_command = on_command
        self.on_engine_lost = on_engine_lost
        self.on_engine_returned = on_engine_returned
        # Configuration utile à l'affichage, renvoyée dans hello_ack (contrat §5).
        self.hello_config = dict(hello_config or {"ftp_w": 250, "gears_total": 24, "theme": "default"})

        self.last_heartbeat_time: float | None = None
        self.engine_connected: bool = False
        self.engine_version: str | None = None
        self.engine_rev: str | None = None
        self.last_cmd_id: int = 0
        self.seq: int = 0
        # Datagrammes illisibles ou non conformes, ignorés (contrat §6).
        self.invalid_datagrams: int = 0
        self._invalid_logged_at: float | None = None
        self._trimmed_logged_at: float | None = None   # dernier avertissement « trame allégée »
        self._invalid_since_log: int = 0

        self._running: bool = False
        self._rx_sock: socket.socket | None = None
        self._tx_sock: socket.socket | None = None
        self._loop_task: asyncio.Task | None = None

    def start(self) -> None:
        try:
            self._rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._rx_sock.setblocking(False)
            self._rx_sock.bind((self.host, self.port_commands))

            self._tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._tx_sock.setblocking(False)
        except OSError as e:
            raise RuntimeError(
                f"Impossible de démarrer l'IPC UDP sur {self.host}:{self.port_commands} : {e}"
            ) from e

        self._running = True
        log.info(
            "IPC démarré : écoute des commandes sur %s:%d, émission d'état vers %s:%d",
            self.host,
            self.port_commands,
            self.host,
            self.port_state,
        )

    def stop(self) -> None:
        self._running = False
        if self._tx_sock:
            try:
                self.send_shutdown()
            except Exception:
                pass
            self._tx_sock.close()
            self._tx_sock = None
        if self._rx_sock:
            self._rx_sock.close()
            self._rx_sock = None
        log.info("IPC arrêté.")

    def send_raw(self, msg_dict: dict[str, Any], max_size: int | None = None) -> None:
        if not self._tx_sock:
            return
        msg_type = msg_dict.get("type")
        if max_size is not None:
            limit = max_size
        elif msg_type in LIST_MESSAGE_TYPES:
            limit = MAX_LIST_DATAGRAM_SIZE
        else:
            limit = MAX_DATAGRAM_SIZE
        payload = encode(msg_dict)
        if len(payload) > limit and msg_type == "state":
            # Trame allégée plutôt que jetée (lot X25) : l'écran garde position et puissance.
            msg_dict, dropped = fit_state(msg_dict, limit)
            payload = encode(msg_dict)
            now = time.monotonic()
            if self._trimmed_logged_at is None or now - self._trimmed_logged_at >= INVALID_LOG_PERIOD_S:
                self._trimmed_logged_at = now
                log.warning("Trame state trop grande, allégée (%s) : %d octets", ", ".join(dropped), len(payload))
        if len(payload) > limit:
            log.warning("Datagramme IPC trop grand (%d octets > %d), ignoré", len(payload), limit)
            return
        try:
            self._tx_sock.sendto(payload, (self.host, self.port_state))
        except OSError as err:
            log.debug("Erreur lors de l'envoi UDP : %s", err)

    def send_state(self, state: IpcState) -> None:
        self.seq += 1
        state.seq = self.seq
        state.last_cmd_id = self.last_cmd_id
        self.send_raw(state.to_dict())

    def send_hello_ack(self, config_summary: dict[str, Any]) -> None:
        msg = {
            "type": "hello_ack",
            "v": CONTRACT_VERSION,
            "rev": CONTRACT_REV,
            "core_version": __version__,
            "config": {**config_summary, "modes": list(CORE_MODES)},
        }
        self.send_raw(msg)

    def send_input_event(self, event_name: str) -> None:
        msg = {
            "type": "input",
            "v": CONTRACT_VERSION,
            "event": event_name,
            **latency_log.ipc_fields(),   # latence_id, latence_t : seulement avec `--latence` (lot X7)
        }
        self.send_raw(msg)

    def send_error(self, code: str, message: str) -> None:
        msg = {
            "type": "error",
            "v": CONTRACT_VERSION,
            "code": code,
            "message": message,
        }
        self.send_raw(msg)

    def send_world_status(self, status: dict[str, Any]) -> None:
        """`world_status` (révision 1.5) : avancement de la préparation du monde ouvert."""
        self.send_raw({"type": "world_status", "v": CONTRACT_VERSION, **status})

    def send_shutdown(self) -> None:
        msg = {
            "type": "shutdown",
            "v": CONTRACT_VERSION,
        }
        self.send_raw(msg)

    def process_incoming_datagrams(self) -> None:
        if not self._rx_sock:
            return
        while True:
            try:
                data, _addr = self._rx_sock.recvfrom(MAX_DATAGRAM_SIZE)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break

            try:
                msg = json.loads(data.decode("utf-8"))
            except Exception:
                self._reject("JSON invalide")
                continue

            reason = _invalid_reason(msg)
            if reason:
                self._reject(reason)
                continue
            self._handle_message(msg)

    def _reject(self, reason: str) -> None:
        """Datagramme illisible : ignoré et compté ; avertissement limité pour ne pas noyer le journal."""
        self.invalid_datagrams += 1
        self._invalid_since_log += 1
        now = time.monotonic()
        if self._invalid_logged_at is None or now - self._invalid_logged_at >= INVALID_LOG_PERIOD_S:
            log.warning("Datagramme reçu ignoré (%s) ; %d rejeté(s) depuis le dernier avertissement, %d au total",
                        reason, self._invalid_since_log, self.invalid_datagrams)
            self._invalid_logged_at = now
            self._invalid_since_log = 0

    def _handle_message(self, msg: dict[str, Any]) -> None:
        msg_type = msg.get("type")
        v = msg.get("v")

        if msg_type == "hello":
            if v != CONTRACT_VERSION:
                log.warning("Version IPC incompatible reçue : %s (attendu %d)", v, CONTRACT_VERSION)
                self.send_error(
                    "version_mismatch",
                    f"Version contrat incompatible ({v} != {CONTRACT_VERSION})",
                )
                return
            self.engine_version = msg.get("engine_version")
            self.last_heartbeat_time = time.monotonic()
            # Le compteur cmd_id est propre à une instance de l'engine : un engine relancé
            # renumérote à partir de 1 (contrat §4).
            self.last_cmd_id = 0
            was_connected = self.engine_connected
            self.engine_connected = True
            rev = msg.get("rev")
            self.engine_rev = rev if isinstance(rev, str) else None
            log.info("Reçu 'hello' de l'engine version %s (contrat %s)", self.engine_version,
                     self.engine_rev or "avant 1.3")
            if self.engine_rev != CONTRACT_REV:
                # Même version majeure : compatible, les champs inconnus sont ignorés (§8).
                log.warning("Révisions du contrat différentes : engine %s, core %s",
                            self.engine_rev or "avant 1.3", CONTRACT_REV)
            self.send_hello_ack(self.hello_config)
            if not was_connected and self.on_engine_returned:
                self.on_engine_returned()

        elif msg_type == "heartbeat":
            self.last_heartbeat_time = time.monotonic()
            if not self.engine_connected:
                self.engine_connected = True
                if self.on_engine_returned:
                    self.on_engine_returned()

        elif msg_type == "cmd":
            cmd_id = msg["cmd_id"]
            name = msg["name"]
            args = msg.get("args") or {}
            self.last_heartbeat_time = time.monotonic()
            # Requêtes : réponse à chaque copie reçue, la réponse a pu se perdre (contrat §4). La création et
            # l'import d'entraînement sont idempotents (même fichier, même identifiant), lot N16.
            is_query = name in ("list_routes", "list_workouts", "list_imports", "create_workout", "import_workout",
                                "list_route_imports",
                                "world_search", "world_map", "world_regions")
            if cmd_id > self.last_cmd_id or is_query:
                self.last_cmd_id = max(self.last_cmd_id, cmd_id)
                log.info("Commande traitée : id=%d name=%s", cmd_id, name)
                if self.on_command:
                    try:
                        self.on_command(name, args, cmd_id)
                    except Exception:   # un bogue de commande ne doit pas arrêter la boucle du core
                        log.exception("Erreur pendant la commande %s (id=%d), ignorée", name, cmd_id)
            else:
                log.debug("Commande redondante ignorée (id=%d <= last=%d)", cmd_id, self.last_cmd_id)

        elif msg_type == "bye":
            log.info("Reçu 'bye' de l'engine.")
            self.engine_connected = False
            self.last_heartbeat_time = None
            if self.on_engine_lost:
                self.on_engine_lost()

    def check_liveness(self) -> None:
        """À appeler périodiquement : détecte si le heartbeat a cessé depuis plus de 2 s."""
        if not self.engine_connected or self.last_heartbeat_time is None:
            return
        elapsed = time.monotonic() - self.last_heartbeat_time
        if elapsed > 2.0:
            log.warning("Heartbeat engine perdu (plus de signal depuis %.1f s)", elapsed)
            self.engine_connected = False
            if self.on_engine_lost:
                self.on_engine_lost()


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _invalid_reason(msg: Any) -> str | None:
    """Contrôle léger des messages reçus (sans jsonschema) ; renvoie la raison du rejet ou None."""
    if not isinstance(msg, dict):
        return "pas un objet JSON"
    if not isinstance(msg.get("type"), str):
        return "champ type absent ou non textuel"
    if msg["type"] == "cmd":
        if not _is_int(msg.get("cmd_id")) or msg["cmd_id"] < 1:
            return "cmd_id doit être un entier >= 1"
        if not isinstance(msg.get("name"), str) or not msg["name"]:
            return "name doit être une chaîne non vide"
        if msg.get("args") is not None and not isinstance(msg["args"], dict):
            return "args doit être un objet"
    return None
