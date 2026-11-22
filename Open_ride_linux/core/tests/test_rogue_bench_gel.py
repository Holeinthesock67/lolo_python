"""Banc du Cyber-Rogue (lot R-gel) : aucun parcours classique demandé ni chargé pendant la run, pause comprise."""

import importlib.util
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name):
    sys.path.insert(0, str(TESTS))
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rb = _load("rogue_bench")

DEBUT = "[test] route_loaded id=demo length_m=5000.0 path=x\n[test] route_world_released trees=120\n"


def test_run_sans_chargement():
    log = DEBUT + "[test] state seq=1\n[test] rogue_scene_left\n[test] route_requested id=demo\n"
    assert rb.classic_loads_during_run(log) == []


def test_demo_demandee_en_pause():
    log = DEBUT + "[test] route_requested id=demo\n[test] route_loaded id=demo length_m=5000.0 path=x\n" \
        "[test] rogue_scene_left\n"
    assert len(rb.classic_loads_during_run(log)) == 2


def test_bornes_absentes():
    assert rb.classic_loads_during_run("[test] route_requested id=demo\n") is None
    assert rb.classic_loads_during_run(DEBUT) is None
