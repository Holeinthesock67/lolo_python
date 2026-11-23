"""Reprise d'une course après un plantage du core (lot RC1, audit du 22 novembre, L10 et M2) : instantané
`race_snapshot` au journal, plateau recomposé, classement, réserves, arrivées, objets et éliminations repris ;
refus propre (autre version du jeu) ; manche de la ligue reprise et comptée à l'arrivée."""

import json

import pytest

from openride_core import league, race_resume
from openride_core.journal import read_journal

from test_grandprix_session import env, validator  # noqa: F401  (fixture partagée)


def _journal(tmp_path):
    return sorted((tmp_path / "journal").glob("*.jsonl"))[-1]


def _snapshots(tmp_path):
    return [ln for ln in read_journal(_journal(tmp_path)) if ln.get("kind") == "race_snapshot"]


def _crash_and_resume(make, tmp_path, port):
    """Le core « tombe » (rien n'est fermé) ; un nouveau core reprend le journal, comme le lanceur (lot N8)."""
    s2, sent2, errors2 = make(port)
    s2.resume_session(_journal(tmp_path))
    return s2, sent2, errors2


def test_snapshots_every_five_seconds_and_at_pause(env):
    make, run, _, tmp_path = env
    s, _, errors = make(7400)
    s._on_command("start", {"mode": "race"}, 2)
    run(s, 21)
    snaps = _snapshots(tmp_path)
    assert [round(x["t"]) for x in snaps] == [5, 10, 15, 20]
    s._on_command("pause", {}, 3)
    snaps = _snapshots(tmp_path)
    assert len(snaps) == 5 and snaps[-1]["t"] == pytest.approx(s._t_session, abs=0.05)
    last = snaps[-1]
    assert last["format"] == race_resume.FORMAT and last["mode"] == "race" and len(last["bots"]) == len(s.bots)
    assert len(json.dumps(last)) < 8000   # quelques Ko par instantané
    assert not errors


def test_course_resumed_with_places_reserves_and_laps(env):
    make, run, _, tmp_path = env
    s, _, _ = make(7410)
    s._on_command("start", {"mode": "race"}, 2)
    run(s, 200)
    snap = _snapshots(tmp_path)[-1]
    place = s.grandprix.place("me")
    bots = {b.id: b for b in s.bots}
    s2, _, errors2 = _crash_and_resume(make, tmp_path, 7420)
    assert not errors2
    assert s2.state.session_state == "PAUSED" and s2.state.pause_reason == "core_restarted"
    gp = s2.grandprix
    assert gp is not None and gp.mode == "race" and s2.race is not None   # Course : mode classique gardé
    assert [b.id for b in s2.bots] == list(bots)
    for b in s2.bots:
        old = bots[b.id]
        assert b.s == pytest.approx(old.s, abs=old.v * 5 + 1.0)        # au plus 5 s d'estimation
        assert b.v == 0.0                                                # tout le monde repart arrêté
        assert b.wbal.w_bal_j == pytest.approx(min(d["w_bal_j"] for d in snap["bots"] if d["id"] == b.id), abs=1.0)
        assert b.scale == pytest.approx(old.scale)
        assert b.tactics.form == pytest.approx(old.tactics.form)
    assert gp.origin_m == pytest.approx(s.grandprix.origin_m)
    assert gp.length_m == pytest.approx(s.grandprix.length_m)
    assert abs(gp.place("me") - place) <= 1
    s2._on_command("resume", {}, 3)
    assert s2.state.session_state == "RUNNING"
    run(s2, 900)
    assert s2.state.session_state == "FINISHED"
    assert s2.state.summary["gp"]["mode"] == "race"
    validator("state").validate(s2.state.to_dict())


