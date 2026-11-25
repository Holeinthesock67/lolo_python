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
    assert msg["season"] is None and msg["history"] == []
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


def test_round_finished_after_midnight_counts_for_its_week(env, short_round):
    """Revue F1-01 : manche partie le dimanche soir, arrivée le lundi : enregistrée pour la semaine du départ."""
    from datetime import timedelta

    make, run, _, tmp_path = env
    s, _, errors = make(7210)
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    assert not errors
    start_day = s._league_run["day"]
    s._league_today = lambda: start_day + timedelta(days=7)   # l'horloge passe au lundi suivant pendant la course
    run(s, 900)
    assert s.state.summary.get("league") is not None
    season = league.load(tmp_path / "ligue.json")
    assert season.results[0].source == "joueur" and season.results[0].day == start_day.isoformat()


def test_arrival_frame_fits_the_datagram(env, short_round):
    """Revue F1-04 : la trame `state` d'arrivée d'une manche (11 rivaux, encart de la ligue) tient sous la limite
    sans rien retirer du bilan ; les lignes de l'encart n'ont que place, nom, points et `me`."""
    from openride_core import ipc_server
    from openride_core.ipc_budget import encode, fit_state, state_limit

    make, run, _, _ = env
    s, _, _ = make(7220)
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    run(s, 900)
    frame = s.state.to_dict()
    assert set(frame["summary"]["league"]["rows"][0]) == {"place", "name", "points", "me"}
    limit = state_limit(ipc_server.CONTRACT_REV)
    assert len(encode(frame)) <= limit, len(encode(frame))   # trame entière, sans allègement
    out, dropped = fit_state(frame, limit)
    assert dropped == [] and out["summary"]["league"] == frame["summary"]["league"]
    from openride_core.ipc_budget import worst_state
    with_devices = {**frame, "devices": worst_state("1.1")["devices"]}   # une trame sur 30 porte les appareils
    print("trame d'arrivée :", len(encode(frame)), "octets ;", len(encode(with_devices)), "avec devices")
    out, dropped = fit_state(with_devices, limit)
    assert "summary" not in dropped and out["summary"]["league"] == frame["summary"]["league"]
    # Bilan le plus lourd du budget (courbe, passages, blocs, test de FTP) plus l'encart : il tient sans perdre
    # le bilan ni l'encart, même avec `devices`.
    from openride_core.ipc_budget import worst_finished_state
    heavy = worst_finished_state()
    heavy["summary"]["league"] = frame["summary"]["league"]
    heavy["devices"] = worst_state("1.1")["devices"]
    print("bilan le plus lourd + encart + devices :", len(encode(heavy)), "octets")
    out, dropped = fit_state(heavy, limit)
    assert "summary" not in dropped and out["summary"]["league"] == frame["summary"]["league"], dropped


def test_new_season_keeps_the_closed_one_aside(env):
    """Revue F1-07 : `league_new` après une saison close garde l'ancienne à part (classement et trophée)."""
    make, _, _, tmp_path = env
    s, sent, errors = make(7230)
    s._on_command("league_new", {}, 2)
    season = league.load(tmp_path / "ligue.json")
    season.closed = "fin"
    league.save(tmp_path / "ligue.json", season)
    s._on_command("league_new", {}, 3)
    assert not errors and _status(sent)["season"]["number"] == 2
    old = league.load(tmp_path / "ligue_saison_1.json")
    assert old is not None and old.number == 1 and old.closed == "fin"
    msg = _status(sent)   # lot CH6 : palmarès dans la réponse
    validator("league").validate(msg)
    assert [r["number"] for r in msg["history"]] == [1] and msg["history"][0]["of"] == 12


def test_hill_finish_round_refuses_a_loop(env, monkeypatch):
    """Revue F1-05 : la manche « arrivée en côte » ne se court pas sur une boucle."""
    from datetime import timedelta

    make, _, _, tmp_path = env
    s, _, errors = make(7240)
    s._on_command("league_new", {}, 2)
    monkeypatch.setattr(league, "PLAYABLE_MODES", ("race", "survivor", "grandprix", "track"))
    start = league.load(tmp_path / "ligue.json").start
    s._league_today = lambda: start + timedelta(weeks=4, days=1)   # semaine 5 ; semaines 2 à 4 jouables (simulées)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    assert errors and "parcours en ligne" in errors[-1][1]


# --- lot CH3b : les autres modes du calendrier --------------------------------------------------


def _week(s, tmp_path, k):
    from datetime import timedelta

    start = league.load(tmp_path / "ligue.json").start
    s._league_today = lambda: start + timedelta(weeks=k, days=1)   # semaine k + 1 (les précédentes simulées)


