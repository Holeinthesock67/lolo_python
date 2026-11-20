"""Parcours propres à un mode (lot GP13, contrat IPC révision 1.19) : table publiée dans `hello_ack.config`,
dernier parcours de chaque mode gardé à part du dernier parcours libre, séance conseillée sur les parcours libres,
Circuit des Prés étiqueté « grandprix » et démonstration d'avant le lot remplacée par les contenus de départ."""

from __future__ import annotations

import json

import pytest

from openride_core import last_choices, mode_routes, profiles
from openride_core.velodrome import write_velodrome

from test_contract_ipc import assert_valid
from test_profils_joueurs import base, home, make, of  # noqa: F401  (fixture `home`)


def test_table_and_mode_of():
    assert mode_routes.MODE_ROUTE_TAGS == {"track": "velodrome", "grandprix": "grandprix"}
    assert mode_routes.mode_of({"library": {"tags": ["velodrome"]}}, "loop") == "track"
    assert mode_routes.mode_of({"tags": ["demo", "grandprix"]}, "loop") == "grandprix"
    assert mode_routes.mode_of({"library": {"tags": ["demo"]}}, "loop") is None
    assert mode_routes.mode_of({"library": None}, "loop") is None and mode_routes.mode_of(None, "loop") is None
    assert mode_routes.mode_of({"library": {"tags": "grandprix"}}, "loop") is None   # mal formé : parcours libre
    # lot GPL1 : un parcours de mode est une boucle ; une trace en ligne étiquetée reste un parcours libre
    for kind in ("open", "out_and_back", None):
        assert mode_routes.mode_of({"tags": ["grandprix"]}, kind) is None
        assert mode_routes.mode_of({"tags": ["velodrome"]}, kind) is None
    block = mode_routes.hello_block()
    block["x"] = "y"
    assert "x" not in mode_routes.MODE_ROUTE_TAGS   # copie


def test_file_keeps_one_route_per_mode(tmp_path):
    path = last_choices.path_for(tmp_path)
    last_choices.remember(path, "route_id", "alpe")
    last_choices.remember_mode_route(path, "grandprix", "demo-circuit")
    out = last_choices.remember_mode_route(path, "track", "velodrome-250")
    assert out == {"route_id": "alpe", "mode_routes": {"grandprix": "demo-circuit", "track": "velodrome-250"}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data["mode_routes"]["inconnu"] = "x"     # fichier modifié à la main : mode inconnu oublié
    data["mode_routes"]["track"] = "ow:balade"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert last_choices.load(path) == {"route_id": "alpe", "mode_routes": {"grandprix": "demo-circuit"}}


def test_mode_route_is_kept_apart_from_the_free_route(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    assert s.server.hello_config["mode_routes"] == {"track": "velodrome", "grandprix": "grandprix"}
    write_velodrome(s.routes_root)
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("select_route", {"route_id": "velodrome-250"}, 2)
    assert s.state.session_state == "READY" and s.state.route_id == "velodrome-250"
    expected = {"route_id": "demo", "mode_routes": {"track": "velodrome-250"}}
    assert s.server.hello_config["last_choices"] == expected
    root_a = profiles.ProfileContext.for_id("cycliste-a", base(home)).root
    assert last_choices.load(last_choices.path_for(root_a)) == expected
    s._on_command("select_profile", {"id": "cycliste-b"}, 3)
    s._on_command("select_profile", {"id": "cycliste-a"}, 4)
    assert s.state.route_id == "demo"   # le core recharge le dernier parcours libre, pas la piste
    (ack,) = of(frames, "hello_ack")[-1:]
    assert ack["config"]["mode_routes"] == {"track": "velodrome", "grandprix": "grandprix"}
    assert ack["config"]["last_choices"]["mode_routes"] == {"track": "velodrome-250"}
    assert_valid(ack)


def test_coach_game_skips_mode_routes(tmp_path):
    from openride_core.coach_game import load_candidates
    from openride_core.demo_world import write_demo_world

    write_demo_world(tmp_path)
    write_velodrome(tmp_path)
    ids = [c.id for c in load_candidates(routes_root=tmp_path, gpx_dir=tmp_path / "gpx")]
    assert "demo" in ids and "velodrome-250" not in ids


def test_circuit_is_a_grand_prix_route_and_old_demo_is_replaced(tmp_path):
    pytest.importorskip("openride_compiler")
    from openride_compiler import demo_biomes

    from openride_core.demo_world import biome_demo_outdated

    tagged = {n: lib["tags"] for n, lib in demo_biomes.DEMO_LIBRARY.items() if "tags" in lib}
    assert tagged == {n: ["grandprix"] for n in ("demo-circuit", "demo-corniche", "demo-vignes")}   # lots GP13, GP13b
    demo_biomes.generate(tmp_path, "demo-circuit", (demo_biomes.CIRCUIT_BIOME,), loop="circuit",
                         title="Circuit des Prés")
    world = tmp_path / "demo-circuit.world"
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["library"]["tags"] == ["grandprix"] and mode_routes.mode_of(manifest, "loop") == "grandprix"
    assert not biome_demo_outdated(world)
    # circuit écrit entre les lots GP13 et NT1 (étiquette sans description) : remplacé
    manifest["library"] = {"tags": ["grandprix"]}
    (world / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert biome_demo_outdated(world)
    del manifest["library"]   # circuit écrit avant le lot GP13 : remplacé par les contenus de départ
    (world / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert biome_demo_outdated(world)
    manifest["compiler"]["name"] = "openride-compiler"   # parcours du joueur du même nom : jamais remplacé
    (world / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert not biome_demo_outdated(world)