def test_grandprix_keeps_items_and_taken_boxes(env):
    make, run, _, tmp_path = env
    s, _, _ = make(7430)
    s._on_command("start", {"mode": "grandprix"}, 2)
    run(s, 150)
    s._on_command("pause", {}, 3)
    gp = s.grandprix
    held = {r.id: (r.held, r.charges) for r in gp.racers.values()}
    taken = dict(gp.boxes.taken)
    counts = {r.id: (dict(r.launched), dict(r.received)) for r in gp.racers.values()}
    finished = {r.id: r.finished for r in gp.racers.values()}
    s2, _, errors2 = _crash_and_resume(make, tmp_path, 7440)
    gp2 = s2.grandprix
    assert not errors2 and gp2 is not None and gp2.mode == "grandprix"
    assert {r.id: (r.held, r.charges) for r in gp2.racers.values()} == held
    assert gp2.boxes.taken == pytest.approx(taken)
    assert {r.id: (dict(r.launched), dict(r.received)) for r in gp2.racers.values()} == counts
    assert {r.id: r.finished for r in gp2.racers.values()} == finished
    assert gp2.boxes.rows == pytest.approx(gp.boxes.rows)
    assert len(gp2.objects) == 0 and all(not r.fx for r in gp2.racers.values())   # rien en vol à la reprise
    s2._on_command("resume", {}, 4)
    run(s2, 900)
    assert s2.state.session_state == "FINISHED"


def test_survivor_keeps_eliminations(env):
    make, run, _, tmp_path = env
    s, _, _ = make(7450)
    s.cfg.survivor.opponents, s.cfg.survivor.spacing_km = 3, 1
    s._on_command("start", {"mode": "survivor"}, 2)
    sv = s.survivor
    assert sv is not None
    for _ in range(200):
        run(s, 5)
        if sv.arch >= 1 or s.state.session_state != "RUNNING":
            break
    assert sv.arch >= 1, "aucune élimination"
    run(s, 15)   # bot éliminé rangé puis retiré (10 s)
    s._on_command("pause", {}, 3)
    out = {r.id: (r.out_arch, r.place) for r in sv.racers.values()}
    ids = [b.id for b in s.bots]
    s2, _, errors2 = _crash_and_resume(make, tmp_path, 7460)
    sv2 = s2.survivor
    assert not errors2 and sv2 is not None
    assert sv2.arch == sv.arch and sv2.arches == pytest.approx(sv.arches)
    assert {r.id: (r.out_arch, r.place) for r in sv2.racers.values()} == out
    assert [b.id for b in s2.bots] == ids
    s2._on_command("resume", {}, 4)
    run(s2, 30)
    assert s2.survivor is not None or s2.state.session_state == "FINISHED"


def test_other_game_version_refused_race_dropped(env, monkeypatch, caplog):
    make, run, _, tmp_path = env
    s, _, _ = make(7470)
    s._on_command("start", {"mode": "race"}, 2)
    run(s, 30)
    monkeypatch.setattr("openride_core.session.__version__", "99.0.0")
    s2, _, _ = _crash_and_resume(make, tmp_path, 7480)
    assert s2.state.session_state == "PAUSED" and s2.grandprix is None and s2.bots == []
    assert "Course non reprise" in caplog.text and "version" in caplog.text


def test_cut_before_first_snapshot_resumes_without_race(env):
    make, run, _, tmp_path = env
    s, _, _ = make(7490)
    s._on_command("start", {"mode": "race"}, 2)
    run(s, 3)
    s2, _, _ = _crash_and_resume(make, tmp_path, 7500)
    assert s2.state.session_state == "PAUSED" and s2.grandprix is None


@pytest.fixture
def short_round(monkeypatch):
    monkeypatch.setattr(league, "RACE_TARGET_S", 120.0)   # une manche d'un tour sur l'anneau de 1,5 km


def test_league_round_resumed_counts_once_at_arrival(env, short_round):
    make, run, _, tmp_path = env
    s, _, _ = make(7510)
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    run(s, 40)
    assert league.load(tmp_path / "ligue.json").results == {}
    s2, _, errors2 = _crash_and_resume(make, tmp_path, 7520)
    assert not errors2 and s2._league_run is not None and len(s2.bots) == 11
    s2._on_command("resume", {}, 4)
    run(s2, 900)
    assert s2.state.session_state == "FINISHED" and "league" in s2.state.summary
    season = league.load(tmp_path / "ligue.json")
    assert len(season.results) == 1 and season.results[0].source == "joueur"


