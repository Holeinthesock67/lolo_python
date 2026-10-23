"""Tests de contrat IPC (SRS §12, contrat §8) : chaque trame émise par le core valide son schéma."""

import asyncio
import json
import re
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.ipc_server import IpcServer, IpcState
from openride_core.mock_driver import MockDriver, TrainerMetrics
from openride_core.session import CoreSession

CONTRACTS = Path(__file__).resolve().parents[2] / "docs" / "contracts"
IPC_DIR = CONTRACTS / "ipc"
MAX_DATAGRAM = 1400


def schema(name: str) -> dict:
    return json.loads((IPC_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def assert_valid(msg: dict) -> None:
    errors = [e.message for e in jsonschema.Draft202012Validator(schema(msg["type"])).iter_errors(msg)]
    assert not errors, f"{msg['type']} invalide : {errors}"
    assert len(json.dumps(msg, separators=(",", ":")).encode()) <= MAX_DATAGRAM


class Capture:
    """Remplace IpcServer.send_raw pour garder les trames émises."""

    def __init__(self, server: IpcServer) -> None:
        self.frames: list[dict] = []
        server.send_raw = self.frames.append   # type: ignore[method-assign]

    def of(self, typ: str) -> list[dict]:
        return [f for f in self.frames if f["type"] == typ]


def make_session(tmp_path, monkeypatch, driver=None, port=5900):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    s = CoreSession(cfg, driver=driver or MockDriver(), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal",
                       routes_root=tmp_path / "routes")
    return s, Capture(s.server)


def run_steps(s, n, t0=100.0):
    for i in range(n):
        s._step(0.02, t0 + i * 0.02)


def test_all_message_schemas_exist():
    for name in ("state", "cmd", "hello", "hello_ack", "heartbeat", "input", "error", "shutdown", "bye"):
        jsonschema.Draft202012Validator.check_schema(schema(name))


def test_state_frames_in_every_session_state(tmp_path, monkeypatch):
    async def scenario():
        s, cap = make_session(tmp_path, monkeypatch)
        seen = []

        def snap():
            s.server.send_state(s.state)
            seen.append((s.state.session_state, s.state.pause_reason))

        snap()                                                   # IDLE
        s._on_command("select_route", {"route_id": "demo"}, 1); snap()       # READY
        s._on_command("start", {}, 2); run_steps(s, 120); snap()             # RUNNING
        for reason in ("user", "engine_lost", "trainer_lost", "recording_failed"):
            s._set_state("PAUSED", reason); snap()
        s._set_state("RUNNING"); run_steps(s, 60, 200.0)
        s._on_command("end_session", {"save": True}, 3); snap()             # FINISHED avec FIT
        assert s.state.summary["fit_path"]
        s._on_command("select_route", {"route_id": "demo"}, 4)
        s._on_command("start", {}, 5); run_steps(s, 60, 300.0)
        s._on_command("end_session", {"save": False}, 6); snap()            # FINISHED sans FIT
        assert s.state.summary["fit_path"] is None
        s._set_state("ERROR"); snap()
        for frame in cap.of("state"):
            assert_valid(frame)
        assert {st for st, _ in seen} >= {"IDLE", "READY", "RUNNING", "PAUSED", "FINISHED", "ERROR"}
    asyncio.run(scenario())


def test_hello_ack_input_error_shutdown(tmp_path, monkeypatch):
    async def scenario():
        s, cap = make_session(tmp_path, monkeypatch, port=5910)
        s.server._handle_message({"type": "hello", "v": 1, "engine_version": "test"})
        s._handle_input(__import__("openride_core.zwift_click", fromlist=["InputEvent"]).InputEvent.PLUS_LONG)
        s.server.send_error("route_not_found", "absent")
        s.server.send_shutdown()
        s.server._handle_message({"type": "hello", "v": 2, "engine_version": "futur"})   # version_mismatch
        for typ in ("hello_ack", "input", "error", "shutdown"):
            assert cap.of(typ), f"aucune trame {typ}"
        for frame in cap.frames:
            assert_valid(frame)
    asyncio.run(scenario())


def contract_json_blocks() -> list[dict]:
    text = (CONTRACTS / "ipc_v1.md").read_text(encoding="utf-8")
    return [json.loads(b) for b in re.findall(r"```json\n(.*?)\n```", text, re.S)]


def test_contract_examples_are_valid():
    state, erg, cmd = contract_json_blocks()
    assert_valid(state)
    assert_valid({**state, "mode": "ERG", "erg": erg})
    assert_valid(cmd)


def test_full_state_frame_fits_in_datagram():
    st = IpcState(route_id="col-du-galibier-par-le-lautaret-version-longue", route_length_m=48000.0,
                  hr=172, mode="ERG", summary=None,
                  erg={"workout_name": "Seuil 2x20 avec rampes et sprints", "block_index": 12,
                       "block_count": 40, "block_type": "interval_on", "block_remaining_s": 512.25,
                       "block_total_s": 1200.0, "target_w": 238.0, "next_target_w": 125.0,
                       "bias_pct": 102.0, "paused": False})
    frame = {**st.to_dict(), "seq": 123456789,
             "bots": [{"id": f"bot-{i}", "s": 12873.456 + i, "v": 9.123} for i in range(10)]}
    size = len(json.dumps(frame, separators=(",", ":")).encode())
    assert size <= MAX_DATAGRAM, f"trame de {size} octets"
