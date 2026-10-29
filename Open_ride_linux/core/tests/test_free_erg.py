"""Lot O18 : ERG d'une session libre (bascule SIM / ERG / ERG cadence depuis la pause, cadence verrouillée)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from test_ble_sim import READY, Rig, wait_for
from test_resume import crash, last_record
from test_workout import make_session, run, workouts_dir  # noqa: F401 (fixture)

from openride_core import fit_export
from openride_core.config import Config
from openride_core.free_erg import (
    CADENCE_BAND_PCT,
    CADENCE_DEFAULT_RPM,
    POWER_MIN_W,
    RATE_MAX_W_PER_S,
    CadenceLock,
    FreeErg,
    start_cadence,
    start_power,
)
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.zwift_click import InputEvent

SCHEMAS = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
FTP = 250.0


def erg_schema() -> Draft202012Validator:
    state = json.loads((SCHEMAS / "state.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(state["properties"]["erg"])


def ride(lock: CadenceLock, cadence: float, seconds: float, dt: float = 0.02) -> None:
    for _ in range(round(seconds / dt)):
        lock.step(dt, cadence)


# --- contrôleurs purs ----------------------------------------------------------------------

def test_start_values():
    assert start_power(247.4, FTP) == 245
    assert start_power(None, FTP) == start_power(10.0, FTP) == 150   # 60 % de la FTP
    assert start_cadence(88.0) == 90 and start_cadence(91.0) == 90
    assert start_cadence(0.0) == start_cadence(None) == CADENCE_DEFAULT_RPM
    assert start_cadence(150.0) == 120


def test_free_erg_bias_like_a_workout():
    erg = FreeErg(200)
    assert erg.target_active and erg.target_w == 200 and not erg.is_freeride
    erg.change_bias(+1)
    assert erg.target_w == 204 and erg.bias_pct == 102
    erg.change_bias(+50)
    assert erg.bias_pct == 120 and erg.target_w == 240   # borne de l'entraînement
    erg.paused = True
    assert not erg.target_active
    d = erg.to_dict()
    assert d["kind"] == "free" and d["block_count"] == 1 and d["next_target_w"] is None
    assert list(erg_schema().iter_errors(d)) == []


def test_cadence_lock_band_and_direction():
    lock = CadenceLock(90, 200, FTP)
    assert lock.low_rpm == pytest.approx(90 * (1 - CADENCE_BAND_PCT / 100))
    assert lock.high_rpm == pytest.approx(103.5)
    ride(lock, 95.0, 10.0)                       # dans la plage : la puissance ne bouge pas
    assert lock.target_w == 200 and lock.zone == "in"
    ride(lock, 112.0, 5.0)                       # trop vite : la puissance monte
    assert lock.zone == "high" and 205 < lock.target_w <= 200 + RATE_MAX_W_PER_S * 5
    w = lock.target_w
    ride(lock, 60.0, 5.0)                        # trop lent : elle baisse
    assert lock.zone == "low" and lock.target_w < w
    d = lock.to_dict()
    assert d["kind"] == "cadence" and d["cadence_zone"] == "low" and d["cadence_target_rpm"] == 90
    assert list(erg_schema().iter_errors(d)) == []


def test_cadence_lock_bounds_rate_and_pause():
    lock = CadenceLock(90, 200, FTP)
    ride(lock, 0.0, 60.0)                        # arrêt : au plus 10 W/s, jusqu'au plancher
    assert lock.target_w == POWER_MIN_W
    ride(lock, 130.0, 120.0)
    assert lock.target_w == round(FTP * 1.5)     # plafond : 150 % de la FTP
    lock.paused = True
    w = lock.target_w
    ride(lock, 0.0, 10.0)
    assert lock.target_w == w and not lock.target_active


def test_cadence_lock_bias_changes_cadence_by_2_percent():
    lock = CadenceLock(90, 200, FTP)
    lock.change_bias(+1)
    assert lock.cadence_target == 92 and lock.target_w == 200   # 90 × 1,02 = 91,8
    lock.change_bias(-6)
    assert lock.bias_pct == 90 and lock.cadence_target == 81     # 90 × 0,90
    lock.change_bias(-20)
    assert lock.bias_pct == 80 and lock.cadence_target == 72


def test_cadence_lock_does_not_oscillate_with_a_rider_that_reacts():
    """Cycliste qui tourne 10 tr/min plus lentement par tranche de 50 W au-dessus de 200 W."""
    lock = CadenceLock(90, 150, FTP)
    seen = []
    for i in range(round(120 / 0.02)):
        cadence = 120.0 - (lock.target_w - 150) / 5.0
        lock.step(0.02, cadence)
        if i % 50 == 0:
            seen.append(lock.target_w)
    tail = seen[-40:]
    assert max(tail) - min(tail) <= 2           # stable après la correction
    assert lock.low_rpm <= 120.0 - (lock.target_w - 150) / 5.0 <= lock.high_rpm


# --- séance (trainer simulé) ----------------------------------------------------------------

def test_session_switches_sim_erg_cadence_and_back(tmp_path, monkeypatch, workouts_dir):
    async def scenario():
        s, driver, errors = make_session(tmp_path, monkeypatch, workouts_dir, port=6510)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        run(s, 3.0)
        p3 = s.state.power_3s
        s._on_command("pause", {}, 3)
        s._on_command("set_ride_mode", {"mode": "erg"}, 4)
        assert s.state.mode == "ERG" and s.state.erg["kind"] == "free" and not errors
        assert s.state.erg["target_w"] == 5 * round(p3 / 5) and s.state.erg["paused"]
        s._on_command("resume", {}, 5)
        run(s, 0.5)
        assert driver.target_power_w == s.state.erg["target_w"]
        gear = s.gearing.k
        s._handle_input(InputEvent.PLUS_SHORT)          # ± = intensité, pas de braquet
        assert s.state.erg["bias_pct"] == 102 and s.gearing.k == gear
        s._handle_input(InputEvent.Z_SHORT)             # pas de blocs : rien ne casse
        assert s.state.mode == "ERG"
        s._on_command("set_ride_mode", {"mode": "erg", "target_w": 180}, 6)
        assert s.state.erg["target_w"] == 180 and s.state.erg["bias_pct"] == 100
        s._on_command("set_ride_mode", {"mode": "cadence", "cadence_rpm": 90}, 7)
        e = s.state.erg
        assert e["kind"] == "cadence" and e["target_w"] == 180 and e["cadence_target_rpm"] == 90
        driver.base_cadence_rpm = 115.0                  # trop vite : la cible monte
        run(s, 4.0)
        assert s.state.erg["target_w"] > 185 and driver.target_power_w == s.state.erg["target_w"]
        s._handle_input(InputEvent.MINUS_SHORT)
        assert s.state.erg["cadence_target_rpm"] == 88
        s._on_command("set_ride_mode", {"mode": "sim"}, 8)
        assert s.state.mode == "SIM" and s.state.erg is None
        run(s, 0.5)
        assert driver.target_power_w is None            # pente de nouveau envoyée
        assert not errors
    asyncio.run(scenario())


def test_set_ride_mode_refusals(tmp_path, monkeypatch, workouts_dir):
    async def scenario():
        s, driver, errors = make_session(tmp_path, monkeypatch, workouts_dir, port=6520)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("set_ride_mode", {"mode": "erg"}, 2)           # hors séance
        assert errors[-1][0] == "busy" and s.state.mode == "SIM"
        s._on_command("select_workout", {"workout_id": "reference"}, 3)
        s._on_command("start", {}, 4)
        s._on_command("set_ride_mode", {"mode": "sim"}, 5)           # entraînement en cours
        assert errors[-1][0] == "busy" and s.state.erg["kind"] == "workout"
        s._on_command("end_session", {"save": False}, 6)
        s._on_command("select_workout", {"workout_id": None}, 7)
        s._on_command("select_route", {"route_id": "demo"}, 8)
        s._on_command("start", {}, 9)
        for bad in ({"mode": "turbo"}, {}, {"mode": "erg", "target_w": "200"},
                    {"mode": "cadence", "cadence_rpm": float("nan")}, {"mode": "erg", "target_w": True}):
            n = len(errors)
            s._on_command("set_ride_mode", bad, 10)
            assert len(errors) == n + 1 and errors[-1][0] == "bad_args" and s.state.mode == "SIM"
    asyncio.run(scenario())


def test_journal_and_resume_keep_the_free_erg(tmp_path, monkeypatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    wall = [1_790_000_000.0]
    monkeypatch.setattr(time, "time", lambda: wall[0])

    def make(port: int) -> CoreSession:
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        s = CoreSession(cfg, driver=MockDriver(base_power_w=200.0), inputs=[NullProvider()],
                        journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes",
                        workouts_dir=tmp_path / "Workouts")
        s.server.send_raw = lambda m: None
        return s

    def run_for(s: CoreSession, seconds: float) -> None:
        for _ in range(round(seconds / 0.02)):
            wall[0] += 0.02
            s._step(0.02, wall[0])

    a = make(6530)
    a._on_command("select_route", {"route_id": "demo"}, 1)
    a._on_command("start", {}, 2)
    run_for(a, 2.0)
    a._on_command("set_ride_mode", {"mode": "cadence", "cadence_rpm": 95}, 3)
    run_for(a, 3.0)
    path = crash(a)
    last = last_record(path)
    assert last["mode"] == "ERG" and last["erg_kind"] == "cadence" and last["cadence_target_rpm"] == 95
    assert last["block"] is None and last["target_w"] is not None
    b = make(6532)
    b.resume_session(path)
    e = b.state.erg
    assert e["kind"] == "cadence" and e["cadence_target_rpm"] == 95 and e["paused"]
    assert e["target_w"] == round(last["target_w"])


def test_ble_sim_trainer_follows_the_cadence_lock(tmp_path, monkeypatch):
    """Vrai pilote FTMS contre le trainer simulé : la cible ERG suit la cadence du cycliste."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")

    async def scenario():
        rig = Rig(READY).start()
        rig.trainer.rider.update(cadence_rpm=110.0)       # le cycliste tourne trop vite
        await wait_for(lambda: rig.driver.status == "CONNECTED")
        await wait_for(lambda: rig.driver.poll().cadence_rpm > 100)
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = 6540, 6541
        s = CoreSession(cfg, driver=rig.driver, inputs=[NullProvider()], journal_dir=tmp_path / "j",
                        routes_root=tmp_path / "routes", workouts_dir=tmp_path / "w")
        s.server.send_raw = lambda m: None
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        s._on_command("set_ride_mode", {"mode": "cadence", "cadence_rpm": 85}, 3)
        start_w = s.state.erg["target_w"]
        loop = asyncio.get_running_loop()
        t0 = last = loop.time()
        while loop.time() - t0 < 3.0:
            await asyncio.sleep(0.02)
            now = loop.time()
            s._step(now - last, now)
            last = now
        assert s.state.erg["cadence_zone"] == "high" and s.state.erg["target_w"] > start_w + 5
        await wait_for(lambda: rig.trainer.mode == "erg" and rig.trainer.target_w is not None
                       and rig.trainer.target_w > start_w)
        s._on_command("set_ride_mode", {"mode": "sim"}, 4)
        s._step(0.02, loop.time())
        await wait_for(lambda: rig.trainer.mode == "sim")
        await rig.stop()
    asyncio.run(scenario())
