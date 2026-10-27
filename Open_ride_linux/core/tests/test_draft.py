"""Aspiration derrière les bots (lot P3) : courbe, file, vent de travers, coût, séance simulée."""

import json
import time
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest
from openride_core import draft as d
from openride_core import fit_export
from openride_core.bots import ConstantPowerBot
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.physics import PhysicsParams, steady_speed
from openride_core.route import RouteSample
from openride_core.session import CoreSession
from openride_core.tools.session_summary import Session, compute_summary

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"


def bot(s: float, bot_id: str = "b1", kind: str = "constant") -> SimpleNamespace:
    return SimpleNamespace(s=s, id=bot_id, kind=kind)


def behind(gap_m: float) -> float:
    """Position du cycliste pour un écart `gap_m` derrière un bot à s = 100 m."""
    return 100.0 - d.BIKE_LENGTH_M - gap_m


# --- critère 2 : courbe ---------------------------------------------------------------------

def test_draft_curve_values_and_monotonic():
    assert d.draft_coefficient(0.5) == pytest.approx(0.38, abs=0.01)
    assert d.draft_coefficient(5.0) == pytest.approx(0.13, abs=0.01)
    assert 0.02 <= d.draft_coefficient(10.0) <= 0.05
    assert d.draft_coefficient(15.1) == 0.0 and d.draft_coefficient(40.0) == 0.0
    assert d.draft_coefficient(-0.5) == 0.0                       # devant le bot
    gaps = [0.3 + i * 0.1 for i in range(147)]
    values = [d.draft_coefficient(g) for g in gaps]
    assert all(a > b for a, b in zip(values, values[1:]))       # strictement décroissante


# --- critère 3 : file et vent de travers ------------------------------------------------------

def test_line_of_bots_and_crosswind():
    one, _ = d.best_draft(behind(0.5), [bot(100.0)])
    line = [bot(100.0, "b1"), bot(100.0 + d.BIKE_LENGTH_M + 1.0, "b2"), bot(100.0 + 2 * (d.BIKE_LENGTH_M + 1.0), "b3")]
    three, bot_id = d.best_draft(behind(0.5), line)
    assert three > one and three <= d.ALPHA_CAP
    assert three == pytest.approx(min(one * 1.18, 0.45))
    assert bot_id == "b1"
    two, _ = d.best_draft(behind(0.5), line[:2])
    assert two == pytest.approx(one * 1.12)
    v = 10.0
    cross, _ = d.best_draft(behind(0.5), [bot(100.0)], rider_v=v, cross_mps=v)   # 45° de travers
    assert cross == pytest.approx(one * 0.5)
    head, _ = d.best_draft(behind(0.5), [bot(100.0)], rider_v=v, head_mps=5.0)
    assert head == pytest.approx(one)
    # Le fantôme n'abrite pas ; un bot derrière le cycliste non plus
    assert d.best_draft(behind(0.5), [bot(100.0, "g", "ghost")]) == (0.0, None)
    assert d.best_draft(110.0, [bot(100.0)]) == (0.0, None)


def test_push_from_behind():
    assert d.push_bonus(behind(0.5), 100.0) == d.PUSH_FROM_BEHIND
    assert d.push_bonus(behind(2.0), 100.0) == 0.0
    assert 0.02 <= d.PUSH_FROM_BEHIND <= 0.03


# --- critère 4 : coût -----------------------------------------------------------------------

def test_best_draft_cost_with_five_bots():
    bots = [bot(100.0 + i * 4.0, f"b{i}") for i in range(4)] + [bot(103.0, "g", "ghost")]
    n = 50_000
    t0 = time.perf_counter()
    for i in range(n):
        d.best_draft(95.0 + (i % 10) * 0.1, bots, 5000.0, True, 10.0, 2.0, 1.0)
    per_call_ms = (time.perf_counter() - t0) * 1000.0 / n
    assert per_call_ms < 0.02, f"{per_call_ms:.4f} ms par appel"


# --- critère 7 : sortie de la roue -----------------------------------------------------------

def test_leaving_the_wheel_is_smooth():
    alpha, steps = 0.40, 0
    while alpha > 0.0:
        new = d.smooth(alpha, 0.0, 0.02)
        assert alpha - new <= 0.05
        alpha, steps = new, steps + 1
    assert steps * 0.02 <= 3.0


# --- critère 8 : boucle ---------------------------------------------------------------------

def test_loop_wraps_around():
    length = 5000.0
    alpha, bot_id = d.best_draft(length - 2.0, [bot(3.0)], length, True)
    assert alpha > 0.1 and bot_id == "b1"
    # Parcours ouvert : un bot en début de route n'abrite pas un cycliste en fin de route
    assert d.best_draft(length - 2.0, [bot(3.0)], length, False) == (0.0, None)


# --- critères 5, 6 et 9 : séance simulée ------------------------------------------------------

class FlatRoute:
    """Boucle plate de 20 km plein nord (critère 5 : « sur le plat »)."""
    is_loop, length_m, type = True, 20_000.0, "loop"

    def wrap(self, s: float) -> float:
        return s % self.length_m

    def sample(self, s: float) -> RouteSample:
        return RouteSample(x=0.0, y=0.0, z=-s, lat=48.0, lon=7.0, alt_m=0.0, grade_pct=0.0, heading_deg=0.0)

    def grade_at(self, s: float) -> float:
        return 0.0


class FakeGhost:
    """Fantôme minimal juste devant le cycliste : seule sa position compte."""
    id, name, kind, s, v = "ghost", "Fantôme", "ghost", 12.0, 9.0

    def step(self, dt, route) -> None:
        pass

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "s": self.s, "v": self.v, "kind": self.kind}


