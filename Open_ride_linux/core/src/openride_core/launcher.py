"""Lanceur unique `openride` : démarre le core et l'engine, les surveille, arrête tout proprement (lot K6).

    openride [options de « openride-core run »]      # défaut : --trainer ftms --input click --autostart

Remplace à terme `scripts/openride-dev.sh`, avec le même comportement de référence :
- un journal par lancement, `~/OpenRide/Logs/openride_AAAA-MM-JJ_HH-MM-SS.log` (lot M8) : sortie du
  core, sortie de Godot (lignes préfixées `[engine] `) et messages du lanceur (`[openride] `,
  horodatés comme le core). `~/run_trainer.log` est un lien vers le dernier journal ; on garde
  les 20 derniers et 200 Mo au plus. `OPENRIDE_LOG` remplace ce journal tournant (sans lien ni
  rotation). Sans terminal (raccourci de bureau), les messages ne vont que dans le journal ;
- l'engine (`GODOT --path engine -- --ipc-state-port=… --ipc-cmd-port=…`) reçoit les ports de la
  configuration (`--config` éventuel, sinon `~/OpenRide/config.toml`) ; variables `GODOT`,
  `GODOT_ARGS` et `OPENRIDE_ENGINE` (dossier du projet Godot).

Supervision :
- l'engine se ferme normalement (code 0) → arrêt propre du core (SIGINT), 10 s au plus, puis
  SIGKILL et `openride-core release-trainer` ;
- l'engine plante (code ≠ 0) → il est relancé, au plus 3 fois en 2 minutes ; s'il reste absent
  plus de 2 s (heartbeat perdu), le core met la séance en pause (`engine_lost`, contrat IPC §6) et
  la reprend au retour de l'engine ; une relance plus rapide passe sans pause ;
  au-delà, abandon : arrêt propre du core, code 1 ;
- le core s'arrête ou plante → l'engine est arrêté ; en cas de plantage, rappel de
  `openride-core recover` (le journal de la séance reste sur disque) ;
- SIGINT, SIGTERM ou SIGHUP (terminal fermé) reçus par le lanceur → même arrêt propre des deux.

Les commandes du core, de l'engine et de la libération du trainer sont des paramètres de
`Supervisor` : les tests les remplacent par de faux programmes.
"""

from __future__ import annotations

import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Callable

DEFAULT_GODOT = Path.home() / "Applications" / "godot" / "Godot_v4.3-stable_linux.x86_64"
DEFAULT_LOG = Path.home() / "run_trainer.log"   # lien vers le dernier journal du lanceur
LOGS_DIR = Path.home() / "OpenRide" / "Logs"
LOG_PREFIX = "openride_"
KEEP_LOGS = 20
MAX_LOGS_BYTES = 200 * 1024 * 1024
DEFAULT_ENGINE_DIR = Path(__file__).resolve().parents[3] / "engine"
DEFAULT_CORE_ARGS = ["--trainer", "ftms", "--input", "click", "--autostart"]

