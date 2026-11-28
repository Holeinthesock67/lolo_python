"""Revue de code S5-01 et S5-05 : profils abîmés protégés, jamais effacés ni remplacés en silence.

S5-01 : la copie de `profile.json` est remise en place (plus seulement lue une fois en mémoire), trois copies
tournent, la remise à zéro (RZ1) n'est pas annulée par la reprise. S5-05 : un `profil.toml` illisible n'est
jamais remplacé par l'autre joueur ni par un `principal` neuf ; le lanceur propose de le réparer en mettant
l'ancien fichier de côté.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_launch_no_terminal import capture_run, home  # noqa: F401  (fixture `home`)

from openride_core import launcher, profiles
from openride_core.profile import (
    BACKUP_COPIES,
    Profile,
    backup_paths,
    load_profile,
    peek_profile,
    record_purchase,
    repair,
    save_profile,
)


def _saved(path: Path, *items: str) -> Profile:
    p = Profile()
    for item in items:
        record_purchase(p, item, 10)
        save_profile(p, path)
    return p


# --- S5-01 : profile.json et ses copies ---------------------------------------------------------------

def test_backup_survives_second_launch_and_later_saves(tmp_path):
    """Scénario de la revue : abîmé, un lancement sans écriture, puis un autre, puis deux enregistrements."""
    path = tmp_path / "profile.json"
    _saved(path, "wheels_light", "frame_climber")   # .bak = {wheels_light}
    path.write_text("{tronqué", encoding="utf-8")
    assert load_profile(path).purchased == {"wheels_light"}
    assert len(list(tmp_path.glob("profile.json.corrompu-*"))) == 1
    second = load_profile(path)                      # avant : profil par défaut
    assert second.purchased == {"wheels_light"}
    record_purchase(second, "helmet_aero", 10)
    save_profile(second, path)
    save_profile(second, path)
    for b in backup_paths(path):
        if b.exists():
            assert "wheels_light" in b.read_text(encoding="utf-8")   # aucune copie n'est un profil vide


def test_missing_file_next_to_a_backup_is_put_back(tmp_path):
    path = tmp_path / "profile.json"
    _saved(path, "wheels_light", "frame_climber")
    path.unlink()                                    # reprise interrompue d'une version d'avant
    assert load_profile(path).purchased == {"wheels_light"}
    assert path.exists()


def test_three_copies_rotate(tmp_path):
    path = tmp_path / "profile.json"
    _saved(path, "a1", "a2", "a3", "a4", "a5")
    assert BACKUP_COPIES == 3
    bought = [json.loads(b.read_text(encoding="utf-8"))["purchases"] for b in backup_paths(path)]
    assert [len(x) for x in bought] == [4, 3, 2]     # .bak, .bak.2, .bak.3 : les trois versions d'avant
    assert not path.with_name("profile.json.bak.4").exists()


def test_older_copy_is_used_when_newer_ones_are_broken(tmp_path):
    path = tmp_path / "profile.json"
    _saved(path, "a1", "a2", "a3")                   # .bak = {a1, a2}, .bak.2 = {a1}
    path.write_text("{", encoding="utf-8")
    backup_paths(path)[0].write_text("[]", encoding="utf-8")
    rec = repair(path)
    assert load_profile(path).purchased == {"a1"}
    assert rec.restored == path and rec.kept is not None
    text = rec.message("Alex")
    assert "« Alex »" in text and "abîmé" in text and rec.kept.name in text and "rien n'a été effacé" in text


def test_nothing_readable_says_defaults_and_keeps_the_file(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text("{", encoding="utf-8")
    rec = repair(path)
    assert rec.defaults and "valeurs par défaut" in rec.message()
    assert len(list(tmp_path.glob("profile.json.corrompu-*"))) == 1


def test_healthy_or_absent_profile_needs_no_message(tmp_path):
    path = tmp_path / "profile.json"
    assert repair(path).message() is None and not path.exists()
    _saved(path, "a1")
    assert repair(path).message() is None


def test_read_error_moves_nothing(tmp_path, monkeypatch):
    """Erreur de lecture passagère : rien n'est mis de côté ni réécrit, la copie sert en mémoire."""
    from openride_core import profile as prof_mod

    path = tmp_path / "profile.json"
    _saved(path, "a1", "a2")
    before = path.read_bytes()
    real = prof_mod._read

    def flaky(p, known):
        if p == path:
            raise PermissionError("lecture refusée")
        return real(p, known)
    monkeypatch.setattr(prof_mod, "_read", flaky)
    assert load_profile(path).purchased == {"a1"}
    assert path.read_bytes() == before and not list(tmp_path.glob("*.corrompu-*"))


def test_peek_writes_nothing(tmp_path):
    path = tmp_path / "profile.json"
    _saved(path, "a1", "a2")
    path.write_text("{", encoding="utf-8")
    assert peek_profile(path).purchased == {"a1"}
    assert path.read_text(encoding="utf-8") == "{" and not list(tmp_path.glob("*.corrompu-*"))


