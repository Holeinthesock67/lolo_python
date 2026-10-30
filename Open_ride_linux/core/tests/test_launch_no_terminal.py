"""Lot N14 : lancement sans terminal (premier démarrage, fenêtres d'erreur, mise à jour, installation).

Tout se passe dans des dossiers temporaires : jamais le vrai `~/OpenRide/config.toml`.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from openride_core import config as config_mod
from openride_core import launcher
from openride_core.launcher import Supervisor

ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT_DIR / "scripts"
BASH = shutil.which("bash")
GIT = shutil.which("git")

FAKE_CORE = r'''
import os, sys, time
mode = "run" if sys.argv[1:] == ["engine"] else os.environ.get("FAKE_MODE", "run")
if mode == "port":
    print("2026-10-25 10:00:00,000 ERROR   openride_core RuntimeError: Impossible de démarrer l'IPC UDP "
          "sur 127.0.0.1:5005 : [Errno 98] Address already in use", flush=True)
    sys.exit(1)
if mode == "refused":
    time.sleep(0.5)
    print("2026-10-25 10:00:01,000 ERROR   session Le trainer refuse le contrôle FTMS après deux reprises.",
          flush=True)
if mode == "crash":
    time.sleep(0.5)
    sys.exit(3)
import signal
signal.signal(signal.SIGINT, lambda *a: sys.exit(0))
signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
while True:
    time.sleep(0.05)
'''


def executable(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`~/OpenRide` temporaire, Godot et projet factices, journal du lanceur temporaire."""
    home = tmp_path / "OpenRide"
    monkeypatch.setattr(config_mod, "OPENRIDE_HOME", home)
    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG_PATH", home / "config.toml")
    godot = executable(tmp_path / "godot", "#!/bin/sh\necho 4.7.2.stable.official\n")
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "project.godot").write_text("", encoding="utf-8")
    monkeypatch.setenv("GODOT", str(godot))
    monkeypatch.setenv("OPENRIDE_ENGINE", str(engine))
    monkeypatch.setenv("OPENRIDE_LOG", str(tmp_path / "openride.log"))
    return home


def capture_run(monkeypatch: pytest.MonkeyPatch) -> list[Supervisor]:
    runs: list[Supervisor] = []

    def fake_run(self: Supervisor) -> int:
        runs.append(self)
        return 0
    monkeypatch.setattr(Supervisor, "run", fake_run)
    return runs


# --- premier démarrage ---------------------------------------------------------------------------

def test_first_run_creates_config_and_folders_then_not_again(home: Path, monkeypatch):
    """Critère 2 : configuration créée depuis le modèle, dossiers, --first-run une seule fois."""
    runs = capture_run(monkeypatch)
    messages: list[tuple[str, bool]] = []
    say = lambda text, error: messages.append((text, error))   # noqa: E731

    assert launcher.main(["--trainer", "mock"], message=say) == 0
    cfg = home / "config.toml"
    # Le modèle, réparti par la migration des profils (lot MJ5) : réglages du joueur dans principal.
    template = config_mod.from_dict(tomllib.loads((SCRIPTS / "config.example.toml").read_text(encoding="utf-8")))
    assert config_mod.load(cfg, home / "Profils" / "principal" / "profil.toml") == template
    assert "ftp_w = " not in cfg.read_text(encoding="utf-8")
    assert (home / "GPX").is_dir() and (home / "Workouts").is_dir()
    assert runs[0].core_cmd[-1] == "--first-run"
    assert any("devices --save" in text and not error for text, error in messages)

    before = cfg.stat().st_mtime_ns
    assert launcher.main(["--trainer", "mock"], message=say) == 0
    assert "--first-run" not in runs[1].core_cmd
    assert cfg.stat().st_mtime_ns == before


def test_config_template_is_valid_and_has_no_real_values():
    """Critère 7 : modèle valide, sans adresse, nom d'appareil réel ni chemin personnel."""
    text = (SCRIPTS / "config.example.toml").read_text(encoding="utf-8")
    config_mod.from_dict(tomllib.loads(text))
    data = tomllib.loads(text)
    assert all(not data["drivers"][k] for k in ("trainer_address", "click_address",
                                                  "click_minus_address", "hr_address"))
    assert "/home/" not in text and data["engine"]["godot"] == ""


