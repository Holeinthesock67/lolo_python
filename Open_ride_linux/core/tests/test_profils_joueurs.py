"""Profils de joueurs dans le core (série MJ, lot MJ7, contrat IPC révision 1.5) : liste, choix
sans relancer, création, renommage, corbeille, profil par défaut, relance du lanceur."""

from __future__ import annotations

from pathlib import Path

import pytest

from openride_core import config as config_mod
from openride_core import fit_export, profiles
from openride_core.input_providers import NullProvider
from openride_core.launcher import Supervisor
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession

from test_contract_ipc import assert_valid
from test_progression import write_journal


@pytest.fixture
def home(tmp_path, monkeypatch):
    """`~/OpenRide` temporaire avec deux profils de joueur, A (FTP 200) et B (FTP 300)."""
    home = tmp_path / "OpenRide"
    monkeypatch.setattr(config_mod, "OPENRIDE_HOME", home)
    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG_PATH", home / "config.toml")
    monkeypatch.setattr(profiles, "_active", None)
    home.mkdir()
    (home / "config.toml").write_text('[render]\nquality = "low"\n', encoding="utf-8")
    for pid, name, ftp in (("cycliste-a", "Cycliste A", 200), ("cycliste-b", "Cycliste B", 300)):
        root = home / "Profils" / pid
        root.mkdir(parents=True)
        (root / "profil.toml").write_text(
            f'[profil]\nid = "{pid}"\nnom = "{name}"\ntype = "joueur"\n\n[rider]\nftp_w = {ftp}\n', encoding="utf-8")
    write_journal(home / "Profils" / "cycliste-b" / "Activities" / ".journal" / "b.jsonl",
                  km=300, climb_m=3000, minutes=300, start_ts=1_760_000_000.0)
    yield home
    profiles.activate(None)


def base(home: Path) -> Path:
    return home / "Profils"


def make(home: Path, monkeypatch, port: int = 6110):
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", home / "act")
    ctx = profiles.ProfileContext.for_id("cycliste-a", base(home))
    profiles.activate(ctx)
    cfg = config_mod.load(home / "config.toml")
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], routes_root=home / "routes",
                    config_path=home / "config.toml")
    s.profiles_base = base(home)
    s.active_profile_path = home / profiles.ACTIVE_FILE
    s.profile_lock = profiles.ProfileLock(ctx)
    s.profile_lock.acquire()
    frames: list[dict] = []
    s.server.send_raw = frames.append
    return s, frames


def of(frames, kind):
    found = [f for f in frames if f["type"] == kind]
    for f in found:
        assert_valid(f)
    return found


# --- profiles.py -----------------------------------------------------------------------------

def test_name_rules_and_id_from_name(home):
    ctx = profiles.create("  Thérèse   Ça-va ", base(home))
    assert (ctx.id, ctx.name, ctx.type) == ("therese-ca-va", "Thérèse Ça-va", "joueur")
    assert profiles.create("Therese ca va", base(home)).id == "therese-ca-va-2"
    for bad in ("", "x" * 17, "a_b", "Zoé!", 12):
        with pytest.raises(profiles.ProfileNameError):
            profiles.create(bad, base(home))
    with pytest.raises(profiles.ProfileNameError, match="déjà pris"):
        profiles.create("cycliste a", base(home))


def test_eight_player_profiles_at_most(home):
    for n in range(6):
        profiles.create(f"Joueur {n}", base(home))
    with pytest.raises(profiles.ProfileContextError, match="8 profils"):
        profiles.create("Neuvième", base(home))


def test_rename_keeps_the_id(home):
    ctx = profiles.rename("cycliste-a", "Thomas", base(home))
    assert (ctx.id, ctx.name) == ("cycliste-a", "Thomas")
    with pytest.raises(profiles.ProfileNameError):
        profiles.rename("cycliste-b", "thomas", base(home))
    assert profiles.rename("cycliste-a", "THOMAS", base(home)).name == "THOMAS"   # le sien : permis


def test_delete_goes_to_trash_with_its_rules(home):
    b = base(home)
    profiles.ProfileContext.for_id("_essai", b).root.mkdir()
    with pytest.raises(profiles.ProfileContextError, match="essai"):
        profiles.delete("_essai", None, b)
    with pytest.raises(profiles.ProfileContextError, match="en cours"):
        profiles.delete("cycliste-a", "cycliste-a", b)
    with profiles.ProfileLock(profiles.ProfileContext.for_id("cycliste-b", b)):
        with pytest.raises(profiles.ProfileContextError, match="déjà utilisé"):
            profiles.delete("cycliste-b", "cycliste-a", b)
    dest = profiles.delete("cycliste-b", "cycliste-a", b)
    assert dest.parent == b / ".corbeille" and (dest / "profil.toml").is_file()
    assert [c.id for c in profiles.list_contexts(b)] == ["cycliste-a", "_essai"]
    with pytest.raises(profiles.ProfileContextError, match="dernier profil"):
        profiles.delete("cycliste-a", None, b)


def test_default_profile_after_migration(home):
    b = base(home)
    assert profiles.default_id(b) is None   # migration pas faite : contexte historique
    (b / profiles.MIGRATION_FILE).write_text("sauvegarde\nfini\n", encoding="utf-8")
    assert profiles.default_id(b) == "cycliste-a"   # deux profils, aucun dernier, pas de principal : le premier
    (b / "principal").mkdir()
    assert profiles.default_id(b) == "principal"
    (b / "principal").rmdir()
    (home / "config.toml").write_text('[profils]\ndernier = "cycliste-b"\n', encoding="utf-8")
    assert profiles.default_id(b) == "cycliste-b"
    profiles.delete("cycliste-b", None, b)
    assert profiles.default_id(b) == "cycliste-a"   # le seul profil joueur
    assert config_mod.from_dict({"profils": {"dernier": "x"}}).profils.dernier == "x"


