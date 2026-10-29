"""Décrochages du trainer ou fatigue, et pompage (lot X44) : cas synthétiques, journal de séance et banc."""

import json
import math

import pytest

from openride_core.tools import decrochages as dc
from openride_core.tools import trainer_steps as ts


def series(fn, t1=60.0, hz=4.0):
    out, t = [], 0.0
    while t < t1:
        p, c = fn(t)
        out.append(dc.Sample(round(t, 3), p, c))
        t += 1.0 / hz
    return out


def brake_loss(t):          # 29/10 : 449 W puis 0 W en 2 s, cadence constante
    if t < 30:
        return 449.0, 75.0
    return max(449.0 - (t - 30) * 220.0, 5.0), 75.0


def fatigue(t):             # la cadence baisse 3 s avant que la puissance s'effondre
    cad = 85.0 if t < 27 else max(85.0 - (t - 27) * 6.0, 50.0)
    p = 450.0 if t < 30 else max(450.0 - (t - 30) * 200.0, 60.0)
    return p, cad


def test_power_drop_at_same_cadence_is_the_trainer():
    drops = dc.detect_drops(series(brake_loss))
    assert len(drops) == 1
    d = drops[0]
    assert 29.0 <= d.t <= 31.0 and d.from_w == pytest.approx(449, abs=1) and d.to_w < 180
    assert d.kind == "trainer" and d.cadence_fall_lead_s is None


def test_cadence_falling_first_is_fatigue():
    d = dc.detect_drops(series(fatigue))[0]
    assert d.kind == "fatigue" and d.cadence_fall_lead_s > 0


def test_stopping_and_small_changes():
    stop = dc.detect_drops(series(lambda t: (300.0, 80.0) if t < 30 else (0.0, 0.0)))
    assert stop[0].kind == "arret"
    assert dc.detect_drops(series(lambda t: (120.0, 80.0) if t < 30 else (0.0, 80.0))) == []   # sous 150 W
    assert dc.detect_drops(series(lambda t: (300.0, 80.0) if t < 30 else (200.0, 80.0))) == []  # −33 %


def test_statuses_and_marks_are_attached():
    drops = dc.attach(dc.detect_drops(series(brake_loss)), [(31.0, "statut 0x14"), (50.0, "loin")], [33.0])
    assert drops[0].statuses == [f"{31.0 - drops[0].t:+.1f} s statut 0x14"] and drops[0].marked


def test_pumping_amplitude_period_and_zero_drops():
    wave = series(lambda t: (300.0 + 60.0 * math.sin(2 * math.pi * t / 8.0), 80.0), t1=120.0, hz=1.0)
    p = dc.pumping(wave, 0.0, 120.0)
    assert p.period_s == pytest.approx(8.0, abs=0.6) and 15.0 <= p.amplitude_pct <= 45.0   # moyenne 4 s : atténuée
    # Coups de pédale (2,4 par seconde) vus à 4 Hz : la moyenne sur 4 s les efface.
    pedal = series(lambda t: (250.0 + 80.0 * math.sin(2 * math.pi * 2.4 * t), 73.0), t1=120.0)
    flat = dc.pumping(pedal, 0.0, 120.0)
    assert flat.amplitude_pct < 10.0
    holes = series(lambda t: (0.0 if 20 <= t % 30 < 22 else 250.0, 80.0), t1=90.0, hz=2.0)
    assert dc.pumping(holes, 0.0, 90.0).zero_drops == 3


def test_session_journal(tmp_path, capsys):
    path = tmp_path / "s.jsonl"
    lines = [{"kind": "header", "version": 1}]
    for k in range(60):
        p, c = brake_loss(float(k))
        lines.append({"kind": "record", "ts": 1000.0 + k, "t": float(k), "power": p, "cadence": c})
    lines += [{"kind": "ftms", "ts": 1031.0, "event": "status", "code": "0x14", "name": "SPIN_DOWN_STATUS", "data": "14 01"},
              {"kind": "ftms", "ts": 1032.0, "event": "brake_loss", "from_w": 449, "to_w": 5, "cadence_rpm": 75},
              {"kind": "event", "ts": 1034.0, "event": "decrochage"}]
    path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    src = dc.read_source(path)
    drops, pumps = dc.analyse(src)
    assert len(drops) == 1 and drops[0].kind == "trainer" and drops[0].marked
    assert any("SPIN_DOWN_STATUS" in s for s in drops[0].statuses) and any("frein lâché" in s for s in drops[0].statuses)
    assert pumps[0][0] == "séance"
    assert dc.main([str(path), "--html", str(tmp_path / "r.html")]) == 0
    out = capsys.readouterr().out
    assert "trainer (cadence inchangée)" in out and (tmp_path / "r.html").read_text(encoding="utf-8").count("<table") == 2
    assert dc.main([str(tmp_path / "absent.jsonl")]) == 2


def test_bench_report_has_drops_and_pumping(tmp_path):
    rec = ts.Recording()
    rec.steps = [(0.0, ts.Step("sim_w", 150, 30, 1.2)), (30.0, ts.Step("sim_w", 470, 30, 6.4))]
    for s in series(brake_loss):
        rec.samples.append((s.t, s.power_w, s.cadence_rpm, 30.0, 20.0))
    rec.events = [(31.0, "ftms", "statut SPIN_DOWN_STATUS [14 01]"), (33.0, "decrochage", "")]
    src = ts.bench_source(rec, "essai")
    drops, pumps = dc.analyse(src)
    assert drops[0].kind == "trainer" and drops[0].marked and [lb for lb, _ in pumps] == ["palier 1", "palier 2"]
    ts.save(rec, tmp_path)
    html = ts.write_report(rec, ts.analyse(rec), tmp_path).read_text(encoding="utf-8")
    assert "<h2>Décrochages</h2>" in html and "SPIN_DOWN_STATUS" in html
    again = dc.read_source(tmp_path)
    assert dc.analyse(again)[0][0].kind == "trainer" and len(again.segments) == 2
