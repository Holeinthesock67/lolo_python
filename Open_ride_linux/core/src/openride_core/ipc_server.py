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

log = logging.getLogger("ipc_server")

CONTRACT_VERSION = 1
MAX_DATAGRAM_SIZE = 1400


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
    last_cmd_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "state",
            "v": CONTRACT_VERSION,
            **asdict(self),
        }


class IpcServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port_state: int = 5005,
        port_commands: int = 5006,
        on_command: Callable[[str, dict[str, Any], int], None] | None = None,
        on_engine_lost: Callable[[], None] | None = None,
        on_engine_returned: Callable[[], None] | None = None,
    ) -> None:
        self.host = host
        self.port_state = port_state
        self.port_commands = port_commands
        self.on_command = on_command
        self.on_engine_lost = on_engine_lost
        self.on_engine_returned = on_engine_returned

        self.last_heartbeat_time: float | None = None
        self.engine_connected: bool = False
        self.engine_version: str | None = None
        self.last_cmd_id: int = 0
        self.seq: int = 0

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

    def send_raw(self, msg_dict: dict[str, Any]) -> None:
        if not self._tx_sock:
            return
        payload = json.dumps(msg_dict, separators=(",", ":")).encode("utf-8")
        if len(payload) > MAX_DATAGRAM_SIZE:
            log.warning("Datagramme IPC trop grand (%d octets), ignoré", len(payload))
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
            "core_version": "0.1.0",
            "config": config_summary,
        }
        self.send_raw(msg)

    def send_input_event(self, event_name: str) -> None:
        msg = {
            "type": "input",
            "v": CONTRACT_VERSION,
            "event": event_name,
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
                log.warning("Datagramme reçu illisible (JSON invalide)")
                continue

            self._handle_message(msg)

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
            was_connected = self.engine_connected
            self.engine_connected = True
            log.info("Reçu 'hello' de l'engine version %s", self.engine_version)
            self.send_hello_ack(
                {"ftp_w": 250, "gears_total": 24, "theme": "default"}
            )
            if not was_connected and self.on_engine_returned:
                self.on_engine_returned()

        elif msg_type == "heartbeat":
            self.last_heartbeat_time = time.monotonic()
            if not self.engine_connected:
                self.engine_connected = True
                if self.on_engine_returned:
                    self.on_engine_returned()

        elif msg_type == "cmd":
            cmd_id = msg.get("cmd_id", 0)
            name = msg.get("name")
            args = msg.get("args", {})
            self.last_heartbeat_time = time.monotonic()
            if cmd_id > self.last_cmd_id:
                self.last_cmd_id = cmd_id
                log.info("Commande traitée : id=%d name=%s", cmd_id, name)
                if self.on_command and name:
                    self.on_command(name, args, cmd_id)
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
