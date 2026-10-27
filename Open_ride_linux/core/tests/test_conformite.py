"""Lot C : écarts au contrat IPC relevés par l'audit du 23 octobre 2026."""

import asyncio
from pathlib import Path

from openride_core import fit_export, ftms
from openride_core.config import BikeConfig, Config, TrainerConfig
from openride_core.ftms_driver import FtmsDriver
from openride_core.input_providers import NullProvider
from openride_core.ipc_server import IpcServer
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from test_drivers_session import FakeClient, fake_finder, ibd, make_factory, wait_for


def make_session(tmp_path, monkeypatch, cfg=None, driver=None, port=5950):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = cfg or Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    s = CoreSession(cfg, driver=driver or MockDriver(), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal",
                       routes_root=tmp_path / "routes")
    frames = []
    s.server.send_raw = frames.append
    return s, frames


def steps(s, n, t0):
    for i in range(n):
        s._step(0.02, t0 + i * 0.02)


# C1 ---------------------------------------------------------------------------------------

def test_c1_engine_restart_resets_cmd_id():
    got = []
    srv = IpcServer(port_state=5960, port_commands=5961, on_command=lambda n, a, i: got.append((n, i)))
    srv.send_raw = lambda m: None
    srv._handle_message({"type": "hello", "v": 1, "engine_version": "a"})
    srv._handle_message({"type": "cmd", "v": 1, "cmd_id": 5, "name": "pause", "args": {}})
    srv._handle_message({"type": "hello", "v": 1, "engine_version": "b"})     # engine relancé
    srv._handle_message({"type": "cmd", "v": 1, "cmd_id": 1, "name": "resume", "args": {}})
    assert got == [("pause", 5), ("resume", 1)]


# C2 ---------------------------------------------------------------------------------------

def test_c2_journal_failure_pauses_then_recovers(tmp_path, monkeypatch):
    async def scenario():
        s, frames = make_session(tmp_path, monkeypatch, port=5962)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        steps(s, 250, 10.0)                                  # 5 s enregistrées
        s._rec._writer._fh.close()                           # panne : fichier fermé
        steps(s, 100, 15.0)                                  # la boucle ne doit pas tomber
        assert (s.state.session_state, s.state.pause_reason) == ("PAUSED", "recording_failed")
        assert any(f["type"] == "error" and f["code"] == "recording_failed" for f in frames)
        first_path = s._rec.path
        s._on_command("resume", {}, 3)
        assert s.state.session_state == "RUNNING" and s._rec.path != first_path
        steps(s, 150, 30.0)
        new_path = s._rec.path
        s._on_command("end_session", {"save": True}, 4)
        lines = list(read_journal(new_path))
        ts = [ln["t"] for ln in lines if ln.get("kind") == "record"]
        assert ts == sorted(set(ts)), "relevés en double ou désordonnés"
        assert all(b - a <= 1.05 for a, b in zip(ts, ts[1:])), "trou dans le journal"   # pas de 20 ms
        assert [ln["event"] for ln in lines if ln.get("kind") == "event"][:1] == ["start"]
        fit = s.state.summary["fit_path"]
        assert fit and list(fit_export.iter_records(__import__("pathlib").Path(fit)))
    asyncio.run(scenario())


def test_c2_fit_produced_even_if_journal_unusable(tmp_path, monkeypatch):
    async def scenario():
        s, frames = make_session(tmp_path, monkeypatch, port=5964)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        steps(s, 200, 10.0)
        s._rec._writer._fh.close()
        steps(s, 10, 14.0)
        s._on_command("end_session", {"save": True}, 3)       # sans reprise du journal
        assert s.state.session_state == "FINISHED" and s.state.summary["fit_path"]
    asyncio.run(scenario())


# C3 ---------------------------------------------------------------------------------------

def test_c3_summary_fields(tmp_path, monkeypatch):
    async def scenario():
        s, _ = make_session(tmp_path, monkeypatch, port=5966)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        steps(s, 200, 10.0)
        s._on_command("end_session", {"save": True}, 3)
        assert {"duration_s", "distance_m", "avg_power_w", "fit_path"}.issubset(set(s.state.summary))
        assert s.state.summary["avg_power_w"] > 0
    asyncio.run(scenario())


# C4 ---------------------------------------------------------------------------------------

