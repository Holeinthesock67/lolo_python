"""Tests du lanceur `openride` (lot K6) avec de faux programmes à la place du core et de l'engine."""

import os
import signal
import sys
import threading
from pathlib import Path

import pytest

from openride_core import launcher
from openride_core.launcher import Supervisor

FAKE = r'''
import os, signal, sys, time
from pathlib import Path
role, mode, marks = sys.argv[1], sys.argv[2], Path(sys.argv[3])
def mark(name):
    with (marks / name).open("a") as fh:
        fh.write(f"{os.getpid()}\n")
mark(f"{role}_start")
if mode == "ignore":                      # core qui ignore SIGINT
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    while True:
        time.sleep(0.05)
if mode == "release":
    sys.exit(0)
if mode.startswith("crash"):              # crash:N:T : plante N fois (après T s) puis tient ; crash : toujours
    parts = mode.split(":")
    limit = int(parts[1]) if len(parts) > 1 else 10**6
    delay = float(parts[2]) if len(parts) > 2 else 0.1
    n = len((marks / f"{role}_start").read_text().split())
    if n <= limit:
        time.sleep(delay)
        sys.exit(3)
if mode.startswith("exit0"):              # exit0:T : se ferme normalement au bout de T s
    time.sleep(float(mode.split(":")[1]))
    sys.exit(0)
def on_stop(signum, _f):
    mark(f"{role}_{signal.Signals(signum).name}")
    sys.exit(0)
signal.signal(signal.SIGINT, on_stop)
signal.signal(signal.SIGTERM, on_stop)
while True:
    time.sleep(0.05)
'''


@pytest.fixture
def fake(tmp_path: Path):
    script = tmp_path / "fake.py"
    script.write_text(FAKE)
    marks = tmp_path / "marks"
    marks.mkdir()

    def make(core: str = "run", engine: str = "run", **kw) -> tuple[Supervisor, list[str]]:
        said: list[str] = []
        sup = Supervisor(
            core_cmd=[sys.executable, str(script), "core", core, str(marks)],
            engine_cmd=[sys.executable, str(script), "engine", engine, str(marks)],
            release_cmd=[sys.executable, str(script), "release", "release", str(marks)],
            log_path=tmp_path / "run.log",
            stop_timeout_s=kw.pop("stop_timeout_s", 2.0), engine_stop_timeout_s=1.0,
            restart_delay_s=0.0, startup_grace_s=kw.pop("startup_grace_s", 0.3), poll_s=0.02, say=said.append, **kw)
        return sup, said

    make.marks = marks
    return make


def count(marks: Path, name: str) -> int:
    f = marks / name
    return len(f.read_text().split()) if f.exists() else 0


def assert_no_orphans(sup: Supervisor) -> None:
    assert sup.started_pids
    for pid in sup.started_pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_engine_closes_normally_core_gets_sigint(fake):
    sup, said = fake(engine="exit0:0.3")
    assert sup.run() == 0
    assert count(fake.marks, "core_SIGINT") == 1
    assert count(fake.marks, "release_start") == 0
    assert_no_orphans(sup)


def test_core_ignoring_sigint_is_killed_then_trainer_released(fake):
    sup, said = fake(core="ignore", engine="exit0:0.2", stop_timeout_s=0.5)
    assert sup.run() == 0
    assert count(fake.marks, "release_start") == 1
    assert any("arrêt forcé" in m for m in said)
    assert_no_orphans(sup)


def test_engine_crashing_twice_is_restarted(fake):
    sup, said = fake(engine="crash:2:0.1")
    timer = threading.Timer(1.5, lambda: os.kill(os.getpid(), signal.SIGTERM))
    timer.start()
    try:
        assert sup.run() == 0
    finally:
        timer.cancel()
    assert sup.restarts == 2
    assert count(fake.marks, "engine_start") == 3
    assert count(fake.marks, "engine_SIGTERM") == 1 and count(fake.marks, "core_SIGINT") == 1
    assert sum("relance" in m for m in said) == 2
    assert_no_orphans(sup)


def test_engine_crashing_four_times_gives_up(fake):
    sup, said = fake(engine="crash:99:0.05")
    assert sup.run() == 1
    assert sup.restarts == 3
    assert count(fake.marks, "engine_start") == 4
    assert count(fake.marks, "core_SIGINT") == 1
    assert any("abandon" in m for m in said)
    assert_no_orphans(sup)


