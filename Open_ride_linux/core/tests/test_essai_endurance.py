"""Essai d'endurance (lot EN1) : horloge murale décalée du core, anneau de la ligue, critères, sans Godot ni core
lancé en entier (l'essai à blanc `essai_endurance.py --court --sans-engine` est la vérification de bout en bout)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

ENGINE_TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
sys.path.insert(0, str(ENGINE_TESTS))

import essai_endurance as ee  # noqa: E402
from openride_core.route import load_world  # noqa: E402


def test_clock_offset_seen_by_child_and_monotonic_untouched(tmp_path: Path) -> None:
    (tmp_path / "montre.py").write_text(
        "import time\nprint(time.time(), time.monotonic())\n", encoding="utf-8")
    clock = ee.Clock(tmp_path / "horloge.json")
    target = datetime(2027, 1, 13, 18, 0)
    clock.set(target)
    env = {"PYTHONPATH": str(tmp_path), "PATH": "/usr/bin:/bin"}
    out = subprocess.run([sys.executable, str(ENGINE_TESTS / "horloge_decalee.py"), "montre", str(clock.path)],
                         capture_output=True, text=True, env=env, check=True, timeout=30).stdout.split()
    assert abs(float(out[0]) - target.timestamp()) < 5.0
    assert abs(float(out[1]) - time.monotonic()) < 60.0   # horloge monotone du système, non décalée


def test_clock_file_is_json_with_offset(tmp_path: Path) -> None:
    clock = ee.Clock(tmp_path / "h.json")
    data = json.loads(clock.path.read_text("utf-8"))
    assert abs(data["decalage_s"]) < 5.0 and "jour" in data


def test_ring_is_a_closed_loop(tmp_path: Path) -> None:
    ee.write_ring(tmp_path, 3000.0)
    world = tmp_path / f"{ee.ROUTE_ID}.world"
    data = json.loads((world / "route.json").read_text("utf-8"))
    assert data["type"] == "loop" and abs(data["length_m"] - 3000.0) < 20.0
    assert data["x"][0] == data["x"][-1] == 0.0 and data["z"][-1] == 0.0
    assert (world / "manifest.json").is_file()
    assert load_world(world).route.is_loop


def test_next_monday_is_strictly_after() -> None:
    assert ee.next_monday(date(2026, 11, 22)) == date(2026, 11, 23)   # dimanche → lundi
    assert ee.next_monday(date(2026, 11, 23)) == date(2026, 11, 30)   # lundi → lundi suivant


def test_gpu_budgets_match_perf_targets() -> None:
    targets = json.loads((ENGINE_TESTS / "perf_targets.json").read_text("utf-8"))["presets"]
    assert {q: float(v["gpu_ms_median_max"]) for q, v in targets.items()} == ee.GPU_BUDGET_MS


def test_limits_documented() -> None:
    doc = (ENGINE_TESTS.parents[1] / "docs" / "ESSAI_ENDURANCE.md").read_text("utf-8")
    for text in ("≤ 20 Mo/h", "≤ 400 Mo", "≤ 100 Mo/h", "≤ + 300 Mo", "≤ 50 Mo/h", "≤ + 10 %", "≤ 6 par heure",
                 "≤ 15 Mo par heure", "≤ 1 500 Ko", "≤ 100 Ko", "≤ 200 Ko", "≤ 200 Mo"):
        assert text in doc, text
