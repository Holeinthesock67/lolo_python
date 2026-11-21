"""Lot PP3 (révision 1.29) : `list_power_curve` -> message `power_curve`, courbe et FTP estimée du profil en cours,
séances fabriquées d'un cycliste fictif (FTP 250 W, aucune donnée réelle)."""

from __future__ import annotations

import asyncio
import json
import time

from openride_core import ipc_lists, profiles
from openride_core.tools import courbe_fictive, power_curve

from test_profils_joueurs import home, make, of  # noqa: F401  (fixture `home`)

NOW = time.time()


def journals(home):
    jdir = profiles.ProfileContext.for_id("cycliste-a", home / "Profils").journal_dir
    courbe_fictive.write_sessions(jdir, NOW)
    return jdir


def test_message_from_the_current_profile(home, monkeypatch):
    jdir = journals(home)
    s, frames = make(home, monkeypatch)
    asyncio.run(s._send_power_curve(7))
    (msg,) = of(frames, "power_curve")                       # conforme à power_curve.schema.json
    assert msg["request_cmd_id"] == 7 and msg["profile_id"] == "cycliste-a" and msg["ftp_set_w"] == 200
    assert [p["s"] for p in msg["points"]] == list(power_curve.DURATIONS_S)
    assert msg["sessions"] == {"m6": 9, "w6": 4}
    p5s = msg["points"][0]
    assert p5s["m6"]["w"] == 880 and p5s["m6"]["e"] == "libre" and p5s["m6"]["r"] == "gp-ligne"
    assert p5s["w6"]["w"] == 820                              # forme du moment plus basse
    erg = msg["points"][-1]["m6"]
    assert erg["e"] == "ERG" and erg["k"] == "seuil_3x15"     # 60 min : la séance de seuil en ERG, avec son entraînement
    assert next(p for p in msg["points"] if p["s"] == 1200)["m6"]["e"] == "libre"
    assert msg["estimate"]["source"] == "cp" and msg["confidence"] == "Fiable"
    assert abs(msg["estimate"]["ftp_w"] - 250) <= 6 and msg["proposal_w"] == msg["estimate"]["ftp_w"]
    assert msg["review"] is True                              # FTP réglée 200 W : plus de 5 % d'écart
    assert len(msg["monthly"]) == 6 and len(msg["warnings"]) == 2
    assert len(json.dumps(msg, ensure_ascii=False).encode("utf-8")) < 4096
    assert jdir.parent.parent.joinpath(".cache", "mmp.json").is_file()   # cache du profil


def test_empty_profile_and_busy_while_riding(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    asyncio.run(s._send_power_curve(8))
    (msg,) = of(frames, "power_curve")
    assert all(p["m6"] is None and p["w6"] is None for p in msg["points"])
    assert msg["estimate"] is None and msg["confidence"] == "Pas assez de données" and msg["proposal_w"] is None
    errors: list[str] = []
    s.server.send_error = lambda code, text: errors.append(code)
    s.state.session_state = "RUNNING"
    asyncio.run(s._send_power_curve(9))
    assert errors == ["busy"] and len(of(frames, "power_curve")) == 1


def test_long_names_stay_under_one_datagram(tmp_path):
    entries = []
    for i, d in enumerate(power_curve.DURATIONS_S):
        e = {"fmt": "jsonl", "start_ts": NOW - 86400 * (i + 1), "source": "live", "route_id": "r" * 200,
             "workout_id": "w" * 200, "all": {str(d): 300.0}, "free": {}}
        entries.append((tmp_path / f"{i}.jsonl", e))
    monkey = power_curve.session_entries
    try:
        power_curve.session_entries = lambda *a, **k: entries
        msg = ipc_lists.build_power_curve_message(1, 250.0, tmp_path, tmp_path / "c.json", ("live",), "x", NOW)
    finally:
        power_curve.session_entries = monkey
    assert len(json.dumps(msg, ensure_ascii=False).encode("utf-8")) < 4096
    assert msg["points"][0]["m6"]["r"] == "r" * 24 and msg["points"][0]["m6"]["k"] is None


def test_command_is_dispatched(home, monkeypatch):
    journals(home)
    s, frames = make(home, monkeypatch)
    called = []
    monkeypatch.setattr(s, "_spawn", lambda coro: (called.append(True), asyncio.run(coro)))
    s._on_command("list_power_curve", {}, 11)
    assert called and of(frames, "power_curve")[0]["request_cmd_id"] == 11