# --- séance du core ------------------------------------------------------------------------------

def test_list_profiles_message(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    assert s.server.hello_config["profile"] == {"id": "cycliste-a", "name": "Cycliste A", "type": "joueur", "count": 2}
    s._on_command("list_profiles", {}, 7)
    (msg,) = of(frames, "profiles")
    assert msg["request_cmd_id"] == 7 and msg["active"] == "cycliste-a"
    assert [(i["id"], i["level"] > 1, i["last_ride"] is not None) for i in msg["items"]] == [
        ("cycliste-a", False, False), ("cycliste-b", True, True)]


def test_select_profile_reloads_without_touching_the_trainer(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    driver, old_lock = s.driver, s.profile_lock
    assert s.cfg.rider.ftp_w == 200
    s._on_command("select_profile", {"id": "cycliste-b"}, 9)
    assert s.driver is driver and not getattr(driver, "stopped", False)
    (ack,) = of(frames, "hello_ack")
    assert ack["config"]["profile"]["id"] == "cycliste-b" and ack["config"]["ftp_w"] == 300
    assert ack["config"]["progression"]["level"] > 1
    assert [f["type"] for f in frames] == ["hello_ack", "settings", "progression"]
    assert s.cfg.rider.ftp_w == 300 and s.journal_dir == base(home) / "cycliste-b" / "Activities" / ".journal"
    assert profiles.current().id == "cycliste-b" and s.profile_lock is not old_lock
    assert profiles.read_active(home / profiles.ACTIVE_FILE) == "cycliste-b"
    assert profiles.last_player(home / "config.toml") == "cycliste-b"
    with profiles.ProfileLock(profiles.ProfileContext.for_id("cycliste-a", base(home))):
        pass   # l'ancien profil est rendu


def test_profile_commands_are_refused_during_a_session(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    s._on_command("select_route", {}, 1)
    s._on_command("start", {}, 2)
    for name, args in (("select_profile", {"id": "cycliste-b"}), ("create_profile", {"name": "Zoé"}),
                       ("rename_profile", {"id": "cycliste-b", "name": "Zoé"}),
                       ("delete_profile", {"id": "cycliste-b"})):
        s._on_command(name, args, 3)
    assert [e["code"] for e in of(frames, "error")] == ["busy"] * 4
    s._on_command("list_profiles", {}, 4)   # accepté à tout moment
    assert of(frames, "profiles")


def test_create_rename_delete_from_the_menu(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    s._on_command("create_profile", {"name": "Zoé"}, 20)
    s._on_command("create_profile", {"name": "Zoé"}, 20)   # copie du même datagramme
    assert profiles.current().id == "zoe"
    assert [c.id for c in profiles.list_contexts(base(home))] == ["cycliste-a", "cycliste-b", "zoe"]
    assert of(frames, "profiles")[-1]["active"] == "zoe"
    s._on_command("create_profile", {"name": "zoé"}, 21)
    s._on_command("rename_profile", {"id": "zoe", "name": "Cycliste B"}, 22)
    s._on_command("delete_profile", {"id": "zoe"}, 23)
    s._on_command("delete_profile", {"id": "inconnu"}, 24)
    s._on_command("select_profile", {"id": "../x"}, 25)
    assert [e["code"] for e in of(frames, "error")] == ["name_invalid", "name_invalid", "profile_invalid",
                                                        "profile_invalid", "profile_invalid"]
    frames.clear()
    s._on_command("rename_profile", {"id": "zoe", "name": "Zoé B"}, 26)
    assert s.server.hello_config["profile"]["name"] == "Zoé B"
    s._on_command("delete_profile", {"id": "cycliste-a"}, 27)
    assert [i["id"] for i in of(frames, "profiles")[-1]["items"]] == ["cycliste-b", "zoe"]


def test_profile_used_elsewhere_is_refused(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    with profiles.ProfileLock(profiles.ProfileContext.for_id("cycliste-b", base(home))):
        s._on_command("select_profile", {"id": "cycliste-b"}, 5)
    assert [e["code"] for e in of(frames, "error")] == ["profile_invalid"]
    assert profiles.current().id == "cycliste-a" and s.cfg.rider.ftp_w == 200


# --- lanceur ------------------------------------------------------------------------------------

def test_launcher_restarts_the_core_on_the_profile_chosen_in_the_menu(home, tmp_path):
    active = home / profiles.ACTIVE_FILE
    sup = Supervisor(core_cmd=["core", "run", "--profil", "cycliste-a"], engine_cmd=["godot"],
                     release_cmd=["core", "release-trainer"], log_path=tmp_path / "log",
                     recover_cmd=["core", "recover", "--profil", "cycliste-a"], active_profile_path=active,
                     say=lambda m: None)
    sup._follow_active_profile()
    assert sup.core_cmd[-1] == "cycliste-a"   # pas de fichier : rien ne change
    active.write_text("_essai\n", encoding="utf-8")
    sup._follow_active_profile()
    assert sup.core_cmd[-1] == "cycliste-a"   # le profil d'essai n'est jamais repris
    active.write_text("cycliste-b\n", encoding="utf-8")
    sup._follow_active_profile()
    assert sup.core_cmd == ["core", "run", "--profil", "cycliste-b"]
    assert sup.recover_cmd == ["core", "recover", "--profil", "cycliste-b"]
    assert sup.journal_dir == base(home) / "cycliste-b" / "Activities" / ".journal"