def make_session(tmp_path, monkeypatch, port, power, bots, workouts_dir=None):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    drv = MockDriver(base_power_w=power, ramp_amplitude_w=0.0)
    kw = {"workouts_dir": workouts_dir} if workouts_dir else {}
    s = CoreSession(cfg, driver=drv, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes", bots=bots, **kw)
    s._on_command("select_route", {"route_id": "demo"}, 1)
    return s, drv


def run(s, seconds, t0=100.0):
    for i in range(int(seconds / 0.02)):
        s._step(0.02, t0 + i * 0.02)


def flat_params(cfg: Config) -> PhysicsParams:
    return PhysicsParams.from_config(cfg)


def test_drafting_speed_and_staying_on_wheel(tmp_path, monkeypatch):
    p = PhysicsParams()
    alone = steady_speed(250.0, 0.0, p)
    # Abri constant de 0,38 : vitesse d'équilibre plus haute que seul (mêmes forces, aéro réduite)
    from openride_core.physics import resistive_force
    lo, hi = 0.0, 40.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if resistive_force(mid, 0.0, 0.0, p, 0.38) * mid < p.efficiency * 250.0:
            lo = mid
        else:
            hi = mid
    assert lo > alone + 0.5

    # Cycliste à 200 W derrière un bot à 250 W, collé dans sa roue : il ne se fait pas distancer
    cfg = Config()
    params = flat_params(cfg)
    leader = ConstantPowerBot(250.0, bot_id="b1", params=params, s=0.0 + d.BIKE_LENGTH_M + 0.4, v=9.0)
    s, _ = make_session(tmp_path, monkeypatch, 5980, 200.0, [leader])
    s.route = FlatRoute()
    s.physics.v = 9.0
    s._on_command("start", {}, 2)
    run(s, 600.0)
    gap = leader.s - s.physics.s - d.BIKE_LENGTH_M
    assert gap < 3.0, f"distancé : {gap:.1f} m derrière le bot après 10 min"
    assert s.state.draft > 0.2 and s.state.draft_bot == "b1"


def test_no_bot_no_draft_and_schema(tmp_path, monkeypatch):
    validator = jsonschema.Draft202012Validator(
        json.loads((IPC_DIR / "state.schema.json").read_text(encoding="utf-8")))
    s, _ = make_session(tmp_path, monkeypatch, 5982, 250.0, [])
    s._on_command("start", {}, 2)
    run(s, 10.0)
    frame = s.state.to_dict()
    assert "draft" not in frame and "draft_bot" not in frame
    assert s._draft == 0.0

    s2, _ = make_session(tmp_path / "g", monkeypatch, 5984, 250.0, [FakeGhost()])
    s2._on_command("start", {}, 2)
    s2.physics.s = 10.0
    run(s2, 2.0)
    frame2 = s2.state.to_dict()
    assert frame2["draft"] == 0.0 and "draft_bot" not in frame2   # le fantôme n'abrite pas
    assert not list(validator.iter_errors(frame2))


def test_erg_command_unchanged_by_draft(tmp_path, monkeypatch):
    workouts = tmp_path / "wk"
    workouts.mkdir()
    (workouts / "plat.zwo").write_text(
        '<workout_file><name>Plat</name><workout><SteadyState Duration="600" Power="0.8"/>'
        '</workout></workout_file>', encoding="utf-8")
    cfg = Config()
    leader = ConstantPowerBot(250.0, bot_id="b1", params=flat_params(cfg), s=d.BIKE_LENGTH_M + 0.4, v=9.0)
    s, drv = make_session(tmp_path, monkeypatch, 5986, 200.0, [leader], workouts)
    s._on_command("select_workout", {"workout_id": "plat"}, 2)
    s._on_command("start", {}, 3)
    s.physics.v = 9.0
    run(s, 20.0)
    assert s._draft > 0.1
    assert drv.target_power_w == pytest.approx(0.8 * cfg.rider.ftp_w, abs=1.0)
    assert s._wind_offset == 0.0


def test_sim_grade_offset_from_draft_and_summary(tmp_path, monkeypatch):
    cfg = Config()
    leader = ConstantPowerBot(250.0, bot_id="b1", params=flat_params(cfg), s=d.BIKE_LENGTH_M + 0.4, v=9.0)
    s, _ = make_session(tmp_path, monkeypatch, 5988, 200.0, [leader])   # 200 W : reste dans la roue
    s.route = FlatRoute()
    s.physics.v = 9.0
    s._on_command("start", {}, 2)
    run(s, 30.0)
    assert s._wind_offset < 0.0   # l'abri allège la pente envoyée en SIM
    assert s._wind_offset >= -cfg.wind.max_grade_offset_pct
    records = [line for line in s._rec.lines if line.get("kind") == "record"]
    assert records and all(r["draft"] is not None for r in records)
    summary = compute_summary(Session(records, [], "jsonl"), cfg.rider.ftp_w)
    assert summary["draft_time_s"] >= 20
    # Bilan d'une séance sans bot : pas de clé draft_time_s
    s0, _ = make_session(tmp_path / "solo", monkeypatch, 5990, 250.0, [])
    s0._on_command("start", {}, 2)
    run(s0, 5.0)
    solo = [line for line in s0._rec.lines if line.get("kind") == "record"]
    assert "draft_time_s" not in compute_summary(Session(solo, [], "jsonl"), cfg.rider.ftp_w)
