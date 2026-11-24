"""Ligue d'hiver, calibrage à 10 % de victoire (série CH, lot CH2) et banc des saisons simulées."""

from __future__ import annotations

import json
from datetime import date

import pytest

from openride_core import bot_elo, league
from openride_core.league import ME, LeagueError
from openride_core.tools import ligue_campagne

MON = date(2026, 11, 23)


def test_round_ratings_give_target_for_every_round():
    s = league.new_season(MON, seed=5)
    for rating in (1100.0, 1500.0, 2000.0):
        for rnd in league.ROUNDS + (league.CLASSIC,):
            cotes = league.round_ratings(s, rnd, rating, {"climber#1": 80.0})
            assert set(cotes) == set(league.field_keys())
            assert league.win_probability(rating, cotes.values()) == pytest.approx(league.TARGET_WIN)
    # Étalement : le haut du plateau plus fort que le cycliste, le bas plus faible.
    cotes = league.round_ratings(s, league.ROUNDS[2], 1500.0)
    assert max(cotes.values()) > 1500.0 > min(cotes.values())
    assert max(cotes.values()) - min(cotes.values()) == pytest.approx(league.SPREAD_WIDTH)


def test_terrain_favours_the_right_profile():
    s = league.new_season(MON, seed=5)
    cotes = league.round_ratings(s, league.ROUNDS[4], 1500.0)      # arrivée en côte
    sp = league.spread(s)
    climber = [cotes[k] - sp[k] for k in cotes if k.startswith("climber")]
    sprinter = [cotes[k] - sp[k] for k in cotes if k.startswith("sprinter")]
    assert min(climber) > max(sprinter)


def test_spread_fixed_by_season_seed():
    a, b = league.new_season(MON, seed=5), league.new_season(MON, seed=5)
    assert league.spread(a) == league.spread(b)
    assert league.spread(a) != league.spread(league.new_season(MON, seed=6))


def test_level_factors_follow_elo_scale():
    f = league.level_factors({"climber#1": 1600.0, "diesel#2": 1500.0})
    assert f["climber#1"] == pytest.approx(bot_elo.level_factor(1600.0))
    assert f["diesel#2"] == pytest.approx(1.0)


def test_rider_update_against_round_ratings():
    s = league.new_season(MON, seed=5)
    book = bot_elo.EloBook()
    cotes = league.round_ratings(s, league.ROUNDS[0], book.rating, book.offsets)
    win = {ME: 1, **{k: n for n, k in enumerate(cotes, 2)}}
    line = league.rider_update(book, win, cotes, ts=12.0)
    # Gagner face à 10 % de chances : la cote monte nettement (K des courses de rodage).
    assert line["mode"] == "league" and line["place"] == 1 and line["of"] == 12 and line["delta"] > 10
    assert book.races == 1 and book.history[-1] == line
    assert abs(sum(book.offsets.values())) < 1.0
    assert all(abs(v) <= bot_elo.OFFSET_MAX for v in book.offsets.values())
    book2 = bot_elo.EloBook()
    last = {ME: 12, **{k: n for n, k in enumerate(cotes, 1)}}
    assert league.rider_update(book2, last, cotes)["delta"] < 0
    with pytest.raises(LeagueError):
        league.rider_update(book2, {ME: 1}, cotes)


def test_bench_passes_and_json(capsys):
    assert ligue_campagne.main(["--saisons", "60", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["errors"] == [] and len(out["results"]) == 3
    for r in out["results"]:
        assert 0.06 <= r["win_rate"] <= 0.14


def test_bench_detects_wrong_target(monkeypatch, capsys):
    monkeypatch.setattr(league, "TARGET_WIN", 0.30)
    monkeypatch.setattr(league.round_ratings, "__defaults__", (None, 0.30))
    assert ligue_campagne.main(["--saisons", "40"]) == 1
    assert "ÉCHEC" in capsys.readouterr().out


def test_bench_invalid_call():
    assert ligue_campagne.main(["--saisons", "2", "--rodage", "3"]) == 2
    assert ligue_campagne.main(["--forces", "abc"]) == 2
