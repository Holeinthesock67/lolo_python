"""Remise à zéro des statistiques d'un profil de joueur (lot RZ1, contrat IPC révision 1.31) : sauvegarde
horodatée avant tout déplacement, fichiers gardés (réglages, FTP), annulation, commandes du menu
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
    (root / "elo.json").write_text('{"rating": 1620}', encoding="utf-8")
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
    assert set(moved) == {"Activities", "records.json", "elo.json", "profile.json", "collection_vue.json",
                          "ligue.json", ".cache"}
    assert sorted(p.name for p in ctx.root.iterdir()) == sorted(kept)   # réglages, FTP, choix, plan
    assert kept_texts(ctx) == kept and "ftp_w = 300" in kept["profil.toml"]
    for name in moved:   # rien n'est effacé : tout est dans la sauvegarde
        assert (dest / name).exists()
    assert (dest / "Activities" / ".journal" / "b.jsonl").is_file()
    assert sorted(p.name for p in (dest / profiles.RESET_KEPT_COPY).iterdir()) == sorted(kept)
    assert 'profil = "cycliste-b"' in (dest / profiles.RESET_MANIFEST).read_text(encoding="utf-8")
    assert profiles.reset_entries(ctx, base(home)) == [
        {"id": "cycliste-b_20261128-093000", "date": "2026-11-28", "time": "09:30"}]
    assert profiles.reset_entries(profiles.ProfileContext.for_id("cycliste-a", base(home)), base(home)) == []


def test_reset_is_refused_for_trial_empty_and_twice_in_a_second(home):
    trial = profiles.ProfileContext.for_id(profiles.TRIAL_ID, base(home))
    profiles.ensure_description(trial)
    with pytest.raises(profiles.ProfileContextError, match="essai"):
        profiles.reset_stats(trial, base(home))
    a = profiles.ProfileContext.for_id("cycliste-a", base(home))
    with pytest.raises(profiles.ProfileContextError, match="rien à remettre à zéro"):
        profiles.reset_stats(a, base(home))
    ctx = player_b(home)
    profiles.reset_stats(ctx, base(home), now=T1)
    (ctx.root / "records.json").write_text("{}", encoding="utf-8")
    with pytest.raises(profiles.ProfileContextError, match="seconde"):
        profiles.reset_stats(ctx, base(home), now=T1)


def test_undo_brings_stats_back_and_saves_rides_since(home):
    ctx = player_b(home)
    profiles.reset_stats(ctx, base(home), now=T1)
    write_journal(ctx.journal_dir / "apres.jsonl", km=20, climb_m=100, minutes=30, start_ts=1_764_000_000.0)
    (ctx.root / "profil.toml").write_text(
        '[profil]\nid = "cycliste-b"\nnom = "Cycliste B"\ntype = "joueur"\n\n[rider]\nftp_w = 310\n', encoding="utf-8")
    back, saved = profiles.undo_reset(ctx, "cycliste-b_20261128-093000", base(home), now=T2)
    assert "Activities" in back and "elo.json" in back
    assert (ctx.journal_dir / "b.jsonl").is_file() and not (ctx.journal_dir / "apres.jsonl").exists()
    assert "ftp_w = 310" in (ctx.root / "profil.toml").read_text(encoding="utf-8")   # réglage d'aujourd'hui gardé
    assert saved is not None and (saved / "Activities" / ".journal" / "apres.jsonl").is_file()
    assert [r["id"] for r in profiles.reset_entries(ctx, base(home))] == ["cycliste-b_20261128-180000"]
    # l'annulation s'annule à son tour : on retrouve la séance d'après la remise
    profiles.undo_reset(ctx, "cycliste-b_20261128-180000", base(home), now=datetime(2026, 11, 28, 18, 5, 0))
    assert (ctx.journal_dir / "apres.jsonl").is_file()


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
    s._on_command("reset_profile_stats", {"confirmed": True}, 4)   # plus rien à remettre à zéro
    assert of(frames, "error")[-1]["code"] == "profile_invalid"
    s._on_command("undo_profile_reset", {"id": msg["resets"][0]["id"], "confirmed": True}, 5)
    assert s.progress_svc.progression_dict()["level"] > 1
    assert of(frames, "profiles")[-1]["resets"] == []
    s._on_command("select_route", {}, 6)
    s._on_command("start", {}, 7)
    s._on_command("reset_profile_stats", {"confirmed": True}, 8)
    assert of(frames, "error")[-1]["code"] == "busy"


def test_reset_from_the_command_line(home, capsys):
    ctx = player_b(home)
    profiles.activate(ctx)
    assert cli.main(["profil", "remise-a-zero", "--profil", "cycliste-b"]) == 0
    out = capsys.readouterr().out
    assert "Sauvegarde" in out and "annuler-remise" in out and not ctx.journal_dir.exists()
    entry = profiles.reset_entries(ctx, base(home))[0]["id"]
    assert cli.main(["profil", "remises", "--profil", "cycliste-b", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["remises"][0]["id"] == entry
    assert cli.main(["profil", "annuler-remise", entry, "--profil", "cycliste-b"]) == 0
    assert (ctx.journal_dir / "b.jsonl").is_file()
    with profiles.ProfileLock(ctx):   # séance en cours de ce profil : refus
        assert cli.main(["profil", "remise-a-zero", "--profil", "cycliste-b"]) == 1
