"""Derniers choix du menu mémorisés par profil (lot O32, contrat IPC révision 1.5) : fichier du profil,
choix acceptés seulement, `hello_ack.config.last_choices`, dernier parcours rechargé par le core."""

from __future__ import annotations

import json

from openride_core import last_choices, profiles

from test_contract_ipc import assert_valid
from test_profils_joueurs import base, home, make, of  # noqa: F401  (fixture `home`)

ZWO = '<workout_file><name>Plat</name><workout><SteadyState Duration="600" Power="0.8"/></workout></workout_file>'


def test_file_round_trip_and_refused_values(tmp_path):
    path = last_choices.path_for(tmp_path)
    assert last_choices.load(path) == {}
    last_choices.remember(path, "route_id", "col_du_test")
    last_choices.remember(path, "bots", [{"kind": "ghost"}])
    assert last_choices.remember(path, "route_id", "ow:balade") == {"route_id": "col_du_test", "bots": [{"kind": "ghost"}]}
    assert last_choices.remember(path, "open_world", {"lat": 95, "lon": 0}).get("open_world") is None
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(workout_id=12, bots="x", inconnu=1)   # fichier modifié à la main : valeurs refusées oubliées
    path.write_text(json.dumps(data), encoding="utf-8")
    assert last_choices.load(path) == {"route_id": "col_du_test"}
    path.write_text("{pas du json", encoding="utf-8")
    assert last_choices.load(path) == {}


def test_menu_choices_are_kept_per_profile(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    s.workouts_dir = home / "Workouts"
    s.workouts_dir.mkdir()
    (s.workouts_dir / "plat.zwo").write_text(ZWO, encoding="utf-8")
    assert s.server.hello_config["last_choices"] == {}
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("select_workout", {"workout_id": "plat"}, 2)
    s._on_command("select_workout", {"workout_id": "absent"}, 3)   # refusé : pas noté
    s._on_command("select_workout", {"workout_id": None}, 4)       # retour au SIM : l'entraînement reste noté
    s._on_command("start", {"bots": [{"kind": "constant", "power_w": 200}]}, 5)
    expected = {"route_id": "demo", "workout_id": "plat", "bots": [{"kind": "constant", "power_w": 200}]}
    assert s.server.hello_config["last_choices"] == expected
    root_a = profiles.ProfileContext.for_id("cycliste-a", base(home)).root
    assert last_choices.load(last_choices.path_for(root_a)) == expected
    s._on_command("end_session", {"save": False}, 6)
    s._on_command("select_profile", {"id": "cycliste-b"}, 7)
    (ack,) = of(frames, "hello_ack")[-1:]
    assert ack["config"]["last_choices"] == {}   # profil B : rien de choisi
    assert_valid(ack)


def test_command_line_choices_are_not_kept(home, monkeypatch):
    s, _ = make(home, monkeypatch)
    s._on_command("select_route", {"route_id": "demo"}, 0)   # --autostart, --route : cmd_id 0
    s._on_command("start", {}, 0)
    assert s.server.hello_config["last_choices"] == {}


def test_start_without_bots_forgets_the_bots(home, monkeypatch):
    s, _ = make(home, monkeypatch)
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {"bots": [{"kind": "ghost"}]}, 2)
    s._on_command("end_session", {"save": False}, 3)
    s._on_command("select_route", {"route_id": "demo"}, 4)
    s._on_command("start", {}, 5)   # « Bot : aucun », fantôme non : l'engine n'envoie pas `bots`
    assert s.server.hello_config["last_choices"]["bots"] == []


def test_last_route_is_reloaded_at_start_and_on_profile_change(home, monkeypatch):
    root_b = profiles.ProfileContext.for_id("cycliste-b", base(home)).root
    last_choices.remember(last_choices.path_for(root_b), "route_id", "demo")
    root_a = profiles.ProfileContext.for_id("cycliste-a", base(home)).root
    last_choices.remember(last_choices.path_for(root_a), "route_id", "parcours_efface")
    s, _ = make(home, monkeypatch)
    s._preselect_last_route()
    assert s.state.session_state == "IDLE" and s.state.route_id is None   # parcours effacé : rien
    s._on_command("select_profile", {"id": "cycliste-b"}, 1)
    assert s.state.session_state == "READY" and s.state.route_id == "demo"
