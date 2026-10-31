"""Tests de l'historique des séances `openride-core history` (lot L7)."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from openride_core.__main__ import main as core_main
from openride_core.fit_export import journal_to_fit
from openride_core.journal import JournalWriter, Record
from openride_core.mock_driver import MockDriver
from openride_core.tools import history
from openride_core.tools.session_summary import compute_summary, load_session

# Mercredi 14 octobre 2026 à 18:00 locale (semaine ISO 2026-W42) et semaine suivante (2026-W43).
T_WEEK1_WED = datetime(2026, 10, 14, 18, 0, 0).timestamp()
T_WEEK2_TUE = datetime(2026, 10, 20, 18, 0, 0).timestamp()
T_WEEK2_THU = datetime(2026, 10, 22, 18, 0, 0).timestamp()
T_WEEK2_SAT = datetime(2026, 10, 24, 10, 0, 0).timestamp()


def _write_mock_journal(
    path: Path,
    start_ts: float,
    seconds: int = 120,
    route_id: str = "demo",
    target_w: float | None = None,
) -> Path:
    drv = MockDriver()
    if target_w is not None:
        drv.set_target_power(target_w)
    with JournalWriter(path, route_id=route_id) as j:
        j.event("start", start_ts)
        for i in range(seconds):
            m = drv.poll(float(i + 1))
            j.record(Record(
                ts=start_ts + i + 1,
                t=float(i + 1),
                lat=45.0,
                lon=6.0,
                alt=200.0 + 0.1 * i,
                distance=8.0 * (i + 1),
                speed=8.0,
                power=round(m.power_w),
                cadence=round(m.cadence_rpm),
                hr=m.hr_bpm,
                grade=2.0,
                mode="ERG" if target_w else "SIM",
                gear=12,
            ))
        j.event("stop", start_ts + seconds)
    return path


def _make_fit_from_mock(
    act_dir: Path,
    start_ts: float,
    seconds: int = 120,
    route_id: str = "demo",
    keep_journal: bool = False,
    target_w: float | None = None,
) -> Path:
    stamp = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d_%H-%M")
    j_dir = act_dir / ".journal" if keep_journal else act_dir / "_tmp_j"
    j_path = _write_mock_journal(
        j_dir / f"{stamp}_{route_id}.jsonl", start_ts, seconds=seconds, route_id=route_id, target_w=target_w
    )
    fit_path = act_dir / f"{stamp}_{route_id}.fit"
    journal_to_fit(j_path, fit_path)
    if not keep_journal:
        j_path.unlink()
    return fit_path


def test_history_deduplicates_fit_and_marks_orphan_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """Critère 2 : 3 séances FIT (dont 1 avec son journal) + 1 journal orphelin -> 4 lignes, orphelin marqué."""
    monkeypatch.setattr(history, "CACHE_PATH", tmp_path / "cache.json")
    act = tmp_path / "Activities"
    _make_fit_from_mock(act, T_WEEK1_WED, seconds=120, route_id="alpe", keep_journal=False)
    _make_fit_from_mock(act, T_WEEK2_TUE, seconds=150, route_id="ventoux", keep_journal=True)
    _make_fit_from_mock(act, T_WEEK2_THU, seconds=180, route_id="galibier", keep_journal=False)
    # Journal orphelin (plantage non récupéré).
    _write_mock_journal(act / ".journal" / "2026-10-24_10-00_demo.jsonl", T_WEEK2_SAT, seconds=90, route_id="demo")

    res = history.compute_history(act, ftp=250.0)
    sessions = res["sessions"]
    assert len(sessions) == 4
    # Tri de la plus récente à la plus ancienne.
    starts = [s["start_ts"] for s in sessions]
    assert starts == sorted(starts, reverse=True)
    assert sessions[0]["format"] == "jsonl" and sessions[0]["status"] == "recover"
    assert "à récupérer" in (sessions[0]["note"] or "")
    assert [s["format"] for s in sessions[1:]] == ["fit", "fit", "fit"]
    assert [s["route"] for s in sessions] == ["demo", "galibier", "ventoux", "alpe"]

    assert core_main(["history", "--dir", str(act), "--ftp", "250"]) == 0
    out_lines = [ln for ln in capsys.readouterr().out.splitlines() if ln and not ln.startswith(("Cumul", "  "))]
    assert len(out_lines) == 4
    assert "à récupérer : proposée à l'accueil" in out_lines[0]


def test_weekly_iso_rollup_matches_summary_totals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Critère 3 : 2 séances la même semaine ISO et 1 la semaine d'avant -> 2 semaines aux bons totaux."""
    monkeypatch.setattr(history, "CACHE_PATH", tmp_path / "cache.json")
    act = tmp_path / "Activities"
    f1 = _make_fit_from_mock(act, T_WEEK1_WED, seconds=180, route_id="s1", target_w=200.0)
    f2 = _make_fit_from_mock(act, T_WEEK2_TUE, seconds=240, route_id="s2", target_w=220.0)
    f3 = _make_fit_from_mock(act, T_WEEK2_THU, seconds=300, route_id="s3", target_w=250.0)

    s1 = compute_summary(load_session(f1), 250.0, str(f1))
    s2 = compute_summary(load_session(f2), 250.0, str(f2))
    s3 = compute_summary(load_session(f3), 250.0, str(f3))

    res = history.compute_history(act, ftp=250.0, weeks=8)
    weeks = res["weeks"]
    assert len(weeks) == 2
    w_recent, w_prev = weeks[0], weeks[1]
    assert w_recent["week"] == "2026-W43" and w_recent["count"] == 2
    assert w_recent["duration_s"] == pytest.approx(round(s2["duration_s"] + s3["duration_s"], 1))
    assert w_recent["distance_m"] == pytest.approx(round(s2["distance_m"] + s3["distance_m"], 1))
    assert w_recent["tss"] == pytest.approx(round(s2["tss"] + s3["tss"], 1))

    assert w_prev["week"] == "2026-W42" and w_prev["count"] == 1
    assert w_prev["duration_s"] == pytest.approx(s1["duration_s"])
    assert w_prev["distance_m"] == pytest.approx(s1["distance_m"])
    assert w_prev["tss"] == pytest.approx(s1["tss"])


