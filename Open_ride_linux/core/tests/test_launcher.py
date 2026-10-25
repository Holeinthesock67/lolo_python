"""Tests du lanceur `openride` (lots K6 et M8) avec de faux programmes à la place du core et de l'engine."""

import os
import signal
import sys
import threading
import time
from pathlib import Path

import pytest

from openride_core import launcher
from openride_core.launcher import LogRotation, Supervisor

FAKE = r'''
import os, signal, sys, time
from pathlib import Path
role, mode, marks = sys.argv[1], sys.argv[2], Path(sys.argv[3])
def mark(name):
    with (marks / name).open("a") as fh:
        fh.write(f"{os.getpid()}\n")
mark(f"{role}_start")
with (marks / f"{role}_argv").open("a") as fh:   # options ajoutées par le lanceur (--resume, journal)
    fh.write(" ".join(sys.argv[4:]) + "\n")
if mode.startswith("say:"):               # say:N:MODE : écrit N lignes d'un coup, puis MODE
    _, n, mode = mode.split(":", 2)
    sys.stdout.write("".join(f"{role} ligne {k}\n" for k in range(int(n))))
    sys.stdout.flush()
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
if mode.startswith("jcrash"):             # jcrash:N:DOSSIER : séance en cours au journal, tué N fois (SIGKILL)
    _, limit, jdir = mode.split(":", 2)
    journal = Path(jdir) / "seance.jsonl"
    if not journal.exists():
        journal.write_text('{"kind":"header","version":1,"route_id":"demo"}\n'
                           '{"kind":"event","event":"start","ts":1}\n')
    if len((marks / f"{role}_start").read_text().split()) <= int(limit):
        time.sleep(0.5)                   # après le délai de démarrage (0,3 s dans ces tests)
        os.kill(os.getpid(), signal.SIGKILL)
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
    script.write_text(FAKE, encoding="utf-8")
    marks = tmp_path / "marks"
    marks.mkdir()

    def make(core: str = "run", engine: str = "run", **kw) -> tuple[Supervisor, list[str]]:
        said: list[str] = []
        kw.setdefault("echo", lambda: True)
        kw.setdefault("compile_enabled", False)
        sup = Supervisor(
            core_cmd=[sys.executable, str(script), "core", core, str(marks)],
            engine_cmd=[sys.executable, str(script), "engine", engine, str(marks)],
            release_cmd=[sys.executable, str(script), "release", "release", str(marks)],
            recover_cmd=[sys.executable, str(script), "recover", "release", str(marks)],
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
        if sys.platform != "win32":
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
    assert count(fake.marks, "core_start") == 4   # trois relances (lot N8), puis abandon
    assert count(fake.marks, "engine_SIGTERM") == 1
    assert any("openride-core recover" in m for m in said)
    assert_no_orphans(sup)


def lines(marks: Path, name: str) -> list[str]:
    f = marks / name
    return f.read_text().splitlines() if f.exists() else []


def test_core_crash_during_session_is_relaunched_with_resume(fake, tmp_path: Path):
    """Lot N8 : relance avec --resume, trainer relâché, engine laissé ouvert."""
    jdir = tmp_path / "journal"
    jdir.mkdir()
    sup, said = fake(core=f"jcrash:2:{jdir}", journal_dir=jdir)
    timer = threading.Timer(3.0, lambda: os.kill(os.getpid(), signal.SIGTERM))
    timer.start()
    try:
        assert sup.run() == 0
    finally:
        timer.cancel()
    journal = jdir / "seance.jsonl"
    assert lines(fake.marks, "core_argv") == ["", f"--resume {journal}", f"--resume {journal}"]
    assert sup.core_restarts == 2 and count(fake.marks, "release_start") == 2
    assert count(fake.marks, "engine_start") == 1 and count(fake.marks, "engine_SIGTERM") == 1
    assert sum("reprise de la séance en pause" in m for m in said) == 2
    assert count(fake.marks, "recover_start") == 0
    assert_no_orphans(sup)


def test_four_core_crashes_in_ten_minutes_call_recover(fake, tmp_path: Path):
    """Critère 4 : pas de quatrième relance, `recover` sur le journal, message clair."""
    jdir = tmp_path / "journal"
    jdir.mkdir()
    sup, said = fake(core=f"jcrash:99:{jdir}", journal_dir=jdir)
    assert sup.run() == 1
    assert count(fake.marks, "core_start") == 4 and sup.core_restarts == 3
    assert lines(fake.marks, "recover_argv") == [str(jdir / "seance.jsonl")]
    assert count(fake.marks, "engine_SIGTERM") == 1
    assert any("abandon" in m and "recover" in m for m in said)
    assert_no_orphans(sup)


def test_core_crash_outside_a_session_is_relaunched_without_resume(fake, tmp_path: Path):
    """Critère 6 : plantage hors séance (aucun journal non terminé de ce lancement)."""
    jdir = tmp_path / "journal"
    jdir.mkdir()
    old = jdir / "ancienne.jsonl"   # séance plantée d'un lancement précédent : pas reprise
    old.write_text('{"kind":"header","version":1}\n{"kind":"event","event":"start","ts":1}\n')
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    sup, said = fake(core="crash:1:0.4", journal_dir=jdir)
    timer = threading.Timer(1.5, lambda: os.kill(os.getpid(), signal.SIGTERM))
    timer.start()
    try:
        assert sup.run() == 0
    finally:
        timer.cancel()
    assert lines(fake.marks, "core_argv") == ["", ""]
    assert any("hors séance" in m for m in said)
    assert_no_orphans(sup)


def test_core_dying_at_startup(fake):
    sup, said = fake(core="crash:99:0.0")
    assert sup.run() == 1
    assert count(fake.marks, "engine_start") == 0
    assert any("au démarrage" in m for m in said)
    assert_no_orphans(sup)


TEST_SIGNALS = [signal.SIGHUP, signal.SIGINT] if hasattr(signal, "SIGHUP") else [signal.SIGINT, signal.SIGTERM]


@pytest.mark.parametrize("sig", TEST_SIGNALS)
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
    assert signal.getsignal(sig) is not sup._on_signal   # gestionnaires rendus


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
    assert sup.engine_cmd[-5:] == [
        "--ipc-state-port=6005",
        "--ipc-cmd-port=6006",
        "--quality=high",
        "--theme=alpes",
        "--visual-grade=1.0",
    ]
    assert sup.release_cmd[-3:] == ["release-trainer", "--config", str(cfg)]
    assert sup.log_path == tmp_path / "x.log"

    default = launcher.build_supervisor([f"--config={cfg}"], env)
    assert default.core_cmd[-1] == f"--config={cfg}"
    no_cfg = launcher.build_supervisor([], {**env})
    assert no_cfg.core_cmd[-(len(launcher.DEFAULT_CORE_ARGS) + 1):] == ["run", *launcher.DEFAULT_CORE_ARGS]
    assert "--autostart" not in launcher.DEFAULT_CORE_ARGS   # menus de l'engine (lot N6)
    assert no_cfg.engine_cmd[-5:] == [
        "--ipc-state-port=5005",
        "--ipc-cmd-port=5006",
        "--quality=low",
        "--theme=default",
        "--visual-grade=1.0",
    ]

    with pytest.raises(FileNotFoundError, match="Godot introuvable"):
        launcher.build_supervisor(["--config", str(cfg)], {**env, "GODOT": str(tmp_path / "absent")})


def test_main_reports_invalid_config(tmp_path: Path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_text("[ipc]\nport_state = 5005\nport_commands = 5005\n")
    assert launcher.main(["--config", str(bad)]) == 1
    assert "configuration invalide" in capsys.readouterr().err


# --- lot M8 : journal du lanceur ------------------------------------------------------------

@pytest.fixture
def rotation(tmp_path: Path) -> LogRotation:
    return LogRotation(logs_dir=tmp_path / "Logs", link=tmp_path / "run_trainer.log")


def test_log_has_core_engine_and_launcher_lines(fake, rotation):
    """Critère 2 : sortie du core telle quelle, de l'engine préfixée, messages du lanceur horodatés."""
    sup, said = fake(core="say:3:run", engine="say:2:exit0:0.3", rotation=rotation)
    assert sup.run() == 0
    assert sup.log_path.parent == rotation.logs_dir and sup.log_path.name.startswith("openride_")
    lines = sup.log_path.read_text(encoding="utf-8").splitlines()
    assert {"core ligne 0", "core ligne 2"} <= set(lines)
    assert {"[engine] engine ligne 0", "[engine] engine ligne 1"} <= set(lines)
    ours = [ln for ln in lines if "[openride]" in ln]
    assert any(ln.endswith("[openride] arrêté. Journal complet : " + str(sup.log_path)) for ln in ours)
    from openride_core.tools.log_report import LINE_RE
    assert all(LINE_RE.match(ln) for ln in ours)   # même format que le core : log_report les lit
    assert said   # avec un terminal, aussi à l'écran
    assert_no_orphans(sup)


def test_run_trainer_link_follows_the_last_log(fake, rotation, tmp_path):
    """Critère 3 : lien vers le dernier journal ; l'ancien fichier ordinaire est renommé une fois."""
    rotation.link.write_text("séance d'hier\n", encoding="utf-8")
    first, _ = fake(engine="exit0:0.1", rotation=rotation)
    assert first.run() == 0
    old = tmp_path / "run_trainer.log.ancien"
    assert old.read_text(encoding="utf-8") == "séance d'hier\n"
    assert rotation.link.is_symlink() and rotation.link.resolve() == first.log_path.resolve()
    second, _ = fake(engine="exit0:0.1", rotation=rotation)
    assert second.run() == 0
    assert second.log_path != first.log_path and first.log_path.exists()
    assert rotation.link.resolve() == second.log_path.resolve()
    assert old.read_text(encoding="utf-8") == "séance d'hier\n"
    assert "Journal complet" in rotation.link.read_text(encoding="utf-8")


def _fake_logs(d: Path, n: int, size: int = 10) -> list[Path]:
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for k in range(n):
        p = d / f"openride_2026-01-{k + 1:02d}_10-00-00.log"
        with p.open("wb") as fh:
            fh.truncate(size)   # fichier creux
        out.append(p)
    return out


def test_rotation_keeps_the_last_20(rotation):
    """Critère 4 : 25 journaux factices, il en reste 20 après un lancement (dont le nouveau)."""
    old = _fake_logs(rotation.logs_dir, 25)
    new = rotation.prepare()
    logs = rotation.logs()
    assert len(logs) == 20 and new in logs
    assert not any(p.exists() for p in old[:6]) and all(p.exists() for p in old[6:])


def test_rotation_keeps_at_most_200_mb(rotation):
    old = _fake_logs(rotation.logs_dir, 6, size=60 * 1024 * 1024)   # 360 Mo creux
    rotation.prepare()
    assert [p.exists() for p in old] == [False, False, False, True, True, True]
    assert sum(p.stat().st_size for p in rotation.logs()) <= rotation.max_bytes


def test_two_launches_in_the_same_second(rotation):
    a, b = rotation.prepare(now=1_761_300_000.0), rotation.prepare(now=1_761_300_000.0)
    assert a != b and b.name.endswith("_2.log")


def test_engine_flood_does_not_delay_the_stop(fake, rotation):
    """Critère 5 : 10 000 lignes d'un coup ; arrêt propre dans les délais, toutes au journal."""
    sup, _ = fake(engine="say:10000:run", rotation=rotation)
    timer = threading.Timer(1.0, lambda: os.kill(os.getpid(), signal.SIGTERM))
    t0 = time.monotonic()
    timer.start()
    try:
        assert sup.run() == 0
    finally:
        timer.cancel()
    assert time.monotonic() - t0 < 1.0 + sup.engine_stop_timeout_s + sup.stop_timeout_s
    lines = sup.log_path.read_text(encoding="utf-8").splitlines()
    assert sum(ln.startswith("[engine] engine ligne ") for ln in lines) == 10000
    assert count(fake.marks, "engine_SIGTERM") == 1
    assert_no_orphans(sup)


def test_without_terminal_messages_only_in_the_log(fake, rotation, capsys):
    """Critère 6 : sortie standard qui n'est pas un terminal : messages au journal seulement, une fois."""
    sup, said = fake(engine="exit0:0.1", rotation=rotation, echo=lambda: False)
    sup.say = launcher.Supervisor.__dataclass_fields__["say"].default
    assert sup.run() == 0
    assert capsys.readouterr().out == ""
    lines = sup.log_path.read_text(encoding="utf-8").splitlines()
    assert sum("Journal complet" in ln for ln in lines) == 1


def test_default_echo_follows_isatty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    if not hasattr(os, "openpty"):
        pytest.skip("openpty requis (Linux)")
    master, slave = os.openpty()
    try:
        with os.fdopen(slave, "w", closefd=False) as tty:
            monkeypatch.setattr(sys, "stdout", tty)
            assert launcher._default_echo() is True
        with (tmp_path / "sortie.txt").open("w") as fh:
            monkeypatch.setattr(sys, "stdout", fh)
            assert launcher._default_echo() is False
    finally:
        os.close(master)
        os.close(slave)


def test_openride_log_replaces_the_rotating_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("openride_core.config.DEFAULT_CONFIG_PATH", tmp_path / "absent.toml")
    godot = tmp_path / "godot"
    godot.write_text("#!/bin/sh\n")
    godot.chmod(0o755)
    env = {"GODOT": str(godot)}
    rotating = launcher.build_supervisor([], env)
    assert isinstance(rotating.rotation, LogRotation) and rotating.rotation.link == launcher.DEFAULT_LOG
    fixed = launcher.build_supervisor([], {**env, "OPENRIDE_LOG": str(tmp_path / "x.log")})
    assert fixed.rotation is None and fixed.log_path == tmp_path / "x.log"


def test_openride_log_file_is_written_without_link(fake, tmp_path):
    sup, _ = fake(core="say:1:run", engine="say:1:exit0:0.2")
    assert sup.run() == 0
    text = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "core ligne 0" in text and "[engine] engine ligne 0" in text
    assert not (tmp_path / "Logs").exists()
