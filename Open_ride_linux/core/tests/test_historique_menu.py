"""Historique dans le menu (lot O28, contrat IPC révision 1.5) : `list_history` -> message `history`,
`history_session` -> bilan d'une séance passée, avec les calculs de `history`, `summary` et `ftp-test`."""

from __future__ import annotations

import asyncio

from openride_core import profiles
from openride_core.tools.history import compute_history
from openride_core.tools.session_summary import compute_summary, load_session

from test_profils_joueurs import home, make, of  # noqa: F401  (fixture `home`)
from test_progression import write_journal

DAY = 86_400.0
FTP_LINE = {"kind": "ftp_test", "ts": 1_760_000_000.0 + 3 * DAY + 1300, "test": "ramp", "ftp_w": 236,
            "method": "ramp_75", "ref_power_w": 315, "held_s": 60.0, "step_w": 20, "warnings": [],
            "previous_ftp_w": 200}


def rides(home):
    jdir = profiles.ProfileContext.for_id("cycliste-a", home / "Profils").journal_dir
    write_journal(jdir / "2025-10-09_10-00_demo.jsonl", km=30, minutes=60, start_ts=1_760_000_000.0)
    write_journal(jdir / "2025-10-12_10-00_demo.jsonl", km=10, minutes=20, start_ts=1_760_000_000.0 + 3 * DAY,
                  extra_lines=[FTP_LINE])
    (jdir / "2025-10-13_10-00_demo.jsonl").write_text("pas du json\n", encoding="utf-8")
    return jdir


def test_history_list_matches_the_command(home, monkeypatch):
    jdir = rides(home)
    s, frames = make(home, monkeypatch)
    asyncio.run(s._send_history("list_history", {}, 3))
    (msg,) = of(frames, "history")
    ref = compute_history(jdir.parent, ftp=200.0)
    assert [i["id"] for i in msg["sessions"]] == ["2025-10-12_10-00_demo.jsonl", "2025-10-09_10-00_demo.jsonl"]
    first = next(x for x in ref["sessions"] if x["filename"] == msg["sessions"][0]["id"])
    assert all(msg["sessions"][0][k] == first[k] for k in ("date", "duration_s", "np_w", "tss", "status"))
    assert msg["unreadable"] == 1 and not msg["truncated"]
    assert [w["count"] for w in msg["weeks"]] == [w["count"] for w in ref["weeks"]]
    (test,) = msg["ftp_tests"]
    assert test["ftp_w"] == 236 and test["previous_ftp_w"] == 200 and test["reliable"]


def test_one_session_summary_and_bad_ids(home, monkeypatch):
    jdir = rides(home)
    s, frames = make(home, monkeypatch)
    errors: list[str] = []
    s.server.send_error = lambda code, text: errors.append(code)
    asyncio.run(s._send_history("history_session", {"id": "2025-10-09_10-00_demo.jsonl"}, 4))
    (msg,) = of(frames, "history_session")
    ref = compute_summary(load_session(jdir / "2025-10-09_10-00_demo.jsonl"), 200.0)
    assert msg["summary"]["tss"] == ref["tss"] and msg["summary"]["np_w"] == ref["np_w"]
    assert msg["summary"]["fit_path"] is None and msg["summary"]["distance_m"] == 30000.0
    for bad in ({"id": "../config.toml"}, {"id": "autre.fit"}, {}, {"id": "2025-10-13_10-00_demo.jsonl"}):
        asyncio.run(s._send_history("history_session", bad, 5))
    assert errors == ["bad_args"] * 4


def test_empty_history(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    asyncio.run(s._send_history("list_history", {}, 6))
    (msg,) = of(frames, "history")
    assert msg["sessions"] == [] and msg["weeks"] == [] and msg["ftp_tests"] == []
