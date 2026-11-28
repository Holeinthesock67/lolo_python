"""Échauffement commun avant une course (demande du 21 novembre, `warmup.py`) et son branchement au départ."""

from __future__ import annotations

import pytest

from openride_core import track as track_mod
from openride_core import warmup as W
from openride_core.config import Config
from openride_core.input_providers import InputEvent
from openride_core.session import CoreSession
from openride_core.start_gate import StartGate

DT = 0.02
RIDING = dict(scene_ready=True, trainer_connected=True, cadence_rpm=80.0, power_w=150.0)


def test_profile_lasts_the_minutes_and_ends_with_two_openers():
    for minutes in (3, 5, 10, 15, 20):
        wk = W.profile(minutes)
        assert wk.duration_s == pytest.approx(minutes * 60.0)
        assert [b.type for b in wk.blocks[-4:]] == ["interval_on", "interval_off"] * 2
    w = W.Warmup(10, 250.0)
    assert w.target_w == round(0.45 * 250)                     # montée douce depuis 45 % de la FTP
    for bad in (0, 2, 21, 10.0, True):
        with pytest.raises(ValueError):
            W.profile(bad)


def test_needed_for_races_only():
    assert all(W.needed(m, 10) for m in W.RACE_MODES)
    assert W.needed("race", 10)                                  # Course en tours (retours du 28 novembre)
    assert not W.needed(None, 10) and not W.needed("wtf", 10) and not W.needed("rogue", 10)
    assert not W.needed("survivor", 0) and not W.needed("survivor", 2)
    assert not W.needed("track", 10, race=track_mod.EVENTS["free"].race)
    assert all(W.needed("track", 10, race=spec.race) for eid, spec in track_mod.EVENTS.items() if eid != "free")


def test_warmup_runs_to_the_end_then_skip_and_dict():
    w = W.Warmup(3, 200.0)
    done = False
    for _ in range(int(3 * 60 / 0.5) + 1):
        done = w.step(0.5) or done
    assert done and w.done and w.left_s == 0.0
    w = W.Warmup(5, 200.0)
    w.step(1.0)
    d = w.to_dict()
    assert d["total_s"] == 300.0 and d["left_s"] == 299.0 and d["block"] == "warmup" and not d["done"]
    assert d["next_target_w"] == 140
    w.skip()
    assert w.done and not w.step(1.0)


def test_gate_warms_up_between_trainer_and_pedalling():
    g = StartGate(cadence_rpm=30, duree_s=1, attente_decor_s=60, warmup=W.Warmup(3, 200.0))
    for _ in range(int(60 / DT)):
        assert not g.update(DT, **RIDING)
    assert g.phase == "echauffement" and g.to_dict()["warmup"]["left_s"] == pytest.approx(120.0, abs=0.1)
    # trainer perdu : l'étape retombe, l'échauffement garde son avance
    g.update(DT, **{**RIDING, "trainer_connected": False})
    assert g.phase == "trainer" and g.warmup.elapsed_s == pytest.approx(60.0, abs=0.1)
    g.warmup.skip()
    opened = False
    for _ in range(int(1.5 / DT)):
        opened = g.update(DT, **RIDING) or opened
    assert opened and g.open


def _session(tmp_path, minutes: int = 5) -> CoreSession:
    cfg = Config()
    cfg.drivers.trainer = "mock"
    cfg.drivers.input = "none"
    cfg.depart.mode = "pedalage"
    cfg.depart.duree_s = 1
    cfg.depart.echauffement_min = minutes
    cfg.survivor.opponents, cfg.survivor.spacing_km = 2, 2   # le Dernier survivant tient sur la démo
    s = CoreSession(cfg, routes_root=tmp_path / "routes", journal_dir=tmp_path / "journal")
    errors: list = []
    s.server.send_error = lambda code, msg: errors.append((code, msg))
    s.server.send_input_event = lambda ev: None
    s.errors = errors
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s.server.engine_connected = True
    s._on_command("scene_ready", {"route_id": "demo"}, 2)
    return s


def _steps(s: CoreSession, seconds: float) -> None:
    for i in range(int(round(seconds / DT))):
        s._step(DT, i * DT)


def test_survivor_starts_after_an_erg_warmup_skipped_with_z(tmp_path):
    s = _session(tmp_path)
    s._on_command("start", {"mode": "survivor"}, 3)
    _steps(s, 3.0)
    wait = s.state.start_wait
    assert s.state.session_state == "READY" and wait["phase"] == "echauffement"
    assert wait["warmup"]["target_w"] == s.driver.target_power_w > 0      # trainer en ERG, watts directs
    assert s.state.t == 0.0 and s.state.s == 0.0 and s._rec is None        # rien ne compte pendant l'échauffement
    s._handle_input(InputEvent.PLUS_SHORT)                                 # + : cible +2 %, comme en ERG
    _steps(s, 0.1)
    assert s.driver.target_power_w > wait["warmup"]["target_w"]
    s._handle_input(InputEvent.Z_SHORT)                                    # Z : on part
    _steps(s, 2.0)
    assert s.state.session_state == "RUNNING" and s.survivor is not None
    assert s.driver.target_power_w is None                                 # de retour en SIM


def test_skip_warmup_command_and_classic_ride_has_none(tmp_path):
    s = _session(tmp_path)
    s._on_command("start", {"mode": "survivor"}, 3)
    _steps(s, 1.0)
    s._on_command("skip_warmup", {}, 4)
    _steps(s, 2.0)
    assert s.state.session_state == "RUNNING"
    s2 = _session(tmp_path / "b")
    s2._on_command("start", {}, 3)
    _steps(s2, 2.0)
    assert s2.state.session_state == "RUNNING"                             # balade libre : pas d'échauffement


def test_no_warmup_when_zero_and_pause_cancels_erg(tmp_path):
    s = _session(tmp_path, minutes=0)
    s._on_command("start", {"mode": "survivor"}, 3)
    _steps(s, 2.0)
    assert s.state.session_state == "RUNNING"
    s = _session(tmp_path / "c")
    s._on_command("start", {"mode": "survivor"}, 3)
    _steps(s, 2.0)
    assert s.driver.target_power_w is not None
    s._on_command("pause", {}, 4)
    assert s._start_gate is None and s.driver.target_power_w is None       # Y : retour à l'écran Prêt, trainer en SIM


def test_race_mode_is_warmed_up_too_and_z_skips_it(tmp_path):
    """Course (manche « Course en tours » de la ligue) : même échauffement que les autres courses (28 novembre)."""
    s = _session(tmp_path)
    s._on_command("start", {"mode": "race"}, 3)
    _steps(s, 3.0)
    assert not s.errors, s.errors
    wait = s.state.start_wait
    assert s.state.session_state == "READY" and wait["phase"] == "echauffement"
    assert s.driver.target_power_w == wait["warmup"]["target_w"] > 0
    s._handle_input(InputEvent.Z_SHORT)                                    # écourté par le cycliste
    _steps(s, 2.0)
    assert s.state.session_state == "RUNNING" and s.driver.target_power_w is None