def test_core_accepts_first_run():
    from openride_core.__main__ import build_parser

    assert build_parser().parse_args(["run", "--first-run"]).first_run


# --- fenêtres d'erreur ---------------------------------------------------------------------------

def test_missing_godot_is_shown_in_a_window(home: Path, monkeypatch):
    capture_run(monkeypatch)
    monkeypatch.setenv("GODOT", str(home / "absent" / "godot"))
    messages: list[tuple[str, bool]] = []
    assert launcher.main([], message=lambda t, e: messages.append((t, e))) == 1
    assert messages and messages[-1][1] and "Godot introuvable" in messages[-1][0]


def test_invalid_config_is_shown_in_a_window(home: Path, monkeypatch):
    capture_run(monkeypatch)
    home.mkdir(parents=True)
    (home / "config.toml").write_text("[rider]\nftp_w = 5\n", encoding="utf-8")
    messages: list[tuple[str, bool]] = []
    assert launcher.main([], message=lambda t, e: messages.append((t, e))) == 1
    assert "configuration invalide" in messages[-1][0] and "ftp_w" in messages[-1][0]


def make_supervisor(tmp_path: Path, mode: str, alerts: list[str]) -> Supervisor:
    script = tmp_path / "fake_core.py"
    script.write_text(FAKE_CORE, encoding="utf-8")
    return Supervisor(
        core_cmd=[sys.executable, str(script)], engine_cmd=[sys.executable, str(script), "engine"], release_cmd=[sys.executable, "-c", "pass"],
        log_path=tmp_path / "run.log", stop_timeout_s=2.0, engine_stop_timeout_s=1.0,
        restart_delay_s=0.0, startup_grace_s=0.3, poll_s=0.02, say=lambda m: None,
        echo=lambda: False, compile_enabled=False, alert=alerts.append)


@pytest.mark.parametrize("mode, expected", [
    ("port", "port IPC"),
    ("refused", "réservé par une autre application"),
    ("crash", "planté 4 fois"),
])
def test_launcher_errors_give_a_precise_message(tmp_path: Path, monkeypatch, mode, expected):
    """Critère 3 : port occupé, trainer réservé, plantages répétés : message précis, code 1."""
    monkeypatch.setenv("FAKE_MODE", mode)
    alerts: list[str] = []
    sup = make_supervisor(tmp_path, mode, alerts)
    assert sup.run() == 1
    assert len(alerts) == 1 and expected in alerts[0]
    assert str(sup.log_path) in alerts[0]
    if mode == "refused":
        assert "Libérer le trainer" in alerts[0]


def test_desktop_message_falls_back_to_nothing(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    launcher.desktop_message("rien à afficher")   # aucun outil : ni erreur ni fenêtre


def test_release_trainer_entry_notifies(monkeypatch):
    calls: list[list[str]] = []

    class Done:
        def __init__(self, code: int) -> None:
            self.returncode = code

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd) or Done(0))
    messages: list[tuple[str, bool]] = []
    assert launcher.main(["--release-trainer"], message=lambda t, e: messages.append((t, e))) == 0
    assert calls[0][-1] == "release-trainer"
    assert messages == [("Trainer libéré : une autre application peut s'y connecter.", False)]

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: Done(1))
    assert launcher.main(["--release-trainer"], message=lambda t, e: messages.append((t, e))) == 1
    assert messages[-1][1] and "non libéré" in messages[-1][0]


# --- update.sh -----------------------------------------------------------------------------------

def git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True,
                          text=True).stdout.strip()


