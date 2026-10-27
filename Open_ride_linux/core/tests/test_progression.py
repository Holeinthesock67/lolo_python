"""Lot V2 : moteur d'expérience (gains, niveaux, défis, recalcul depuis le journal)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from openride_core.journal import JournalWriter, Record, read_journal
from openride_core.progression import (
    ProgressionError, SessionFacts, journal_source, level_for, level_thresholds, load_table,
    recompute, session_facts, session_gains, ineligible_reason,
)


@pytest.fixture
def table():
    return load_table(user_path=None)


def write_journal(path: Path, *, km: float = 30.0, climb_m: float = 300.0, minutes: float = 60.0,
                  source: str | None = "live", erg: bool = False, workout_id: str | None = None,
                  start_ts: float = 1_760_000_000.0, extra_lines: list[dict] | None = None) -> Path:
    """Journal synthétique à 1 Hz : distance et montée régulières, cible ERG si `erg`."""
    n = int(round(minutes * 60))
    with JournalWriter(path, route_id="demo", workout_id=workout_id, source=source) as w:
        w.event("start", start_ts)
        for i in range(1, n + 1):
            frac = i / n
            w.record(Record(ts=start_ts + i, t=float(i), distance=km * 1000 * frac,
                            alt=100.0 + climb_m * frac, power=200.0,
                            mode="ERG" if erg else "SIM", target_w=200.0 if erg else None))
        w.event("stop", start_ts + n + 1)
    if extra_lines:
        with path.open("a", encoding="utf-8") as fh:
            for line in extra_lines:
                fh.write(json.dumps(line) + "\n")
    return path


# --- niveaux ----------------------------------------------------------------------------------

def test_levels_curve(table):
    th = table.thresholds
    assert len(th) == 50
    assert th[0] == 0 and th[1] == 1000 and th[-1] == 100000
    gaps = [b - a for a, b in zip(th, th[1:])]
    assert all(b > a for a, b in zip(gaps, gaps[1:])), "écarts strictement croissants"
    assert 3000 <= gaps[-1] <= 3200


def test_level_for(table):
    assert level_for(0, table).level == 1
    assert level_for(999, table).level == 1
    info = level_for(1000, table)
    assert (info.level, info.xp_level_start, info.xp_next_level) == (2, 1000, table.thresholds[2])
    top = level_for(250_000, table)
    assert top.level == 50 and top.xp_next_level is None


def test_levels_refuse_impossible_curve():
    with pytest.raises(ProgressionError, match="xp_level_max"):
        level_thresholds(50, 1000, 40000)


# --- gains d'une séance -----------------------------------------------------------------------

def test_sim_session_gains(tmp_path, table):
    facts = session_facts(write_journal(tmp_path / "a.jsonl"))
    assert facts.source == "live" and facts.route_id == "demo"
    assert facts.distance_m == pytest.approx(30000)
    assert facts.climb_m == pytest.approx(300, abs=1.5)
    gains = session_gains(facts, table)
    assert gains.by_source["distance"] == 600
    assert gains.by_source["climb"] == pytest.approx(600, abs=3)
    assert gains.total == pytest.approx(1200, abs=3)
    assert ineligible_reason(facts, table) is None


def test_short_session_refused(tmp_path, table):
    facts = session_facts(write_journal(tmp_path / "a.jsonl", minutes=4 + 59 / 60))
    assert ineligible_reason(facts, table) == "too_short"
    facts = session_facts(write_journal(tmp_path / "b.jsonl", minutes=5))
    assert ineligible_reason(facts, table) is None


def test_erg_completed_and_interrupted(tmp_path, table):
    done = session_facts(write_journal(tmp_path / "a.jsonl", erg=True, workout_id="w"),
                         workout_duration_s=3600)
    assert done.erg_completed is True
    g = session_gains(done, table).by_source
    assert (g["erg"], g["erg_bonus"], g["distance"], g["climb"]) == (600, 120, 0, 0)

    cut = session_facts(write_journal(tmp_path / "b.jsonl", erg=True, workout_id="w", minutes=40),
                        workout_duration_s=3600)
    assert cut.erg_completed is False
    assert session_gains(cut, table).total == 400

    unknown = session_facts(write_journal(tmp_path / "c.jsonl", erg=True, workout_id="w"))
    assert unknown.erg_completed is None
    assert session_gains(unknown, table).total == 600


def test_erg_distance_option(tmp_path):
    user = tmp_path / "progression.toml"
    user.write_text("[rules]\nerg_replaces_distance = false\n", encoding="utf-8")
    table = load_table(user_path=user)
    facts = session_facts(write_journal(tmp_path / "a.jsonl", erg=True), workout_duration_s=3600)
    assert session_gains(facts, table).by_source["distance"] == 600


def test_sources(tmp_path, table):
    replay = session_facts(write_journal(tmp_path / "a.jsonl", source="replay"))
    sim = session_facts(write_journal(tmp_path / "b.jsonl", source="simulated"))
    old = session_facts(write_journal(tmp_path / "c.jsonl", source=None))
    assert ineligible_reason(replay, table) == "replay"
    assert ineligible_reason(sim, table) == "simulated"
    assert old.source == "live" and ineligible_reason(old, table) is None


def test_journal_source_mapping():
    assert journal_source("ftms") == "live"
    assert journal_source("mock") == "simulated"
    assert journal_source("sim") == "simulated"
    assert journal_source("mock", "seance.jsonl") == "replay"


def test_header_source_written(tmp_path):
    path = write_journal(tmp_path / "a.jsonl", minutes=1, source="simulated")
    head = next(iter(read_journal(path)))
    assert head["kind"] == "header" and head["source"] == "simulated"
    path = write_journal(tmp_path / "b.jsonl", minutes=1, source=None)
    assert "source" not in next(iter(read_journal(path)))


def test_climb_deadband_ignores_noise(tmp_path, table):
    path = tmp_path / "noise.jsonl"
    with JournalWriter(path, source="live") as w:
        w.event("start", 0.0)
        for i in range(600):
            w.record(Record(ts=float(i), t=float(i), distance=float(i * 8),
                            alt=100.0 + (0.4 if i % 2 else 0.0)))
    assert session_facts(path).climb_m == 0.0


def test_events_from_series_t_and_r(table):
    facts = SessionFacts(journal="x", duration_s=3600, distance_m=0, events=[
        {"kind": "segment", "pr": True, "category": "HC"},
        {"kind": "segment", "pr": False},
        {"kind": "jersey", "jersey": "kom"},
        {"kind": "rogue_run", "minutes": 45, "bosses": ["chimere_centrale", "puncheur"]},
    ])
    g = session_gains(facts, table).by_source
    assert (g["segment"], g["segment_pr"], g["jersey"]) == (100, 100, 200)
    assert (g["rogue"], g["rogue_boss"]) == (450, 300 + 100)


# --- recalcul complet --------------------------------------------------------------------------

def test_recompute_history(tmp_path, table):
    d = tmp_path / "journal"
    d.mkdir()
    write_journal(d / "2026-10-01_10-00-00.jsonl", km=30, start_ts=1_000_000)
    write_journal(d / "2026-10-02_10-00-00.jsonl", km=52, climb_m=0, start_ts=2_000_000)
    write_journal(d / "2026-10-03_10-00-00.jsonl", km=10, minutes=3, start_ts=3_000_000)
    trunc = d / "2026-10-04_10-00-00.jsonl"
    write_journal(trunc, km=20, climb_m=0, start_ts=4_000_000)
    trunc.write_text(trunc.read_text(encoding="utf-8") + '{"kind": "record", "t": 99', encoding="utf-8")

    p = recompute(d, table)
    assert [r.reason for r in p.sessions] == [None, None, "too_short", None]
    assert p.total_xp == sum(r.gains.total for r in p.counted)
    assert p.total_xp == pytest.approx(600 + 600 + 1040 + 400, abs=3)
    assert p.level.level == 3 and p.level.xp_level_start == 2040
    assert p.stats["sessions"] == 3
    km50 = next(c for c in p.challenges if c.id == "session_50km")
    assert km50.journal == "2026-10-02_10-00-00.jsonl" and km50.reward == "socks_longue_distance"


def test_recompute_dedupes_reopened_journal(tmp_path, table):
    d = tmp_path / "journal"
    d.mkdir()
    write_journal(d / "2026-10-01_10-00-00.jsonl", km=10, minutes=20, start_ts=1_000_000)
    write_journal(d / "2026-10-01_10-35-00_reprise-1.jsonl", km=30, minutes=60, start_ts=1_000_000)
    p = recompute(d, table)
    assert len(p.sessions) == 1 and p.sessions[0].facts.journal.endswith("_reprise-1.jsonl")


def test_recompute_erg_challenge_with_lookup(tmp_path, table):
    d = tmp_path / "journal"
    d.mkdir()
    for i in range(10):
        write_journal(d / f"s{i:02d}.jsonl", erg=True, workout_id="sweet", minutes=6,
                      start_ts=1_000_000 + i * 10_000)
    p = recompute(d, table, {"sweet": 360.0})
    assert p.stats["erg_completed"] == 10
    assert any(c.id == "erg_10" and c.journal == "s09.jsonl" for c in p.challenges)
    assert recompute(d, table).stats["erg_completed"] == 0


def test_recompute_empty_dir(tmp_path, table):
    p = recompute(tmp_path / "absent", table)
    assert p.total_xp == 0 and p.level.level == 1 and p.sessions == []


# --- fichier de données --------------------------------------------------------------------------

def test_user_table_overrides_keys(tmp_path):
    user = tmp_path / "progression.toml"
    user.write_text("[xp]\nper_km = 30\n", encoding="utf-8")
    table = load_table(user_path=user)
    assert table.xp("per_km") == 30 and table.xp("per_climb_m") == 2
    assert len(table.challenges) == 7


@pytest.mark.parametrize("text, key", [
    ("[xp]\nper_kmm = 30\n", "per_kmm"),
    ("[xp]\nper_km = \"vingt\"\n", "per_km"),
    ("[rules]\nmin_session_s = -1\n", "min_session_s"),
    ("[levels]\ncount = 2.5\n", "count"),
    ("[[challenges]]\nid = \"a\"\nname = \"A\"\nstat = \"inconnue\"\nthreshold = 1\n", "stat"),
    ("[[challenges]]\nid = \"a\"\nname = \"A\"\nstat = \"sessions\"\n", "threshold"),
])
def test_invalid_user_table_names_key(tmp_path, text, key):
    user = tmp_path / "progression.toml"
    user.write_text(text, encoding="utf-8")
    with pytest.raises(ProgressionError, match=key):
        load_table(user_path=user)


def test_invalid_toml(tmp_path):
    user = tmp_path / "progression.toml"
    user.write_text("[xp\n", encoding="utf-8")
    with pytest.raises(ProgressionError, match="TOML invalide"):
        load_table(user_path=user)


# --- commande -----------------------------------------------------------------------------------

def test_cli_json(tmp_path, monkeypatch):
    d = tmp_path / "journal"
    d.mkdir()
    write_journal(d / "a.jsonl")
    write_journal(d / "b.jsonl", source="replay", start_ts=1_770_000_000)
    monkeypatch.setenv("HOME", str(tmp_path))
    out = subprocess.run([sys.executable, "-m", "openride_core", "xp", "--dir", str(d), "--json"],
                         capture_output=True, text=True, check=True, env={"HOME": str(tmp_path),
                         "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
    data = json.loads(out.stdout)
    assert data["level"] == 2 and data["total_xp"] == pytest.approx(1200, abs=3)
    assert [s["reason"] for s in data["sessions"]] == [None, "replay"]
    text = subprocess.run([sys.executable, "-m", "openride_core", "xp", "--dir", str(d)],
                          capture_output=True, text=True, check=True, env={"HOME": str(tmp_path),
                          "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}).stdout
    assert "Niveau 2" in text and "refusée : rejeu" in text
