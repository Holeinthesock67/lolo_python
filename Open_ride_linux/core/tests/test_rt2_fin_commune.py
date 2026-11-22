"""Lot RT2 : fin de séance commune (révision IPC 1.32).

Choix du propriétaire du 21 novembre (10 h 37, audit des retours) : « après la fin, on continue à rouler, A maintenu
= bilan », dans tous les modes. L'arrivée d'un parcours en ligne, du Grand Prix et de la Course ne termine plus la
séance : `state.arrival` dit l'issue, le cycliste continue au calme (demi-tour automatique au bout d'un parcours en
ligne) jusqu'à « Terminer et enregistrer » (`end_session`), et le bilan en garde une copie (`summary.arrival`)."""

from test_grandprix_session import env, validator  # noqa: F401  (fixture partagée)


def test_race_on_a_loop_keeps_rolling_after_the_line(env):
    make, run, frame, _ = env
    s, _, errors = make(6950)
    s.cfg.race.opponents, s.cfg.race.laps = 3, 1
    s._on_command("start", {"mode": "race"}, 2)
    assert not errors and s.state.session_state == "RUNNING"
    for _ in range(600):   # au plus 10 min de course
        run(s, 1.0, end_at_arrival=False)
        if s.state.arrival is not None:
            break
    arr = s.state.arrival
    assert s.state.session_state == "RUNNING", "l'arrivée ne termine plus la séance"
    assert arr is not None and arr["kind"] == "race" and arr["of"] == 4 and 1 <= arr["place"] <= 4
    assert arr["place"] == s.grandprix.racers["me"].finished
    validator("state").validate(frame(s))
    s_before = s.physics.distance
    run(s, 20.0, end_at_arrival=False)
    assert s.state.session_state == "RUNNING" and s.physics.distance > s_before + 50.0   # retour au calme
    assert s.state.arrival == arr, "posée une seule fois"
    s._on_command("end_session", {"save": True}, 3)
    assert s.state.session_state == "FINISHED" and s.state.arrival is None
    summary = s.state.summary
    assert summary["arrival"] == arr and summary["gp"]["finished"] is True and summary["gp"]["mode"] == "race"
    validator("state").validate(s.state.to_dict())


def test_race_stopped_before_the_line_has_no_arrival(env):
    make, run, _, _ = env
    s, _, _ = make(6952)
    s.cfg.race.opponents, s.cfg.race.laps = 3, 2
    s._on_command("start", {"mode": "race"}, 2)
    run(s, 30.0, end_at_arrival=False)
    s._on_command("end_session", {"save": True}, 3)
    assert s.state.session_state == "FINISHED"
    assert "arrival" not in s.state.summary and s.state.summary["gp"]["finished"] is False


def test_free_ride_on_a_line_route_turns_back_at_the_end(env):
    make, run, frame, _ = env
    s, _, errors = make(6954, route_id="demo")
    s._on_command("start", {}, 2)
    assert not errors and s.state.session_state == "RUNNING" and not s.route.is_loop
    run(s, 2.0, end_at_arrival=False)
    s.physics.s = s.route.length_m - 1.0   # juste avant le bout
    run(s, 2.0, end_at_arrival=False)
    assert s.state.session_state == "RUNNING"
    assert s.state.arrival == {"kind": "route", "place": None, "of": None}
    assert s.physics.direction < 0 and s.state.dir == -1, "demi-tour automatique"
    validator("state").validate(frame(s))
    s.physics.s = 0.5   # retour au départ, à rebours : nouveau demi-tour, même arrivée
    run(s, 2.0, end_at_arrival=False)
    assert s.state.session_state == "RUNNING" and s.physics.direction > 0
    assert s.state.arrival["kind"] == "route"
    s._on_command("end_session", {"save": True}, 3)
    assert s.state.summary["arrival"]["kind"] == "route"


def test_grand_prix_on_a_line_route_turns_back_once_finished(env):
    make, run, _, _ = env
    s, _, errors = make(6956, route_id="demo", distance_km=2)
    s._on_command("start", {"mode": "grandprix"}, 2)
    assert not errors and s.grandprix.lap_m is None
    assert s._u_turn_refusal("RUNNING") is not None, "pas de demi-tour pendant la course"
    for _ in range(900):
        run(s, 1.0, end_at_arrival=False)
        if s.state.arrival is not None or s.state.session_state != "RUNNING":
            break
    assert s.state.session_state == "RUNNING" and s.state.arrival["kind"] == "grandprix"
    assert s._u_turn_refusal("RUNNING") is None, "course finie : demi-tour permis"
    s.physics.s = s.route.length_m - 1.0   # course de 2 km sur 5 km : le cycliste roule jusqu'au bout
    run(s, 2.0, end_at_arrival=False)
    assert s.state.session_state == "RUNNING" and s.physics.direction < 0
    s._on_command("end_session", {"save": True}, 3)
    assert s.state.summary["arrival"]["kind"] == "grandprix" and s.state.summary["gp"]["finished"] is True


def test_finished_workout_sets_the_arrival(env):
    make, run, _, _ = env
    s, _, errors = make(6958)
    s._on_command("select_workout", {"workout_id": "erg"}, 2)
    s._on_command("start", {}, 3)
    assert not errors and s.erg is not None
    s.erg.skip()   # un seul bloc : entraînement fini
    s._sync_erg_state()
    assert s.state.workout_done is not None and s.state.arrival == {"kind": "workout", "place": None, "of": None}
    run(s, 1.0, end_at_arrival=False)
    assert s.state.session_state == "RUNNING"
