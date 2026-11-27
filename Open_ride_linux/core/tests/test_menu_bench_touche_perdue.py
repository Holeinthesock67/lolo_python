"""Banc des menus, voie clavier : touche perdue pendant un blocage de l'engine, renvoyée une fois (lot GF8).

Bancs rGL2 de #1054 (24/11, high et low) : « LEFT_SHORT reçu par l'engine : aucune ligne « (Bip|Souris) : LEFT_SHORT »
(engine muet 14,5 s) ». La touche part en un seul datagramme sur le port des trames `state` ; pendant un gel du fil
principal, le tampon du noyau se remplit de trames et la touche se perd. Défaut de l'outil, pas de la PR."""

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


class FakeRun:
    send_key = mb.Run.send_key

    def __init__(self, acks):
        self.acks = list(acks)          # réponse de l'engine à chaque attente d'accusé
        self.sent = []
        self.waited = []
        self.renvois = []
        self.silent_s = 0.0
        self.engine = type("P", (), {"t_start": 0.0, "p": type("Q", (), {"poll": lambda self: None})()})()

    def _send(self, msg):
        self.sent.append(msg)

    def wait_engine(self, pattern, delay, after):
        self.waited.append((pattern, delay))
        ack = self.acks.pop(0)
        if ack is None:
            self.silent_s += 14.5
        return ack

    def silence(self, since):
        return f" (engine muet {self.silent_s - since:.1f} s)" if self.silent_s - since >= 1.0 else ""


def test_accuse_recu_une_seule_touche():
    run = FakeRun([(1.0, object())])
    run.send_key("LEFT_SHORT", "Left", False, 150, 5.0)
    assert len(run.sent) == 1 and not run.renvois
    pattern, delay = run.waited[0]
    assert "key done=Left " in pattern and delay == 0.15 + mb.KEY_DONE_S


def test_touche_perdue_renvoyee_une_fois_et_relevee():
    run = FakeRun([None])
    t = run.send_key("RIGHT_SHORT", "Right", False, 150, 5.0)
    assert len(run.sent) == 2 and run.sent[0] == run.sent[1]
    assert t >= 0.0 and run.renvois == ["RIGHT_SHORT à 5 s (engine muet 14.5 s)"]


def test_motif_de_l_accuse_correspond_a_la_ligne_de_l_engine():
    import re
    run = FakeRun([(1.0, object())])
    run.send_key("LEFT_SHORT", "Left", False, 150, 0.0)
    assert re.search(run.waited[0][0], "[test] key done=Left shift=false hold_ms=150")
    assert not re.search(run.waited[0][0], "[test] key done=LeftBracket shift=false hold_ms=150")