def test_league_round_not_resumed_stays_open(env, short_round, monkeypatch):
    """Reprise refusée : rien n'est compté, la manche se recourt (règle de CH3 gardée)."""
    make, run, _, tmp_path = env
    s, _, _ = make(7530)
    s._on_command("league_new", {}, 2)
    s._on_command("start", {"mode": "race", "league": True}, 3)
    run(s, 40)
    monkeypatch.setattr("openride_core.session.__version__", "99.0.0")
    s2, _, _ = _crash_and_resume(make, tmp_path, 7540)
    assert s2._league_run is None and s2.grandprix is None
    s2._on_command("end_session", {"save": True}, 4)
    assert league.load(tmp_path / "ligue.json").results == {}


# --- lancement suivant : « Reprendre la course » (lot RC3) -------------------------------------------------

def _interrupted(s):
    s._publish_interrupted()
    return s.server.hello_config.get("interrupted", [])


def test_interrupted_race_offered_with_place_and_resumed_from_menu(env):
    make, run, _, tmp_path = env
    s, _, _ = make(7550)
    s._on_command("start", {"mode": "race"}, 2)
    run(s, 60)
    place = s.grandprix.place("me")
    s2, sent2, errors2 = make(7560)   # le jeu entier a été fermé : nouveau lancement, menu
    items = _interrupted(s2)
    assert len(items) == 1 and items[0]["resumable"] is True
    race = items[0]["race"]
    assert race["mode"] == "race" and race["of"] == len(s.bots) + 1 and abs(race["place"] - place) <= 1
    assert race["lap"] is not None and race["league"] is False
    validator("interrupted").validate({"type": "interrupted", "v": 1, "request_cmd_id": 0, "id": "x", "saved": False,
                                       "fit_path": None, "items": items})   # forme des éléments, `race` compris
    s2._on_command("recover_session", {"id": items[0]["id"], "resume": True}, 5)
    assert not errors2
    assert s2.state.session_state == "PAUSED" and s2.state.pause_reason == "core_restarted"
    assert s2.grandprix is not None and len(s2.bots) == len(s.bots)
    msg = [m for m in sent2 if m.get("type") == "interrupted"][-1]
    validator("interrupted").validate(msg)
    assert msg["resumed"] is True and msg["items"] == []
    s2._on_command("resume", {}, 6)
    run(s2, 900)
    assert s2.state.session_state == "FINISHED"


def test_interrupted_too_old_or_other_version_not_resumable(env, monkeypatch):
    from openride_core.resume import RESUME_WINDOW_S, interrupted_sessions

    make, run, _, tmp_path = env
    s, _, _ = make(7570)
    s._on_command("start", {"mode": "race"}, 2)
    run(s, 30)
    import time
    later = time.time() + RESUME_WINDOW_S + 60
    old = interrupted_sessions(tmp_path / "journal", now=later)
    assert old[0]["resumable"] is False and old[0]["race"]["mode"] == "race"
    s2, _, errors2 = make(7580)
    monkeypatch.setattr("openride_core.__version__", "99.0.0")
    items = _interrupted(s2)
    assert items[0]["resumable"] is False
    s2._on_command("recover_session", {"id": items[0]["id"], "resume": True}, 3)
    assert errors2 and "ne peut plus être reprise" in errors2[-1][1]
    assert s2.state.session_state in ("IDLE", "READY")


def test_race_cut_before_snapshot_not_resumable(env):
    make, run, _, tmp_path = env
    s, _, _ = make(7590)
    s._on_command("start", {"mode": "race"}, 2)
    run(s, 3)
    s2, _, _ = make(7600)
    items = _interrupted(s2)
    assert items[0]["resumable"] is False and "race" not in items[0]
