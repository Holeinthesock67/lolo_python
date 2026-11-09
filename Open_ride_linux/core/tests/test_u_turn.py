"""Demi-tour depuis l'écran de pause (lot N17, contrat IPC révision 1.9) : commande `u_turn`, champ `dir`,
pente inversée, arrivée au départ du parcours, distance croissante du journal et du FIT, segments à rebours
non comptés, bots dans leur sens, reprise après un plantage du core."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage

from openride_core import fit_export
from openride_core.bots import ConstantPowerBot
from openride_core.config import Config
from openride_core.demo_world import write_world
from openride_core.fit_export import iter_records
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.resume import load_resume_state
from openride_core.segment_timing import SegmentTimer, passes_from_journal
from openride_core.session import CoreSession

LENGTH_M = 6000.0


def _grade(s: float) -> float:
    """Montée de 3 % entre 1 000 et 2 000 m, plat ailleurs."""
    return 3.0 if 1000.0 <= s <= 2000.0 else 0.0


def make_session(tmp_path, monkeypatch, port, grade=_grade, bots=None):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    routes = tmp_path / "routes"
    routes.mkdir(parents=True, exist_ok=True)
    write_world(routes, "aller", LENGTH_M, created="2026-11-08T00:00:00+00:00", grade=grade)
    drv = MockDriver(base_power_w=250.0, ramp_amplitude_w=0.0)
    s = CoreSession(cfg, driver=drv, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=routes, workouts_dir=tmp_path / "wk", bots=bots)
    s._on_command("select_route", {"route_id": "aller"}, 1)
    s._on_command("start", {}, 2)
    assert s.state.session_state == "RUNNING"
    return s, drv


def ride_until(s, cond, dt=0.1, limit=40000):
    t = 100.0
    for _ in range(limit):
        if cond():
            return
        s._step(dt, t)
        t += dt
    raise AssertionError("condition jamais atteinte")


def u_turn(s, cmd_id=10):
    s._on_command("pause", {}, cmd_id)
    s._on_command("u_turn", {}, cmd_id + 1)
    s._on_command("resume", {}, cmd_id + 2)


def errors(monkeypatch, s) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    monkeypatch.setattr(s.server, "send_error", lambda code, msg="": out.append((code, msg)))
    return out


# --- physique -------------------------------------------------------------------------------------


def test_physics_u_turn_keeps_distance_growing() -> None:
    p = RiderPhysics(PhysicsParams(), s=100.0)
    for _ in range(50):
        p.step(250.0, 0.0, dt=0.1)
    s_turn, d_turn = p.s, p.distance
    assert d_turn == pytest.approx(s_turn)
    p.u_turn()
    assert p.direction == -1 and p.v == 0.0 and p.s == s_turn
    for _ in range(50):
        p.step(250.0, 0.0, dt=0.1)
    assert p.s < s_turn and p.distance > d_turn
    assert p.distance - d_turn == pytest.approx(s_turn - p.s)
    p.place(0.0)
    assert (p.s, p.v, p.distance, p.direction) == (0.0, 0.0, 0.0, 1)


# --- critère 2 : demi-tour à 3 km, arrivée au km 0, 6 km dans le FIT --------------------------------


def test_u_turn_at_3_km_ends_at_km_0_with_6_km(tmp_path, monkeypatch) -> None:
    s, _ = make_session(tmp_path, monkeypatch, 7100)
    ride_until(s, lambda: s.physics.s >= 3000.0)
    s_turn = s.physics.s
    u_turn(s)
    assert s.state.dir == -1 and s.state.to_dict()["dir"] == -1
    ride_until(s, lambda: s.state.session_state == "FINISHED")
    assert s.physics.s <= 0.0
    summary = s.state.summary
    assert summary["distance_m"] == pytest.approx(2 * s_turn, abs=15.0)
    assert "dir" not in s.state.to_dict()   # séance finie : sens du parcours
    msgs = [r.message for r in iter_records(Path(summary["fit_path"]))]
    dist = [m.distance for m in msgs if isinstance(m, RecordMessage)]
    assert all(b >= a for a, b in zip(dist, dist[1:])), "distance du FIT croissante"
    assert dist[-1] == pytest.approx(2 * s_turn, abs=15.0)
    fit_session = next(m for m in msgs if isinstance(m, SessionMessage))
    assert fit_session.total_distance == pytest.approx(6000.0, abs=30.0)
    lines = [json.loads(ln) for f in (tmp_path / "journal").glob("*.jsonl") for ln in f.read_text().splitlines()]
    turns = [ln for ln in lines if ln.get("event") == "u_turn"]
    assert len(turns) == 1 and turns[0]["dir"] == -1 and turns[0]["s"] == pytest.approx(s_turn, abs=0.01)
    recs = [ln for ln in lines if ln.get("kind") == "record"]
    after = [r for r in recs if "pos" in r]
    assert after and all(r["pos"] < r["distance"] for r in after)


# --- critère 3 : pente du trainer de signe opposé sur le même tronçon -------------------------------


def test_grade_sent_opposite_on_same_stretch(tmp_path, monkeypatch) -> None:
    s, drv = make_session(tmp_path, monkeypatch, 7102)
    s.gearing.ratios = [1.0] * len(s.gearing.ratios)   # braquet neutre : pente envoyée = pente × difficulté
    ride_until(s, lambda: s.physics.s >= 1500.0)
    forward_sent, forward_grade = drv.sim_grade_pct, s.state.grade
    ride_until(s, lambda: s.physics.s >= 2500.0)
    u_turn(s)
    ride_until(s, lambda: s.physics.s <= 1500.0)
    assert s.state.grade == pytest.approx(-forward_grade, abs=0.01)
    assert forward_sent > 1.0
    assert drv.sim_grade_pct == pytest.approx(-forward_sent, abs=0.1)


# --- refus ----------------------------------------------------------------------------------------


def test_u_turn_refused_outside_pause(tmp_path, monkeypatch) -> None:
    s, _ = make_session(tmp_path, monkeypatch, 7104)
    errs = errors(monkeypatch, s)
    ride_until(s, lambda: s.physics.s >= 50.0)
    s._on_command("u_turn", {}, 5)
    assert errs and errs[0][0] == "busy"
    assert s.physics.direction == 1 and s.state.session_state == "RUNNING"


def test_u_turn_refused_at_start_of_line_route(tmp_path, monkeypatch) -> None:
    s, _ = make_session(tmp_path, monkeypatch, 7106)
    errs = errors(monkeypatch, s)
    s._on_command("pause", {}, 5)
    s._on_command("u_turn", {}, 6)
    assert errs and errs[0][0] == "busy" and s.physics.direction == 1


def test_u_turn_twice_goes_forward_again(tmp_path, monkeypatch) -> None:
    s, _ = make_session(tmp_path, monkeypatch, 7108)
    ride_until(s, lambda: s.physics.s >= 500.0)
    u_turn(s, 10)
    ride_until(s, lambda: s.physics.s <= 400.0)
    u_turn(s, 20)
    assert s.state.dir is None and "dir" not in s.state.to_dict()
    ride_until(s, lambda: s.physics.s >= 450.0)
    assert s.physics.distance == pytest.approx(500.0 + 100.0 + 50.0, abs=5.0)


# --- segments, bots -------------------------------------------------------------------------------


class _Seg:
    def __init__(self, sid: str, a: float, b: float) -> None:
        self.id, self.name, self.type, self.s_start, self.s_end = sid, sid, "climb", a, b


def test_segment_ridden_backwards_does_not_count(tmp_path) -> None:
    timer = SegmentTimer([_Seg("m", 1000.0, 2000.0)], LENGTH_M)
    t = 0.0
    for s in range(2500, 500, -10):   # à rebours sur tout le segment
        timer.step(t, float(s), 250.0)
        t += 1.0
    assert timer.passes == []
    journal = tmp_path / "j.jsonl"
    lines = [{"kind": "record", "t": float(i), "distance": 2500.0 + i * 10.0, "pos": 2500.0 - i * 10.0,
              "power": 250} for i in range(200)]
    journal.write_text("\n".join(json.dumps(ln) for ln in lines) + "\n", encoding="utf-8")
    assert passes_from_journal(journal, [_Seg("m", 1000.0, 2000.0)], LENGTH_M) == []


def test_bots_keep_their_direction_and_no_draft_backwards(tmp_path, monkeypatch) -> None:
    bot = ConstantPowerBot(250.0, bot_id="b1")
    s, _ = make_session(tmp_path, monkeypatch, 7110, bots=[bot])
    ride_until(s, lambda: s.physics.s >= 800.0)
    bot_before = bot.s
    u_turn(s)
    ride_until(s, lambda: s.physics.s <= 600.0)
    assert bot.s > bot_before                # le bot continue dans le sens du parcours
    assert s._draft == pytest.approx(0.0, abs=1e-6) and s.state.draft_bot is None
    assert s.state.bot_ahead is None and s.state.bot_behind is None and s.state.segment is None
    assert s.state.lane_m is not None and s.state.lane_m < 0.0   # repère de la route : à droite du cycliste


# --- reprise après un plantage du core ------------------------------------------------------------


def test_resume_after_crash_keeps_direction(tmp_path, monkeypatch) -> None:
    s, _ = make_session(tmp_path, monkeypatch, 7112)
    ride_until(s, lambda: s.physics.s >= 1200.0)
    u_turn(s)
    ride_until(s, lambda: s.physics.s <= 1000.0)
    path = next((tmp_path / "journal").glob("*.jsonl"))
    rs = load_resume_state(path)
    assert rs.direction == -1 and rs.s < 1100.0 and rs.distance > 1300.0
    again = CoreSession(s.cfg, driver=MockDriver(base_power_w=250.0, ramp_amplitude_w=0.0),
                        inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                        routes_root=tmp_path / "routes", workouts_dir=tmp_path / "wk")
    again.resume_session(path)
    assert again.physics.direction == -1 and again.state.dir == -1
    assert again.physics.s == pytest.approx(rs.s) and again.physics.distance == pytest.approx(rs.distance)


# --- Y maintenu en roulant (révision 1.11, §7.1) ----------------------------------------------------


def test_click_y_long_without_dead_zone() -> None:
    from openride_core.zwift_click import InputEvent, PressClassifier
    pc = PressClassifier()

    def tap(held: float):
        pc.update("Y", True, 0.0)
        return pc.update("Y", False, held)
    assert tap(0.2) == InputEvent.Y_SHORT
    assert tap(0.7) == InputEvent.Y_SHORT   # pas de zone floue : la pause ne se perd jamais
    assert tap(0.9) == InputEvent.Y_LONG and tap(2.0) == InputEvent.Y_LONG


def test_y_long_turns_around_without_stopping(tmp_path, monkeypatch) -> None:
    from openride_core.zwift_click import InputEvent
    s, _ = make_session(tmp_path, monkeypatch, 7114)
    relayed: list[str] = []
    monkeypatch.setattr(s.server, "send_input_event", relayed.append)
    ride_until(s, lambda: s.physics.s >= 1500.0)
    v, s_turn = s.physics.v, s.physics.s
    s._handle_input(InputEvent.Y_LONG)
    assert s.state.session_state == "RUNNING" and s.physics.direction == -1 and s.state.dir == -1
    assert s.physics.v == pytest.approx(v) and s.physics.s == s_turn
    assert relayed == ["Y_LONG"]
    ride_until(s, lambda: s.physics.s <= 1400.0)
    s._handle_input(InputEvent.Y_LONG)
    assert s.physics.direction == 1 and s.state.dir is None and s.state.session_state == "RUNNING"
    lines = [json.loads(ln) for f in (tmp_path / "journal").glob("*.jsonl") for ln in f.read_text().splitlines()]
    assert [ln["dir"] for ln in lines if ln.get("event") == "u_turn"] == [-1, 1]


def test_y_long_pauses_where_no_u_turn(tmp_path, monkeypatch) -> None:
    from openride_core.zwift_click import InputEvent
    s, _ = make_session(tmp_path, monkeypatch, 7116)
    relayed: list[str] = []
    monkeypatch.setattr(s.server, "send_input_event", relayed.append)
    s._handle_input(InputEvent.Y_LONG)   # au départ d'un parcours en ligne : pas de demi-tour, pause
    assert s.state.session_state == "PAUSED" and s.physics.direction == 1 and relayed == []
    s._handle_input(InputEvent.Y_LONG)   # sur l'écran de pause : relayé à l'engine (comme Y court)
    assert relayed == ["Y_LONG"] and s.physics.direction == 1
