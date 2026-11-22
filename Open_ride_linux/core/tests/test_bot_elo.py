"""Cote Elo du cycliste et des bots (lot BOT-elo) : règle, bornes, fichier, convergence simulée."""

from __future__ import annotations

import json
import random
import statistics

import pytest

from openride_core import bot_elo as E


def test_plan_keys_suit_les_noms_des_bots():
    assert E.plan_keys(["climber", "rouleur", "climber", "sprinter", "rouleur"]) == [
        "climber#1", "rouleur#1", "climber#2", "sprinter#1", "rouleur#2"]


def test_facteur_25_pour_cent_par_100_points():
    assert E.level_factor(E.START) == pytest.approx(1.0)
    assert E.level_factor(E.START + 100) == pytest.approx(1.025)
    assert E.level_factor(E.START - 200) == pytest.approx(0.95)


def test_victoire_fait_monter_la_cote_et_le_peloton():
    book = E.EloBook()
    keys = E.plan_keys(["climber", "rouleur", "sprinter"])
    line = book.update([[E.ME]] + [[k] for k in keys], "grandprix", ts=10.0)
    assert line["place"] == 1 and line["of"] == 4
    assert line["before"] == 1500 and line["after"] > 1500 and line["delta"] == line["after"] - 1500
    # K provisoire : 40 × (3 × 0,5) / 3 = +20
    assert book.rating == pytest.approx(1520.0)
    assert book.factor("climber#1") > 1.0
    assert sum(book.offsets[k] for k in keys) == pytest.approx(0.0, abs=0.2)


def test_defaite_fait_baisser_la_cote():
    book = E.EloBook()
    line = book.update([["climber#1"], ["rouleur#1"], [E.ME]], "survivor")
    assert line["place"] == 3 and line["after"] < 1500


def test_egalite_et_places_survivant():
    order = E.order_from_places([("me", 3), ("bot1", None), ("bot2", None), ("bot3", 4)], unplaced_first=True)
    assert order == [["bot1", "bot2"], ["me"], ["bot3"]]
    book = E.EloBook()
    line = book.update([["a#1", "b#1"], [E.ME], ["c#1"]], "survivor")
    assert line["place"] == 3   # deux coureurs à égalité devant


def test_k_provisoire_puis_normal():
    book = E.EloBook(races=E.PROVISIONAL_RACES)
    assert book.k_rider() == E.K_RIDER
    assert E.EloBook().k_rider() == E.K_RIDER_NEW


def test_bornes_de_la_cote_et_des_ecarts():
    book = E.EloBook(rating=E.RATING_BOUNDS[1] - 1)
    for _ in range(30):
        book.update([[E.ME], ["climber#1"], ["rouleur#1"]], "grandprix")
    assert book.rating == E.RATING_BOUNDS[1]
    assert all(abs(v) <= E.OFFSET_MAX for v in book.offsets.values())


def test_classement_refuse_sans_cycliste_ou_en_double():
    book = E.EloBook()
    with pytest.raises(ValueError):
        book.update([["climber#1"], ["rouleur#1"]], "grandprix")
    with pytest.raises(ValueError):
        book.update([[E.ME], [E.ME]], "grandprix")
    with pytest.raises(ValueError):
        book.update([[E.ME]], "grandprix")


def test_fichier_ecrit_relu_et_valeurs_refusees(tmp_path):
    path = E.path_for(tmp_path)
    assert E.load(path).rating == E.START   # fichier absent
    book = E.EloBook()
    book.update([[E.ME], ["climber#1"]], "track", ts=1.0)
    E.save(path, book)
    again = E.load(path)
    assert again.rating == pytest.approx(book.rating, abs=0.01) and again.races == 1
    assert again.history[-1]["mode"] == "track"
    path.write_text(json.dumps({"rating": "x", "races": -2, "offsets": {"a#1": 9999, "b#1": "?"}}))
    bad = E.load(path)
    assert bad.rating == E.START and bad.races == 0 and bad.offsets == {"a#1": E.OFFSET_MAX}
    path.write_text("{abîmé")
    assert E.load(path).rating == E.START


def test_historique_borne():
    book = E.EloBook()
    for _ in range(E.HISTORY_MAX + 5):
        book.update([[E.ME], ["climber#1"]], "grandprix")
    assert len(book.history) == E.HISTORY_MAX


@pytest.mark.parametrize("true_strength", [0.9, 1.0, 1.1])
def test_convergence_simulee_juste_part(true_strength):
    """Un cycliste plus fort (ou plus faible) que sa FTP ne le dit : sa cote rejoint sa force, sa place moyenne
    revient au milieu du peloton, les écarts des bots restent bornés (pas d'emballement)."""
    rnd = random.Random(7)
    book = E.EloBook()
    keys = E.plan_keys(["climber", "rouleur", "sprinter", "diesel"] * 2)[:7]
    places = []
    for race in range(200):
        perf = {E.ME: true_strength * (1 + rnd.gauss(0, 0.02))}
        for k in keys:
            perf[k] = book.factor(k) * (1 + rnd.gauss(0, 0.02))
        line = book.update([[r] for r in sorted(perf, key=lambda r: -perf[r])], "grandprix")
        if race >= 100:
            places.append(line["place"])
    target = E.START + (true_strength - 1.0) * E.POINTS_PER_UNIT
    assert abs(book.rating - target) < 60
    assert 3.5 <= statistics.mean(places) <= 5.5   # milieu d'un peloton de 8
    assert all(abs(v) <= E.OFFSET_MAX for v in book.offsets.values())
