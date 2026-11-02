"""Lot O36 : départ au pédalage (start_gate.py) et son branchement dans la séance."""

from __future__ import annotations

from openride_core.config import Config
from openride_core.session import CoreSession
from openride_core.start_gate import StartGate

DT = 0.02


def _run(gate: StartGate, seconds: float, **kw) -> bool:
    opened = False
    for _ in range(int(round(seconds / DT))):
        opened = gate.update(DT, **kw) or opened
    return opened


RIDING = dict(scene_ready=True, trainer_connected=True, cadence_rpm=60.0, power_w=120.0)


def test_immediate_is_open_at_once():
    assert StartGate(immediate=True).open


def test_waits_scene_then_trainer_then_pedalling():
    g = StartGate(cadence_rpm=30, duree_s=3, attente_decor_s=60)
    assert not _run(g, 10, **{**RIDING, "scene_ready": False}) and g.phase == "decor"
    assert not _run(g, 5, **{**RIDING, "trainer_connected": False}) and g.phase == "trainer"
    assert not _run(g, 2.9, **RIDING) and g.phase == "pedalage"
    assert _run(g, 0.2, **RIDING) and g.open


def test_short_dropouts_do_not_reset_the_count():
    g = StartGate(cadence_rpm=30, duree_s=3)
    _run(g, 2.0, **RIDING)
    _run(g, 1.5, **{**RIDING, "cadence_rpm": 10.0})   # à-coup de 1,5 s sous le seuil : compte gardé
    assert g.held_s >= 1.9
    assert _run(g, 1.1, **RIDING)


def test_long_stop_decays_the_count():
    g = StartGate(cadence_rpm=30, duree_s=3)
    _run(g, 2.0, **RIDING)
    _run(g, 4.0, **{**RIDING, "cadence_rpm": 0.0, "power_w": 0.0})
    assert g.held_s == 0.0 and not g.open


def test_power_counts_when_cadence_is_missing():
    g = StartGate(cadence_rpm=30, duree_s=1)
    assert _run(g, 1.1, **{**RIDING, "cadence_rpm": None, "power_w": 60.0})


def test_scene_timeout_for_an_engine_that_never_says_ready():
    g = StartGate(duree_s=1, attente_decor_s=5)
    assert not _run(g, 4.9, **{**RIDING, "scene_ready": False})
    assert _run(g, 1.2, **{**RIDING, "scene_ready": False}) and g.decor_timeout


def test_trainer_lost_restarts_the_count():
    g = StartGate(duree_s=3)
    _run(g, 2.0, **RIDING)
    _run(g, 0.1, **{**RIDING, "trainer_connected": False})
    assert g.phase == "trainer" and g.held_s == 0.0


# --- branchement dans la séance -------------------------------------------------------------


def _session(tmp_path, mode: str = "pedalage") -> CoreSession:
    cfg = Config()
    cfg.drivers.trainer = "mock"
    cfg.drivers.input = "none"
    cfg.depart.mode = mode
    cfg.depart.duree_s = 2
    s = CoreSession(cfg, routes_root=tmp_path / "routes", journal_dir=tmp_path / "journal")
    s._on_command("select_route", {"route_id": "demo"}, 1)
    assert s.state.session_state == "READY"
    return s


def _steps(s: CoreSession, seconds: float) -> None:
    for i in range(int(round(seconds / DT))):
        s._step(DT, i * DT)


def test_session_waits_for_scene_ready_then_pedalling(tmp_path):
    s = _session(tmp_path)
    s.server.engine_connected = True
    s._on_command("start", {}, 2)
    assert s.state.session_state == "READY" and s.state.start_wait["phase"] == "decor"
    assert s._rec is None   # rien n'est enregistré pendant l'attente
    _steps(s, 1.0)
    assert s.state.session_state == "READY" and s.state.t == 0.0 and s.state.s == 0.0
    s._on_command("scene_ready", {"route_id": "demo"}, 3)
    _steps(s, 1.0)
    assert s.state.start_wait["phase"] == "pedalage" and s.state.cadence > 30
    _steps(s, 1.2)
    assert s.state.session_state == "RUNNING" and s.state.start_wait is None
    assert s._rec is not None and s.state.t < 0.2
    assert "start_wait" not in s.state.to_dict()


def test_scene_of_another_route_does_not_count(tmp_path):
    s = _session(tmp_path)
    s.server.engine_connected = True
    s._on_command("scene_ready", {"route_id": "autre"}, 2)
    s._on_command("start", {}, 3)
    _steps(s, 3.0)
    assert s.state.session_state == "READY" and s.state.start_wait["phase"] == "decor"


def test_pause_cancels_the_wait(tmp_path):
    s = _session(tmp_path)
    s._on_command("start", {}, 2)
    assert s.state.start_wait is not None
    s._on_command("pause", {}, 3)
    assert s.state.session_state == "READY" and s.state.start_wait is None and s._start_gate is None
    _steps(s, 2.0)
    assert s.state.session_state == "READY"


def test_immediate_mode_starts_at_once(tmp_path):
    s = _session(tmp_path, mode="immediat")
    s._on_command("start", {}, 2)
    assert s.state.session_state == "RUNNING" and s.state.start_wait is None


def test_rogue_run_has_no_scene_to_wait_for(tmp_path):
    # Run Cyber-Rogue : pas de parcours (route_id nul), la scène du mode ne charge pas de tuiles.
    s = _session(tmp_path)
    s.server.engine_connected = True
    s._on_command("start_run", {"objective": "threshold", "duration_min": 45, "seed": 3}, 2)
    assert s.state.session_state == "READY" and s.state.route_id is None
    s._on_command("start", {}, 3)
    _steps(s, 1.0)
    assert s.state.start_wait["phase"] == "pedalage"
    _steps(s, 1.2)
    assert s.state.session_state == "RUNNING"
