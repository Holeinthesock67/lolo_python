"""Lot VD6 : épreuves de piste branchées dans la séance (départ, trame `track`, journal, FIT, records, bilan)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export, ipc_budget, profile, velodrome
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.records import RecordBook
from openride_core.session import CoreSession

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
DT = 0.02
T0_WALL = 1_790_000_000.0


def validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads((IPC_DIR / "state.schema.json").read_text("utf-8")))


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    wall = [T0_WALL]
    monkeypatch.setattr(time, "time", lambda: wall[0])
    routes = tmp_path / "routes"
    velodrome.write_velodrome(routes)

    def make(port: int, route: str = velodrome.TRACK_ID, power_w: float = 400.0, living: bool = False):
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        cfg.render.living = living
        s = CoreSession(cfg, driver=MockDriver(base_power_w=power_w, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=tmp_path / "journal", routes_root=routes,
                        workouts_dir=tmp_path / "wk", records_path=tmp_path / "records.json",
                        powerups_path=tmp_path / "powerups.toml", wtf_path=tmp_path / "wtf.toml")
        sent: list[dict] = []
        errors: list[tuple[str, str]] = []
        s.server.send_raw = lambda m, max_size=None: sent.append(m)
        s.server.send_error = lambda code, msg: errors.append((code, msg))
        s.server.send_input_event = lambda ev: None
        s._on_command("select_route", {"route_id": route}, 1)
        return s, errors

    def run(s: CoreSession, seconds: float, check=None, until=None) -> None:
        for i in range(int(round(seconds / DT))):
            if s.state.session_state != "RUNNING" or (until and until(s)):
                return
            wall[0] += DT
            s._step(DT, wall[0])
            if i % 25 == 0:
                s.state.bots = [b.to_dict() for b in s.bots] or None
                s._fill_track_frame()
                if check:
                    check(s)

    return make, run, tmp_path


def test_kilo_end_to_end_record_fit_and_summary(env):
    make, run, tmp_path = env
    s, errors = make(6800)
    s._on_command("start", {"mode": "track", "track": {"event": "kilo"}}, 2)
    assert not errors and s.state.session_state == "RUNNING" and s.race is None and s.bots == []
    v = validator()
    frames: list[dict] = []

    def check(sess):
        d = sess.state.to_dict()
        v.validate(d)
        assert "segment" not in d and "powerup" not in d and ipc_budget.size(d) <= 4096
        frames.append(d["track"])

    run(s, 200, check, until=lambda sess: sess.track_event is not None and sess.track_event.finished)
    ev = s.track_event
    assert ev is not None and ev.finished and frames[0]["event"] == "kilo" and frames[0]["laps"] == 4
    s._on_command("end_session", {"save": True}, 3)
    summary = s.state.summary["track"]
    v.validate(s.state.to_dict())
    assert summary["place"] == 1 and summary["record"]["id"] == "track:kilo" and summary["record_rank"] == 1
    assert summary["record"]["time_s"] > 0 and len(summary["laps"]) >= 4
    book = RecordBook.load(tmp_path / "records.json")
    assert book.best(velodrome.TRACK_ID, "track:kilo", False).time_s == pytest.approx(summary["record"]["time_s"], abs=0.01)
    journal = next((tmp_path / "journal").glob("*.jsonl"))
    lines = [json.loads(x) for x in journal.read_text("utf-8").splitlines()]
    kinds = [ln.get("kind") for ln in lines]
    assert "track_start" in kinds and "track_summary" in kinds
    laps = fit_export.lap_starts(lines)
    assert len(laps) == len(summary["laps"])
    out, _ = fit_export.journal_to_fit(journal, tmp_path / "re.fit")
    n_laps = sum(1 for r in fit_export.iter_records(out) if type(r.message).__name__ == "LapMessage")
    # un tour du FIT par passage sur la ligne, plus la fin de séance quand elle vient après le dernier passage
    assert len(laps) >= 4 and len(laps) <= n_laps <= len(laps) + 1


def test_scratch_with_bots_on_the_grid(env):
    make, run, _ = env
    s, errors = make(6810, power_w=300.0)
    s._on_command("start", {"mode": "track", "track": {"event": "scratch", "opponents": 3, "laps": 10}}, 2)
    assert not errors and len(s.bots) == 3 and all(b.s <= s.physics.s for b in s.bots)
    run(s, 30)
    f = s.state.track
    assert f["event"] == "scratch" and f["laps"] == 10 and len(f["ranking"]) == 4 and f["points"] is None
    validator().validate(s.state.to_dict())


def test_pursuit_opponent_starts_on_the_other_side(env):
    make, _, _ = env
    s, errors = make(6820)
    s._on_command("start", {"mode": "track", "track": {"event": "pursuit", "opponents": 1, "distance_m": 3000}}, 2)
    assert not errors and len(s.bots) == 1
    assert s.bots[0].s - s.physics.s == pytest.approx(125.0)


def test_team_pursuit_field(env):
    make, _, _ = env
    s, errors = make(6830)
    s._on_command("start", {"mode": "track", "track": {"event": "team_pursuit", "opponents": 1}}, 2)
    assert not errors and len(s.bots) == 7
    ev = s.track_event
    assert ev.teams["home"].order[0] == "me" and len(ev.teams["home"].order) == 4


@pytest.mark.parametrize("args,why", [
    ({"mode": "track"}, "track"),
    ({"mode": "track", "track": {"event": "nope"}}, "inconnue"),
    ({"mode": "track", "track": {"event": "scratch", "laps": 7}}, "refusé"),
    ({"mode": "track", "track": {"event": "scratch"}, "bots": []}, "plateau"),
    ({"mode": "track", "track": {"event": "kilo"}, "ftp_test": "ramp"}, "SIM"),
])
def test_refused_starts(env, args, why):
    make, _, _ = env
    s, errors = make(6840)
    s._on_command("start", args, 2)
    assert errors and errors[-1][0] == "bad_args" and why in errors[-1][1]
    assert s.state.session_state == "READY" and s.track_event is None


def test_track_events_only_on_a_velodrome(env):
    make, _, _ = env
    s, errors = make(6850, route="demo")
    s._on_command("start", {"mode": "track", "track": {"event": "kilo"}}, 2)
    assert errors and "vélodrome" in errors[-1][1] and s.state.session_state == "READY"


def test_no_traffic_in_the_hall(env):
    make, run, _ = env
    s, errors = make(6860, living=True)
    s._on_command("start", {"mode": "track", "track": {"event": "free", "opponents": 0}}, 2)
    run(s, 5)
    assert not errors and s.traffic is None and s.road_cyclists is None and s.state.vehicles is None


def test_erg_only_in_free_session(env):
    make, run, _ = env
    s, errors = make(6870)
    s._on_command("start", {"mode": "track", "track": {"event": "kilo"}}, 2)
    s._on_command("set_ride_mode", {"mode": "erg", "target_w": 200}, 3)
    assert errors and errors[-1][0] == "busy"
    s2, errors2 = make(6872)
    s2._on_command("start", {"mode": "track", "track": {"event": "free", "opponents": 0}}, 2)
    s2._on_command("set_ride_mode", {"mode": "erg", "target_w": 200}, 3)
    assert not [e for e in errors2 if e[0] == "busy"]