def test_c4_control_refused_twice_goes_to_error(tmp_path, monkeypatch):
    async def scenario():
        client = FakeClient([ftms.INDOOR_BIKE_DATA, ftms.SUPPORTED_POWER_RANGE])
        client.read_gatt_char = _power_range_reader(0, 1000)
        drv = FtmsDriver(TrainerConfig(power_smooth_tau_s=0.0), BikeConfig(),
                         device_finder=fake_finder, client_factory=make_factory(client))
        task = asyncio.create_task(drv.run())
        await wait_for(lambda: ftms.CONTROL_POINT in client.cbs)
        client.cbs[ftms.INDOOR_BIKE_DATA](None, bytearray(ibd(150)))

        assert drv.power_range == (0.0, 1000.0)
        drv.set_target_power(1500)
        assert drv._want.value == 1000.0                    # borné à la plage annoncée

        s, frames = make_session(tmp_path, monkeypatch, driver=drv, port=5968)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        refuse = bytearray([ftms.OP_RESPONSE, ftms.OP_SET_SIM_PARAMS, 0x05])
        for _ in range(3):                                   # refus initial puis 2 reprises
            client.cbs[ftms.CONTROL_POINT](None, refuse)
        client.cbs[ftms.INDOOR_BIKE_DATA](None, bytearray(ibd(150)))
        s._step(0.02, 50.0)
        assert s.state.session_state == "ERROR"
        assert any(f["type"] == "error" and f["code"] == "trainer_control_refused" for f in frames)
        s._on_command("start", {}, 3)
        assert s.state.session_state == "ERROR"             # pas de démarrage depuis ERROR
        s._on_command("select_route", {}, 4)
        assert s.state.session_state == "READY" and not drv.control_refused
        drv.stop()
        await asyncio.wait_for(task, 3)
    asyncio.run(scenario())


def _power_range_reader(lo, hi):
    import struct

    async def read(uuid):
        if uuid == ftms.SUPPORTED_POWER_RANGE:
            return struct.pack("<hhH", lo, hi, 1)
        return struct.pack("<II", 0x4402, 0x2008)
    return read


# C5 ---------------------------------------------------------------------------------------

def test_c5_hello_ack_reflects_config(tmp_path, monkeypatch):
    cfg = Config()
    cfg.rider.ftp_w, cfg.gearing.n_gears, cfg.gearing.start_gear = 280.0, 22, 11
    s, frames = make_session(tmp_path, monkeypatch, cfg=cfg, port=5970)
    s.server._handle_message({"type": "hello", "v": 1, "engine_version": "t"})
    ack = [f for f in frames if f["type"] == "hello_ack"][0]
    progression = ack["config"].pop("progression")   # révision 1.4, lot V11 : voir test_progression_session.py
    assert progression["level"] == 1 and progression["coins"] == 0
    rogue = ack["config"].pop("rogue")            # bloc Cyber-Rogue (lot R8) : testé dans test_rogue_session
    assert rogue["cp_w"] == 280.0
    assert ack["config"] == {"ftp_w": 280.0, "gears_total": 22, "theme": "default", "chart": "reduced",
                             "difficulty_pct": 50,
                             "modes": ["ride", "erg", "open_world", "rogue"],     # modes : révision 1.3, monde ouvert 1.5, Cyber-Rogue 1.4
                             "open_world_dir": str(Path(cfg.open_world.cache_dir).expanduser() / "seances")}


# C6 ---------------------------------------------------------------------------------------

def test_c6_difficulty_halves_sent_grade_not_speed(tmp_path, monkeypatch):
    async def ride(pct, port):
        cfg = Config()
        cfg.trainer.difficulty_pct = pct
        cfg.trainer.grade_rate_up_pct_per_s = cfg.trainer.grade_rate_down_pct_per_s = 1000.0  # sans lissage
        s, _ = make_session(tmp_path / str(pct), monkeypatch, cfg=cfg, port=port)
        s._on_command("select_route", {}, 1)
        s._on_command("start", {}, 2)
        steps(s, 500, 10.0)
        expected = s.gearing.effective_grade(
            s.route.grade_at(s.physics.s + s.physics.v * cfg.trainer.latency_tau_s))
        return s, expected

    async def scenario():
        full, eff = await ride(100.0, 5972)
        half, _ = await ride(50.0, 5974)
        assert abs(full.state.grade_sent - eff) < 0.05
        assert abs(half.state.grade_sent - eff / 2) < 0.05
        assert abs(full.state.v - half.state.v) < 1e-9     # vitesse virtuelle inchangée
    asyncio.run(scenario())


# C7 ---------------------------------------------------------------------------------------

def test_c7_run_mock_session_is_a_thin_wrapper():
    from openride_core.tools import run_mock_session
    src = open(run_mock_session.__file__, encoding="utf-8").read()
    assert len(src.splitlines()) < 40 and "CoreSession" in src
