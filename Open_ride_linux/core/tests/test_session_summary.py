"""Tests du bilan de séance `openride-core summary` (lot K7)."""

import json
import time
from pathlib import Path

import pytest

from openride_core.__main__ import main as core_main
from openride_core.fit_export import write_fit
from openride_core.journal import JournalWriter, Record
from openride_core.mock_driver import MockDriver
from openride_core.tools.session_summary import (
    SummaryError, compute_summary, load_session, normalized_power, run,
)

T0 = 1_790_000_000.0


def write_session(path: Path, powers: list[float], pauses: dict[int, float] | None = None,
                  alt=None, blocks=None, cadence: float = 85.0, hr: int | None = 140) -> Path:
    """Journal à 1 Hz ; `pauses` : {indice de l'échantillon : durée de la pause avant lui}."""
    pauses = pauses or {}
    with JournalWriter(path, route_id="test") as j:
        j.event("start", T0)
        wall, dist = T0, 0.0
        for i, p in enumerate(powers):
            if i in pauses:
                j.event("pause", wall)
                wall += pauses[i]
                j.event("resume", wall)
            wall += 1.0
            dist += 8.0
            j.record(Record(ts=wall, t=float(i + 1), alt=alt(i) if alt else 100.0, distance=dist, speed=8.0,
                            power=p, cadence=cadence, hr=hr, grade=0.0, gear=12,
                            mode="ERG" if blocks else "SIM", block=blocks(i) if blocks else None))
        j.event("stop", wall)
    return path


def summary_of(path: Path, ftp: float = 250.0) -> dict:
    return compute_summary(load_session(path), ftp, str(path))


def test_constant_200w_one_hour(tmp_path: Path):
    r = summary_of(write_session(tmp_path / "s.jsonl", [200.0] * 3600))
    assert r["duration_s"] == pytest.approx(3600.0)
    assert r["np_w"] == pytest.approx(200.0, abs=1.0)
    assert r["avg_power_w"] == pytest.approx(200.0)
    assert r["if"] == pytest.approx(0.80)
    assert r["tss"] == pytest.approx(64.0, abs=0.5)
    z3 = next(z for z in r["zones"] if z["zone"] == "Z3")
    assert z3["pct"] == 100.0 and z3["seconds"] == 3600
    assert r["best_power_w"] == {"5s": 200.0, "1min": 200.0, "5min": 200.0, "20min": 200.0}
    assert r["cadence"] == {"avg": 85.0, "max": 85.0} and r["hr"] == {"avg": 140.0, "max": 140.0}
    assert r["erg"] is None


def test_np_on_square_wave_matches_hand_computation(tmp_path: Path):
    powers = ([400.0] * 30 + [0.0] * 30) * 20
    r = summary_of(write_session(tmp_path / "s.jsonl", powers))

    # Méthode écrite : pour chaque seconde k à partir de la 30ᵉ, moyenne des 30 dernières
    # secondes (boucle naïve), puissance 4, moyenne de ces valeurs, racine 4.
    rolled = [sum(powers[k - 29:k + 1]) / 30 for k in range(29, len(powers))]
    expected = (sum(x ** 4 for x in rolled) / len(rolled)) ** 0.25

    assert r["avg_power_w"] == pytest.approx(200.0)
    assert r["np_w"] > r["avg_power_w"]
    assert r["np_w"] == pytest.approx(round(expected, 1))
    # Ordre de grandeur analytique : moyenne glissante en triangle → NP ≈ 400 / 5^¼ ≈ 267,5 W.
    assert r["np_w"] == pytest.approx(400 / 5 ** 0.25, abs=2.0)
    assert r["best_power_w"]["5s"] == 400.0
    assert r["best_power_w"]["1min"] == pytest.approx(200.0)
    assert r["best_power_w"]["20min"] == pytest.approx(200.0)


def test_jsonl_and_fit_give_same_figures(tmp_path: Path):
    powers = [150.0 + (i % 47) * 3 for i in range(900)]
    j = write_session(tmp_path / "s.jsonl", powers, pauses={300: 45.0},
                      alt=lambda i: 100.0 + 20.0 * (i / 900))
    sess = load_session(j)
    fit = tmp_path / "s.fit"
    write_fit(sess.records, sess.events, fit)

    a, b = summary_of(j), summary_of(fit)
    assert b["format"] == "fit"
    for key in ("duration_s", "elapsed_s", "distance_m", "avg_power_w", "np_w", "if", "tss", "best_power_w",
                "cadence", "hr"):
        assert a[key] == pytest.approx(b[key], abs=0.2), key
    assert a["elevation_gain_m"] == pytest.approx(b["elevation_gain_m"], abs=0.5)
    assert [z["seconds"] for z in a["zones"]] == [z["seconds"] for z in b["zones"]]


