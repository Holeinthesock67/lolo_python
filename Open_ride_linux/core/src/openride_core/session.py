"""Boucle principale du core (SRS §3, §4, §9) : pilotes réels ou simulés, physique, IPC, journal.

Une seule boucle asyncio :
- physique à 50 Hz avec le pas réellement écoulé ;
- trame `state` à 30 Hz vers l'engine, commandes et heartbeat lus à chaque tour ;
- BLE (trainer, Click) dans des tâches asyncio séparées ;
- journal JSONL à 1 Hz ; FIT en fin de séance ;
- mesures de performance (durée du pas, retard de boucle, CPU) pour la décision Rust (SRS §14.1).
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from pathlib import Path
from typing import Any

from .config import Config
from .fit_export import journal_to_fit
from .gearing import Gearing
from .input_providers import KeyboardProvider, NullProvider, ZwiftClickProvider
from .ipc_server import IpcServer, IpcState
from .journal import JOURNAL_DIR, JournalWriter, Record
from .mock_driver import MockDriver
from .physics import PhysicsParams, RiderPhysics
from .tools.fake_world import build_route
from .tools.fit_demo import LinearRoute
from .zwift_click import InputEvent

log = logging.getLogger("core")

DT_PHYSICS = 0.02        # 50 Hz
DT_STATE = 1.0 / 30.0    # 30 Hz
STATS_PERIOD_S = 60.0
MAX_STEP_S = 0.1         # un pas plus long (gel du processus) est borné


class LoopStats:
    """Mesure de la boucle : durée du pas physique, retard de tick, charge CPU."""

    def __init__(self) -> None:
        self.step_ms: list[float] = []
        self.lag_ms: list[float] = []
        self._wall0 = time.monotonic()
        self._cpu0 = time.process_time()

    def add(self, step_s: float, lag_s: float) -> None:
        self.step_ms.append(step_s * 1000.0)
        self.lag_ms.append(lag_s * 1000.0)

    @staticmethod
    def _pct(values: list[float], q: float) -> float:
        if not values:
            return 0.0
        v = sorted(values)
        return v[min(int(q * len(v)), len(v) - 1)]

    def report(self) -> dict[str, float]:
        wall = max(time.monotonic() - self._wall0, 1e-9)
        out = {
            "step_p50_ms": self._pct(self.step_ms, 0.50),
            "step_p99_ms": self._pct(self.step_ms, 0.99),
            "step_max_ms": max(self.step_ms, default=0.0),
            "lag_p99_ms": self._pct(self.lag_ms, 0.99),
            "lag_max_ms": max(self.lag_ms, default=0.0),
            "cpu_pct": 100.0 * (time.process_time() - self._cpu0) / wall,
        }
        self.step_ms.clear()
        self.lag_ms.clear()
        self._wall0, self._cpu0 = time.monotonic(), time.process_time()
        return out


def build_driver(cfg: Config) -> Any:
    if cfg.drivers.trainer == "ftms":
        from .ftms_driver import FtmsDriver
        return FtmsDriver(cfg.trainer, cfg.bike, cfg.drivers.trainer_address or None)
    return MockDriver()


def build_inputs(cfg: Config) -> list[Any]:
    kind = cfg.drivers.input
    if kind == "click":
        # Le clavier reste actif en parallèle (contrat IPC §6).
        return [ZwiftClickProvider(cfg.drivers.click_address or None,
                                   cfg.drivers.click_short_max_s, cfg.drivers.click_long_min_s),
                KeyboardProvider()]
    if kind == "keyboard":
        return [KeyboardProvider()]
    return [NullProvider()]


class CoreSession:
    def __init__(self, cfg: Config, driver: Any = None, inputs: list[Any] | None = None,
                 journal_dir: Path = JOURNAL_DIR) -> None:
        self.cfg = cfg
        self.driver = driver if driver is not None else build_driver(cfg)
        self.inputs = inputs if inputs is not None else build_inputs(cfg)
        self.journal_dir = journal_dir
        self.gearing = Gearing(cfg.gearing, cfg.trainer)
        self.physics = RiderPhysics(PhysicsParams.from_config(cfg))
        self.route: LinearRoute | None = None
        self.state = IpcState(session_state="IDLE", gears_total=self.gearing.n_gears,
                              gear=self.gearing.k)
        self.server = IpcServer(
            port_state=cfg.ipc.port_state, port_commands=cfg.ipc.port_commands,
            on_command=self._on_command, on_engine_lost=self._on_engine_lost,
            on_engine_returned=lambda: log.info("Engine connecté."))
        self.stats = LoopStats()
        self.stop_event = asyncio.Event()

        self._t_session = 0.0
        self._grade_sent = 0.0
        self._power_window: list[tuple[float, float]] = []
        self._journal: JournalWriter | None = None
        self._journal_path: Path | None = None
        self._next_record = 0.0
        self._trainer_lost_since: float | None = None

    # --- machine à états ---------------------------------------------------------------

    def _set_state(self, new: str, reason: str | None = None) -> None:
        old = self.state.session_state
        self.state.session_state, self.state.pause_reason = new, reason
        log.info("Séance : %s -> %s%s", old, new, f" ({reason})" if reason else "")
        now = time.time()
        if self._journal:
            if new == "PAUSED" and old == "RUNNING":
                self._journal.event("pause", now)
            elif new == "RUNNING" and old == "PAUSED":
                self._journal.event("resume", now)
        if new in ("PAUSED", "READY", "FINISHED", "IDLE"):
            self._release_trainer()

    def _release_trainer(self) -> None:
        self._grade_sent = 0.0
        self.driver.set_sim_grade(0.0)

    def _on_command(self, name: str, args: dict, cmd_id: int) -> None:
        log.info("Commande %s %s (id=%d)", name, args, cmd_id)
        st = self.state.session_state
        if name == "select_route" and st in ("IDLE", "READY", "FINISHED"):
            # Provisoire : le lecteur .world arrive avec le compilateur ; parcours factice.
            self.route = LinearRoute(build_route(5000.0))
            self.state.route_id = args.get("route_id", "demo")
            self.state.route_length_m = self.route.length
            self.physics.s = self.physics.v = 0.0
            self._t_session = 0.0
            self._set_state("READY")
        elif name == "start" and st == "READY":
            self._open_journal()
            self._set_state("RUNNING")
        elif name == "pause" and st == "RUNNING":
            self._set_state("PAUSED", "user")
        elif name == "resume" and st == "PAUSED":
            self._trainer_lost_since = None
            self._set_state("RUNNING")
        elif name == "end_session" and st in ("RUNNING", "PAUSED"):
            self._finish(bool(args.get("save", True)))

    def _on_engine_lost(self) -> None:
        if self.state.session_state == "RUNNING":
            log.warning("Engine perdu : pause automatique.")
            self._set_state("PAUSED", "engine_lost")

    # --- journal et FIT ----------------------------------------------------------------

    def _open_journal(self) -> None:
        self._journal_path = self.journal_dir / f"{time.strftime('%Y-%m-%d_%H-%M-%S')}.jsonl"
        self._journal = JournalWriter(self._journal_path, route_id=self.state.route_id)
        self._journal.event("start", time.time())
        self._next_record = 0.0

    def _finish(self, save: bool) -> None:
        summary = None
        if self._journal:
            self._journal.event("stop", time.time())
            self._journal.close()
            if save:
                try:
                    fit_path, s = journal_to_fit(self._journal_path)
                    summary = {"fit_path": str(fit_path), "distance_m": round(s.distance_m, 1),
                               "timer_s": round(s.timer_s, 1)}
                except Exception as exc:
                    log.error("Export FIT impossible : %s", exc)
                    self.server.send_error("recording_failed", str(exc))
            self._journal = None
        self.state.summary = summary
        self._set_state("FINISHED")

    # --- entrées utilisateur -------------------------------------------------------------

    def _handle_input(self, ev: InputEvent) -> None:
        if self.state.session_state != "RUNNING":
            self.server.send_input_event(ev.value)   # menu piloté par l'engine
            return
        if ev == InputEvent.PLUS_SHORT:
            self.gearing.shift_up()
        elif ev == InputEvent.MINUS_SHORT:
            self.gearing.shift_down()
        # Appuis longs : sans effet en SIM en v1 (SRS §4.4).
        self.state.gear = self.gearing.k

    def _drain_inputs(self) -> None:
        for provider in self.inputs:
            while not provider.events.empty():
                self._handle_input(provider.events.get_nowait())
        # Statut d'entrée : celui du premier fournisseur (Click s'il est configuré).
        self.state.input_status = self.inputs[0].status if self.inputs else "KEYBOARD"

    # --- pas de simulation ---------------------------------------------------------------

    def _step(self, dt: float, now_mono: float) -> None:
        m = self.driver.poll(self._t_session)
        self.state.trainer_status = getattr(self.driver, "status", "MOCK")

        if self.state.session_state != "RUNNING":
            return
        if not m.connected:
            self._trainer_lost_since = self._trainer_lost_since or now_mono
            if now_mono - self._trainer_lost_since >= 3.0:
                log.warning("Trainer perdu : pause automatique.")
                self._set_state("PAUSED", "trainer_lost")
                return
        else:
            self._trainer_lost_since = None

        self._t_session += dt
        s = self.physics.s
        tau = self.cfg.trainer.latency_tau_s
        route = self.route
        grade = route.sample("grade_pct", s) if route else 0.0
        ahead = route.sample("grade_pct", s + self.physics.v * tau) if route else 0.0
        alt = route.sample("alt_m", s) if route else 0.0

        # Pente envoyée : anticipée de la latence du trainer, braquet appliqué, variation limitée.
        target = self.gearing.effective_grade(ahead)
        max_delta = self.cfg.trainer.grade_rate_pct_per_s * dt
        self._grade_sent += min(max(target - self._grade_sent, -max_delta), max_delta)
        self.driver.set_sim_grade(self._grade_sent)

        self.physics.step(m.power_w, grade, alt, dt)

        self._power_window.append((self._t_session, m.power_w))
        while self._power_window and self._power_window[0][0] < self._t_session - 3.0:
            self._power_window.pop(0)
        p3 = sum(p for _, p in self._power_window) / len(self._power_window)

        st = self.state
        st.t, st.s, st.v = self._t_session, self.physics.s, self.physics.v
        st.grade, st.grade_sent = grade, round(self._grade_sent, 2)
        st.power, st.power_3s, st.cadence, st.hr = m.power_w, round(p3, 1), m.cadence_rpm, m.hr_bpm
        st.gear = self.gearing.k
        if route:
            st.lat, st.lon, st.alt = route.sample("lat", st.s), route.sample("lon", st.s), alt

        if self._journal and self._t_session >= self._next_record:
            self._next_record += 1.0
            self._journal.record(Record(
                ts=round(time.time(), 3), t=round(self._t_session, 2), lat=st.lat, lon=st.lon,
                alt=round(alt, 2), distance=round(st.s, 2), speed=round(st.v, 3),
                power=round(m.power_w), cadence=round(m.cadence_rpm), hr=m.hr_bpm,
                grade=round(grade, 2), gear=self.gearing.k))

        if route and st.s >= route.length:
            log.info("Arrivée atteinte.")
            self._finish(True)

    # --- boucle principale ---------------------------------------------------------------

    async def run(self, autostart: bool = False) -> None:
        self.server.start()
        tasks = [asyncio.create_task(p.run(), name=type(p).__name__)
                 for p in [*self.inputs, self.driver] if hasattr(p, "run")]
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop_event.set)
            except NotImplementedError:
                pass
        if autostart:
            self._on_command("select_route", {"route_id": "demo"}, 0)
            self._on_command("start", {}, 0)
        log.info("Core démarré (trainer=%s, entrées=%s).", self.cfg.drivers.trainer,
                 self.cfg.drivers.input)
        try:
            await self._loop()
        finally:
            await self._shutdown(tasks)

    async def _loop(self) -> None:
        mono = time.monotonic
        next_tick = last = mono()
        next_state = next_check = last
        next_stats = last + STATS_PERIOD_S
        while not self.stop_event.is_set():
            now = mono()
            lag = max(now - next_tick, 0.0)
            t0 = mono()
            self.server.process_incoming_datagrams()
            self._drain_inputs()
            dt = min(now - last, MAX_STEP_S)
            last = now
            self._step(dt, now)
            step_s = mono() - t0
            self.stats.add(step_s, lag)

            if now >= next_check:
                next_check = now + 0.5
                self.server.check_liveness()
            if now >= next_state:
                next_state = now + DT_STATE
                self.server.send_state(self.state)
            if now >= next_stats:
                next_stats = now + STATS_PERIOD_S
                r = self.stats.report()
                log.info("Perf : pas p50 %.2f / p99 %.2f / max %.2f ms ; retard p99 %.1f / max %.1f ms ;"
                         " CPU %.1f %%", r["step_p50_ms"], r["step_p99_ms"], r["step_max_ms"],
                         r["lag_p99_ms"], r["lag_max_ms"], r["cpu_pct"])

            next_tick += DT_PHYSICS
            if next_tick < mono() - 0.5:   # très en retard : on se recale au lieu de rattraper
                next_tick = mono()
            await asyncio.sleep(max(next_tick - mono(), 0.0))

    async def _shutdown(self, tasks: list[asyncio.Task]) -> None:
        log.info("Arrêt du core…")
        if self._journal:
            self._finish(True)   # la séance n'est jamais perdue
        self.driver.set_sim_grade(0.0)
        for p in [*self.inputs, self.driver]:
            if hasattr(p, "stop"):
                p.stop()
        # Laisse le pilote relâcher la résistance (écriture BLE) avant d'annuler.
        done, pending = await asyncio.wait(tasks, timeout=3.0) if tasks else (set(), set())
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self.server.stop()
