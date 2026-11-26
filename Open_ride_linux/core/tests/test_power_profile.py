"""Lot PP5 : « Se connaître » (profil en un mot, point fort et point faible, forme, record vieillissant, trous),
séances fabriquées (modèle à 250 W, aucune donnée réelle)."""

from __future__ import annotations

from openride_core.tools import power_curve as pc
from openride_core.tools import power_profile as pp

from test_power_curve import DAY, LIVE, NOW, write_journal

P20 = 250.0


def best(p5=3.4, p60=1.7, p300=1.18):
    return {5: p5 * P20, 60: p60 * P20, 300: p300 * P20, 1200: P20}


def test_kind_in_one_word():
    assert pp.kind_of(best())["kind"] == "complet"
    sprint = pp.kind_of(best(p5=4.2))
    assert sprint == {"kind": "sprinteur", "strong": 5, "weak": 1200, "missing": []} or sprint["kind"] == "sprinteur"
    assert pp.kind_of(best(p60=2.1))["kind"] == "puncheur" and pp.kind_of(best(p60=2.1))["strong"] == 60
    assert pp.kind_of(best(p300=1.4))["kind"] == "grimpeur"
    rouleur = pp.kind_of(best(p5=3.0, p60=1.5, p300=1.08))
    assert rouleur["kind"] == "rouleur" and rouleur["strong"] == 1200 and rouleur["weak"] in (5, 60, 300)


def test_missing_effort_gives_no_word():
    b = best()
    del b[1200]
    assert pp.kind_of(b) == {"kind": None, "strong": None, "weak": None, "missing": [1200]}


def windows(tmp_path):
    kept = pc.kept_sessions(pc.session_entries(tmp_path / "Activities", tmp_path / "c.json"), LIVE)
    return pc.window_curve(kept, 183, NOW), pc.window_curve(kept, 42, NOW)


def test_form_aging_and_gaps(tmp_path):
    j = tmp_path / "Activities" / ".journal"
    write_journal(j, "vieux", NOW - 150 * DAY, [(1200, 260.0), (300, 100.0), (5, 900.0)])
    write_journal(j, "recent", NOW - 5 * DAY, [(1200, 247.0), (300, 100.0), (5, 855.0)])
    write_journal(j, "erg", NOW - 2 * DAY, [(3600, 200.0, True)])
    m6, w6 = windows(tmp_path)
    r = pp.profile_from_windows(m6, w6, NOW)
    assert r["form_pct"] == 95                                   # 247/260 et 855/900
    assert r["aging"]["age_d"] == 150 and r["aging"]["left_d"] == 33 and r["aging"]["s"] in pc.DURATIONS_S
    assert r["gaps"] and r["gaps"][-1] == [1800, 3600]           # 60 min en ERG : pas un effort à fond
    assert "Trou : aucun effort libre de 30 min à 60 min depuis 6 semaines" in pp.format_text(r)


def test_empty_profile(tmp_path):
    (tmp_path / "Activities").mkdir()
    m6, w6 = windows(tmp_path)
    r = pp.profile_from_windows(m6, w6, NOW)
    assert r["kind"] is None and r["form_pct"] is None and r["aging"] is None and r["gaps"] == []