def test_truncated_fit_listed_with_error_and_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """Critère 4 : un fichier .fit tronqué apparaît avec son erreur ; le code de sortie reste 0."""
    monkeypatch.setattr(history, "CACHE_PATH", tmp_path / "cache.json")
    act = tmp_path / "Activities"
    good = _make_fit_from_mock(act, T_WEEK2_TUE, seconds=60, route_id="demo")
    bad = act / "2026-10-23_18-00_tronque.fit"
    bad.write_bytes(good.read_bytes()[:24])

    rc = core_main(["history", "--dir", str(act), "--ftp", "250"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "2026-10-23_18-00_tronque.fit" in out and "erreur" in out

    res = history.compute_history(act, ftp=250.0)
    err_items = [s for s in res["sessions"] if s["status"] == "error"]
    assert len(err_items) == 1 and err_items[0]["error"]


def test_cache_accelerates_fifty_sessions_and_recovers_from_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Critère 5 : 2e lancement sur 50 séances < 10 % du 1er, et cache effacé ou corrompu sans erreur."""
    cache_file = tmp_path / "history_cache.json"
    monkeypatch.setattr(history, "CACHE_PATH", cache_file)
    act = tmp_path / "Activities"
    base_fit = _make_fit_from_mock(tmp_path / " proto", T_WEEK1_WED, seconds=90, route_id="demo")
    raw_bytes = base_fit.read_bytes()
    act.mkdir(parents=True, exist_ok=True)
    for k in range(50):
        (act / f"2026-10-14_18-{k:02d}_demo.fit").write_bytes(raw_bytes)

    t0 = time.perf_counter()
    res1 = history.compute_history(act, ftp=250.0)
    dt1 = time.perf_counter() - t0
    assert len(res1["sessions"]) == 50 and cache_file.is_file()

    t1 = time.perf_counter()
    res2 = history.compute_history(act, ftp=250.0)
    dt2 = time.perf_counter() - t1
    assert len(res2["sessions"]) == 50
    assert dt2 < dt1 * 0.10, f"cache trop lent : dt1={dt1:.4f}s, dt2={dt2:.4f}s"

    # Cache corrompu puis effacé : aucune erreur.
    cache_file.write_text("{corrompu", encoding="utf-8")
    assert len(history.compute_history(act, ftp=250.0)["sessions"]) == 50
    cache_file.unlink()
    assert len(history.compute_history(act, ftp=250.0)["sessions"]) == 50


def test_json_keys_and_rounding_match_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """Critère 6 : --json présente les clés documentées et les valeurs arrondies comme summary."""
    monkeypatch.setattr(history, "CACHE_PATH", tmp_path / "cache.json")
    act = tmp_path / "Activities"
    fit_path = _make_fit_from_mock(act, T_WEEK2_THU, seconds=120, route_id="col", target_w=215.0)
    ref = compute_summary(load_session(fit_path), 250.0, str(fit_path))

    assert core_main(["history", "--dir", str(act), "--ftp", "250", "--weeks", "4", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"directory", "ftp_w", "weeks_limit", "sessions", "weeks"}
    assert payload["weeks_limit"] == 4 and payload["ftp_w"] == 250.0
    assert len(payload["sessions"]) == 1
    sess = payload["sessions"][0]
    assert set(sess) == {
        "source", "filename", "format", "status", "date", "start_ts", "route",
        "duration_s", "distance_m", "elevation_gain_m", "avg_power_w", "np_w",
        "if", "tss", "note", "error", "workout", "plan",
    }
    for key in ("duration_s", "distance_m", "elevation_gain_m", "avg_power_w", "np_w", "if", "tss"):
        assert sess[key] == ref[key], key

    assert len(payload["weeks"]) == 1
    wk = payload["weeks"][0]
    assert set(wk) == {
        "week", "start_date", "end_date", "count",
        "duration_s", "distance_m", "elevation_gain_m", "tss",
    }
    assert wk["tss"] == ref["tss"]
