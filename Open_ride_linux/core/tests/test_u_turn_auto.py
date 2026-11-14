"""Demi-tour automatique au bout d'un parcours en ligne pendant un entraînement ERG ou un test de FTP (lot N26) :
l'entraînement n'est plus coupé par l'arrivée ; le cycliste repart dans l'autre sens sans s'arrêter, autant de
fois qu'il le faut ; une fois l'entraînement fini (ou hors entraînement), le bout du parcours termine la séance."""

from __future__ import annotations

import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.demo_world import write_world
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.workout import ErgController

LENGTH_M = 1200.0
ZWO = '<workout_file><name>Court</name><workout><SteadyState Duration="420" Power="0.8"/></workout></workout_file>'


def make_session(tmp_path, monkeypatch, port, workout_id: str | None = "court"):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    routes = tmp_path / "routes"
    routes.mkdir(parents=True, exist_ok=True)
    write_world(routes, "aller", LENGTH_M, created="2026-11-14T00:00:00+00:00", grade=lambda s: 0.0)
    wk = tmp_path / "wk"
    wk.mkdir(exist_ok=True)
    (wk / "court.zwo").write_text(ZWO, encoding="utf-8")
    drv = MockDriver(base_power_w=250.0, ramp_amplitude_w=0.0)
    s = CoreSession(cfg, driver=drv, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=routes, workouts_dir=wk)
    s._on_command("select_route", {"route_id": "aller"}, 1)
    if workout_id is not None:
        s._on_command("select_workout", {"workout_id": workout_id}, 2)
    s._on_command("start", {}, 3)
    assert s.state.session_state == "RUNNING"
    return s


def ride_until(s, cond, dt=0.1, limit=60000):
    t = 100.0
    for _ in range(limit):
        if cond():
            return
        s._step(dt, t)
        t += dt
    raise AssertionError("condition jamais atteinte")


def test_workout_turns_at_each_end_then_finishes_after_the_workout(tmp_path, monkeypatch):
    s = make_session(tmp_path, monkeypatch, 7380)
    assert isinstance(s.erg, ErgController)
    ride_until(s, lambda: s.physics.direction < 0)          # bout du parcours : demi-tour, pas d'arrivée
    assert s.state.session_state == "RUNNING" and s.state.dir == -1
    assert s.physics.s == pytest.approx(LENGTH_M, abs=1.0) and s.physics.v > 5.0   # sans s'arrêter
    ride_until(s, lambda: s.physics.direction > 0)          # retour au départ : nouveau demi-tour
    assert s.state.session_state == "RUNNING" and s.state.dir is None
    assert s.physics.s == pytest.approx(0.0, abs=1.0)
    assert s.physics.distance > 2 * LENGTH_M - 2.0          # distance du journal toujours croissante
    ride_until(s, lambda: s.erg is None)                    # entraînement fini : retour au SIM
    assert s.state.workout_done is not None and s.state.session_state == "RUNNING"
    ride_until(s, lambda: s.state.session_state == "FINISHED")   # bout suivant : arrivée ordinaire
    assert s.state.summary is not None and s.state.summary["distance_m"] > 3 * LENGTH_M


def test_ftp_ramp_turns_too(tmp_path, monkeypatch):
    s = make_session(tmp_path, monkeypatch, 7384, workout_id="ftp_test:ramp")
    assert isinstance(s.erg, ErgController)
    ride_until(s, lambda: s.physics.direction < 0 or s.state.session_state != "RUNNING")
    assert s.state.session_state == "RUNNING" and s.state.dir == -1


def test_sim_session_still_finishes_at_the_end(tmp_path, monkeypatch):
    s = make_session(tmp_path, monkeypatch, 7388, workout_id=None)
    ride_until(s, lambda: s.state.session_state == "FINISHED")
    assert s.physics.direction > 0 and s.physics.s >= LENGTH_M


def test_free_erg_still_finishes_at_the_end(tmp_path, monkeypatch):
    s = make_session(tmp_path, monkeypatch, 7392, workout_id=None)
    s._on_command("pause", {}, 10)
    s._on_command("set_ride_mode", {"mode": "erg", "target_w": 200}, 11)
    s._on_command("resume", {}, 12)
    assert s.erg is not None and not isinstance(s.erg, ErgController)
    ride_until(s, lambda: s.state.session_state == "FINISHED")
    assert s.physics.direction > 0


def test_journal_records_the_automatic_u_turn(tmp_path, monkeypatch):
    s = make_session(tmp_path, monkeypatch, 7396)
    path = s._rec.path
    ride_until(s, lambda: s.physics.direction < 0)
    s._on_command("end_session", {"save": True}, 20)
    assert s.state.session_state == "FINISHED"
    assert '"u_turn"' in path.read_text(encoding="utf-8")
