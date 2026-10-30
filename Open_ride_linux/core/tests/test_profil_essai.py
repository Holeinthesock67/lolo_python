"""Série MJ, lot MJ2 : profil d'essai `_essai` (séances simulées comptées, journal marqué, remise à zéro)."""

import json
import shutil

import pytest

from openride_core import config, launcher, profiles
from openride_core.__main__ import main
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.progression import SessionFacts, ineligible_reason, load_table, recompute
from openride_core.session import CoreSession

from test_progression import write_journal

FAST_RULES = "[rules]\nmin_session_s = 10\n"   # séance comptée dès 10 s (surcharge propre au profil)


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """`~/OpenRide` dans le dossier du test ; contexte historique avant et après."""
    monkeypatch.setattr(config, "OPENRIDE_HOME", tmp_path / "OpenRide")
    profiles.activate(None)
    yield tmp_path / "OpenRide"
    profiles.activate(None)


def trial(fast: bool = True) -> profiles.ProfileContext:
    ctx = profiles.ProfileContext.for_id(profiles.TRIAL_ID)
    if fast:
        ctx.root.mkdir(parents=True, exist_ok=True)
        (ctx.root / "progression.toml").write_text(FAST_RULES, encoding="utf-8")
    return ctx


# --- description du profil -------------------------------------------------------------------

def test_trial_and_player_defaults_are_data():
    ctx = profiles.ProfileContext.for_id("_essai")
    assert ctx.type == "essai" and ctx.is_trial and ctx.counted_sources == ("live", "simulated")
    assert ctx.name == "Profil d'essai" and ctx.fit_suffix() == "_essai"
    player = profiles.ProfileContext.for_id("cycliste-2")
    assert player.type == "joueur" and player.counted_sources == ("live",) and player.fit_suffix() == ""
    legacy = profiles.current()
    assert legacy.type == "joueur" and legacy.counted_sources == ("live",) and legacy.journal_header() is None


def test_description_written_once_and_read_back():
    ctx = profiles.ProfileContext.for_id("_essai")
    path = profiles.ensure_description(ctx)
    text = path.read_text(encoding="utf-8")
    assert 'type = "essai"' in text and 'seances_comptees = ["live", "simulated"]' in text
    path.write_text(text.replace('nom = "Profil d\'essai"', 'nom = "Essais du soir"'), encoding="utf-8")
    profiles.ensure_description(ctx)   # déjà là : rien n'est réécrit
    again = profiles.ProfileContext.for_id("_essai")
    assert again.name == "Essais du soir" and again.created and again.is_trial


@pytest.mark.parametrize("body, message", [
    ("[profil\n", "illisible"),
    ('[profil]\ntype = "admin"\n', "type"),
    ('[profil]\nseances_comptees = ["live", "bidon"]\n', "seances_comptees"),
    ('[profil]\nid = "autre"\n', "différent du dossier"),
])
def test_bad_description_is_refused(home, body, message):
    root = home / "Profils" / "cycliste-2"
    root.mkdir(parents=True)
    (root / "profil.toml").write_text(body, encoding="utf-8")
    with pytest.raises(profiles.ProfileContextError, match=message):
        profiles.ProfileContext.for_id("cycliste-2")


# --- séances comptées et journaux marqués ---------------------------------------------------

def test_counted_sources_decide_eligibility():
    table = load_table(None)
    facts = SessionFacts(journal="a", source="simulated", duration_s=600)
    assert ineligible_reason(facts, table) == "simulated"
    assert ineligible_reason(facts, table, ("live", "simulated")) is None
    assert ineligible_reason(SessionFacts(journal="b", source="replay", duration_s=600), table,
                             ("live", "simulated")) == "replay"


def mark(path, profile_id, source="live"):
    lines = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()]
    lines[0].update({"profile_id": profile_id, "source": source})
    path.write_text("".join(json.dumps(ln) + "\n" for ln in lines), encoding="utf-8")


def test_journal_of_another_profile_never_counts(tmp_path):
    table = load_table(None)
    jd = tmp_path / "j"
    jd.mkdir()
    write_journal(jd / "a.jsonl", km=30, climb_m=100, minutes=60, start_ts=1_000_000.0)    # non marqué
    write_journal(jd / "b.jsonl", km=30, climb_m=100, minutes=60, start_ts=2_000_000.0)
    mark(jd / "b.jsonl", "_essai", "simulated")
    player = profiles.ProfileContext.for_id("cycliste-2")
    res = recompute(jd, table, counted=player.counted_sources, owns=player.owns)
    assert [r.reason for r in res.sessions] == [None, "other_profile"]
    essai = profiles.ProfileContext.for_id("_essai")
    res = recompute(jd, table, counted=essai.counted_sources, owns=essai.owns)
    assert [r.reason for r in res.sessions] == ["other_profile", None]   # non marqué : pas à l'essai
    assert res.total_xp > 0


