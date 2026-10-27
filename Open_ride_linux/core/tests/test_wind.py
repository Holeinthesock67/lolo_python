"""Vent physique côté core (lot P2) : modèle, projection, physique, ressenti en SIM, trame `state`."""

import json
from pathlib import Path

import jsonschema
import pytest

from openride_core import config as config_mod
from openride_core import fit_export
from openride_core.config import Config, ConfigError
from openride_core.input_providers import NullProvider
from openride_core.journal import Record
from openride_core.mock_driver import MockDriver
from openride_core.physics import (
    G,
    PhysicsParams,
    RiderPhysics,
    air_density,
    steady_speed,
)
from openride_core.session import CoreSession, theme_wind
from openride_core.wind import (
    WindModel,
    WindSample,
    aero_force_delta,
    grade_offset_pct,
    head_component,
    wind_frame,
)

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
REF = PhysicsParams(mass_kg=84.0, cda_m2=0.32, crr=0.004, efficiency=0.97)
KMH20 = 20.0 / 3.6


def ride(params: PhysicsParams, power: float = 250.0, seconds: float = 400.0) -> float:
    phys = RiderPhysics(params)
    for _ in range(int(seconds / 0.02)):
        phys.step(power, 0.0, 0.0)
    return phys.v


# --- critère 1 et 2 : physique ----------------------------------------------------------

def test_reference_case_unchanged_without_wind():
    assert ride(REF) == pytest.approx(steady_speed(250.0, 0.0, REF), rel=1e-3)
    assert ride(REF) == pytest.approx(10.2, rel=0.03)


def test_head_and_tail_wind_20kmh():
    calm = ride(REF)
    head = PhysicsParams(**{**REF.__dict__, "wind_mps": KMH20})
    tail = PhysicsParams(**{**REF.__dict__, "wind_mps": -KMH20})
    v_head, v_tail = ride(head), ride(tail)
    assert v_head < calm - 1.5            # nettement plus lent
    assert v_tail > calm + 1.0
    assert v_head == pytest.approx(steady_speed(250.0, 0.0, head), rel=0.01)
    assert v_tail == pytest.approx(steady_speed(250.0, 0.0, tail), rel=0.01)


# --- critère 3 : projection sur le cap ----------------------------------------------------

def test_head_component_north_wind():
    north = WindSample(5.0, 0.0, 0.0)
    assert head_component(north, 0.0) == pytest.approx(5.0, abs=0.01)     # route plein nord : de face
    assert head_component(north, 180.0) == pytest.approx(-5.0, abs=0.01)  # plein sud : de dos
    assert head_component(north, 90.0) == pytest.approx(0.0, abs=0.01)    # plein est : travers


# --- critère 4 : déterminisme --------------------------------------------------------------

def test_gusts_deterministic_and_constant_without_gust():
    a = WindModel("gusty", 20.0, 270.0, 40.0, seed=7)
    b = WindModel("gusty", 20.0, 270.0, 40.0, seed=7)
    c = WindModel("gusty", 20.0, 270.0, 40.0, seed=8)
    times = [i * 0.5 for i in range(400)]
    assert [a.sample(t) for t in times] == [b.sample(t) for t in times]
    assert [a.sample(t) for t in times] != [c.sample(t) for t in times]
    speeds = [a.sample(t).speed_mps for t in times]
    base = 20.0 / 3.6
    assert min(speeds) >= base * 0.6 - 1e-9 and max(speeds) <= base * 1.4 + 1e-9
    assert max(speeds) - min(speeds) > base * 0.2     # les rafales se voient
    dirs = [a.sample(t).from_deg for t in times]
    assert all(min(abs(d - 270.0), 360 - abs(d - 270.0)) <= 15.0 + 1e-9 for d in dirs)
    still = WindModel("gusty", 20.0, 270.0, 0.0, seed=7)
    assert {still.sample(t) for t in times} == {WindSample(base, 270.0, 0.0)}
    fixed = WindModel("fixed", 20.0, 90.0, 80.0, seed=7)   # gust_pct ignoré en mode fixe
    assert {fixed.sample(t) for t in times} == {WindSample(base, 90.0, 0.0)}
    assert not WindModel("off", 20.0).active


# --- critère 5 : ressenti -----------------------------------------------------------------

