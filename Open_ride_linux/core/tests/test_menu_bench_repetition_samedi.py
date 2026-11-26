"""Répétition du samedi 28/11 (lot REP1) : scénario `repetition_samedi` du banc des menus et motif de `choisir`."""

import importlib.util
import sys
from pathlib import Path

from openride_core import bot_elo, league

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mb = _load("menu_bench")
SCENARIO = mb.SCENARIOS_DIR / "repetition_samedi.json"


def test_scenario_charge_et_profil_d_essai_lisible():
    sc = mb.load_scenario(SCENARIO)
    files = sc["fichiers"]
    # jamais le cache réel du monde ouvert ni le réseau : HOME temporaire du banc seulement
    assert not sc.get("caches_reels") and not sc.get("reseau")
    season = league.Season.from_dict(files["OpenRide/Profils/principal/ligue.json"])
    assert season.number == 2   # après la remise à zéro, l'écran doit dire « saison 1 », pas « saison 3 »
    assert bot_elo.EloBook.from_dict(files["OpenRide/Profils/principal/elo.json"]).races == 14
    steps = sc["etapes"]
    # la manche se termine par le vrai geste (Y puis A maintenu), pas par la commande end_session
    assert not any(s.get("commande") == "end_session" for s in steps)
    gestes = [s.get("appui") for s in steps if "appui" in s]
    assert gestes[-2:] == ["Y_SHORT", "A_LONG"]


class _Run(mb.Run):
    def __init__(self, items):
        self.engine = object()
        self.voie = "click"
        self._items = items
        self.moved = []

    def state(self):
        return {"items": self._items, "rows": []}

    def move_focus(self, item):
        self.moved.append(item)
        return True

    def gesture(self, name):
        return name == "A_LONG"


def test_choisir_motif_premier_element_actif():
    items = [{"id": "b:20261125-0700_restauration", "enabled": True},
             {"id": "b:20261125-0641_semaine", "enabled": False},
             {"id": "b:20261118-0641_semaine", "enabled": True}]
    run = _Run(items)
    assert run.choose("b:*_semaine")
    assert run.moved == ["b:20261118-0641_semaine"]
    assert not _Run(items).choose("b:*_mise-a-jour")
