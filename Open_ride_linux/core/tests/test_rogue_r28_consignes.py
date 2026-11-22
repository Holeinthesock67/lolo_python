"""Lot R28 : consignes du Cyber-Rogue (essai du propriétaire du 22 novembre).

La plage affichée est la plage jugée (« 170–195 W » affichés, adrénaline dès 153 W) ; l'adrénaline monte de 1 par
seconde dans la plage, quelle que soit la cadence (choix du propriétaire, A + C).
"""

from __future__ import annotations

import pytest

from openride_core.rogue.combat import in_target, judged_band_pct, overheat_limit, target_at
from test_rogue_run import B, DT, fight_engine, step_in_room


def test_owner_choice_one_per_second_whatever_the_cadence():
    assert B.adrenaline_per_s == 1.0 and B.adrenaline_roc_mult == 1.0 and B.adrenaline_veloce_mult == 1.0
    assert B.strike_cost / B.adrenaline_per_s == pytest.approx(50.0)     # une frappe Z toutes les 50 s


def test_band_is_the_judged_band_rounded_inwards():
    band = judged_band_pct(0.68, 0.78, 250.0, B)      # consigne 170 W, plafond 195 W, tolérance 17 W
    assert band == {"lo": 62, "hi": 84}               # 155 W (≥ 153 W jugés) à 210 W (≤ 212 W jugés)
    assert in_target(band["lo"] / 100, 0.68, 250.0, False, B)          # à la puissance écrite, on est dedans
    assert not in_target((band["lo"] - 2) / 100, 0.68, 250.0, False, B)
    assert judged_band_pct(0.68, None, 250.0, B)["hi"] is None


def test_room_target_pct_matches_what_fills_the_adrenaline():
    e = fight_engine(first="diesel", objective="endurance")
    out = step_in_room(e, 5.0, power=150.0)
    tgt = target_at(e.room, 5.0)
    assert out.rogue["target_pct"] == judged_band_pct(tgt, overheat_limit(tgt, B), 250.0, B)
    lo_w = out.rogue["target_pct"]["lo"] * 2.5
    out = step_in_room(e, 6.0, power=lo_w, n=round(2.0 / DT))
    assert out.rogue["in_target"] and out.rogue["adrenaline_trend"]["cause"] in ("gain", "full")
