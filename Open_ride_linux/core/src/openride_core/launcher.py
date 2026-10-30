"""Lanceur unique `openride` : démarre le core et l'engine, les surveille, arrête tout proprement (lot K6).

    openride [options de « openride-core run »]      # défaut : --trainer ftms --input click (menus, lot N6)
             [--no-compile] [--compile-only] [--compile-timeout SECONDES]

Compilation au lancement (lot N11) :
- Au démarrage, vérifie les traces GPX nouvelles ou modifiées (`to_compile` ou `outdated`).
- Les compile via `openride-compiler build-all` avec journalisation et notification bureau (`notify-send`).
- `--no-compile` : saute cette étape.
- `--compile-only` : effectue la compilation puis quitte immédiatement.
- `--compile-timeout` : délai maximal en secondes (défaut : 300 s).

Remplace à terme `scripts/openride-dev.sh`, avec le même comportement de référence :
- un journal par lancement, `~/OpenRide/Logs/openride_AAAA-MM-JJ_HH-MM-SS.log` (lot M8) : sortie du
  core, sortie de Godot (lignes préfixées `[engine] `) et messages du lanceur (`[openride] `,
  horodatés comme le core). `~/run_trainer.log` est un lien vers le dernier journal ; on garde
  les 20 derniers et 200 Mo au plus. `OPENRIDE_LOG` remplace ce journal tournant (sans lien ni
  rotation). Sans terminal (raccourci de bureau), les messages ne vont que dans le journal ;
- l'engine (`GODOT --path engine -- --ipc-state-port=… --ipc-cmd-port=…`) reçoit les ports et la
  section `[render]` de la configuration (`--config` éventuel, sinon `~/OpenRide/config.toml`) ;
  variables `GODOT`, `GODOT_ARGS`, `OPENRIDE_ENGINE` (dossier du projet Godot), `OPENRIDE_PERF_PROBE`
  (fichier CSV de la sonde de performance du moteur, `--perf-probe`, lot X13) et `OPENRIDE_DISPLAY`
  (`windowed`, `borderless` ou `fullscreen` : remplace `[render] display` le temps d'un lancement,
  par exemple `OPENRIDE_DISPLAY=windowed` pour garder une fenêtre pendant un essai) ;
- au démarrage, le thème choisi (`[render] theme`, s'il est installé dans `~/OpenRide/Themes`) est daté dans
  `~/OpenRide/Themes/.utilisation.json` : `theme-install` retire d'abord les packs oubliés (lot U15).

Supervision :
- l'engine se ferme normalement (code 0) → arrêt propre du core (SIGINT), 10 s au plus, puis
  SIGKILL et `openride-core release-trainer` ;
- l'engine plante (code ≠ 0) → il est relancé, au plus 3 fois en 2 minutes ; s'il reste absent
  plus de 2 s (heartbeat perdu), le core met la séance en pause (`engine_lost`, contrat IPC §6) et
  la reprend au retour de l'engine ; une relance plus rapide passe sans pause ;
  au-delà, abandon : arrêt propre du core, code 1 ;
- le core s'arrête normalement → l'engine est arrêté ;
- le core plante (code ≠ 0, lot N8) → le trainer est relâché (`release-trainer`), puis le core est
  relancé sans arrêter l'engine, au plus 3 fois en 10 minutes : avec `--resume JOURNAL` si une
  séance était en cours (journal de ce lancement non terminé), elle reprend alors en pause
  (`core_restarted`) au même endroit ; sinon relance simple. Au-delà, l'engine est arrêté et
  `openride-core recover` fait le FIT de la séance ;
- SIGINT, SIGTERM ou SIGHUP (terminal fermé) reçus par le lanceur → même arrêt propre des deux.

Relance demandée depuis le menu (lot N13) :
- l'engine se ferme avec le code 64 (`EXIT_RELAUNCH`, après l'enregistrement de nouveaux appareils)
  → arrêt propre du core (trainer relâché), puis core et engine relancés : le core relit
  `config.toml` et se connecte aux appareils choisis. Ce n'est pas un plantage : le compteur de
  relances de l'engine n'avance pas. En session simulée, le code 64 ramène au vrai matériel ;
- code 65 (`EXIT_SIM`, menu « Session simulée ») → même relance, mais le core reçoit
  `--trainer sim --input sim --hr sim --sim-scenario nominal` (HomeTrainer, Click et ceinture
  simulés, `docs/SIMULATION_BLE.md`) et `--profil _essai` (profil d'essai, série MJ, lot MJ2 :
  les séances simulées n'écrivent rien dans le vrai profil), et l'engine `--sim-session` ; les
  relances après un plantage gardent le mode en cours, et la reprise cherche alors les journaux
  du profil d'essai.

Lancement sans terminal (lot N14) :
- premier démarrage : sans `~/OpenRide/config.toml`, il est créé depuis
  `scripts/config.example.toml`, avec `~/OpenRide/GPX/` et `~/OpenRide/Workouts/`, et le core
  reçoit `--first-run` ; une fenêtre d'information rappelle `openride-core devices --save` ;
- un arrêt sur erreur (Godot introuvable, configuration invalide, port IPC occupé, trainer
  réservé par une autre application, plantages répétés du core) s'affiche dans une fenêtre
  (`zenity`, sinon `kdialog`, sinon `notify-send`), avec l'emplacement du journal, et le lanceur
  sort avec le code 1 ;
- `openride --release-trainer` (entrée de bureau « Libérer le trainer ») lance
  `openride-core release-trainer` et en donne le résultat en notification ;
- pendant `scripts/update.sh` (verrou `~/OpenRide/.update.lock`), le lanceur refuse de démarrer ;
- `OPENRIDE_NO_GUI=1` : ni fenêtre ni notification (tests).

Les commandes du core, de l'engine et de la libération du trainer sont des paramètres de
`Supervisor` : les tests les remplacent par de faux programmes.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import IO, Callable

from . import __version__

DEFAULT_GODOT = Path.home() / "Applications" / "godot" / "Godot_v4.7.2-stable_linux.x86_64"
DEFAULT_LOG = Path.home() / "run_trainer.log"   # lien vers le dernier journal du lanceur
LOGS_DIR = Path.home() / "OpenRide" / "Logs"
LOG_PREFIX = "openride_"
KEEP_LOGS = 20
MAX_LOGS_BYTES = 200 * 1024 * 1024
DEFAULT_ENGINE_DIR = Path(__file__).resolve().parents[3] / "engine"
# Sans --autostart depuis le lot N6 : parcours et entraînement se choisissent dans les menus de l'engine.
DEFAULT_CORE_ARGS = ["--trainer", "ftms", "--input", "click"]

# Code de sortie de l'engine : « tout relancer » (menu « Appareils », lot N13 ; engine/scripts/main.gd).
EXIT_RELAUNCH = 64
EXIT_SIM = 65
# Options du core en session simulée (remplacent --trainer, --input, --hr, --sim-scenario et --profil) :
# matériel simulé et profil d'essai (série MJ, lot MJ2).
SIM_PROFILE = "_essai"
SIM_CORE_ARGS = ["--trainer", "sim", "--input", "sim", "--hr", "sim", "--sim-scenario", "nominal",
                 "--profil", SIM_PROFILE]
SIM_OPTIONS = ("--trainer", "--input", "--hr", "--sim-scenario", "--profil")
SIM_ENGINE_ARG = "--sim-session"

STOP_SIGNALS = tuple(s for s in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGHUP", None)) if s is not None)


def log_timestamp(t: float | None = None) -> str:
    """Horodatage au format `asctime` du module logging, celui du journal du core."""
    t = time.time() if t is None else t
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) + f",{int(t % 1 * 1000):03d}"


@dataclass
class LogRotation:
    """Journal tournant du lanceur : un fichier par lancement, lien `run_trainer.log` vers le dernier."""
    logs_dir: Path = LOGS_DIR
    link: Path | None = DEFAULT_LOG
    keep: int = KEEP_LOGS
    max_bytes: int = MAX_LOGS_BYTES
    notes: list[str] = field(default_factory=list, init=False)   # messages pour le journal

    def logs(self) -> list[Path]:
        """Journaux existants, du plus ancien au plus récent (le nom porte la date)."""
        return sorted(p for p in self.logs_dir.glob(f"{LOG_PREFIX}*.log") if p.is_file())

    def prune(self) -> list[Path]:
        """Supprime les plus anciens pour qu'avec le nouveau il en reste `keep` et `max_bytes` au plus."""
        logs, removed = self.logs(), []
        sizes = {p: p.stat().st_size for p in logs}
        total = sum(sizes.values())
        while logs and (len(logs) > self.keep - 1 or total > self.max_bytes):
            old = logs.pop(0)
            total -= sizes[old]
            try:
                old.unlink()
                removed.append(old)
            except OSError as exc:
                self.notes.append(f"journal ancien non supprimé : {old} ({exc})")
        return removed

    def prepare(self, now: float | None = None) -> Path:
        """Crée le dossier, fait la rotation, choisit le nom du journal et pose le lien."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        removed = self.prune()
        if removed:
            self.notes.append(f"{len(removed)} ancien(s) journal(aux) supprimé(s) dans {self.logs_dir}")
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time() if now is None else now))
        path, n = self.logs_dir / f"{LOG_PREFIX}{stamp}.log", 2
        while path.exists():   # deux lancements dans la même seconde
            path, n = self.logs_dir / f"{LOG_PREFIX}{stamp}_{n}.log", n + 1
        path.touch()
        if self.link is not None:
            self._link(path)
        return path

    def _link(self, target: Path) -> None:
        link = self.link
        assert link is not None
        try:
            if link.exists() and not link.is_symlink():
                old = link.with_name(link.name + ".ancien")
                if old.exists() or old.is_symlink():
                    self.notes.append(f"{link} est un fichier ordinaire et {old} existe déjà : lien non posé")
                    return
                link.rename(old)   # l'ancien journal unique est gardé, une seule fois
                self.notes.append(f"ancien {link.name} renommé en {old.name}")
            tmp = link.with_name(f".{link.name}.{os.getpid()}.tmp")
            tmp.unlink(missing_ok=True)
            tmp.symlink_to(target)
            os.replace(tmp, link)
        except OSError as exc:
            self.notes.append(f"lien {link} impossible : {exc}")


CONFIG_TEMPLATE = Path(__file__).resolve().parents[3] / "scripts" / "config.example.toml"
FIRST_RUN_INFO = ("Bienvenue dans OpenRide. Configurez vos appareils : openride-core devices --save "
                  "(la section « Appareils » du menu viendra plus tard).")
PORT_IN_USE_RE = re.compile(r"Impossible de démarrer l'IPC UDP.*(Address already in use|déjà utilisée|Errno 98)")
TRAINER_REFUSED_RE = re.compile(r"Le trainer refuse le contrôle FTMS")

MSG_PORT_IN_USE = ("Le port IPC d'OpenRide est déjà utilisé : une autre fenêtre d'OpenRide est sans doute "
                   "ouverte. Fermez-la puis relancez OpenRide.")
MSG_TRAINER_REFUSED = ("Le home trainer est réservé par une autre application. Fermez l'application Zwift "
                       "(ou autre) ou lancez OpenRide → Libérer le trainer, puis relancez OpenRide.")


UPDATE_LOCK = Path.home() / "OpenRide" / ".update.lock"   # tenu par scripts/update.sh (flock)


def update_in_progress(lock: Path = UPDATE_LOCK) -> bool:
    """Vrai si `scripts/update.sh` tient son verrou : le code et le venv sont en cours de remplacement."""
    try:
        import fcntl
    except ImportError:   # Windows : pas de scripts/update.sh
        return False
    try:
        fd = os.open(lock, os.O_RDONLY)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except OSError:
        return True
    finally:
        os.close(fd)
    return False


def _run_dialog(cmd: list[str]) -> bool:
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def desktop_message(message: str, error: bool = True) -> None:
    """Fenêtre de bureau : zenity, sinon kdialog, sinon notify-send ; rien sans aucun des trois."""
    import shutil

    title = "OpenRide"
    if os.environ.get("OPENRIDE_NO_GUI") == "1":
        return
    if shutil.which("zenity"):
        _run_dialog(["zenity", "--error" if error else "--info", "--no-wrap", f"--title={title}",
                     f"--text={message}"])
    elif shutil.which("kdialog"):
        _run_dialog(["kdialog", f"--title={title}", "--error" if error else "--msgbox", message])
    elif shutil.which("notify-send"):
        _run_dialog(["notify-send", "-u", "critical" if error else "normal", title, message])


def ensure_first_run(home: Path | None = None, template: Path | None = None) -> bool:
    """Premier démarrage : crée la configuration et les dossiers ; vrai si la configuration manquait."""
    from . import config as config_mod

    home = home or config_mod.OPENRIDE_HOME
    cfg_path = home / "config.toml"
    for sub in ("GPX", "Workouts"):
        (home / sub).mkdir(parents=True, exist_ok=True)
    if cfg_path.exists():
        return False
    template = template or CONFIG_TEMPLATE
    text = template.read_text(encoding="utf-8") if template.is_file() else "# Configuration OpenRide\n"
    cfg_path.write_text(text, encoding="utf-8")
    return True


def _default_echo() -> bool:
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


@dataclass
class Supervisor:
    core_cmd: list[str]
    engine_cmd: list[str]
    release_cmd: list[str]
    log_path: Path
    stop_timeout_s: float = 10.0       # délai laissé au core pour relâcher le trainer
    engine_stop_timeout_s: float = 5.0
    max_restarts: int = 3
    restart_window_s: float = 120.0
    restart_delay_s: float = 1.0
    startup_grace_s: float = 2.0       # le core doit tenir ce temps avant le lancement de l'engine
    poll_s: float = 0.1
    say: Callable[[str], None] = field(default=lambda msg: print(f"openride : {msg}", flush=True))
    clock: Callable[[], float] = time.monotonic
    rotation: LogRotation | None = None   # journal tournant ; None : `log_path` tel quel
    echo: Callable[[], bool] = _default_echo   # vrai : messages aussi au terminal (`say`)
    reader_join_s: float = 2.0         # délai pour vider la sortie de l'engine après son arrêt
    compile_enabled: bool = True       # compilation au lancement (lot N11)
    compile_only: bool = False         # quitte après la compilation sans lancer le core
    compile_timeout_s: float = 300.0   # délai maximal de compilation
    compiler_cmd: list[str] | None = None
    routes_dir: Path | None = None
    gpx_dir: Path | None = None
    notify: Callable[[str], None] | None = None
    journal_dir: Path | None = None    # journaux de séance (reprise après plantage, lot N8) ; None : pas de reprise
    sim_journal_dir: Path | None = None   # journaux du profil d'essai, en session simulée (lot MJ2)
    recover_cmd: list[str] | None = None   # `openride-core recover` ; le chemin du journal est ajouté
    core_max_restarts: int = 3
    core_restart_window_s: float = 600.0
    alert: Callable[[str], None] | None = None   # fenêtre d'erreur (lot N14) ; None : journal seul
    theme_name: str = ""               # thème choisi, daté au démarrage dans la bibliothèque (lot U15)
    themes_dir: Path | None = None     # ~/OpenRide/Themes ; None : rien n'est daté

    started_pids: list[int] = field(default_factory=list, init=False)
    restarts: int = field(default=0, init=False)
    core_restarts: int = field(default=0, init=False)
    relaunches: int = field(default=0, init=False)   # relances demandées depuis le menu (codes 64 et 65)
    sim_mode: bool = field(default=False, init=False)   # session simulée en cours (code 65)
    _launched_at: float = field(default=0.0, init=False)   # heure Unix du lancement (journaux de ce lancement)
    _log_scan_pos: int = field(default=0, init=False)
    _next_log_scan: float = field(default=0.0, init=False)
    _stop_signal: int | None = field(default=None, init=False)
    _log: IO[bytes] | None = field(default=None, init=False)
    _log_lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _readers: list[threading.Thread] = field(default_factory=list, init=False)

    # --- journal -----------------------------------------------------------------------

    def _write_log(self, data: bytes) -> None:
        if self._log is None:
            return
        with self._log_lock:
            try:
                self._log.write(data)
            except (OSError, ValueError):
                pass

    def _say(self, msg: str) -> None:
        """Message du lanceur : au journal (horodaté, `[openride] `) et au terminal s'il y en a un."""
        self._write_log(f"{log_timestamp()} INFO    [openride] {msg}\n".encode())
        if self._log is None or self.echo():
            self.say(msg)

    def _say_warning(self, msg: str) -> None:
        """Avertissement du lanceur : au journal (`WARNING [openride]`) et au terminal s'il y en a un."""
        self._write_log(f"{log_timestamp()} WARNING [openride] {msg}\n".encode())
        if self._log is None or self.echo():
            self.say(f"avertissement : {msg}")

    def _alert(self, msg: str) -> None:
        """Erreur qui arrête le lanceur : au journal et dans une fenêtre, avec le chemin du journal."""
        self._say_warning(msg)
        if self.alert is not None:
            try:
                self.alert(f"{msg}\n\nJournal : {self.log_path}")
            except Exception:   # une fenêtre impossible ne doit rien bloquer
                pass

    def _log_text(self, new_only: bool = False) -> str:
        try:
            with self.log_path.open("rb") as fh:
                if new_only:
                    fh.seek(self._log_scan_pos)
                data = fh.read()
                if new_only:
                    self._log_scan_pos = fh.tell()
        except OSError:
            return ""
        return data.decode("utf-8", errors="replace")

    def _open_log(self) -> None:
        if self.rotation is not None:
            self.log_path = self.rotation.prepare()
            self._log = self.log_path.open("ab", buffering=0)
            self._say(f"OpenRide {__version__}")
            for note in self.rotation.notes:
                self._say(note)
            self.rotation.notes.clear()
        else:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = self.log_path.open("wb", buffering=0)
            self._say(f"OpenRide {__version__}")
        self._say(f"journal : {self.log_path}")

    def _pump(self, stream: IO[bytes]) -> None:
        """Recopie la sortie de l'engine dans le journal, ligne à ligne, préfixée `[engine] `."""
        try:
            for line in iter(stream.readline, b""):
                if not line.endswith(b"\n"):
                    line += b"\n"
                self._write_log(b"[engine] " + line)
        except (OSError, ValueError):
            pass
        finally:
            stream.close()

    # --- processus ---------------------------------------------------------------------

    def _spawn(self, cmd: list[str], **kw) -> subprocess.Popen:
        # Nouvelle session : un Ctrl+C du terminal n'atteint que le lanceur, qui arrête tout dans l'ordre.
        p = subprocess.Popen(cmd, start_new_session=True, **kw)
        self.started_pids.append(p.pid)
        return p

    def _core_cmd(self) -> list[str]:
        return sim_core_cmd(self.core_cmd) if self.sim_mode else list(self.core_cmd)

    def _engine_cmd(self) -> list[str]:
        return [*self.engine_cmd, SIM_ENGINE_ARG] if self.sim_mode else list(self.engine_cmd)

    def _start_core(self, extra: list[str] | None = None) -> subprocess.Popen:
        if self._log is None:
            self._open_log()
        return self._spawn([*self._core_cmd(), *(extra or [])], stdin=subprocess.DEVNULL,
                           stdout=self._log, stderr=subprocess.STDOUT)

    def _unfinished_journal(self) -> Path | None:
        """Journal d'une séance de ce lancement que le core n'a pas terminée (lot N8)."""
        directory = self.sim_journal_dir if self.sim_mode else self.journal_dir
        if directory is None:
            return None
        from .resume import find_unfinished_journal

        return find_unfinished_journal(directory, since=self._launched_at - 1.0)

    def _recover(self, journal: Path | None) -> None:
        if journal is None or self.recover_cmd is None:
            return
        cmd = with_profile(self.recover_cmd, SIM_PROFILE) if self.sim_mode else self.recover_cmd
        try:
            p = self._spawn([*cmd, str(journal)], stdin=subprocess.DEVNULL,
                            stdout=self._log or subprocess.DEVNULL, stderr=subprocess.STDOUT)
            if not self._wait(p, 60.0):
                p.kill()
                p.wait()
            if p.returncode == 0:
                self._say(f"séance enregistrée en FIT depuis {journal}.")
            else:
                self._say(f"`openride-core recover` a échoué (code {p.returncode}) ; le journal reste : {journal}")
        except OSError as exc:
            self._say(f"`openride-core recover` impossible : {exc}")

    def _start_engine(self) -> subprocess.Popen:
        if self._log is None:
            return self._spawn(self._engine_cmd(), stdin=subprocess.DEVNULL)
        p = self._spawn(self._engine_cmd(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        reader = threading.Thread(target=self._pump, args=(p.stdout,), name="engine-log", daemon=True)
        reader.start()
        self._readers.append(reader)
        return p

    def _join_readers(self) -> None:
        deadline = time.monotonic() + self.reader_join_s
        for r in self._readers:
            r.join(max(0.0, deadline - time.monotonic()))
        self._readers = [r for r in self._readers if r.is_alive()]

    @staticmethod
    def _wait(p: subprocess.Popen, timeout: float) -> bool:
        try:
            p.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            return False

    def _stop_core(self, core: subprocess.Popen) -> None:
        if core.poll() is None:
            core.send_signal(signal.SIGINT)
            if not self._wait(core, self.stop_timeout_s):
                self._say(f"le core ne s'arrête pas en {self.stop_timeout_s:.0f} s : arrêt forcé puis libération du trainer.")
                core.kill()
                core.wait()
                self._release_trainer()
        core.wait()

    def _release_trainer(self) -> None:
        try:
            p = self._spawn(self.release_cmd, stdin=subprocess.DEVNULL,
                            stdout=self._log or subprocess.DEVNULL, stderr=subprocess.STDOUT)
            if not self._wait(p, 60.0):
                p.kill()
                p.wait()
        except OSError as exc:
            self._say(f"libération du trainer impossible : {exc}")

    def _stop_engine(self, engine: subprocess.Popen | None) -> None:
        if engine is None:
            return
        if engine.poll() is None:
            engine.terminate()
            if not self._wait(engine, self.engine_stop_timeout_s):
                engine.kill()
        engine.wait()
        self._join_readers()

    # --- compilation au lancement ------------------------------------------------------

    def _run_compilation(self) -> int:
        from .launch_compile import run_startup_compilation

        return run_startup_compilation(
            routes_dir=self.routes_dir,
            gpx_dir=self.gpx_dir,
            timeout_s=self.compile_timeout_s,
            compiler_cmd=self.compiler_cmd,
            log_file=self._log,
            say=self._say,
            say_warning=self._say_warning,
            notify=self.notify,
        )

    # --- signaux -----------------------------------------------------------------------

    def _on_signal(self, signum: int, _frame) -> None:
        self._stop_signal = signum

    # --- boucle ------------------------------------------------------------------------

    def run(self) -> int:
        previous = {s: signal.signal(s, self._on_signal) for s in STOP_SIGNALS}
        core: subprocess.Popen | None = None
        engine: subprocess.Popen | None = None
        self._launched_at = time.time()
        try:
            if self.compile_enabled:
                if self._log is None:
                    self._open_log()
                compile_code = self._run_compilation()
                if self.compile_only:
                    return compile_code
                if self._stop_signal is not None:
                    return 0

            if self.themes_dir is not None and self.theme_name:
                record_theme_use(self.themes_dir, self.theme_name)
            core = self._start_core()
            deadline = self.clock() + self.startup_grace_s
            while self.clock() < deadline and core.poll() is None and self._stop_signal is None:
                time.sleep(self.poll_s)
            if core.poll() is not None:
                self._say(f"le core s'est arrêté au démarrage (code {core.returncode}) ; voir {self.log_path}")
                self._print_log_tail(20, only_alerts=False)
                if PORT_IN_USE_RE.search(self._log_text()):
                    self._alert(MSG_PORT_IN_USE)
                else:
                    self._alert(f"OpenRide n'a pas pu démarrer (le core s'est arrêté, code {core.returncode}).")
                return 1
            if self._stop_signal is not None:
                return self._finish(core, None, 0)

            engine = self._start_engine()
            crashes: list[float] = []
            core_crashes: list[float] = []
            while True:
                time.sleep(self.poll_s)
                if self._stop_signal is not None:
                    self._say(f"signal {signal.Signals(self._stop_signal).name} reçu : arrêt de la séance.")
                    return self._finish(core, engine, 0)

                if self._trainer_refused():
                    self._alert(MSG_TRAINER_REFUSED)
                    return self._finish(core, engine, 1)

                if core.poll() is not None:
                    code = core.returncode
                    if code == 0:
                        self._stop_engine(engine)
                        return self._finish(core, engine, 0)
                    journal = self._unfinished_journal()
                    now = self.clock()
                    core_crashes = [t for t in core_crashes if now - t < self.core_restart_window_s] + [now]
                    self._release_trainer()   # le core n'a pas pu rendre le trainer
                    if len(core_crashes) > self.core_max_restarts:
                        self._say(f"le core a planté {len(core_crashes)} fois en "
                                  f"{self.core_restart_window_s / 60:.0f} min (code {code}) : abandon. "
                                  "La séance est dans le journal : `openride-core recover` en fait un FIT.")
                        self._stop_engine(engine)
                        self._recover(journal)
                        self._alert(f"Le core d'OpenRide a planté {len(core_crashes)} fois de suite : arrêt. "
                                    "La séance est enregistrée en FIT si elle avait commencé.")
                        return self._finish(core, engine, 1)
                    n = len(core_crashes)
                    if journal is not None:
                        self._say(f"le core a planté (code {code}) : relance {n}/{self.core_max_restarts} "
                                  f"avec reprise de la séance en pause ({journal.name}).")
                        core = self._start_core(["--resume", str(journal)])
                    else:
                        self._say(f"le core a planté hors séance (code {code}) : relance {n}/{self.core_max_restarts}.")
                        core = self._start_core()
                    self.core_restarts += 1
                    continue

                if engine.poll() is not None:
                    code = engine.returncode
                    if code == 0:
                        return self._finish(core, engine, 0)
                    if code in (EXIT_RELAUNCH, EXIT_SIM):
                        self.sim_mode = code == EXIT_SIM
                        self._say("relance demandée depuis le menu"
                                  + (" en session simulée (sans matériel)" if self.sim_mode else "")
                                  + " : arrêt du core puis nouveau lancement.")
                        self._join_readers()
                        self._stop_core(core)
                        core = self._start_core()
                        if not self._core_survives_startup(core):
                            self._say(f"le core s'est arrêté à la relance (code {core.returncode}) ; voir {self.log_path}")
                            self._alert(f"OpenRide n'a pas pu redémarrer (le core s'est arrêté, code {core.returncode}).")
                            return self._finish(core, engine, 1)
                        engine = self._start_engine()
                        self.relaunches += 1
                        continue
                    now = self.clock()
                    crashes = [t for t in crashes if now - t < self.restart_window_s] + [now]
                    if len(crashes) > self.max_restarts:
                        self._say(f"l'engine a planté {len(crashes)} fois en {self.restart_window_s:.0f} s : abandon.")
                        return self._finish(core, engine, 1)
                    self._say(f"l'engine a planté (code {code}) : relance {len(crashes)}/{self.max_restarts}, "
                             "la séance passe en pause si l'engine reste absent plus de 2 s.")
                    if self.restart_delay_s > 0:
                        time.sleep(self.restart_delay_s)
                    engine = self._start_engine()
                    self.restarts += 1
        finally:
            for p in (engine, core):
                if p is not None and p.poll() is None:   # filet de sécurité : jamais d'orphelin
                    p.kill()
                    p.wait()
            self._join_readers()
            if self._log is not None:
                with self._log_lock:
                    self._log.close()
                    self._log = None
            for s, h in previous.items():
                signal.signal(s, h)

    def _core_survives_startup(self, core: subprocess.Popen) -> bool:
        deadline = self.clock() + self.startup_grace_s
        while self.clock() < deadline and core.poll() is None and self._stop_signal is None:
            time.sleep(self.poll_s)
        return core.poll() is None

    def _trainer_refused(self) -> bool:
        """Lit au plus une fois par seconde la suite du journal : refus du contrôle FTMS ?"""
        if self._log is None:
            return False
        now = time.monotonic()
        if now < self._next_log_scan:
            return False
        self._next_log_scan = now + 1.0
        return bool(TRAINER_REFUSED_RE.search(self._log_text(new_only=True)))

    def _finish(self, core: subprocess.Popen, engine: subprocess.Popen | None, code: int) -> int:
        self._stop_engine(engine)
        self._stop_core(core)
        if self._log is not None:
            self._log.flush()
        self._say(f"arrêté. Journal complet : {self.log_path}")
        self._print_log_tail(15, only_alerts=True)
        return code

    def _print_log_tail(self, n: int, only_alerts: bool) -> None:
        if not self.echo():   # sans terminal, le journal suffit : rien en double
            return
        try:
            lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return
        if only_alerts:
            lines = [ln for ln in lines if re.search(r"WARNING|ERROR", ln)]
            if lines:
                print("--- Avertissements ---")
        for ln in lines[-n:]:
            print(ln)


# --- ligne de commande -------------------------------------------------------------------

def _without_options(cmd: list[str], names: tuple[str, ...]) -> list[str]:
    """`cmd` sans les options `names` (`--nom V` et `--nom=V`)."""
    out: list[str] = []
    skip = False
    for a in cmd:
        if skip:
            skip = False
            continue
        if a in names:
            skip = True
            continue
        if a.split("=", 1)[0] in names:
            continue
        out.append(a)
    return out


def with_profile(cmd: list[str], profile_id: str) -> list[str]:
    """`cmd` avec `--profil profile_id` à la place de tout `--profil` donné (série MJ)."""
    return [*_without_options(cmd, ("--profil",)), "--profil", profile_id]


def sim_core_cmd(core_cmd: list[str]) -> list[str]:
    """Commande du core en session simulée : matériel simulé et profil d'essai (`SIM_CORE_ARGS`)."""
    return [*_without_options(core_cmd, SIM_OPTIONS), *SIM_CORE_ARGS]


def extract_launcher_args(args: list[str]) -> tuple[list[str], bool, bool, float]:
    """Extrait les arguments propres au lanceur (--no-compile, --compile-only, --compile-timeout)."""
    core_args: list[str] = []
    no_compile = False
    compile_only = False
    compile_timeout = 300.0
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--no-compile":
            no_compile = True
            i += 1
        elif a == "--compile-only":
            compile_only = True
            i += 1
        elif a == "--compile-timeout":
            if i + 1 >= len(args):
                raise ValueError("--compile-timeout requiert une valeur en secondes")
            compile_timeout = float(args[i + 1])
            i += 2
        elif a.startswith("--compile-timeout="):
            compile_timeout = float(a.split("=", 1)[1])
            i += 1
        else:
            core_args.append(a)
            i += 1
    return core_args, no_compile, compile_only, compile_timeout


def _option_arg(args: list[str], name: str) -> str | None:
    """Valeur de l'option `name` (`--nom V` ou `--nom=V`) dans les arguments du core, ou None."""
    for i, a in enumerate(args):
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
        if a == name and i + 1 < len(args):
            return args[i + 1]
    return None


THEMES_DIR = Path.home() / "OpenRide" / "Themes"
THEME_USE_FILE = ".utilisation.json"   # lu par openride_compiler.theme_packs (bibliothèque des thèmes, lot U15)


def record_theme_use(themes_dir: Path, theme: str, when: datetime | None = None) -> None:
    """Date de dernière utilisation du thème choisi (`{nom: date ISO}`), pour que `theme-install` retire d'abord
    les packs oubliés. Le thème intégré n'est pas daté (jamais retiré) ; fichier illisible : recommencé ;
    erreur d'écriture : ignorée (la séance démarre quand même)."""
    if theme == "default" or not (themes_dir / theme).is_dir():
        return
    path = themes_dir / THEME_USE_FILE
    try:
        uses = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):   # absent ou illisible : recommencé
        uses = {}
    if not isinstance(uses, dict):
        uses = {}
    uses[theme] = (when or datetime.now()).isoformat(timespec="seconds")
    try:
        path.write_text(json.dumps(uses, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass


def _config_arg(args: list[str]) -> Path | None:
    value = _option_arg(args, "--config")
    return Path(value) if value is not None else None


def worldgen_command(env: dict[str, str] | None = None) -> list[str]:
    """Commande du générateur du monde ouvert (lot W9) : `OPENRIDE_WORLDGEN`, sinon le paquet du compilateur
    lancé par le même Python que le core (installé dans le même environnement, `scripts/install.sh`)."""
    env = os.environ if env is None else env
    if env.get("OPENRIDE_WORLDGEN"):
        return shlex.split(env["OPENRIDE_WORLDGEN"])
    return [sys.executable, "-m", "openride_compiler.worldgen.process"]


def worldmenu_command(env: dict[str, str] | None = None) -> list[str]:
    """Requêtes du menu du monde ouvert (lot W11) : `OPENRIDE_WORLDMENU`, sinon `menu_query` du compilateur."""
    env = os.environ if env is None else env
    if env.get("OPENRIDE_WORLDMENU"):
        return shlex.split(env["OPENRIDE_WORLDMENU"])
    return [sys.executable, "-m", "openride_compiler.worldgen.menu_query"]


def build_supervisor(core_args: list[str], env: dict[str, str] | None = None) -> Supervisor:
    """Construit le superviseur réel ; lève `ConfigError` ou `FileNotFoundError` avec un message lisible."""
    from . import config as config_mod
    from . import profiles

    env = os.environ if env is None else env
    raw_args = list(core_args) if core_args else list(DEFAULT_CORE_ARGS)
    clean_core_args, no_compile, compile_only, compile_timeout = extract_launcher_args(raw_args)
    clean_core_args = clean_core_args or list(DEFAULT_CORE_ARGS)
    config_path = _config_arg(clean_core_args)
    cfg = config_mod.load(config_path)   # ConfigError si invalide
    # Profil de joueur (série MJ, lot MJ1) : `--profil` passe au core ; reprise et FIT dans son dossier.
    profile_id = _option_arg(clean_core_args, "--profil")
    ctx = profiles.resolve(profile_id, env) or profiles.current()   # ProfileContextError si refusé
    profile_args = ["--profil", ctx.id] if ctx.id is not None else []

    godot = Path(env.get("GODOT") or cfg.engine.godot or DEFAULT_GODOT).expanduser()
    if not (godot.is_file() and os.access(godot, os.X_OK)):
        raise FileNotFoundError(f"Godot introuvable : {godot} (relancer scripts/install.sh, ou [engine] godot "
                                "dans ~/OpenRide/config.toml, ou GODOT=/chemin/vers/godot)")
    engine_dir = Path(env.get("OPENRIDE_ENGINE") or DEFAULT_ENGINE_DIR).expanduser()
    if not (engine_dir / "project.godot").is_file():
        raise FileNotFoundError(f"projet Godot introuvable : {engine_dir} (définir OPENRIDE_ENGINE)")

    core = [sys.executable, "-m", "openride_core"]
    config_args = ["--config", str(config_path)] if config_path else []
    return Supervisor(
        core_cmd=[*core, "run", *clean_core_args],
        engine_cmd=[
            str(godot),
            "--path",
            str(engine_dir),
            *shlex.split(env.get("GODOT_ARGS", "")),
            "--",
            f"--ipc-state-port={cfg.ipc.port_state}",
            f"--ipc-cmd-port={cfg.ipc.port_commands}",
            f"--quality={cfg.render.quality}",
            f"--theme={cfg.render.theme}",
            f"--visual-grade={cfg.render.visual_grade_scale}",
            f"--camera={cfg.render.camera}",
            f"--living={'on' if cfg.render.living else 'off'}",
            f"--load-guard={'on' if cfg.render.load_guard else 'off'}",
            f"--display={env.get('OPENRIDE_DISPLAY') or cfg.render.display}",
            *([f"--perf-probe={env['OPENRIDE_PERF_PROBE']}"] if env.get("OPENRIDE_PERF_PROBE") else []),
        ],
        release_cmd=[*core, "release-trainer", *config_args],
        recover_cmd=[*core, "recover", *profile_args],
        journal_dir=ctx.journal_dir,
        sim_journal_dir=profiles.ProfileContext.for_id(SIM_PROFILE).journal_dir,
        log_path=Path(env["OPENRIDE_LOG"]).expanduser() if env.get("OPENRIDE_LOG") else DEFAULT_LOG,
        rotation=None if env.get("OPENRIDE_LOG") else LogRotation(),
        compile_enabled=not no_compile,
        compile_only=compile_only,
        compile_timeout_s=compile_timeout,
        theme_name=cfg.render.theme,
        themes_dir=THEMES_DIR,
    )


def release_trainer_from_desktop(args: list[str], notify: Callable[[str, bool], None]) -> int:
    """Entrée de bureau « Libérer le trainer » : `openride-core release-trainer`, résultat notifié."""
    config_path = _config_arg(args)
    cmd = [sys.executable, "-m", "openride_core", "release-trainer",
           *(["--config", str(config_path)] if config_path else [])]
    try:
        code = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=120).returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        notify(f"Trainer non libéré : {exc}", True)
        return 1
    if code == 0:
        notify("Trainer libéré : une autre application peut s'y connecter.", False)
    else:
        notify("Trainer non libéré : allumez-le, approchez-le du PC et réessayez.", True)
    return 0 if code == 0 else 1


def main(argv: list[str] | None = None, message: Callable[[str, bool], None] | None = None) -> int:
    """`openride` ; `message(texte, erreur)` affiche une fenêtre (défaut : sans terminal seulement)."""
    from .config import ConfigError

    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if args and args[0] == "--version":
        print(f"openride {__version__}")
        return 0
    if message is None:
        message = (lambda text, error: None) if _default_echo() else desktop_message
    if "--release-trainer" in args:
        args.remove("--release-trainer")
        return release_trainer_from_desktop(args, message)

    def fail(text: str) -> int:
        print(f"openride : {text}", file=sys.stderr)
        message(f"OpenRide ne peut pas démarrer : {text}", True)
        return 1

    if update_in_progress():
        return fail("une mise à jour est en cours. Relancez OpenRide quand elle sera terminée.")
    first_run = False
    if _config_arg(args) is None:
        try:
            first_run = ensure_first_run()
        except OSError as exc:
            return fail(f"création de ~/OpenRide impossible : {exc}")
    try:
        sup = build_supervisor(args)
    except ConfigError as exc:
        return fail(f"configuration invalide : {exc}")
    except ValueError as exc:
        return fail(str(exc))
    except FileNotFoundError as exc:
        return fail(str(exc))
    sup.alert = lambda text: message(text, True)
    if first_run:
        sup.core_cmd.append("--first-run")
        message(FIRST_RUN_INFO, False)
    return sup.run()


if __name__ == "__main__":
    raise SystemExit(main())
