"""Ligue d'hiver, cœur de la saison (série CH, lot CH1) : calendrier, barème, 6 meilleurs, classique, pause."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta

import pytest

from openride_core import bots, league
from openride_core.league import ME, LeagueError

MON = date(2026, 11, 23)          # un lundi


def _season(seed: int = 7) -> league.Season:
    return league.new_season(MON + timedelta(days=2), seed=seed)


def _places(season: league.Season, me: int | None) -> dict[str, int]:
    """Classement complet : le cycliste à la place `me`, les rivaux dans l'ordre du plateau autour."""
    keys = [r.key for r in season.rivals]
    out: dict[str, int] = {}
    order = keys[:]
    if me is not None:
        order.insert(me - 1, ME)
    for n, k in enumerate(order, 1):
        out[k] = n
    return out


def _week(i: int, day: int = 2) -> date:
    return MON + timedelta(weeks=i, days=day)


def test_new_season_field_and_calendar():
    s = _season()
    assert s.start == MON and s.number == 1
    assert [r.key for r in s.rivals] == league.field_keys()
    assert len(s.rivals) == 11 and len(s.racers()) == league.RIDERS
    counts = {p: league.field_profiles(s).count(p) for p in set(league.field_profiles(s))}
    assert counts == {"climber": 3, "rouleur": 3, "sprinter": 3, "diesel": 2}
    assert all(p in bots.PROFILES for p in counts)
    assert len({r.name for r in s.rivals}) == 11 and len({r.team for r in s.rivals}) == 11
    assert all(r.team.startswith("Équipe ") and r.color.startswith("#") for r in s.rivals)
    assert len(league.ROUNDS) == league.WEEKS
    assert "rogue" not in {r.mode for r in league.ROUNDS}
    assert [r.mode for r in league.ROUNDS][:4] == ["race", "survivor", "grandprix", "track"]
    assert league.ROUNDS[3].event == "elimination"
    # Tirage reproductible par la graine.
    assert [r.name for r in _season(7).rivals] == [r.name for r in s.rivals]


def test_points_scale():
    assert [league.points_for(p) for p in range(1, 13)] == [25, 20, 16, 13, 11, 10, 9, 8, 7, 6, 5, 4]
    assert league.points_for(None) == 0 and league.points_for(13) == 0 and league.points_for(0) == 0


def test_record_once_and_only_this_week():
    s = _season()
    assert s.current_round(_week(0)) == 0
    s.record(0, _places(s, 4), _week(0))
    assert s.current_round(_week(0, 5)) is None
    with pytest.raises(LeagueError, match="premier résultat"):
        s.record(0, _places(s, 1), _week(0, 6))
    with pytest.raises(LeagueError, match="pas celle de la semaine"):
        s.record(1, _places(s, 1), _week(0))
    with pytest.raises(LeagueError, match="incomplet"):
        s.record(1, {ME: 1}, _week(1))
    bad = _places(s, 1)
    bad[ME] = 13
    with pytest.raises(LeagueError, match="place refusée"):
        s.record(1, bad, _week(1))
    assert s.results[0].places[ME] == 4 and s.results[0].source == "joueur"


def test_missed_weeks_simulated_for_rivals_and_six_best():
    s = _season()
    for i in range(6):
        s.record(i, _places(s, 2), _week(i))
    # Semaines 7 et 8 sautées : jokers, simulées pour les rivaux.
    done = s.advance(_week(8, 0))
    assert done == [6, 7, league.WEEKS] and s.closed == "fin"
    assert ME not in s.results[6].places and s.results[6].source == "simule"
    assert sorted(s.results[6].places.values()) == list(range(1, 12))
    me = next(r for r in s.standings() if r["id"] == ME)
    assert me["rounds"] == [20] * 6 + [0, 0]
    assert me["points"] == 120 and me["ran"] == 6
    assert s.rider_rounds() == 6


def test_best_six_drop_worst():
    s = _season()
    worst = [12, 11, 1, 1, 1, 1, 1, 1]
    for i, p in enumerate(worst):
        s.record(i, _places(s, p), _week(i))
    me = next(r for r in s.standings() if r["id"] == ME)
    assert me["points"] == 6 * 25 and me["wins"] == 6