def test_pause_time_is_excluded(tmp_path: Path):
    base = summary_of(write_session(tmp_path / "a.jsonl", [200.0] * 600))
    paused = summary_of(write_session(tmp_path / "b.jsonl", [200.0] * 600, pauses={300: 600.0}))
    assert paused["duration_s"] == pytest.approx(600.0)
    assert paused["elapsed_s"] == pytest.approx(1200.0)
    assert paused["np_w"] == base["np_w"] == pytest.approx(200.0)
    assert paused["tss"] == base["tss"]


def test_records_written_during_a_pause_are_ignored(tmp_path: Path):
    p = write_session(tmp_path / "s.jsonl", [200.0] * 120, pauses={60: 30.0})
    with JournalWriter(tmp_path / "x.jsonl") as j:   # copie avec des relevés à 0 W pendant la pause
        from openride_core.journal import read_journal
        for line in read_journal(p):
            if line["kind"] == "event":
                j.event(line["event"], line["ts"])
                if line["event"] == "pause":
                    for k in range(1, 30):
                        j.record(Record(ts=line["ts"] + k, t=0.0, power=0.0))
            elif line["kind"] == "record":
                j.record(Record(**{k: v for k, v in line.items() if k != "kind"}))
    r = summary_of(tmp_path / "x.jsonl")
    assert r["avg_power_w"] == pytest.approx(200.0)
    assert sum(z["seconds"] for z in r["zones"]) == 120


def test_elevation_gain_and_short_session(tmp_path: Path):
    # 300 m de montée régulière, puis du bruit de ± 0,4 m qui ne doit rien ajouter.
    alt = lambda i: 100.0 + i if i < 300 else 400.0 + (0.4 if i % 2 else -0.4)
    r = summary_of(write_session(tmp_path / "s.jsonl", [250.0] * 600, alt=alt))
    assert r["elevation_gain_m"] == pytest.approx(300.0, abs=2.0)

    short = summary_of(write_session(tmp_path / "c.jsonl", [300.0] * 90))
    assert short["best_power_w"]["5s"] == 300.0 and short["best_power_w"]["1min"] == 300.0
    assert short["best_power_w"]["5min"] is None and short["best_power_w"]["20min"] is None


def test_hr_zero_and_freewheel_cadence_ignored(tmp_path: Path):
    r = summary_of(write_session(tmp_path / "s.jsonl", [0.0] * 60, cadence=0.0, hr=0))
    assert r["cadence"] is None and r["hr"] is None
    assert r["zones"][0]["seconds"] == 60


