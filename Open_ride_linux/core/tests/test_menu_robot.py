"""Robot des menus (`engine/tests/menu_robot.py`) : parties sans Godot.

Le tableau bouton -> action suit la spécification générale §7.1 et les seuils du décodeur du Click, l'oracle
de navigation suit les règles de `menu_model.gd`, et chaque scénario livré est valide.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from openride_core import zwift_click
from openride_core.ble_sim import CLICK_BUTTONS

ENGINE_TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


@pytest.fixture(scope="module")
def robot():
    sys.path.insert(0, str(ENGINE_TESTS))
    try:
        spec = importlib.util.spec_from_file_location("menu_robot", ENGINE_TESTS / "menu_robot.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["menu_robot"] = mod   # ses dataclasses relisent leurs annotations dans le module
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.modules.pop("menu_robot", None)
        sys.path.remove(str(ENGINE_TESTS))


def test_table_follows_click_thresholds_and_buttons(robot):
    for name, b in robot.BOUTONS.items():
        assert b.click in CLICK_BUTTONS or b.click in ("+", "-"), name
        if name.endswith("court"):
            assert b.duree < zwift_click.SHORT_MAX_S, name
        elif name.endswith("long"):
            assert b.duree >= zwift_click.LONG_MIN_S, name
        elif name.endswith("flou"):
            assert zwift_click.SHORT_MAX_S < b.duree < zwift_click.LONG_MIN_S, name
    # Spécification générale §7.1, colonne « Menus ».
    effets = {k: b.effet for k, b in robot.BOUTONS.items()}
    assert effets["+ court"] == effets["A court"] == effets["droite"] == "suivant"
    assert effets["- court"] == effets["B court"] == effets["gauche"] == "precedent"
    assert (effets["+ long"], effets["- long"], effets["B long"]) == ("+5", "-5", "-5")
    assert (effets["A long"], effets["Y court"]) == ("valider", "retour")
    assert {effets[k] for k in ("Z court", "Z long", "haut", "bas", "+ flou", "- flou")} == {"rien"}
    # Souris (menu_view.gd) : molette, clic gauche sur l'élément, clic droit.
    assert robot.BOUTONS["+ court"].souris == "wheel_down" and robot.BOUTONS["- court"].souris == "wheel_up"
    assert robot.BOUTONS["A long"].souris == "left" and robot.BOUTONS["Y court"].souris == "right"
    for key, button in robot.SYNONYMES.items():
        assert button in robot.BOUTONS, key


def test_button_names(robot):
    assert robot.cle_bouton("− long") == "- long"
    assert robot.cle_bouton("A") == "A court"
    assert robot.cle_bouton("  +   court ") == "+ court"
    with pytest.raises(ValueError, match="bouton inconnu"):
        robot.cle_bouton("X long")


def test_focus_oracle_matches_menu_model_rules(robot):
    items = [{"id": str(i), "enabled": i != 2} for i in range(8)]
    fa = robot.focus_attendu
    assert fa(items, 1, "suivant") == 3              # saute l'élément désactivé
    assert fa(items, 7, "suivant") == 0              # boucle en fin de liste
    assert fa(items, 0, "precedent") == 7            # boucle au début
    assert fa(items, 0, "+5") == 6 and fa(items, 6, "+5") == 7   # cinq éléments actifs plus loin, borné
    assert fa(items, 7, "-5") == 1 and fa(items, 1, "-5") == 0
    assert fa(items, 4, "rien") == 4 and fa(items, -1, "suivant") == -1


def test_delivered_scenarios_are_valid_and_cover_the_menus(robot):
    scenarios = robot.charger_scenarios()
    assert len(scenarios) >= 10
    seen = set()
    for doc in scenarios.values():
        for st in doc["etapes"]:
            seen.update(v for k in ("ecran", "attendre_ecran") if isinstance(v := st.get(k), str))
    # Accueil, réglages, appareils, parcours, entraînements, plans, FTP, pause, bilan, Garage, confirmations,
    # Cyber-Rogue.
    assert {"connect", "home", "settings", "settings_group", "pairing", "routes", "ready", "workouts",
            "workout_create", "workout_import", "plans", "plan", "ftp_test", "pause", "summary", "garage",
            "confirm", "records", "rogue_start"} <= seen
    used = {c for doc in scenarios.values() for c in doc.get("canaux", robot.CANAUX)}
    assert used == set(robot.CANAUX)


@pytest.mark.parametrize("doc, message", [
    ({"etapes": []}, "liste non vide"),
    ({"etapes": [{"bouton": "X"}]}, "bouton inconnu"),
    ({"etapes": [{"note": "seule"}]}, "aucune action ni vérification"),
    ({"etapes": [{"bouton": "A long", "ouvrir": "settings"}]}, "une seule action"),
    ({"etapes": [{"touche": "F12"}]}, "touche inconnue"),
    ({"canaux": ["manette"], "etapes": [{"ecran": "home"}]}, "canal inconnu"),
    ({"etapes": [{"ecran": "home", "couleur": "rouge"}]}, "clé(s) inconnue(s) couleur"),
    ({"preparation": {"velo": 1}, "etapes": [{"ecran": "home"}]}, "preparation"),
])
def test_scenario_validation(robot, doc, message):
    with pytest.raises(robot.ScenarioError, match=message.replace("(", r"\(").replace(")", r"\)")):
        robot.valider_scenario("essai", doc)