def test_old_engine_crashes_leave_the_window(fake):
    now = [0.0]

    def clock():
        now[0] += 60.0   # chaque lecture avance d'une minute : jamais 4 plantages en 2 min
        return now[0]

    sup, said = fake(engine="crash:5:0.05", clock=clock, startup_grace_s=0.0)
    timer = threading.Timer(2.0, lambda: os.kill(os.getpid(), signal.SIGTERM))
    timer.start()
    try:
        assert sup.run() == 0
    finally:
        timer.cancel()
    assert sup.restarts == 5 and not any("abandon" in m for m in said)
    assert_no_orphans(sup)


def test_core_crash_stops_engine_and_mentions_recover(fake):
    sup, said = fake(core="crash:99:0.6")
    assert sup.run() == 1
    assert count(fake.marks, "engine_SIGTERM") == 1
    assert any("openride-core recover" in m for m in said)
    assert_no_orphans(sup)


def test_core_dying_at_startup(fake):
    sup, said = fake(core="crash:99:0.0")
    assert sup.run() == 1
    assert count(fake.marks, "engine_start") == 0
    assert any("au démarrage" in m for m in said)
    assert_no_orphans(sup)


@pytest.mark.parametrize("sig", [signal.SIGHUP, signal.SIGINT])
def test_signal_stops_both_cleanly(fake, sig):
    sup, said = fake()
    timer = threading.Timer(0.8, lambda: os.kill(os.getpid(), sig))
    timer.start()
    try:
        assert sup.run() == 0
    finally:
        timer.cancel()
    assert count(fake.marks, "core_SIGINT") == 1 and count(fake.marks, "engine_SIGTERM") == 1
    assert count(fake.marks, "release_start") == 0
    assert_no_orphans(sup)
    assert signal.getsignal(signal.SIGHUP) is not sup._on_signal   # gestionnaires rendus


def test_build_supervisor_reads_config_and_checks_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("openride_core.config.DEFAULT_CONFIG_PATH", tmp_path / "absent_default.toml")
    cfg = tmp_path / "config.toml"
    cfg.write_text("[ipc]\nport_state = 6005\nport_commands = 6006\n[render]\nquality = \"high\"\ntheme = \"alpes\"\n")
    godot = tmp_path / "godot"
    godot.write_text("#!/bin/sh\n")
    godot.chmod(0o755)
    env = {"GODOT": str(godot), "OPENRIDE_LOG": str(tmp_path / "x.log"), "GODOT_ARGS": "--verbose"}

    sup = launcher.build_supervisor(["--trainer", "mock", "--config", str(cfg)], env)
    assert sup.core_cmd[-5:] == ["run", "--trainer", "mock", "--config", str(cfg)]
    assert sup.engine_cmd[0] == str(godot) and "--verbose" in sup.engine_cmd
    assert sup.engine_cmd[-4:] == [
        "--ipc-state-port=6005",
        "--ipc-cmd-port=6006",
        "--quality=high",
        "--theme=alpes",
    ]
    assert sup.release_cmd[-3:] == ["release-trainer", "--config", str(cfg)]
    assert sup.log_path == tmp_path / "x.log"

    default = launcher.build_supervisor([f"--config={cfg}"], env)
    assert default.core_cmd[-1] == f"--config={cfg}"
    no_cfg = launcher.build_supervisor([], {**env})
    assert no_cfg.core_cmd[-6:] == ["run", *launcher.DEFAULT_CORE_ARGS]
    assert no_cfg.engine_cmd[-4:] == [
        "--ipc-state-port=5005",
        "--ipc-cmd-port=5006",
        "--quality=low",
        "--theme=default",
    ]

    with pytest.raises(FileNotFoundError, match="Godot introuvable"):
        launcher.build_supervisor(["--config", str(cfg)], {**env, "GODOT": str(tmp_path / "absent")})


def test_main_reports_invalid_config(tmp_path: Path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_text("[ipc]\nport_state = 5005\nport_commands = 5005\n")
    assert launcher.main(["--config", str(bad)]) == 1
    assert "configuration invalide" in capsys.readouterr().err
