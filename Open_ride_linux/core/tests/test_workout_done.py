"""Invite de fin de séance (1er novembre) : champ `workout_done` de `state` après le dernier bloc.

Constat du vélo du 1er novembre : à la fin de la séance d'un plan, le core repasse en SIM et la séance
continue ; rien ne disait à l'écran qu'il fallait Y puis « Terminer et enregistrer ». Le core publie
désormais `workout_done` tant que la séance continue après l'entraînement (contrat IPC §3)."""

import asyncio
import json
from pathlib import Path

import jsonschema
import pytest
from test_workout import make_session, run

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"

COURT = """<workout_file><name>Court</name><sportType>bike</sportType><workout>
<SteadyState Duration="2" Power="0.6"/><SteadyState Duration="2" Power="0.8"/>
</workout></workout_file>"""


@pytest.fixture
def short_dir(tmp_path):
    d = tmp_path / "workouts"
    d.mkdir()
    (d / "court.zwo").write_text(COURT, encoding="utf-8")
    return d


def started(tmp_path, monkeypatch, short_dir, port):
    s, driver, errors = make_session(tmp_path, monkeypatch, short_dir, port=port)
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("select_workout", {"workout_id": "court"}, 2)
    s._on_command("start", {}, 3)
    return s, driver, errors


def test_workout_done_after_last_block_until_session_ends(tmp_path, monkeypatch, short_dir):
    validator = jsonschema.Draft202012Validator(
        json.loads((IPC_DIR / "state.schema.json").read_text(encoding="utf-8")))

    async def scenario():
        s, _driver, errors = started(tmp_path, monkeypatch, short_dir, 6010)
        run(s, 1.0)
        assert s.state.mode == "ERG" and s.state.workout_done is None
        assert "workout_done" not in s.state.to_dict()
        run(s, 3.5)
        assert s.state.session_state == "RUNNING" and s.state.mode == "SIM" and s.state.erg is None
        frame = s.state.to_dict()
        assert frame["workout_done"] == {"workout_name": "Court"}
        validator.validate(frame)
        s._on_command("pause", {}, 4)
        assert s.state.session_state == "PAUSED" and s.state.workout_done == {"workout_name": "Court"}
        s._on_command("resume", {}, 5)
        run(s, 0.5)
        assert s.state.workout_done is not None   # l'invite reste tant que la séance continue
        s._on_command("end_session", {"save": False}, 6)
        run(s, 0.5)
        assert s.state.session_state == "FINISHED" and s.state.workout_done is None
        assert "workout_done" not in s.state.to_dict() and not errors
    asyncio.run(scenario())


def test_new_session_starts_without_the_invite(tmp_path, monkeypatch, short_dir):
    async def scenario():
        s, _driver, _errors = started(tmp_path, monkeypatch, short_dir, 6012)
        run(s, 4.5)
        assert s.state.workout_done is not None
        s._on_command("end_session", {"save": False}, 4)
        run(s, 0.5)
        s._on_command("select_workout", {"workout_id": "court"}, 5)
        s._on_command("select_route", {"route_id": "demo"}, 6)
        s._on_command("start", {}, 7)
        run(s, 0.5)
        assert s.state.mode == "ERG" and s.state.workout_done is None
    asyncio.run(scenario())


def test_ride_mode_chosen_at_pause_clears_the_invite(tmp_path, monkeypatch, short_dir):
    """Le cycliste choisit de continuer (ERG libre, ERG cadence ou SIM depuis la pause) : plus d'invite."""
    async def scenario():
        s, _driver, errors = started(tmp_path, monkeypatch, short_dir, 6014)
        run(s, 4.5)
        s._on_command("pause", {}, 4)
        s._on_command("set_ride_mode", {"mode": "erg", "target_w": 150}, 5)
        assert not errors and s.state.mode == "ERG" and s.state.erg["kind"] == "free"
        assert s.state.workout_done is None and "workout_done" not in s.state.to_dict()
    asyncio.run(scenario())
