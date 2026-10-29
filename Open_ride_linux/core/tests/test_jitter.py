"""Gigue de la boucle du core (lot X17) : histogramme, ligne du journal, log_report --gigue, séance sous charge."""

import json

import pytest

from openride_core.jitter import BIN_MS, JitterMeter, line
from openride_core.tools import gigue_charge
from openride_core.tools.log_report import PATTERNS, jitter_report
from openride_core.tools.log_report import main as log_report_main


def test_percentiles_and_max_on_fabricated_steps():
    m = JitterMeter()
    t = 0.0
    for i in range(1000):   # 990 pas réguliers à ± 0,2 ms, 9 pas en retard de 3 ms, un de 12 ms
        dt = 0.020 + (0.0002 if i % 2 else -0.0002)
        if i % 100 == 50 and i < 900:
            dt = 0.023
        if i == 999:
            dt = 0.032
        t += dt
        m.interval(t, 0.020)
    assert m.n == 999                                     # le premier pas n'a pas d'intervalle
    assert m.percentile(0.50) == pytest.approx(0.25, abs=BIN_MS)
    assert m.percentile(0.99) == pytest.approx(3.0, abs=BIN_MS)
    assert m.max_ms == pytest.approx(12.0, abs=1e-6)
    assert JitterMeter().percentile(0.99) == 0.0


def test_overflow_bin_merge_and_clear():
    a, b = JitterMeter(), JitterMeter()
    a.add(250.0)            # au-delà de 100 ms : dernière case, maximum exact
    b.add(1.0)
    a.merge(b)
    assert (a.n, a.max_ms, a.percentile(1.0)) == (2, 250.0, 250.0)
    a.interval(5.0, 0.02)
    a.clear()
    a.interval(5.021, 0.02)
    assert a.n == 1 and a.max_ms == pytest.approx(1.0, abs=1e-6)   # instant du dernier pas gardé


def test_log_line_matches_the_report_pattern():
    p, s = JitterMeter(), JitterMeter()
    for v in (0.3, 0.4, 4.0):
        p.add(v)
    s.add(15.0)
    m = PATTERNS["jitter"].match(line(p, s))
    assert m and not m["whole"] and PATTERNS["jitter"].match(line(p, s, whole=True))["whole"]
    assert float(m["p50"]) == pytest.approx(0.4, abs=BIN_MS) and float(m["max"]) == 4.0
    assert (float(m["state_max"]), int(m["n"])) == (15.0, 3)


LOG = """2026-10-28 10:00:00,000 INFO    core Core démarré (trainer=sim, entrées=none).
2026-10-28 10:01:00,000 INFO    core Gigue : physique p50 0.30 p99 1.80 max 9.00 ms ; state p99 15.00 max 19.00 ms (3000 pas)
2026-10-28 10:02:00,000 INFO    core Gigue : physique p50 0.30 p99 6.20 max 40.00 ms ; state p99 16.00 max 21.00 ms (3000 pas)
[engine] [gigue] state : écart entre trames p50 33.0 p99 50.0 max 120.0 ms (1800 trames)
2026-10-28 10:02:30,000 INFO    core Gigue (séance entière) : physique p50 0.30 p99 4.10 max 40.00 ms ; state p99 15.50 max 21.00 ms (7500 pas)
"""


def test_jitter_report_minutes_whole_and_engine():
    rep = jitter_report(LOG.splitlines())
    assert [r["p99_ms"] for r in rep["minutes"]] == [1.8, 6.2]
    assert rep["minutes"][0]["heure"] == "2026-10-28 10:01:00"
    assert rep["seance"]["pas"] == 7500 and rep["p99_ms"] == 4.1 and rep["ok"]
    assert rep["engine"] == [{"p50_ms": 33.0, "p99_ms": 50.0, "max_ms": 120.0, "trames": 1800}]
    no_whole = jitter_report(LOG.splitlines()[:3])
    assert no_whole["p99_ms"] == 6.2 and not no_whole["ok"]       # pire minute sans ligne de séance


def test_log_report_gigue_command(tmp_path, capsys):
    log = tmp_path / "run.log"
    log.write_text(LOG, encoding="utf-8")
    assert log_report_main([str(log), "--gigue"]) == 0
    out = capsys.readouterr().out
    assert "séance entière" in out and "[OK] gigue de la physique p99 4.10 ms (limite 5 ms)" in out
    log.write_text("\n".join(LOG.splitlines()[:3]) + "\n", encoding="utf-8")
    assert log_report_main([str(log), "--gigue", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["p99_ms"] == 6.2
    log.write_text(LOG.splitlines()[0] + "\n", encoding="utf-8")
    assert log_report_main([str(log), "--gigue"]) == 0              # core antérieur : rien à juger
    assert "Aucune ligne « Gigue »" in capsys.readouterr().out


def test_session_writes_the_whole_line(tmp_path):
    """Critère 2 : une courte séance simulée sans charge donne la ligne de la séance entière."""
    rep = gigue_charge.run(8.0, "aucune", tmp_path)
    assert rep["seance"] is not None and rep["seance"]["pas"] > 200, rep
    assert "Core démarré (trainer=sim, entrées=none)." in (tmp_path / "core.log").read_text(encoding="utf-8")


def test_fabricated_track(tmp_path):
    text = gigue_charge.write_track(tmp_path / "t.gpx", km=2.0).read_text(encoding="utf-8")
    assert text.count("<trkpt") == 200 and 'lat="45.' in text
