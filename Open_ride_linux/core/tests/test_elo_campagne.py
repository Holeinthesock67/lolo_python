"""Banc des campagnes Elo simulées (lot BOT-elo) : courte campagne avec la vraie séance, contrôles et appel."""

import pytest

from openride_core import bot_elo
from openride_core.tools import elo_campagne as ec


@pytest.mark.slow
def test_campagne_courte_plus_fort_monte_plus_faible_descend():
    strong = ec.campaign(1.08, races=4, opponents=3)
    weak = ec.campaign(0.92, races=4, opponents=3)
    assert len(strong["lines"]) == 4 and strong["of"] == 4
    assert strong["final"] > bot_elo.START > weak["final"]
    assert all(1 <= ln["place"] <= 4 for ln in strong["lines"] + weak["lines"])
    assert strong["offset_max"] <= bot_elo.OFFSET_MAX


def test_controles_de_la_campagne():
    def run(force, final, place=2.5, std=10.0):
        return {"force": force, "final": final, "of": 5, "tail_place": place, "tail_std": std, "offset_max": 50.0}
    ok = ec.checks([run(0.92, 1350), run(1.0, 1490), run(1.08, 1650)])
    assert all(c for c, _ in ok)
    bad = ec.checks([run(0.92, 1490), run(1.08, 1480, place=1.2, std=90.0)])
    texts = [t for c, t in bad if not c]
    assert any("ordre des forces" in t for t in texts) and any("monte" in t for t in texts)
    assert any("descend" in t for t in texts) and any("juste part" in t for t in texts)
    assert any("stable" in t for t in texts)


def test_appel_invalide():
    assert ec.main(["--courses", "2"]) == 2
    assert ec.main(["--forces", "x"]) == 2
