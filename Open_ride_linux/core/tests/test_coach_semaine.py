"""Lot OS1 : objectif de la semaine de l'accueil (séances comptées de la semaine ISO contre le réglage
`coach.seances_semaine`), séances fabriquées d'un cycliste fictif (aucune donnée réelle)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from openride_core import coach, config, ipc_lists, settings

TABLE = coach.load_table()
SUNDAY = date(2026, 11, 22)       # dimanche
WEDNESDAY = date(2026, 11, 18)


def fact(day: date, minutes: float, hour: int = 18) -> coach.SessionFacts:
    ts = datetime.combine(day, time(hour, 0)).timestamp()
    return coach.SessionFacts(ts, minutes * 60.0, 40.0, {n: 0.0 for n in coach.NEEDS}, False, {})


def test_counts_this_iso_week_only():
    facts = [fact(SUNDAY - timedelta(days=7), 45),        # dimanche précédent : autre semaine
             fact(date(2026, 11, 16), 45, hour=0),         # lundi à minuit : compte
             fact(WEDNESDAY, 45), fact(WEDNESDAY, 12)]     # 12 min : trop court
    assert coach.week_goal(facts, WEDNESDAY, 3, TABLE) == {"target": 3, "done": 2, "days_left": 5,
                                                          "reached": False}
    facts.append(fact(date(2026, 11, 20), 30))
    assert coach.week_goal(facts, SUNDAY, 3, TABLE) == {"target": 3, "done": 3, "days_left": 1, "reached": True}
    assert coach.week_goal(facts, date(2026, 11, 19), 3, TABLE)["done"] == 2   # séance de vendredi pas encore


def test_monday_and_none():
    assert coach.week_goal([], date(2026, 11, 23), 2, TABLE) == {"target": 2, "done": 0, "days_left": 7,
                                                                 "reached": False}
    assert coach.week_goal([fact(SUNDAY, 60)], SUNDAY, 0, TABLE) is None


def test_setting_default_and_bounds():
    assert config.CoachConfig().seances_semaine == 2
    assert config.BOUNDS[("coach", "seances_semaine")] == (0, 7)
    assert ("coach", "seances_semaine") in config.PROFILE_KEYS
    item = next(s for s in settings.current(config.Config()) if s["key"] == "coach.seances_semaine")
    assert item["label"] == "Objectif de la semaine" and item["min"] == 0 and item["max"] == 7
    assert item["value"] == 2 and item["unit"] == "séances" and "0 : pas d'objectif" in item["help"]


def test_coach_message_carries_week_goal():
    advice = {"date": "2026-11-22", "need": "light", "need_label": "aérobie léger", "rule": "R6", "reason": "r",
              "duration_min": 45, "notes": [], "alternatives": [], "workout": None, "other_workouts": [],
              "details": {}, "week_goal": {"target": 2, "done": 1, "days_left": 1, "reached": False}}
    msg = ipc_lists.build_coach_message(4, advice)
    assert msg["week_goal"] == {"target": 2, "done": 1, "days_left": 1, "reached": False}
    advice.pop("week_goal")
    assert ipc_lists.build_coach_message(4, advice)["week_goal"] is None


def test_advice_today_adds_week_goal(tmp_path):
    r = coach.advice_today(SUNDAY, 250.0, "endurance", 60, directory=tmp_path / "act", workouts_dir=tmp_path / "w",
                           week_target=3)
    assert r["week_goal"] == {"target": 3, "done": 0, "days_left": 1, "reached": False}
    r = coach.advice_today(SUNDAY, 250.0, "endurance", 60, directory=tmp_path / "act", workouts_dir=tmp_path / "w")
    assert r["week_goal"] is None
