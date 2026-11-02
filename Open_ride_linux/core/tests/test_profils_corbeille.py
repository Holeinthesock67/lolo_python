"""Profil d'essai vidé et profil restauré depuis la corbeille, depuis le menu (lot O33, contrat IPC
révision 1.5) : commandes `clear_trial_profile` et `restore_profile`, champ `trash` du message `profiles`."""

from __future__ import annotations

from datetime import datetime

from openride_core import profiles

from test_contract_ipc import assert_valid  # noqa: F401
from test_profils_joueurs import base, home, make, of  # noqa: F401  (fixture `home`)
from test_progression import write_journal


def trial_with_a_ride(home):
    trial = profiles.ProfileContext.for_id(profiles.TRIAL_ID, base(home))
    profiles.ensure_description(trial)
    write_journal(trial.journal_dir / "essai.jsonl", km=40, climb_m=400, minutes=60, start_ts=1_760_000_000.0)
    (trial.root / "records.json").write_text("{}", encoding="utf-8")
    return trial


def test_trash_entries_and_restore(home):
    b = base(home)
    profiles.delete("cycliste-b", "cycliste-a", b, now=datetime(2026, 10, 30, 21, 5, 0))
    (b / profiles.TRASH_DIRNAME / "pas-un-profil").mkdir()
    entries = profiles.trash_entries(b)
    assert entries == [{"id": "cycliste-b_20261030-210500", "name": "Cycliste B", "deleted": "2026-10-30"}]
    ctx = profiles.restore("cycliste-b_20261030-210500", b)
    assert ctx.name == "Cycliste B" and [c.id for c in profiles.list_contexts(b)] == ["cycliste-a", "cycliste-b"]
    assert profiles.trash_entries(b) == []


def test_restore_is_refused_when_taken(home):
    b = base(home)
    profiles.delete("cycliste-b", "cycliste-a", b, now=datetime(2026, 10, 30, 21, 5, 0))
    profiles.create("Cycliste B", b)   # même nom, même identifiant repris entre-temps
    for entry, why in (("cycliste-b_20261030-210500", "existe déjà"), ("../x_20261030-210500", "introuvable"),
                       (12, "introuvable")):
        try:
            profiles.restore(entry, b)
        except profiles.ProfileContextError as exc:
            assert why in str(exc)
        else:
            raise AssertionError(f"restauration acceptée : {entry}")


def test_restore_and_trash_from_the_menu(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    s._on_command("delete_profile", {"id": "cycliste-b"}, 2)
    msg = of(frames, "profiles")[-1]
    assert [i["id"] for i in msg["items"]] == ["cycliste-a"] and msg["trash"][0]["name"] == "Cycliste B"
    s._on_command("restore_profile", {"id": msg["trash"][0]["id"]}, 3)
    msg = of(frames, "profiles")[-1]
    assert [i["id"] for i in msg["items"]] == ["cycliste-a", "cycliste-b"] and msg["trash"] == []
    assert s.server.hello_config["profile"]["count"] == 2
    s._on_command("restore_profile", {"id": "cycliste-b_20261030-210500"}, 4)
    assert [e["code"] for e in of(frames, "error")] == ["profile_invalid"]


def test_clear_trial_from_a_player_profile(home, monkeypatch):
    trial = trial_with_a_ride(home)
    s, frames = make(home, monkeypatch)
    s._on_command("clear_trial_profile", {}, 5)
    assert {p.name for p in trial.root.iterdir()} <= set(profiles.KEPT_ON_CLEAR) and (trial.root / profiles.FILE_NAME).is_file()
    assert of(frames, "profiles")[-1]["active"] == "cycliste-a"
    with profiles.ProfileLock(trial):
        s._on_command("clear_trial_profile", {}, 6)   # essai ouvert par un autre OpenRide
    assert [e["code"] for e in of(frames, "error")] == ["profile_invalid"]


def test_clear_trial_while_riding_it_reloads(home, monkeypatch):
    trial = trial_with_a_ride(home)
    s, frames = make(home, monkeypatch)
    s._on_command("select_profile", {"id": profiles.TRIAL_ID}, 7)
    frames.clear()
    s._on_command("clear_trial_profile", {}, 8)
    assert [f["type"] for f in frames][:1] == ["hello_ack"]
    assert not trial.journal_dir.exists() and profiles.current().id == profiles.TRIAL_ID
    s._on_command("select_route", {}, 9)
    s._on_command("start", {}, 10)
    s._on_command("clear_trial_profile", {}, 11)
    assert of(frames, "error")[-1]["code"] == "busy"