STOP_SIGNALS = tuple(getattr(signal, s) for s in ("SIGINT", "SIGTERM", "SIGHUP") if hasattr(signal, s))


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

    started_pids: list[int] = field(default_factory=list, init=False)
    restarts: int = field(default=0, init=False)
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

    def _open_log(self) -> None:
        if self.rotation is not None:
            self.log_path = self.rotation.prepare()
            self._log = self.log_path.open("ab", buffering=0)
            for note in self.rotation.notes:
                self._say(note)
            self.rotation.notes.clear()
        else:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = self.log_path.open("wb", buffering=0)
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

    def _start_core(self) -> subprocess.Popen:
        if self._log is None:
            self._open_log()
        return self._spawn(self.core_cmd, stdin=subprocess.DEVNULL, stdout=self._log, stderr=subprocess.STDOUT)

    def _start_engine(self) -> subprocess.Popen:
        if self._log is None:
            return self._spawn(self.engine_cmd, stdin=subprocess.DEVNULL)
        p = self._spawn(self.engine_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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

    # --- signaux -----------------------------------------------------------------------

    def _on_signal(self, signum: int, _frame) -> None:
        self._stop_signal = signum

    # --- boucle ------------------------------------------------------------------------

    def run(self) -> int:
        previous = {s: signal.signal(s, self._on_signal) for s in STOP_SIGNALS}
        core: subprocess.Popen | None = None
        engine: subprocess.Popen | None = None
        try:
            core = self._start_core()
            deadline = self.clock() + self.startup_grace_s
            while self.clock() < deadline and core.poll() is None and self._stop_signal is None:
                time.sleep(self.poll_s)
            if core.poll() is not None:
                self._say(f"le core s'est arrêté au démarrage (code {core.returncode}) ; voir {self.log_path}")
                self._print_log_tail(20, only_alerts=False)
                return 1
            if self._stop_signal is not None:
                return self._finish(core, None, 0)

            engine = self._start_engine()
            crashes: list[float] = []
            while True:
                time.sleep(self.poll_s)
                if self._stop_signal is not None:
                    self._say(f"signal {signal.Signals(self._stop_signal).name} reçu : arrêt de la séance.")
                    return self._finish(core, engine, 0)

                if core.poll() is not None:
                    code = core.returncode
                    self._stop_engine(engine)
                    if code != 0:
                        self._say(f"le core s'est arrêté brutalement (code {code}). La séance est dans le journal : "
                                 "`openride-core recover` en fait un FIT.")
                        self._release_trainer()
                        return self._finish(core, engine, 1)
                    return self._finish(core, engine, 0)

                if engine.poll() is not None:
                    code = engine.returncode
                    if code == 0:
                        return self._finish(core, engine, 0)
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

def _config_arg(args: list[str]) -> Path | None:
    for i, a in enumerate(args):
        if a.startswith("--config="):
            return Path(a.split("=", 1)[1])
        if a == "--config" and i + 1 < len(args):
            return Path(args[i + 1])
    return None


def build_supervisor(core_args: list[str], env: dict[str, str] | None = None) -> Supervisor:
    """Construit le superviseur réel ; lève `ConfigError` ou `FileNotFoundError` avec un message lisible."""
    from . import config as config_mod

    env = os.environ if env is None else env
    core_args = core_args or list(DEFAULT_CORE_ARGS)
    config_path = _config_arg(core_args)
    cfg = config_mod.load(config_path)   # ConfigError si invalide

    godot = Path(env.get("GODOT") or DEFAULT_GODOT).expanduser()
    if not (godot.is_file() and os.access(godot, os.X_OK)):
        raise FileNotFoundError(f"Godot introuvable : {godot} (définir GODOT=/chemin/vers/godot)")
    engine_dir = Path(env.get("OPENRIDE_ENGINE") or DEFAULT_ENGINE_DIR).expanduser()
    if not (engine_dir / "project.godot").is_file():
        raise FileNotFoundError(f"projet Godot introuvable : {engine_dir} (définir OPENRIDE_ENGINE)")

    core = [sys.executable, "-m", "openride_core"]
    config_args = ["--config", str(config_path)] if config_path else []
    return Supervisor(
        core_cmd=[*core, "run", *core_args],
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
        ],
        release_cmd=[*core, "release-trainer", *config_args],
        log_path=Path(env["OPENRIDE_LOG"]).expanduser() if env.get("OPENRIDE_LOG") else DEFAULT_LOG,
        rotation=None if env.get("OPENRIDE_LOG") else LogRotation(),
    )


def main(argv: list[str] | None = None) -> int:
    from .config import ConfigError

    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    try:
        sup = build_supervisor(args)
    except ConfigError as exc:
        print(f"openride : configuration invalide : {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"openride : {exc}", file=sys.stderr)
        return 1
    return sup.run()


if __name__ == "__main__":
    raise SystemExit(main())
