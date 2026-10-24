"""Boucle principale du core (SRS §3, §4, §9) : pilotes réels ou simulés, physique, IPC, journal.

Une seule boucle asyncio :
- physique à 50 Hz avec le pas réellement écoulé ;
- trame `state` à 30 Hz vers l'engine, commandes et heartbeat lus à chaque tour ;
- BLE (trainer, Click) dans des tâches asyncio séparées ;
- journal JSONL à 1 Hz ; FIT en fin de séance ;
- entraînements ERG (`.zwo`, SRS §6) : cible de puissance au lieu de la pente, hors roue libre ;
- mesures de performance (durée du pas, retard de boucle, CPU) pour la décision Rust (SRS §14.1).
"""

from __future__ import annotations

import asyncio
import logging
import re
import signal
import time
from pathlib import Path
from typing import Any

from .config import WORKOUTS_DIR, Config
from .gearing import Gearing
from .hr_monitor import HeartRateProvider
from .input_providers import ClickPair, KeyboardProvider, NullProvider, SimClickKeyboard, ZwiftClickProvider
from .ipc_server import IpcServer, IpcState
from .journal import JOURNAL_DIR, Record
from .mock_driver import MockDriver
from .physics import PhysicsParams, RiderPhysics
from .recorder import SessionRecorder
from .demo_world import ensure_demo_world
from .route import Route, WorldError, find_world, load_world, routes_dir
from .workout import BIAS_DEFAULT_PCT, ErgController, Workout, WorkoutError, load_workout, workout_path
from .zwift_click import InputEvent

log = logging.getLogger("core")

DT_PHYSICS = 0.02        # 50 Hz
DT_STATE = 1.0 / 30.0    # 30 Hz
STATS_PERIOD_S = 60.0
SHUTDOWN_GRACE_S = 5.0   # délai laissé aux pilotes pour relâcher le trainer et se déconnecter
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


def build_sim_world(cfg: Config) -> Any:
    """Bluetooth simulé (`ble_sim.py`) si un pilote vaut « sim », sinon None.

    Lève `SimScenarioError` si le scénario (`drivers.sim_scenario`) est inconnu ou invalide.
    """
    d = cfg.drivers
    if "sim" not in (d.trainer, d.input, d.hr):
        return None
    from .sim_scenarios import build_world, load_scenario

    name = d.sim_scenario or "demo"
    world = build_world(load_scenario(name), name, trainer=d.trainer == "sim",
                        click=d.input == "sim", hr=d.hr == "sim")
    log.info("Bluetooth simulé, scénario « %s » (%d événement(s)).", name, len(world.events))
    return world


def build_driver(cfg: Config, sim: Any = None) -> Any:
    if cfg.drivers.trainer in ("ftms", "sim"):
        from .ftms_driver import FtmsDriver
        if cfg.drivers.trainer == "sim":   # vrai pilote, radio simulée
            return FtmsDriver(cfg.trainer, cfg.bike, None, device_finder=sim.find_device,
                              client_factory=sim.client_factory)
        return FtmsDriver(cfg.trainer, cfg.bike, cfg.drivers.trainer_address or None)
    replay = None
    if cfg.drivers.mock_replay:
        from .replay import ReplayError, load_replay
        try:
            replay = load_replay(Path(cfg.drivers.mock_replay).expanduser())
            log.info("Rejeu chargé depuis %s (%d échantillons).", cfg.drivers.mock_replay, len(replay))
        except ReplayError as exc:
            log.error("Rejeu impossible (%s) : démarrage avec le simulateur ordinaire.", exc)
    return MockDriver(replay=replay)


def build_inputs(cfg: Config, sim: Any = None) -> list[Any]:
    kind = cfg.drivers.input
    if kind == "sim":
        # Vrais fournisseurs du Click contre la paire simulée ; le clavier appuie sur le Click simulé.
        d, pair = cfg.drivers, ClickPair()
        return [ZwiftClickProvider(None, d.click_short_max_s, d.click_long_min_s, pair=pair,
                                   device_finder=sim.find_device, client_factory=sim.client_factory),
                ZwiftClickProvider(None, d.click_short_max_s, d.click_long_min_s, pair=pair,
                                   optional=True, device_finder=sim.find_device,
                                   client_factory=sim.client_factory),
                SimClickKeyboard(sim)]
    if kind == "click":
        # Deux fournisseurs pour la paire du Click récent (boîtiers « + » et « − », même nom) ;
        # le clavier reste actif en parallèle (contrat IPC §6).
        d, pair = cfg.drivers, ClickPair()
        return [ZwiftClickProvider(d.click_address or None, d.click_short_max_s, d.click_long_min_s,
                                   pair=pair),
                ZwiftClickProvider(None, d.click_short_max_s, d.click_long_min_s,
                                   pair=pair, optional=True),
                KeyboardProvider()]
    if kind == "keyboard":
        return [KeyboardProvider()]
    return [NullProvider()]


