"""Repère « décrochage » : Z long en roulant écrit un événement au journal (§7.1, lot X47)."""

from __future__ import annotations

import asyncio

import pytest

from openride_core.journal import EVENTS, TIMER_EVENTS, JournalWriter, Record, read_journal
from openride_core.zwift_click import InputEvent

from test_journal_devices import _records, _session, run


def _marks(s):
    return [ln for ln in s._rec.lines if ln["kind"] == "event" and ln["event"] == "decrochage"]


@pytest.mark.parametrize("workout, port", [(None, 6560), ("deux_blocs", 6570)])
def test_z_long_marks_a_dropout_without_changing_the_ride(tmp_path, monkeypatch, workout, port):
    async def scenario():
        s, _ = _session(tmp_path, monkeypatch, port)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        if workout:
            s._on_command("select_workout", {"workout_id": workout}, 2)
        s._on_command("start", {}, 3)
        run(s, 3.0)
        before = (s.state.gear, s.erg.bias_pct if s.erg else None, getattr(s.erg, "index", None), s.state.session_state)
        s._handle_input(InputEvent.Z_LONG)
        assert s.dropout_marks == 1 and len(_marks(s)) == 1
        assert before == (s.state.gear, s.erg.bias_pct if s.erg else None, getattr(s.erg, "index", None),
                          s.state.session_state)
        run(s, 2.0)
        assert _records(s)[-1]["t"] > 3.0                     # le chronomètre continue
        assert all(ln["event"] != "decrochage" for ln in s._rec.events)   # hors chronomètre et hors FIT
        lines = list(read_journal(s._rec.path))
        assert [ln["event"] for ln in lines if ln.get("kind") == "event"].count("decrochage") == 1
    asyncio.run(scenario())


def test_z_long_does_nothing_while_paused(tmp_path, monkeypatch):
    async def scenario():
        s, _ = _session(tmp_path, monkeypatch, 6580)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        run(s, 1.0)
        s._handle_input(InputEvent.Y_SHORT)
        s._handle_input(InputEvent.Z_LONG)
        assert s.dropout_marks == 0 and not _marks(s)
    asyncio.run(scenario())


def test_journal_accepts_the_mark_outside_the_timer(tmp_path):
    assert "decrochage" in EVENTS and "decrochage" not in TIMER_EVENTS
    w = JournalWriter(tmp_path / "j.jsonl", "demo")
    w.event("decrochage", 12.5)
    w.close()
    assert {"kind": "event", "event": "decrochage", "ts": 12.5} in list(read_journal(tmp_path / "j.jsonl"))


def test_decrochages_reads_the_mark_next_to_the_drop(tmp_path):
    """Le repère posé au Z long est rattaché par l'outil `decrochages` (X44) à la chute qu'il suit de près."""
    from openride_core.tools import decrochages

    path = tmp_path / "j.jsonl"
    w = JournalWriter(path, "demo")
    for i in range(60):
        power = 450.0 if i < 30 else 5.0
        w.record(Record(ts=1000.0 + i, t=float(i), speed=10.0, power=power, cadence=90.0))
    w.event("decrochage", 1032.0)
    w.close()
    src = decrochages.read_journal(path)
    assert src.marks == [32.0]
    drops, _ = decrochages.analyse(src)
    assert len(drops) == 1 and drops[0].marked and drops[0].kind == "trainer"
