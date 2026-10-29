"""Analyse automatique d'une séance (lot X12) : journaux fabriqués (montée à 7 %, ERG à paliers, coupure)."""

import json
import math

import pytest

from openride_core.tools import session_report as sr

T0 = 1_760_000_000.0


def write_journal(path, records, extra=()):
    lines = [{"kind": "header", "version": 1, "route_id": "essai", "workout_id": None}, {"kind": "event", "ts": T0, "event": "start"}]
    lines += [{"kind": "record", **r} for r in records] + list(extra)
    lines.append({"kind": "event", "ts": records[-1]["ts"] + 1, "event": "stop"})
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    return path


def climb_ride(tau=10.0, step_at=120, n=300):
    """Plat à 150 W, puis montée à 7 % dès `step_at` s : puissance du 1er ordre vers 250 W (constante `tau`)."""
    recs, dist = [], 0.0
    for t in range(n):
        climbing = t >= step_at
        p = 150.0 + (100.0 * (1 - math.exp(-(t - step_at) / tau)) if climbing else 0.0)
        speed = 6.0 if climbing else 9.0
        dist += speed
        recs.append({"ts": T0 + t, "t": float(t), "distance": dist, "speed": speed, "power": p, "cadence": 88.0,
                     "hr": 130, "grade": 7.0 if climbing else 0.0, "grade_sent": 3.5 if climbing else 0.0,
                     "gear": 9 if climbing else 14, "alt": 100.0, "mode": "SIM"})
    return recs


def test_first_order_response_of_10_s_gives_a_lag_of_10_s(tmp_path):
    out = sr.build(write_journal(tmp_path / "s.jsonl", climb_ride(tau=10.0)))
    (step,) = out["grade_steps"]
    assert (step["grade_from_pct"], step["grade_to_pct"]) == (0.0, 7.0)
    assert step["lag_s"] == pytest.approx(10.0, abs=1.0)
    assert step["power_from_w"] == 150.0 and step["power_to_w"] > 245.0


def test_sections_split_the_flat_and_the_climb(tmp_path):
    out = sr.build(write_journal(tmp_path / "s.jsonl", climb_ride()))
    flat, climb = out["sections"]
    assert (flat["grade_pct"], climb["grade_pct"]) == (0.0, 7.0)
    assert flat["length_m"] >= 200.0 and climb["start_m"] == pytest.approx(120 * 9.0 + 6.0, abs=10)
    assert (flat["gear"], climb["gear"], climb["grade_sent_pct"]) == (14, 9, 3.5)
    assert (flat["power_w"], flat["cadence_rpm"], flat["speed_kmh"], flat["hr_bpm"]) == (150.0, 88.0, 32.4, 130)


def test_short_bumps_stay_in_their_section(tmp_path):
    recs = climb_ride(n=120)            # 1 080 m de plat
    for r in recs[50:55]:               # 45 m à 5 % : trop court pour une section
        r["grade"] = 5.0
    assert len(sr.build(write_journal(tmp_path / "s.jsonl", recs))["sections"]) == 1


def test_erg_steps_deviation_and_time_outside_5_percent(tmp_path):
    recs = []
    for t in range(120):
        block, target = (1, 150.0) if t < 60 else (2, 250.0)
        power = target + (40.0 if t in (60, 61, 62) else 2.0)   # trois secondes de dépassement au changement de palier
        recs.append({"ts": T0 + t, "t": float(t), "distance": 8.0 * t, "speed": 8.0, "power": power, "cadence": 90.0,
                     "grade": 0.0, "mode": "ERG", "block": block, "target_w": target})
    b1, b2 = sr.build(write_journal(tmp_path / "e.jsonl", recs))["erg"]
    assert (b1["block"], b1["seconds"], b1["delta_median_w"], b1["outside_5pct_s"]) == (1, 60, 2.0, 0)
    assert (b2["target_w"], b2["outside_5pct_s"], b2["delta_p90_w"]) == (250.0, 3, 2.0)


def test_dropout_segments_and_powerups_are_reported(tmp_path):
    extra = [{"kind": "device", "ts": T0 + 30, "device": "trainer", "state": "down"},
             {"kind": "device", "ts": T0 + 34.5, "device": "trainer", "state": "up"},
             {"kind": "segment", "ts": T0 + 200, "segment_id": "climb1", "lap": 0, "type": "climb", "category": "4",
              "time_s": 80.2, "bonuses": [], "pr": True},
             {"kind": "powerup", "ts": T0 + 150, "powerup": "aero", "t": 150.0, "duration_s": 15.0}]
    out = sr.build(write_journal(tmp_path / "s.jsonl", climb_ride(), extra))
    assert out["devices"] == {"trainer": {"drops": 1, "down_s": 4.5}}
    assert out["segments"] == [{"segment_id": "climb1", "lap": 0, "type": "climb", "category": "4", "time_s": 80.2,
                                "pr": True, "bonuses": []}]
    assert out["powerups"] == [{"powerup": "aero", "t": 150.0, "duration_s": 15.0}]


def test_engine_perf_lines():
    text = ("[perf-rendu] images/s moy 58.0 ; temps d'image p50 16.1 / p99 30.2 / max 41.0 ms ; arbres 10 ; appels de dessin 300 ; préréglage low\n"
            "[perf-rendu] images/s moy 44.0 ; temps d'image p50 20.0 / p99 55.0 / max 90.5 ms ; arbres 10 ; appels de dessin 300 ; préréglage low\n")
    assert sr.engine_perf(text) == {"count": 2, "fps_min": 44.0, "fps_median": 51.0, "frame_p99_max_ms": 55.0, "frame_max_ms": 90.5}
    assert sr.engine_perf("rien") is None


def test_report_files_are_written_offline(tmp_path, capsys):
    journal = write_journal(tmp_path / "seance.jsonl", climb_ride())
    assert sr.main([str(journal), "--out", str(tmp_path / "rapport")]) == 0
    page = (tmp_path / "rapport" / "rapport.html").read_text()
    assert "<svg" in page and "http" not in page.replace('xmlns="http', "")   # aucune ressource en ligne
    assert (tmp_path / "rapport" / "sections.csv").read_text().splitlines()[0].startswith("index;start_m;length_m")
    resume = json.loads((tmp_path / "rapport" / "resume.json").read_text())
    assert resume["source"] == "seance.jsonl" and "_profile" not in resume
    assert "retard 10 s" in capsys.readouterr().out
    assert sr.main([str(tmp_path / "absent.jsonl"), "--out", str(tmp_path / "x")]) == 1
