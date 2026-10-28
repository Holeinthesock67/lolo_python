"""Séance en monde ouvert (lot W9) : générateur, route qui s'allonge, carrefours, choix, pause, panne.

La plupart des essais utilisent `data/stub_worldgen.py`, une doublure du générateur (bibliothèque
standard seulement) ; un essai lance le faux générateur du lot W15 quand le compilateur est installé.
"""

import json
import sys
import time
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.open_world import OpenWorldError, parse_start
from openride_core.session import CoreSession
from openride_core.zwift_click import InputEvent

STUB = Path(__file__).resolve().parent / "data" / "stub_worldgen.py"
IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
START = {"lat": 45.0, "lon": 6.0, "heading_deg": 90, "nav": "ride", "seed": 7}


class Spy:
    """Messages que le core aurait envoyés à l'engine."""

    def __init__(self, server):
        self.sent = []
        server.send_raw = lambda msg, max_size=None: self.sent.append(msg)

    def of(self, kind):
        return [m for m in self.sent if m.get("type") == kind]


def make_session(tmp_path, monkeypatch, port, power=250.0, stub_args=(), cmd=None):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    cfg.open_world.cache_dir = str(tmp_path / "cache")
    s = CoreSession(cfg, driver=MockDriver(base_power_w=power, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes")
    s.worldgen_cmd = cmd or [sys.executable, str(STUB)]
    s.worldgen_args = list(stub_args)
    s.spy = Spy(s.server)
    s.clock = 1000.0
    return s


def step(s, seconds, pause=0.002):
    """Avance de `seconds` secondes simulées, en laissant au générateur le temps de répondre."""
    n = int(seconds / 0.02)
    for i in range(n):
        s.clock += 0.02
        s._step(0.02, s.clock)
        if i % 25 == 24:
            time.sleep(pause)


def wait_until(s, cond, timeout=20.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        step(s, 0.1, pause=0.01)
        if cond():
            return True
    return False


def open_world(s, args=None):
    s._on_command("start_open_world", args or START, 1)
    assert s.state.session_state == "LOADING"
    assert wait_until(s, lambda: s.state.session_state != "LOADING"), "monde ouvert jamais prêt"


@pytest.fixture
def session(tmp_path, monkeypatch):
    made = []

    def build(*a, **kw):
        s = make_session(tmp_path, monkeypatch, *a, **kw)
        made.append(s)
        return s

    yield build
    for s in made:
        s._close_open_world(wait=True)


# --- arguments de `start_open_world` --------------------------------------------------------------

def test_parse_start_validates_arguments():
    msg = parse_start({"lat": 45.1, "lon": 6.2})
    assert msg["nav"] == "ride" and msg["heading_deg"] == 0.0 and msg["seed"] == 0 and msg["target"] is None
    assert parse_start({**START, "nav": "loop", "loop_km": 30})["loop_km"] == 30.0
    dest = parse_start({**START, "nav": "destination", "target": {"lat": 45.2, "lon": 6.3}})
    assert dest["target"] == {"lat": 45.2, "lon": 6.3}
    for bad in (None, {}, {"lat": "x", "lon": 6}, {"lat": 91, "lon": 6}, {**START, "nav": "vol"},
                {**START, "nav": "destination"}, {**START, "nav": "loop"}, {**START, "nav": "loop", "loop_km": 0},
                {**START, "seed": True}):
        with pytest.raises(OpenWorldError) as err:
            parse_start(bad)
        assert err.value.code == "bad_args"


def test_hello_ack_announces_modes_and_world_dir(session):
    s = session(7010)
    assert "open_world" in s.server.hello_config.get("modes", ["open_world"])
    assert s.server.hello_config["open_world_dir"].endswith("seances")


def test_bad_arguments_return_to_idle_with_bad_args(session):
    s = session(7012)
    s._on_command("start_open_world", {"lat": "x"}, 1)
    assert s.state.session_state == "IDLE" and s.openworld is None
    assert s.spy.of("error")[-1]["code"] == "bad_args"


def test_busy_during_a_session(session):
    s = session(7014)
    open_world(s)
    s._on_command("start", {}, 2)
    s._on_command("start_open_world", START, 3)
    assert s.spy.of("error")[-1]["code"] == "busy" and s.state.session_state == "RUNNING"


# --- préparation ---------------------------------------------------------------------------------

def test_start_loading_status_then_ready(session):
    s = session(7016)
    open_world(s)
    assert s.state.session_state == "READY"
    assert s.state.route_id.startswith("ow:ow-") and s.state.route_length_m >= 2000.0
    phases = [m["phase"] for m in s.spy.of("world_status")]
    assert phases[-1] == "ready" and "osm" in phases
    validator = jsonschema.Draft202012Validator(
        json.loads((IPC_DIR / "world_status.schema.json").read_text(encoding="utf-8")))
    for m in s.spy.of("world_status"):
        assert not list(validator.iter_errors(m)), m
    assert Path(s.server.hello_config["open_world_dir"], s.state.route_id[3:] + ".world").is_dir()


def test_world_unavailable_returns_to_idle(session):
    s = session(7018, stub_args=["--unavailable"])
    s._on_command("start_open_world", START, 1)
    assert wait_until(s, lambda: s.state.session_state == "IDLE")
    assert s.spy.of("error")[-1]["code"] == "world_unavailable" and s.openworld is None


def test_missing_generator_is_world_unavailable(session):
    s = session(7020, cmd=["/nonexistent/openride-worldgen"])
    s._on_command("start_open_world", START, 1)
    assert s.state.session_state == "IDLE" and s.spy.of("error")[-1]["code"] == "world_unavailable"


def test_generator_dying_while_opening_is_world_unavailable(session, tmp_path):
    s = session(7022, cmd=[sys.executable, "-c", "import sys; sys.exit(2)"])
    s._on_command("start_open_world", START, 1)
    assert wait_until(s, lambda: s.state.session_state == "IDLE")
    assert s.spy.of("error")[-1]["code"] == "world_unavailable"


# --- critère 3 : 10 km sans pause -------------------------------------------------------------------

def test_ten_kilometres_without_pause_and_route_keeps_growing(session):
    s = session(7024, power=450.0)
    open_world(s)
    first_length = s.state.route_length_m
    s._on_command("start", {}, 2)
    ow = s.openworld
    states = set()
    t0 = time.time()
    while s.physics.s < 10_000.0 and time.time() - t0 < 120:
        step(s, 5.0)
        states.add(s.state.session_state)
        assert ow.known_ahead(s.physics.s) > 0.0, f"à {s.physics.s:.0f} m : route épuisée"
    assert s.physics.s >= 10_000.0
    assert states == {"RUNNING"}
    assert s.state.route_length_m > first_length + 8_000.0 and ow.rev > 3
    assert s.state.open_world["data"] == "cached" and s.state.open_world["rev"] == ow.rev
    s._on_command("end_session", {"save": False}, 3)
    assert s.state.session_state == "FINISHED" and s.openworld is None and s.state.open_world is None


def test_open_world_does_not_finish_at_the_end_of_the_known_route(session):
    s = session(7026, power=450.0, stub_args=["--horizon", "400"])
    open_world(s)
    s._on_command("start", {}, 2)
    step(s, 120.0)
    assert s.state.session_state == "RUNNING"    # une route finie finirait la séance (arrivée atteinte)


# --- critère 4 : choix aux carrefours -----------------------------------------------------------------

def junction_frame(s):
    return s.state.open_world["next"]


def at(s, meters):
    """Place le cycliste à `meters` du début de la route, sans pédaler."""
    s.physics.s, s.physics.v = meters, 0.0


def test_right_short_chooses_when_offered_and_is_ignored_once_locked(session):
    s = session(7028, power=0.0)
    open_world(s)
    s._on_command("start", {}, 2)
    sent = []
    real = s.openworld.client.send
    s.openworld.client.send = lambda m: (sent.append(m), real(m))[1]
    at(s, 350.0)                           # carrefour jA à 500 m : 150 m devant
    step(s, 0.2)
    nxt = junction_frame(s)
    assert nxt["id"] == "jA" and nxt["chosen"] == 1 and not nxt["locked"] and 140 < nxt["d_m"] < 160
    assert [b[1] for b in nxt["b"]] == ["m", "t", "s"] and [b[0] for b in nxt["b"]] == [-90, 0, 90]
    s._handle_input(InputEvent.RIGHT_SHORT)
    step(s, 0.1)
    assert junction_frame(s)["chosen"] == 2
    choose = [m for m in sent if m["type"] == "choose"]
    assert choose == [{"type": "choose", "junction_id": "jA", "branch": 2}]
    assert InputEvent.RIGHT_SHORT.value in [m["event"] for m in s.spy.of("input")]    # toujours relayé à l'engine
    assert wait_until(s, lambda: s.state.open_world["next"]["chosen"] == 2 and s.openworld.route.junctions[0]["chosen"] == 2)
    # À 20 m : verrouillé, rien n'est envoyé et le choix reste.
    at(s, 480.0)
    step(s, 0.2)
    assert junction_frame(s)["locked"] is True
    sent.clear()
    s._handle_input(InputEvent.LEFT_SHORT)
    step(s, 0.1)
    assert [m for m in sent if m["type"] == "choose"] == [] and junction_frame(s)["chosen"] == 2


def test_left_right_a_short_and_a_long(session):
    s = session(7030, power=0.0)
    open_world(s)
    s._on_command("start", {}, 2)
    at(s, 300.0)
    step(s, 0.2)

    def press(ev):
        s._handle_input(ev)
        step(s, 0.02)
        return junction_frame(s)["chosen"]

    assert press(InputEvent.LEFT_SHORT) == 0
    assert press(InputEvent.LEFT_SHORT) == 0        # pas de boucle avec les flèches
    assert press(InputEvent.RIGHT_SHORT) == 1
    assert press(InputEvent.RIGHT_SHORT) == 2
    assert press(InputEvent.A_SHORT) == 0           # A : suivante, en boucle
    assert press(InputEvent.A_SHORT) == 1
    assert press(InputEvent.A_LONG) == 1             # valide tout de suite : verrouillé
    assert junction_frame(s)["locked"] is True
    assert press(InputEvent.RIGHT_SHORT) == 1


def test_far_junction_is_not_offered(session):
    s = session(7032, power=0.0)
    open_world(s)
    s._on_command("start", {}, 2)
    at(s, 100.0)                                    # jA à 400 m : au-delà de 300 m
    step(s, 0.2)
    assert junction_frame(s)["id"] == "jA" and 390 < junction_frame(s)["d_m"] < 410
    s._handle_input(InputEvent.RIGHT_SHORT)
    assert junction_frame(s)["chosen"] == 1


def test_choose_branch_command_and_its_errors(session):
    s = session(7034, power=0.0)
    open_world(s)
    s._on_command("start", {}, 2)
    at(s, 350.0)
    step(s, 0.2)
    s._on_command("choose_branch", {"junction_id": "jA", "branch": 0}, 3)
    step(s, 0.02)
    assert junction_frame(s)["chosen"] == 0
    s._on_command("choose_branch", {"junction_id": "nope", "branch": 0}, 4)
    assert s.spy.of("error")[-1]["code"] == "unknown_junction"
    s._on_command("choose_branch", {"junction_id": "jA", "branch": 7}, 5)
    assert s.spy.of("error")[-1]["code"] == "unknown_junction"
    at(s, 490.0)
    step(s, 0.2)
    s._on_command("choose_branch", {"junction_id": "jA", "branch": 2}, 6)
    assert s.spy.of("error")[-1]["code"] == "branch_locked" and junction_frame(s)["chosen"] == 0


def test_choices_reach_the_journal_at_lock_time(session, tmp_path):
    s = session(7036, power=0.0)
    open_world(s)
    s._on_command("start", {}, 2)
    at(s, 350.0)
    step(s, 0.2)
    s._handle_input(InputEvent.RIGHT_SHORT)
    at(s, 495.0)
    step(s, 0.5)
    journal = s._rec.path
    s._on_command("end_session", {"save": False}, 3)
    lines = [ln for ln in read_journal(journal) if ln.get("kind") == "junction"]
    assert len(lines) == 1
    assert lines[0]["id"] == "jA" and lines[0]["branch"] == 2 and lines[0]["of"] == 3
    assert lines[0]["how"] == "click" and lines[0]["road_class"] == "s" and lines[0]["s_m"] == 500.0


def test_untouched_junction_takes_the_default_branch(session):
    s = session(7038, power=0.0)
    open_world(s)
    s._on_command("start", {}, 2)
    at(s, 495.0)
    step(s, 0.5)
    journal = s._rec.path
    s._on_command("end_session", {"save": False}, 3)
    line = next(ln for ln in read_journal(journal) if ln.get("kind") == "junction")
    assert line["how"] == "default" and line["branch"] == 1


# --- critère 5 : route qui ne s'allonge plus -----------------------------------------------------------

def test_pause_world_data_then_automatic_resume(session, tmp_path):
    s = session(7040, power=450.0, stub_args=["--stall-m", "800", "--horizon", "1000"])
    open_world(s)
    s._on_command("start", {}, 2)
    # les pauses d'un générateur seulement en retard sur la simulation accélérée reprennent seules
    assert wait_until(s, lambda: s.state.session_state == "PAUSED" and s.openworld.data == "missing", timeout=60.0)
    assert s.state.pause_reason == "world_data"
    s_pause = s.physics.s
    # au bout de la route, ou plus tôt si une pause de retard a précédé le manque de données (reprise à 500 m)
    assert s.openworld.route.length_m - s_pause < 500.0 and s_pause > 700.0
    assert s.state.open_world["data"] == "missing"
    step(s, 3.0)
    assert s.state.session_state == "PAUSED" and s.physics.s == s_pause    # la séance reste figée
    (tmp_path / "cache" / "seances" / "resume.flag").write_text("x")
    assert wait_until(s, lambda: s.state.session_state == "RUNNING", timeout=20.0)
    assert s.openworld.route.length_m - s.physics.s >= 500.0 or s.openworld.known_ahead(s.physics.s) > 200.0
    assert s.state.open_world["data"] == "cached"


def test_late_generator_pauses_instead_of_riding_past_the_known_route(session, tmp_path):
    """Générateur en retard (données présentes, route pas encore prolongée) : pause au bout de la route."""
    s = session(7052, power=450.0, stub_args=["--late-m", "800", "--horizon", "1000"])
    open_world(s)
    s._on_command("start", {}, 2)
    # route figée vers 1 800 m (800 m + horizon) : pause à moins de 200 m de son bout
    assert wait_until(s, lambda: s.state.session_state == "PAUSED" and s.physics.s > 1500.0, timeout=60.0)
    assert s.state.pause_reason == "world_data" and s.openworld.data == "cached"
    s_pause = s.physics.s
    assert 0.0 < s.openworld.known_ahead(s_pause) < 200.0
    step(s, 30.0)
    assert s.state.session_state == "PAUSED" and s.physics.s == s_pause    # jamais au-delà de la route connue
    (tmp_path / "cache" / "seances" / "resume.flag").write_text("x")
    assert wait_until(s, lambda: s.state.session_state == "RUNNING", timeout=20.0)
    assert s.openworld.known_ahead(s.physics.s) >= 500.0


# --- critère 7 : générateur tué ----------------------------------------------------------------------------

def test_generator_killed_is_restarted_once(session):
    s = session(7042, power=450.0, stub_args=["--crash-after-m", "600", "--crash-times", "1"])
    open_world(s)
    s._on_command("start", {}, 2)
    first = s.openworld.client
    assert wait_until(s, lambda: s.openworld.client is not first, timeout=60.0), "pas de relance"
    assert s.openworld.client.alive and first.exit_code == 3 and not s.openworld.dead
    assert wait_until(s, lambda: s.openworld._next is None and not s.openworld.opening, timeout=30.0)
    s_swap = s.physics.s
    step(s, 60.0)
    assert s.state.session_state == "RUNNING" and s.physics.s > s_swap + 100.0
    assert s.openworld.route.base_m > 500.0                  # la distance continue de croître
    assert s.openworld.known_ahead(s.physics.s) > 0.0


def test_generator_falling_again_pauses_world_data(session):
    s = session(7044, power=450.0, stub_args=["--crash-after-m", "300", "--crash-times", "2", "--horizon", "700"])
    open_world(s)
    s._on_command("start", {}, 2)
    assert wait_until(s, lambda: s.state.session_state == "PAUSED" and s.openworld.dead, timeout=90.0)
    assert s.state.pause_reason == "world_data"
    assert s.openworld.known_ahead(s.physics.s) < 500.0      # pause au bout de la route, ou plus tôt si le générateur était en retard
    step(s, 3.0)
    assert s.state.session_state == "PAUSED"                 # pas de reprise : plus de générateur


# --- trame state ----------------------------------------------------------------------------------------

def test_state_frame_is_valid_and_small_with_open_world(session):
    s = session(7046, power=300.0)
    open_world(s)
    s._on_command("start", {}, 2)
    at(s, 350.0)
    step(s, 0.3)
    s.state.devices = None
    frame = s.state.to_dict()
    validator = jsonschema.Draft202012Validator(
        json.loads((IPC_DIR / "state.schema.json").read_text(encoding="utf-8")))
    assert "open_world" in frame and not list(validator.iter_errors(frame))
    assert len(json.dumps(frame, separators=(",", ":"), ensure_ascii=False).encode()) < 1400
    s.state.devices = {"trainer": {"status": "MOCK", "name": None, "address": None}, "click": [],
                       "hr": {"status": "NONE", "source": None, "battery_pct": None}}
    assert "open_world" not in s.state.to_dict()              # jamais avec devices (contrat §4)


def test_other_routes_leave_open_world_alone(session, tmp_path):
    s = session(7048, power=0.0)
    open_world(s)
    ow = s.openworld
    s._on_command("select_route", {"route_id": "demo"}, 2)
    assert s.openworld is None and s.state.open_world is None and s.state.route_id == "demo"
    assert ow.client is not None            # le générateur est arrêté dans un fil (close) : pas d'attente ici


# --- générateur de W15 -------------------------------------------------------------------------------------

def test_real_fake_generator_starts_a_ride(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("openride_compiler.worldgen.synthetic")
    s = make_session(tmp_path, monkeypatch, 7050, power=300.0,
                     cmd=[sys.executable, "-m", "openride_compiler.worldgen.synthetic"],
                     stub_args=["--work-dir", str(tmp_path / "work")])
    try:
        s._on_command("start_open_world", {"lat": 43.0, "lon": 4.6, "heading_deg": 90, "nav": "ride", "seed": 7}, 1)
        assert wait_until(s, lambda: s.state.session_state != "LOADING", timeout=120.0)
        assert s.state.session_state == "READY"
        s._on_command("start", {}, 2)
        step(s, 60.0, pause=0.005)
        assert s.state.session_state == "RUNNING" and s.physics.s > 100.0
        assert s.state.open_world["next"] is not None and s.state.lat != 0.0
    finally:
        s._close_open_world(wait=True)
