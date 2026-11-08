"""Lot CO3 : contrat du conseil (commande `get_coach`, message `coach`), saisies du conseil (prochaine
course, suggestion de la montre) et réglages `[coach]` ; historiques fabriqués, aucune donnée réelle."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta

from openride_core import coach, profiles
from openride_core.coach import Inputs
from openride_core.ipc_lists import build_coach_message

from test_coach import FTP, TABLE, TODAY, base_history, write_journal
from test_contract_ipc import assert_valid
from test_profils_joueurs import home, make, of  # noqa: F401  (fixture `home`)


def ts(day: date) -> float:
    return datetime(day.year, day.month, day.day, 18).timestamp()


def endurance(folder, today: date, watts: float) -> None:
    """Sorties quotidiennes d'une heure en Z2 d'il y a 40 à 8 jours, puis une semaine de repos : CTL ≈ 22,
    au-dessus de la reprise, forme positive, 20 séances sur 4 semaines."""
    for d in range(8, 41):
        write_journal(folder, f"s{d:02d}", ts(today - timedelta(days=d)), [(3600, watts)])


def rides(home):
    """Profil A (FTP 200) : endurance à 140 W, rien ne bloque."""
    jdir = profiles.ProfileContext.for_id("cycliste-a", home / "Profils").journal_dir
    endurance(jdir, date.today(), 140.0)
    return jdir


def coach_frames(s, frames, name, args, cmd_id=7):
    errors: list[str] = []
    s.server.send_error = lambda code, text: errors.append(code)
    frames.clear()
    asyncio.run(s._send_coach(name, args, cmd_id))
    return of(frames, "coach"), errors


# --- message `coach` -----------------------------------------------------------------------------------

def test_message_matches_the_command_and_its_schema():
    adv = coach.advise(base_history(), FTP, TODAY, Inputs(), TABLE, coach.classify_library(
        __import__("openride_core.plans", fromlist=["BUILTIN_WORKOUTS_DIR"]).BUILTIN_WORKOUTS_DIR, FTP, TABLE))
    msg = build_coach_message(3, adv)
    assert_valid(msg)
    assert (msg["need"], msg["rule"], msg["reason"]) == (adv["need"], adv["rule"], adv["reason"])
    assert msg["duration_s"] == adv["duration_min"] * 60 and msg["route"] is None
    assert msg["workout"]["duration_s"] == adv["workout"]["duration_min"] * 60
    assert msg["tss_estimate"] == adv["workout"]["tss_estimate"]
    assert msg["details"] == adv["details"]


def test_every_rule_gives_a_valid_message():
    cases = [
        ([], Inputs()),                                                       # R0
        (base_history(), Inputs(watch={"type": "repos", "duration_min": None, "target_w": None})),   # RG
        (base_history(), Inputs(raced_yesterday=True, yesterday_tss=95)),     # R1
        (base_history(), Inputs(next_race=TODAY + timedelta(days=2), race_kind="championnat")),     # R2
        (base_history(), Inputs(plan_today={"plan": "p", "name": "Plan", "week": 1, "workout": "w"})),  # R5
        (base_history(), Inputs(chosen_need="anaerobic")),                    # CH
    ]
    rules = []
    for facts, inputs in cases:
        msg = build_coach_message(1, coach.advise(facts, FTP, TODAY, inputs, TABLE, []))
        assert_valid(msg)
        rules.append(msg["rule"])
    assert rules == ["R0", "RG", "R1", "R2", "R5", "CH"]


def test_chosen_need_keeps_the_advice_as_first_idea():
    plain = coach.advise(base_history(), FTP, TODAY, Inputs(), TABLE, [])
    chosen = coach.advise(base_history(), FTP, TODAY, Inputs(chosen_need="ftp_test"), TABLE, [])
    assert (chosen["need"], chosen["rule"], chosen["duration_min"]) == ("ftp_test", "CH", TABLE["durations"]["ftp_test"])
    assert chosen["alternatives"][0] == plain["need"]
    assert chosen["reason"] == "Besoin choisi : test de FTP."
    assert any(plain["reason"] in n for n in chosen["notes"])
    same = coach.advise(base_history(), FTP, TODAY, Inputs(chosen_need=plain["need"]), TABLE, [])
    assert same["rule"] == plain["rule"]                   # le besoin du conseil : rien ne change


# --- prochaine course dans conseil.json ----------------------------------------------------------------

def test_next_race_saved_until_its_day(tmp_path):
    path = tmp_path / "conseil.json"
    coach.save_watch(coach.parse_watch("fond", TABLE), TODAY, path)
    race = coach.parse_race((TODAY + timedelta(days=2)).isoformat(), "championnat", TODAY)
    coach.save_next_race(race, path)
    assert coach.saved_next_race(TODAY, path) == (TODAY + timedelta(days=2), "championnat")
    assert coach.saved_next_race(TODAY + timedelta(days=2), path) is not None     # le jour même
    assert coach.saved_next_race(TODAY + timedelta(days=3), path) is None         # passée
    assert coach.saved_watch(TODAY, TABLE, path) is not None                      # autre clé gardée
    assert coach.clear_next_race(path) and not coach.clear_next_race(path)
    assert coach.saved_next_race(TODAY, path) is None


def test_race_input_is_checked():
    for day, kind in (("hier", None), ((TODAY - timedelta(days=1)).isoformat(), None),
                      ((TODAY + timedelta(days=400)).isoformat(), None), (TODAY.isoformat(), "marathon"), (None, None)):
        try:
            coach.parse_race(day, kind, TODAY)
        except coach.CoachError:
            continue
        raise AssertionError(f"accepté : {day} {kind}")
    assert coach.parse_race(TODAY.isoformat(), None, TODAY) == {"date": TODAY.isoformat(), "kind": "course"}


# --- commandes IPC ---------------------------------------------------------------------------------------

def test_get_coach_and_inputs_over_ipc(home, monkeypatch):
    rides(home)
    s, frames = make(home, monkeypatch)
    s.workouts_dir = home / "vide"
    (msg,), errors = coach_frames(s, frames, "get_coach", {})
    assert not errors and msg["request_cmd_id"] == 7 and msg["details"]["ftp_w"] == 200.0
    assert msg["details"]["sessions_28d"] == 20 and msg["details"]["objective"] == "endurance"

    in_two_days = (date.today() + timedelta(days=2)).isoformat()
    (msg,), _ = coach_frames(s, frames, "set_next_race", {"date": in_two_days, "kind": "championnat"})
    assert msg["rule"] == "R2" and msg["details"]["next_race"] == {"date": in_two_days, "kind": "championnat"}
    saved = json.loads((home / "Profils" / "cycliste-a" / "conseil.json").read_text(encoding="utf-8"))
    assert saved["next_race"] == {"date": in_two_days, "kind": "championnat"}
    (msg,), _ = coach_frames(s, frames, "get_coach", {})
    assert msg["rule"] == "R2"                                         # reprise au calcul suivant

    (msg,), _ = coach_frames(s, frames, "set_watch_advice", {"type": "seuil", "duration_min": 50})
    assert (msg["rule"], msg["need"], msg["duration_s"]) == ("RG", "intense", 3000)
    assert any("Course dans 2 jours" in n for n in msg["notes"])
    (msg,), _ = coach_frames(s, frames, "clear_watch_advice", {})
    assert msg["rule"] == "R2"
    (msg,), _ = coach_frames(s, frames, "clear_next_race", {})
    assert msg["rule"] != "R2" and msg["details"]["next_race"] is None

    (msg,), _ = coach_frames(s, frames, "get_coach", {"need": "anaerobic"})
    assert (msg["rule"], msg["need"]) == ("CH", "anaerobic")


def test_bad_inputs_answer_bad_args(home, monkeypatch):
    s, frames = make(home, monkeypatch)
    s.workouts_dir = home / "vide"
    for name, args in (("get_coach", {"need": "plan"}), ("set_next_race", {"date": "2020-01-01"}),
                       ("set_next_race", {}), ("set_watch_advice", {"type": "marathon"}),
                       ("set_watch_advice", {"type": "seuil", "duration_min": "50"}),
                       ("set_watch_advice", {"type": "seuil", "duration_min": 2})):
        found, errors = coach_frames(s, frames, name, args)
        assert not found and errors == ["bad_args"], (name, args)
    assert not (home / "Profils" / "cycliste-a" / "conseil.json").exists()


def test_settings_of_the_profile_feed_the_advice(home, monkeypatch):
    from openride_core import settings

    rides(home)
    s, frames = make(home, monkeypatch)
    s.workouts_dir = home / "vide"
    items = {i["key"]: i for i in settings.current(s.cfg)}
    assert items["coach.objectif"]["choices"] == ["endurance", "courses", "grimpeur"]
    assert (items["coach.temps_disponible_min"]["min"], items["coach.temps_disponible_min"]["max"]) == (30, 120)
    s._on_command("set_setting", {"key": "coach.objectif", "value": "courses"}, 20)
    s._on_command("set_setting", {"key": "coach.temps_disponible_min", "value": 90}, 21)
    profil = (home / "Profils" / "cycliste-a" / "profil.toml").read_text(encoding="utf-8")
    assert "[coach]" in profil and 'objectif = "courses"' in profil        # suit le joueur (MJ4)
    (msg,), _ = coach_frames(s, frames, "get_coach", {"need": "light"})
    assert msg["details"]["objective"] == "courses" and msg["duration_s"] == 90 * 60


def test_cli_saves_next_race_and_reads_settings(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path)}
    env.pop("OPENRIDE_PROFIL", None)
    act = tmp_path / "Activities"
    endurance(act / ".journal", TODAY, 175.0)
    cfg = tmp_path / "config.toml"
    cfg.write_text('[coach]\nobjectif = "grimpeur"\ntemps_disponible_min = 45\n', encoding="utf-8")
    base = [sys.executable, "-m", "openride_core", "coach", "--date", TODAY.isoformat(), "--ftp", "250",
            "--dir", str(act), "--workouts", str(tmp_path / "vide"), "--config", str(cfg), "--json"]
    run = lambda *extra: subprocess.run(base + list(extra), capture_output=True, text=True, env=env, check=True)  # noqa: E731
    first = json.loads(run("--besoin", "light").stdout)
    assert first["details"]["objective"] == "grimpeur" and first["duration_min"] == 45
    race = (TODAY + timedelta(days=1)).isoformat()
    run("--prochaine-course", f"{race}:championnat", "--enregistrer")
    again = json.loads(run().stdout)
    assert again["rule"] == "R2" and again["details"]["next_race"] == {"date": race, "kind": "championnat"}
    assert "effacée" in run("--effacer-course").stdout
    assert json.loads(run().stdout)["details"]["next_race"] is None
