"""Filet de la boucle du core (audit du 22 novembre, R3 et L10) : un mode qui lève une exception termine la
séance avec son bilan et son FIT, envoie `mode_failed` avec un message en mots, et le core continue.
Une erreur du trainer n'est pas attrapée : le lanceur relance le core, comme avant."""

import json
import time
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export, profile
from openride_core.game_modes import registry as game_modes
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.journal import TIMER_EVENTS, read_journal
from openride_core.mock_driver import MockDriver
from openride_core.session import MODE_FAIL_LIMIT_S, MODE_FAILED_SAVED, MODE_FAILED_TEXT, CoreSession

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
DT = 0.02
T0_WALL = 1_790_000_000.0


class Boom(RuntimeError):
    pass


def _boom(*_a, **_k):
    raise Boom("panne du mode")


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    wall = [T0_WALL]
    monkeypatch.setattr(time, "time", lambda: wall[0])

    def make(port: int) -> tuple[CoreSession, list, list]:
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        cfg.survivor.opponents, cfg.survivor.spacing_km = 2, 2
        s = CoreSession(cfg, driver=MockDriver(base_power_w=220.0, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                        routes_root=tmp_path / "routes", records_path=tmp_path / "records.json",
                        powerups_path=tmp_path / "powerups.toml", wtf_path=tmp_path / "wtf.toml")
        sent: list[dict] = []
        errors: list[tuple[str, str]] = []
        s.server.send_raw = lambda m, max_size=None: sent.append(m)
        s.server.send_error = lambda code, msg: errors.append((code, msg))
        s.server.send_input_event = lambda ev: None
        s._on_command("select_route", {"route_id": "demo"}, 1)
        return s, sent, errors

    def run(s: CoreSession, seconds: float) -> None:
        for _ in range(int(round(seconds / DT))):
            wall[0] += DT
            s._safe_step(DT, wall[0])
            s._fill_mode_frames(wall[0])

    return make, run, tmp_path, wall


def _journal_lines(tmp_path: Path) -> list[dict]:
    path = next((tmp_path / "journal").glob("*.jsonl"))
    return [json.loads(x) for x in path.read_text("utf-8").splitlines() if x.strip()]


def test_mode_error_in_step_ends_session_with_summary(env):
    make, run, tmp_path, _ = env
    s, _sent, errors = make(7310)
    s._on_command("start", {"mode": "survivor"}, 2)
    assert s.state.session_state == "RUNNING" and s.survivor is not None
    run(s, 30)
    s.survivor.step = _boom   # le mode lève une exception au pas suivant
    run(s, 1)
    assert s.state.session_state == "FINISHED"
    assert s.survivor is None and s._rec is None
    summary = s.state.summary
    assert summary["duration_s"] >= 29 and summary["fit_path"]            # séance enregistrée, FIT écrit
    assert summary["mode_error"] == {"mode": "survivor", "error": "Boom"}
    assert "survivor" in summary                                         # bilan du mode gardé
    assert errors == [("mode_failed", MODE_FAILED_SAVED)]                # un seul message, en mots
    jsonschema.Draft202012Validator(
        json.loads((IPC_DIR / "state.schema.json").read_text("utf-8"))).validate(s.state.to_dict())
    lines = _journal_lines(tmp_path)
    err = [ln for ln in lines if ln.get("kind") == "mode_error"]
    assert len(err) == 1 and err[0]["mode"] == "survivor" and err[0]["where"] == "pas"
    assert err[0]["error"] == "Boom" and err[0]["message"] == "panne du mode"
    timer = [ln for ln in read_journal(next((tmp_path / "journal").glob("*.jsonl")))
             if ln.get("kind") == "event" and ln.get("event") in TIMER_EVENTS]
    assert timer[-1]["event"] == "stop"   # journal terminé : pas de reprise après plantage (resume.py)

    # Le core reste vivant : la boucle continue et une nouvelle séance démarre.
    run(s, 1)
    s._on_command("select_route", {"route_id": "demo"}, 3)
    s._on_command("start", {}, 4)
    run(s, 2)
    assert s.state.session_state == "RUNNING" and errors == [("mode_failed", MODE_FAILED_SAVED)]


def test_mode_error_in_frame_ends_session(env, monkeypatch):
    make, run, _tmp, _ = env
    s, _sent, errors = make(7320)
    s._on_command("start", {"mode": "survivor"}, 2)
    run(s, 5)
    monkeypatch.setattr(game_modes.BY_ID["survivor"], "fill_frame", _boom)   # adaptateur du mode (lot IM1)
    run(s, 1)
    assert s.state.session_state == "FINISHED" and s.state.summary["mode_error"]["mode"] == "survivor"
    assert errors == [("mode_failed", MODE_FAILED_SAVED)]


def test_trainer_error_is_not_caught(env):
    make, run, _tmp, _ = env
    s, _sent, errors = make(7330)
    s._on_command("start", {}, 2)
    run(s, 1)
    s.driver.poll = _boom
    with pytest.raises(Boom):
        run(s, 1)
    assert not errors


def test_finish_failure_falls_back_to_error_state(env):
    make, run, _tmp, _ = env
    s, _sent, errors = make(7340)
    s._on_command("start", {"mode": "survivor"}, 2)
    run(s, 5)
    s.survivor.step = _boom
    s._finish = _boom   # la fin de séance échoue à son tour
    run(s, 1)
    assert s.state.session_state == "ERROR"
    assert s.survivor is None and s._rec is None and s.erg is None
    assert errors == [("mode_failed", MODE_FAILED_TEXT)]
    run(s, 1)   # le core tourne toujours


def test_repeated_error_outside_session_raises_after_limit(env):
    make, run, _tmp, _ = env
    s, _sent, errors = make(7350)
    s._open_world_tick = _boom   # erreur à chaque pas, hors séance
    run(s, MODE_FAIL_LIMIT_S - 1)
    assert errors == [("mode_failed", MODE_FAILED_TEXT)]   # une suite d'erreurs : un seul message
    with pytest.raises(Boom):
        run(s, 2)


def test_journal_unwritable_at_start_waits_paused(env):
    """Revue de code du 22 novembre : sans journal au départ, la séance attend en pause au lieu de rouler."""
    make, run, tmp_path, _ = env
    s, _sent, errors = make(7360)
    s.journal_dir = tmp_path / "pas_un_dossier"
    s.journal_dir.write_text("fichier à la place du dossier", encoding="utf-8")
    s._on_command("start", {}, 2)
    assert (s.state.session_state, s.state.pause_reason) == ("PAUSED", "recording_failed")
    assert [c for c, _ in errors] == ["recording_failed"]
    s._on_command("resume", {}, 3)   # toujours impossible : refus en mots, la séance reste en pause
    assert s.state.session_state == "PAUSED" and errors[-1][0] == "recording_failed"
    assert "toujours impossible" in errors[-1][1]
    s.journal_dir.unlink()
    s._on_command("resume", {}, 4)   # dossier de nouveau possible : journal rouvert, la séance roule
    assert s.state.session_state == "RUNNING" and not s._rec.failed
    run(s, 2)
    s._on_command("end_session", {"save": True}, 5)
    assert s.state.session_state == "FINISHED" and s.state.summary["fit_path"]
