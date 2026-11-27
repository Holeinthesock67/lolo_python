"""Lot PP8 : le coach lit la courbe de puissance (point faible de « Se connaître », test de rampe proposé
quand la FTP estimée s'écarte, pas à date fixe). Historiques fabriqués, aucune donnée réelle."""

from __future__ import annotations

from datetime import timedelta

from openride_core import coach
from openride_core.coach import Inputs

from test_coach import FTP, TABLE, TODAY, base_history, fact


def advise(facts, curve, **inputs):
    return coach.advise(facts, FTP, TODAY, Inputs(**inputs), TABLE, curve=curve)


def estimate(ftp_w, review, confidence="Fiable"):
    return {"estimate": {"ftp_w": ftp_w}, "review": review, "confidence": confidence, "ftp_set_w": round(FTP)}


def no_recent_test():
    return [f for f in base_history() if not f.ftp_test_w] + [fact(60, ftp_test=FTP)]


def test_curve_signals():
    s = coach.curve_signals({"weak": 300}, estimate(270, True))
    assert s == {"weak_s": 300, "review": {"estimate_w": 270, "ftp_set_w": 250}, "confirmed": False}
    assert coach.curve_signals(None, estimate(252, False))["confirmed"] is True
    assert coach.curve_signals(None, estimate(252, False, "Indicative"))["confirmed"] is False
    assert coach.curve_signals(None, {"estimate": None, "review": False}) == {"weak_s": None, "review": None,
                                                                              "confirmed": False}


def test_r4_when_estimate_drifts():
    r = advise(base_history(), coach.curve_signals(None, estimate(270, True)))   # test récent, mais écart
    assert (r["need"], r["rule"]) == ("ftp_test", "R4")
    assert "Ta FTP estimée (270 W) s'écarte de plus de 5 % de ta FTP réglée (250 W)" in r["reason"]
    assert r["details"]["curve"]["review"]["estimate_w"] == 270


def test_no_r4_on_a_fixed_date_when_estimate_confirms_ftp():
    old = no_recent_test()
    assert advise(old, None)["rule"] == "R4"                                           # sans courbe : comme avant
    assert advise(old, coach.curve_signals(None, estimate(252, False)))["rule"] != "R4"   # Fiable, < 5 %
    assert advise(old, coach.curve_signals(None, estimate(252, False, "Indicative")))["rule"] == "R4"


def test_weak_point_from_the_curve_breaks_r7_ties():
    def history():
        facts = [fact(d, light=3000, intense=330, anaerobic=0, tss=80) for d in range(3, 90, 2)]
        facts.append(fact(10, light=800, intense=700, ftp_test=FTP))
        return facts
    base = advise(history(), None, objective="courses")
    assert base["rule"] == "R7" and base["need"] == "anaerobic"                         # le moins récent
    sig = {**coach.curve_signals({"weak": 300}, None)}
    facts = [f for f in history()]
    # sans profil S4 (pas de meilleurs efforts dans les faits) : le point faible 5 min de la courbe décide
    r = advise(facts, sig, objective="courses")
    assert (r["need"], r["rule"]) == ("intense", "R7") and "profil de puissance" in r["reason"]
    assert coach.profile_weak({"profile": None, "curve": {"weak_s": 5}}, TABLE) == "anaerobic"
    assert coach.profile_weak({"profile": None, "curve": None}, TABLE) is None