def test_reset_to_zero_is_not_undone_by_the_backups(tmp_path):
    """La remise à zéro (RZ1) déplace le profil ET ses copies : la reprise ne la contourne pas."""
    base = tmp_path / "Profils"
    ctx = profiles.ProfileContext.for_id("alex", base)
    profiles.ensure_description(ctx)
    _saved(ctx.profile_path, "a1", "a2", "a3")
    _, moved = profiles.reset_stats(ctx, base)
    assert "profile.json.bak" in moved and "profile.json.bak.2" in moved
    assert load_profile(ctx.profile_path).purchased == set()
    assert not ctx.profile_path.exists()


# --- S5-05 : profil.toml illisible -------------------------------------------------------------------

def _player(base: Path, pid: str, name: str, extra: str = "") -> Path:
    ctx = profiles.ProfileContext.for_id(pid, base)
    path = profiles.ensure_description(ctx)
    path.write_text(path.read_text(encoding="utf-8").replace(f'nom = "{pid}"', f'nom = "{name}"') + extra,
                    encoding="utf-8")
    return path


def _migrated(home_dir: Path, last: str | None = None) -> Path:
    base = home_dir / "Profils"
    base.mkdir(parents=True, exist_ok=True)
    (base / profiles.MIGRATION_FILE).write_text("sauvegarde\nfini\n", encoding="utf-8")
    if last:
        (home_dir / "config.toml").write_text(f'[profils]\ndernier = "{last}"\n', encoding="utf-8")
    return base


def test_last_player_unreadable_is_not_replaced_by_the_other(tmp_path):
    base = _migrated(tmp_path, last="alex")
    _player(base, "alex", "Alex").write_text("[profil\nid = ", encoding="utf-8")
    _player(base, "bea", "Béa")
    assert profiles.unreadable(base)[0][0] == "alex"
    assert profiles.default_id(base) == "alex"       # avant : « bea »
    with pytest.raises(profiles.ProfileContextError, match="illisible"):
        profiles.ProfileContext.for_id("alex", base)


def test_single_unreadable_player_is_not_replaced_by_a_new_principal(tmp_path):
    base = _migrated(tmp_path)
    _player(base, "alex", "Alex").write_text('[profil]\nid = "alex"\ntype = "pro"\n', encoding="utf-8")
    assert profiles.default_id(base) == "alex"       # avant : « principal », neuf et vide


def test_set_aside_keeps_the_old_file_and_what_still_reads(tmp_path):
    base = tmp_path / "Profils"
    path = _player(base, "alex", "Alex")
    broken = (path.read_text(encoding="utf-8").replace('type = "joueur"', 'type = "pro"')
              + "\n[rider]\nftp_w = 250\nmass_kg = 70\n\n[camera]\nmode = = \n")
    path.write_text(broken, encoding="utf-8")
    kept, lost = profiles.set_aside_description(base / "alex", "alex")
    assert kept.read_text(encoding="utf-8") == broken      # jamais effacé
    assert kept.name.startswith("profil.toml.illisible-")
    ctx = profiles.ProfileContext.for_id("alex", base)
    assert ctx.name == "Alex" and ctx.type == "joueur"
    assert "ftp_w = 250" in path.read_text(encoding="utf-8")
    assert lost == ["[camera]"]


def test_launcher_repairs_unreadable_profile_on_yes(home, monkeypatch):  # noqa: F811
    runs = capture_run(monkeypatch)
    base = _migrated(home, last="alex")
    _player(base, "alex", "Alex", extra="\n[rider]\nftp_w = 250\n[[oops\n")
    _player(base, "bea", "Béa")
    questions: list[str] = []
    messages: list[tuple[str, bool]] = []
    assert launcher.main([], message=lambda t, e: messages.append((t, e)),
                         ask=lambda q: questions.append(q) or True) == 0
    assert len(questions) == 1 and "« alex »" in questions[0] and "rien n'est effacé" in questions[0]
    assert any("réparé" in t for t, _ in messages)
    assert list((base / "alex").glob("profil.toml.illisible-*"))
    assert runs and runs[0].recover_cmd[-2:] == ["--profil", "alex"]   # pas l'autre joueur


def test_launcher_refusal_stops_instead_of_starting_the_other_player(home, monkeypatch):  # noqa: F811
    runs = capture_run(monkeypatch)
    base = _migrated(home, last="alex")
    path = _player(base, "alex", "Alex")
    path.write_text("[profil\n", encoding="utf-8")
    _player(base, "bea", "Béa")
    messages: list[tuple[str, bool]] = []
    assert launcher.main([], message=lambda t, e: messages.append((t, e)), ask=lambda q: False) == 1
    assert not runs and path.read_text(encoding="utf-8") == "[profil\n"
    assert "profil.toml" in messages[-1][0] and "aucun autre" in messages[-1][0]


def test_launcher_puts_back_a_broken_profile_json_and_says_so(home, monkeypatch):  # noqa: F811
    runs = capture_run(monkeypatch)
    base = _migrated(home, last="alex")
    _player(base, "alex", "Alex")
    pj = base / "alex" / "profile.json"
    _saved(pj, "a1", "a2")
    pj.write_text("{", encoding="utf-8")
    messages: list[tuple[str, bool]] = []
    assert launcher.main([], message=lambda t, e: messages.append((t, e)), ask=lambda q: True) == 0
    assert runs and load_profile(pj).purchased == {"a1"}
    assert any("« Alex »" in t and "copie" in t for t, _ in messages)
