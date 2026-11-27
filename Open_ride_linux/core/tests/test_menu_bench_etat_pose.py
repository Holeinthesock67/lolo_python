"""Banc des menus : gestes et vérifications sur un menu posé (lot BM2, 26 novembre).

Trois échecs de la CI sans rapport avec les PR : vélodrome à la souris (#1093, #953) « A_LONG à la souris : clic sur
«  » : sans réponse » (écran Prêt reconstruit après le choix de l'épreuve, focus vide un instant, clic envoyé au
centre de l'écran) ; parcours_import (#964) : écran « Compilation de … » déjà passé quand l'engine, muet 13 s sur un
runner lent, a répondu. Cause commune : une décision prise sur un état du menu lu pendant qu'il change."""

import importlib.util
import json
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
    settled_focus = mb.Run.settled_focus
    wait_screen = mb.Run.wait_screen
    _screen_ok = mb.Run._screen_ok

    def __init__(self, etats):
        self.etats = list(etats)
        self.last = {}
        self.silent_s = 0.0
        self.checks = []
        self.engine = type("P", (), {"p": type("Q", (), {"poll": lambda self: None})()})()

    def state(self, timeout=10.0):
        if len(self.etats) > 1:
            self.last = self.etats.pop(0)
        else:
            self.last = self.etats[0]
        return self.last

    def slowdown(self):
        return 1.0

    def silence(self, since):
        return ""

    def check(self, ok, label, measure):
        self.checks.append((ok, label, measure))
        return ok


def _etat(screen, focus="", status="", items=("a", "b")):
    return {"visible": True, "screen": screen, "title": "", "status": status, "focus_id": focus,
            "items": [{"id": i, "label": i, "detail": "", "enabled": True} for i in items], "rows": []}


def test_focus_attendu_apres_reconstruction_de_l_ecran():
    run = FakeRun([_etat("ready"), _etat("ready"), _etat("ready", "track_event")])
    run.last = _etat("ready")                                   # lu pendant la reconstruction : pas de focus
    assert run.settled_focus(5.0) == "track_event"


def test_focus_jamais_revenu_donne_vide():
    run = FakeRun([_etat("ready")])
    run.last = _etat("ready")
    assert run.settled_focus(0.3) == ""


def test_ecran_transitoire_deja_passe():
    etape = {"ecran": "route_import", "statut": "^Compilation de essai", "transitoire": True, "delai": 0.2}
    suivant = {"ecran": "routes", "statut": "^Parcours ajouté : "}
    run = FakeRun([_etat("routes", "essai-import", "Parcours ajouté : essai-import")])
    run.wait_screen(etape, suivant)
    ok, label, measure = run.checks[-1]
    assert ok and "transitoire" in label and "déjà passé" in measure


def test_ecran_transitoire_ni_vu_ni_passe_echoue():
    etape = {"ecran": "route_import", "statut": "^Compilation de essai", "transitoire": True, "delai": 0.2}
    suivant = {"ecran": "routes", "statut": "^Parcours ajouté : "}
    run = FakeRun([_etat("home")])
    run.wait_screen(etape, suivant)
    assert run.checks[-1][0] is False


def test_ecran_ordinaire_ne_saute_pas_sur_le_suivant():
    etape = {"ecran": "route_import", "delai": 0.2}
    run = FakeRun([_etat("routes")])
    run.wait_screen(etape, {"ecran": "routes"})
    assert run.checks[-1][0] is False


def test_scenario_import_marque_l_ecran_de_compilation_transitoire():
    doc = json.loads((TESTS / "menu_scenarios" / "parcours_import.json").read_text(encoding="utf-8"))
    compil = [e for e in doc["etapes"] if str(e.get("statut", "")).startswith("^Compilation")]
    assert compil and all(e.get("transitoire") for e in compil)
    mb.load_scenario(TESTS / "menu_scenarios" / "parcours_import.json")   # clé connue du banc


def test_liste_remplie_par_le_core_attendue_avant_de_deplacer_le_focus():
    FakeRun.settled_items = mb.Run.settled_items
    vide = {**_etat("contents", items=()), "focus_id": ""}
    run = FakeRun([vide, vide, _etat("contents", "content:starter", items=("content:starter", "content:pack"))])
    st = run.settled_items("content:pack", 5.0)
    assert st["focus_id"] == "content:starter"


def test_liste_jamais_remplie_rend_le_dernier_etat():
    FakeRun.settled_items = mb.Run.settled_items
    vide = {**_etat("contents", items=()), "focus_id": ""}
    run = FakeRun([vide])
    assert run.settled_items("content:pack", 0.3)["items"] == []
