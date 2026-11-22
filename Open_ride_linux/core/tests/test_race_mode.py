"""Lot CR1 : mode « Course » (course classique contre les bots), le Grand Prix sans objet sur tous les parcours.

Demande du propriétaire du 20 novembre (« il manque un mode course classique vs bots », « un grand prix sans objet
mais sur tous les parcours », « classement éloigné aussi ») : même arbitre que le Grand Prix (arrivée, places,
écarts, tours), aucun objet ni boîte, mode classique gardé (segments, maillots, bonus, tactique des bots), boutons
de la séance libre, réglages `race.*`, objet `gp` de `state` et `summary.gp` avec `mode` = « race »."""

import json
from pathlib import Path

import pytest

from openride_core import settings
from openride_core.bots import ProfileBot
from openride_core.config import Config
from openride_core.grandprix import ME
from openride_core.grandprix.mode import GrandPrixMode

from test_grandprix_session import STATE_LIMIT_BYTES, env, validator  # noqa: F401  (fixture partagée)


def test_three_laps_race_without_objects_full_ranking_and_bilan(env):
    make, run, frame, tmp_path = env
    s, _, errors = make(6900)
    s.cfg.race.opponents, s.cfg.race.laps = 7, 2
    s._on_command("start", {"mode": "race"}, 2)
    assert not errors and s.state.session_state == "RUNNING"
    assert [type(b) for b in s.bots] == [ProfileBot] * 7
    gp = s.grandprix
    assert gp.mode == "race" and gp.enabled == () and gp.boxes.rows == []
    assert gp.lap_m == pytest.approx(1500.0) and gp.length_m == pytest.approx(3000.0)
    assert s.race is not None                              # mode classique gardé : segments, maillots, bonus
    state_v = validator("state")
    seen: list[dict] = []

    def check(sess):
        if sess.state.session_state != "RUNNING":
            return
        d = frame(sess)
        state_v.validate(d)
        assert len(json.dumps(d, ensure_ascii=False).encode()) < STATE_LIMIT_BYTES
        g = d["gp"]
        assert g["mode"] == "race" and g["held"] is None and g["obj"] == [] and g["boxes"] == []
        assert g["warn"] is None and g["fx"] == [] and not g["pick"]
        assert all(b.get("item") is None for b in d["bots"] if "item" in b)
        # classement complet : tous les coureurs, loin compris, portent leur position
        assert len(d["bots"]) == 7 and all("s" in b for b in d["bots"])
        seen.append(g)

    run(s, 900, check)
    assert s.state.session_state == "FINISHED" and not errors
    assert {f["of"] for f in seen} == {8} and {f["lap"][1] for f in seen} == {2}
    summary = s.state.summary["gp"]
    assert summary["mode"] == "race" and 1 <= summary["place"] <= 8 and summary["of"] == 8 and summary["laps"] == 2
    assert summary["launched"] == {} and summary["received"] == {} and summary["dodged"] == 0
    validator("state").validate({**s.state.to_dict()})
    journal = next((tmp_path / "journal").glob("*.jsonl"))
    lines = [json.loads(x) for x in journal.read_text("utf-8").splitlines()]
    start = next(ln for ln in lines if ln.get("kind") == "gp_start")
    assert start["mode"] == "race" and start["opponents"] == 7 and start["laps"] == 2 and "items" not in start
    assert not any(ln.get("kind") == "gp" and ln.get("event") in ("box", "use", "hit") for ln in lines)
    assert s.grandprix is None and s.state.gp is None


def test_line_route_runs_to_the_finish_of_the_route(env):
    """En ligne, la Course va jusqu'à l'arrivée du parcours (ligne 30 m avant le bout, file des bots arrivés),
    sans réglage de distance (le Grand Prix des objets, lui, se court sur une boucle seulement, lot GPL1)."""
    from openride_core.session import GP_RUNOUT_M

    make, run, _, _ = env
    s, _, errors = make(6910, route_id="demo")
    s._on_command("start", {"mode": "race"}, 2)
    assert not errors and s.grandprix.lap_m is None
    assert s.grandprix.length_m == pytest.approx(s.route.length_m - s.physics.s - GP_RUNOUT_M)
    run(s, 2)
    assert s.state.summary is None and s.state.session_state == "RUNNING"


