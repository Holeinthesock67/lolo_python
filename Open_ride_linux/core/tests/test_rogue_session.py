"""Lot R8 : mode ROGUE dans la session du core (start_run, pente centrée, boutons, pause, journal, reprise)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import jsonschema
import pytest
from garmin_fit_sdk import Decoder, Stream

from openride_core import fit_export
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.rogue.combat import target_at
from openride_core.rogue.mode import RogueMode, RunInvalid, hello_block, journal_line, parse_start_run
from openride_core.session import CoreSession
from openride_core.zwift_click import InputEvent

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
T0_WALL = 1_790_000_000.0
FTP = 250.0


def validator(name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(json.loads((IPC_DIR / f"{name}.schema.json").read_text("utf-8")))


STATE, ROOM, LOOT, ERROR = validator("state"), validator("room"), validator("loot"), validator("error")
HELLO_ACK = validator("hello_ack")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    wall = [T0_WALL]
    monkeypatch.setattr(time, "time", lambda: wall[0])

    def make(port: int):
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        s = CoreSession(cfg, driver=MockDriver(base_power_w=FTP, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                        journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes",
                        workouts_dir=tmp_path / "Workouts", records_path=tmp_path / "records.json",
                        powerups_path=tmp_path / "powerups.toml", config_path=tmp_path / "config.toml")
        sent: list[dict] = []
        s.server.send_raw = lambda m, max_size=None: sent.append(m)
        return s, sent

    def advance(s, seconds: float, dt: float = 0.5, follow: bool = True, every: int = 0, frames: list | None = None):
        """Fait avancer la séance ; `follow` : le cycliste suit la cible de la salle (puissance du trainer simulé)."""
        n = int(seconds / dt)
        for i in range(n):
            rg = s.rogue
            if follow and rg is not None and rg.in_fight:
                s.driver.base_power_w = target_at(rg.engine.room, s.physics.s) * FTP
            elif follow:
                s.driver.base_power_w = 0.6 * FTP
            wall[0] += dt
            s._step(dt, 100.0 + i * dt)
            results = (s.state.rogue or {}).get("phase") == "RESULTS"     # montrée avant FINISHED (lot X40)
            if every and frames is not None and (i % every == 0 or results):
                s.server.seq += 1
                frames.append(s.state.to_dict())
            if s.state.session_state in ("FINISHED", "ERROR"):
                break

    return make, advance, tmp_path


def start(s, objective="threshold", duration=30, seed=5, **extra):
    s._on_command("start_run", {"objective": objective, "duration_min": duration, "seed": seed, **extra}, 1)


def errors(sent):
    return [m for m in sent if m["type"] == "error"]


# --- lancement -----------------------------------------------------------------------------------

def test_hello_ack_announces_the_mode_and_its_block(env):
    make, _, _ = env
    s, _ = make(6000)
    s.server.send_hello_ack(s.server.hello_config)
    ack = s.server.hello_config
    block = ack["rogue"]
    assert block["objectives"] == ["endurance", "threshold", "vo2max"] and block["durations_min"] == [30, 45, 60, 90]
    assert block["cp_w"] == FTP and block["w_prime_j"] == 20000.0
    from openride_core.ipc_server import CORE_MODES
    assert "rogue" in CORE_MODES
    HELLO_ACK.validate({"type": "hello_ack", "v": 1, "rev": "1.4", "core_version": "x",
                        "config": {**ack, "modes": list(CORE_MODES)}})


def test_start_run_goes_loading_then_ready_in_rogue_mode(env):
    make, _, _ = env
    s, sent = make(6010)
    states = []
    real = s._set_state
    s._set_state = lambda new, reason=None: (states.append(new), real(new, reason))[1]
    start(s)
    assert states == ["LOADING", "READY"] and s.state.mode == "ROGUE" and s.state.route_id == "rogue"
    assert s.state.gear == 6 and s.state.gears_total == 12 and s.state.lat is None
    s.server.send_state(s.state)
    STATE.validate([m for m in sent if m["type"] == "state"][-1])


@pytest.mark.parametrize("args, code", [
    ({"objective": "sprint", "duration_min": 45}, "run_invalid"),
    ({"objective": "threshold", "duration_min": 44}, "run_invalid"),
    ({"objective": "threshold", "duration_min": 45, "seed": -1}, "run_invalid"),
    ({"objective": "threshold", "duration_min": 45, "w_prime_j": 100}, "run_invalid"),
    ({"objective": "threshold", "duration_min": 45, "chassis": "blinde"}, "item_locked"),
])
def test_start_run_refuses_bad_arguments_with_contract_codes(env, args, code):
    make, _, _ = env
    s, sent = make(6020)
    s._on_command("start_run", args, 1)
    errs = errors(sent)
    assert len(errs) == 1 and errs[0]["code"] == code
    ERROR.validate(errs[0])
    assert s.state.session_state == "IDLE" and s.rogue is None


def test_null_seed_and_w_prime_take_defaults(env):
    cfg = Config()
    req = parse_start_run({"objective": "vo2max", "duration_min": 60, "seed": None, "w_prime_j": None}, cfg)
    assert req.w_prime_j == cfg.rogue.w_prime_j and 0 < req.seed < 2**31 and req.chassis == "standard"
    with pytest.raises(RunInvalid):
        parse_start_run(None, cfg)


def test_start_run_refused_during_a_session(env):
    make, advance, _ = env
    s, sent = make(6030)
    start(s)
    s._on_command("start", {}, 2)
    start(s)
    assert errors(sent)[-1]["code"] == "busy"
    assert s.state.session_state == "RUNNING"


def test_select_route_in_ready_drops_the_run(env):
    make, _, _ = env
    s, _ = make(6040)
    start(s)
    s._on_command("select_route", {"route_id": "demo"}, 2)
    assert s.rogue is None and s.state.mode == "SIM" and s.state.rogue is None and s.state.gears_total == 24
    assert s.state.session_state == "READY"


# --- pente centrée, difficulté, boutons -----------------------------------------------------------

def test_grade_sent_follows_the_centered_formula_and_ignores_difficulty(env):
    make, advance, _ = env
    runs = []
    for difficulty in (0, 100):
        s, _ = make(6050 + difficulty // 50 * 2)
        s._on_command("set_difficulty", {"pct": difficulty}, 1)
        start(s)
        s._on_command("start", {}, 2)
        s._on_command("input_event", {"event": "PLUS_LONG"}, 3)
        advance(s, 60.0, dt=0.5)
        rg = s.rogue
        runs.append(round(s.state.grade_sent, 3))
        expect = rg.out.grade_enemy + (rg.gear - 6)
        assert rg.gear == 9 and s.state.gear == 9
        assert s.state.grade_sent == pytest.approx(min(max(expect, -10.0), 16.0), abs=0.05)
    assert runs[0] == runs[1]


def test_rate_limit_applies_to_the_ramp_but_not_to_gear_changes(env):
    make, advance, _ = env
    s, _ = make(6060)
    start(s)
    s._on_command("start", {}, 2)
    advance(s, 20.0, dt=0.5)
    before = s.state.grade_sent
    s._on_command("input_event", {"event": "PLUS_LONG"}, 3)
    advance(s, 0.5, dt=0.5)
    assert s.state.grade_sent - before == pytest.approx(3.0, abs=0.6)    # +3 vitesses : tout de suite, sans rampe


def test_buttons_gear_game_pause(env):
    make, advance, _ = env
    s, sent = make(6070)
    start(s)
    s._on_command("start", {}, 2)
    advance(s, 5.0, dt=0.5)
    s._handle_input(InputEvent.MINUS_LONG)
    assert s.rogue.gear == 3
    s._handle_input(InputEvent.PLUS_SHORT)
    assert s.rogue.gear == 4
    s._handle_input(InputEvent.A_SHORT)       # hors couloir : aucun effet sur le jeu
    s._handle_input(InputEvent.A_LONG)
    assert s.rogue.gear == 4
    advance(s, 0.5, dt=0.5)
    assert s.state.rogue["loot_focus"] is None
    assert {"A_SHORT", "A_LONG"} <= {m["event"] for m in sent if m["type"] == "input"}   # relayés à l'engine
    s._handle_input(InputEvent.Y_SHORT)
    assert s.state.session_state == "PAUSED"
    s._handle_input(InputEvent.PLUS_LONG)     # en pause : aucun effet
    assert s.rogue.gear == 4
    s._on_command("resume", {}, 4)
    assert s.state.session_state == "RUNNING"


def test_pause_freezes_the_run_and_releases_the_trainer(env):
    make, advance, _ = env
    s, _ = make(6080)
    start(s)
    s._on_command("start", {}, 2)
    advance(s, 30.0, dt=0.5)
    s._on_command("pause", {}, 3)
    t = s.rogue.engine.t_total
    adv = s.rogue.engine.t_phase
    advance(s, 10.0, dt=0.5)
    assert s.rogue.engine.t_total == t and s.rogue.engine.t_phase == adv
    assert s._grade_sent == 0.0 and s.driver.sim_grade_pct == 0.0


def test_lost_click_stops_the_firewall_in_the_mode_step():
    cfg = Config()
    req = parse_start_run({"objective": "threshold", "duration_min": 30, "seed": 3}, cfg)
    results = {}
    for lost in (False, True):
        mode = RogueMode(cfg, req)
        from openride_core.physics import RiderPhysics
        body = RiderPhysics(mode.rider.params)
        for _ in range(1500):
            mode.step(0.5, 0.0, 85.0, body, lost, T0_WALL)
            if mode.engine.firewall is not None:
                break
        gap0 = None
        while mode.engine.phase not in ("ROOM",) and mode.engine.t_total < 1500:
            mode.step(0.5, 0.6 * FTP, 85.0, body, lost, T0_WALL)
        for _ in range(30):
            mode.step(0.5, 0.0, 85.0, body, lost, T0_WALL)
        results[lost] = mode.engine.firewall.state.gap_m if mode.engine.firewall else None
    assert results[True] is not None and results[False] is not None
    assert results[True] > results[False]            # le mur a avancé quand la manette était présente


# --- run complète, journal, FIT ---------------------------------------------------------------------

def run_to_the_end(env, port=6100, seed=5):
    make, advance, tmp = env
    s, sent = make(port)
    start(s, seed=seed)
    s._on_command("start", {}, 2)
    frames: list = []
    advance(s, 4 * 3600.0, dt=0.5, every=40, frames=frames)
    return s, sent, frames, tmp


def test_full_run_reaches_the_results_with_valid_frames_and_summary(env):
    s, sent, frames, tmp = run_to_the_end(env)
    # Terminée d'elle-même, comme à l'arrivée d'un parcours, après RESULTS_HOLD_S en RESULTS (lot X40).
    assert s.state.session_state == "FINISHED" and s.rogue is None
    phases = []
    for f in frames:
        STATE.validate(f)
        if f["rogue"]["phase"] not in phases:
            phases.append(f["rogue"]["phase"])
    assert phases[0] == "WARMUP" and "ROOM" in phases and "CORRIDOR" in phases and phases[-1] == "RESULTS"
    assert max(len(json.dumps(f, separators=(",", ":"))) for f in frames) < 1400 + 600     # + devices éventuels
    for m in sent:
        if m["type"] == "room":
            ROOM.validate(m)
        elif m["type"] == "loot":
            LOOT.validate(m)
    assert any(m["type"] == "room" for m in sent) and any(m["type"] == "loot" for m in sent)
    summary = s.state.summary
    validator("state").validate({**frames[-1], "summary": summary, "session_state": "FINISHED", "mode": "SIM"})
    assert summary["rogue"]["result"] in ("victory", "defeat") and summary["rogue"]["objective"] == "threshold"
    assert s.state.mode == "SIM" and s.rogue is None and s.state.gears_total == 24


def test_journal_lines_fit_and_progression(env):
    s, sent, frames, tmp = run_to_the_end(env, port=6110, seed=7)
    s._on_command("end_session", {"save": True}, 9)
    journal = sorted((tmp / "journal").glob("*.jsonl"))[-1]
    lines = list(read_journal(journal))
    kinds = {ln["kind"] for ln in lines}
    assert {"rogue", "rogue_snapshot", "rogue_run", "record"} <= kinds
    events = {ln["event"] for ln in lines if ln["kind"] == "rogue"}
    assert {"room_start", "run_end"} <= events and ({"room_won", "room_fled"} & events)
    first = next(ln for ln in lines if ln["kind"] == "rogue" and ln["event"] == "balance")
    assert len(first["hash"]) == 8
    run = next(ln for ln in lines if ln["kind"] == "rogue_run")
    assert run["objective"] == "threshold" and run["chassis"] == "standard" and run["minutes"] > 5
    assert all(ln["mode"] == "ROGUE" for ln in lines if ln["kind"] == "record")
    fit = Path(s.state.summary["fit_path"])
    stream = Stream.from_file(str(fit))
    decoder = Decoder(stream)
    assert decoder.is_fit() and decoder.check_integrity()
    stream.reset()
    messages, errs = decoder.read()
    assert errs == [] and messages["session_mesgs"][0]["sport"] == "cycling"
    assert messages["session_mesgs"][0]["sub_sport"] == "virtual_activity"
    rooms = [ln for ln in lines if ln["kind"] == "rogue" and ln["event"] == "room_start"]
    laps = messages["lap_mesgs"]
    assert len(laps) == len(rooms) + 1 or len(laps) == len(rooms)       # un tour par salle, le premier tour couvre l'échauffement
    assert messages["session_mesgs"][0]["num_laps"] == len(laps)
    assert "position_lat" not in messages["record_mesgs"][0] or messages["record_mesgs"][0]["position_lat"] is None
    from openride_core.progression import load_table, recompute
    from openride_core.rogue.progress import rogue_stats
    stats = rogue_stats(recompute(tmp / "journal", load_table(None)))
    assert stats.total("runs") in (0, 1)


def test_journal_line_parser():
    line = journal_line("rogue room id=3 archetype=diesel variant=a length=1500", 5.0, 12.0)
    assert line == {"kind": "rogue", "event": "room_start", "ts": 5.0, "t": 12.0, "id": 3, "archetype": "diesel",
                    "variant": "a", "length": 1500}
    assert journal_line("rogue room_end id=3 outcome=won gold=40", 1.0, 1.0)["event"] == "room_won"
    assert journal_line("rogue room_end id=3 outcome=fled gold=10", 1.0, 1.0)["event"] == "room_fled"
    assert journal_line("autre chose", 1.0, 1.0) is None


# --- reprise ------------------------------------------------------------------------------------

def test_resume_after_a_crash_restarts_the_current_room_with_its_noted_state(env):
    make, advance, tmp = env
    s, _ = make(6120)
    start(s, seed=5)
    s._on_command("start", {}, 2)
    advance(s, 400.0, dt=0.5)                                  # échauffement fini, première salle commencée
    assert s.rogue.engine.phase in ("ROOM", "CORRIDOR", "WARMUP")
    while s.rogue.engine.phase != "ROOM":
        advance(s, 1.0, dt=0.5)
    advance(s, 40.0, dt=0.5)
    snap = [ln for ln in read_journal(sorted((tmp / "journal").glob("*.jsonl"))[-1]) if ln["kind"] == "rogue_snapshot"][-1]
    room_id = s.rogue.engine.room_id
    # le core meurt ici : un nouveau core reprend le journal
    s._rec.close() if hasattr(s._rec, "close") else None
    journal = sorted((tmp / "journal").glob("*.jsonl"))[-1]
    s2, _ = make(6130)
    s2.resume_session(journal)
    assert s2.state.session_state == "PAUSED" and s2.state.pause_reason == "core_restarted"
    assert s2.rogue is not None and s2.state.mode == "ROGUE"
    eng = s2.rogue.engine
    assert eng.phase == "ROOM" and eng.room_id == room_id and eng.t_phase < 5.0   # début de la salle
    assert eng.combat.enemy_hp == pytest.approx(eng.combat.enemy_hp_max)           # PV de l'ennemi intacts
    assert s2.rogue.gear == snap["gear"]
    s2._on_command("resume", {}, 1)
    advance(s2, 20.0, dt=0.5)
    assert s2.state.session_state == "RUNNING" and s2.rogue.engine.t_phase > 10.0


def test_config_rate_keys_are_bounded(tmp_path):
    from openride_core.config import ConfigError, load
    p = tmp_path / "config.toml"
    p.write_text("[rogue]\ngrade_rate_up_pct_per_s = 500\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="grade_rate_up_pct_per_s"):
        load(p)
    p.write_text("[rogue]\ngrade_rate_up_pct_per_s = 5\ngrade_rate_down_pct_per_s = 9\n", encoding="utf-8")
    cfg = load(p)
    assert (cfg.rogue.grade_rate_up_pct_per_s, cfg.rogue.grade_rate_down_pct_per_s) == (5.0, 9.0)
