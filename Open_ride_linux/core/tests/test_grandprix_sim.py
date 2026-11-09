"""Lot GP5 : simulateur d'équilibrage du Grand Prix des objets (rejouable, rapport, cibles)."""

from openride_core.tools import grandprix_sim as gs


def test_race_is_replayable_and_complete():
    a = gs.race(4, "normal", 100.0, 7)
    assert a == gs.race(4, "normal", 100.0, 7)
    assert 1 <= a["place"] <= 5 and a["of"] == 5 and a["launched"] > 0
    assert set(a["time"]) <= set(gs.ITEM_IDS)


def test_report_lists_every_configuration_and_target():
    out = gs.simulate([2], ["normal"], [100.0, 90.0], 3, seed=1)
    assert out == gs.simulate([2], ["normal"], [100.0, 90.0], 3, seed=1, jobs=2)   # même rapport, quel que soit --jobs
    checks = gs.criteria(out)
    text = gs.report_markdown(out, checks)
    assert "| 2 | normal | 100 % |" in text and "| 2 | normal | 90 % |" in text and "## Cibles" in text
    assert len(checks) == 3   # victoires à niveau égal (pas de cible à 90 %), part du plus lourd objet pour chacun


def test_bad_call_returns_2():
    assert gs.main(["--chaos", "fou"]) == 2
    assert gs.main(["--opponents", "12"]) == 2