def test_buttons_stay_those_of_the_free_ride(env):
    """Z court, A et flèches ne vont pas au Grand Prix (aucun objet, pas de voies) : la Course garde les boutons
    de la séance libre."""
    make, run, _, _ = env
    s, _, errors = make(6920)
    s._on_command("start", {"mode": "race"}, 2)
    run(s, 2)
    called: list[str] = []
    s._grandprix_press = lambda ev: called.append(ev) or True
    for ev in ("Z_SHORT", "A_SHORT", "LEFT_SHORT", "RIGHT_SHORT"):
        s._on_command("input_event", {"event": ev}, 3)
    assert called == [] and not errors


def test_refusals_like_the_grand_prix(env):
    make, run, _, _ = env
    s, _, errors = make(6930)
    s._on_command("start", {"mode": "race", "bots": []}, 2)
    assert errors[-1][0] == "bad_args" and "Course" in errors[-1][1] and s.state.session_state == "READY"
    s._on_command("select_workout", {"workout_id": "erg"}, 3)
    s._on_command("start", {"mode": "race"}, 4)
    assert errors[-1][0] == "bad_args" and s.state.session_state == "READY"
    s._on_command("select_workout", {"workout_id": None}, 5)
    s.cfg.grandprix.box_every_m = 1200                    # réglage des objets : sans effet sur la Course
    s._on_command("start", {"mode": "race"}, 6)
    assert s.state.session_state == "RUNNING"
    run(s, 1)
    s._on_command("set_ride_mode", {"mode": "erg"}, 7)
    assert errors[-1][0] == "busy" and s.state.mode == "SIM"


def test_mode_race_rejects_unknown_mode():
    with pytest.raises(Exception):
        GrandPrixMode([ME, "b1"], 1000.0, mode="course")


def test_settings_listed_and_mode_announced():
    from openride_core.ipc_server import CORE_MODES
    keys = [st.key for st in settings.SETTINGS]
    i = keys.index("grandprix.box_every_m")
    assert keys[i + 1:i + 3] == ["race.opponents", "race.laps"]
    assert "race" in CORE_MODES
    items = {it["key"]: it for it in settings.current(Config())}
    assert (items["race.opponents"]["min"], items["race.opponents"]["max"], items["race.opponents"]["value"]) == (2, 11, 7)
    assert (items["race.laps"]["min"], items["race.laps"]["max"], items["race.laps"]["value"]) == (1, 10, 3)


def test_frame_gap_is_to_the_rider_ahead():
    """`state.gp.gap_s` (contrat §4) : écart avec le coureur de devant, avec le second en tête ; le HUD le nomme
    (« à 1,0 s de Rouleur ») : ce n'est pas le retard sur le premier."""
    from openride_core.grandprix import GpInput, RiderIn

    gp = GrandPrixMode([ME, "b1", "b2"], 5000.0, mode="race")
    riders = {"b1": RiderIn(300.0, 10.0, 10.0), "b2": RiderIn(250.0, 10.0, 10.0), ME: RiderIn(240.0, 10.0, 10.0)}
    gp.start(0.0, riders)
    gp.step(GpInput(0.02, 0.02, riders))
    assert gp.frame(ME)["place"] == 3 and gp.frame(ME)["gap_s"] == pytest.approx(1.0)   # 10 m derrière b2
    assert gp.gap_s(ME) == pytest.approx(6.0)                                         # retard sur le premier
    lead = {"b1": RiderIn(300.0, 10.0, 10.0), "b2": RiderIn(250.0, 10.0, 10.0), ME: RiderIn(320.0, 10.0, 10.0)}
    gp.step(GpInput(0.04, 0.02, lead))
    assert gp.frame(ME)["place"] == 1 and gp.frame(ME)["gap_s"] == pytest.approx(2.0)   # avance sur le second