def test_grade_offset_matches_delta_force_and_is_capped():
    v, head = 9.0, KMH20
    expected = 100.0 * aero_force_delta(v, head, 0.0, 0.0, REF) / (REF.mass_kg * G)
    manual = 0.5 * air_density(0.0) * REF.cda_m2 * ((v + head) ** 2 - v * v)
    assert expected == pytest.approx(100.0 * manual / (REF.mass_kg * G))
    assert grade_offset_pct(v, head, 0.0, 0.0, REF, 4.0) == pytest.approx(expected, abs=0.05)
    assert grade_offset_pct(v, 15.0, 0.0, 0.0, REF, 4.0) == 4.0
    assert grade_offset_pct(v, -15.0, 0.0, 0.0, REF, 4.0) < 0.0
    assert grade_offset_pct(v, -40.0, 0.0, 0.0, REF, 2.5) == -2.5
    # CdA réduit par un bonus (série T) : supplément plus faible, sans deuxième voie
    slim = PhysicsParams(**{**REF.__dict__, "cda_m2": 0.24})
    assert grade_offset_pct(v, head, 0.0, 0.0, slim, 4.0) < grade_offset_pct(v, head, 0.0, 0.0, REF, 4.0)


class Capture:
    def __init__(self, server) -> None:
        self.frames: list[dict] = []
        server.send_raw = self.frames.append

    def states(self) -> list[dict]:
        return [f for f in self.frames if f["type"] == "state"]


def make_session(tmp_path, monkeypatch, port, **wind):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    for key, value in wind.items():
        setattr(cfg.wind, key, value)
    drv = MockDriver(base_power_w=250.0, ramp_amplitude_w=0.0)
    s = CoreSession(cfg, driver=drv, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=tmp_path / "routes")
    return s, drv, Capture(s.server)


def start(s) -> None:
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)


def run(s, n, t0=100.0):
    for i in range(n):
        s._step(0.02, t0 + i * 0.02)


def test_feel_grade_in_sim_and_nothing_when_off(tmp_path, monkeypatch):
    s, drv, _ = make_session(tmp_path, monkeypatch, 5960, mode="fixed", speed_kmh=30.0,
                             from_deg=0.0, feel="grade", max_grade_offset_pct=3.0)
    start(s)
    run(s, 500)
    assert s.physics.p.wind_mps == pytest.approx(s._head_mps)
    assert s._head_mps != 0.0
    expected = grade_offset_pct(s.physics.v, s._head_mps, 0.0, s.state.alt, s.physics.p, 3.0)
    assert abs(s._wind_offset) <= 3.0
    # Le pas suivant recalcule le supplément avec la vitesse de ce pas : on compare au même instant.
    assert s._wind_offset == pytest.approx(expected, abs=0.05)
    assert drv.sim_wind_mps == 0.0   # feel = "grade" : champ vent FTMS inutilisé

    off, _, _ = make_session(tmp_path / "off", monkeypatch, 5962)
    start(off)
    run(off, 500)
    assert off._wind_offset == 0.0 and off._head_mps == 0.0 and off.physics.p.wind_mps == 0.0


def test_feel_ftms_passes_head_wind_and_keeps_grade(tmp_path, monkeypatch):
    s, drv, _ = make_session(tmp_path, monkeypatch, 5964, mode="fixed", speed_kmh=25.0,
                             from_deg=90.0, feel="ftms")
    start(s)
    run(s, 200)
    assert drv.sim_wind_mps == pytest.approx(s._head_mps)
    assert s._wind_offset == 0.0


def test_erg_wind_changes_speed_only(tmp_path, monkeypatch):
    workouts = tmp_path / "wk"
    workouts.mkdir()
    (workouts / "plat.zwo").write_text(
        '<workout_file><name>Plat</name><workout><SteadyState Duration="600" Power="0.8"/>'
        '</workout></workout_file>', encoding="utf-8")

    def erg_session(sub, port, **wind):
        monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / sub / "act")
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
        for key, value in wind.items():
            setattr(cfg.wind, key, value)
        drv = MockDriver(base_power_w=200.0, ramp_amplitude_w=0.0)
        s = CoreSession(cfg, driver=drv, inputs=[NullProvider()], journal_dir=tmp_path / sub / "j",
                        routes_root=tmp_path / sub / "routes", workouts_dir=workouts)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("select_workout", {"workout_id": "plat"}, 2)
        s._on_command("start", {}, 3)
        run(s, 1500)
        return s, drv

    calm, drv_calm = erg_session("calm", 5966)
    windy, drv_windy = erg_session("windy", 5968, mode="fixed", speed_kmh=40.0, from_deg=0.0)
    assert windy.state.mode == "ERG"
    assert drv_windy.target_power_w == drv_calm.target_power_w   # puissance demandée inchangée
    assert windy._wind_offset == 0.0
    assert windy.physics.s != pytest.approx(calm.physics.s, abs=1.0)   # la vitesse virtuelle change


