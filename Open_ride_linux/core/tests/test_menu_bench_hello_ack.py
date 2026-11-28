"""Banc des menus : engine sans hello_ack (train #1151 du 27 novembre, passage collection, 1 sur 18, vert au rejeu,
rien au journal pour trancher) : diagnostic écrit, puis une seule relance de l'engine, dite au rapport."""

import importlib.util
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mb = _load("menu_bench")


class _P:
    def __init__(self, rc):
        self.rc = rc

    def poll(self):
        return self.rc


class _Proc:
    def __init__(self, lines, rc=None):
        self.lines = [(0.0, line) for line in lines]
        self.p = _P(rc)

    def matching(self, pattern):
        import re
        rx = re.compile(pattern)
        return [(t, m) for t, line in self.lines if (m := rx.search(line))]


def test_diagnostic_says_alive_or_dead_hello_seen_and_last_lines():
    engine = _Proc(["Godot Engine v4.7.2", "", "Chargement du thème", "Parcours prêt"])
    core = _Proc(["Core démarré", "Reçu 'hello' de l'engine version 6.0 (contrat 1.41)"])
    d = mb.hello_diagnostic(engine, core, 40.0)
    assert d.startswith("engine encore vivant après 40 s ; hello reçu par le core ; 3 ligne(s)")
    assert d.endswith("Godot Engine v4.7.2 | Chargement du thème | Parcours prêt")
    d = mb.hello_diagnostic(_Proc([], rc=139), _Proc(["Core démarré"]), 40.0)
    assert "engine arrêté (code 139)" in d and "hello jamais reçu" in d and "journal vide" in d
    assert "hello jamais reçu" in mb.hello_diagnostic(_Proc([]), None, 40.0)


def test_relaunch_is_written_in_the_start_of_a_pass():
    src = (TESTS / "menu_bench.py").read_text(encoding="utf-8")
    start = src[src.index("    def start(self"):src.index("    def wait_engine_ready")]
    assert "engine sans hello_ack" in start and "_relance.log" in start and "après une relance" in start
    assert start.count('wait_for(r"hello_ack reçu", HELLO_ACK_S)') == 2   # une seule relance
