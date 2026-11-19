"""Liste finale du jeu de base (lot NT1, nettoyage et intégration des démos avant l'installateur J9).

Une seule liste fait foi : le « Col du lacet » (`demo_world.DEMO_NAME`), les démonstrations des biomes marquées
pour le jeu de base dans `openride_compiler.demo_biomes.DEMO_SET` (`GAME_DEMOS`) et les pistes de
`velodrome.TRACKS`. Ce test la verrouille (décisions du propriétaire des 9, 12, 13 et 14 novembre 2026) et vérifie
que les outils de la recette suivent la même liste : `engine/tests/captures_demo.py` (captures de chaque parcours)
et le scénario de menus `parcours_demo` (liste des parcours, écran Prêt de chacun, modes Grand Prix et Vélodrome).
Le pack « Cols célèbres » (lot PK1) vient du paquet et n'est pas dans cette liste.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from openride_core import demo_world, mode_routes
from openride_core.velodrome import TRACKS

demo_biomes = pytest.importorskip("openride_compiler.demo_biomes")

REPO = Path(__file__).resolve().parents[2]
CAPTURES = REPO / "engine" / "tests" / "captures_demo.py"
SCENARIO = REPO / "engine" / "tests" / "menu_scenarios" / "parcours_demo.json"

FINAL = {   # identifiant de fichier → nom au menu
    "demo": "Col du lacet",
    "demo-biomes-paysages": "Tour des nouveaux paysages",
    "demo-japon": "Route des Érables",
    "demo-circuit": "Circuit des Prés",
    "demo-recif": "Récif des tortues",
    "demo-volcan": "Volcan en flammes",
    "demo-biomes-sud": "Route du Sud",
    "demo-biomes-nord": "Route du Grand Nord",
    "velodrome-250": "Vélodrome 250 m",
}
RETIRED = ("demo-biomes-tour", "demo-biomes-gravel", "demo-biomes-cote", "demo-biomes-alpin")
MODE_ROUTES = {"demo-circuit": "grandprix", "velodrome-250": "track"}   # hors de la liste générale (lot GP13)


def _base_game() -> dict[str, str]:
    titles = {name: title for name, title, *_, base in demo_biomes.DEMO_SET if base}
    return {demo_world.DEMO_NAME: demo_world.DEMO_TITLE, **titles, **{k: t.name for k, t in TRACKS.items()}}


def test_final_list_is_locked() -> None:
    assert _base_game() == FINAL
    assert demo_biomes.RETIRED_DEMOS == RETIRED and not set(RETIRED) & set(FINAL)
    assert tuple(demo_biomes.GAME_DEMOS) == tuple(n for n, *_, base in demo_biomes.DEMO_SET if base)


def test_every_route_has_a_fiche_and_modes_by_tag() -> None:
    """Chaque parcours du jeu de base a une description au menu ; seuls le circuit et la piste sont d'un mode."""
    libs = {demo_world.DEMO_NAME: demo_world.DEMO_LIBRARY,
            **{n: demo_biomes.library_of(n) for n in demo_biomes.GAME_DEMOS}}
    for name in FINAL:
        if name in TRACKS:
            continue   # fiche de la piste : `velodrome.build_manifest`
        assert libs[name] and libs[name]["description"], name
    modes = {n: mode_routes.mode_of(lib) for n, lib in libs.items() if mode_routes.mode_of(lib)}
    assert modes == {k: v for k, v in MODE_ROUTES.items() if k not in TRACKS}


def _captures_routes() -> tuple[str, ...]:
    tree = ast.parse(CAPTURES.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "ROUTES" for t in node.targets):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("ROUTES introuvable dans captures_demo.py")


def test_captures_follow_the_list() -> None:
    """Captures de la recette : chaque parcours du jeu de base sauf la piste (déjà vue par son propre banc)."""
    assert sorted(_captures_routes()) == sorted(n for n in FINAL if n not in TRACKS)


def test_menu_scenario_follows_the_list() -> None:
    steps = json.loads(SCENARIO.read_text(encoding="utf-8"))["etapes"]
    listing = next(s for s in steps if s.get("titre") == "Parcours")
    free = [n for n in FINAL if n not in MODE_ROUTES]
    assert listing["elements"] == free
    # carte de détail du premier parcours de la liste (tri par nom) : sa fiche (lot NT1)
    assert listing["contient"] == [FINAL[n] for n in free] + [demo_world.DEMO_LIBRARY["description"]]
    absent = set(listing["absent"])
    assert {"Fictif", "Fictive", "demo-biomes"} <= absent
    assert {FINAL[n] for n in MODE_ROUTES} | set(MODE_ROUTES) <= absent
    retired_titles = {title for name, title, *_ in demo_biomes.DEMO_SET if name in RETIRED}
    assert retired_titles == {"Tour des six paysages", "demo-biomes-gravel", "Route de la côte", "Montée alpine"}
    assert retired_titles <= absent
    titles = {s["titre"] for s in steps if s.get("ecran") == "ready" and "titre" in s}
    for n in free:
        assert f"Prêt : session libre — {FINAL[n]}" in titles, n
    assert f"Prêt : Grand Prix des objets — {FINAL['demo-circuit']}" in titles
    assert f"Prêt : {FINAL['velodrome-250']}" in titles
    captures = {s["capture"] for s in steps if "capture" in s}
    assert captures == {"parcours_liste"} | {f"pret_{n}" for n in FINAL}