@pytest.mark.skipif(not (BASH and GIT), reason="bash ou git absent")
def test_update_script_fast_forward_only(tmp_path: Path):
    """Critère 5 : refus sur modification locale ou sans avance rapide, succès sinon."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))
    proj = work / "Open_ride_linux"
    (proj / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPTS / "update.sh", proj / "scripts" / "update.sh")
    (proj / "README.md").write_text("v1\n", encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "v1")
    git(work, "push", "-q", "-u", "origin", "main")
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(origin), str(other))

    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "OPENRIDE_NO_PIP": "1", "PATH": "/usr/bin:/bin", "HOME": str(home),
           "OPENRIDE_NO_GUI": "1"}

    def update() -> subprocess.CompletedProcess:
        return subprocess.run([BASH, str(proj / "scripts" / "update.sh")], env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True)

    r = update()
    assert r.returncode == 0 and "déjà à jour" in r.stdout, r.stdout + r.stderr

    (other / "Open_ride_linux" / "README.md").write_text("v2\n", encoding="utf-8")
    git(other, "commit", "-q", "-am", "v2")
    git(other, "push", "-q")
    r = update()
    assert r.returncode == 0 and "mis à jour" in r.stdout, r.stdout + r.stderr
    assert (proj / "README.md").read_text(encoding="utf-8") == "v2\n"

    (proj / "README.md").write_text("local\n", encoding="utf-8")
    r = update()
    assert r.returncode == 1 and "modifications locales" in r.stdout
    assert (proj / "README.md").read_text(encoding="utf-8") == "local\n"   # rien n'est perdu
    git(work, "checkout", "--", ".")

    git(work, "commit", "-q", "--allow-empty", "-m", "local")
    (other / "Open_ride_linux" / "README.md").write_text("v3\n", encoding="utf-8")
    git(other, "commit", "-q", "-am", "v3")
    git(other, "push", "-q")
    head = git(work, "rev-parse", "HEAD")
    r = update()
    assert r.returncode == 1 and "avance rapide" in r.stdout
    assert "1 commit(s)" in r.stdout and "git branch sauvegarde-" in r.stdout   # quoi faire
    assert git(work, "rev-parse", "HEAD") == head
    log = (home / "OpenRide" / "Logs" / "update.log").read_text(encoding="utf-8")
    assert "local" in log   # le commit local est listé au journal


def _update_repo(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """Dépôt de test à jour d'un commit (v2 publié après le clone) ; renvoie (work, proj, env)."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))
    proj = work / "Open_ride_linux"
    (proj / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPTS / "update.sh", proj / "scripts" / "update.sh")
    (proj / "README.md").write_text("v1\n", encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "v1")
    git(work, "push", "-q", "-u", "origin", "main")
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(origin), str(other))
    (other / "Open_ride_linux" / "README.md").write_text("v2\n", encoding="utf-8")
    git(other, "commit", "-q", "-am", "v2")
    git(other, "push", "-q")
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "OPENRIDE_NO_PIP": "1", "PATH": "/usr/bin:/bin", "HOME": str(home),
           "OPENRIDE_NO_GUI": "1"}
    return work, proj, env


def _run_update(proj: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run([BASH, str(proj / "scripts" / "update.sh")], env=env,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)


@pytest.mark.skipif(not (BASH and GIT) or not Path("/proc/self/cmdline").exists(),
                    reason="bash, git ou /proc absent")
@pytest.mark.parametrize("kind", ["venv", "godot"])
def test_update_script_refuses_while_game_open(tmp_path: Path, kind: str):
    """Jeu ouvert (Python du venv ou Godot sur `engine`) : refus lisible, dépôt intact ; puis succès."""
    work, proj, env = _update_repo(tmp_path)
    if kind == "venv":
        bin_dir = proj / "core" / ".venv" / "bin"
        bin_dir.mkdir(parents=True)
        fake = bin_dir / "python3"
        fake.symlink_to(sys.executable)
        cmd = [str(fake), "-c", "import time; time.sleep(60)", str(bin_dir / "openride")]
    else:
        cmd = [sys.executable, "-c", "import time; time.sleep(60)", "--path", str(proj / "engine")]
    head = git(work, "rev-parse", "HEAD")
    game = subprocess.Popen(cmd)
    try:
        r = _run_update(proj, env)
        assert r.returncode == 1 and "OpenRide est ouvert" in r.stdout, r.stdout + r.stderr
        assert git(work, "rev-parse", "HEAD") == head   # rien n'a bougé
    finally:
        game.kill()
        game.wait()
    r = _run_update(proj, env)
    assert r.returncode == 0 and "mis à jour" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not (BASH and GIT) or not shutil.which("flock"), reason="bash, git ou flock absent")
