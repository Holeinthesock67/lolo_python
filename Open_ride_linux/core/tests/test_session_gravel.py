"""Gravel dans la séance (lot U21) : supplément de pente en SIM ajouté au vent sous la borne commune,
vitesse virtuelle seule en ERG, surface imposée, gravel coupé identique à avant, journal et bilan."""

from __future__ import annotations

import json
import logging

import pytest

from openride_core import fit_export, surface_physics
from openride_core.config import Config
from openride_core.demo_world import write_world
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.tools import log_report


def _world(routes, name: str, surface: str | None) -> None:
    world = write_world(routes, name, 3000.0, created="2026-10-30T00:00:00+00:00", grade=lambda s: 0.0)
    if surface is not None:
        route = json.loads((world / "route.json").read_text(encoding="utf-8"))
        route["surface"] = [surface] * route["n"]
        (world / "route.json").write_text(json.dumps(route), encoding="utf-8")


def make_session(tmp_path, monkeypatch, port, route="plat", surface=None, workout=None, gravel=None, wind=None):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    for key, value in (gravel or {}).items():
        setattr(cfg.gravel, key, value)
    for key, value in (wind or {}).items():
        setattr(cfg.wind, key, value)
    routes = tmp_path / "routes"
    routes.mkdir(parents=True, exist_ok=True)
    _world(routes, route, surface)
    workouts = tmp_path / "wk"
    workouts.mkdir(exist_ok=True)
    (workouts / "plat.zwo").write_text(
        '<workout_file><name>Plat</name><workout><SteadyState Duration="600" Power="0.8"/>'
        '</workout></workout_file>', encoding="utf-8")
    drv = MockDriver(base_power_w=200.0, ramp_amplitude_w=0.0)
    s = CoreSession(cfg, driver=drv, inputs=[NullProvider()], journal_dir=tmp_path / "journal",
                    routes_root=routes, workouts_dir=workouts)
    s._on_command("select_route", {"route_id": route}, 1)
    if workout:
        s._on_command("select_workout", {"workout_id": workout}, 2)
    s._on_command("start", {}, 3)
    return s, drv


def run(s, n, t0=100.0):
    for i in range(n):
        s._step(0.02, t0 + i * 0.02)


def _records(s) -> list[dict]:
    return [line for line in s._rec.lines if line.get("kind") == "record"]


def test_off_leaves_session_unchanged(tmp_path, monkeypatch) -> None:
    s, _ = make_session(tmp_path, monkeypatch, 6900, surface="dirt")
    run(s, 500)
    assert s.physics.p is s._base_params and s._gravel_offset == 0.0
    recs = _records(s)
    assert recs and all("surface" not in r and "gravel_grade_pct" not in r for r in recs)


def test_auto_on_dirt_route_sends_offset(tmp_path, monkeypatch) -> None:
    s, drv = make_session(tmp_path, monkeypatch, 6902, surface="dirt", gravel={"mode": "auto"})
    run(s, 500)
    assert s._gravel_factor == 3.0
    assert s._gravel_offset == pytest.approx(0.8, abs=0.01)       # (3 − 1) × 0,004 × 100 sur le plat
    assert s.physics.p.crr == pytest.approx(0.012) and s._base_params.crr == pytest.approx(0.004)
    recs = _records(s)
    assert recs[-1]["surface"] == "dirt" and recs[-1]["gravel_grade_pct"] == pytest.approx(0.8, abs=0.01)


def test_forced_gravel_on_route_without_column(tmp_path, monkeypatch) -> None:
    forced, _ = make_session(tmp_path / "f", monkeypatch, 6904, gravel={"mode": "gravel"})
    run(forced, 300)
    assert forced._gravel_offset == pytest.approx(0.6, abs=0.01)
    auto, _ = make_session(tmp_path / "a", monkeypatch, 6906, gravel={"mode": "auto"})
    run(auto, 300)
    assert auto._gravel_offset == 0.0 and auto._gravel_factor == 1.0
    assert _records(auto)[-1]["surface"] == "paved"


def test_wind_and_gravel_capped_together(tmp_path, monkeypatch) -> None:
    assert surface_physics.combined_offset_pct(3.8, 0.6, 4.0) == 4.0          # critère 3
    assert surface_physics.combined_offset_pct(1.0, 0.6, 4.0) == pytest.approx(1.6)
    s, _ = make_session(tmp_path, monkeypatch, 6908, gravel={"mode": "gravel"},
                        wind={"mode": "fixed", "speed_kmh": 60.0, "from_deg": 0.0, "max_grade_offset_pct": 4.0})
    run(s, 1500)
    assert s._wind_offset == pytest.approx(4.0)    # vent seul déjà à la borne : le gravel n'ajoute rien
    assert s._gravel_offset == pytest.approx(0.6, abs=0.01) and s._gravel_sent == pytest.approx(0.0, abs=1e-9)


def test_erg_power_unchanged_speed_lower(tmp_path, monkeypatch) -> None:
    paved, drv_p = make_session(tmp_path / "p", monkeypatch, 6910, surface="paved", workout="plat",
                                gravel={"mode": "auto"})
    dirt, drv_d = make_session(tmp_path / "d", monkeypatch, 6912, surface="dirt", workout="plat",
                               gravel={"mode": "auto"})
    run(paved, 1500)
    run(dirt, 1500)
    assert dirt.state.mode == "ERG"
    assert drv_d.target_power_w == drv_p.target_power_w
    assert dirt.physics.s < paved.physics.s - 1.0


def test_summary_line_read_by_log_report(tmp_path, monkeypatch, caplog) -> None:
    s, _ = make_session(tmp_path, monkeypatch, 6914, surface="gravel", gravel={"mode": "auto"})
    run(s, 500)
    with caplog.at_level(logging.INFO, logger="core"):
        s._log_gravel()
    line = next(r for r in caplog.records if r.getMessage().startswith("Gravel :"))
    rep = log_report.analyse([f"2026-10-30 10:00:00,000 INFO     core {line.getMessage()}"])
    assert rep.gravel and rep.gravel[0]["mode"] == "auto" and rep.gravel[0]["unpaved_m"] > 0
