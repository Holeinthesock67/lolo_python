"""Banc des menus, voie clavier : un geste non reçu dit si l'engine a accusé la touche (lot GF8).

Bancs rGL2 de #1054 (24/11, high et low) : « LEFT_SHORT reçu par l'engine : aucune ligne « (Bip|Souris) : LEFT_SHORT »
(engine muet 14,5 s) ». La touche part en un seul datagramme sur le port des trames `state` ; pendant un gel du fil
principal, le tampon du noyau se remplit de trames et la touche se perd : défaut de l'outil, pas de la PR. Un premier
essai renvoyait la touche sans accusé : au cloud, une touche tardive faisait alors un double appui (trains #1170 et
#1172) ; le banc ne renvoie plus rien et le dit seulement."""

import importlib.util
import re
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


class FakeEngine:
    def __init__(self, lines):
        self.lines = lines

    def matching(self, pattern):
        rx = re.compile(pattern)
        return [(t, m) for t, line in self.lines if (m := rx.search(line))]


class FakeRun:
    key_note = mb.Run.key_note

    def __init__(self, lines):
        self.engine = FakeEngine(lines)


def test_touche_jamais_accusee_est_un_defaut_du_banc():
    run = FakeRun([(1.0, "[test] key done=Left shift=false hold_ms=150")])   # appui précédent
    assert "perdue par le banc (outil)" in run.key_note("LEFT_SHORT", 5.0)


def test_touche_accusee_puis_sans_bip():
    run = FakeRun([(6.0, "[test] key done=Left shift=false hold_ms=150")])
    assert "accusée par l'engine, perdue après" in run.key_note("LEFT_SHORT", 5.0)
    # touche voisine au nom plus long : pas un accusé de « Left »
    run = FakeRun([(6.0, "[test] key done=LeftBracket shift=false hold_ms=150")])
    assert "perdue par le banc" in run.key_note("LEFT_SHORT", 5.0)


def test_plus_aucun_renvoi_de_touche():
    assert not hasattr(mb.Run, "send_key") and not hasattr(mb, "KEY_DONE_S")
