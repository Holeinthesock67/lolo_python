"""Tests du journal et de l'export FIT (relecture par bibliothèque, SRS §12)."""

import json
from pathlib import Path

import pytest
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage

from openride_core.fit_export import iter_records, journal_to_fit
from openride_core.journal import JournalWriter, Record, read_journal
from openride_core.tools.fake_world import build_manifest, build_route

T0 = 1_790_000_000.0  # 2026


def make_journal(path: Path, n: int = 120, pause_at: int = 60, pause_len: float = 20.0) -> Path:
    with JournalWriter(path, route_id="test") as j:
        j.event("start", T0)
        wall = T0
        for i in range(n):
            if i == pause_at:
                j.event("pause", wall)
                wall += pause_len
                j.event("resume", wall)
            wall += 1.0
            j.record(Record(ts=wall, t=float(i + 1), lat=45.0 + i * 1e-5, lon=6.0, alt=1000.0 + i,
                            distance=8.0 * (i + 1), speed=8.0, power=200.0, cadence=85, hr=140,
                            grade=3.0, gear=12))
        j.event("stop", wall)
    return path


def test_truncated_last_line_is_ignored(tmp_path: Path):
    p = make_journal(tmp_path / "j.jsonl", n=5)
    with p.open("a", encoding="utf-8") as fh:
        fh.write('{"kind":"record","ts":12')   # plantage en cours d'écriture
    lines = list(read_journal(p))
    assert sum(1 for l in lines if l["kind"] == "record") == 5


def test_fit_roundtrip(tmp_path: Path):
    j = make_journal(tmp_path / "j.jsonl")
    fit_path, s = journal_to_fit(j, tmp_path / "out.fit")
    assert fit_path.exists() and fit_path.stat().st_size > 1000
    assert s.timer_s == pytest.approx(120.0)
    assert s.elapsed_s == pytest.approx(140.0)

    msgs = [r.message for r in iter_records(fit_path)]
    records = [m for m in msgs if isinstance(m, RecordMessage)]
    sessions = [m for m in msgs if isinstance(m, SessionMessage)]
    events = [m for m in msgs if isinstance(m, EventMessage)]
    assert len(records) == 120
    assert len(sessions) == 1 and len(events) == 4
    assert records[0].position_lat == pytest.approx(45.0, abs=1e-6)
    assert records[0].power == 200
    assert sessions[0].total_distance == pytest.approx(960.0, abs=0.1)
    assert sessions[0].total_timer_time == pytest.approx(120.0, abs=0.01)


def test_fake_world_matches_contract():
    route = build_route(1234.0)
    n = route["n"]
    assert n == 125  # 0, 10, …, 1230, puis 1234
    for key in ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg"):
        assert len(route[key]) == n
    assert route["x"][0] == 0.0 and route["z"][0] == 0.0
    # Le dernier pas fait 4 m, donc la distance horizontale entre les deux derniers points aussi.
    dx = route["x"][-1] - route["x"][-2]
    dz = route["z"][-1] - route["z"][-2]
    assert (dx * dx + dz * dz) ** 0.5 == pytest.approx(4.0, abs=0.05)
    m = build_manifest("t", route)
    assert m["format"] == "openride-world" and m["route"]["n"] == n
    json.dumps(m)