# --- séance sur le profil d'essai ------------------------------------------------------------

def ride_session(port, seconds=30):
    """Séance simulée hors boucle asyncio : le bilan `xp_result` part tout de suite."""
    frames = []
    cfg = Config()
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], routes_root=profiles.current().root / "routes")
    s.server.send_raw = frames.append
    s._on_command("select_route", {"route_id": "demo"}, 1)
    s._on_command("start", {}, 2)
    now = 1000.0
    for _ in range(int(seconds * 50)):
        now += 0.02
        s._step(0.02, now)
    s._on_command("end_session", {"save": True}, 3)
    return [f for f in frames if f.get("type") == "xp_result"]


def test_simulated_session_counts_only_on_trial_profile(home):
    ctx = trial()
    profiles.activate(ctx)
    result = ride_session(5962)
    assert result and result[-1]["eligible"] and result[-1]["total"] > 0 and result[-1]["coins_gained"] >= 0
    journal = sorted(ctx.journal_dir.glob("*.jsonl"))[-1]
    head = next(read_journal(journal))
    assert head["profile_id"] == "_essai" and head["profile_type"] == "essai" and head["source"] == "simulated"
    fits = list(ctx.activities_dir.glob("*.fit"))
    assert fits and all(f.stem.endswith("_essai") for f in fits)
    # Le même genre de séance sur un profil de joueur (même surcharge de règles) : refusée, comme avant.
    player = profiles.ProfileContext.for_id("cycliste-2")
    player.root.mkdir(parents=True)
    (player.root / "progression.toml").write_text(FAST_RULES, encoding="utf-8")
    profiles.activate(player)
    result = ride_session(5964)
    assert result and not result[-1]["eligible"] and result[-1]["reason"] == "simulated"


def test_trial_journal_copied_into_player_is_ignored(home, capsys):
    ctx = trial()
    profiles.activate(ctx)
    ride_session(5966)
    player = profiles.ProfileContext.for_id("cycliste-2")
    player.journal_dir.mkdir(parents=True)
    for j in ctx.journal_dir.glob("*.jsonl"):
        shutil.copy(j, player.journal_dir / j.name)
    profiles.activate(None)
    assert main(["xp", "--profil", "cycliste-2", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total_xp"] == 0 and {s["reason"] for s in out["sessions"]} == {"other_profile"}


def test_clear_trial_profile_keeps_description(home, capsys):
    ctx = trial()
    profiles.activate(ctx)
    ride_session(5968)
    profiles.ensure_description(ctx)
    assert main(["profil", "essai", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["total_xp"] > 0
    assert main(["profil", "essai", "--vider"]) == 0
    assert "Activities" in capsys.readouterr().out
    assert sorted(p.name for p in ctx.root.iterdir() if p.name != ".verrou") == ["profil.toml", "progression.toml"]
    assert main(["profil", "essai", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total_xp"] == 0 and out["profile"] == "_essai" and out["profile_type"] == "essai"


def test_player_profile_cannot_be_cleared():
    with pytest.raises(profiles.ProfileContextError, match="seul le profil d'essai"):
        profiles.clear(profiles.ProfileContext.for_id("cycliste-2"))


# --- session simulée du menu (lanceur) -------------------------------------------------------

def test_sim_session_runs_on_trial_profile():
    cmd = ["py", "-m", "openride_core", "run", "--profil", "cycliste-2", "--trainer", "ftms"]
    out = launcher.sim_core_cmd(cmd)
    assert out[-2:] == ["--profil", "_essai"] and out.count("--profil") == 1 and "cycliste-2" not in out
    assert launcher.with_profile(["py", "recover", "--profil=x"], "_essai") == ["py", "recover", "--profil", "_essai"]


def test_sim_mode_resume_looks_in_trial_journals(tmp_path):
    sup = launcher.Supervisor(core_cmd=["c"], engine_cmd=["e"], journal_dir=tmp_path / "joueur",
                              release_cmd=["x"], log_path=tmp_path / "log", sim_journal_dir=tmp_path / "essai", recover_cmd=["r"])
    seen = []
    import openride_core.resume as resume
    real = resume.find_unfinished_journal
    resume.find_unfinished_journal = lambda d, since: seen.append(d)
    try:
        sup._unfinished_journal()
        sup.sim_mode = True
        sup._unfinished_journal()
    finally:
        resume.find_unfinished_journal = real
    assert seen == [tmp_path / "joueur", tmp_path / "essai"]
