"""Boucle principale du core (SRS §3, §4, §9) : pilotes réels ou simulés, physique, IPC, journal.

Une seule boucle asyncio :
- physique à 50 Hz avec le pas réellement écoulé ;
- trame `state` à 30 Hz vers l'engine, commandes et heartbeat lus à chaque tour ;
- BLE (trainer, Click) dans des tâches asyncio séparées ;
- journal JSONL à 1 Hz ; FIT en fin de séance ;
- entraînements ERG (`.zwo`, SRS §6) : cible de puissance au lieu de la pente, jamais sous 50 W (pas de roue libre, lot O19) ;
- mesures de performance (durée du pas, retard de boucle, CPU) pour la décision Rust (SRS §14.1).
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import math
import re
import signal
import threading
import time
import zlib
from collections import deque
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Callable

from .classic import ClassicRace, GainJob
from .config import GPX_DIR, OPENRIDE_HOME, PLANS_DIR, WORKOUTS_DIR, Config
from .equipment import segment_time_gain
from .gearing import Gearing
from .hr_monitor import HeartRateProvider
from .jitter import JitterMeter
from .jitter import line as jitter_line
from .input_providers import ClickPair, KeyboardProvider, NullProvider, SimClickKeyboard, ZwiftClickProvider
from . import latency_log
from .ipc_lists import summary_extras
from .ipc_server import IpcServer, IpcState
from .journal import Record
from .progression import journal_source
from .mock_driver import MockDriver
from .garage import GarageError, ProgressionService, estimate_w_prime, workout_duration_finder
from .open_world import CHOICE_EVENTS, OpenWorld, OpenWorldError
from .open_world_save import save_ride
from .physics import PhysicsParams, RiderPhysics
from . import surface_physics
from . import powerups as powerups_mod, profiles
from .powerups import PowerUpError, load_table
from .records import RecordBook, RecordsError
from .recorder import SessionRecorder
from .resume import ResumeError, ResumeState, close_interrupted, interrupted_sessions, load_resume_state
from .rogue import mode as rogue_mode
from .demo_world import ensure_demo_world
from .route import Route, WorldError, find_world, load_world, routes_dir
from . import draft as draft_mod
from .wind import CALM, WindModel, grade_offset_pct, head_component, wind_frame
from .wtf import rules as wtf_rules
from .wtf.events import WtfInput
from .wtf.mode import WtfMode
from .free_erg import CadenceLock, FreeErg, start_cadence, start_power
from .ftp_test import KINDS as FTP_TEST_KINDS
from .ftp_test import FtpResult, RampWatch, cooldown_index, estimate_ftp
from .ftp_test import kind_of as ftp_test_kind
from .ftp_test import workout_for as ftp_test_workout
from .workout import BIAS_DEFAULT_PCT, ErgController, Workout, WorkoutError, load_workout, workout_path
from .zwift_click import InputEvent

log = logging.getLogger("core")

DT_PHYSICS = 0.02        # 50 Hz
SCAN_ATTEMPTS = 3        # recherche du menu Appareils : essais si BlueZ répond « InProgress »
DT_STATE = 1.0 / 30.0    # 30 Hz
STATS_PERIOD_S = 60.0
SHUTDOWN_GRACE_S = 5.0   # délai laissé aux pilotes pour relâcher le trainer et se déconnecter
MAX_STEP_S = 0.1         # un pas plus long (gel du processus) est borné
# Biais ERG par appui de + ou − (§7.1) : petit pas ± 2 %, grand pas ± 10 % (cinq pas de BIAS_STEP_PCT).
BIAS_STEPS = {InputEvent.PLUS_SHORT: +1, InputEvent.MINUS_SHORT: -1, InputEvent.PLUS_LONG: +5, InputEvent.MINUS_LONG: -5}
WIND_FRAME_EVERY = 15    # champ `wind` 2 fois par seconde (contrat IPC révision 1.3)
DEFAULT_THEME_JSON = Path(__file__).resolve().parents[3] / "engine" / "themes" / "default" / "theme.json"


CONTENT_COMMANDS = ("list_contents", "install_content")   # lot O25
CONTENT_PROGRESS_PERIOD_S = 1.0   # message `contents` pendant une installation, une fois par seconde au plus
PROFILE_COMMANDS = ("list_profiles", "select_profile", "create_profile", "rename_profile", "delete_profile")   # lot MJ7
XP_RESULT_REPEATS = 10      # `xp_result` répété tant que la séance reste FINISHED (contrat 1.4, D7)
W_PRIME_ESTIMATE_WAIT_S = 3.0   # attente du W' estimé avant le premier hello_ack (lot R16)
XP_RESULT_PERIOD_S = 1.0


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
        if cfg.drivers.trainer == "sim":
            # Vrai pilote, radio simulée. Le trainer simulé est cherché sous son propre nom : celui de
            # config.toml est souvent le nom du vrai trainer, écrit par l'appairage (lot N12), qui le cachait.
            trainer = replace(cfg.trainer, device_name=sim.trainer.name) if sim.trainer else cfg.trainer
            return FtmsDriver(trainer, cfg.bike, None, device_finder=sim.find_device,
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


def click_side_of(d: Any) -> Callable[[str], str | None]:
    """Côté d'un boîtier du Click d'après son adresse, pour le journal du lot Q6 : « + » à droite, « − » à
    gauche. None sans adresse configurée (premier boîtier vu inconnu d'avance)."""
    def side_of(address: str) -> str | None:
        addr = address.upper()
        if d.click_address:
            return "droit" if addr == d.click_address.upper() else "gauche"
        if d.click_minus_address:
            return "gauche" if addr == d.click_minus_address.upper() else "droit"
        if d.input == "sim":
            from .sim_scenarios import PLUS_ADDRESS
            return "droit" if addr == PLUS_ADDRESS else "gauche"
        return None
    return side_of


def build_inputs(cfg: Config, sim: Any = None) -> list[Any]:
    kind = cfg.drivers.input
    d = cfg.drivers
    # Réglages du lot Q6 (trace brute, boîtier muet, reprise), communs aux deux boîtiers.
    q6 = {"trace_raw": d.click_trace_raw, "mute_after_s": d.click_mute_after_s,
          "rehandshake_s": d.click_rehandshake_s, "reset_locked": d.click_reset_locked, "side_of": click_side_of(d)}
    if kind == "sim":
        # Vrais fournisseurs du Click contre la paire simulée ; le clavier appuie sur le Click simulé.
        pair = ClickPair()
        return [ZwiftClickProvider(None, d.click_short_max_s, d.click_long_min_s, pair=pair,
                                   device_finder=sim.find_device, client_factory=sim.client_factory, **q6),
                ZwiftClickProvider(None, d.click_short_max_s, d.click_long_min_s, pair=pair,
                                   optional=True, device_finder=sim.find_device,
                                   client_factory=sim.client_factory, **q6),
                SimClickKeyboard(sim)]
    if kind == "click":
        # Deux fournisseurs pour la paire du Click récent (boîtiers « + » et « − », même nom) ;
        # le clavier reste actif en parallèle (contrat IPC §6).
        pair = ClickPair()
        return [ZwiftClickProvider(d.click_address or None, d.click_short_max_s, d.click_long_min_s,
                                   pair=pair, **q6),
                ZwiftClickProvider(d.click_minus_address or None, d.click_short_max_s,
                                   d.click_long_min_s, pair=pair, optional=True, **q6),
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


def theme_wind(theme: str, themes_dir: Path | None = None) -> dict | None:
    """Objet `wind` du thème 1.2 choisi (`[render] theme`), sinon du thème par défaut ; None s'il manque."""
    candidates = [(themes_dir or OPENRIDE_HOME / "Themes") / theme / "theme.json", DEFAULT_THEME_JSON]
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("wind"), dict):
            return data["wind"]
    return None


class AutostartError(Exception):
    """Parcours ou entraînement demandé au lancement (`--route`, `--workout`) refusé."""


class CoreSession:
    def __init__(self, cfg: Config, driver: Any = None, inputs: list[Any] | None = None,
                 journal_dir: Path | None = None, routes_root: Path | None = None,
                 workouts_dir: Path = WORKOUTS_DIR, bots: list[Any] | None = None,
                 config_path: Path | None = None, records_path: Path | None = None,
                 powerups_path: Path | None = None, profile_path: Path | None = None,
                 wtf_path: Path | None = None) -> None:
        # Fichiers du joueur : ceux du profil en cours (série MJ, lot MJ1), sauf chemins donnés (tests).
        self.profile_ctx = profiles.current()
        self.cfg = cfg
        self.config_path = config_path   # écrit par pair_devices (lot N13) ; défaut ~/OpenRide/config.toml
        self.bots = list(bots) if bots else []
        self._cli_bots = self.bots   # ceux de la ligne de commande, remis quand `start` n'a pas de `bots`
        self.sim = build_sim_world(cfg)
        self.driver = driver if driver is not None else build_driver(cfg, self.sim)
        if hasattr(self.driver, "event_sink"):   # statuts du trainer et perte de frein au journal
            self.driver.event_sink = lambda line: self._rec.ftms(line) if self._rec else None
        self.inputs = inputs if inputs is not None else build_inputs(cfg, self.sim)
        self.hr = build_hr(cfg, self.sim)
        self.journal_dir = journal_dir if journal_dir is not None else self.profile_ctx.journal_dir
        self.routes_root = routes_root or routes_dir()
        self.workouts_dir = workouts_dir
        self.gearing = Gearing(cfg.gearing, cfg.trainer)
        self.progress_svc = self._build_progression(profile_path)   # série V (lot V11)
        # Paramètres sans bonus de la série T (lot T7), avec le cadre et les roues choisis (série V)
        self._base_params = self._equipped_params()
        self.physics = RiderPhysics(self._base_params)
        self._build_wind()
        self._head_mps = 0.0          # vent de face au point s (physique à 50 Hz)
        self._wind_offset = 0.0       # supplément de pente dû au vent (feel = "grade")
        self._gravel_factor = 1.0     # roulement multiplié des routes non revêtues (lot U21)
        self._gravel_offset = 0.0     # supplément de pente du gravel avant la borne commune
        self._gravel_sent = 0.0       # part du gravel envoyée en SIM, après la borne commune
        self._gravel_stats = [0.0, 0.0, 0.0, 0]   # m non revêtus, m parcourus, somme des suppléments, pas SIM
        self._wind_pending = False    # trame `wind` décalée parce que la trame portait `devices`
        self._draft = 0.0             # abri lissé derrière un bot (lot P3)
        self._draft_bot: str | None = None
        self._bot_cda = {id(b): b.params.cda_m2 for b in self.bots if getattr(b, "params", None)}
        self.route: Route | None = None
        self._segments: tuple = ()               # couche segments du parcours (série T)
        self.race: ClassicRace | None = None      # mode classique de la séance (lot T7)
        self.records_path: Path = records_path or self.profile_ctx.records_path  # lot T5
        self.powerups_path: Path = powerups_path or powerups_mod.POWERUPS_FILE  # lot T6
        self.wtf_path: Path = wtf_path or wtf_rules.WTF_FILE   # règles du mode WTF (lot WTF2)
        self.wtf: WtfMode | None = None
        self._records_writable = True
        self.difficulty_pct: float = float(cfg.trainer.difficulty_pct)
        self.state = IpcState(session_state="IDLE", gears_total=self.gearing.n_gears,
                              gear=self.gearing.k, difficulty_pct=round(self.difficulty_pct))
        self.server = IpcServer(
            port_state=cfg.ipc.port_state, port_commands=cfg.ipc.port_commands,
            on_command=self._on_command, on_engine_lost=self._on_engine_lost,
            on_engine_returned=lambda: log.info("Engine connecté."),
            hello_config={"ftp_w": cfg.rider.ftp_w, "hr_max_bpm": cfg.rider.hr_max_bpm, "gears_total": self.gearing.n_gears,
                          "theme": cfg.render.theme, "chart": cfg.render.chart,
                          "difficulty_pct": round(self.difficulty_pct),
                          "open_world_dir": str(Path(cfg.open_world.cache_dir).expanduser() / "seances")})
        self._publish_progression()
        log.info("Difficulté du trainer : %d %%", round(self.difficulty_pct))
        log.info("Rampe de pente du trainer : +%.1f %%/s (montée), -%.1f %%/s (descente)",
                 cfg.trainer.grade_rate_up_pct_per_s, cfg.trainer.grade_rate_down_pct_per_s)
        self.stats = LoopStats()
        self.stop_event = asyncio.Event()

        self._t_session = 0.0
        self._grade_sent = 0.0
        self._power_window: deque[tuple[float, float]] = deque()   # (temps de séance, W) des 3 dernières s
        self._rec: SessionRecorder | None = None
        self.dropout_marks = 0   # repères « décrochage » posés au Z long (§7.1, lot X47)
        self._device_up: dict[str, bool] = {}   # dernier état écrit au journal (lignes `device`)
        self._next_record = 0.0
        self._trainer_lost_since: float | None = None
        self._autoresume = False
        self._shift_pending = False
        self._workout: Workout | None = None     # entraînement choisi (select_workout)
        self._workout_id: str | None = None
        self._click_seen: dict[str, str] = {}   # boîtiers du Click vus, sans adresse configurée
        # Contrôleur ERG de la séance : entraînement en cours, ou ERG d'une session libre (lot O18).
        self.erg: ErgController | FreeErg | None = None
        self._ramp_watch: RampWatch | None = None   # fin de la rampe d'un test de FTP (lot O10)
        self._ftp_result: FtpResult | None = None   # dernier test de FTP, pour `accept_ftp` (lot O12)
        self._plan_day: str | None = None           # séance du jour du dernier message `plans` (lot O12)
        self.plans_dir: Path | None = None          # dossiers des plans (défauts de plans.py ; tests)
        self.plan_state_path: Path | None = None
        self.activities_dir: Path | None = None
        self._frame_count = 0
        self._last_devices: dict[str, Any] | None = None
        self._bg_tasks: set[asyncio.Task[Any]] = set()
        self._contents = None   # contenus du menu (lot O25), créés à la première commande
        self.themes_dir = OPENRIDE_HOME / "Themes"   # thèmes installés, listés dans « Contenus » (lot O29)
        self.first_run = False  # premier lancement (`run --first-run`) : contenus de départ installés seuls
        # Appairage depuis le menu (lot N13) : dernière recherche et identification du « + » en cours.
        self._scan_items: list[dict[str, Any]] = []
        # Menu ERG (lot N16, décision D4 de l'audit IPC) : dossier personnel fouillé par list_imports
        # et chemins proposés à l'engine, seuls acceptés par import_workout.
        self.import_home = Path.home()
        self._import_offer: set[str] = set()
        self._scanning = False
        self._identify: dict[str, Any] | None = None
        # Monde ouvert (lot W9) : générateur et route engagée ; `worldgen_cmd` remplace la commande (essais).
        self.openworld: OpenWorld | None = None
        self.worldgen_cmd: list[str] | None = None
        self.worldmenu: Any = None                 # WorldMenu du lot W11, créé à la première demande ; remplaçable (essais)
        self.worldgen_args: list[str] = []
        self.gpx_dir: Path | None = None        # balades enregistrées (défaut ~/OpenRide/GPX ; essais)
        self._ow_previous = "IDLE"
        # Mode Cyber-Rogue (lot R8) : run en cours ; `rogue_provider()` rend (table des châssis, statistiques,
        # vies) d'après la progression de la série V (lot R9) ; progression coupée : seul le châssis standard.
        self.rogue: rogue_mode.RogueMode | None = None
        self.rogue_provider: Callable[[], tuple] | None = self.progress_svc.rogue_progress
        self._rogue_dist = 0.0
        self.w_prime_estimate_j: float | None = None   # W' estimé des séances passées (lot R16), calculé dans run()
        self.mmp_cache_path: Path | None = None   # None : cache du profil de joueur en cours (série MJ)
        self._publish_rogue()
        # Profils de joueurs (série MJ, lot MJ7) : verrou du profil en cours (posé par `openride-core run`),
        # dossier des profils et fichier lu par le lanceur pour relancer le core sur le bon profil.
        self.profile_lock: profiles.ProfileLock | None = None
        self.profiles_base: Path | None = None   # None : ~/OpenRide/Profils
        self.active_profile_path: Path | None = None   # None : ~/OpenRide/.profil_actif
        self._last_create: tuple[int, Any] | None = None   # dernier create_profile traité (copies ignorées)
        self._publish_profile()
        self._resumed_journal: Path | None = None   # journal repris par `--resume`, jamais proposé (lot O34)

    # --- machine à états ---------------------------------------------------------------

    def _set_state(self, new: str, reason: str | None = None) -> None:
        old = self.state.session_state
        self.state.session_state, self.state.pause_reason = new, reason
        log.info("Séance : %s -> %s%s", old, new, f" ({reason})" if reason else "")
        now = time.time()
        if self._rec:
            if new == "PAUSED" and old == "RUNNING":
                self._rec.event("pause", now, reason or "user")
            elif new == "RUNNING" and old == "PAUSED":
                self._rec.event("resume", now)
        if self.erg:
            self.erg.paused = new == "PAUSED"   # l'ERG suit la pause de la séance (Y), seule pause (§7.1)
            self._sync_erg_state()
        if self.race and new == "PAUSED" and old == "RUNNING":
            self.race.pause(reason or "user")   # pause Y : passages annulés ; coupure subie : suspendus (T4)
        if new in ("PAUSED", "READY", "FINISHED", "IDLE", "ERROR"):
            self._release_trainer()

    def _release_trainer(self) -> None:
        self._grade_sent = 0.0
        if self.rogue is not None:
            self.rogue.grade_sent = 0.0
        self.driver.set_sim_grade(0.0)

    def _on_command(self, name: str, args: dict, cmd_id: int) -> None:
        log.info("Commande %s %s (id=%d)", name, args, cmd_id)
        st = self.state.session_state
        if name == "start_run":
            self._start_run(args if isinstance(args, dict) else {}, st)
        elif name == "rogue_resync":
            if self.rogue is not None:
                for msg in self.rogue.resync():
                    self.server.send_raw(msg)
        elif name == "select_route" and st in ("IDLE", "READY", "FINISHED", "ERROR"):
            self._drop_rogue()
            reset = getattr(self.driver, "reset_control", None)
            if reset:
                reset()   # sortie de ERROR : nouvelle prise de contrôle du trainer
            self._select_route(str(args.get("route_id") or "demo"), previous=st)
        elif name == "select_workout":
            # Accepté aussi après une séance (FINISHED, ERROR) : le menu choisit l'entraînement avant
            # le parcours, et le core reste en FINISHED jusqu'au select_route suivant.
            if st in ("IDLE", "READY", "FINISHED", "ERROR"):
                self._drop_rogue()
                self._select_workout(args.get("workout_id"))
            else:
                log.warning("Entraînement « %s » refusé : séance %s.", args.get("workout_id"), st)
                self.server.send_error("busy", "Choix de l'entraînement impossible pendant une séance.")
        elif name == "start_open_world":
            self._start_open_world(args, st)
        elif name == "choose_branch":
            if self.openworld is None:
                self.server.send_error("unknown_junction", "Pas de monde ouvert en cours.")
            else:
                self.openworld.choose_branch(str(args.get("junction_id") or ""), args.get("branch"), self.physics.s)
        elif name == "list_wtf_rules":
            self._send_wtf_rules()
        elif name == "set_wtf_rule":
            self._set_wtf_rule(args if isinstance(args, dict) else {})
        elif name == "start" and st == "READY":
            game_mode = (args if isinstance(args, dict) else {}).get("mode")
            if game_mode not in (None, "ride", "wtf"):
                self.server.send_error("bad_args", "start : 'mode' vaut ride ou wtf")
                return
            if game_mode == "wtf" and self._workout is not None:
                # Mode WTF : SIM seulement, comme la Course tactique (plan de la série WTF §1).
                self.server.send_error("bad_args", "Le mode WTF se joue sans entraînement ERG.")
                return
            if not self._choose_start_workout(args if isinstance(args, dict) else {}):
                return
            if not self._choose_start_bots(args if isinstance(args, dict) else {}):
                return
            self._open_journal()
            if self._workout:
                self.erg = ErgController(self._workout, self.cfg.rider.ftp_w)
                log.info("Entraînement « %s » démarré : %d blocs, %.0f s.", self._workout.name,
                         len(self._workout.blocks), self._workout.duration_s)
                self._watch_ramp()
                self._sync_erg_state()
            if game_mode == "wtf":
                self._start_wtf()
            self._new_race(classic=self.wtf is None)
            self._set_state("RUNNING")
        elif name == "skip_block" and self._workout_erg() and st in ("RUNNING", "PAUSED"):
            self._skip_block()
        elif name == "set_ride_mode":
            self._set_ride_mode(args if isinstance(args, dict) else {}, st)
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
        elif name == "set_difficulty":
            raw_pct = args.get("pct") if isinstance(args, dict) else None
            if raw_pct is None or isinstance(raw_pct, bool) or not isinstance(raw_pct, (int, float)) \
                    or not math.isfinite(raw_pct):
                self.server.send_error("bad_args", "set_difficulty attend un nombre 'pct'")
                return
            new_val = int(round(max(0, min(100, float(raw_pct)))))
            old_val = round(self.difficulty_pct)
            if new_val != old_val:
                log.info("Difficulté : %d %% -> %d %%", old_val, new_val)
            self.difficulty_pct = float(new_val)
            self.state.difficulty_pct = new_val
            if self.server.hello_config:
                self.server.hello_config["difficulty_pct"] = new_val
            self._save_difficulty(new_val)
        elif name == "list_routes":
            self._spawn(self._handle_list_routes(cmd_id))
        elif name == "list_workouts":
            self._spawn(self._handle_list_workouts(cmd_id))
        elif name in ("world_search", "world_map", "world_regions", "world_pin"):
            self._spawn(self._handle_world_menu(name, args if isinstance(args, dict) else {}, cmd_id))
        elif name in ("scan_devices", "identify_click_plus", "pair_devices"):
            self._on_pairing_command(name, args, cmd_id)
        elif name == "list_settings":
            self._send_settings(cmd_id)
        elif name == "set_setting":
            self._set_setting(args, cmd_id)
        elif name in ("list_plans", "start_plan", "stop_plan", "create_plan"):
            self._on_plan_command(name, args if isinstance(args, dict) else {}, cmd_id)
        elif name == "accept_ftp":
            self._accept_ftp(args if isinstance(args, dict) else {}, cmd_id)
        elif name in ("list_imports", "create_workout", "import_workout"):
            self._on_workout_menu_command(name, args, cmd_id)
        elif name in ("list_garage", "equip", "buy", "set_avatar"):
            self._on_garage_command(name, args if isinstance(args, dict) else {}, cmd_id)
        elif name in PROFILE_COMMANDS:
            self._on_profile_command(name, args if isinstance(args, dict) else {}, cmd_id)
        elif name == "recover_session":
            self._recover_session(args if isinstance(args, dict) else {}, cmd_id)
        elif name in CONTENT_COMMANDS:
            self._on_content_command(name, args if isinstance(args, dict) else {}, cmd_id)

    # --- contenus installables depuis le menu (lot O25, contrat IPC révision 1.5) ---------------

    def _content_service(self):
        from .contents import ContentDirs, ContentService

        if self._contents is None:
            plans_dir = self.plans_dir if self.plans_dir is not None else PLANS_DIR
            self._contents = ContentService(ContentDirs(
                self.workouts_dir, plans_dir, self.routes_root, gpx=GPX_DIR, themes=self.themes_dir,
                home=self.import_home, themes_max_gb=self.cfg.render.theme_library_gb))
        return self._contents

    def _send_contents(self, cmd_id: int) -> None:
        svc = self._content_service()
        try:
            asyncio.get_running_loop()
        except RuntimeError:   # hors boucle (essais) : calcul sur place
            self.server.send_raw(svc.message(cmd_id))
            return

        async def send() -> None:
            self.server.send_raw(await asyncio.to_thread(svc.message, cmd_id))

        self._spawn(send())

    def _on_content_command(self, name: str, args: dict, cmd_id: int) -> None:
        from .contents import ContentError

        if name == "list_contents":
            self._send_contents(cmd_id)
            return
        if self.state.session_state in ("RUNNING", "PAUSED"):
            self.server.send_error("busy", "Contenus installables seulement hors séance (terminer d'abord).")
            return
        try:
            job = self._content_service().start(str(args.get("id") or ""))
        except ContentError as exc:
            self.server.send_error("content_invalid", f"Contenu refusé : {exc}")
            return
        log.info("Installation du contenu « %s ».", job.id)
        self._spawn(self._install_content(job, cmd_id))

    async def _install_content(self, job, cmd_id: int) -> None:
        """Installation dans un fil ; message `contents` au départ, chaque seconde puis à la fin."""
        svc = self._content_service()
        self.server.send_raw(svc.message(cmd_id))
        work = asyncio.create_task(asyncio.to_thread(svc.run, job))
        last = -1
        while not work.done():
            await asyncio.wait({work}, timeout=CONTENT_PROGRESS_PERIOD_S)
            if not work.done() and job.progress_pct != last:
                last = job.progress_pct
                self.server.send_raw(svc.message(cmd_id))
        await work
        log.info("Contenu « %s » : %s", job.id, job.message)
        if job.failed:
            self.server.send_error("content_failed", job.message)
        self.server.send_raw(await asyncio.to_thread(svc.message, cmd_id))

    # --- profils de joueurs (série MJ, lot MJ7, contrat IPC révision 1.5) ------------------------

    def _profile_block(self) -> dict[str, Any] | None:
        """`hello_ack.config.profile` : profil en cours et nombre de profils joueur ; None sans profil."""
        ctx = self.profile_ctx
        if ctx.id is None:
            return None
        count = sum(not c.is_trial for c in profiles.list_contexts(self.profiles_base))
        return {"id": ctx.id, "name": ctx.name or ctx.id, "type": ctx.type, "count": count}

    def _publish_profile(self) -> None:
        block = self._profile_block()
        if block is None:
            self.server.hello_config.pop("profile", None)
        else:
            self.server.hello_config["profile"] = block

    def _profiles_message(self, cmd_id: int) -> dict[str, Any]:
        """Message `profiles` : profils joueur triés par nom, le profil d'essai seulement s'il est en cours."""
        from .garage import profile_summary

        workouts = workout_duration_finder(self.workouts_dir)
        items = [profile_summary(c, workouts) for c in profiles.list_contexts(self.profiles_base)
                 if not c.is_trial or c.id == self.profile_ctx.id][:profiles.MAX_PROFILES]
        return {"type": "profiles", "v": 1, "request_cmd_id": cmd_id, "active": self.profile_ctx.id, "items": items}

    def _send_profiles(self, cmd_id: int) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:   # hors boucle (essais) : calcul sur place
            self.server.send_raw(self._profiles_message(cmd_id))
            return

        async def send() -> None:
            self.server.send_raw(await asyncio.to_thread(self._profiles_message, cmd_id))

        self._spawn(send())

    def _on_profile_command(self, name: str, args: dict, cmd_id: int) -> None:
        if name == "list_profiles":
            self._send_profiles(cmd_id)
            return
        if self.state.session_state not in ("IDLE", "READY", "FINISHED", "ERROR"):
            self.server.send_error("busy", "Profils modifiables seulement hors séance (terminer d'abord).")
            return
        base = self.profiles_base
        try:
            if name == "select_profile":
                self._select_profile(profiles.ProfileContext.for_id(profiles.check_id(str(args.get("id") or "")), base),
                                     cmd_id)
            elif name == "create_profile":
                if self._last_create == (cmd_id, args.get("name")):
                    self._send_profiles(cmd_id)   # copie d'une commande déjà traitée : pas de second profil
                    return
                ctx = profiles.create(args.get("name"), base)
                self._last_create = (cmd_id, args.get("name"))
                log.info("Profil créé : %s (%s).", ctx.name, ctx.id)
                self._select_profile(ctx, cmd_id)
                self._send_profiles(cmd_id)
            elif name == "rename_profile":
                ctx = profiles.rename(args.get("id"), args.get("name"), base)
                log.info("Profil renommé : %s → %s.", ctx.id, ctx.name)
                if ctx.id == self.profile_ctx.id:
                    self.profile_ctx = ctx
                    self._publish_profile()
                self._send_profiles(cmd_id)
            else:
                dest = profiles.delete(args.get("id"), self.profile_ctx.id, base)
                log.info("Profil mis à la corbeille : %s.", dest)
                self._publish_profile()
                self._send_profiles(cmd_id)
        except profiles.ProfileNameError as exc:
            log.warning("Profil : %s refusé : %s", name, exc)
            self.server.send_error("name_invalid", str(exc))
        except (profiles.ProfileContextError, OSError) as exc:
            log.warning("Profil : %s refusé : %s", name, exc)
            self.server.send_error("profile_invalid", str(exc))

    def _select_profile(self, ctx: profiles.ProfileContext, cmd_id: int) -> None:
        """Change de profil sans relancer : configuration effective, progression, records, plan et
        dossier des séances rechargés ; liaison du trainer et du Click gardée ; `hello_ack` complet,
        puis `settings` et `progression`. Lève `ProfileContextError` (rien n'a changé)."""
        from . import config as config_mod

        old_ctx, old_lock = self.profile_ctx, self.profile_lock
        if ctx.id == old_ctx.id:
            self._send_profile_reload(cmd_id)
            return
        lock = profiles.ProfileLock(ctx)
        lock.acquire()   # profil déjà utilisé par une autre séance : ProfileContextError
        profiles.activate(ctx)
        try:
            profiles.ensure_description(ctx)
            cfg = config_mod.load(self.config_path)
        except (config_mod.ConfigError, OSError) as exc:
            profiles.activate(old_ctx)
            lock.release()
            raise profiles.ProfileContextError(f"profil « {ctx.label} » illisible : {exc}") from None
        if old_lock is not None:
            old_lock.release()
        self.profile_lock = lock
        self.profile_ctx = ctx
        old_hr = (self.cfg.drivers.hr, self.cfg.drivers.hr_address)
        self.cfg = cfg
        self.journal_dir = ctx.journal_dir
        self.records_path = ctx.records_path
        self.progress_svc = self._build_progression(None)
        self.rogue_provider = self.progress_svc.rogue_progress
        self._base_params = self._equipped_params()
        self.physics.p = self._base_params
        self._build_wind()
        self.gearing.k = min(max(cfg.gearing.start_gear, 1), self.gearing.n_gears)
        self.difficulty_pct = float(cfg.trainer.difficulty_pct)
        self.state.difficulty_pct = round(self.difficulty_pct)
        if (cfg.drivers.hr, cfg.drivers.hr_address) != old_hr:
            self._swap_hr()
        self.server.hello_config.update(ftp_w=cfg.rider.ftp_w, hr_max_bpm=cfg.rider.hr_max_bpm, theme=cfg.render.theme,
                                        chart=cfg.render.chart, difficulty_pct=round(self.difficulty_pct))
        self._publish_progression()
        self.w_prime_estimate_j = None
        self._publish_rogue()
        self._note_profile()
        log.info("Profil de joueur : %s (%s)%s.", ctx.id, ctx.root, " — PROFIL D'ESSAI" if ctx.is_trial else "")
        self._send_profile_reload(cmd_id)
        try:
            asyncio.get_running_loop()
            self._spawn(self._publish_w_prime_estimate())   # W' du nouveau profil, au hello_ack suivant
        except RuntimeError:
            pass

    def _send_profile_reload(self, cmd_id: int) -> None:
        self._publish_profile()
        self._publish_interrupted()
        self.server.send_hello_ack(self.server.hello_config)
        self._send_settings(cmd_id)
        if self.progress_svc.enabled and self.progress_svc.progression_dict() is not None:
            self.server.send_raw(self.progress_svc.progression_message(cmd_id))

    # --- séance interrompue d'un lancement précédent (lot O34, contrat IPC révision 1.5) -------------

    def _publish_interrupted(self) -> None:
        """`hello_ack.config.interrupted` : séances interrompues du profil sans FIT (absent s'il n'y en a pas)."""
        items = interrupted_sessions(self.journal_dir, skip=self._resumed_journal)
        if items:
            self.server.hello_config["interrupted"] = items
        else:
            self.server.hello_config.pop("interrupted", None)

    def _recover_session(self, args: dict, cmd_id: int) -> None:
        """`recover_session` : enregistre (FIT) ou non une séance interrompue, puis la retire de la liste ;
        réponse `interrupted`. Hors séance seulement, comme les profils."""
        if self.state.session_state not in ("IDLE", "READY", "FINISHED", "ERROR"):
            self.server.send_error("busy", "Séance interrompue : à traiter hors séance.")
            return
        known = [it["id"] for it in self.server.hello_config.get("interrupted", [])]
        sid, save = args.get("id"), args.get("save")
        if sid not in known or not isinstance(save, bool):
            self.server.send_error("bad_args", "recover_session : 'id' d'une séance proposée et 'save' booléen")
            return
        try:
            fit = close_interrupted(self.journal_dir / sid, save)
        except ResumeError as exc:
            self.server.send_error("bad_args", str(exc))
            return
        except (OSError, ValueError) as exc:
            log.error("Séance interrompue %s non enregistrée : %s", sid, exc)
            self.server.send_error("recording_failed", f"Séance non enregistrée : {exc}")
            return
        log.info("Séance interrompue %s %s.", sid, f"enregistrée : {fit}" if fit else "terminée sans FIT")
        self._publish_interrupted()
        self.server.send_raw({"type": "interrupted", "v": 1, "request_cmd_id": cmd_id, "id": sid, "saved": fit is not None,
                              "fit_path": str(fit) if fit else None,
                              "items": self.server.hello_config.get("interrupted", [])})

    def _note_profile(self) -> None:
        """`.profil_actif` pour le lanceur ; `[profils] dernier` pour un profil de joueur seulement."""
        from . import config as config_mod
        from . import config_edit

        ctx = self.profile_ctx
        try:
            profiles.write_active(ctx, self.active_profile_path)
        except OSError as exc:
            log.warning("Profil en cours non noté : %s", exc)
        if ctx.id is None or ctx.is_trial or (self.sim is not None and self.config_path is None):
            return
        try:
            config_edit.update_config(self.config_path or config_mod.DEFAULT_CONFIG_PATH, [("profils", "dernier", ctx.id)])
        except config_edit.ConfigEditError as exc:
            log.warning("Dernier profil non enregistré : %s", exc)

    def _swap_hr(self) -> None:
        """Ceinture cardio du nouveau profil : l'ancienne s'arrête, la nouvelle est recherchée."""
        if self.hr is not None and hasattr(self.hr, "stop"):
            self.hr.stop()
        self.hr = build_hr(self.cfg, self.sim)
        if self.hr is not None and hasattr(self.hr, "run"):
            try:
                asyncio.get_running_loop()
                self._spawn(self.hr.run())
            except RuntimeError:
                pass
        log.info("Ceinture cardio : %s.", self.cfg.drivers.hr if self.hr is not None else "aucune")

    # --- progression, Garage et bilan d'expérience (série V, lot V11, contrat IPC révision 1.4) ----

    def _build_progression(self, profile_path: Path | None) -> ProgressionService:
        return ProgressionService(self.cfg, self.journal_dir, workout_duration_finder(self.workouts_dir),
                                  profile_path or self.profile_ctx.profile_path, self.profile_ctx.table_path)

    def _equipped_params(self) -> PhysicsParams:
        """Paramètres physiques de la séance : `config.toml` et équipement choisi (cadre, roues)."""
        return self.progress_svc.physics_params(PhysicsParams.from_config(self.cfg))

    def _publish_progression(self) -> None:
        """`hello_ack.config.progression` d'après l'état courant (retiré si la progression est coupée)."""
        config = self.server.hello_config
        progression = self.progress_svc.progression_dict()
        if progression is None:
            config.pop("progression", None)
        else:
            config["progression"] = progression

    def _on_garage_command(self, name: str, args: dict, cmd_id: int) -> None:
        svc = self.progress_svc
        if self.state.session_state not in ("IDLE", "READY"):
            self.server.send_error("busy", "Garage impossible pendant une séance (terminer d'abord).")
            return
        if not svc.enabled:
            self.server.send_error("bad_args", "Progression coupée ([progression] enabled = false).")
            return
        if name == "list_garage":
            for m in svc.garage_messages(cmd_id):
                self.server.send_raw(m)
            return
        try:
            if name == "equip":
                svc.equip(args.get("slot"), args.get("item_id"))
            elif name == "buy":
                svc.buy(args.get("item_id"))
            else:
                svc.set_avatar(args.get("avatar"))
        except GarageError as exc:
            log.warning("Garage : %s refusé (%s) : %s", name, exc.code, exc)
            self.server.send_error(exc.code, str(exc))
            return
        log.info("Garage : %s %s", name, {k: v for k, v in args.items() if k != "avatar"})
        self._base_params = self._equipped_params()   # le cadre et les roues valent pour la séance suivante
        self.physics.p = self._base_params
        self._publish_progression()
        self.server.send_raw(svc.progression_message(cmd_id))

    def _after_session(self, journal: str, records: list[dict] | None) -> None:
        """Bilan d'expérience de la séance qui vient de finir : calcul hors de la boucle, puis envoi."""
        if not self.progress_svc.enabled:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:   # hors boucle (essais) : bilan envoyé une fois
            msg = self._build_xp_result(journal, records)
            self.server.send_raw(msg)
            return
        self._spawn(self._send_xp_result(journal, records))

    def _build_xp_result(self, journal: str, records: list[dict] | None) -> dict[str, Any]:
        svc = self.progress_svc
        old = svc.refresh()
        msg = svc.xp_result(journal, old, records, PhysicsParams.from_config(self.cfg))
        self._publish_progression()
        self._publish_rogue()   # châssis débloqués, vies et dernière run pour la prochaine connexion de l'engine
        return msg

    async def _send_xp_result(self, journal: str, records: list[dict] | None) -> None:
        """`xp_result` à la fin de la séance, répété chaque seconde tant qu'elle reste `FINISHED`."""
        try:
            msg = await asyncio.to_thread(self._build_xp_result, journal, records)
            for i in range(XP_RESULT_REPEATS):
                if self.state.session_state != "FINISHED":
                    break
                self.server.send_raw(msg)
                if i < XP_RESULT_REPEATS - 1:
                    await asyncio.sleep(XP_RESULT_PERIOD_S)
        except Exception:
            log.exception("Bilan d'expérience impossible (%s)", journal)

    # --- plans et test de FTP depuis le menu (lot O12, contrat IPC révision 1.3) ----------------

    # --- mode Cyber-Rogue (lot R8) -------------------------------------------------------------

    def _start_run(self, args: dict, st: str) -> None:
        """`start_run` : compose la run, passe par `LOADING` puis `READY` en mode `ROGUE`."""
        if st not in ("IDLE", "READY", "FINISHED"):
            self.server.send_error("busy", "Une run ne se prépare pas pendant une séance.")
            return
        chassis_table, stats, lives = self.rogue_provider() if self.rogue_provider else (None, None, 0)
        try:
            request = rogue_mode.parse_start_run(args, self.cfg)
            chassis = rogue_mode.choose(chassis_table, stats, request.chassis)
        except rogue_mode.RunInvalid as exc:
            log.warning("start_run refusé : %s", exc)
            self.server.send_error(exc.code, str(exc))
            return
        self._close_open_world()
        self.state.open_world = None
        self._set_state("LOADING")
        # L'équipement de la série V ne s'applique pas dans ce mode : les châssis en tiennent lieu (lot V5).
        plain = PhysicsParams.from_config(self.cfg)
        self.rogue = rogue_mode.RogueMode(self.cfg, request, chassis=chassis, lives=lives, params=plain)
        self.route, self._segments, self.race = None, (), None
        self.erg, self._workout, self._workout_id, self._ramp_watch = None, None, None, None
        self.physics = RiderPhysics(plain)
        self._t_session, self._grade_sent, self._rogue_dist = 0.0, 0.0, 0.0
        self._sync_erg_state()
        self.state.route_id, self.state.route_length_m = None, None   # contrat IPC : null en mode ROGUE
        self.state.gear, self.state.gears_total = self.rogue.gear, self.rogue.balance.gear_max
        self.state.lat = self.state.lon = self.state.alt = None
        self.state.summary = None
        log.info("Run Cyber-Rogue préparée : %s, %d min, graine %d, W' %.0f J, châssis %s, table %s.",
                 request.objective, request.duration_min, request.seed, request.w_prime_j, self.rogue.chassis_id,
                 self.rogue.hash)
        self._set_state("READY")

    def _publish_rogue(self) -> None:
        """`hello_ack.config.rogue` d'après la progression : châssis, vies, dernière run (lots R9, R13), W' estimé (R16)."""
        chassis, stats, lives = self.rogue_provider() if self.rogue_provider else (None, None, 0)
        self.server.hello_config["rogue"] = rogue_mode.hello_block(self.cfg, self.w_prime_estimate_j, chassis,
                                                                   stats, lives)

    def _estimate_w_prime(self) -> float | None:
        """W' estimé depuis les séances passées (FIT et journaux), `None` si l'historique ne suffit pas (lot R16)."""
        return estimate_w_prime(self.journal_dir, self.cfg.rider.ftp_w, self.mmp_cache_path)

    async def _publish_w_prime_estimate(self) -> None:
        """Calcul hors de la boucle à 50 Hz ; publié dans `hello_ack` dès qu'il est prêt."""
        est = await asyncio.to_thread(self._estimate_w_prime)
        if est is not None:
            log.info("W' estimé des séances passées : %.1f kJ.", est / 1000.0)
        self.w_prime_estimate_j = est
        self._publish_rogue()

    def _drop_rogue(self) -> None:
        """Retour au mode classique : la run préparée est abandonnée."""
        if self.rogue is None:
            return
        log.info("Run Cyber-Rogue abandonnée avant le départ.")
        self.rogue = None
        self.physics.p = self._base_params   # l'équipement revient hors du Cyber-Rogue (lot V5)
        self.state.rogue = None
        self.state.gears_total = self.gearing.n_gears
        self.state.gear = self.gearing.k
        self._sync_erg_state()

    def _step_rogue(self, dt: float, m: Any) -> None:
        """Pas du mode ROGUE : moteur de run, pente de l'ennemi décalée par le braquet, journal."""
        rg = self.rogue
        assert rg is not None
        clicks = [p for p in self.inputs if isinstance(p, ZwiftClickProvider)]
        input_lost = bool(clicks) and self.state.input_status != "CONNECTED"
        ts = time.time()
        out, lines = rg.step(dt, m.power_w, m.cadence_rpm, self.physics, input_lost, ts)
        for msg in out.messages:
            self.server.send_raw(msg)
        if self._rec:
            for line in lines:
                self._rec.game(line)
        cfg = self.cfg.rogue
        self._grade_sent, shifted = rg.target_grade(cfg.grade_rate_up_pct_per_s, cfg.grade_rate_down_pct_per_s, dt)
        self.driver.set_sim_grade(self._grade_sent, immediate=shifted)
        self._rogue_dist += self.physics.v * dt
        p3 = self._power_3s(m.power_w)
        st = self.state
        st.t, st.s, st.v = self._t_session, self._rogue_dist, self.physics.v
        st.grade, st.grade_sent = round(out.grade_enemy, 2), round(self._grade_sent, 2)
        st.power, st.power_3s, st.cadence, st.hr = m.power_w, round(p3, 1), m.cadence_rpm, m.hr_bpm
        st.gear, st.rogue = rg.gear, out.rogue
        if self._rec and self._t_session >= self._next_record:
            self._next_record += 1.0
            self._rec.record(Record(
                ts=round(time.time(), 3), t=round(self._t_session, 2), distance=round(st.s, 2),
                speed=round(st.v, 3), power=round(m.power_w), cadence=round(m.cadence_rpm), hr=m.hr_bpm,
                grade=round(out.grade_enemy, 2), mode="ROGUE", gear=rg.gear, grade_sent=st.grade_sent))
        if rg.done:   # comme l'arrivée d'un parcours : la séance se termine d'elle-même, avec le bilan
            log.info("Run Cyber-Rogue terminée : %s.", rg.engine.result)
            self._finish(True)

    def _choose_start_workout(self, args: dict) -> bool:
        """`start` avec `ftp_test` ou `plan_day` : choisit l'entraînement avant de démarrer.

        Renvoie faux (rien ne démarre) si l'entraînement demandé est refusé.
        """
        if args.get("ftp_test") is not None:
            kind = args["ftp_test"]
            if kind not in FTP_TEST_KINDS:
                self.server.send_error("bad_args", f"start : ftp_test attendu parmi {', '.join(FTP_TEST_KINDS)}")
                return False
            self._select_workout(f"ftp_test:{kind}")
        elif args.get("plan_day"):
            if not self._plan_day:
                self.server.send_error("plan_invalid", "Aucune séance du plan à faire aujourd'hui.")
                return False
            self._select_workout(self._plan_day)
        else:
            return True
        return self._workout is not None   # entraînement refusé : `workout_invalid` déjà envoyé

    def _choose_start_bots(self, args: dict) -> bool:
        """`start` avec `bots` (lot O7) : remplace les bots de la séance (ceux de --bot et --ghost
        sinon) ; renvoie faux (rien ne démarre, `error` `bot_invalid`) si la liste est refusée."""
        if args.get("bots") is None:
            self._set_bots(self._cli_bots)   # sans `bots` : ceux de la ligne de commande (--bot, --ghost)
            return True
        from .bots import BotError, bots_from_menu

        try:
            bots = bots_from_menu(args["bots"], PhysicsParams.from_config(self.cfg), self.cfg.rider.ftp_w,
                                  self.state.route_id, self.journal_dir, s=self.physics.s,
                                  bike_mass_kg=self.cfg.bike.mass_kg)
        except BotError as exc:
            self.server.send_error("bot_invalid", f"Bots refusés : {exc}")
            return False
        self._set_bots(bots)
        return True

    def _set_bots(self, bots: list[Any]) -> None:
        if bots is self.bots:
            return
        self.bots = bots
        self._bot_cda = {id(b): b.params.cda_m2 for b in self.bots if getattr(b, "params", None)}
        self._draft = 0.0
        log.info("Bots de la séance : %s.", ", ".join(b.name for b in self.bots) or "aucun")

    def _on_plan_command(self, name: str, args: dict, cmd_id: int) -> None:
        from . import plans

        created = None
        if name != "list_plans":
            if self.state.session_state in ("RUNNING", "PAUSED"):
                self.server.send_error("busy", "Plan impossible à changer pendant une séance.")
                return
            try:
                if name == "start_plan":
                    raw = args.get("start_date")
                    start = date.fromisoformat(raw) if isinstance(raw, str) and raw else None
                    plans.start_plan(str(args.get("id") or ""), start, self.plans_dir, self.workouts_dir,
                                     self.plan_state_path)
                elif name == "create_plan":   # plan maison composé dans le menu (lot O30)
                    workouts, days, weeks = args.get("workouts"), args.get("days"), args.get("weeks")
                    if not isinstance(workouts, list) or not isinstance(days, list) or not (
                            weeks is None or (isinstance(weeks, int) and not isinstance(weeks, bool))):
                        raise plans.PlanError("arguments attendus : workouts, days (listes), weeks (entier ou null)")
                    plan = plans.create_from_library(workouts, days, weeks, args.get("name") or None,
                                                     self.plans_dir, self.workouts_dir)
                    created = {"id": plan.id, "name": plan.name}
                else:
                    plans.stop_plan(self.plan_state_path)
            except (plans.PlanError, ValueError, TypeError) as exc:
                self.server.send_error("plan_invalid", f"Plan refusé : {exc}")
                return
            log.info("Plan %s.", {"start_plan": f"« {args.get('id')} » démarré", "stop_plan": "arrêté",
                                  "create_plan": f"« {created and created['id']} » créé"}[name])
        self._spawn(self._send_plans(cmd_id, created))

    async def _send_plans(self, cmd_id: int, created: dict[str, str] | None = None) -> None:
        from .ipc_lists import build_plans_message

        try:
            msg = await asyncio.to_thread(build_plans_message, cmd_id, self.cfg.rider.ftp_w, self.plans_dir,
                                          self.workouts_dir, self.plan_state_path, self.activities_dir)
            if created:
                msg["created"] = created
        except Exception:
            log.exception("Erreur lors de la préparation de plans (cmd_id=%d)", cmd_id)
            return
        self._plan_day = msg["active"]["plan_day"] if msg["active"] else None
        self.server.send_raw(msg)

    def _accept_ftp(self, args: dict, cmd_id: int) -> None:
        """Enregistre la FTP du dernier test (`[rider] ftp_w`) ; réponse `settings` comme `set_setting`."""
        if self.state.session_state in ("RUNNING", "PAUSED"):
            self.server.send_error("busy", "FTP impossible à changer pendant une séance (terminer d'abord).")
            return
        result = self._ftp_result
        if result is None or result.ftp_w is None:
            self.server.send_error("ftp_result_missing", "Aucun résultat de test de FTP à enregistrer.")
            return
        if not result.reliable and not args.get("force"):
            self.server.send_error("ftp_result_doubtful", "Résultat douteux : non enregistré sans confirmation.")
            return
        self._set_setting({"key": "rider.ftp_w", "value": result.ftp_w}, cmd_id)

    # --- entraînements créés ou importés depuis le menu (lot N16, audit IPC D4) ------------------

    def _on_workout_menu_command(self, name: str, args: dict, cmd_id: int) -> None:
        if self.state.session_state in ("RUNNING", "PAUSED"):
            self.server.send_error("busy", "Entraînements modifiables seulement hors séance.")
            return
        self._spawn(self._workout_menu(name, args, cmd_id))

    async def _workout_menu(self, name: str, args: dict, cmd_id: int) -> None:
        from . import workout_menu
        from .ipc_lists import chunk_list_message, MAX_DATAGRAM_BYTES

        try:
            if name == "list_imports":
                items = await asyncio.to_thread(workout_menu.import_candidates, self.import_home,
                                                self.workouts_dir)
                self._import_offer = {it["path"] for it in items}
                for m in chunk_list_message("imports", cmd_id, items, False, MAX_DATAGRAM_BYTES):
                    self.server.send_raw(m)
                return
            if name == "create_workout":
                res = await asyncio.to_thread(workout_menu.create_interval_workout, self.workouts_dir, args)
            else:
                path = args.get("path") if isinstance(args, dict) else None
                if not isinstance(path, str) or path not in self._import_offer:
                    raise workout_menu.WorkoutMenuError(
                        "workout_invalid", "Fichier non proposé par list_imports : redemander la liste.")
                res = await asyncio.to_thread(workout_menu.import_file, Path(path), self.workouts_dir)
            log.info("Entraînement %s : %s (%s)", "créé" if name == "create_workout" else "importé",
                     res["workout_id"], "nouveau" if res["created"] else "déjà présent")
            self.server.send_raw({"type": "workout_saved", "v": 1, "request_cmd_id": cmd_id, **res})
        except workout_menu.WorkoutMenuError as exc:
            log.warning("Menu ERG : %s refusé : %s", name, exc)
            self.server.send_error(exc.code, str(exc))
        except Exception:
            log.exception("Erreur pendant %s (cmd_id=%d)", name, cmd_id)

    # --- réglages depuis le menu (lots O3 et O4, contrat IPC révision 1.3) -----------------------

    def _send_settings(self, cmd_id: int) -> None:
        from . import settings

        self.server.send_raw({"type": "settings", "v": 1, "request_cmd_id": cmd_id,
                              "items": settings.current(self.cfg)})

    def _save_difficulty(self, pct: int) -> None:
        """Difficulté choisie à la pause gardée dans `config.toml` pour la séance suivante (tout réglage du menu persiste)."""
        from . import settings

        if self.sim is not None and self.config_path is None:   # Bluetooth simulé : pas de fichier à écrire
            return
        try:
            settings.apply(self.cfg, {"trainer.difficulty_pct": pct}, self.config_path)
        except settings.SettingError as exc:
            log.warning("Difficulté non enregistrée : %s", exc)

    def _build_wind(self) -> None:
        """Vent des séances d'après `[wind]` (et le thème en mode `theme`) : au lancement et après un réglage."""
        cfg = self.cfg
        self.wind = WindModel.from_config(
            cfg.wind, theme_wind(cfg.render.theme) if cfg.wind.mode == "theme" else None)
        self._wind_sample = self.wind.sample(0.0) if self.wind.active else CALM
        if self.wind.active:
            log.info("Vent : mode %s, %.0f km/h venant de %.0f°, rafales %.0f %%, ressenti %s "
                     "(supplément de pente borné à %.1f points)", self.wind.mode, self.wind.base_mps * 3.6,
                     self.wind.from_deg, self.wind.gust_frac * 100, cfg.wind.feel,
                     cfg.wind.max_grade_offset_pct)

    def _set_setting(self, args: dict, cmd_id: int) -> None:
        from . import settings

        key = args.get("key") if isinstance(args, dict) else None
        in_session = self.state.session_state in ("RUNNING", "PAUSED")
        if in_session and str(key) in settings.KEYS and settings.get(str(key)).applies != "now":
            # Réglage de la séance suivante : refusé pendant une séance. Ceux que l'engine applique tout de
            # suite (`applies = now` : vue, qualité, volumes...) restent permis : la séance n'en dépend pas.
            self.server.send_error("busy", "Réglage impossible pendant une séance (terminer d'abord).")
            return
        try:
            changed = settings.apply(self.cfg, {str(key): args.get("value")}, self.config_path)
        except settings.SettingError as exc:
            log.warning("Réglage refusé : %s", exc)
            self.server.send_error("setting_invalid", str(exc))
            return
        log.info("Réglage enregistré (%s) : %s", self.config_path or "config.toml",
                 "; ".join(changed) if changed else "inchangé")
        if in_session:
            self._send_settings(cmd_id)
            return
        # Prise en compte pour la séance suivante, sans relancer.
        self._build_wind()
        self._base_params = self._equipped_params()
        self.physics.p = self._base_params
        self.gearing.k = min(max(self.cfg.gearing.start_gear, 1), self.gearing.n_gears)
        self.difficulty_pct = float(self.cfg.trainer.difficulty_pct)
        self.state.difficulty_pct = round(self.difficulty_pct)
        self.server.hello_config.update(ftp_w=self.cfg.rider.ftp_w, hr_max_bpm=self.cfg.rider.hr_max_bpm, theme=self.cfg.render.theme,
                                        chart=self.cfg.render.chart, difficulty_pct=round(self.difficulty_pct))
        self._send_settings(cmd_id)

    # --- appairage depuis le menu (lot N13, contrat IPC révision 1.3) -------------------------

    def _on_pairing_command(self, name: str, args: dict, cmd_id: int) -> None:
        from . import pairing

        if self.state.session_state not in pairing.SCAN_STATES:
            self.server.send_error("busy", "Recherche des appareils impossible pendant une séance.")
            return
        if name == "scan_devices":
            if self._scanning:
                return
            try:
                timeout = min(30.0, max(1.0, float(args.get("timeout_s", pairing.SCAN_TIMEOUT_S))))
            except (TypeError, ValueError):
                timeout = pairing.SCAN_TIMEOUT_S
            self._scanning = True
            self.server.send_raw(pairing.scan_results_message(cmd_id, self._scan_items, False))
            self._spawn(self._scan_devices(cmd_id, timeout))
        elif name == "identify_click_plus":
            self._identify = {"cmd_id": cmd_id, "until": time.monotonic() + pairing.IDENTIFY_TIMEOUT_S}
            log.info("Appairage : appui sur « + » attendu (%.0f s).", pairing.IDENTIFY_TIMEOUT_S)
            if not any(isinstance(p, ZwiftClickProvider) and getattr(p, "_link_up", False) for p in self.inputs):
                # Aucun boîtier relié à la séance : connexion directe aux boîtiers trouvés (comme N12).
                addresses = [it["address"] for it in self._scan_items if it["role"] == "click"]
                if addresses and self.sim is None:
                    self._spawn(self._identify_direct(cmd_id, addresses))
        elif name == "pair_devices":
            self._pair_devices(args)

    async def _scan_devices(self, cmd_id: int, timeout: float) -> None:
        from . import pairing

        error: str | None = None
        try:
            inv = await self._scan_inventory(timeout)
            self._scan_items = pairing.scan_items(inv, pairing.configured_addresses(self.cfg))
            log.info("Appairage : %d appareil(s) trouvé(s).", len(self._scan_items))
        except Exception as exc:   # Bluetooth éteint, BlueZ absent, BlueZ occupé ailleurs
            log.warning("Appairage : recherche impossible : %s", exc)
            error = pairing.scan_error_message(exc)
        finally:
            self._scanning = False
        self.server.send_raw(pairing.scan_results_message(cmd_id, self._scan_items, True))
        if error:   # après la fin de recherche, pour que l'écran garde la raison affichée
            self.server.send_error("scan_failed", error)

    async def _scan_inventory(self, timeout: float) -> dict:
        """Recherche du menu Appareils, à la suite des recherches du Click, du trainer et de la
        ceinture (verrou BLE commun, pris par `pairing.scan_inventory` : BlueZ n'en accepte qu'une,
        « InProgress ») ; refaite deux fois après 1 s si BlueZ est encore occupé par un autre programme."""
        from . import pairing

        for attempt in range(SCAN_ATTEMPTS):
            try:
                return await pairing.scan_inventory(self.sim, timeout)
            except Exception as exc:
                if not pairing.is_in_progress(exc) or attempt == SCAN_ATTEMPTS - 1:
                    raise
                log.info("Appairage : Bluetooth occupé, nouvel essai dans 1 s.")
                await asyncio.sleep(1.0)
        raise AssertionError("inatteignable")

    async def _identify_direct(self, cmd_id: int, addresses: list[str]) -> None:
        from . import pairing

        addr = await pairing.wait_plus_press(addresses, pairing.IDENTIFY_TIMEOUT_S)
        if self._identify and self._identify["cmd_id"] == cmd_id:
            self._identify_done(addr)

    def _identify_done(self, address: str | None) -> None:
        from . import pairing

        cmd_id = self._identify["cmd_id"] if self._identify else 0
        self._identify = None
        log.info("Appairage : %s", f"« + » reçu de {address}" if address else "aucun appui sur « + »")
        self.server.send_raw(pairing.scan_results_message(cmd_id, self._scan_items, True,
                                                          address.upper() if address else None))

    def _pair_devices(self, args: dict) -> None:
        from . import pairing

        if self.sim is not None and self.config_path is None:
            self.server.send_error("pairing_failed", "Bluetooth simulé : préciser --config pour enregistrer.")
            return
        try:
            paired = pairing.paired_from_args(args, self._scan_items)
            changed = pairing.save(paired, self.config_path)
        except pairing.PairingError as exc:
            log.warning("Appairage refusé : %s", exc)
            self.server.send_error("pairing_failed", str(exc))
            return
        log.info("Appairage enregistré (%s) : %s ; prise en compte au prochain lancement.",
                 self.config_path or "config.toml", "; ".join(changed) if changed else "aucun changement")
        for it in self._scan_items:
            it["configured"] = it["address"] in {paired.trainer_address, paired.click_plus_address,
                                                 paired.click_minus_address, paired.hr_address}

    def _spawn(self, coro: Any) -> asyncio.Task[Any]:
        """Lance une tâche de fond en gardant sa référence jusqu'à la fin."""
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        return task

    async def _handle_list_routes(self, cmd_id: int) -> None:
        from .config import GPX_DIR
        from .ipc_lists import build_routes_messages

        try:
            msgs = await asyncio.to_thread(build_routes_messages, cmd_id, self.routes_root, GPX_DIR,
                                           ftp_w=self.cfg.rider.ftp_w)
            for m in msgs:
                self.server.send_raw(m)
        except Exception:
            log.exception("Erreur lors de la préparation de routes (cmd_id=%d)", cmd_id)

    async def _handle_list_workouts(self, cmd_id: int) -> None:
        from .ipc_lists import build_workouts_messages

        try:
            msgs = await asyncio.to_thread(build_workouts_messages, cmd_id, self.workouts_dir,
                                           ftp_w=self.cfg.rider.ftp_w)
            for m in msgs:
                self.server.send_raw(m)
        except Exception:
            log.exception("Erreur lors de la préparation de workouts (cmd_id=%d)", cmd_id)

    async def _handle_world_menu(self, name: str, args: dict, cmd_id: int) -> None:
        """Menu du monde ouvert (lot W11) : recherche, carte, régions ; le travail se fait dans un fil."""
        from .world_menu import WorldMenu

        if self.worldmenu is None:
            self.worldmenu = WorldMenu(self.cfg.open_world.network, self.config_path)
        wm = self.worldmenu
        try:
            if name == "world_search":
                msgs = await asyncio.to_thread(wm.search, cmd_id, args.get("query"))
            elif name == "world_map":
                msgs = await asyncio.to_thread(wm.world_map, cmd_id, args)
            else:
                msgs = await asyncio.to_thread(wm.regions, cmd_id, args if name == "world_pin" else None)
            for m in msgs:
                self.server.send_raw(m)
        except Exception:
            log.exception("Erreur du menu du monde ouvert (%s, cmd_id=%d)", name, cmd_id)

    # --- monde ouvert (lot W9, contrat IPC révision 1.5) ------------------------------------------

    def _start_open_world(self, args: Any, st: str) -> None:
        if st not in ("IDLE", "READY", "FINISHED", "ERROR"):
            self.server.send_error("busy", "Monde ouvert impossible pendant une séance.")
            return
        self._close_open_world()
        ow = OpenWorld(self.cfg.open_world, self.config_path, self.worldgen_cmd, list(self.worldgen_args),
                       send_status=self.server.send_world_status, send_error=self.server.send_error,
                       journal=lambda line: self._rec.junction(line) if self._rec else None)
        self._ow_previous = "IDLE" if st in ("FINISHED", "ERROR") else st
        self._set_state("LOADING")
        try:
            ow.begin(args)
        except OpenWorldError as exc:
            log.error("Monde ouvert refusé : %s", exc)
            self.server.send_error(exc.code, str(exc))
            ow.close()
            self._set_state(self._ow_previous)
            return
        self.openworld = ow
        log.info("Monde ouvert : préparation de %s.", ow.folder)

    def _close_open_world(self, wait: bool = False) -> None:
        """Fin du générateur ; en séance, dans un fil pour ne pas retenir la boucle à 50 Hz."""
        ow, self.openworld = self.openworld, None
        if ow is None:
            return
        if wait:
            ow.close()
        else:
            threading.Thread(target=ow.close, name="worldgen-close", daemon=True).start()

    def _open_world_tick(self, now_mono: float) -> None:
        ow = self.openworld
        if ow is None:
            return
        st = self.state.session_state
        ow.tick(self.physics.s, self.physics.v, st == "RUNNING", now_mono)
        if st == "LOADING":
            if ow.failed:
                self._close_open_world()
                self._set_state(self._ow_previous)
            elif ow.ready and ow.route is not None and ow.route.ready:
                self.route = ow.route
                self.erg = None
                self._sync_erg_state()
                self.state.route_id = f"ow:{ow.id}"
                self.state.route_length_m = ow.route.length_m
                self.physics.s = self.physics.v = 0.0
                self._set_session_clock(0.0)
                log.info("Monde ouvert prêt : %.0f m de route engagée.", ow.route.length_m)
                self._set_state("READY")
            return
        if st not in ("READY", "RUNNING", "PAUSED"):
            return
        if ow.route is not None and ow.route.ready:
            self.route = ow.route            # générateur relancé : sa route remplace l'ancienne
            self.state.route_length_m = ow.route.length_m
        s = self.physics.s
        self.state.open_world = ow.state_field(s)
        if st == "RUNNING" and ow.should_pause(s):
            log.warning("Plus de route connue devant (%.0f m) : pause.", ow.known_ahead(s))
            self._set_state("PAUSED", "world_data")
        elif st == "PAUSED" and self.state.pause_reason == "world_data" and ow.can_resume(s):
            log.info("Route de nouveau connue (%.0f m) : reprise.", ow.known_ahead(s))
            self._set_state("RUNNING")

    def _set_session_clock(self, t: float) -> None:
        """Remet le temps de séance (nouveau parcours, reprise d'un journal) ; la fenêtre de la puissance 3 s
        repart de zéro : gardée, ses relevés datés de l'ancienne séance ne sortaient plus jamais (endurance 7bi)."""
        self._t_session = t
        self._power_window.clear()

    def _power_3s(self, power_w: float) -> float:
        """Ajoute la puissance du pas et renvoie la moyenne des 3 dernières secondes de la séance."""
        w = self._power_window
        w.append((self._t_session, power_w))
        while w[0][0] < self._t_session - 3.0:
            w.popleft()
        return sum(p for _, p in w) / len(w)

    def _select_route(self, route_id: str, previous: str) -> None:
        """LOADING, lecture de la couche route du .world, puis READY (contrat §7, étape 6)."""
        self._close_open_world()
        self.state.open_world = None
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
        self._segments = world.segments
        self.erg = None
        self._sync_erg_state()
        self.state.route_id = route_id
        self.state.route_length_m = world.route.length_m
        self.physics.s = self.physics.v = 0.0
        self._set_session_clock(0.0)
        log.info("Parcours « %s » chargé : %.0f m, type %s", route_id, world.route.length_m,
                 world.route.type)
        self._set_state("READY")

    def _select_workout(self, workout_id: Any) -> None:
        """Choisit l'entraînement du prochain `start` ; null revient au SIM (contrat §4)."""
        self._workout_id = None
        if workout_id is None or str(workout_id) == "":
            self._workout = None
            log.info("Aucun entraînement : mode SIM.")
            return
        try:
            self._workout = self._load_workout(str(workout_id))
        except WorkoutError as exc:
            self._workout = None
            log.error("Entraînement « %s » refusé : %s", workout_id, exc)
            self.server.send_error("workout_invalid", f"Entraînement « {workout_id} » invalide : {exc}")
            return
        self._workout_id = str(workout_id)
        w = self._workout
        log.info("Entraînement « %s » choisi : %d blocs, %.0f s.", w.name, len(w.blocks), w.duration_s)

    def _load_workout(self, workout_id: str) -> Workout:
        """Entraînement de la bibliothèque, ou test de FTP (`ftp_test:ramp`, lot O10)."""
        kind = ftp_test_kind(workout_id)
        if kind:
            return ftp_test_workout(kind, self.cfg.rider.ftp_w)
        return load_workout(workout_path(self.workouts_dir, workout_id))

    def _watch_ramp(self) -> None:
        """Surveille la fin de la rampe pendant une séance de test par paliers (lot O10)."""
        ramp = self._workout is not None and ftp_test_kind(self._workout_id) == "ramp"
        self._ramp_watch = RampWatch(self._workout) if ramp else None

    def _end_ramp(self, reason: str) -> None:
        """Fin de la rampe : retour au calme (5 min à 100 W) au lieu d'un arrêt net."""
        assert self.erg is not None
        why = {"cadence": "cadence sous 50 tr/min", "power": "puissance sous 80 % de la cible",
               "abandon": "abandon"}[reason]
        log.info("Test de FTP : fin de la rampe au palier de %d W (%s), retour au calme.",
                 self.erg.block.start_w or 0, why)
        self.erg.goto(cooldown_index(self.erg.workout))
        self._sync_erg_state()

    def _workout_erg(self) -> ErgController | None:
        """Contrôleur de l'entraînement en cours (None en SIM et en ERG d'une session libre)."""
        return self.erg if isinstance(self.erg, ErgController) else None

    def _set_ride_mode(self, args: dict, st: str) -> None:
        """Bascule SIM, ERG libre ou ERG cadence pendant une session libre (lot O18, révision 1.5).

        `mode` : `sim`, `erg` ou `cadence` ; `target_w` (ERG) et `cadence_rpm` (cadence) facultatifs :
        sans eux, la cible en cours, sinon la mesure (puissance des 3 dernières secondes, cadence)."""
        if st not in ("RUNNING", "PAUSED"):
            self.server.send_error("busy", "Changement de mode possible seulement pendant une séance.")
            return
        if self.rogue is not None or self._workout_erg() is not None:
            self.server.send_error("busy", "Changement de mode impossible pendant un entraînement ou une run.")
            return
        if self.wtf is not None and args.get("mode") != "sim":
            self.server.send_error("busy", "Le mode WTF se joue en SIM seulement.")
            return
        mode = args.get("mode")
        if mode not in ("sim", "erg", "cadence"):
            self.server.send_error("bad_args", "set_ride_mode attend 'mode' : sim, erg ou cadence")
            return
        nums: dict[str, float | None] = {}
        for key in ("target_w", "cadence_rpm"):
            raw = args.get(key)
            if raw is not None and (isinstance(raw, bool) or not isinstance(raw, (int, float))
                                    or not math.isfinite(raw)):
                self.server.send_error("bad_args", f"set_ride_mode : '{key}' doit être un nombre")
                return
            nums[key] = None if raw is None else float(raw)
        cur = self.erg
        ftp = self.cfg.rider.ftp_w
        self._ramp_watch = None   # rampe d'un test de FTP déjà terminé : plus rien à surveiller
        if mode == "sim":
            self.erg = None
            self._grade_sent = 0.0   # la pente reprend depuis 0 % avec la limitation de variation
        elif mode == "erg":
            w = nums["target_w"]
            if w is None:
                w = cur.target_w if cur is not None else start_power(self.state.power_3s, ftp)
            self.erg = FreeErg(w)
        else:
            w = cur.target_w if cur is not None else start_power(self.state.power_3s, ftp)
            rpm = nums["cadence_rpm"]
            if rpm is None:
                rpm = cur.cadence_target if isinstance(cur, CadenceLock) else start_cadence(self.state.cadence)
            self.erg = CadenceLock(rpm, w, ftp)
        if self.erg is not None:
            self.erg.paused = st == "PAUSED"
        log.info("Mode de la séance : %s%s.", mode.upper(),
                 f", cible {self.erg.target_w} W" if self.erg is not None else "")
        self._sync_erg_state()

    def _skip_block(self) -> None:
        assert isinstance(self.erg, ErgController)
        if self._ramp_watch and self._ramp_watch.abandon(self.erg):
            self._end_ramp("abandon")   # pendant la rampe, le saut de bloc vaut abandon du test
            return
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
        self.state.mode = "ROGUE" if self.rogue is not None else ("ERG" if erg else "SIM")
        self.state.erg = erg.to_dict() if erg else None

    def _on_engine_lost(self) -> None:
        if self.state.session_state == "RUNNING":
            log.warning("Engine perdu : pause automatique.")
            self._set_state("PAUSED", "engine_lost")

    # --- journal et FIT ----------------------------------------------------------------

    def _open_journal(self) -> None:
        from .plans import active_tag

        route_id = rogue_mode.JOURNAL_ROUTE_ID if self.rogue is not None else self.state.route_id
        self._rec = SessionRecorder(self.journal_dir, route_id,
                                    on_failure=self._on_recording_failure,
                                    workout_id=self._workout_id, source=self._journal_source(),
                                    progression=self.progress_svc.journal_header(equipped=self.rogue is None),
                                    profile=self.profile_ctx.journal_header(),
                                    plan=active_tag(self._workout_id, state_path=self.plan_state_path,
                                                    plans_dir=self.plans_dir, workouts_dir=self.workouts_dir))
        self._rec.event("start", time.time())
        self._device_up = self._device_states()   # état de départ : seuls les changements s'écrivent
        self._next_record = 0.0

    def _journal_source(self) -> str:
        """Origine de la séance écrite en tête du journal (progression, lot V2)."""
        d = self.cfg.drivers
        return journal_source(d.trainer, d.mock_replay)

    def _click_device(self, address: str) -> str:
        """Boîtier « + » ou « − » (lot N12) : d'après `click_address` et `click_minus_address`.

        Sans adresse configurée : adresse simulée du « + » en simulation ; sinon le premier
        boîtier vu est le « + », l'autre le « − ».
        """
        d = self.cfg.drivers
        addr = address.upper()
        if d.click_address:
            return "click_plus" if addr == d.click_address.upper() else "click_minus"
        if d.click_minus_address:
            return "click_minus" if addr == d.click_minus_address.upper() else "click_plus"
        if d.input == "sim":
            from .sim_scenarios import PLUS_ADDRESS
            return "click_plus" if addr == PLUS_ADDRESS else "click_minus"
        seen = self._click_seen.setdefault(addr, "click_plus" if not self._click_seen else "click_minus")
        return seen

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

    def _finish(self, save: bool, final_state: str = "FINISHED", ts: float | None = None) -> None:
        summary = None
        journal: str | None = None
        records_done: list[dict] | None = []
        race, self.race = self.race, None
        wtf, self.wtf = self.wtf, None
        self.state.wtf = None
        self._log_gravel()
        if race and self._rec:
            for line in race.take_journal() + race.jersey_lines():
                self._rec.game(line)
        if wtf is not None and self._rec:
            for line in wtf.take_journal():
                self._rec.game({**line, "ts": round(time.time(), 3)})
            self._rec.game({"kind": "wtf_summary", "ts": round(time.time(), 3), **wtf.summary()})
            self.physics.p = self._base_params
            for bot in self.bots:
                if hasattr(bot, "power_factor"):
                    bot.power_factor = 1.0
        if self._rec:
            rec, self._rec = self._rec, None
            journal = rec.path.name if rec.path is not None else None
            ftp_result = self._write_ftp_test(rec)
            if ftp_result is not None:
                self._ftp_result = ftp_result
            rogue_summary = None
            if self.rogue is not None:   # ligne `rogue_run` : l'expérience, les pièces et les statistiques la lisent
                rogue_summary = self.rogue.summary()
                rec.game(self.rogue.run_line(time.time()))
                self.progress_svc.use_lives(self.rogue.engine.lives_used)   # vies rattrapant une défaite (R9)
            fit_path, s, fit_error = rec.finish(save, ts=ts)
            records, events = rec.records, rec.events
            records_done = records if self.rogue is None else None   # pas d'équipement en Cyber-Rogue (V5)
            if fit_error and save:
                self.server.send_error("recording_failed", f"FIT non produit : {fit_error}")

            summary = {
                "duration_s": round(s.timer_s, 1),
                "distance_m": round(s.distance_m, 1),
                "avg_power_w": round(s.avg_power or 0.0, 1),
                "fit_path": str(fit_path) if fit_path else None,
                **summary_extras(records, events, self.cfg.rider.ftp_w),
            }
            if rogue_summary is not None:   # lot R8 : bilan de la run
                summary["rogue"] = rogue_summary
            if wtf is not None:   # lot WTF2 : points et événements joués
                summary["wtf"] = wtf.summary()
            segments = race.summary() if race else None
            if segments is not None:   # série T (lot T7, révision 1.4)
                summary["segments"] = segments
            if ftp_result is not None:   # lot O12 : résultat du test au bilan, pour `accept_ftp`
                summary["ftp_test"] = {"test": ftp_result.kind, "ftp_w": ftp_result.ftp_w,
                                       "previous_ftp_w": ftp_result.previous_ftp_w,
                                       "warnings": list(ftp_result.warnings), "reliable": ftp_result.reliable}
        self.state.summary = summary
        ow = self.openworld
        if ow is not None and save and ow.route is not None and ow.route.ready:
            try:   # lot W14 : la route parcourue devient un parcours de la bibliothèque
                save_ride(ow.route, self.physics.s, ow.id, self.gpx_dir or GPX_DIR)
            except (OSError, WorldError) as exc:
                log.warning("Balade du monde ouvert non enregistrée : %s", exc)
        self._close_open_world()
        self.state.open_world = None
        self.erg = None
        self._ramp_watch = None
        if self.rogue is not None:
            self.rogue = None
            self.state.rogue = None
            self.state.gears_total, self.state.gear = self.gearing.n_gears, self.gearing.k
            self.physics.p = self._base_params   # l'équipement revient hors du Cyber-Rogue (lot V5)
        self._sync_erg_state()
        self._set_state(final_state)
        if journal is not None and final_state == "FINISHED":
            self._after_session(journal, records_done)

    # --- mode « What the fuck » (série WTF, lot WTF2) -----------------------------------

    def _wtf_table(self) -> wtf_rules.WtfTable:
        try:
            return wtf_rules.load_table(self.wtf_path)
        except wtf_rules.WtfError as exc:
            log.warning("Règles du mode WTF refusées, toutes actives : %s", exc)
            return wtf_rules.DEFAULT_TABLE

    def _start_wtf(self) -> None:
        """Séance en mode WTF : règles de `wtf.toml`, costumes des bots, ligne `wtf_start` au journal."""
        table = self._wtf_table()
        self.wtf = WtfMode(table, float(self.cfg.rider.ftp_w), replace(self._base_params),
                           seed=int(time.time()) & 0xFFFFFFFF)
        for bot in self.bots:
            self.wtf.bot_skin(bot.id)
        if self._rec:
            self._rec.game({"kind": "wtf_start", "ts": round(time.time(), 3), "rules": sorted(table.enabled)})
        log.info("Mode WTF : %d règle(s) active(s) sur %d.", len(table.enabled), len(wtf_rules.RULE_IDS))

    def _send_wtf_rules(self) -> None:
        table = self.wtf.table if self.wtf is not None else self._wtf_table()
        self.server.send_raw({"type": "wtf_rules", "v": 1, "rules": table.rules_list()})

    def _set_wtf_rule(self, args: dict) -> None:
        """Allume ou coupe une règle (écrit `wtf.toml`) ; prise en compte tout de suite pendant une séance."""
        rule, on = args.get("id"), args.get("on")
        if not isinstance(rule, str) or not isinstance(on, bool):
            self.server.send_error("bad_args", "set_wtf_rule attend 'id' (texte) et 'on' (vrai ou faux)")
            return
        try:
            table = self._wtf_table().with_rule(rule, on)
            wtf_rules.save_table(table, self.wtf_path)
        except wtf_rules.WtfError as exc:
            self.server.send_error("wtf_rule_invalid", str(exc))
            return
        except OSError as exc:
            self.server.send_error("wtf_rule_invalid", f"règles non écrites : {exc}")
            return
        if self.wtf is not None:
            self.wtf.table = table
        log.info("Mode WTF : règle %s %s.", rule, "allumée" if on else "coupée")
        self._send_wtf_rules()

    def _fill_wtf_frame(self) -> None:
        st = self.state
        if self.wtf is None or st.session_state not in ("RUNNING", "PAUSED"):
            st.wtf = None
            return
        st.wtf = self.wtf.frame(self._t_session, self.physics.s)

    # --- mode classique de la série T (lot T7) ------------------------------------------

    def _new_race(self, classic: bool = True) -> None:
        """Segments, records, bonus, maillots et écarts de la séance qui commence.

        `classic` faux (mode WTF) : pas de segments, de records ni de bonus, seulement les bots calibrés."""
        route = self.route
        self.race = None
        if route is None:
            return
        try:
            book = RecordBook.load(self.records_path)
            self._records_writable = True
        except RecordsError as exc:   # fichier abîmé : gardé tel quel, rien n'est écrit par-dessus
            log.warning("Records non chargés, ils ne seront pas enregistrés : %s", exc)
            book, self._records_writable = RecordBook(), False
        try:
            table = load_table(self.powerups_path)
        except PowerUpError as exc:
            log.warning("Valeurs des bonus refusées, valeurs par défaut : %s", exc)
            table = None
        header = self.progress_svc.journal_header()   # équipement de la série V (None : progression coupée)
        plain = PhysicsParams.from_config(self.cfg)
        gain_mode = "off" if header is None else ("zero" if self._base_params == plain else "compute")
        if classic:
            self.race = ClassicRace(
                route_id=self.state.route_id or "demo", segments=self._segments, length_m=route.length_m,
                loop=route.is_loop, rider_mass_kg=self.cfg.rider.mass_kg, book=book, table=table,
                powerups_on=self.cfg.powerups.mode == "on",
                loadout=header["loadout"] if header else None, gain_mode=gain_mode)
        from .bots import RefRider, attach_segments, calibrate_bots

        attach_segments(self.bots, self._segments)   # montées et sprints des bots à profil (lot T12)
        t0 = time.perf_counter()
        # Niveau des bots (lot T13) : cycliste équipé (lot V5), bots sans équipement (leur physique de séance).
        rider = RefRider(self.cfg.rider.ftp_w, self._base_params)
        scales = calibrate_bots(self.bots, route, rider, self.cfg.bots.level_pct, self._segments,
                                self.cfg.bike.mass_kg, bot_params=plain)
        if scales:
            log.info("Bots calibrés en %.0f ms : %s.", 1000.0 * (time.perf_counter() - t0),
                     ", ".join(f"{p} à {lv:g} % : CP × {k:.2f}" for (p, lv), k in scales.items()))
        if self.race is None:
            return
        self.race.start(self._t_session, self.physics.s, self.bots)
        if self._segments:
            log.info("Mode classique : %d segment(s), bonus %s.", len(self._segments), self.cfg.powerups.mode)

    def _flush_race_journal(self) -> None:
        """Lignes `powerup` et `segment` au journal ; records écrits hors de la boucle à 50 Hz."""
        race = self.race
        if race is None:
            return
        for line in race.take_journal():
            if self._rec:
                self._rec.game(line)
        if race.book_dirty:
            race.book_dirty = False
            self._save_records(race.book)

    def _segment_gain(self, job: GainJob) -> None:
        """`equipment_gain_s` d'un passage (lot V5) : simulation hors de la boucle à 50 Hz."""
        records = self._rec.records if self._rec else []
        equipped, plain = self._base_params, PhysicsParams.from_config(self.cfg)

        def compute() -> float | None:
            return segment_time_gain(records, equipped, plain, job.t_start, job.t_end, job.s_start, job.s_end)

        try:
            asyncio.get_running_loop()
        except RuntimeError:   # tests et outils sans boucle asyncio : calcul direct
            job.resolve(compute())
            return

        async def run() -> None:
            try:
                job.resolve(await asyncio.to_thread(compute))
            except Exception:
                log.exception("Temps gagné par l'équipement non calculé (segment)")
                job.resolve(None)

        self._spawn(run())

    def _save_records(self, book: RecordBook) -> None:
        if not self._records_writable:
            return
        snapshot, path = copy.deepcopy(book), self.records_path

        def save() -> None:
            try:
                snapshot.save(path)
            except OSError as exc:
                log.error("Records non écrits (%s) : %s", path, exc)

        try:
            asyncio.get_running_loop()
        except RuntimeError:   # tests et outils sans boucle asyncio : écriture directe
            save()
            return
        self._spawn(asyncio.to_thread(save))

    def _fill_race_frame(self) -> None:
        """Champs de la révision 1.4 de la série T dans la trame `state`."""
        st = self.state
        race = self.race
        if race is None or st.session_state not in ("RUNNING", "PAUSED"):
            st.segment = st.powerup = st.jerseys = None
            st.bot_ahead = st.bot_behind = None
            return
        f = race.frame(self._t_session, self.physics.s, self.physics.v, self.bots)
        st.segment, st.powerup, st.jerseys = f.get("segment"), f.get("powerup"), f.get("jerseys")
        st.bot_ahead, st.bot_behind = f.get("bot_ahead"), f.get("bot_behind")
        extra = f.get("bots_extra") or {}
        if st.bots:
            st.bots = [{**b, **extra.get(b["id"], {})} for b in st.bots]

    def _write_ftp_test(self, rec: SessionRecorder) -> FtpResult | None:
        """Séance de test de FTP : résultat au journal (ligne `ftp_test`), rien dans `config.toml`."""
        kind = ftp_test_kind(rec.workout_id)
        if not kind or self._workout is None:
            return None
        result = estimate_ftp(rec.records, kind, rec.events, rec.devices, self.cfg.rider.ftp_w,
                              self._workout, ts=round(time.time(), 3))
        log.info("%s.", result.describe())
        rec.ftp_test(result.to_line())
        return result

    def _build_devices(self) -> dict[str, Any]:
        """Construit l'objet `devices` du contrat v1.1 à partir de l'état connu des pilotes."""
        trainer_st = getattr(self.driver, "status", "MOCK")
        trainer_name = getattr(self.driver, "device_name", None) or getattr(self.cfg.trainer, "device_name", None)
        trainer_addr = getattr(self.driver, "device_address", None) or self.cfg.drivers.trainer_address or None
        trainer_info = {
            "status": trainer_st,
            "name": str(trainer_name) if trainer_name else None,
            "address": str(trainer_addr) if trainer_addr else None,
            # Control Point occupé (autre appareil sur le trainer) : bandeau de l'engine
            "busy": bool(getattr(self.driver, "busy", False)),
        }

        clicks: list[dict[str, Any]] = []
        click_providers = [p for p in self.inputs if isinstance(p, ZwiftClickProvider)]
        if len(click_providers) == 1:
            p = click_providers[0]
            st = "CONNECTED" if getattr(p, "_link_up", False) else ("LOST" if getattr(p, "_ever_connected", False) else "SEARCHING")
            clicks.append({
                "side": "single",
                "status": st,
                "battery_pct": getattr(p, "battery_pct", None),
            })
        elif len(click_providers) >= 2:
            for p in click_providers[:2]:
                addr = getattr(p, "_conn_address", "")
                if addr and addr != "?":
                    side = "plus" if self._click_device(addr) == "click_plus" else "minus"
                else:
                    side = "minus" if getattr(p, "_optional", False) else "plus"
                st = "CONNECTED" if getattr(p, "_link_up", False) else ("LOST" if getattr(p, "_ever_connected", False) else "SEARCHING")
                clicks.append({
                    "side": side,
                    "status": st,
                    "battery_pct": getattr(p, "battery_pct", None),
                })

        if self.hr is not None:
            hr_st = "CONNECTED" if getattr(self.hr, "connected", False) else ("LOST" if getattr(self.hr, "_ever_connected", False) else "SEARCHING")
            hr_source = "strap" if hr_st in ("CONNECTED", "LOST") else None
            hr_info = {
                "status": hr_st,
                "source": hr_source,
                "battery_pct": getattr(self.hr, "battery_pct", None),
            }
        else:
            if getattr(self.state, "hr", None) is not None:
                hr_info = {"status": "CONNECTED", "source": "trainer", "battery_pct": None}
            else:
                hr_info = {"status": "NONE", "source": None, "battery_pct": None}

        return {
            "trainer": trainer_info,
            "click": clicks,
            "hr": hr_info,
        }

    # --- entrées utilisateur -------------------------------------------------------------

    def _mark_dropout(self) -> None:
        """Z long en roulant (§7.1, lot X47) : le cycliste sent le trainer décrocher ; repère au journal, relu par
        l'outil `decrochages` (lot X44) pour le mettre face aux chutes de puissance mesurées."""
        self.dropout_marks += 1
        log.warning("Repère « décrochage » du cycliste (Z long) : %.0f W, %.0f rpm, %.1f km/h.",
                    self.state.power, self.state.cadence, self.state.v * 3.6)
        if self._rec:
            self._rec.event("decrochage", time.time())

    def _handle_input(self, ev: InputEvent) -> None:
        # Rôle des boutons : spécification générale §7.1. Y en séance : pause, sans relais ; ailleurs
        # (menus, écran de pause), l'engine en fait « écran précédent » ou « reprendre ».
        if ev == InputEvent.Y_SHORT and self.state.session_state == "RUNNING":
            self._on_command("pause", {}, 0)
            return
        # Relayé à l'engine : menus hors séance, retour sonore (bips) et explications pendant la séance.
        self.server.send_input_event(ev.value)
        if self.openworld is not None and ev.value in CHOICE_EVENTS and self.state.session_state == "RUNNING":
            if self.openworld.on_input(ev.value, self.physics.s):   # carrefour proposé : choix de la branche
                return
        if self.rogue is not None:
            # Mode Cyber-Rogue (R8, plan de boutons §7.1) : Z et A vers le moteur de run (sélection en couloir
            # ou relais à l'engine pour la vue de caméra), + et B vers le braquet ; Y est la pause, plus haut.
            if self.state.session_state == "RUNNING":
                self.rogue.press(ev.value)
                if self.rogue.shift(ev.value):
                    self.state.gear = self.rogue.gear
            return
        if self.state.session_state != "RUNNING":
            return
        if self.wtf is not None and self.wtf.press(ev.value):   # Z court : « Non merci, chef ! »
            return
        erg = self.erg
        if ev == InputEvent.Z_LONG:
            self._mark_dropout()
            return
        if ev == InputEvent.Z_SHORT:
            # Z court : action du mode (§7.1) ; bloc suivant en ERG ; sinon, en mode
            # classique et en ERG d'une session libre (sans blocs, lot O18), bonus en réserve (T6, T7).
            if self._workout_erg():
                self._skip_block()
            elif self.race and self.race.activate(self._t_session):
                log.info("Bonus activé : %s.", self.race.powerups.active)
                self._flush_race_journal()
            return
        if ev not in BIAS_STEPS:
            return   # ni + ni − (A, flèches, appui ambigu) : rien dans le core (vues de caméra : engine, V12)
        if erg:
            # ERG (§7.1, SRS §4.4) : ± court = biais ± 2 %, ± long = biais ± 10 % ; en cadence
            # verrouillée (lot O18), cadence cible ± 2 % et ± 10 %.
            erg.change_bias(BIAS_STEPS[ev])
            self._sync_erg_state()
            latency_log.expect_cp()   # nouvelle cible ERG écrite au Control Point
            return
        n = self.cfg.gearing.long_press_gears
        if ev == InputEvent.PLUS_SHORT:
            self.gearing.shift_up()
        elif ev == InputEvent.MINUS_SHORT:
            self.gearing.shift_down()
        elif ev == InputEvent.PLUS_LONG:
            self.gearing.shift_up(n)     # grand pas : plusieurs braquets d'un coup (§7.1)
        elif ev == InputEvent.MINUS_LONG:
            self.gearing.shift_down(n)
        self.state.gear = self.gearing.k
        self._shift_pending = True   # le changement de braquet doit se sentir tout de suite
        latency_log.expect_cp()

    def _drain_inputs(self) -> None:
        if self._identify and time.monotonic() > self._identify["until"]:
            self._identify_done(None)
        for provider in self.inputs:
            while not provider.events.empty():
                ev = provider.events.get_nowait()
                with latency_log.handling(provider):   # lot X7 : étage « evenement » de l'appui suivi
                    if self._identify and ev in (InputEvent.PLUS_SHORT, InputEvent.PLUS_LONG) \
                            and getattr(provider, "_conn_address", "") not in ("", "?", None):
                        self._identify_done(provider._conn_address)   # appui d'identification : pas de menu
                        continue
                    self._handle_input(ev)
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

        self._open_world_tick(now_mono)
        if self._autoresume and self.state.session_state == "PAUSED":
            reason = self.state.pause_reason
            if (reason == "trainer_lost" and m.connected) or \
                    (reason == "engine_lost" and self.server.engine_connected) or \
                    (reason == "core_restarted" and m.connected and self.server.engine_connected):
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
        if self.rogue is not None:
            self._step_rogue(dt, m)
            return
        if self.erg:
            self.erg.step(dt, m.cadence_rpm)   # le temps du bloc ne court que pendant RUNNING
            reason = self._ramp_watch.update(dt, m.power_w, m.cadence_rpm, self.erg) if self._ramp_watch else None
            if reason:
                self._end_ramp(reason)
            self._sync_erg_state()
        erg = self.erg
        workout_erg = self._workout_erg()
        free_erg = erg if isinstance(erg, FreeErg) else None
        s = self.physics.s
        tau = self.cfg.trainer.latency_tau_s
        route = self.route
        here = route.sample(s) if route else None           # sample ramène s sur le parcours (boucle)
        grade = here.grade_pct if here else 0.0
        ahead = route.grade_at(s + self.physics.v * tau) if route else 0.0
        alt = here.alt_m if here else 0.0
        wcfg = self.cfg.wind
        race = self.race
        if race:
            race.set_erg(self.state.mode == "ERG")
            # Bonus de masse ou de CdA : paramètres du pas, utilisés aussi par le supplément de vent et
            # d'aspiration ci-dessous (CdA courant, ancien contenu de T7). Pente du parcours inchangée.
            self.physics.p = race.params(self._base_params)
        route_grade = grade
        wtf = self.wtf
        wtf_eff = None
        if wtf is not None:
            # Mode WTF (lot WTF2) : pente transformée pour la physique et la pente envoyée, masse,
            # roulement et vent de la règle en cours ; la puissance mesurée reste celle du journal.
            wtf.set_erg(self.state.mode == "ERG")
            wtf.step(WtfInput(self._t_session, dt, self.physics.s, self.physics.v, m.power_w, m.cadence_rpm,
                              grade, measures_ok=m.connected and not getattr(self.driver, "busy", False)))
            wtf_eff = wtf.effects()
            grade, ahead = wtf.grade(grade, wtf_eff), wtf.grade(ahead, wtf_eff)
            self.physics.p = wtf.physics_params(self._base_params, wtf_eff)
            for bot in self.bots:
                if hasattr(bot, "power_factor"):
                    bot.power_factor = wtf.bot_power_factor(bot.id)
        gcfg = self.cfg.gravel
        if gcfg.mode != "off":
            # Gravel (lot U21) : roulement multiplié, lissé sur 20 m ; vitesse virtuelle en SIM comme en ERG.
            params = self.physics.p if (race or wtf is not None) else self._base_params
            self._gravel_factor = self._gravel_factor_at(route, s)
            self.physics.p = replace(params, crr=params.crr * self._gravel_factor)
            self._gravel_offset = surface_physics.grade_offset_pct(params.crr, self._gravel_factor, grade)
        if self.wind.active:   # vent figé en pause : son temps est celui de la séance
            self._wind_sample = self.wind.sample(self._t_session)
            self._head_mps = head_component(self._wind_sample, here.heading_deg if here else 0.0)
            self.physics.p.wind_mps = self._head_mps + (wtf_eff.wind_add_mps if wtf_eff else 0.0)
            if wcfg.feel == "ftms":
                setter = getattr(self.driver, "set_wind", None)
                if setter:
                    setter(self._head_mps)
        self._wind_offset = 0.0
        if self.bots:
            self._update_draft(dt, route, here.heading_deg if here else 0.0)
        draft = wtf.draft(self._draft_bot, self._draft) if wtf is not None else self._draft   # baleine volante

        if erg and erg.target_active:
            # ERG : cible de puissance, aucune pente envoyée ; la physique garde la pente du terrain.
            self._grade_sent = 0.0
            self.driver.set_target_power(erg.target_w)
        else:
            # Pente envoyée : anticipée de la latence du trainer, braquet appliqué, variation limitée.
            target = self.gearing.effective_grade(ahead, self.difficulty_pct / 100.0)
            if (self.wind.active and wcfg.feel == "grade") or draft > 0.0:
                # Vent et abri ressentis : supplément de pente avant la limitation de variation et les
                # bornes. Avec feel = "ftms", le vent part dans la commande 0x11 et seul l'abri passe ici.
                head = self._head_mps if wcfg.feel == "grade" else 0.0
                self._wind_offset = grade_offset_pct(self.physics.v, head, draft, alt,
                                                     self.physics.p, wcfg.max_grade_offset_pct)
                target += self._wind_offset
            if gcfg.mode != "off":
                # Gravel ajouté au vent et à l'abri, le total sous la même borne (lot U21).
                total = surface_physics.combined_offset_pct(self._wind_offset, self._gravel_offset,
                                                            wcfg.max_grade_offset_pct)
                self._gravel_sent = total - self._wind_offset
                target += self._gravel_sent
                self._gravel_stats[2] += self._gravel_sent
                self._gravel_stats[3] += 1
            if wtf_eff is not None:   # supplément du mode WTF borné, puis bornes du mode
                target = wtf.clamp_feel(target + wtf.feel_offset(wtf_eff))
            rate = (self.cfg.trainer.grade_rate_up_pct_per_s
                    if target >= self._grade_sent
                    else self.cfg.trainer.grade_rate_down_pct_per_s)
            max_delta = rate * dt
            shifted = self._shift_pending
            if shifted:   # braquet : pas de limitation de vitesse (seul le relief est lissé)
                self._shift_pending = False
                self._grade_sent = target
            else:
                self._grade_sent += min(max(target - self._grade_sent, -max_delta), max_delta)
            self.driver.set_sim_grade(self._grade_sent, immediate=shifted)

        power_used = race.power(m.power_w) if race else m.power_w
        if wtf_eff is not None:
            power_used = wtf.power(power_used, wtf_eff)
        self.physics.step(power_used, grade, alt, dt, alpha_draft=draft)
        if gcfg.mode != "off":
            ridden = self.physics.v * dt
            self._gravel_stats[1] += ridden
            if self._gravel_factor > 1.0:
                self._gravel_stats[0] += ridden
        for bot in self.bots:
            params = getattr(bot, "params", None)   # bots à puissance constante : même vent (lot P2)
            if self.wind.active and params is not None and route:
                params.wind_mps = head_component(self._wind_sample, route.sample(bot.s).heading_deg)
            bot.step(dt, route)

        if race:
            race.step(self._t_session, dt, self.physics.s, m.power_w, self.bots)
            for job in race.take_gain_jobs():
                self._segment_gain(job)
            self._flush_race_journal()
            for msg in race.due_results(self._t_session):
                self.server.send_raw(msg)
        if wtf is not None and self._rec:
            for line in wtf.take_journal():
                self._rec.game({**line, "ts": round(time.time(), 3)})

        p3 = self._power_3s(m.power_w)

        st = self.state
        st.t, st.s, st.v = self._t_session, self.physics.s, self.physics.v
        st.grade, st.grade_sent = grade, round(self._grade_sent, 2)
        st.power, st.power_3s, st.cadence, st.hr = m.power_w, round(p3, 1), m.cadence_rpm, m.hr_bpm
        st.gear = self.gearing.k
        if here:
            st.lat, st.lon, st.alt = here.lat, here.lon, alt
        if self.bots:
            st.draft = round(self._draft, 3)
            st.draft_bot = self._draft_bot if st.draft > 0.0 else None

        if self._rec and self._t_session >= self._next_record:
            self._next_record += 1.0
            self._rec.record(Record(
                ts=round(time.time(), 3), t=round(self._t_session, 2), lat=st.lat, lon=st.lon,
                alt=round(alt, 2), distance=round(st.s, 2), speed=round(st.v, 3),
                power=round(m.power_w), cadence=round(m.cadence_rpm), hr=m.hr_bpm,
                grade=round(route_grade, 2), mode=st.mode, gear=self.gearing.k, grade_sent=st.grade_sent,
                difficulty_pct=round(self.difficulty_pct),
                block=workout_erg.index + 1 if workout_erg else None,
                target_w=erg.target_w if erg and erg.target_active else None,
                erg_bias_pct=erg.bias_pct - BIAS_DEFAULT_PCT if erg and erg.target_active else None,
                head_mps=round(self._head_mps, 2) if self.wind.active else None,
                wind_grade_pct=round(self._wind_offset, 2)
                if (self.wind.active and wcfg.feel == "grade") or self.bots else None,
                draft=round(self._draft, 3) if self.bots else None,
                surface=self._surface_here(route, st.s) if gcfg.mode != "off" else None,
                gravel_grade_pct=round(self._gravel_offset, 2) if gcfg.mode != "off" else None,
                hr_frozen=True if m.hr_bpm is None and getattr(m, "hr_frozen", False) else None,
                erg_kind=free_erg.kind if free_erg else None,
                cadence_target_rpm=free_erg.cadence_target if isinstance(free_erg, CadenceLock) else None))

        if route and not route.is_loop and self.openworld is None and st.s >= route.length_m:   # ni une boucle, ni le monde ouvert
            log.info("Arrivée atteinte.")
            self._finish(True)

    def _gravel_factor_at(self, route: Route | None, s: float) -> float:
        """Facteur de roulement en s (lot U21) : colonne `surface` lissée sur 20 m en `auto`, surface imposée
        sinon ; une route sans colonne (monde ouvert compris) est revêtue en `auto`."""
        gcfg = self.cfg.gravel
        if route is None or not hasattr(route, "surface_at"):
            return surface_physics.crr_factor(surface_physics.effective_surface("paved", gcfg.mode), gcfg)
        return surface_physics.blended_factor(route, s, gcfg.mode, gcfg)

    def _surface_here(self, route: Route | None, s: float) -> str:
        here = route.surface_at(s) if route is not None and hasattr(route, "surface_at") else "paved"
        return surface_physics.effective_surface(here, self.cfg.gravel.mode)

    def _log_gravel(self) -> None:
        """Bilan du gravel de la séance, lu par `tools/log_report.py`."""
        unpaved, ridden, offsets, steps = self._gravel_stats
        if self.cfg.gravel.mode == "off" or ridden <= 0.0:
            return
        log.info("Gravel : %.0f m non revêtus sur %.0f m, supplément de pente moyen %.2f points (mode %s)",
                 unpaved, ridden, offsets / steps if steps else 0.0, self.cfg.gravel.mode)
        self._gravel_stats = [0.0, 0.0, 0.0, 0]

    def _update_draft(self, dt: float, route: Route | None, heading_deg: float) -> None:
        """Abri derrière les bots (lot P3) : cible de `draft.best_draft`, lissée à 1 s ; abri, roue suivie et
        poussée des bots (lot AS1, `draft.update_bots`), tous sur les positions du pas précédent."""
        length = route.length_m if route else None
        is_loop = bool(route and route.is_loop)
        ws = self._wind_sample if self.wind.active else None

        def cross_at(heading: float) -> float:
            return ws.speed_mps * math.sin(math.radians(ws.from_deg - heading)) if ws else 0.0

        cross = cross_at(heading_deg)
        draft_mod.update_bots(self.bots, draft_mod.Source(self.physics.s, self.physics.v), dt, length, is_loop,
                              (lambda b: cross_at(route.sample(b.s).heading_deg)) if ws and route else None)
        target, bot_id = draft_mod.best_draft(self.physics.s, self.bots, length, is_loop,
                                              self.physics.v, self._head_mps, cross)
        self._draft = draft_mod.smooth(self._draft, target, dt)
        if bot_id is not None:
            self._draft_bot = bot_id
        elif self._draft == 0.0:
            self._draft_bot = None
        for bot in self.bots:   # poussée vers l'avant : le bot suivi de près résiste un peu moins
            base = self._bot_cda.get(id(bot))
            if base is not None:
                bot.params.cda_m2 = base * (1.0 - getattr(bot, "push", 0.0))

    def _fill_wind_frame(self) -> None:
        """Champ `wind` une trame sur quinze, jamais dans la trame qui porte `devices` (taille de la trame)."""
        st = self.state
        st.wind = None
        if not self.wind.active:
            return
        if self._frame_count % WIND_FRAME_EVERY == 0 or self._wind_pending:
            if st.devices is not None:
                self._wind_pending = True
            else:
                self._wind_pending = False
                st.wind = wind_frame(self._wind_sample, self._head_mps)

    # --- boucle principale ---------------------------------------------------------------

    def resume_session(self, path: Path) -> ResumeState:
        """Reprend une séance après un plantage du core (lot N8), en `PAUSED` / `core_restarted`.

        Recharge le parcours et l'entraînement du journal, restaure temps, distance, braquet,
        bloc ERG et biais, puis continue le même journal (événement `resume_after_crash`).
        Lève `ResumeError` si le journal ne peut pas être repris.
        """
        rs = load_resume_state(path)
        if rs.route_id == rogue_mode.JOURNAL_ROUTE_ID:
            return self._resume_rogue(path, rs)
        route_id = rs.route_id or "demo"
        self._select_route(route_id, previous="IDLE")
        if self.state.session_state != "READY":
            raise ResumeError(f"parcours « {route_id} » du journal introuvable")
        if rs.workout_id:
            self._select_workout(rs.workout_id)
            if self._workout is None:
                raise ResumeError(f"entraînement « {rs.workout_id} » du journal introuvable")

        self._set_session_clock(rs.t)
        self.physics.s, self.physics.v = rs.s, 0.0
        if rs.gear is not None and 1 <= int(rs.gear) <= self.gearing.n_gears:
            self.gearing.k = int(rs.gear)
        self.state.gear = self.gearing.k
        if self._workout and rs.block is not None:
            erg = ErgController(self._workout, self.cfg.rider.ftp_w)
            erg.index = min(max(int(rs.block) - 1, 0), len(self._workout.blocks) - 1)
            erg.t_block = min(rs.t_block, erg.block.duration_s)
            if rs.erg_bias_pct is not None:
                erg.bias_pct = BIAS_DEFAULT_PCT + rs.erg_bias_pct
            self.erg = erg
            self._watch_ramp()
        elif rs.erg_kind in ("free", "cadence"):
            # ERG d'une session libre (lot O18) : même mode, même cible et même cadence cible.
            ftp = self.cfg.rider.ftp_w
            w = rs.target_w if rs.target_w is not None else start_power(None, ftp)
            self.erg = FreeErg(w) if rs.erg_kind == "free" else \
                CadenceLock(rs.cadence_target_rpm or start_cadence(None), w, ftp)
        self._sync_erg_state()
        st = self.state
        st.t, st.s, st.v = rs.t, rs.s, 0.0

        self._rec = SessionRecorder(self.journal_dir, route_id, on_failure=self._on_recording_failure,
                                    workout_id=rs.workout_id, resume_path=path, lines=rs.lines,
                                    source=self._journal_source(), profile=self.profile_ctx.journal_header())
        if rs.running:
            # Le chronomètre s'arrête à la dernière ligne écrite avant le plantage.
            self._rec.event("pause", rs.last_ts, "core_restarted")
        self._rec.event("resume_after_crash", time.time())
        self._device_up = self._device_states()
        self._next_record = float(int(rs.t)) + 1.0
        self._new_race()   # segments repris à la position du journal ; points et maillots repartent à zéro
        self.state.session_state = "PAUSED"   # la pause est déjà au journal
        self._set_state("PAUSED", "core_restarted")
        log.info("Séance reprise après un plantage du core : %s (t %.0f s, %.0f m%s).", path, rs.t, rs.s,
                 f", bloc {rs.block}" if rs.block else "")
        return rs

    def _resume_rogue(self, path: Path, rs: ResumeState) -> ResumeState:
        """Reprise d'une run Cyber-Rogue : au début de la phase du dernier instantané (lot R8)."""
        snap = rs.rogue
        if snap is None:
            raise ResumeError("aucun instantané de la run dans le journal")
        try:
            req = snap["req"]
            request = rogue_mode.RunRequest(req["objective"], int(req["duration_min"]), int(req["seed"]),
                                            float(req["w_prime_j"]), str(snap.get("chassis", "standard")))
            self.rogue = rogue_mode.RogueMode(self.cfg, request, params=PhysicsParams.from_config(self.cfg))
            self.rogue.restore(snap)
        except (KeyError, TypeError, ValueError, EOFError, zlib.error) as exc:
            self.rogue = None
            raise ResumeError(f"instantané de la run illisible : {exc}") from exc
        self.route, self._segments, self.race, self.erg, self._workout = None, (), None, None, None
        self.physics = RiderPhysics(PhysicsParams.from_config(self.cfg))   # sans équipement (lot V5)
        self._t_session, self._grade_sent, self._rogue_dist = rs.t, 0.0, rs.s
        self._sync_erg_state()
        st = self.state
        st.route_id, st.route_length_m, st.t, st.s, st.v = None, None, rs.t, rs.s, 0.0
        st.gear, st.gears_total = self.rogue.gear, self.rogue.balance.gear_max
        st.lat = st.lon = st.alt = None
        self._rec = SessionRecorder(self.journal_dir, rogue_mode.JOURNAL_ROUTE_ID, on_failure=self._on_recording_failure,
                                    resume_path=path, lines=rs.lines, source=self._journal_source(),
                                    profile=self.profile_ctx.journal_header())
        if rs.running:
            self._rec.event("pause", rs.last_ts, "core_restarted")
        self._rec.event("resume_after_crash", time.time())
        self._device_up = self._device_states()
        self._next_record = float(int(rs.t)) + 1.0
        self.state.session_state = "PAUSED"
        self._set_state("PAUSED", "core_restarted")
        log.info("Run Cyber-Rogue reprise après un plantage du core : %s (t %.0f s, phase %s).", path, rs.t,
                 self.rogue.phase)
        return rs

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
                self._load_workout(workout_id)
            except WorkoutError as exc:
                raise AutostartError(f"entraînement « {workout_id} » refusé : {exc}") from exc

    async def run(self, autostart: bool = False, route_id: str = "demo",
                  workout_id: str | None = None, resume: Path | None = None) -> None:
        """Boucle de séance. Avec `autostart` : select_route, select_workout éventuel, puis start.

        Lève `AutostartError` avant d'ouvrir les ports IPC si le parcours ou l'entraînement
        demandé est refusé. Avec `resume` (lot N8) : reprise du journal donné à la place du
        lancement ; `autostart` garde la reprise automatique dès que l'engine et le trainer
        sont là (essais sans menu).
        """
        if autostart and resume is None:
            self.check_autostart(route_id, workout_id)
        # W' estimé (lot R16) : attendu au plus 3 s avant d'ouvrir les ports, pour être dans le premier hello_ack ;
        # au-delà, il arrive au hello_ack suivant (engine relancé ou reconnecté).
        await asyncio.wait({self._spawn(self._publish_w_prime_estimate())}, timeout=W_PRIME_ESTIMATE_WAIT_S)
        self._resumed_journal = resume
        self._publish_interrupted()   # lot O34 : dans le premier hello_ack
        self.server.start()
        tasks = [asyncio.create_task(p.run(), name=type(p).__name__)
                 for p in self._services() if hasattr(p, "run")]  # trainer prioritaire
        loop = asyncio.get_running_loop()
        # SIGHUP : terminal fermé. Sans gestionnaire, le processus mourrait sans relâcher le
        # trainer et BlueZ garderait la liaison ouverte (trainer réservé pour les autres applis).
        for name in ("SIGINT", "SIGTERM", "SIGHUP"):
            if hasattr(signal, name):
                try:
                    loop.add_signal_handler(getattr(signal, name), self.stop_event.set)
                except NotImplementedError:
                    pass
        if resume is not None:
            self._autoresume = autostart
            try:
                self.resume_session(resume)
            except ResumeError as exc:
                log.error("Reprise impossible : %s ; le core démarre sans séance.", exc)
                self._rec = None
                self._set_state("IDLE")
        elif autostart:
            self._autoresume = True
            self._on_command("select_route", {"route_id": route_id}, 0)
            if workout_id:
                self._on_command("select_workout", {"workout_id": workout_id}, 0)
            self._on_command("start", {}, 0)
        if self.first_run:
            self._on_command("install_content", {"id": "starter"}, 0)
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
        physics, state, physics_all, state_all = (JitterMeter() for _ in range(4))   # gigue (lot X17)
        while not self.stop_event.is_set():
            now = mono()
            physics.interval(now, DT_PHYSICS)
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
                state.add((now - next_state) * 1000.0)
                # Échéances fixes : « now + DT_STATE » ne tomberait qu'un pas de 20 ms sur deux (25 Hz).
                next_state += DT_STATE
                if next_state <= now:   # retard de plus d'une trame : on se recale
                    next_state = now + DT_STATE
                self._frame_count += 1
                curr_dev = self._build_devices()
                if (curr_dev != self._last_devices) or (self._frame_count % 30 == 0):
                    self.state.devices = curr_dev
                    self._last_devices = curr_dev
                else:
                    self.state.devices = None
                if self.bots:
                    self.state.bots = [b.to_dict() for b in self.bots]
                else:
                    self.state.bots = None
                self._fill_race_frame()
                self._fill_wind_frame()
                self._fill_wtf_frame()
                self.server.send_state(self.state)
            if now >= next_stats:
                next_stats = now + STATS_PERIOD_S
                r = self.stats.report()
                log.info("Perf : pas p50 %.2f / p99 %.2f / max %.2f ms ; retard p99 %.1f / max %.1f ms ;"
                         " CPU %.1f %%", r["step_p50_ms"], r["step_p99_ms"], r["step_max_ms"],
                         r["lag_p99_ms"], r["lag_max_ms"], r["cpu_pct"])
                log.info(jitter_line(physics, state))
                physics_all.merge(physics)
                state_all.merge(state)
                physics.clear()
                state.clear()

            next_tick += DT_PHYSICS
            if next_tick < mono() - 0.5:   # très en retard : on se recale au lieu de rattraper
                next_tick = mono()
            await asyncio.sleep(max(next_tick - mono(), 0.0))
        physics_all.merge(physics)
        state_all.merge(state)
        if physics_all.n:
            log.info(jitter_line(physics_all, state_all, whole=True))

    async def _shutdown(self, tasks: list[asyncio.Task]) -> None:
        log.info("Arrêt du core…")
        try:
            if self._rec:
                self._finish(True)   # la séance n'est jamais perdue
            self._close_open_world(wait=True)
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