def test_wind_frozen_during_pause(tmp_path, monkeypatch):
    s, _, _ = make_session(tmp_path, monkeypatch, 5970, mode="gusty", speed_kmh=30.0, gust_pct=60.0)
    start(s)
    run(s, 100)
    s._on_command("pause", {}, 3)
    before = s._wind_sample
    run(s, 500, 200.0)
    assert s._wind_sample == before


# --- critère 6 : trame state -------------------------------------------------------------

def test_state_frames_with_and_without_wind(tmp_path, monkeypatch):
    validator = jsonschema.Draft202012Validator(
        json.loads((IPC_DIR / "state.schema.json").read_text(encoding="utf-8")))
    s, _, cap = make_session(tmp_path, monkeypatch, 5972, mode="gusty", speed_kmh=20.0, gust_pct=30.0)
    start(s)
    run(s, 50)
    for frame_no in range(1, 62):   # trames 15, 31 (30 porte devices), 45 et 61
        s._frame_count = frame_no
        s.state.devices = {"trainer": {"status": "MOCK", "name": None, "address": None},
                           "click": [], "hr": {"status": "NONE", "source": None,
                                               "battery_pct": None}} if frame_no % 30 == 0 else None
        s._fill_wind_frame()
        s.server.send_state(s.state)
    frames = cap.states()
    with_wind = [f for f in frames if "wind" in f]
    assert len(with_wind) == 4                                # 2 fois par seconde sur 2 s
    assert not any("wind" in f and "devices" in f for f in frames)
    for f in frames:
        assert not list(validator.iter_errors(f))
        assert len(json.dumps(f, separators=(",", ":")).encode()) <= 1400
    assert with_wind[0]["wind"]["head_mps"] == round(s._head_mps, 2)

    off, _, cap_off = make_session(tmp_path / "off", monkeypatch, 5974)
    for frame_no in range(1, 31):
        off._frame_count = frame_no
        off._fill_wind_frame()
        off.server.send_state(off.state)
    assert not any("wind" in f for f in cap_off.states())


def test_wind_frame_rounding():
    frame = wind_frame(WindSample(5.123456, 359.97, 0.456), -3.14159)
    assert frame == {"speed_mps": 5.12, "from_deg": 360.0, "head_mps": -3.14, "gust": 0.46}


def test_journal_records_head_wind_and_offset(tmp_path, monkeypatch):
    s, _, _ = make_session(tmp_path, monkeypatch, 5976, mode="fixed", speed_kmh=20.0, from_deg=0.0)
    start(s)
    run(s, 200)
    rec = s._rec
    records = [line for line in rec.lines if line.get("kind") == "record"]
    assert records and records[-1]["head_mps"] is not None and records[-1]["wind_grade_pct"] is not None
    assert {"head_mps", "wind_grade_pct"} <= set(Record.__dataclass_fields__)


# --- critère 7 : configuration -----------------------------------------------------------

@pytest.mark.parametrize("section, message", [
    ({"speed_kmh": -3}, "speed_kmh"),
    ({"mode": "tempête"}, "mode"),
    ({"feel": "vibreur"}, "feel"),
    ({"max_grade_offset_pct": 9}, "max_grade_offset_pct"),
    ({"from_deg": 400}, "from_deg"),
])
def test_invalid_wind_config(section, message):
    with pytest.raises(ConfigError, match=message):
        config_mod.from_dict({"wind": section})


def test_wind_config_defaults_and_theme(tmp_path):
    cfg = Config()
    assert cfg.wind.mode == "off" and cfg.wind.feel == "grade" and cfg.wind.max_grade_offset_pct == 4.0
    theme = tmp_path / "Themes" / "breton"
    theme.mkdir(parents=True)
    (theme / "theme.json").write_text(json.dumps({"version": "1.2", "wind": {"speed_kmh": 35,
                                                  "from_deg": 225, "gust_pct": 50}}), encoding="utf-8")
    tw = theme_wind("breton", tmp_path / "Themes")
    assert tw == {"speed_kmh": 35, "from_deg": 225, "gust_pct": 50}
    cfg.wind.mode = "theme"
    model = WindModel.from_config(cfg.wind, tw)
    assert model.active and model.gusty and model.base_mps == pytest.approx(35 / 3.6)
    # Thème inconnu : vent du thème par défaut du dépôt
    assert theme_wind("absent", tmp_path / "Themes") is not None
