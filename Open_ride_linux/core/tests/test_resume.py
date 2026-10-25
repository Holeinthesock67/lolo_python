"""Lot N8 : reprise d'une séance après un plantage du core (journal relu, même fichier, FIT unique)."""

import time
from pathlib import Path

import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.resume import ResumeError, find_unfinished_journal, is_unfinished, load_resume_state
from openride_core.session import CoreSession
from openride_core.zwift_click import InputEvent

DT = 0.02
T0_WALL = 1_790_000_000.0

ERG_ZWO = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <name>Reprise ERG</name>
    <workout>
        <SteadyState Duration="300" Power="0.60"/>
        <SteadyState Duration="600" Power="0.80"/>
        <SteadyState Duration="300" Power="0.50"/>
    </workout>
</workout_file>
"""


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Horloge murale simulée, dossiers isolés ; `make(port)` crée une session (un « processus » du core)."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    wall = [T0_WALL]
    monkeypatch.setattr(time, "time", lambda: wall[0])
    workouts = tmp_path / "Workouts"
    workouts.mkdir()
    (workouts / "reprise.zwo").write_text(ERG_ZWO, encoding="utf-8")

    def make(port: int) -> CoreSession:
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        s = CoreSession(cfg, driver=MockDriver(base_power_w=200.0), inputs=[NullProvider()],
                        journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes",
                        workouts_dir=workouts)
        s.server.send_raw = lambda m: None
        return s

    def run_for(s: CoreSession, seconds: float) -> None:
        for _ in range(int(round(seconds / DT))):
            wall[0] += DT
            s._step(DT, wall[0])

    return make, run_for, wall


def crash(s: CoreSession) -> Path:
    """Mort brutale du core : ni fin de séance ni FIT, le journal reste tel quel sur disque."""
    path = s._rec.path
    s._rec._writer._fh.close()
    return path


def last_record(path: Path) -> dict:
    return [ln for ln in read_journal(path) if ln.get("kind") == "record"][-1]


def test_sim_session_resumes_paused_and_fit_has_one_session(env):
    """Critère 2 : plantage à 6 min, reprise en pause, 4 min de plus : FIT de 10 min, une seule séance."""
    make, run_for, wall = env
    a = make(6400)
    a._on_command("select_route", {"route_id": "demo"}, 1)
    a._on_command("start", {}, 2)
    a._handle_input(InputEvent.PLUS_SHORT)   # braquet 13 : doit être repris
    run_for(a, 360.0)
    path = crash(a)
    assert is_unfinished(path)
    last = last_record(path)

    wall[0] += 20.0   # relance par le lanceur
    b = make(6402)
    b.resume_session(path)
    assert (b.state.session_state, b.state.pause_reason) == ("PAUSED", "core_restarted")
    assert abs(b.state.t - last["t"]) < 1.0 and abs(b.state.t - 360.0) < 1.0
    assert abs(b.state.s - last["distance"]) < 10.0
    assert b.state.v == 0.0 and b.state.gear == last["gear"] == 13
    assert b._rec.path == path   # même fichier

    run_for(b, 5.0)   # en pause : rien ne bouge
    assert abs(b.state.t - last["t"]) < 1.0
    b._on_command("resume", {}, 3)
    run_for(b, 240.0)
    b._on_command("end_session", {"save": True}, 4)

    summary = b.state.summary
    assert summary["duration_s"] == pytest.approx(600.0, abs=2.0)
    fit = Path(summary["fit_path"])
    msgs = [r.message for r in fit_export.iter_records(fit)]
    assert sum(type(m).__name__ == "SessionMessage" for m in msgs) == 1
    lines = list(read_journal(path))
    assert sum(ln.get("kind") == "header" for ln in lines) == 1
    events = [ln["event"] for ln in lines if ln.get("kind") == "event"]
    assert events == ["start", "pause", "resume_after_crash", "resume", "stop"]
    ts = [ln["t"] for ln in lines if ln.get("kind") == "record"]
    assert ts == sorted(ts) and len(ts) == len(set(ts)), "relevés en double après la reprise"


def test_erg_resumes_same_block_with_bias(env):
    """Critère 3 : même bloc, temps restant à 1 s près, biais du Click conservé."""
    make, run_for, wall = env
    a = make(6404)
    a._on_command("select_route", {"route_id": "demo"}, 1)
    a._on_command("select_workout", {"workout_id": "reprise"}, 2)
    a._on_command("start", {}, 3)
    run_for(a, 100.0)
    a._handle_input(InputEvent.PLUS_SHORT)   # biais +2 %
    run_for(a, 260.0)                        # 6 min : bloc 2, 60 s écoulées
    before = dict(a.state.erg)
    bias = a.erg.bias_pct
    path = crash(a)

    wall[0] += 15.0
    b = make(6406)
    b.resume_session(path)
    assert b.state.mode == "ERG"
    assert b.state.erg["block_index"] == before["block_index"] == 2
    assert b.state.erg["block_remaining_s"] == pytest.approx(before["block_remaining_s"], abs=1.0)
    assert b.erg.bias_pct == bias
    b._on_command("resume", {}, 4)
    run_for(b, 1.0)
    assert b.state.erg["target_w"] == before["target_w"]


def test_truncated_last_line_resumes_on_last_complete_line(env):
    """Critère 5 : journal coupé au milieu d'une ligne, reprise sur la dernière ligne complète."""
    make, run_for, wall = env
    a = make(6408)
    a._on_command("select_route", {"route_id": "demo"}, 1)
    a._on_command("start", {}, 2)
    run_for(a, 30.0)
    path = crash(a)
    last = last_record(path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"kind":"record","ts":17900000')   # plantage pendant l'écriture
    rs = load_resume_state(path)
    assert rs.t == last["t"] and rs.s == last["distance"]
    b = make(6410)
    b.resume_session(path)
    assert b.state.session_state == "PAUSED"


def test_finished_or_foreign_journal_is_not_resumed(env, tmp_path: Path):
    make, run_for, wall = env
    a = make(6412)
    a._on_command("select_route", {"route_id": "demo"}, 1)
    a._on_command("start", {}, 2)
    run_for(a, 5.0)
    path = a._rec.path
    a._on_command("end_session", {"save": True}, 3)
    assert not is_unfinished(path)
    with pytest.raises(ResumeError, match="déjà terminée"):
        load_resume_state(path)
    assert find_unfinished_journal(path.parent) is None
    assert find_unfinished_journal(tmp_path / "absent") is None


def test_cli_run_accepts_resume():
    from openride_core.__main__ import build_parser

    args = build_parser().parse_args(["run", "--autostart", "--resume", "/tmp/x.jsonl"])
    assert args.resume == Path("/tmp/x.jsonl") and args.autostart


def test_click_y_pauses_and_resumes_without_relay(env):
    """Lot N6 : bouton Y du Click, pause puis reprise ; rien n'est relayé à l'engine."""
    make, run_for, wall = env
    s = make(6414)
    sent: list[str] = []
    s.server.send_input_event = sent.append
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)
    run_for(s, 2.0)
    s._handle_input(InputEvent.PAUSE)
    assert (s.state.session_state, s.state.pause_reason) == ("PAUSED", "user")
    s._handle_input(InputEvent.PAUSE)
    assert s.state.session_state == "RUNNING"
    assert sent == []
