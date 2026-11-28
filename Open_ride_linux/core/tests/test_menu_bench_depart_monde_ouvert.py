"""Banc des menus : gabarit unique du départ du monde ouvert (`depart_monde_ouvert`, après le lot W18)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


mb = _load("menu_bench")


def _write(tmp_path: Path, steps: list, **head) -> Path:
    p = tmp_path / "essai.json"
    p.write_text(json.dumps({"description": "essai", "voies": ["clavier"], **head, "etapes": steps}), encoding="utf-8")
    return p


def test_every_scenario_loads() -> None:
    for name, path in mb.scenarios().items():
        assert mb.load_scenario(path)["etapes"], name


def test_open_world_scenarios_all_use_the_template() -> None:
    """Tout scénario qui part en monde ouvert passe par le gabarit : aucun départ recopié à la main."""
    users = []
    for name, path in mb.scenarios().items():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if any("depart_monde_ouvert" in s for s in raw.get("etapes", [])):
            users.append(name)
    assert {"w17_cap", "ea1_lac", "ea2_lac_loin", "ea3_riviere", "ea4_pont", "ea5_tunnel", "ow_6km"} <= set(users)


def test_template_is_the_w18_start(tmp_path) -> None:
    steps = mb.load_scenario(_write(tmp_path, [{"depart_monde_ouvert": {"recherche": "saint jorioz",
                                                                         "contient": "Saint-Jorioz"}},
                                               {"attendre": 1}]))["etapes"]
    keys = [s["touche"] for s in steps if "touche" in s and s["touche"] != "Enter"]
    assert keys == list("saint") + ["Space"] + list("jorioz")
    motifs = [s["motif"] for s in steps if "journal" in s]
    assert motifs == ["Monde ouvert prêt", "Commande start ", "-> RUNNING"]
    # Lot W18 : ni accueil ni écran Prêt après le préchargement
    after_ready = steps[next(i for i, s in enumerate(steps) if s.get("motif") == "Monde ouvert prêt"):]
    assert not any("ecran" in s or "choisir" in s for s in after_ready)
    assert [s["capture"] for s in steps if "capture" in s] == ["carte", "cap", "depart"]
    assert next(s for s in steps if s.get("monde") == "search")["contient"] == ["Saint-Jorioz"]
    assert steps[-1] == {"attendre": 1}


def test_cap_steps_are_played_on_the_setup_screen(tmp_path) -> None:
    cap = [{"touche": "Minus"}, {"capture": "cap_auto"}]
    steps = mb.load_scenario(_write(tmp_path, [{"depart_monde_ouvert": {"recherche": "a", "cap": cap}}]))["etapes"]
    i = next(i for i, s in enumerate(steps) if s.get("monde") == "setup")
    assert steps[i + 1:i + 3] == cap and steps[i + 3] == {"capture": "cap"}
    assert next(s for s in steps if s.get("monde") == "search")["contient"] == ["a"]   # défaut : la recherche


def test_copied_start_is_refused(tmp_path) -> None:
    old = [{"journal": "core", "motif": "Monde ouvert prêt", "delai": 600}, {"ecran": "home"}, {"choisir": "ride"}]
    with pytest.raises(mb.ScenarioError, match="depart_monde_ouvert"):
        mb.load_scenario(_write(tmp_path, old))


@pytest.mark.parametrize("step", [
    {"depart_monde_ouvert": {}},
    {"depart_monde_ouvert": {"recherche": " "}},
    {"depart_monde_ouvert": {"recherche": "a", "lieu": "b"}},
    {"depart_monde_ouvert": {"recherche": "a"}, "delai": 3},
    {"depart_monde_ouvert": {"recherche": "a", "cap": [{"inconnue": 1}]}},
    {"depart_monde_ouvert": {"recherche": "a", "cap": [{"depart_monde_ouvert": {"recherche": "b"}}]}},
])
def test_bad_template_is_refused(tmp_path, step) -> None:
    with pytest.raises(mb.ScenarioError):
        mb.load_scenario(_write(tmp_path, [step]))


def test_template_keeps_its_lanes(tmp_path) -> None:
    steps = mb.load_scenario(_write(tmp_path, [{"voies": ["click"], "depart_monde_ouvert": {"recherche": "ab"}}]))
    lanes = [s.get("voies") for s in steps["etapes"]]
    assert all(v is not None for v in lanes)
    assert [s for s in steps["etapes"] if "touche" in s and s["touche"] != "Enter"][0]["voies"] == []   # lettres : clavier


def test_menu_ferme_attendu_apres_le_monde_pret(tmp_path) -> None:
    """26/11, Grenoble : la fermeture du menu dépend du préchargement ; elle s'attend après « Monde ouvert prêt »
    (événement, délai large), jamais sur une durée fixe avant lui."""
    steps = mb.load_scenario(_write(tmp_path, [{"depart_monde_ouvert": {"recherche": "grenoble"}}]))["etapes"]
    pret = next(i for i, s in enumerate(steps) if s.get("motif") == "Monde ouvert prêt")
    ferme = next(i for i, s in enumerate(steps) if s.get("monde") is False)
    assert pret < ferme
    assert steps[pret]["delai"] >= 900 and steps[ferme]["delai"] <= 120
