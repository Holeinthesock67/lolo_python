"""Série MJ, lot MJ1 : contexte de profil (dossiers du joueur en cours), `--profil`, verrou."""

import asyncio
import subprocess
import sys

import pytest

from openride_core import config, fit_export, journal, plans, profile, profiles, progression, records
from openride_core.__main__ import build_parser, main
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.launcher import build_supervisor
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.tools import estimate_cp, history


@pytest.fixture(autouse=True)
def no_active_profile():
    """Chaque test part du contexte historique et y revient."""
    profiles.activate(None)
    yield
    profiles.activate(None)


def test_legacy_context_is_todays_paths():
    ctx = profiles.current()
    assert ctx.id is None and ctx.root == config.OPENRIDE_HOME
    assert ctx.profile_path == profile.PROFILE_PATH
    assert ctx.records_path == records.RECORDS_FILE
    assert ctx.plan_state_path == plans.STATE_PATH
    assert ctx.activities_dir == fit_export.ACTIVITIES_DIR
    assert ctx.journal_dir == journal.JOURNAL_DIR
    assert ctx.history_cache == history.CACHE_PATH and ctx.mmp_cache == estimate_cp.CACHE_PATH
    assert ctx.table_path == progression.USER_TABLE_PATH


def test_legacy_context_follows_redirected_constants(tmp_path, monkeypatch):
    """Les constantes sont lues à l'appel : un test qui les redirige est suivi."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "p.json")
    assert profiles.current().activities_dir == tmp_path / "act"
    assert profiles.current().profile_path == tmp_path / "p.json"
    assert fit_export.default_fit_path(0.0, "demo").parent == tmp_path / "act"


def test_named_profile_paths(tmp_path):
    ctx = profiles.ProfileContext.for_id("cycliste-2", tmp_path)
    root = tmp_path / "cycliste-2"
    assert ctx.root == root and ctx.lock_path == root / ".verrou"
    assert ctx.profile_path == root / "profile.json" and ctx.records_path == root / "records.json"
    assert ctx.plan_state_path == root / "plan_state.toml"
    assert ctx.activities_dir == root / "Activities" and ctx.journal_dir == root / "Activities" / ".journal"
    assert ctx.history_cache.parent == root / ".cache" and ctx.mmp_cache.parent == root / ".cache"
    assert ctx.table_path == progression.USER_TABLE_PATH   # pas de surcharge propre au profil
    (root / "progression.toml").parent.mkdir(parents=True)
    (root / "progression.toml").write_text("", encoding="utf-8")
    assert ctx.table_path == root / "progression.toml"


def test_default_base_is_profils_under_openride_home():
    assert profiles.ProfileContext.for_id("a").root == config.OPENRIDE_HOME / "Profils" / "a"


@pytest.mark.parametrize("bad", ["", "../x", "Cycliste", "a b", "-a", "a/b", "x" * 33, "_autre"])
def test_refused_ids(bad):
    with pytest.raises(profiles.ProfileContextError):
        profiles.check_id(bad)


def test_resolve_option_then_env():
    assert profiles.resolve(None, {}) is None
    assert profiles.resolve(None, {profiles.ENV_VAR: "b"}).id == "b"
    assert profiles.resolve("a", {profiles.ENV_VAR: "b"}).id == "a"


def test_every_path_default_follows_active_profile(tmp_path):
    ctx = profiles.ProfileContext.for_id("cycliste-2", tmp_path)
    profiles.activate(ctx)
    assert profiles.current() is ctx
    assert fit_export.default_fit_path(0.0, "demo").parent == ctx.activities_dir
    assert journal.latest_journal() is None
    profile.save_profile(profile.Profile())
    assert ctx.profile_path.is_file()
    records.RecordBook().save()
    assert ctx.records_path.is_file()
    plans.stop_plan()
    assert plans.load_state() is None


def test_lock_refuses_second_session(tmp_path):
    ctx = profiles.ProfileContext.for_id("cycliste-2", tmp_path)
    with profiles.ProfileLock(ctx):
        with pytest.raises(profiles.ProfileContextError, match="déjà utilisé"):
            profiles.ProfileLock(ctx).acquire()
    with profiles.ProfileLock(ctx):   # rendu à la sortie
        pass


def test_lock_released_when_process_dies(tmp_path):
    ctx = profiles.ProfileContext.for_id("x", tmp_path)
    code = ("import sys; from pathlib import Path; from openride_core import profiles; "
            f"profiles.ProfileLock(profiles.ProfileContext.for_id('x', Path({str(tmp_path)!r}))).acquire(); "
            "sys.exit(0)")
    subprocess.run([sys.executable, "-c", code], check=True)
    with profiles.ProfileLock(ctx):
        pass


def test_session_writes_only_in_its_profile(tmp_path):
    """Séance simulée sur un profil nommé : journal, FIT, records et profil V4 dans son dossier."""
    ctx = profiles.ProfileContext.for_id("cycliste-2", tmp_path / "Profils")
    profiles.activate(ctx)

    async def scenario():
        cfg = Config()
        cfg.ipc.port_state, cfg.ipc.port_commands = 5960, 5961
        s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], routes_root=tmp_path / "routes")
        assert s.journal_dir == ctx.journal_dir and s.records_path == ctx.records_path
        assert s.progress_svc.profile_path == ctx.profile_path
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        now = 1000.0
        for _ in range(500):
            now += 0.02
            s._step(0.02, now)
        s._on_command("end_session", {"save": True}, 3)
    asyncio.run(scenario())
    assert list(ctx.journal_dir.glob("*.jsonl"))
    assert list(ctx.activities_dir.glob("*.fit"))
    assert not fit_export.ACTIVITIES_DIR.exists() or not list(fit_export.ACTIVITIES_DIR.glob("*.fit"))


def test_profil_option_on_every_subcommand():
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    for name, cmd in sub.choices.items():
        assert any("--profil" in a.option_strings for a in cmd._actions), name


def test_cli_refuses_bad_profile_id(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["xp", "--profil", "../x"])
    assert exc.value.code == 2 and "identifiant de profil refusé" in capsys.readouterr().err


def test_xp_reads_the_profile_journals(tmp_path, monkeypatch, capsys):
    from test_progression import write_journal

    monkeypatch.setattr(config, "OPENRIDE_HOME", tmp_path)
    ctx = profiles.ProfileContext.for_id("cycliste-2")
    ctx.journal_dir.mkdir(parents=True)
    write_journal(ctx.journal_dir / "a.jsonl", km=30, climb_m=300, minutes=60, start_ts=1_000_000.0)
    assert main(["xp", "--profil", "cycliste-2", "--json"]) == 0
    import json
    out = json.loads(capsys.readouterr().out)
    assert out["directory"] == str(ctx.journal_dir) and out["total_xp"] > 0


def test_launcher_passes_profile_to_recover_and_resume(tmp_path, monkeypatch):
    godot = tmp_path / "godot"
    godot.write_text("#!/bin/sh\n", encoding="utf-8")
    godot.chmod(0o755)
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "project.godot").write_text("", encoding="utf-8")
    env = {"GODOT": str(godot), "OPENRIDE_ENGINE": str(engine)}
    monkeypatch.setattr(config, "OPENRIDE_HOME", tmp_path / "OpenRide")
    sup = build_supervisor(["--trainer", "mock", "--profil", "cycliste-2"], env)
    assert sup.journal_dir == tmp_path / "OpenRide" / "Profils" / "cycliste-2" / "Activities" / ".journal"
    assert sup.recover_cmd[-2:] == ["--profil", "cycliste-2"]
    assert sup.core_cmd[-2:] == ["--profil", "cycliste-2"]
    sup = build_supervisor(["--trainer", "mock"], env)
    assert sup.journal_dir == journal.JOURNAL_DIR and "--profil" not in sup.recover_cmd
    with pytest.raises(ValueError):
        build_supervisor(["--profil", "A B"], env)
