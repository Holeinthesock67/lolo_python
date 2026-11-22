"""Copies automatiques du profil et restauration (lot SV1) : copie complète sans verrou ni caches, liens durs vers
la copie précédente pour les fichiers inchangés, rotation par raison, copie de la semaine, copie avant la remise à
zéro (RZ1), restauration depuis le menu (`list_profile_backups`, `restore_profile_backup`, message
`profile_backups`) et en ligne de commande, `scripts/update.sh` qui refuse la mise à jour si la copie échoue.

Tout se passe dans le `~/OpenRide` temporaire de la fixture `home` (jamais le vrai profil)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pytest

from openride_core import __main__ as cli
from openride_core import profile_backups as pb
from openride_core import profiles

from test_contract_ipc import assert_valid  # noqa: F401
from test_profil_remise_a_zero import player_b
from test_profils_joueurs import base, home, make, of  # noqa: F401  (fixture `home`)
from test_progression import write_journal

T1 = datetime(2026, 11, 8, 13, 5, 0)


def b(home):
    return profiles.ProfileContext.for_id("cycliste-b", base(home))


def test_copy_is_complete_without_lock_nor_caches(home):
    ctx = player_b(home)
    (ctx.root / profiles.LOCK_NAME).write_text("123", encoding="utf-8")
    dest = pb.create(ctx, "semaine", base(home), now=T1)
    assert dest == home / "Sauvegardes" / "profils" / "cycliste-b" / "20261108-130500_semaine"
    names = sorted(p.name for p in dest.iterdir())
    assert profiles.LOCK_NAME not in names and ".cache" not in names
    assert {"profil.toml", "records.json", "elo.json", "ligue.json", "Activities", pb.MANIFEST} <= set(names)
    assert (dest / "Activities" / ".journal" / "b.jsonl").read_bytes() == (ctx.journal_dir / "b.jsonl").read_bytes()
    man = (dest / pb.MANIFEST).read_text(encoding="utf-8")
    assert 'raison = "semaine"' in man and 'profil = "cycliste-b"' in man
    assert not list(dest.parent.glob("*.tmp"))
    [row] = pb.entries(ctx, base(home))
    assert row == {"id": "20261108-130500_semaine", "reason": "semaine", "date": "2026-11-08", "time": "13:05",
                   "sessions": 0}


def test_unchanged_files_are_hard_links_to_the_previous_copy_never_to_the_live_file(home):
    ctx = player_b(home)
    first = pb.create(ctx, "semaine", base(home), now=T1)
    write_journal(ctx.journal_dir / "nouvelle.jsonl", km=20, climb_m=100, minutes=30, start_ts=1_764_000_000.0)
    second = pb.create(ctx, "semaine", base(home), now=T1 + timedelta(days=7))
    old, new = first / "Activities" / ".journal" / "b.jsonl", second / "Activities" / ".journal" / "b.jsonl"
    assert os.path.samefile(old, new)   # inchangé : même fichier sur le disque
    assert not os.path.samefile(new, ctx.journal_dir / "b.jsonl")   # jamais le fichier vivant
    assert (second / "Activities" / ".journal" / "nouvelle.jsonl").is_file()
    assert not (first / "Activities" / ".journal" / "nouvelle.jsonl").exists()
    # un journal complété en place ne change aucune copie
    before = old.read_bytes()
    with (ctx.journal_dir / "b.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"t": 1}\n')
    assert old.read_bytes() == before and new.read_bytes() == before
    third = pb.create(ctx, "semaine", base(home), now=T1 + timedelta(days=14))
    assert not os.path.samefile(third / "Activities" / ".journal" / "b.jsonl", new)   # changé : nouvelle copie


def test_rotation_keeps_a_season_of_weekly_copies_per_reason(home):
    ctx = player_b(home)
    for week in range(10):
        pb.create(ctx, "semaine", base(home), now=T1 + timedelta(days=7 * week))
    for i in range(5):
        pb.create(ctx, "mise-a-jour", base(home), now=T1 + timedelta(days=70, minutes=i))
    rows = pb.entries(ctx, base(home))
    weekly = [r for r in rows if r["reason"] == "semaine"]
    assert len(weekly) == pb.REASONS["semaine"] == 8   # une saison de 8 semaines
    assert weekly[-1]["date"] == "2026-11-22"   # les deux plus anciennes sont effacées
    assert len([r for r in rows if r["reason"] == "mise-a-jour"]) == 3
    assert rows == sorted(rows, key=lambda r: r["id"][:15], reverse=True)
    for p in (home / "Sauvegardes" / "profils" / "cycliste-b").iterdir():   # copies restantes entières
        assert (p / "Activities" / ".journal" / "b.jsonl").is_file()


def test_weekly_copy_is_due_after_seven_days_only_for_player_profiles_with_data(home):
    ctx = player_b(home)
    assert pb.weekly_due(ctx, base(home), now=T1)
    assert pb.weekly_if_due(ctx, base(home), now=T1) is not None
    assert not pb.weekly_due(ctx, base(home), now=T1 + timedelta(days=6, hours=23))
    assert pb.weekly_due(ctx, base(home), now=T1 + timedelta(days=7))
    pb.create(ctx, "mise-a-jour", base(home), now=T1 + timedelta(days=7))   # une autre raison ne compte pas
    assert pb.weekly_due(ctx, base(home), now=T1 + timedelta(days=7))
    trial = profiles.ProfileContext.for_id(profiles.TRIAL_ID, base(home))
    profiles.ensure_description(trial)
    assert not pb.weekly_due(trial, base(home), now=T1)
    with pytest.raises(pb.BackupError, match="essai"):
        pb.create(trial, "semaine", base(home))
    fresh = profiles.create("Tout Neuf", base(home))
    assert not pb.weekly_due(fresh, base(home), now=T1)   # profil neuf : rien à protéger
    with pytest.raises(pb.BackupError, match="raison"):
        pb.create(ctx, "inconnue", base(home))


def test_failed_copy_leaves_nothing_behind(home, monkeypatch):
    ctx = player_b(home)

    def boom(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(pb.shutil, "copy2", boom)
    with pytest.raises(pb.BackupError, match="impossible"):
        pb.create(ctx, "semaine", base(home), now=T1)
    folder = pb.folder(ctx, base(home))
    assert not folder.exists() or list(folder.iterdir()) == []
    assert pb.weekly_if_due(ctx, base(home), now=T1) is None   # journalisé, jamais levé


def test_restore_brings_the_copy_back_and_saves_the_current_state(home):
    ctx = player_b(home)
    copy = pb.create(ctx, "semaine", base(home), now=T1)
    write_journal(ctx.journal_dir / "apres.jsonl", km=20, climb_m=100, minutes=30, start_ts=1_764_000_000.0)
    (ctx.root / "elo.json").write_text('{"rating": 900}', encoding="utf-8")
    (ctx.root / "profil.toml").write_text((ctx.root / "profil.toml").read_text(encoding="utf-8")
                                         .replace("ftp_w = 300", "ftp_w = 310"), encoding="utf-8")
    (ctx.root / profiles.LOCK_NAME).write_text("verrou", encoding="utf-8")
    saved = pb.restore(ctx, copy.name, base(home), now=T1 + timedelta(hours=1))
    assert (ctx.root / "elo.json").read_text(encoding="utf-8") == '{"rating": 1620}'
    assert "ftp_w = 300" in (ctx.root / "profil.toml").read_text(encoding="utf-8")   # réglages de la copie
    assert not (ctx.journal_dir / "apres.jsonl").exists()
    assert (ctx.root / profiles.LOCK_NAME).read_text(encoding="utf-8") == "verrou"   # verrou intact
    assert not (ctx.root / pb.MANIFEST).exists() and not list(ctx.root.glob("*.tmp"))
    assert not os.path.samefile(ctx.journal_dir / "b.jsonl", copy / "Activities" / ".journal" / "b.jsonl")
    assert saved.name.endswith("_restauration") and (saved / "Activities" / ".journal" / "apres.jsonl").is_file()
    # la restauration s'annule à son tour
    pb.restore(ctx, saved.name, base(home), now=T1 + timedelta(hours=2))
    assert (ctx.journal_dir / "apres.jsonl").is_file() and "ftp_w = 310" in (ctx.root / "profil.toml").read_text()


def test_restore_is_refused_for_unknown_copy_or_other_profile(home):
    ctx = player_b(home)
    copy = pb.create(ctx, "semaine", base(home), now=T1)
    a = profiles.ProfileContext.for_id("cycliste-a", base(home))
    for who, entry in ((a, copy.name), (ctx, "../cycliste-a"), (ctx, 12), (ctx, "20261107-130500_semaine")):
        with pytest.raises(pb.BackupError, match="introuvable"):
            pb.restore(who, entry, base(home))


def test_restore_failure_puts_the_profile_back(home, monkeypatch):
    ctx = player_b(home)
    copy = pb.create(ctx, "semaine", base(home), now=T1)
    (ctx.root / "elo.json").write_text('{"rating": 900}', encoding="utf-8")
    real = pb.shutil.copytree

    def boom(src, dst, **kw):
        if str(dst).startswith(str(ctx.root)):
            raise OSError(28, "No space left on device")
        return real(src, dst, **kw)

    monkeypatch.setattr(pb.shutil, "copytree", boom)
    with pytest.raises(pb.BackupError, match="tel quel"):
        pb.restore(ctx, copy.name, base(home), now=T1 + timedelta(hours=1))
    assert (ctx.root / "elo.json").read_text(encoding="utf-8") == '{"rating": 900}'
    assert (ctx.journal_dir / "b.jsonl").is_file() and not list(ctx.root.glob("*.tmp"))


def test_backups_and_restore_from_the_menu(home, monkeypatch):
    player_b(home)
    s, frames = make(home, monkeypatch)
    s._on_command("select_profile", {"id": "cycliste-b"}, 2)
    ctx = b(home)
    copy = pb.create(ctx, "semaine", base(home), now=T1)
    level = s.progress_svc.progression_dict()["level"]
    assert level > 1
    s._on_command("reset_profile_stats", {"confirmed": True}, 3)   # RZ1 : copie complète avant la remise à zéro
    rows = pb.entries(ctx, base(home))
    assert [r["reason"] for r in rows] == ["remise-a-zero", "semaine"]
    assert s.progress_svc.progression_dict()["level"] == 1
    frames.clear()
    s._on_command("list_profile_backups", {}, 4)
    msg = of(frames, "profile_backups")[-1]
    assert msg["profile"] == "cycliste-b" and [r["id"] for r in msg["items"]] == [r["id"] for r in rows]
    frames.clear()
    s._on_command("restore_profile_backup", {"id": copy.name}, 4)   # sans confirmation : refus
    assert of(frames, "error")[-1]["code"] == "bad_args" and not of(frames, "hello_ack")
    frames.clear()
    s._on_command("restore_profile_backup", {"id": copy.name, "confirmed": True}, 5)
    assert [f["type"] for f in frames][:1] == ["hello_ack"]   # profil rechargé
    assert s.progress_svc.progression_dict()["level"] == level
    assert of(frames, "profiles") and "restauration" in [r["reason"] for r in of(frames, "profile_backups")[-1]["items"]]
    s._on_command("restore_profile_backup", {"id": copy.name, "confirmed": True}, 5)   # copie de la même commande : rien de plus
    assert len([r for r in pb.entries(ctx, base(home)) if r["reason"] == "restauration"]) == 1
    s._on_command("restore_profile_backup", {"id": "nimporte", "confirmed": True}, 6)
    assert of(frames, "error")[-1]["code"] == "profile_invalid"
    s._on_command("select_route", {}, 7)
    s._on_command("start", {}, 8)
    s._on_command("list_profile_backups", {}, 9)   # lecture : aussi pendant une séance
    assert of(frames, "profile_backups")[-1]["request_cmd_id"] == 9
    s._on_command("restore_profile_backup", {"id": copy.name, "confirmed": True}, 10)
    assert of(frames, "error")[-1]["code"] == "busy"


def test_backups_from_the_command_line(home, capsys):
    ctx = player_b(home)
    profiles.activate(ctx)
    assert cli.main(["profil", "sauvegarde", "--tous", "--raison", "mise-a-jour"]) == 0
    out = capsys.readouterr().out
    assert "Cycliste A" in out and "Cycliste B" in out
    assert cli.main(["profil", "sauvegardes", "--profil", "cycliste-b", "--json"]) == 0
    [row] = json.loads(capsys.readouterr().out)["copies"]
    assert row["reason"] == "mise-a-jour"
    assert cli.main(["profil", "sauvegardes", "--profil", "cycliste-b"]) == 0
    assert "avant la mise à jour" in capsys.readouterr().out
    (ctx.root / "elo.json").write_text('{"rating": 900}', encoding="utf-8")
    assert cli.main(["profil", "restaurer", row["id"], "--profil", "cycliste-b"]) == 0
    assert "1620" in (ctx.root / "elo.json").read_text(encoding="utf-8")
    with profiles.ProfileLock(ctx):   # séance en cours de ce profil : refus
        assert cli.main(["profil", "restaurer", row["id"], "--profil", "cycliste-b"]) == 1


def test_weekly_copy_runs_in_the_background(home):
    ctx = player_b(home)
    t = pb.start_weekly(ctx, base(home))
    assert t is not None
    t.join(10)
    assert [r["reason"] for r in pb.entries(ctx, base(home))] == ["semaine"]
    assert pb.start_weekly(ctx, base(home)) is None   # faite : plus due avant 7 jours


# --- scripts/update.sh ------------------------------------------------------------------------------

from test_launch_no_terminal import BASH, GIT, _run_update, _update_repo  # noqa: E402


@pytest.mark.skipif(not (BASH and GIT), reason="bash ou git absent")
@pytest.mark.parametrize("core", ["absent", "echec", "ok"])
def test_update_refuses_when_profiles_cannot_be_copied(tmp_path, core):
    """Profils présents : la mise à jour copie d'abord ; sans programme ou copie en échec, refus et rien changé."""
    work, proj, env = _update_repo(tmp_path)
    (tmp_path / "home" / "OpenRide" / "Profils" / "principal").mkdir(parents=True)
    calls = tmp_path / "appels.txt"
    if core != "absent":
        bin_dir = proj / "core" / ".venv" / "bin"
        bin_dir.mkdir(parents=True)
        fake = bin_dir / "openride-core"
        fake.write_text(f'#!/bin/sh\necho "$@" >> "{calls}"\n' + ("exit 1\n" if core == "echec" else "exit 0\n"),
                        encoding="utf-8")
        fake.chmod(0o755)
    r = _run_update(proj, env)
    readme = (proj / "README.md").read_text(encoding="utf-8")
    if core == "ok":
        assert r.returncode == 0 and readme == "v2\n", r.stdout + r.stderr
        assert calls.read_text(encoding="utf-8").split() == ["profil", "sauvegarde", "--tous", "--raison",
                                                              "mise-a-jour"]
        r = _run_update(proj, env)   # déjà à jour : pas de nouvelle copie
        assert "déjà à jour" in r.stdout and len(calls.read_text(encoding="utf-8").splitlines()) == 1
    else:
        assert r.returncode == 1 and readme == "v1\n"
        assert "Rien n'a été changé" in r.stdout and "copie de tes profils" in r.stdout
        assert ("install.sh" if core == "absent" else "Libère de la place") in r.stdout