def build_hr(cfg: Config, sim: Any = None) -> HeartRateProvider | None:
    d = cfg.drivers
    if d.hr == "ble":
        return HeartRateProvider(d.hr_address or None, d.hr_name)
    if d.hr == "sim":
        return HeartRateProvider(None, "", device_finder=sim.find_device,
                                 client_factory=sim.client_factory)
    return None


ROUTE_ID_RE = re.compile(r"^[^/\\.][^/\\]*$")   # un nom de dossier simple, comme les entraînements


class AutostartError(Exception):
    """Parcours ou entraînement demandé au lancement (`--route`, `--workout`) refusé."""


class CoreSession:
    def __init__(self, cfg: Config, driver: Any = None, inputs: list[Any] | None = None,
                 journal_dir: Path = JOURNAL_DIR, routes_root: Path | None = None,
                 workouts_dir: Path = WORKOUTS_DIR) -> None:
        self.cfg = cfg
        self.sim = build_sim_world(cfg)
        self.driver = driver if driver is not None else build_driver(cfg, self.sim)
        self.inputs = inputs if inputs is not None else build_inputs(cfg, self.sim)
        self.hr = build_hr(cfg, self.sim)
        self.journal_dir = journal_dir
        self.routes_root = routes_root or routes_dir()
        self.workouts_dir = workouts_dir
        self.gearing = Gearing(cfg.gearing, cfg.trainer)
        self.physics = RiderPhysics(PhysicsParams.from_config(cfg))
        self.route: Route | None = None
        self.state = IpcState(session_state="IDLE", gears_total=self.gearing.n_gears,
                              gear=self.gearing.k)
        self.server = IpcServer(
            port_state=cfg.ipc.port_state, port_commands=cfg.ipc.port_commands,
            on_command=self._on_command, on_engine_lost=self._on_engine_lost,
            on_engine_returned=lambda: log.info("Engine connecté."),
            hello_config={"ftp_w": cfg.rider.ftp_w, "gears_total": self.gearing.n_gears,
                          "theme": cfg.render.theme})
        self.stats = LoopStats()
        self.stop_event = asyncio.Event()

        self._t_session = 0.0
        self._grade_sent = 0.0
        self._power_window: list[tuple[float, float]] = []
        self._rec: SessionRecorder | None = None
        self._device_up: dict[str, bool] = {}   # dernier état écrit au journal (lignes `device`)
        self._next_record = 0.0
        self._trainer_lost_since: float | None = None
        self._autoresume = False
        self._shift_pending = False
        self._workout: Workout | None = None     # entraînement choisi (select_workout)
        self.erg: ErgController | None = None   # entraînement en cours pendant la séance

    # --- machine à états ---------------------------------------------------------------

    def _set_state(self, new: str, reason: str | None = None) -> None:
        old = self.state.session_state
        self.state.session_state, self.state.pause_reason = new, reason
        log.info("Séance : %s -> %s%s", old, new, f" ({reason})" if reason else "")
        now = time.time()
        if self._rec:
            if new == "PAUSED" and old == "RUNNING":
                self._rec.event("pause", now)
            elif new == "RUNNING" and old == "PAUSED":
                self._rec.event("resume", now)
        if new in ("PAUSED", "READY", "FINISHED", "IDLE", "ERROR"):
            self._release_trainer()

    def _release_trainer(self) -> None:
        self._grade_sent = 0.0
        self.driver.set_sim_grade(0.0)

    def _on_command(self, name: str, args: dict, cmd_id: int) -> None:
        log.info("Commande %s %s (id=%d)", name, args, cmd_id)
        st = self.state.session_state
        if name == "select_route" and st in ("IDLE", "READY", "FINISHED", "ERROR"):
            reset = getattr(self.driver, "reset_control", None)
            if reset:
                reset()   # sortie de ERROR : nouvelle prise de contrôle du trainer
            self._select_route(str(args.get("route_id") or "demo"), previous=st)
        elif name == "select_workout" and st in ("IDLE", "READY"):
            self._select_workout(args.get("workout_id"))
        elif name == "start" and st == "READY":
            self._open_journal()
            if self._workout:
                self.erg = ErgController(self._workout, self.cfg.rider.ftp_w)
                log.info("Entraînement « %s » démarré : %d blocs, %.0f s.", self._workout.name,
                         len(self._workout.blocks), self._workout.duration_s)
                self._sync_erg_state()
            self._set_state("RUNNING")
        elif name == "skip_block" and self.erg and st in ("RUNNING", "PAUSED"):
            self._skip_block()
        elif name == "pause" and st == "RUNNING":
            self._set_state("PAUSED", "user")
        elif name == "resume" and st == "PAUSED":
            if self._rec and self._rec.failed and not self._rec.reopen():
                self.server.send_error("recording_failed",
                                       "Journal toujours impossible à écrire : séance en pause.")
                return
            self._trainer_lost_since = None
            self._set_state("RUNNING")
        elif name == "input_event":   # touches lues par l'engine (fenêtre active) : même effet que le Click
            try:
                self._handle_input(InputEvent(args.get("event", "")))
            except ValueError:
                log.warning("input_event inconnu : %s", args.get("event"))
        elif name == "end_session" and st in ("RUNNING", "PAUSED"):
            self._finish(bool(args.get("save", True)))

    def _select_route(self, route_id: str, previous: str) -> None:
        """LOADING, lecture de la couche route du .world, puis READY (contrat §7, étape 6)."""
        self._set_state("LOADING")
        try:
            if route_id == "demo":
                ensure_demo_world(self.routes_root)   # parcours de démonstration commun
            world = load_world(find_world(route_id, self.routes_root))
        except WorldError as exc:
            log.error("Parcours « %s » refusé : %s", route_id, exc)
            self.server.send_error(exc.code, str(exc))
            self._set_state(previous)
            return
        self.route = world.route
        self.erg = None
        self._sync_erg_state()
        self.state.route_id = route_id
        self.state.route_length_m = world.route.length_m
        self.physics.s = self.physics.v = 0.0
        self._t_session = 0.0
        log.info("Parcours « %s » chargé : %.0f m, type %s", route_id, world.route.length_m,
                 world.route.type)
        self._set_state("READY")

    def _select_workout(self, workout_id: Any) -> None:
        """Choisit l'entraînement du prochain `start` ; null revient au SIM (contrat §4)."""
        if workout_id is None or str(workout_id) == "":
            self._workout = None
            log.info("Aucun entraînement : mode SIM.")
            return
        try:
            self._workout = load_workout(workout_path(self.workouts_dir, str(workout_id)))
        except WorkoutError as exc:
            self._workout = None
            log.error("Entraînement « %s » refusé : %s", workout_id, exc)
            self.server.send_error("workout_invalid", f"Entraînement « {workout_id} » invalide : {exc}")
            return
        w = self._workout
        log.info("Entraînement « %s » choisi : %d blocs, %.0f s.", w.name, len(w.blocks), w.duration_s)

    def _skip_block(self) -> None:
        assert self.erg is not None
        self.erg.skip()
        log.info("Bloc suivant demandé.")
        self._sync_erg_state()

    def _sync_erg_state(self) -> None:
        """Recalcule `mode` et l'objet `erg` ; termine l'entraînement après son dernier bloc."""
        erg = self.erg
        if erg and erg.finished:
            log.info("Entraînement « %s » terminé : retour au mode SIM, parcours libre.", erg.workout.name)
            self.erg = erg = None
            self._grade_sent = 0.0   # la pente reprend depuis 0 % avec la limitation de variation
        self.state.mode = "ERG" if erg and not erg.is_freeride else "SIM"
        self.state.erg = erg.to_dict() if erg else None

    def _on_engine_lost(self) -> None:
        if self.state.session_state == "RUNNING":
            log.warning("Engine perdu : pause automatique.")
            self._set_state("PAUSED", "engine_lost")

    # --- journal et FIT ----------------------------------------------------------------

    def _open_journal(self) -> None:
        self._rec = SessionRecorder(self.journal_dir, self.state.route_id,
                                    on_failure=self._on_recording_failure)
        self._rec.event("start", time.time())
        self._device_up = self._device_states()   # état de départ : seuls les changements s'écrivent
        self._next_record = 0.0

    def _click_device(self, address: str) -> str:
        """Boîtier « + » : celui de `click_address` (adresse du « + » réel par défaut)."""
        from .sim_scenarios import PLUS_ADDRESS   # adresse du boîtier « + » réel (CLAUDE.md)
        plus = (self.cfg.drivers.click_address or PLUS_ADDRESS).upper()
        return "click_plus" if address.upper() == plus else "click_minus"

    def _device_states(self) -> dict[str, bool]:
        """État des appareils d'après ce que la session connaît déjà (aucune entrée-sortie BLE)."""
        out: dict[str, bool] = {}
        status = getattr(self.driver, "status", None)
        if status is not None:
            out["trainer"] = status == "CONNECTED"
        elif hasattr(self.driver, "connected"):   # MockDriver
            out["trainer"] = bool(self.driver.connected)
        for p in self.inputs:
            if isinstance(p, ZwiftClickProvider):
                addr = str(getattr(p, "_conn_address", "?"))
                if addr != "?":   # boîtier jamais connecté : inconnu
                    key = self._click_device(addr)
                    out[key] = out.get(key, False) or p.status == "CONNECTED"
        if self.hr is not None:
            out["hr"] = bool(self.hr.connected)
        return out

    def _journal_devices(self) -> None:
        """Écrit une ligne `device` à chaque coupure ou retour (lot M4)."""
        if not self._rec:
            return
        states = self._device_states()
        if states == self._device_up:
            return
        now = round(time.time(), 3)
        for dev, up in states.items():
            before = self._device_up.get(dev)
            if before is not None and before != up:
                self._rec.device(dev, "up" if up else "down", now)
        self._device_up = states

    def _on_recording_failure(self, exc: Exception) -> None:
        """Panne d'écriture du journal : erreur à l'écran et pause (contrat IPC §6)."""
        self.server.send_error("recording_failed", f"Écriture du journal impossible : {exc}")
        if self.state.session_state in ("RUNNING", "PAUSED"):
            self._set_state("PAUSED", "recording_failed")

    def _finish(self, save: bool, final_state: str = "FINISHED") -> None:
        summary = None
        if self._rec:
            rec, self._rec = self._rec, None
            fit_path, s, fit_error = rec.finish(save)
            if fit_error and save:
                self.server.send_error("recording_failed", f"FIT non produit : {fit_error}")
            summary = {
                "duration_s": round(s.timer_s, 1),
                "distance_m": round(s.distance_m, 1),
                "avg_power_w": round(s.avg_power or 0.0, 1),
                "fit_path": str(fit_path) if fit_path else None,
            }
        self.state.summary = summary
        self.erg = None
        self._sync_erg_state()
        self._set_state(final_state)

    # --- entrées utilisateur -------------------------------------------------------------

    def _handle_input(self, ev: InputEvent) -> None:
        # Toujours relayé à l'engine : menu hors séance, retour sonore (bips) pendant la séance.
        self.server.send_input_event(ev.value)
        if self.state.session_state != "RUNNING":
            return
        erg = self.erg
        if erg and (ev in (InputEvent.PLUS_LONG, InputEvent.MINUS_LONG) or not erg.is_freeride):
            # ERG (SRS §4.4) : court ± = biais, long + = bloc suivant, long − = pause ERG.
            # En roue libre, les appuis courts restent des braquets.
            if ev == InputEvent.PLUS_SHORT:
                erg.change_bias(+1)
            elif ev == InputEvent.MINUS_SHORT:
                erg.change_bias(-1)
            elif ev == InputEvent.PLUS_LONG:
                self._skip_block()
                return
            else:
                erg.toggle_pause()
                log.info("ERG %s.", "en pause (pente 0 %)" if erg.paused else "repris")
            self._sync_erg_state()
            return
        n = self.cfg.gearing.long_press_gears
        if ev == InputEvent.PLUS_SHORT:
            self.gearing.shift_up()
        elif ev == InputEvent.MINUS_SHORT:
            self.gearing.shift_down()
        elif ev == InputEvent.PLUS_LONG:
            self.gearing.shift_up(n)     # SIM : saut de plusieurs braquets (essai ; ERG : bloc suivant)
        elif ev == InputEvent.MINUS_LONG:
            self.gearing.shift_down(n)
        self.state.gear = self.gearing.k
        self._shift_pending = True   # le changement de braquet doit se sentir tout de suite

    def _drain_inputs(self) -> None:
        for provider in self.inputs:
            while not provider.events.empty():
                self._handle_input(provider.events.get_nowait())
        # Statut d'entrée : celui du premier fournisseur (Click s'il est configuré) ; la paire de
        # Click est « connectée » dès qu'un des deux boîtiers l'est.
        clicks = [p for p in self.inputs if isinstance(p, ZwiftClickProvider)]
        if any(p.status == "CONNECTED" for p in clicks):
            self.state.input_status = "CONNECTED"
        else:
            self.state.input_status = self.inputs[0].status if self.inputs else "KEYBOARD"

    # --- pas de simulation ---------------------------------------------------------------

    def _step(self, dt: float, now_mono: float) -> None:
        m = self.driver.poll(self._t_session)
        self.state.trainer_status = getattr(self.driver, "status", "MOCK")
        self._journal_devices()
        if self.hr is not None and self.hr.bpm is not None:
            m.hr_bpm = self.hr.bpm   # la ceinture passe avant la fréquence lue par le trainer

        if getattr(self.driver, "control_refused", False) and \
                self.state.session_state in ("READY", "RUNNING", "PAUSED"):
            log.error("Le trainer refuse le contrôle FTMS après deux reprises.")
            self.server.send_error("trainer_control_refused",
                                   "Le trainer refuse les consignes (contrôle FTMS refusé).")
            if self._rec:
                self._finish(True, final_state="ERROR")   # la séance n'est jamais perdue
            else:
                self._set_state("ERROR")
            return

        if self._autoresume and self.state.session_state == "PAUSED":
            reason = self.state.pause_reason
            if (reason == "trainer_lost" and m.connected) or \
                    (reason == "engine_lost" and self.server.engine_connected):
                self._on_command("resume", {}, 0)   # essais sans menu : reprise automatique
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
        if self.erg:
            self.erg.step(dt)        # le temps du bloc ne court que pendant RUNNING
            self._sync_erg_state()
        erg = self.erg
        s = self.physics.s
        tau = self.cfg.trainer.latency_tau_s
        route = self.route
        here = route.sample(s) if route else None           # sample ramène s sur le parcours (boucle)
        grade = here.grade_pct if here else 0.0
        ahead = route.grade_at(s + self.physics.v * tau) if route else 0.0
        alt = here.alt_m if here else 0.0

        if erg and erg.target_active:
            # ERG : cible de puissance, aucune pente envoyée ; la physique garde la pente du terrain.
            self._grade_sent = 0.0
            self.driver.set_target_power(erg.target_w)
        elif erg and erg.paused:
            self._grade_sent = 0.0   # pause ERG : pente 0 % en SIM (SRS §4.4)
            self.driver.set_sim_grade(0.0)
        else:
            # Pente envoyée : anticipée de la latence du trainer, braquet appliqué, variation limitée.
            target = self.gearing.effective_grade(ahead, self.cfg.trainer.difficulty_pct / 100.0)
            max_delta = self.cfg.trainer.grade_rate_pct_per_s * dt
            shifted = self._shift_pending
            if shifted:   # braquet : pas de limitation de vitesse (seul le relief est lissé)
                self._shift_pending = False
                self._grade_sent = target
            else:
                self._grade_sent += min(max(target - self._grade_sent, -max_delta), max_delta)
            self.driver.set_sim_grade(self._grade_sent, immediate=shifted)

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
        if here:
            st.lat, st.lon, st.alt = here.lat, here.lon, alt

        if self._rec and self._t_session >= self._next_record:
            self._next_record += 1.0
            self._rec.record(Record(
                ts=round(time.time(), 3), t=round(self._t_session, 2), lat=st.lat, lon=st.lon,
                alt=round(alt, 2), distance=round(st.s, 2), speed=round(st.v, 3),
                power=round(m.power_w), cadence=round(m.cadence_rpm), hr=m.hr_bpm,
                grade=round(grade, 2), mode=st.mode, gear=self.gearing.k, grade_sent=st.grade_sent,
                block=erg.index + 1 if erg else None,
                target_w=erg.target_w if erg and erg.target_active else None,
                erg_bias_pct=erg.bias_pct - BIAS_DEFAULT_PCT if erg and erg.target_active else None))

        if route and not route.is_loop and st.s >= route.length_m:   # une boucle ne finit pas
            log.info("Arrivée atteinte.")
            self._finish(True)

    # --- boucle principale ---------------------------------------------------------------

    def check_autostart(self, route_id: str, workout_id: str | None) -> None:
        """Vérifie parcours et entraînement d'un `--autostart` avant d'ouvrir les ports (lot J1).

        Lève `AutostartError` avec un message clair : aucune séance ne démarre sur un mauvais
        parcours ou sans l'entraînement demandé.
        """
        if not ROUTE_ID_RE.match(route_id):
            raise AutostartError(f"identifiant de parcours invalide : {route_id!r}")
        try:
            if route_id == "demo":
                ensure_demo_world(self.routes_root)
            load_world(find_world(route_id, self.routes_root))
        except WorldError as exc:
            raise AutostartError(f"parcours « {route_id} » refusé : {exc}") from exc
        if workout_id:
            try:
                load_workout(workout_path(self.workouts_dir, workout_id))
            except WorkoutError as exc:
                raise AutostartError(f"entraînement « {workout_id} » refusé : {exc}") from exc

    async def run(self, autostart: bool = False, route_id: str = "demo",
                  workout_id: str | None = None) -> None:
        """Boucle de séance. Avec `autostart` : select_route, select_workout éventuel, puis start.

        Lève `AutostartError` avant d'ouvrir les ports IPC si le parcours ou l'entraînement
        demandé est refusé.
        """
        if autostart:
            self.check_autostart(route_id, workout_id)
        self.server.start()
        tasks = [asyncio.create_task(p.run(), name=type(p).__name__)
                 for p in self._services() if hasattr(p, "run")]  # trainer prioritaire
        loop = asyncio.get_running_loop()
        # SIGHUP : terminal fermé. Sans gestionnaire, le processus mourrait sans relâcher le
        # trainer et BlueZ garderait la liaison ouverte (trainer réservé pour les autres applis).
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            try:
                loop.add_signal_handler(sig, self.stop_event.set)
            except NotImplementedError:
                pass
        if autostart:
            self._autoresume = True
            self._on_command("select_route", {"route_id": route_id}, 0)
            if workout_id:
                self._on_command("select_workout", {"workout_id": workout_id}, 0)
            self._on_command("start", {}, 0)
        log.info("Core démarré (trainer=%s, entrées=%s).", self.cfg.drivers.trainer,
                 self.cfg.drivers.input)   # format lu par tools/log_report.py
        if self.hr is not None:
            log.info("Ceinture cardio : %s.", self.cfg.drivers.hr)
        try:
            await self._loop()
        finally:
            await self._shutdown(tasks)

    def _services(self) -> list[Any]:
        """Tâches de fond : trainer, entrées, ceinture, puis le déroulé du Bluetooth simulé."""
        return [self.driver, *self.inputs, *([self.hr] if self.hr else []),
                *([self.sim] if self.sim else [])]

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
                # Échéances fixes : « now + DT_STATE » ne tomberait qu'un pas de 20 ms sur deux (25 Hz).
                next_state += DT_STATE
                if next_state <= now:   # retard de plus d'une trame : on se recale
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
        try:
            if self._rec:
                self._finish(True)   # la séance n'est jamais perdue
        except Exception:
            # Une panne du journal ou du FIT ne doit pas empêcher de relâcher le trainer.
            log.exception("Fin de séance incomplète")
        finally:
            await self._stop_drivers(tasks)
            self.server.stop()

    async def _stop_drivers(self, tasks: list[asyncio.Task]) -> None:
        """Annule la consigne, arrête les pilotes et leur laisse le temps de rendre le trainer."""
        try:
            self.driver.set_sim_grade(0.0)
        except Exception:
            log.exception("Consigne 0 % impossible")
        for p in [*self.inputs, *([self.hr] if self.hr else []), self.driver,
                  *([self.sim] if self.sim else [])]:
            if hasattr(p, "stop"):
                p.stop()
        # Le pilote écrit pente 0 % puis Reset (chacun borné à 1,5 s) puis se déconnecte.
        done, pending = await asyncio.wait(tasks, timeout=SHUTDOWN_GRACE_S) if tasks else (set(), set())
        for t in pending:
            log.warning("Arrêt forcé de %s", t.get_name())
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
