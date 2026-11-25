"""Banc des menus : `end_session` attend la séance partie (scénario `bots_elo` instable sur la CI, trains #1050 et
#1062 : la commande arrivait pendant la préparation du décor du Grand Prix, le core la prenait pour une annulation
du départ et le menu restait sur l'écran Prêt au lieu de « Fin de séance »)."""

import importlib.util
import json
import re
import sys
import threading
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mb = _load("menu_bench")


class FakeCore:
    """Journal du core : mêmes `lines`, `matching` et `wait_for` que `e2e_check.Proc`."""

    def __init__(self, lines=()):
        self.lines = [(float(i), line) for i, line in enumerate(lines)]
        self._lock = threading.Lock()

    def add(self, line):
        with self._lock:
            self.lines.append((self.lines[-1][0] + 1.0 if self.lines else 0.0, line))

    def matching(self, pattern):
        rx = re.compile(pattern)
        return [(t, m) for t, line in list(self.lines) if (m := rx.search(line))]

    def wait_for(self, pattern, timeout, after=0.0):
        rx = re.compile(pattern)
        deadline = time.monotonic() + timeout
        while True:
            for t, line in list(self.lines):
                m = rx.search(line)
                if m and t >= after:
                    return t, m
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.01)


class FakeRun:
    wait_session_started = mb.Run.wait_session_started

    def __init__(self, core):
        self.core = core
        self.checks = []

    def check(self, ok, label, measure):
        self.checks.append((ok, label, measure))
        return ok


START = "core INFO Commande start {'mode': 'grandprix'} (id=7)"


def test_waits_for_running_after_last_start() -> None:
    core = FakeCore(["core INFO Séance : IDLE -> READY", START, "core INFO Départ : étape decor -> "])
    run = FakeRun(core)
    threading.Timer(0.2, core.add, ["core INFO Séance : READY -> RUNNING"]).start()
    t0 = time.monotonic()
    run.wait_session_started(5.0)
    assert time.monotonic() - t0 >= 0.15        # n'envoie pas end_session pendant le décor
    assert run.checks and run.checks[-1][0] and "RUNNING" in run.checks[-1][2]


def test_old_session_does_not_count() -> None:
    # séance d'avant finie, puis nouveau départ : son FINISHED ne vaut pas départ
    core = FakeCore(["core INFO Commande start {} (id=1)", "core INFO Séance : READY -> RUNNING",
                     "core INFO Séance : RUNNING -> FINISHED", "core INFO Séance : FINISHED -> READY", START,
                     "core INFO Départ : étape decor -> "])
    run = FakeRun(core)
    run.wait_session_started(0.2)
    ok, label, measure = run.checks[-1]
    assert not ok and "séance partie" in label and "Départ : étape decor" in measure


def test_no_start_no_wait() -> None:
    run = FakeRun(FakeCore(["core INFO Séance : IDLE -> READY"]))
    run.wait_session_started(5.0)
    assert run.checks == []


def test_bots_elo_waits_running_before_end() -> None:
    steps = json.loads((TESTS / "menu_scenarios" / "bots_elo.json").read_text(encoding="utf-8"))["etapes"]
    end = next(i for i, s in enumerate(steps) if s.get("commande") == "end_session")
    assert any(s.get("motif") == "-> RUNNING" for s in steps[:end])
    assert mb.SESSION_START_S >= 120