def test_classic_bonus_and_dates():
    s = _season()
    days = s.classic_days(_week(0))
    assert days and all(d.weekday() >= 5 for d in days)
    assert days[-1] == MON + timedelta(weeks=7, days=6)
    with pytest.raises(LeagueError, match="jour refusé"):
        s.choose_classic(_week(2, 2), _week(0))          # un mercredi
    s.choose_classic(_week(3, 5), _week(0))
    assert not s.classic_open(_week(3, 4))
    assert s.classic_open(_week(3, 5)) and s.classic_open(_week(5, 1))
    s.record_classic(_places(s, 1), _week(3, 6))
    assert not s.classic_open(_week(4, 5))
    me = next(r for r in s.standings() if r["id"] == ME)
    assert me["classic"] == 37.5 and me["points"] == 37.5
    with pytest.raises(LeagueError, match="déjà courue"):
        s.choose_classic(_week(5, 5), _week(4))


def test_classic_not_run_is_simulated_at_end():
    s = _season()
    s.choose_classic(_week(2, 6), _week(0))
    s.advance(_week(8))
    assert s.classic is not None and s.classic.source == "simule" and ME not in s.classic.places
    winner = next(k for k, v in s.classic.places.items() if v == 1)
    row = next(r for r in s.standings() if r["id"] == winner)
    assert row["classic"] == 37.5


def test_tie_break_order():
    s = _season()
    s.results[0] = league.RoundResult(_places(s, None), "simule")
    s.results[7] = league.RoundResult(_places(s, None), "simule")
    # Rivaux 1 et 2 : swap pour égalité de points (25+20 chacun), pas d'égalité de victoires… on force l'égalité.
    k1, k2 = s.rivals[0].key, s.rivals[1].key
    s.results[7].places[k1], s.results[7].places[k2] = 2, 1
    rows = s.standings()
    assert {rows[0]["id"], rows[1]["id"]} == {k1, k2}
    assert rows[0]["points"] == rows[1]["points"] == 45 and rows[0]["wins"] == rows[1]["wins"] == 1
    # Égalité de victoires : la meilleure place à la finale passe devant.
    assert rows[0]["id"] == k2


def test_pause_freezes_and_long_pause_closes():
    s = _season()
    s.record(0, _places(s, 3), _week(0))
    s.pause(_week(1, 1))
    assert s.current_round(_week(2)) is None
    assert s.week_index(_week(3)) == 1
    s.advance(_week(3))
    assert 1 not in s.results
    s.resume(_week(3, 2))
    # Deux semaines gelées : la manche 2 se court en semaine 4 du calendrier réel.
    assert s.week_index(_week(3, 3)) == 1 and s.current_round(_week(3, 3)) == 1
    assert s.end_day(_week(3, 3)) == MON + timedelta(weeks=9, days=6)
    s.record(1, _places(s, 1), _week(3, 4))
    # Pause trop longue : close au classement du moment, sans trophée.
    s.pause(_week(4))
    s.advance(_week(6))
    assert s.closed is None
    s.advance(_week(7))
    assert s.closed == "pause" and s.trophy() is None
    with pytest.raises(LeagueError):
        s.record(2, _places(s, 1), _week(7))


def test_trophies():
    gold = _season()
    for i in range(league.WEEKS):
        gold.record(i, _places(gold, 1), _week(i))
    assert gold.trophy() is None            # pas finie
    gold.advance(_week(8))
    assert gold.trophy() == ("or", "Trophée d'or")
    reg = _season()
    for i in range(6):
        reg.record(i, _places(reg, 12), _week(i))
    reg.advance(_week(8))
    assert reg.place_of() > 3 and reg.trophy() == ("regularite", "Trophée de régularité")
    none = _season()
    for i in range(5):
        none.record(i, _places(none, 12), _week(i))
    none.advance(_week(8))
    assert none.trophy() is None


def test_home_line():
    s = _season()
    assert s.home_line(_week(0)).endswith("manche 1/8 : Course en tours, à courir cette semaine")
    s.record(0, _places(s, 1), _week(0))
    assert s.home_line(_week(0)) == "1er · manche 1/8 faite · prochaine lundi"
    s.advance(_week(2))
    assert "manche 3/8 : Grand Prix, à courir cette semaine" in s.home_line(_week(2))
    s.pause(_week(2))
    assert "saison en pause" in s.home_line(_week(2))
    s.resume(_week(2))
    s.advance(_week(8))
    assert s.home_line(_week(8)).startswith("Saison finie · ")


