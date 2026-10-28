"""Écart de progression avant/après une PR (lot X39) : `openride-core xp --save` puis `--compare`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openride_core.tools import xp
from test_progression import write_journal


@pytest.fixture
def home(tmp_path, monkeypatch):
    # Rien du vrai ~/OpenRide : configuration, profil et entraînements absents.
    monkeypatch.setenv("HOME", str(tmp_path))
    d = tmp_path / "journal"
    d.mkdir()
    write_journal(d / "a.jsonl")
    write_journal(d / "b.jsonl", source="replay", start_ts=1_770_000_000)
    return tmp_path, d


def _run(d: Path, tmp: Path, **kw) -> int:
    return xp.run(d, kw.pop("as_json", False), tmp / "absent.toml", workouts_dir=tmp / "workouts",
                  profile_path=tmp / "profile.json", **kw)


def test_save_writes_the_json_output_and_compare_finds_no_change(home, capsys):
    tmp, d = home
    snap = tmp / "avant" / "xp.json"
    assert _run(d, tmp, save=snap) == 0
    assert "Instantané écrit" in capsys.readouterr().out
    data = json.loads(snap.read_text(encoding="utf-8"))
    assert [s["journal"] for s in data["sessions"]] == ["a.jsonl", "b.jsonl"]
    assert _run(d, tmp, compare=snap) == 0
    assert "[OK] aucun écart" in capsys.readouterr().out


def test_compare_reports_xp_coins_and_sessions_that_changed(home, capsys):
    tmp, d = home
    snap = tmp / "xp.json"
    assert _run(d, tmp, save=snap) == 0
    write_journal(d / "c.jsonl", km=60.0, climb_m=1200.0, minutes=120.0, start_ts=1_780_000_000)
    old = json.loads(snap.read_text(encoding="utf-8"))
    old["sessions"][0]["xp"] -= 50          # « avant la PR », la séance a valait 50 XP de moins
    snap.write_text(json.dumps(old), encoding="utf-8")
    capsys.readouterr()
    assert _run(d, tmp, compare=snap, as_json=True) == 1
    diff = json.loads(capsys.readouterr().out)
    assert [t["key"] for t in diff["totals"]][:1] == ["total_xp"]
    by_name = {s["journal"]: s for s in diff["sessions"]}
    assert by_name["a.jsonl"]["changes"] == ["xp"]
    assert by_name["a.jsonl"]["after"]["xp"] - by_name["a.jsonl"]["before"]["xp"] == 50
    assert by_name["c.jsonl"]["changes"] == ["ajoutée"] and by_name["c.jsonl"]["before"] is None
    assert "b.jsonl" not in by_name         # séance refusée inchangée : pas d'écart
    assert _run(d, tmp, compare=snap) == 1
    text = capsys.readouterr().out
    assert "[ÉCART] XP :" in text and "2 séance(s) changée(s)" in text and "— → " in text


def test_challenges_and_refusals_are_compared():
    base = {"directory": "j", "total_xp": 100, "level": 1, "coins_earned": 3, "coins_balance": 3,
            "challenges": [{"id": "first_100km", "journal": "a.jsonl"}],
            "sessions": [{"journal": "a.jsonl", "date": "2026-10-01 10:00", "counted": True, "reason": None,
                          "xp": 100, "coins": 3}], "errors": []}
    after = json.loads(json.dumps(base))
    after["challenges"] = [{"id": "first_climb", "journal": "a.jsonl"}]
    after["sessions"][0].update(counted=False, reason="simulated", xp=0, coins=0)
    after["errors"] = [{"journal": "z.jsonl", "error": "JSON invalide"}]
    diff = xp.compare_snapshots(base, after, "avant.json")
    assert diff["challenges_added"] == [{"id": "first_climb", "journal": "a.jsonl"}]
    assert diff["challenges_removed"] == [{"id": "first_100km", "journal": "a.jsonl"}]
    assert diff["sessions"][0]["changes"] == ["counted", "reason", "xp", "coins"]
    text = xp.format_diff(diff)
    assert "défi perdu : first_100km" in text and "refusée (séance simulée)" in text
    assert "journal devenu illisible : z.jsonl" in text
    assert not xp.has_changes(xp.compare_snapshots(base, base))


def test_unreadable_snapshot_gives_code_2(home, capsys):
    tmp, d = home
    bad = tmp / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    assert _run(d, tmp, compare=bad) == 2
    assert _run(d, tmp, compare=tmp / "absent.json") == 2
    assert "illisible" in capsys.readouterr().err
