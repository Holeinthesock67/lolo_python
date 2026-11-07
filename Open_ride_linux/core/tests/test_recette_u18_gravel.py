"""Recette U18, étape vélo gravel (7bu) : critères §5.4 lus au journal d'une séance simulée.

Séance du core avec le trainer simulé sur un parcours plat à portions non revêtues, en SIM puis en ERG libre
(lot O18) ; seules les fonctions pures de `engine/tests/recette_u18.py` sont appelées (sans Godot)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from openride_core import fit_export
from openride_core.config import Config
from openride_core.demo_world import write_world
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.physics import PhysicsParams, steady_speed
from openride_core.session import CoreSession

ENGINE_TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
sys.path.insert(0, str(ENGINE_TESTS))

import recette_u18 as ru  # noqa: E402

PORT = 6980


def _surface(s: float) -> str:
    """Comme `demo-biomes-gravel` : un tiers de chaque bloc de 2 km non revêtu, gravel puis dirt."""
    block, x = divmod(s, 2000.0)
    if 700.0 <= x < 700.0 + 2000.0 / 3.0:
        return "gravel" if block % 2 == 0 else "dirt"
    return "paved"


def _session(tmp_path, monkeypatch, port: int, mode: str = "auto") -> CoreSession:
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    cfg.gravel.mode = mode
    routes = tmp_path / "routes"
    routes.mkdir(parents=True, exist_ok=True)
    world = write_world(routes, "demo-gravel", 6000.0, created="2026-11-07T00:00:00+00:00", grade=lambda s: 0.0)
    route = json.loads((world / "route.json").read_text(encoding="utf-8"))
    route["surface"] = [_surface(i * route["ds_m"]) for i in range(route["n"])]
    (world / "route.json").write_text(json.dumps(route), encoding="utf-8")
    s = CoreSession(cfg, driver=MockDriver(base_power_w=200.0, ramp_amplitude_w=0.0), inputs=[NullProvider()],
                    journal_dir=tmp_path / "journal", routes_root=routes, workouts_dir=tmp_path / "wk")
    s._on_command("select_route", {"route_id": "demo-gravel"}, 1)
    s._on_command("start", {}, 2)
    return s


def _ride(s: CoreSession, seconds: float, t0: float) -> float:
    n = int(seconds / 0.02)
    for i in range(n):
        s._step(0.02, t0 + i * 0.02)
    return t0 + n * 0.02


def _records(s: CoreSession) -> list[dict]:
    return [line for line in s._rec.lines if line.get("kind") == "record"]


def test_sim_puis_erg_libre_passe_les_criteres(tmp_path, monkeypatch):
    s = _session(tmp_path, monkeypatch, PORT)
    t = _ride(s, 300.0, 100.0)                       # SIM : bitume, gravel (700 m), bitume
    s._on_command("set_ride_mode", {"mode": "erg", "target_w": 200}, 3)
    _ride(s, 300.0, t)                               # ERG : bitume puis dirt (2,7 km)
    rows = _records(s)
    res = ru.gravel_stats(rows, PhysicsParams(), steady_speed)
    checks = ru.gravel_checks(res)
    assert [c["ok"] for c in checks] == [True, True, True, True], checks
    assert res["sim_non_revetu"]["gravel_pct"] > 0.5 and res["sim_bitume"]["gravel_pct"] < 0.01
    assert res["erg_non_revetu"]["speed_kmh"] < res["erg_bitume"]["speed_kmh"]
    assert res["offset_sent_max"] <= 4.0


def test_gravel_sans_effet_est_refuse(tmp_path, monkeypatch):
    """Supplément nul en non revêtu (facteurs à 1) : le critère SIM échoue, il n'est pas « non jugé »."""
    s = _session(tmp_path, monkeypatch, PORT)
    for key in ("factor_compacted", "factor_gravel", "factor_dirt"):
        setattr(s.cfg.gravel, key, 1.0)
    _ride(s, 300.0, 100.0)
    checks = ru.gravel_checks(ru.gravel_stats(_records(s), PhysicsParams(), steady_speed))
    assert checks[0]["ok"] is False
    assert checks[2]["ok"] is None and checks[3]["ok"] is None    # pas d'ERG roulé


def test_steady_records_ecarte_les_transitions():
    rows = [{"distance": float(d), "speed": 8.0, "surface": "gravel" if 700 <= d < 1000 else "paved", "mode": "SIM"}
            for d in range(0, 1500, 10)]
    kept = [r["distance"] for r in ru.steady_records(rows)]
    assert 750.0 not in kept and 800.0 in kept and 1050.0 not in kept and 1100.0 in kept


def test_commande_ecrit_le_resume_sans_trace_nommee(tmp_path, monkeypatch):
    s = _session(tmp_path, monkeypatch, PORT)
    _ride(s, 120.0, 100.0)
    journal = tmp_path / "j.jsonl"
    lines = [{"kind": "header", "route_id": "ma-sortie-du-dimanche"}] + _records(s)
    journal.write_text("\n".join(json.dumps(r) for r in lines) + "\n", encoding="utf-8")
    code = ru.main(["gravel", str(journal), "--out", str(tmp_path / "out")])
    text = (tmp_path / "out" / "resume_gravel.md").read_text(encoding="utf-8")
    assert code in (0, 1)
    assert "trace personnelle" in text and "dimanche" not in text