def test_erg_blocks_without_target_are_flagged(tmp_path: Path):
    powers = [150.0] * 60 + [250.0] * 60
    r = summary_of(write_session(tmp_path / "s.jsonl", powers, blocks=lambda i: 1 + i // 60))
    erg = r["erg"]
    assert erg["target_available"] is False and "indisponible" in erg["note"]
    assert [(b["block"], b["seconds"], b["avg_power_w"], b["delta_w"]) for b in erg["blocks"]] == [
        (1, 60, 150.0, None), (2, 60, 250.0, None)]


def test_json_output_keys_are_stable(tmp_path: Path, capsys):
    p = write_session(tmp_path / "s.jsonl", [200.0] * 120)
    assert core_main(["summary", str(p), "--ftp", "250", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out) == {"source", "format", "ftp_w", "start_ts", "duration_s", "elapsed_s", "distance_m",
                        "elevation_gain_m", "avg_power_w", "np_w", "if", "tss", "zones", "best_power_w",
                        "cadence", "hr", "erg"}
    assert set(out["zones"][0]) == {"zone", "low_pct", "high_pct", "seconds", "pct"}
    assert set(out["best_power_w"]) == {"5s", "1min", "5min", "20min"}


def test_text_output_and_errors(tmp_path: Path, capsys):
    p = write_session(tmp_path / "s.jsonl", [200.0] * 120)
    assert core_main(["summary", str(p), "--ftp", "250"]) == 0
    out = capsys.readouterr().out
    assert "NP 200 W" in out and "IF 0.80" in out and "Z3" in out

    # Critère 3 et 5 du lot L6 : journal ERG avec target_w, bilan JSON/texte, FIT, recover, replay.
    from openride_core.fit_export import journal_to_fit
    from openride_core.replay import load_replay
    from openride_core.tools.session_summary import format_text

    erg_path = tmp_path / "erg_l6.jsonl"
    with JournalWriter(erg_path, route_id="test") as j:
        j.event("start", T0)
        for i in range(120):
            blk = 1 if i < 60 else 2
            pw = 195.0 if i < 60 else 308.0
            tw = 200.0 if i < 60 else 300.0
            j.record(Record(
                ts=T0 + i + 1, t=float(i + 1), alt=100.0, distance=8.0 * (i + 1),
                speed=8.0, power=pw, cadence=85.0, hr=140, grade=0.0, gear=12,
                mode="ERG", block=blk, target_w=tw,
            ))
        j.event("stop", T0 + 120)
    res_l6 = summary_of(erg_path)
    assert res_l6["erg"]["target_available"] is True
    assert res_l6["erg"]["note"] is None
    assert res_l6["erg"]["blocks"][0] == {
        "block": 1, "seconds": 60, "avg_power_w": 195.0, "target_w": 200.0, "delta_w": -5.0,
    }
    assert res_l6["erg"]["blocks"][1] == {
        "block": 2, "seconds": 60, "avg_power_w": 308.0, "target_w": 300.0, "delta_w": 8.0,
    }
    txt_l6 = format_text(res_l6)
    assert "bloc  1 : 0:01:00, 195 W / cible 200 W, écart -5 W" in txt_l6
    assert "bloc  2 : 0:01:00, 308 W / cible 300 W, écart +8 W" in txt_l6
    sess_l6 = load_session(erg_path)
    write_fit(sess_l6.records, sess_l6.events, tmp_path / "erg_l6.fit")
    rec_fit, _ = journal_to_fit(erg_path, tmp_path / "recovered_l6.fit")
    assert rec_fit.is_file()
    assert len(load_replay(erg_path)) == 120

    assert run(tmp_path / "absent.jsonl", 250.0, False) == 1
    assert "introuvable" in capsys.readouterr().err
    (tmp_path / "x.txt").write_text("rien")
    assert run(tmp_path / "x.txt", 250.0, False) == 1
    (tmp_path / "vide.jsonl").write_text("")
    with pytest.raises(SummaryError):
        load_session(tmp_path / "vide.jsonl")


def test_ftp_from_config_and_invalid_config(tmp_path: Path, capsys):
    p = write_session(tmp_path / "s.jsonl", [200.0] * 120)
    good = tmp_path / "good.toml"
    good.write_text("[rider]\nftp_w = 200\n")
    assert core_main(["summary", str(p), "--json", "--config", str(good)]) == 0
    assert json.loads(capsys.readouterr().out)["if"] == pytest.approx(1.0)

    bad = tmp_path / "bad.toml"
    bad.write_text("[rider]\nftp_w = 5000\n")
    assert core_main(["summary", str(p), "--config", str(bad)]) == 1
    assert "configuration invalide" in capsys.readouterr().err


def test_mock_driver_ten_minutes_under_one_second(tmp_path: Path):
    drv = MockDriver()
    samples = [drv.poll(float(t)) for t in range(600)]
    p = tmp_path / "mock.jsonl"
    with JournalWriter(p) as j:
        j.event("start", T0)
        for t, m in enumerate(samples):
            j.record(Record(ts=T0 + t + 1, t=float(t + 1), alt=100.0, distance=8.0 * t, speed=8.0,
                            power=m.power_w, cadence=m.cadence_rpm, hr=m.hr_bpm))
        j.event("stop", T0 + 600)
    t0 = time.perf_counter()
    assert core_main(["summary", str(p), "--ftp", "250"]) == 0
    assert time.perf_counter() - t0 < 1.0


def test_normalized_power_short_series():
    assert normalized_power([]) == 0.0
    assert normalized_power([100.0, 300.0]) == pytest.approx(200.0)
