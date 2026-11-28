"""Série PP, lot PP6 : bots calés sur la courbe du cycliste (cycliste fictif à FTP 250 W, aucune donnée réelle)."""

from __future__ import annotations

import math

import pytest

from openride_core import bot_effort as be

CURVE = ((60.0, 172.0), (300.0, 126.0), (1200.0, 103.0), (3600.0, 96.0))


def test_generic_without_curve_or_outside_its_durations():
    assert be.curve_pct_for(None, 1200.0) == be.curve_pct(1200.0)
    assert be.curve_pct_for(CURVE, 7200.0) == be.curve_pct(7200.0)   # au-delà de l'heure : courbe type
    assert be.curve_pct_for(((300.0, 120.0),), 300.0) == be.curve_pct(300.0)   # un seul point : courbe type


def test_personal_curve_used_and_bounded():
    assert be.curve_pct_for(CURVE, 300.0) == pytest.approx(126.0)
    mid = be.curve_pct_for(CURVE, math.sqrt(300.0 * 1200.0))
    assert 103.0 < mid < 126.0
    huge = ((60.0, 260.0), (3600.0, 60.0))      # record isolé et heure très faible : ± 15 % de la courbe type
    assert be.curve_pct_for(huge, 60.0) == pytest.approx(be.curve_pct(60.0) * 1.15)
    assert be.curve_pct_for(huge, 3600.0) == pytest.approx(be.curve_pct(3600.0) * 0.85)


def test_target_pct_follows_the_curve():
    time_of = lambda w: 600.0 * 200.0 / max(w, 1.0)   # noqa: E731 - temps d'un passage, décroissant
    generic, d0 = be.target_pct(100.0, be.Effort("max"), 250.0, time_of, 5000.0)
    mine, d1 = be.target_pct(100.0, be.Effort("max", curve=CURVE), 250.0, time_of, 5000.0)
    assert mine != pytest.approx(generic)
    assert mine == pytest.approx(be.curve_pct_for(CURVE, d1), rel=0.05)
    fixed, d = be.target_pct(100.0, be.Effort("max", duration_s=3600.0, curve=CURVE), 250.0, time_of, 5000.0)
    assert d == 3600.0 and fixed == pytest.approx(96.0)


def test_hold_s_is_the_inverse():
    for pct in (150.0, 120.0, 100.0):
        d = be.hold_s(pct, CURVE)
        assert be.curve_pct_for(CURVE, d) == pytest.approx(pct, abs=0.1)
    assert be.hold_s(500.0, CURVE) == be.HOLD_MIN_S
    assert be.hold_s(10.0, CURVE) == be.HOLD_MAX_S
    assert be.hold_s(110.0) == pytest.approx(600.0, rel=0.02)   # courbe type : 110 % sur 10 min


def test_personal_curve_from_windows():
    w6 = [{"seconds": 300, "watts": 320}, {"seconds": 1200, "watts": 260}, {"seconds": 60, "watts": None}]
    m6 = [{"seconds": 60, "watts": 430}, {"seconds": 300, "watts": 330}, {"seconds": 3600, "watts": 270}]
    c = be.personal_curve(w6, m6, 250.0)
    # 6 semaines d'abord (300 s : 320 W), 6 mois ailleurs ; l'heure ne dépasse jamais les 20 min.
    assert c == ((60.0, 172.0), (300.0, 128.0), (1200.0, 108.0), (3600.0, 108.0))
    assert be.personal_curve([], [{"seconds": 300, "watts": 300}], 250.0) is None
    assert be.personal_curve(w6, m6, 0.0) is None


def test_session_effort_carries_the_curve(tmp_path):
    from openride_core.config import Config
    from openride_core.input_providers import NullProvider
    from openride_core.mock_driver import MockDriver
    from openride_core.session import CoreSession

    s = CoreSession(Config(), driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes", workouts_dir=tmp_path / "workouts",
                    records_path=tmp_path / "records.json", profile_path=tmp_path / "profile.json")
    assert s._bot_effort(None).curve is None
    s._rider_curve = CURVE
    assert s._bot_effort(None).curve == CURVE
    assert s._bot_effort("grandprix").curve == CURVE


def test_rider_curve_from_journals(tmp_path):
    """Séance fictive de 25 min à 260 W : 20 min à 104 % d'une FTP de 250 W."""
    from openride_core.ipc_lists import rider_curve
    from openride_core.journal import JournalWriter, Record

    act = tmp_path / "Activities"
    path = act / ".journal" / "s.jsonl"
    path.parent.mkdir(parents=True)
    start = 1772880000.0
    with JournalWriter(path, route_id="demo", source="live") as w:
        w.event("start", start)
        for i in range(1, 25 * 60 + 1):
            w.record(Record(ts=start + i, t=float(i), distance=8.0 * i, alt=100.0, power=260.0))
        w.event("stop", start + 25 * 60 + 1)
    c = rider_curve(act, tmp_path / "cache" / "mmp.json", ("live",), 250.0, now=start + 3600.0)
    assert c is not None and dict(c)[1200.0] == pytest.approx(104.0)
    assert rider_curve(tmp_path / "vide", tmp_path / "cache2.json", ("live",), 250.0) is None
