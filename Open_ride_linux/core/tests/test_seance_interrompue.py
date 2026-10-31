"""Séance interrompue d'un lancement précédent (lot O34, contrat IPC révision 1.5) : proposée dans
`hello_ack.config.interrupted`, enregistrée en FIT ou terminée sans FIT par `recover_session`."""

from __future__ import annotations

import json
import time

from openride_core import resume

from test_contract_ipc import assert_valid
from test_profils_joueurs import home, make, of  # noqa: F401  (fixture `home`)


def crashed_session(home, monkeypatch, seconds: int = 30):
    """Séance de `seconds` s commencée puis abandonnée sans `end_session` (PC éteint) ; renvoie le journal."""
    s, _ = make(home, monkeypatch)
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)
    t0 = time.time()
    for i in range(seconds * 50):
        s._step(0.02, t0 + i * 0.02)
    path = s._rec.path
    s._rec._writer.close()   # le processus meurt : rien d'autre n'est écrit
    s.profile_lock.release()
    return path


def test_crashed_session_is_offered_then_saved(home, monkeypatch):
    journal = crashed_session(home, monkeypatch)
    s, frames = make(home, monkeypatch, port=6130)
    s._publish_interrupted()
    (item,) = s.server.hello_config["interrupted"]
    assert item["id"] == journal.name and item["route_id"] == "demo" and item["duration_s"] >= 25
    s.server.send_hello_ack(s.server.hello_config)
    assert_valid(of(frames, "hello_ack")[-1])
    s._on_command("recover_session", {"id": journal.name, "save": True}, 3)
    (msg,) = of(frames, "interrupted")
    assert msg["saved"] and msg["items"] == [] and msg["request_cmd_id"] == 3
    assert "interrupted" not in s.server.hello_config
    lines = [json.loads(ln) for ln in journal.read_text(encoding="utf-8").splitlines()]
    assert lines[-1]["event"] == "stop" and lines[-1]["reason"] == "interrupted"
    assert resume.interrupted_sessions(journal.parent) == []


def test_not_saved_closes_without_fit_and_bad_ids_are_refused(home, monkeypatch):
    journal = crashed_session(home, monkeypatch)
    with journal.open("a", encoding="utf-8") as fh:
        fh.write('{"kind": "record", "ts": 1')   # dernière ligne tronquée par la coupure
    s, frames = make(home, monkeypatch, port=6140)
    s._publish_interrupted()
    errors: list[str] = []
    s.server.send_error = lambda code, text: errors.append(code)
    s._on_command("recover_session", {"id": "autre.jsonl", "save": True}, 3)
    s._on_command("recover_session", {"id": journal.name}, 4)
    assert errors == ["bad_args", "bad_args"]
    s._on_command("recover_session", {"id": journal.name, "save": False}, 5)
    (msg,) = of(frames, "interrupted")
    assert not msg["saved"] and msg["fit_path"] is None
    assert not any(journal.parent.parent.glob("*.fit"))
    assert json.loads(journal.read_text(encoding="utf-8").splitlines()[-1])["reason"] == "interrupted"


def test_resumed_journal_is_not_offered(home, monkeypatch):
    journal = crashed_session(home, monkeypatch)
    assert resume.interrupted_sessions(journal.parent, skip=journal) == []
    assert len(resume.interrupted_sessions(journal.parent)) == 1