def _finish_round(s, run, tmp_path, errors, index, mode, seconds, until=None):
    assert not errors, errors
    assert s.state.session_state == "RUNNING" and len(s.bots) == 11
    season = league.load(tmp_path / "ligue.json")
    assert [b.name for b in s.bots] == [r.short for r in season.rivals]
    if until is None:
        run(s, seconds)
    else:
        for _ in range(int(seconds // 10)):
            if until(s) or s.state.session_state != "RUNNING":
                break
            run(s, 10)
    if s.state.session_state == "RUNNING":   # après l'arrivée on roule encore : bilan demandé (RT1, RT2)
        s._on_command("end_session", {"save": True}, 90)
    assert s.state.session_state == "FINISHED" and not errors, (s.state.session_state, errors)
    validator("state").validate(s.state.to_dict())
    box = s.state.summary["league"]
    assert box["round"] == index + 1 and box["of"] == 12 and box["points"] == league.points_for(box["place"])
    season = league.load(tmp_path / "ligue.json")
    res = season.results[index]
    assert res.source == "joueur" and set(res.places) == set(season.racers())
    assert sorted(res.places.values())[0] == 1 and s.state.summary["elo"]["mode"] == "league"
    journal = next((tmp_path / "journal").glob("*.jsonl"))
    lines = [json.loads(x) for x in journal.read_text("utf-8").splitlines()]
    assert any(x.get("kind") == "league_start" and x.get("mode") == mode for x in lines)
    return box


def test_survivor_round_eleven_arches(env):
    make, run, _, tmp_path = env
    s, sent, errors = make(7300)
    s._on_command("league_new", {}, 2)
    _week(s, tmp_path, 1)
    s._on_command("league_status", {}, 3)
    rnd = _status(sent)["season"]["round"]
    assert rnd["mode"] == "survivor" and rnd["playable"]
    s.cfg.survivor.opponents = 4   # réglage du mode ignoré : la ligue engage ses 11 rivaux
    s._on_command("start", {"mode": "survivor", "league": True}, 4)
    assert s.survivor is not None and len(s.survivor.arches) == 11
    _finish_round(s, run, tmp_path, errors, 1, "survivor", 4000,
                  until=lambda x: x.survivor.racers["me"].place is not None)
    assert s.state.summary["league"]["of"] == 12


def test_grandprix_round_keeps_objects_and_league_laps(env, short_round):
    make, run, _, tmp_path = env
    s, _, errors = make(7310, laps=5)
    s._on_command("league_new", {}, 2)
    _week(s, tmp_path, 2)
    s._on_command("start", {"mode": "grandprix", "league": True}, 3)
    assert s.grandprix is not None and s.grandprix.mode == "grandprix"
    assert s.grandprix.length_m == pytest.approx(1500.0)   # 1 tour de ligue (cible courte), pas les 5 du réglage
    _finish_round(s, run, tmp_path, errors, 2, "grandprix", 900)


def test_track_round_is_an_elimination_on_the_velodrome(env):
    from openride_core import velodrome

    make, run, _, tmp_path = env
    velodrome.write_velodrome(tmp_path / "routes")
    s, _, errors = make(7320)
    s._on_command("league_new", {}, 2)
    _week(s, tmp_path, 3)
    s._on_command("start", {"mode": "track", "league": True}, 3)   # sur l'anneau : refusé
    assert errors and "vélodrome" in errors[-1][1]
    errors.clear()
    s2, _, errors2 = make(7330, route_id=velodrome.TRACK_ID)
    _week(s2, tmp_path, 3)
    s2._on_command("start", {"mode": "track", "league": True}, 2)
    assert s2.track_event is not None and s2.track_event.event_id == "elimination"
    _finish_round(s2, run, tmp_path, errors2, 3, "track", 7200,
                  until=lambda x: x.track_event.riders["me"].out is not None or x.track_event.finished)


def test_road_round_allowed_on_a_velodrome_loop(env, short_round):
    """Une manche de route reste permise sur une piste (boucle d'essai du Grand Prix du banc des menus : copie du
    vélodrome) ; seule l'élimination exige le vélodrome."""
    from openride_core import velodrome

    make, _, _, tmp_path = env
    velodrome.write_velodrome(tmp_path / "routes")
    s, _, errors = make(7340, route_id=velodrome.TRACK_ID)
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    assert not errors and s.state.session_state == "RUNNING"


def test_missed_weeks_are_now_simulated(env):
    """CH3b : tous les modes du calendrier sont jouables, une semaine manquée est simulée (plus neutralisée)."""
    make, _, _, tmp_path = env
    s, sent, _ = make(7350)
    s._on_command("league_new", {}, 2)
    _week(s, tmp_path, 4)
    s._on_command("league_status", {}, 3)
    season = league.load(tmp_path / "ligue.json")
    assert [season.results[i].source for i in range(4)] == ["simule"] * 4


def test_round_cut_by_mode_error_stays_open(env, short_round):
    """Filet de la boucle (lot FB1) : une erreur du mode pendant la manche termine la séance avec son bilan, sans
    arrivée ; aucun résultat n'est écrit et la manche se recourt dans la semaine."""
    from openride_core.session import MODE_FAILED_SAVED

    make, run, _, tmp_path = env
    s, _, errors = make(7370)
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    run(s, 20)

    def boom(*_a, **_k):
        raise RuntimeError("panne du mode")

    s.grandprix.step = boom
    s._safe_step(0.02, 1.0)
    assert s.state.session_state == "FINISHED" and s.state.summary["mode_error"]["mode"] == "grandprix"
    assert "league" not in s.state.summary and errors[-1] == ("mode_failed", MODE_FAILED_SAVED)
    assert league.load(tmp_path / "ligue.json").results == {}
    s2, sent2, errors2 = make(7380)
    s2._on_command("league_status", {}, 2)
    assert _status(sent2)["season"]["round"]["playable"]
