"""Lot T5 : records personnels par segment et classement local (module pur `records`)."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from openride_core.journal import JournalWriter, Record
from openride_core.records import TOP_N, RecordBook, RecordEntry, RecordsError
from openride_core.segment_timing import SegmentPass, passes_from_journal

ROUTE = "demo"


def a_pass(time_s: float, bonuses: tuple[str, ...] = (), seg: str = "climb-1") -> SegmentPass:
    return SegmentPass(seg, 0, 0.0, time_s, time_s, 250.0, 3.3, 3.6 * 1000 / time_s, bonuses)


def test_tables_with_and_without_bonus_are_separate():
    book = RecordBook()
    r = book.add(ROUTE, "climb-1", a_pass(300.0), "2026-10-20 18:00")
    assert r.rank == 1 and r.is_record and r.previous_best_s is None and r.gap_s is None
    r = book.add(ROUTE, "climb-1", a_pass(280.0, ("aero",)), "2026-10-21 18:00")
    assert r.is_record            # premier temps de la table « avec bonus »
    assert book.best(ROUTE, "climb-1", False).time_s == 300.0
    assert book.best(ROUTE, "climb-1", True).time_s == 280.0
    r = book.add(ROUTE, "climb-1", a_pass(290.0), "2026-10-22 18:00")
    assert r.is_record and r.previous_best_s == 300.0 and r.gap_s == pytest.approx(-10.0)
    r = book.add(ROUTE, "climb-1", a_pass(295.0), "2026-10-23 18:00")
    assert r.rank == 2 and not r.is_record and r.gap_s == pytest.approx(5.0)


def test_only_ten_best_kept_with_their_date():
    book = RecordBook()
    for i in range(12):
        book.add(ROUTE, "sprint-1", a_pass(30.0 + i, seg="sprint-1"), f"2026-10-{i + 1:02d} 18:00")
    table = book.table(ROUTE, "sprint-1", False)
    assert len(table) == TOP_N
    assert [e.time_s for e in table] == [30.0 + i for i in range(TOP_N)]
    assert table[0].date == "2026-10-01 18:00"
    r = book.add(ROUTE, "sprint-1", a_pass(99.0, seg="sprint-1"), "2026-10-30 18:00")
    assert r.rank is None and not r.is_record


def test_same_pass_is_not_counted_twice():
    book = RecordBook()
    book.add(ROUTE, "climb-1", a_pass(300.0), "2026-10-20 18:00")
    book.add(ROUTE, "climb-1", a_pass(300.0), "2026-10-20 18:00")
    assert len(book.table(ROUTE, "climb-1", False)) == 1


def test_file_round_trip_and_atomic_write(tmp_path):
    path = tmp_path / "records.json"
    assert RecordBook.load(path).routes == {}            # fichier absent : carnet vide
    book = RecordBook()
    book.add(ROUTE, "climb-1", a_pass(300.0), "2026-10-20 18:00")
    book.add(ROUTE, "climb-1", a_pass(280.0, ("power",)), "2026-10-21 18:00")
    book.save(path)
    assert not (tmp_path / "records.json.tmp").exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["routes"][ROUTE]["climb-1"]["no_bonus"][0] == {
        "time_s": 300.0, "date": "2026-10-20 18:00", "avg_power_w": 250.0, "avg_wkg": 3.3}
    again = RecordBook.load(path)
    assert again.best(ROUTE, "climb-1", True) == RecordEntry(280.0, "2026-10-21 18:00", 250.0, 3.3)


@pytest.mark.parametrize("content", [
    "pas du json",
    json.dumps({"version": 2, "routes": {}}),
    json.dumps({"version": 1, "routes": {"demo": {"climb-1": {"autre": []}}}}),
    json.dumps({"version": 1, "routes": {"demo": {"climb-1": {"no_bonus": [{"time_s": -3, "date": "x"}]}}}}),
])
def test_bad_files_are_refused(tmp_path, content):
    path = tmp_path / "records.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(RecordsError):
        RecordBook.load(path)


def test_live_gap_pro_rata_of_distance():
    book = RecordBook()
    assert book.live_gap(ROUTE, "climb-1", False, 10.0, 0.1) is None
    book.add(ROUTE, "climb-1", a_pass(300.0), "2026-10-20 18:00")
    assert book.live_gap(ROUTE, "climb-1", False, 147.0, 0.5) == pytest.approx(-3.0)
    assert book.live_gap(ROUTE, "climb-1", False, 310.0, 1.2) == pytest.approx(10.0)


def test_local_ranking_you_records_and_bots_without_extra_ghost():
    book = RecordBook()
    book.add(ROUTE, "climb-1", a_pass(300.0), "2026-10-20 18:00")
    book.add(ROUTE, "climb-1", a_pass(310.0), "2026-10-21 18:00")
    book.add(ROUTE, "climb-1", a_pass(250.0, ("aero",)), "2026-10-22 18:00")   # autre table
    rows = book.ranking(ROUTE, "climb-1", a_pass(305.0), {"grimpeur": 290.0, "diesel": 320.0})
    assert [(r.kind, r.id) for r in rows] == [
        ("bot", "grimpeur"), ("record", "2026-10-20 18:00"), ("you", "you"),
        ("record", "2026-10-21 18:00"), ("bot", "diesel")]
    # Le fantôme ne s'ajoute pas : ton meilleur temps (300 s) le représente déjà.
    assert sum(r.kind == "record" for r in rows) == 2


def _write_journal(path, route_id, laps_at_10mps, pause_in_first=False, powerup_at=None):
    """Séance de `laps_at_10mps` × 1 000 m à 10 m/s, relevés à 1 Hz."""
    ts0 = datetime(2026, 10, 25, 18, 0).timestamp()
    with JournalWriter(path, route_id=route_id) as j:
        j.event("start", ts0)
        if powerup_at is not None:
            j.powerup("aero", powerup_at, 15.0, ts0 + powerup_at)
        for k in range(int(laps_at_10mps * 100) + 1):
            if pause_in_first and k == 50:
                j.event("pause", ts0 + k)
                j.event("resume", ts0 + k)
            j.record(Record(ts=ts0 + k, t=float(k), distance=10.0 * k, speed=10.0, power=200.0))
        j.event("stop", ts0 + 1000)


def test_rebuild_from_journals(tmp_path):
    seg = SimpleNamespace(id="climb-1", name="Côte", type="climb", s_start=100.0, s_end=600.0)
    _write_journal(tmp_path / "a.jsonl", ROUTE, 1.0)
    _write_journal(tmp_path / "b.jsonl", ROUTE, 1.0, pause_in_first=True)     # passage annulé
    _write_journal(tmp_path / "c.jsonl", "autre", 1.0)                        # autre parcours
    _write_journal(tmp_path / "d.jsonl", ROUTE, 1.0, powerup_at=20.0)          # bonus aéro
    book = RecordBook.rebuild(ROUTE, sorted(tmp_path.glob("*.jsonl")), [seg], 1000.0)
    plain = book.table(ROUTE, "climb-1", False)
    assert len(plain) == 1 and plain[0].time_s == pytest.approx(50.0, abs=0.02)
    assert plain[0].date == "2026-10-25 18:00"
    assert book.best(ROUTE, "climb-1", True).time_s == pytest.approx(50.0, abs=0.02)
    # Fusion dans un carnet existant sans doublon.
    book.merge(RecordBook.rebuild(ROUTE, [tmp_path / "a.jsonl"], [seg], 1000.0))
    assert len(book.table(ROUTE, "climb-1", False)) == 1


def test_journal_powerup_line_is_read_back(tmp_path):
    seg = SimpleNamespace(id="climb-1", name="Côte", type="climb", s_start=100.0, s_end=600.0)
    _write_journal(tmp_path / "d.jsonl", ROUTE, 1.0, powerup_at=20.0)
    lines = [json.loads(x) for x in (tmp_path / "d.jsonl").read_text().splitlines()]
    pu = next(x for x in lines if x["kind"] == "powerup")
    assert pu["powerup"] == "aero" and pu["t"] == 20.0 and pu["duration_s"] == 15.0
    (p,) = passes_from_journal(tmp_path / "d.jsonl", [seg], 1000.0)
    assert p.bonuses == ("aero",) and p.with_bonus
