"""Lot DS2 : mode « Dernier survivant » branché dans la séance (plateau, éliminations, trame, bilan)."""

import json
import time
from pathlib import Path

import jsonschema
import pytest

from openride_core import fit_export, profile, settings
from openride_core.bots import ProfileBot
from openride_core.config import Config
from openride_core.input_providers import NullProvider
STATE_LIMIT_BYTES = 4096
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.session import SURVIVOR_RETIRED_S, CoreSession

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
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    wall = [T0_WALL]
    monkeypatch.setattr(time, "time", lambda: wall[0])
    workouts = tmp_path / "Workouts"
    workouts.mkdir()
    (workouts / "erg.zwo").write_text(ERG_ZWO, encoding="utf-8")

    def make(port: int, power_w: float = 220.0, opponents: int = 2, spacing_km: int = 2,
             after_out: str = "ride", level_pct: int = 100) -> tuple[CoreSession, list, list]:
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        cfg.survivor.opponents, cfg.survivor.spacing_km, cfg.survivor.after_out = opponents, spacing_km, after_out
        cfg.bots.level_pct = level_pct
        s = CoreSession(cfg, driver=MockDriver(base_power_w=power_w, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                        routes_root=tmp_path / "routes", workouts_dir=workouts,
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
            if s.state.session_state != "RUNNING":
                return
            wall[0] += DT
            s._step(DT, wall[0])
            if i % 15 == 0:
                s.state.bots = [b.to_dict() for b in s.bots] or None
                s._fill_race_frame()
                s._fill_survivor_frame()
                if check:
                    check(s)

    return make, run, tmp_path


def test_strong_rider_wins_and_bilan(env):
    make, run, tmp_path = env
    s, sent, errors = make(6700, power_w=400.0, level_pct=60)
    s._on_command("start", {"mode": "survivor"}, 2)
    assert not errors and s.state.session_state == "RUNNING" and s.race is None
    assert [type(b) for b in s.bots] == [ProfileBot, ProfileBot]
    assert [b.profile for b in s.bots] == ["climber", "rouleur"]
    assert s.bots[0].level_pct > s.bots[1].level_pct
    sv = s.survivor
    frames: list[dict] = []
    state_v = validator("state")

    def check(sess):
        d = sess.state.to_dict()
        assert "segment" not in d and "powerup" not in d
        state_v.validate(d)
        assert len(json.dumps(d, ensure_ascii=False).encode()) < STATE_LIMIT_BYTES
        frames.append(d["survivor"])

    run(s, 900, check)   # 4 km de course, puis arrivée du parcours de 5 km : séance terminée
    assert frames[0]["arches"] == 2 and frames[0]["alive"][0] in ("me", "bot1", "bot2")
    assert sv.winner == "me" and s.state.session_state == "FINISHED"
    elim = [m for m in sent if m.get("type") == "elimination"]
    elim_v = validator("elimination")
    for m in elim:
        elim_v.validate(m)
    assert sorted({(m["arch"], m["rider"]) for m in elim})[0][0] == 1 and len(elim) == 6   # 2 × 3 envois
    summary = s.state.summary["survivor"]
    assert summary["place"] == 1 and summary["of"] == 3 and summary["winner"] == "me"
    validator("state").validate(s.state.to_dict())
    lines = [json.loads(x) for x in next((tmp_path / "journal").glob("*.jsonl")).read_text("utf-8").splitlines()]
    kinds = [ln.get("kind") for ln in lines]
    assert "survivor_start" in kinds and kinds.count("survivor") == 3 and "survivor_summary" in kinds


def test_weak_rider_eliminated_keeps_riding_or_ends(env):
    make, run, _ = env
    s, sent, errors = make(6710, power_w=90.0, level_pct=120)
    s._on_command("start", {"mode": "survivor"}, 2)
    run(s, 600)
    assert s.survivor.racers["me"].out_arch == 1 and s.state.session_state == "RUNNING"
    assert s.survivor.frame()["me_out"] == 1 and s.state.survivor["d_m"] is None
    s, sent, errors = make(6720, power_w=90.0, level_pct=120, after_out="end")
    s._on_command("start", {"mode": "survivor"}, 2)
    run(s, 600)
    assert s.state.session_state == "FINISHED" and s.state.summary["survivor"]["place"] == 3


def test_eliminated_bot_retires_and_leaves_draft(env):
    make, run, _ = env
    s, sent, errors = make(6730, power_w=400.0, level_pct=60)
    s._on_command("start", {"mode": "survivor"}, 2)
    seen_out: list[float] = []

    marked: list[int] = []

    def check(sess):
        marked.extend(b["out"] for b in sess.state.bots or [] if "out" in b)
        for rid, t0 in sess._survivor_out.items():
            assert sess._t_session - t0 < SURVIVOR_RETIRED_S + 0.5
            assert rid not in [b.id for b in sess._racing_bots()]
            seen_out.append(t0)

    run(s, 900, check)
    assert seen_out and marked and set(marked) <= {1, 2}
    assert s.state.summary["survivor"]["winner"] == "me"


def test_start_refusals_and_erg_refused(env):
    make, run, _ = env
    s, sent, errors = make(6740, opponents=4, spacing_km=2)   # 8 km sur un parcours de 5 km
    s._on_command("start", {"mode": "survivor"}, 2)
    assert errors[-1][0] == "bad_args" and "trop court" in errors[-1][1] and s.state.session_state == "READY"
    s, sent, errors = make(6750)
    s._on_command("start", {"mode": "survivor", "bots": []}, 2)
    assert errors[-1][0] == "bad_args" and s.state.session_state == "READY"
    s._on_command("select_workout", {"workout_id": "erg"}, 3)
    s._on_command("start", {"mode": "survivor"}, 4)
    assert errors[-1][0] == "bad_args" and s.state.session_state == "READY"
    s._on_command("select_workout", {"workout_id": None}, 5)
    s._on_command("start", {"mode": "survivor"}, 6)
    assert s.state.session_state == "RUNNING"
    run(s, 1)
    s._on_command("set_ride_mode", {"mode": "erg"}, 7)
    assert errors[-1][0] == "busy" and s.state.mode == "SIM"


def test_classic_ride_unchanged_after_survivor(env):
    make, run, _ = env
    s, sent, errors = make(6760)
    s._on_command("start", {"mode": "survivor"}, 2)
    run(s, 5)
    s._on_command("end_session", {"save": False}, 3)
    s._on_command("select_route", {"route_id": "demo"}, 4)
    s._on_command("start", {}, 5)
    assert s.survivor is None and s.state.survivor is None and s.bots == [] and s.race is not None
    assert all(getattr(b, "survival", None) is None for b in s.bots)


def test_settings_listed_and_bounds():
    keys = [st.key for st in settings.SETTINGS]
    for k in ("survivor.opponents", "survivor.spacing_km", "survivor.spread", "survivor.after_out"):
        assert k in keys
    cfg = Config()
    items = {it["key"]: it for it in settings.current(cfg)}
    assert items["survivor.opponents"]["min"] == 2 and items["survivor.opponents"]["max"] == 4
    assert items["survivor.spread"]["choices"] == ["tight", "normal", "wide"]
    assert items["survivor.after_out"]["value"] == "ride"
