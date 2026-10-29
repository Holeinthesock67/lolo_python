"""Lot WTF2 : mode « What the fuck » branché dans la séance (pente, bornes, trame, journal, commandes)."""

import json
import time
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export, garage
from openride_core.bots import ConstantPowerBot
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.wtf.mode import FEEL_MAX_PCT, FEEL_MIN_PCT
from openride_core.wtf.rules import RULE_IDS, load_table
from openride_core.zwift_click import InputEvent

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
DT = 0.02
T0_WALL = 1_790_000_000.0

ERG_ZWO = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file><name>ERG</name><workout><SteadyState Duration="600" Power="0.70"/></workout></workout_file>
"""


def validator(name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads((IPC_DIR / f"{name}.schema.json").read_text("utf-8")))


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(garage, "PROFILE_PATH", tmp_path / "profile.json")
    wall = [T0_WALL]
    monkeypatch.setattr(time, "time", lambda: wall[0])
    workouts = tmp_path / "Workouts"
    workouts.mkdir()
    (workouts / "erg.zwo").write_text(ERG_ZWO, encoding="utf-8")

    def make(port: int, bots=None) -> tuple[CoreSession, list, list]:
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        s = CoreSession(cfg, driver=MockDriver(base_power_w=220.0, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                        routes_root=tmp_path / "routes", workouts_dir=workouts, bots=bots,
                        records_path=tmp_path / "records.json", powerups_path=tmp_path / "powerups.toml",
                        wtf_path=tmp_path / "wtf.toml")
        sent: list[dict] = []
        errors: list[tuple[str, str]] = []
        s.server.send_raw = lambda m, max_size=None: sent.append(m)
        s.server.send_error = lambda code, msg: errors.append((code, msg))
        s.server.send_input_event = lambda ev: None
        s._on_command("select_route", {"route_id": "demo"}, 1)
        return s, sent, errors

    def run(s: CoreSession, seconds: float, check=None) -> None:
        for i in range(int(round(seconds / DT))):
            wall[0] += DT
            s._step(DT, wall[0])
            if i % 15 == 0:
                s._fill_wtf_frame()
                if check:
                    check(s)

    return make, run, tmp_path


def test_wtf_session_bounds_frame_and_summary(env):
    make, run, tmp_path = env
    s, sent, errors = make(6620, bots=[ConstantPowerBot(200.0, bot_id="b1"), ConstantPowerBot(230.0, bot_id="b2")])
    s._on_command("start", {"mode": "wtf"}, 2)
    assert s.state.session_state == "RUNNING" and s.wtf is not None and s.race is None and not errors
    state_v = validator("state")
    seen = set()

    def check(sess):
        assert FEEL_MIN_PCT - 1e-6 <= sess._grade_sent <= FEEL_MAX_PCT + 1e-6
        frame = sess.state.to_dict()
        assert "wtf" in frame and "segment" not in frame
        state_v.validate(frame)
        assert len(json.dumps(frame, ensure_ascii=False).encode()) < 4096
        if frame["wtf"]["event"]:
            seen.add(frame["wtf"]["event"]["id"])

    run(s, 420, check)                           # le parcours de démonstration fait 5 km
    assert len(seen) >= 2, seen
    assert s.state.wtf["skins"] == {"b1": "grandma", "b2": "tractor"}
    s._on_command("end_session", {"save": True}, 3)
    summary = s.state.summary
    assert summary["wtf"]["points"] >= 0 and sum(summary["wtf"]["events"].values()) >= 1
    assert s.wtf is None and s.state.wtf is None
    state_v.validate(s.state.to_dict())
    types = {ln.get("kind") for ln in read_journal(next((tmp_path / "journal").glob("*.jsonl")))}
    assert {"wtf_start", "wtf", "wtf_summary"} <= types


def test_measured_power_untouched_in_journal(env):
    make, run, tmp_path = env
    s, sent, errors = make(6630)
    s._on_command("start", {"mode": "wtf"}, 2)
    run(s, 300)
    assert s._rec.records and all(r["power"] == 220 for r in s._rec.records)


def test_start_refusals_and_erg_switch_refused(env):
    make, run, _ = env
    s, sent, errors = make(6640)
    s._on_command("start", {"mode": "turbo"}, 2)
    assert errors[-1][0] == "bad_args" and s.state.session_state == "READY"
    s._on_command("select_workout", {"workout_id": "erg"}, 3)
    s._on_command("start", {"mode": "wtf"}, 4)
    assert errors[-1][0] == "bad_args" and s.state.session_state == "READY"
    s._on_command("select_workout", {"workout_id": None}, 5)
    s._on_command("start", {"mode": "wtf"}, 6)
    run(s, 1)
    s._on_command("set_ride_mode", {"mode": "erg"}, 7)
    assert errors[-1][0] == "busy" and s.state.mode == "SIM"


def test_rules_commands_write_file_and_apply_live(env):
    make, run, tmp_path = env
    s, sent, errors = make(6650)
    s._on_command("list_wtf_rules", {}, 2)
    msg = sent[-1]
    validator("wtf_rules").validate(msg)
    assert [r["id"] for r in msg["rules"]] == list(RULE_IDS) and all(r["on"] for r in msg["rules"])
    s._on_command("set_wtf_rule", {"id": "clock", "on": False}, 3)
    assert not load_table(tmp_path / "wtf.toml").on("clock")
    assert [r["on"] for r in sent[-1]["rules"] if r["id"] == "clock"] == [False]
    s._on_command("set_wtf_rule", {"id": "licorne", "on": True}, 4)
    assert errors[-1][0] == "wtf_rule_invalid"
    s._on_command("set_wtf_rule", {"id": "clock", "on": "oui"}, 5)
    assert errors[-1][0] == "bad_args"
    s._on_command("start", {"mode": "wtf"}, 6)
    run(s, 1)
    s._fill_wtf_frame()
    assert "clock_h" not in s.state.wtf and "kata" in s.state.wtf
    s._on_command("set_wtf_rule", {"id": "katamari", "on": False}, 7)   # pendant la séance
    s._fill_wtf_frame()
    assert "kata" not in s.state.wtf


def test_chef_refused_with_z(env):
    make, run, tmp_path = env
    (tmp_path / "wtf.toml").write_text("[rules]\n" + "".join(f"{r} = {'true' if r == 'chef' else 'false'}\n"
                                                             for r in RULE_IDS)
                                       + "[director]\nfirst_s = 5\n", encoding="utf-8")
    s, sent, errors = make(6660)
    s._on_command("start", {"mode": "wtf"}, 2)
    run(s, 10)                                   # chef arrivé (4 s) puis cloche soulevée
    assert s.wtf.event.id == "chef" and s.wtf.event.phase == "reveal"
    s._handle_input(InputEvent.Z_SHORT)
    run(s, 0.1)
    assert s.wtf.event is None and s.wtf.vexed


def test_classic_start_unchanged(env):
    make, run, _ = env
    s, sent, errors = make(6670)
    s._on_command("start", {}, 2)
    run(s, 2)
    assert s.wtf is None and s.race is not None and "wtf" not in s.state.to_dict()
