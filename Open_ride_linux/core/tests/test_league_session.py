"""Ligue d'hiver dans la séance (série CH, lot CH3, révision 1.30) : saison créée, manche de la semaine courue en
mode Course contre les 11 rivaux, résultat dans `ligue.json`, cote tenue, encart du bilan, refus."""

import json

import pytest

from openride_core import bot_elo, league, rivals
from openride_core.bots import ProfileBot

from test_grandprix_session import env, validator  # noqa: F401  (fixture partagée)


@pytest.fixture
def short_round(monkeypatch):
    monkeypatch.setattr(league, "RACE_TARGET_S", 120.0)   # une manche d'un tour sur l'anneau de 1,5 km


def _status(sent):
    return [m for m in sent if m.get("type") == "league"][-1]


def test_status_without_season_then_new_season(env):
    make, _, _, tmp_path = env
    s, sent, errors = make(7100)
    s._on_command("league_status", {}, 2)
    msg = _status(sent)
    validator("league").validate(msg)
    assert msg["season"] is None
    s._on_command("league_new", {}, 3)
    msg = _status(sent)
    validator("league").validate(msg)
    season = msg["season"]
    assert season["number"] == 1 and season["week"] == 1 and season["round"]["mode"] == "race"
    assert season["round"]["playable"] and not season["round"]["done"]
    assert len(season["standings"]) == 12 and sum(r["me"] for r in season["standings"]) == 1
    assert "à courir cette semaine" in season["home_line"]
    assert (tmp_path / "ligue.json").is_file()
    s._on_command("league_new", {}, 4)
    assert errors and "déjà en cours" in errors[-1][1]


def test_round_raced_recorded_once_with_bilan(env, short_round):
    make, run, _, tmp_path = env
    s, sent, errors = make(7110)
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    assert not errors and s.state.session_state == "RUNNING"
    assert len(s.bots) == 11 and all(isinstance(b, ProfileBot) for b in s.bots)
    season = league.load(tmp_path / "ligue.json")
    assert [b.name for b in s.bots] == [r.short for r in season.rivals]
    roster = rivals.load(tmp_path / rivals.FILE_NAME)   # mêmes rivaux que les autres modes (lot R4)
    assert all(roster.get(r.key).name == r.name for r in season.rivals)
    assert [b.profile for b in s.bots] == league.field_profiles(season)
    assert s.grandprix.mode == "race" and s.grandprix.lap_m == pytest.approx(1500.0)
    assert s.grandprix.length_m == pytest.approx(1500.0)
    run(s, 900)
    assert s.state.session_state == "FINISHED" and not errors
    summary = s.state.summary
    validator("state").validate(s.state.to_dict())
    box = summary["league"]
    assert box["round"] == 1 and box["of_rounds"] == 8 and box["of"] == 12
    assert box["points"] == league.points_for(box["place"]) and len(box["rows"]) == 5
    assert any(r["me"] for r in box["rows"])
    assert summary["elo"]["mode"] == "league" and summary["elo"]["of"] == 12
    season = league.load(tmp_path / "ligue.json")
    assert season.results[0].source == "joueur" and season.results[0].places[league.ME] == box["place"]
    book = bot_elo.load(tmp_path / bot_elo.FILE_NAME)
    assert book.races == 1 and book.history[-1]["mode"] == "league"
    journal = next((tmp_path / "journal").glob("*.jsonl"))
    kinds = [json.loads(x).get("kind") for x in journal.read_text("utf-8").splitlines()]
    assert "league_start" in kinds and "league_round" in kinds
    # Une seule tentative : la manche faite, la suivante n'ouvre que lundi.
    s2, sent2, errors2 = make(7120)
    s2._on_command("start", {"mode": "race", "league": True}, 2)
    assert errors2 and "pas de manche" in errors2[-1][1]
    s2._on_command("league_status", {}, 3)
    st = _status(sent2)["season"]
    assert st["round"]["done"] and "faite" in st["home_line"]


def test_abandoned_round_not_counted(env, short_round):
    make, run, _, tmp_path = env
    s, _, errors = make(7130)
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    run(s, 20)
    s._on_command("end_session", {"save": True}, 4)
    assert s.state.summary is not None and "league" not in s.state.summary
    assert league.load(tmp_path / "ligue.json").results == {}
    s2, _, errors2 = make(7140)
    s2._on_command("start", {"mode": "race", "league": True}, 2)
    assert not errors2 and s2.state.session_state == "RUNNING"


def test_refusals(env):
    make, _, _, tmp_path = env
    s, _, errors = make(7150)
    s._on_command("start", {"mode": "race", "league": True}, 2)
    assert errors and "pas de manche" in errors[-1][1]
    s._on_command("league_new", {}, 3)
    s._on_command("start", {"mode": "grandprix", "league": True}, 4)
    assert "se court en mode race" in errors[-1][1]
    s._on_command("start", {"mode": "race", "league": True, "bots": []}, 5)
    assert "compose elle-même" in errors[-1][1]
    line, _, errl = make(7160, route_id="demo")
    line._on_command("start", {"mode": "race", "league": True}, 2)
    assert errl and "boucle" in errl[-1][1]
    assert s.state.session_state == "READY"


def test_easy_intensity_marked(env, short_round):
    make, run, _, tmp_path = env
    s, _, errors = make(7170, objective="endurance")
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    run(s, 900)
    assert s.state.summary["league"]["easy"] is True
    assert league.load(tmp_path / "ligue.json").results[0].easy is True


def test_round_cut_by_core_crash_stays_open(env, short_round):
    """Plantage du core pendant la manche (audit L10) : la reprise ne restaure pas les courses, aucun résultat n'est
    écrit ; la manche compte comme abandonnée et se recourt dans la semaine."""
    make, run, _, tmp_path = env
    s, _, _ = make(7180)
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    run(s, 20)   # le core « tombe » ici : ni fin de séance, ni arrivée
    assert league.load(tmp_path / "ligue.json").results == {}
    s2, sent2, errors2 = make(7190)
    s2._on_command("league_status", {}, 2)
    assert _status(sent2)["season"]["round"]["playable"]
    s2._on_command("start", {"mode": "race", "league": True}, 3)
    assert not errors2 and s2.state.session_state == "RUNNING"


def test_clock_going_back_keeps_last_seen_day(env):
    """Horloge du PC qui recule (audit L11) : la ligue garde le dernier jour vu et ne revient pas en arrière."""
    from datetime import date, timedelta

    make, _, _, tmp_path = env
    s, sent, _ = make(7200)
    s._on_command("league_new", {}, 2)
    season = league.load(tmp_path / "ligue.json")
    ahead = date.today() + timedelta(days=8)   # jour vu plus tard que l'horloge actuelle
    season.last_seen = ahead
    league.save(tmp_path / "ligue.json", season)
    s._on_command("league_status", {}, 3)
    assert _status(sent)["season"]["week"] == season.week_index(ahead) + 1 >= 2
    assert league.load(tmp_path / "ligue.json").last_seen == ahead
