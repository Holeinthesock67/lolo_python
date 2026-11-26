"""Lot FO1 : courbe de forme de « Ma puissance » (condition CTL, fatigue ATL) calculée comme le conseil, sur des
séances fabriquées d'un cycliste fictif (aucune donnée réelle, aucune puissance dans le résultat)."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, time, timedelta

from openride_core import coach

from test_power_curve_ipc import journals
from test_profils_joueurs import home, make, of  # noqa: F401  (fixture `home`)

TABLE = coach.load_table()
TODAY = date(2026, 11, 22)


def fact(day: date, tss: float) -> coach.SessionFacts:
    ts = datetime.combine(day, time(18, 0)).timestamp()
    return coach.SessionFacts(ts, 2700.0, tss, {n: 0.0 for n in coach.NEEDS}, False, {})


def test_no_session_gives_none():
    assert coach.fitness_series([], TODAY, TABLE) is None
    old = [fact(TODAY - timedelta(days=400), 60)]   # hors de la fenêtre d'amorce
    assert coach.fitness_series(old, TODAY, TABLE) is None


def test_same_values_as_the_advice():
    facts = [fact(TODAY - timedelta(days=d), 55) for d in range(0, 90, 4)]
    fit = coach.fitness_series(facts, TODAY, TABLE)
    sig = coach.build_signals(facts, 250.0, TODAY, TABLE)
    assert fit["ctl_now"] == round(sig["ctl"], 1) and fit["atl_now"] == round(sig["atl"], 1)
    assert fit["form"] == round(sig["form"], 1)
    assert fit["days"] == 84 and fit["step_days"] == 2
    assert len(fit["ctl"]) == len(fit["atl"]) == 42 and fit["ctl"][-1] == round(sig["ctl"])
    assert len(fit["weeks"]) == 12 and sum(fit["weeks"]) == sum(1 for d in range(0, 84, 4))
    assert all(isinstance(v, int) and v >= 0 for v in fit["ctl"] + fit["atl"])


def test_building_up_then_tired():
    # Huit semaines de reprise, de plus en plus chargées : la condition monte, et la dernière semaine très dure
    # fait passer la fatigue au-dessus de la condition.
    facts = [fact(TODAY - timedelta(days=d), 30 + (84 - d)) for d in range(7, 84, 3)]
    facts += [fact(TODAY - timedelta(days=d), 140) for d in range(0, 6)]
    fit = coach.fitness_series(facts, TODAY, TABLE)
    assert fit["trend"] == "up" and fit["weeks_up"] >= 4
    assert fit["form"] < -20 and fit["label"] in ("tres_fatigue", "epuise")
    assert "fatigué" in fit["label_text"]


def test_rested_after_a_break():
    facts = [fact(TODAY - timedelta(days=d), 70) for d in range(14, 84, 2)]
    fit = coach.fitness_series(facts, TODAY, TABLE)
    assert fit["trend"] == "down" and fit["weeks_up"] == 0
    assert fit["form"] >= 5 and fit["label"] == "frais"
    assert fit["weeks"][-2:] == [0, 0]   # deux semaines sans séance


def test_labels_cover_every_form():
    labels = TABLE["fitness"]["labels"]
    assert [lab["min"] for lab in labels] == sorted((lab["min"] for lab in labels), reverse=True)
    assert labels[-1]["min"] <= -1000
    assert {lab["min"] for lab in labels} >= {TABLE["rules"]["r1_form"], TABLE["rules"]["r3_form"]}


def test_power_curve_message_carries_fitness(home, monkeypatch):
    journals(home)
    s, frames = make(home, monkeypatch)
    asyncio.run(s._send_power_curve(11))
    (msg,) = of(frames, "power_curve")                 # conforme à power_curve.schema.json
    fit = msg["fitness"]
    assert fit is not None and fit["ctl_now"] > 0 and sum(fit["weeks"]) > 0
    text = json.dumps(fit, ensure_ascii=False)
    assert " W" not in text and "ftp" not in text.lower()   # points de charge seulement
    assert len(json.dumps(msg, ensure_ascii=False).encode("utf-8")) < 4096


def test_empty_profile_has_no_fitness(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    asyncio.run(s._send_power_curve(12))
    (msg,) = of(frames, "power_curve")
    assert msg["fitness"] is None