def test_update_lock_blocks_second_update_and_launcher(tmp_path: Path, monkeypatch):
    """Verrou ~/OpenRide/.update.lock : seconde mise à jour refusée, lanceur refusé."""
    import fcntl

    work, proj, env = _update_repo(tmp_path)
    lock = Path(env["HOME"]) / "OpenRide" / ".update.lock"
    lock.parent.mkdir(parents=True)
    assert not launcher.update_in_progress(lock)
    with lock.open("a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        assert launcher.update_in_progress(lock)
        r = _run_update(proj, env)
        assert r.returncode == 1 and "déjà en cours" in r.stdout, r.stdout + r.stderr

        monkeypatch.setattr(launcher, "update_in_progress", lambda: True)
        messages: list[tuple[str, bool]] = []
        assert launcher.main([], message=lambda t, e: messages.append((t, e))) == 1
        assert messages and "mise à jour est en cours" in messages[0][0]
        monkeypatch.undo()
    assert not launcher.update_in_progress(lock)


# --- install.sh ----------------------------------------------------------------------------------

@pytest.mark.skipif(not BASH or sys.platform == "win32", reason="bash absent")
def test_install_script_twice_gives_same_result(tmp_path: Path):
    """Critère 6 : deux installations de suite dans un HOME temporaire, Godot factice."""
    home = tmp_path / "home"
    home.mkdir()
    bins = tmp_path / "venv-bin"
    bins.mkdir()
    for cmd in ("openride", "openride-core"):
        executable(bins / cmd, "#!/bin/sh\nexit 0\n")
    godot = executable(tmp_path / "Godot_v4.7.2", "#!/bin/sh\necho 4.7.2.stable.official.77dcf97d8\n")
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "OPENRIDE_NO_PIP": "1",
           "OPENRIDE_PYTHON": sys.executable, "OPENRIDE_BIN_SRC": str(bins), "GODOT": str(godot),
           "PYTHONPATH": os.pathsep.join(sys.path)}

    def install() -> dict[str, bytes]:
        r = subprocess.run([BASH, str(SCRIPTS / "install.sh")], env=env, capture_output=True,
                           text=True, stdin=subprocess.DEVNULL)
        assert r.returncode == 0, r.stdout + r.stderr
        files = [p for p in home.rglob("*") if p.is_file() or p.is_symlink()]
        return {str(p.relative_to(home)): (os.readlink(p).encode() if p.is_symlink() else p.read_bytes())
                for p in files if not p.name.endswith(".bak")}

    first = install()
    cfg = tomllib.loads((home / "OpenRide" / "config.toml").read_text(encoding="utf-8"))
    assert cfg["engine"]["godot"] == str(godot)
    apps = home / ".local" / "share" / "applications"
    assert sorted(p.name for p in apps.glob("*.desktop")) == [
        "openride-release.desktop", "openride-update.desktop", "openride.desktop"]
    assert (home / ".local" / "bin" / "openride").is_symlink()
    assert (home / "OpenRide" / "GPX").is_dir()
    assert install() == first

    env["GODOT"] = str(tmp_path / "absent")
    env_bad = {**env}
    (home / "OpenRide" / "config.toml").write_text("", encoding="utf-8")
    r = subprocess.run([BASH, str(SCRIPTS / "install.sh")], env=env_bad, capture_output=True,
                       text=True, stdin=subprocess.DEVNULL)
    assert r.returncode == 1 and "Godot 4.7 introuvable" in r.stderr

    old = executable(tmp_path / "Godot_v4.3", "#!/bin/sh\necho 4.3.stable.official.77dcf97d8\n")
    r = subprocess.run([BASH, str(SCRIPTS / "install.sh")], env={**env, "GODOT": str(old)},
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert r.returncode == 1 and "Godot 4.7 attendu" in r.stderr and "4.7.2-stable" in r.stderr