def test_new_season_keeps_eight():
    s = _season()
    nxt = league.new_season(_week(8), seed=99, previous=s)
    assert nxt.number == 2 and nxt.start == MON + timedelta(weeks=8)
    assert [r.key for r in nxt.rivals] == league.field_keys()
    kept = {r.name for r in s.rivals} & {r.name for r in nxt.rivals}
    assert len(kept) == league.KEEP_RIVALS
    assert len({r.name for r in nxt.rivals}) == 11 and len({r.team for r in nxt.rivals}) == 11
    for old, new in zip(s.rivals, nxt.rivals):
        assert old.profile == new.profile


def test_easy_flag_kept():
    s = _season()
    s.record(0, _places(s, 5), _week(0), easy=True)
    back = league.Season.from_dict(json.loads(json.dumps(s.to_dict())))
    assert back.results[0].easy is True


def test_round_trip_and_safe_files(tmp_path):
    s = _season()
    s.record(0, _places(s, 4), _week(0))
    s.choose_classic(_week(5, 5), _week(0))
    s.pause(_week(1))
    s.resume(_week(1, 3))
    path = league.path_for(tmp_path)
    league.save(path, s)
    back = league.load(path)
    assert back is not None and back.to_dict() == s.to_dict()
    assert not path.with_name(path.name + ".tmp").exists()
    assert league.load(tmp_path / "absent.json") is None
    path.write_text("{abîmé", encoding="utf-8")
    assert league.load(path) is None
    assert not path.exists() and path.with_name("ligue.json.abime").exists()


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(version=99),
    lambda d: d["rivals"].pop(),
    lambda d: d.update(closed="peut-etre"),
    lambda d: d["results"].update({"9": d["results"]["0"]}),
    lambda d: d["results"]["0"].update(source="triche"),
    lambda d: d["results"]["0"]["places"].update(me=40),
])
def test_from_dict_refuses(mutate):
    s = _season()
    s.record(0, _places(s, 4), _week(0))
    d = json.loads(json.dumps(s.to_dict()))
    mutate(d)
    with pytest.raises(LeagueError):
        league.Season.from_dict(d)


def test_simulation_follows_ratings_and_terrain():
    s = _season()
    strong = s.rivals[0].key
    wins = 0
    for seed in range(200):
        s.seed = seed
        order = league.simulate_order(s, league.ROUNDS[0], 0, ratings={strong: 1900.0})
        wins += order[strong] == 1
    assert wins > 70           # environ la moitié : 10 contre 1 face à chacun
    # Arrivée en côte : les grimpeurs devant les sprinteurs en moyenne.
    climb = {"climber": [], "sprinter": []}
    for seed in range(200):
        s.seed = seed
        order = league.simulate_order(s, league.ROUNDS[4], 4)
        for r in s.rivals:
            if r.profile in climb:
                climb[r.profile].append(order[r.key])
    mean = {k: sum(v) / len(v) for k, v in climb.items()}
    assert mean["climber"] < mean["sprinter"]
    # Reproductible.
    s.seed = 3
    assert league.simulate_order(s, league.ROUNDS[2], 2) == league.simulate_order(s, league.ROUNDS[2], 2)


def test_simulated_seasons_rider_fair_share():
    """Saisons entières simulées : un cycliste de même force que le plateau gagne sa part (~1/12), jamais de
    saison incohérente (totaux, places, trophée)."""
    wins = races = 0
    rng = random.Random(1)
    for n in range(60):
        s = league.new_season(MON, seed=n)
        for i in range(league.WEEKS):
            if rng.random() < 0.8:
                order = league.simulate_order(s, league.ROUNDS[i], i, extra={ME: league.START_RATING})
                s.record(i, order, _week(i))
                wins += order[ME] == 1
                races += 1
        s.advance(_week(8))
        rows = s.standings()
        assert [r["place"] for r in rows] == list(range(1, 13))
        assert all(r["points"] <= 6 * 25 + 37.5 for r in rows)
        assert s.closed == "fin" and len(s.results) == league.WEEKS
        if s.trophy() is None:
            assert s.place_of() > 3 and s.rider_rounds() < 6
    assert 0.04 < wins / races < 0.14


def test_seen_day_never_goes_back():
    from datetime import date

    s = league.new_season(date(2026, 11, 28), seed=3)
    assert s.seen(date(2026, 12, 2)) == date(2026, 12, 2)
    assert s.seen(date(2026, 11, 30)) == date(2026, 12, 2)   # horloge reculée : le jour vu est gardé
    assert league.Season.from_dict(s.to_dict()).last_seen == date(2026, 12, 2)
    old = s.to_dict()
    old.pop("last_seen")
    assert league.Season.from_dict(old).last_seen is None   # fichier d'avant : lu sans le champ
