"""Remise à zéro des statistiques d'un profil de joueur (lot RZ1, contrat IPC révision 1.31) : sauvegarde
horodatée avant tout déplacement, fichiers gardés (réglages, FTP, séances du coach), date de départ des
statistiques, cote du cycliste gardée et bots remis à zéro, annulation, commandes du menu
`reset_profile_stats` et `undo_profile_reset`, champ `resets` du message `profiles`, outil en ligne de commande.

Tout se passe dans le `~/OpenRide` temporaire de la fixture `home` (jamais le vrai profil)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from openride_core import __main__ as cli
from openride_core import profiles

from test_contract_ipc import assert_valid  # noqa: F401
from test_profils_joueurs import base, home, make, of  # noqa: F401  (fixture `home`)
from test_progression import write_journal

T1 = datetime(2026, 11, 28, 9, 30, 0)
T2 = datetime(2026, 11, 28, 18, 0, 0)


def player_b(home):
    """Profil B de la fixture (une séance) complété de toutes les familles de statistiques."""
    ctx = profiles.ProfileContext.for_id("cycliste-b", base(home))
    root = ctx.root
    (root / "records.json").write_text('{"demo": {}}', encoding="utf-8")
    (root / "elo.json").write_text('{"version": 1, "rating": 1620, "races": 14, "offsets": {"climber#1": 40}, '
                                   '"history": [{"mode": "race"}]}', encoding="utf-8")
    (root / "conseil.json").write_text("{}", encoding="utf-8")
    (root / "profile.json").write_text('{"owned": ["roue-carbone"]}', encoding="utf-8")
    (root / "collection_vue.json").write_text("[]", encoding="utf-8")
    (root / "ligue.json").write_text("{}", encoding="utf-8")
    (root / ".cache").mkdir()
    (root / ".cache" / "mmp.json").write_text("{}", encoding="utf-8")
    (root / "derniers_choix.json").write_text('{"route": "demo"}', encoding="utf-8")
    (root / "plan_state.toml").write_text('plan = "base"\n', encoding="utf-8")
    (root / "progression.toml").write_text("", encoding="utf-8")
    return ctx


def kept_texts(ctx):
    return {n: (ctx.root / n).read_text(encoding="utf-8") for n in profiles.KEPT_ON_RESET
            if n != profiles.LOCK_NAME and (ctx.root / n).is_file()}


def test_reset_moves_stats_to_a_timestamped_backup_and_keeps_settings(home):
    ctx = player_b(home)
    kept = kept_texts(ctx)
    dest, moved = profiles.reset_stats(ctx, base(home), now=T1)
    assert dest == base(home) / profiles.RESETS_DIRNAME / "cycliste-b_20261128-093000"
    assert set(moved) == {"records.json", "elo.json", "profile.json", "collection_vue.json", "ligue.json"}
    for name in moved:   # rien n'est effacé : tout est dans la sauvegarde
        assert (dest / name).exists()
    assert kept_texts(ctx).items() >= kept.items() and "ftp_w = 300" in kept["profil.toml"]
    assert (ctx.journal_dir / "b.jsonl").is_file() and (ctx.root / ".cache" / "mmp.json").is_file()   # coach, FIT
    assert sorted(p.name for p in (dest / profiles.RESET_KEPT_COPY).iterdir()) == sorted(kept)
    assert 'profil = "cycliste-b"' in (dest / profiles.RESET_MANIFEST).read_text(encoding="utf-8")
    again = profiles.ProfileContext.for_id("cycliste-b", base(home))
    assert again.stats_since == T1.timestamp()
    elo = json.loads((ctx.root / "elo.json").read_text(encoding="utf-8"))   # cote du cycliste gardée, bots à zéro
    assert (elo["rating"], elo["races"], elo["offsets"], elo["history"]) == (1620, 14, {}, [])
    assert profiles.reset_entries(ctx, base(home)) == [
        {"id": "cycliste-b_20261128-093000", "date": "2026-11-28", "time": "09:30"}]
    assert profiles.reset_entries(profiles.ProfileContext.for_id("cycliste-a", base(home)), base(home)) == []


def test_rides_before_the_reset_no_longer_count(home):
    from openride_core.progression import load_table, recompute

    ctx = player_b(home)
    table = load_table(ctx.table_path)
    before = recompute(ctx.journal_dir, table, counted=ctx.counted_sources, owns=ctx.owns, since=ctx.stats_since)
    assert before.total_xp > 0
    profiles.reset_stats(ctx, base(home), now=T1)
    ctx = profiles.ProfileContext.for_id("cycliste-b", base(home))
    after = recompute(ctx.journal_dir, table, counted=ctx.counted_sources, owns=ctx.owns, since=ctx.stats_since)
    assert after.total_xp == 0 and after.level.level == 1 and after.challenges == []
    assert {r.reason for r in after.sessions} == {"before_reset"}
    write_journal(ctx.journal_dir / "apres.jsonl", km=20, climb_m=100, minutes=30, start_ts=T2.timestamp())
    after = recompute(ctx.journal_dir, table, counted=ctx.counted_sources, owns=ctx.owns, since=ctx.stats_since)
    assert 0 < after.total_xp < before.total_xp   # la séance d'après compte, seule


def test_reset_is_refused_for_trial_and_two_in_a_second_both_kept(home):
    trial = profiles.ProfileContext.for_id(profiles.TRIAL_ID, base(home))
    profiles.ensure_description(trial)
    with pytest.raises(profiles.ProfileContextError, match="essai"):
        profiles.reset_stats(trial, base(home))
    ctx = player_b(home)
    profiles.reset_stats(ctx, base(home), now=T1)
    dest, _ = profiles.reset_stats(ctx, base(home), now=T1)
    assert dest.name == "cycliste-b_20261128-093001"


def test_undo_brings_stats_back_and_saves_what_came_after(home):
    ctx = player_b(home)
    profiles.reset_stats(ctx, base(home), now=T1)
    write_journal(ctx.journal_dir / "apres.jsonl", km=20, climb_m=100, minutes=30, start_ts=T2.timestamp())
    (ctx.root / "records.json").write_text('{"apres": {}}', encoding="utf-8")
    (ctx.root / "profil.toml").write_text(
        '[profil]\nid = "cycliste-b"\nnom = "Cycliste B"\ntype = "joueur"\n\n[rider]\nftp_w = 310\n', encoding="utf-8")
    back, saved = profiles.undo_reset(ctx, "cycliste-b_20261128-093000", base(home), now=T2)
    assert set(back) == {"records.json", "elo.json", "profile.json", "collection_vue.json", "ligue.json"}
    assert json.loads((ctx.root / "elo.json").read_text(encoding="utf-8"))["offsets"] == {"climber#1": 40}
    assert (ctx.journal_dir / "b.jsonl").is_file() and (ctx.journal_dir / "apres.jsonl").is_file()   # séances jamais déplacées
    assert "ftp_w = 310" in (ctx.root / "profil.toml").read_text(encoding="utf-8")   # réglage d'aujourd'hui gardé
    assert profiles.ProfileContext.for_id("cycliste-b", base(home)).stats_since is None   # tout recompte
    assert saved is not None and json.loads((saved / "records.json").read_text(encoding="utf-8")) == {"apres": {}}
    assert profiles.reset_entries(ctx, base(home)) == []   # au menu : plus de remise à annuler
    assert [r["id"] for r in profiles.reset_entries(ctx, base(home), all_kinds=True)] == ["cycliste-b_20261128-180000"]
    # l'annulation s'annule à son tour : on retrouve la période d'après la remise et sa date de départ
    profiles.undo_reset(ctx, "cycliste-b_20261128-180000", base(home), now=datetime(2026, 11, 28, 18, 5, 0))
    assert json.loads((ctx.root / "records.json").read_text(encoding="utf-8")) == {"apres": {}}
    assert profiles.ProfileContext.for_id("cycliste-b", base(home)).stats_since == T1.timestamp()


def test_undo_is_refused_for_unknown_or_other_profile(home):
    ctx = player_b(home)
    profiles.reset_stats(ctx, base(home), now=T1)
    a = profiles.ProfileContext.for_id("cycliste-a", base(home))
    for who, entry in ((a, "cycliste-b_20261128-093000"), (ctx, "../x_20261128-093000"), (ctx, 12),
                       (ctx, "cycliste-b_20261127-093000")):
        with pytest.raises(profiles.ProfileContextError, match="introuvable"):
            profiles.undo_reset(who, entry, base(home))


def test_reset_and_undo_from_the_menu(home, monkeypatch):
    player_b(home)
    s, frames = make(home, monkeypatch)
    s._on_command("select_profile", {"id": "cycliste-b"}, 2)
    assert s.progress_svc.progression_dict()["level"] > 1
    frames.clear()
    s._on_command("reset_profile_stats", {}, 2)   # sans confirmation : refus, rien ne bouge
    assert of(frames, "error")[-1]["code"] == "bad_args" and (base(home) / "cycliste-b" / "elo.json").is_file()
    frames.clear()
    s._on_command("reset_profile_stats", {"confirmed": True}, 3)
    assert [f["type"] for f in frames][:1] == ["hello_ack"]   # profil rechargé
    assert s.progress_svc.progression_dict()["level"] == 1 and s.progress_svc.progression_dict()["xp"] == 0
    msg = of(frames, "profiles")[-1]
    assert msg["active"] == "cycliste-b" and len(msg["resets"]) == 1
    assert len(json.dumps(msg).encode()) < 1600
    s._on_command("reset_profile_stats", {"confirmed": True}, 3)   # copie de la même commande : pas de seconde remise
    assert of(frames, "error") == [] and len(of(frames, "profiles")[-1]["resets"]) == 1
    s._on_command("undo_profile_reset", {"id": msg["resets"][0]["id"], "confirmed": True}, 5)
    assert s.progress_svc.progression_dict()["level"] > 1
    assert of(frames, "profiles")[-1]["resets"] == []
    assert s.profile_ctx.stats_since is None
    s._on_command("select_route", {}, 6)
    s._on_command("start", {}, 7)
    s._on_command("reset_profile_stats", {"confirmed": True}, 8)
    assert of(frames, "error")[-1]["code"] == "busy"


def test_reset_from_the_command_line(home, capsys):
    ctx = player_b(home)
    profiles.activate(ctx)
    assert cli.main(["profil", "remise-a-zero", "--profil", "cycliste-b"]) == 0
    out = capsys.readouterr().out
    assert "Sauvegarde" in out and "annuler-remise" in out and not (ctx.root / "records.json").exists()
    entry = profiles.reset_entries(ctx, base(home))[0]["id"]
    assert cli.main(["profil", "remises", "--profil", "cycliste-b", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["remises"][0]["id"] == entry
    assert cli.main(["profil", "annuler-remise", entry, "--profil", "cycliste-b"]) == 0
    assert (ctx.root / "records.json").is_file()
    with profiles.ProfileLock(ctx):   # séance en cours de ce profil : refus
        assert cli.main(["profil", "remise-a-zero", "--profil", "cycliste-b"]) == 1
