"""Banc de latence du trainer (lot X5) : analyse sur des réponses synthétiques, puis essai complet
sur le Bluetooth simulé (le trainer simulé suit sa consigne avec une constante de 1,5 s)."""

import asyncio
import math

import pytest

from openride_core import config
from openride_core.sim_scenarios import build_world, load_scenario
from openride_core.tools import trainer_steps as ts


def first_order(rec, t_from, t_to, p0, p1, tau, delay, hz=4.0, noise=0.0):
    t = t_from
    while t < t_to:
        dt = t - t_from - delay
        p = p0 if dt < 0 else p1 + (p0 - p1) * math.exp(-dt / tau)
        rec.samples.append((t, p + noise * math.sin(7 * t), 85.0))
        t += 1.0 / hz


def synthetic(tau=2.0, delay=0.5, noise=0.0):
    rec = ts.Recording()
    rec.steps = [(0.0, ts.Step("erg", 150, 20)), (20.0, ts.Step("erg", 250, 30))]
    first_order(rec, 0.0, 20.0, 150, 150, tau, 0)
    first_order(rec, 20.0, 50.0, 150, 250, tau, delay, noise=noise)
    rec.events = [(0.0, "command", "erg 150"), (20.0, "command", "erg 250"),
                  (20.05, "write", "ERG 250 W"), (20.11, "ack", "réponse ERG SUCCESS")]
    return rec


def test_first_order_response_is_measured():
    r = ts.analyse(synthetic())[1]
    assert r.write_ms == pytest.approx(50, abs=1) and r.ack_ms == pytest.approx(60, abs=1)
    assert r.baseline_w == pytest.approx(150) and r.final_w == pytest.approx(250, abs=0.5)
    # 63 % à délai + tau, au pas des trames (4 Hz) et de la moyenne sur 3 trames près
    assert 2.5 <= r.t63_s <= 3.1
    assert r.t10_s < r.t63_s < r.t90_s and 0.5 + 2 * 2.3 - 0.1 <= r.t90_s <= 5.6
    assert r.overshoot_pct == 0.0 and r.settle_s is not None


def test_noise_does_not_break_thresholds():
    r = ts.analyse(synthetic(noise=4.0))[1]
    assert r.t63_s is not None and 2.0 <= r.t63_s <= 3.5


def test_decreasing_step_and_first_step():
    rec = ts.Recording()
    rec.steps = [(0.0, ts.Step("sim", 8, 20)), (20.0, ts.Step("sim", 0, 30))]
    first_order(rec, 0.0, 20.0, 240, 240, 1, 0)
    first_order(rec, 20.0, 50.0, 240, 180, 6.0, 1.0)   # relâchement lent
    first, down = ts.analyse(rec)
    assert first.note == "palier de départ"
    assert down.delta_w == pytest.approx(-60, abs=1) and 6.5 <= down.t63_s <= 7.5
    assert down.write_ms is None   # aucune écriture relevée


def test_tiny_change_is_not_measured():
    rec = ts.Recording()
    rec.steps = [(0.0, ts.Step("sim", 0, 10)), (10.0, ts.Step("sim", 1, 10))]
    first_order(rec, 0.0, 20.0, 180, 180, 1, 0)
    assert "trop faible" in ts.analyse(rec)[1].note


def test_save_load_and_report(tmp_path):
    rec = synthetic()
    ts.save(rec, tmp_path)
    again = ts.load(tmp_path)
    assert len(again.samples) == len(rec.samples) and again.steps[1][1].value == 250
    results = ts.analyse(again)
    text = ts.write_results(results, tmp_path)
    assert "150→250 W" in text and (tmp_path / "steps.csv").is_file()
    assert "<svg" in ts.write_report(again, results, tmp_path).read_text(encoding="utf-8")


def test_protocols(tmp_path):
    assert ts.load_protocol("sim")[0].hold_s == 60
    fast = ts.load_protocol("erg", fast=True)
    assert all(s.hold_s <= 8 for s in fast) and fast[1].value == 250
    custom = tmp_path / "p.json"
    custom.write_text('{"steps": [{"mode": "sim", "value": 5, "hold_s": 20}]}', encoding="utf-8")
    assert ts.load_protocol(str(custom)) == [ts.Step("sim", 5.0, 20.0)]
    custom.write_text('{"steps": [{"mode": "pente", "value": 5, "hold_s": 20}]}', encoding="utf-8")
    with pytest.raises(ValueError):
        ts.load_protocol(str(custom))


def test_bench_on_simulated_trainer():
    world = build_world(load_scenario("nominal"), "nominal", click=False, hr=False)
    steps = [ts.Step("erg", 150, 4), ts.Step("erg", 250, 6)]
    rec = asyncio.run(ts.run_bench(steps, config.Config(), sim_world=world, lead_in_s=0))
    assert world.trainer.released                       # trainer relâché à la fin
    assert any(e[1] == "write" for e in rec.events) and any(e[1] == "ack" for e in rec.events)
    up = ts.analyse(rec)[1]
    assert up.ack_ms is not None and up.ack_ms < 200
    assert up.t63_s is not None and 0.8 <= up.t63_s <= 3.0   # constante du trainer simulé : 1,5 s


def test_bench_measures_the_realistic_model():
    """Lot X6 : sur le trainer simulé réaliste, le banc retrouve le t63 du modèle à ± 20 %."""
    spec = load_scenario("realiste")
    spec["trainer"].update({"brake_delay_s": 0.3, "brake_tau_up_s": 0.8, "brake_tau_down_s": 1.6,
                            "rider_max_w": 2000})
    world = build_world(spec, "realiste", click=False, hr=False)
    steps = [ts.Step("erg", 150, 4), ts.Step("erg", 250, 7), ts.Step("erg", 150, 9)]
    rec = asyncio.run(ts.run_bench(steps, config.Config(), sim_world=world, lead_in_s=0))
    checks = ts.model_checks(ts.analyse(rec), world.trainer.model, 1.0 / world.trainer.ibd_hz)
    assert len(checks) == 2 and all(ok for ok, _ in checks), checks
    assert ts.load_protocol("marche_pente", fast=True, fast_hold_s=20.0)[1].hold_s == 20.0
    assert [s.hold_s for s in ts.load_protocol("rogue_fenetres")[1:6]] == [1.5] * 5

