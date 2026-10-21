"""Simulateur de boucle principale du core pour le Sprint 1 (MockDriver + Physique + IPC Server).

Permet de faire tourner le serveur core en continu avec le MockDriver pour tester
directement l'engine Godot ou un client externe :
- Boucle physique à 50 Hz avec MockDriver
- Émission de l'état `state` en UDP vers l'engine à 30 Hz (port 5005)
- Écoute des commandes et du heartbeat de l'engine sur le port 5006
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from pathlib import Path

from ..config import Config
from ..gearing import Gearing
from ..ipc_server import IpcServer, IpcState
from ..mock_driver import MockDriver
from ..physics import DT_DEFAULT, PhysicsParams, RiderPhysics
from .fake_world import build_route
from .fit_demo import LinearRoute

log = logging.getLogger("core_session")


class CoreSession:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.gearing = Gearing(cfg.gearing, cfg.trainer)
        self.physics = RiderPhysics(PhysicsParams.from_config(cfg))
        self.driver = MockDriver()
        self.route: LinearRoute | None = None
        self.state = IpcState(
            session_state="IDLE",
            trainer_status="MOCK",
            gears_total=self.gearing.n_gears,
            gear=self.gearing.k,
        )

        self.server = IpcServer(
            port_state=cfg.ipc.port_state,
            port_commands=cfg.ipc.port_commands,
            on_command=self._on_command,
            on_engine_lost=self._on_engine_lost,
            on_engine_returned=self._on_engine_returned,
        )
        self._running = False
        self._t_session = 0.0

    def _on_command(self, name: str, args: dict, cmd_id: int) -> None:
        log.info("Commande reçue : %s %s (cmd_id=%d)", name, args, cmd_id)
        if name == "select_route":
            route_id = args.get("route_id", "demo")
            # Générer/charger parcours factice pour le mock
            route_dict = build_route(5000.0)
            self.route = LinearRoute(route_dict)
            self.state.route_id = route_id
            self.state.route_length_m = self.route.length
            self.state.session_state = "READY"
        elif name == "start":
            if self.state.session_state in ("READY", "PAUSED"):
                self.state.session_state = "RUNNING"
                self.state.pause_reason = None
        elif name == "pause":
            if self.state.session_state == "RUNNING":
                self.state.session_state = "PAUSED"
                self.state.pause_reason = "user"
        elif name == "resume":
            if self.state.session_state == "PAUSED":
                self.state.session_state = "RUNNING"
                self.state.pause_reason = None
        elif name == "end_session":
            self.state.session_state = "FINISHED"

    def _on_engine_lost(self) -> None:
        if self.state.session_state == "RUNNING":
            log.warning("Engine perdu : mise en pause automatique de la séance.")
            self.state.session_state = "PAUSED"
            self.state.pause_reason = "engine_lost"

    def _on_engine_returned(self) -> None:
        log.info("Engine reconnecté.")

    def run(self) -> None:
        self.server.start()
        self._running = True

        log.info("Session Core démarrée. État : %s", self.state.session_state)
        # Par défaut en mode mock, charger un parcours pour être prêt immédiatement
        self._on_command("select_route", {"route_id": "demo"}, 1)
        self._on_command("start", {}, 2)

        dt_physics = 0.02  # 50 Hz
        dt_state = 1.0 / 30.0  # 30 Hz

        next_physics = time.monotonic()
        next_state = time.monotonic()
        next_check = time.monotonic()

        power_window: list[float] = []

        try:
            while self._running:
                now = time.monotonic()

                # Boucle réseau IPC
                self.server.process_incoming_datagrams()

                if now >= next_check:
                    self.server.check_liveness()
                    next_check = now + 0.5

                # Boucle physique (50 Hz)
                if now >= next_physics:
                    next_physics += dt_physics
                    if self.state.session_state == "RUNNING":
                        self._t_session += dt_physics
                        metrics = self.driver.poll(self._t_session)

                        grade = (
                            self.route.sample("grade_pct", self.physics.s)
                            if self.route
                            else 0.0
                        )
                        alt = (
                            self.route.sample("alt_m", self.physics.s)
                            if self.route
                            else 0.0
                        )

                        self.physics.step(metrics.power_w, grade, alt, dt_physics)

                        # Fenêtre glissante 3s pour power_3s
                        power_window.append(metrics.power_w)
                        if len(power_window) > 150:  # 3s à 50 Hz
                            power_window.pop(0)

                        power_3s = sum(power_window) / len(power_window) if power_window else 0.0

                        # Mise à jour de l'état
                        self.state.t = self._t_session
                        self.state.s = self.physics.s
                        self.state.v = self.physics.v
                        self.state.grade = grade
                        self.state.grade_sent = self.gearing.effective_grade(grade)
                        self.state.power = metrics.power_w
                        self.state.power_3s = round(power_3s, 1)
                        self.state.cadence = metrics.cadence_rpm
                        self.state.hr = metrics.hr_bpm
                        self.state.gear = self.gearing.k
                        if self.route:
                            self.state.lat = self.route.sample("lat", self.physics.s)
                            self.state.lon = self.route.sample("lon", self.physics.s)
                            self.state.alt = alt

                # Émission de l'état vers l'engine (30 Hz)
                if now >= next_state:
                    next_state += dt_state
                    self.server.send_state(self.state)

                time.sleep(0.001)

        except KeyboardInterrupt:
            log.info("Arrêt demandé par l'utilisateur.")
        finally:
            self.server.stop()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
        datefmt="%H:%M:%S",
    )
    cfg = Config()
    session = CoreSession(cfg)
    session.run()


if __name__ == "__main__":
    main()
