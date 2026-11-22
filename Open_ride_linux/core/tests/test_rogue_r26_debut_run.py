"""Lot R26 : début de run et adrénaline du Cyber-Rogue (essai du propriétaire du 21 novembre).

Choix du propriétaire : l'échauffement charge l'adrénaline à sa consigne ; puissance jugée sur une moyenne de 8 s ;
tolérance de 10 % de la consigne (au moins 5 W), avec une marge de sortie ; retours `target_in` / `target_out`.
"""

from __future__ import annotations

import jsonschema
import pytest

from openride_core.rogue.combat import in_target, target_grace
from openride_core.rogue.run import RunInputs
from test_rogue_run import B, DT, ROGUE_SCHEMA, Rider, engine, fight_engine, step_in_room


def test_balance_choices_of_the_owner():
    assert B.judged_power_s == 8.0 and B.target_grace_frac == 0.10 and B.target_grace_w == 5.0


def test_grace_is_ten_percent_of_target_at_least_5_w():
    assert target_grace(0.8, 250.0, B) * 250.0 == pytest.approx(20.0)      # 200 W : 20 W
    assert target_grace(0.1, 250.0, B) * 250.0 == pytest.approx(5.0)       # 25 W : 5 W au moins


def test_in_target_has_an_exit_margin():
    tgt = 0.8                                     # 200 W pour 250 W de FTP : entrée à 180 W, sortie sous 170 W
    assert not in_target(175 / 250, tgt, 250.0, False, B)
    assert in_target(181 / 250, tgt, 250.0, False, B)
    assert in_target(171 / 250, tgt, 250.0, True, B)
    assert not in_target(169 / 250, tgt, 250.0, True, B)


def test_judged_power_is_the_8_s_mean():
    e = fight_engine()
    step_in_room(e, 5.0, power=300.0, n=round(8.0 / DT), judged=None)
    assert e.judged_w == pytest.approx(300.0, abs=2.0)
    out = step_in_room(e, 6.0, power=100.0, n=round(4.0 / DT), judged=None)
    assert out.rogue["power_judged_w"] == pytest.approx(200.0, abs=3.0)
    # bruit du trainer : ±80 W un pas sur deux, moyenne jugée à 200 W près de 5 W
    for k in range(round(8.0 / DT)):
        out = step_in_room(e, 7.0, power=200.0 + (80.0 if k % 2 else -80.0), judged=None)
    assert out.rogue["power_judged_w"] == pytest.approx(200.0, abs=5.0)


def test_warmup_charges_adrenaline_for_the_first_door():
    e = engine()
    r = Rider(e)                                  # 0,6 FTP à l'échauffement (200 s), dans la plage
    while e.phase == "WARMUP":
        r.run(max_s=r.t + DT)
    assert e.phase == "ROOM" and e.combat.adrenaline >= B.strike_cost
    assert r.outs[-2].rogue["adrenaline"] >= B.strike_cost   # affichée pendant l'échauffement
    jsonschema.validate(r.outs[-2].rogue, ROGUE_SCHEMA)


def test_warmup_below_target_keeps_adrenaline():
    e = engine()
    for _ in range(round(20.0 / DT)):
        out = e.step(DT, RunInputs(power_w=60.0, cadence_rpm=85, gear=6, ftp_w=250))
    assert out.rogue["adrenaline"] == 0.0 and out.rogue["adrenaline_trend"]["cause"] == "below"
    assert out.rogue["in_target"] is False


def test_target_in_and_out_events_once_per_crossing():
    e = fight_engine()
    tgt_w = None
    step_in_room(e, 5.0, power=60.0, n=3)
    out = step_in_room(e, 5.0, power=60.0)
    tgt_w = out.rogue["target_pct"]["lo"] * 2.5
    assert not out.rogue["in_target"]
    seen = []
    for p in (tgt_w, tgt_w, tgt_w * 0.88, tgt_w * 0.80, tgt_w * 0.80, tgt_w):
        out = step_in_room(e, 6.0, power=p)
        seen += [ev for ev in out.rogue["events"] if ev.startswith("target_")]
    assert seen == ["target_in", "target_out", "target_in"]   # 88 % : encore dedans (marge) ; 80 % : dehors
    jsonschema.validate(out.rogue, ROGUE_SCHEMA)
