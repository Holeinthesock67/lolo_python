"""Lot R28 : consignes du Cyber-Rogue (essai du propriétaire du 22 novembre).

La plage affichée est la plage jugée (« 170–195 W » affichés, adrénaline dès 153 W) ; l'adrénaline monte de 1 par
seconde dans la plage, quelle que soit la cadence (choix du propriétaire, A + C).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from openride_core.rogue.combat import hp_factor, in_target, judged_band_pct, overheat_limit, target_at, win_target
from test_rogue_run import B, DT, fight_engine, step_in_room


def test_owner_choice_one_per_second_whatever_the_cadence():
    assert B.adrenaline_per_s == 1.0 and B.adrenaline_roc_mult == 1.0 and B.adrenaline_veloce_mult == 1.0
    assert B.strike_cost / B.adrenaline_per_s == pytest.approx(50.0)     # une frappe Z toutes les 50 s


def test_band_is_the_judged_band_rounded_inwards():
    band = judged_band_pct(0.68, 0.78, 250.0, B)      # consigne 170 W, plafond 195 W, tolérance 17 W
    assert band == {"lo": 68, "hi": 84}               # on entre à 170 W ; surchauffe au-delà de 212 W
    assert in_target(band["lo"] / 100, 0.68, 250.0, False, B)          # à la consigne écrite, on est dedans
    assert not in_target((band["lo"] - 1) / 100, 0.68, 250.0, False, B)
    assert in_target(0.62, 0.68, 250.0, True, B)                       # une fois dedans : marge de 10 % en sortie
    assert judged_band_pct(0.68, None, 250.0, B)["hi"] is None


def test_written_target_is_the_one_that_wins():
    """« Affiche une vraie consigne » : la consigne écrite vide la barre de l'ennemi à temps (PV = facteur × cible)."""
    for arch, objective in (("diesel", "threshold"), ("diesel", "endurance"), ("boss", "threshold")):
        e = fight_engine(first="diesel", objective=objective)
        room = e.room
        if arch == "boss":
            room = replace(room, archetype="boss")
        assert win_target(room, 5.0, B) == pytest.approx(target_at(room, 5.0) * hp_factor(room, B))
    assert B.boss_hp_factor == pytest.approx(1.118)   # le boss ne baisse pas (choix du propriétaire)


def test_room_target_pct_matches_what_fills_the_adrenaline():
    e = fight_engine(first="diesel", objective="endurance")
    out = step_in_room(e, 5.0, power=150.0)
    tgt = win_target(e.room, 5.0, B)
    assert out.rogue["target_pct"] == judged_band_pct(tgt, overheat_limit(tgt, B), 250.0, B)
    lo_w = out.rogue["target_pct"]["lo"] * 2.5
    out = step_in_room(e, 6.0, power=lo_w, n=round(9.0 / DT))
    assert out.rogue["in_target"] and out.rogue["adrenaline_trend"]["cause"] in ("gain", "full")
