"""Série BC, lot BC1 : collection de cartes (catalogue, règles, saisons, anti-triche, annonce).

Historiques synthétiques seulement : dates fictives, aucune donnée personnelle (plan BC §9).
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from openride_core.collection import (
    RARITIES, TEXT_MAX, TITLE_MAX, CollectionError, add_years, announcement, card_line, easter,
    evaluate, load_catalogue, load_seen, new_cards, parse_catalogue, save_seen, season_edition,
    seen_path,
)
from openride_core.journal import JournalWriter, Record
from openride_core.progression import (
    LevelInfo, Progress, SessionFacts, SessionResult, XpGains, load_table, recompute,
)

UTC = timezone.utc
NOW = datetime(2030, 1, 1, tzinfo=UTC).timestamp()


@pytest.fixture(scope="module")
def table():
    return load_table(user_path=None)


@pytest.fixture(scope="module")
def cards(table):
    return load_catalogue(table=table)


def ts(y, m, d, h=18, mi=0) -> float:
    return datetime(y, m, d, h, mi, tzinfo=UTC).timestamp()


def facts(start: float, km: float = 30.0, minutes: float = 60.0, climb: float = 200.0,
          events: list[dict] | None = None, name: str | None = None) -> SessionFacts:
    return SessionFacts(journal=name or f"{start:.0f}.jsonl", start_ts=start, duration_s=minutes * 60,
                        distance_m=km * 1000, climb_m=climb, events=list(events or []))


def progress(*items: SessionFacts) -> Progress:
    """Séances déjà comptées par la progression (le tri chronologique est celui de `recompute`)."""
    ordered = sorted(items, key=lambda f: f.start_ts)
    return Progress(sessions=[SessionResult(f, XpGains({}), None) for f in ordered], errors=[],
                    total_xp=0, level=LevelInfo(1, 0, 0, 1000), stats={}, challenges=[])


def run(cards, table, *items: SessionFacts, now: float = NOW):
    return evaluate(progress(*items), cards, table, tz=UTC, now=now)


def keys(col) -> list[str]:
    return [e.key for e in col.earned]


# --- catalogue --------------------------------------------------------------------------------

def test_catalogue_delivered(cards, table):
    assert len(cards) >= 40
    assert {c.family for c in cards} >= {"distance", "heure", "saison", "anniversaire", "modes"}
    assert all(len(c.title) <= TITLE_MAX and len(c.text) <= TEXT_MAX for c in cards)
    assert all(c.rarity in RARITIES for c in cards)
    assert len({c.visual for c in cards}) == len(cards), "un visuel par carte (fiche de BC4)"
    challenges = {c.id for c in table.challenges}
    cited = {c.rule["challenge"] for c in cards if c.kind == "defi"}
    assert cited == challenges, "chaque défi de la série V a sa carte, une seule"
    for wanted in ("km_100", "leve_tot", "halloween", "noel", "premiere_annee"):
        assert wanted in {c.id for c in cards}


def _one(rule: dict, **over) -> dict:
    card = {"id": "x", "title": "X", "text": "x", "family": "seance", "rarity": "commune",
            "visual": "x", "rule": rule}
    card.update(over)
    return {"cards": [card]}


@pytest.mark.parametrize("data, message", [
    (_one({"kind": "inconnue"}), "kind"),
    (_one({"kind": "cumul", "stat": "total_miles", "threshold": 1}), "stat inconnue"),
    (_one({"kind": "cumul", "stat": "total_km"}), "threshold"),
    (_one({"kind": "seance", "min_km": "loin"}), "float attendu"),
    (_one({"kind": "seance", "count": 0}), "count"),
    (_one({"kind": "seance", "vitesse": 3}), "clé inconnue"),
    (_one({"kind": "heure", "from_h": 7, "to_h": 7}), "from_h"),
    (_one({"kind": "mode", "event": "rogue_run", "win": True}), "survivor_summary"),
    (_one({"kind": "mode", "event": "kart"}), "ligne de jeu inconnue"),
    (_one({"kind": "defi", "challenge": "defi_fantome"}), "défi inconnu"),
    (_one({"kind": "saison", "from": "02-30", "to": "03-01"}, family="saison"), "date impossible"),
    (_one({"kind": "saison", "from": "10-25"}, family="saison"), "vont ensemble"),
    (_one({"kind": "saison", "from": "10-25", "to": "10-31", "easter_from": 0, "easter_to": 0},
          family="saison"), "soit"),
    (_one({"kind": "saison", "from": "10-25", "to": "10-31"}), "famille"),
    (_one({"kind": "seance"}, family="saison"), "famille"),
    (_one({"kind": "seance"}, rarity="mythique"), "rarity"),
    (_one({"kind": "seance"}, title="T" * (TITLE_MAX + 1)), "title"),
    (_one({"kind": "seance"}, id="Majuscule"), "id"),
    ({"cards": []}, "absente ou vide"),
])
def test_catalogue_refuses(data, message, table):
    with pytest.raises(CollectionError, match=message):
        parse_catalogue(data, "essai.toml", table)


def test_catalogue_refuses_duplicate(table):
    data = _one({"kind": "seance"})
    data["cards"].append(dict(data["cards"][0]))
    with pytest.raises(CollectionError, match="double"):
        parse_catalogue(data, "essai.toml", table)


# --- dates ------------------------------------------------------------------------------------

def test_easter_known_dates():
    assert [easter(y) for y in (2024, 2025, 2026, 2027, 2038)] == [
        date(2024, 3, 31), date(2025, 4, 20), date(2026, 4, 5), date(2027, 3, 28), date(2038, 4, 25)]


def test_season_windows():
    halloween = {"from": "10-25", "to": "10-31"}
    assert season_edition(halloween, date(2026, 10, 31)) == 2026
    assert season_edition(halloween, date(2026, 11, 1)) is None
    assert season_edition(halloween, date(2026, 10, 24)) is None
    winter = {"from": "12-28", "to": "01-03"}
    assert season_edition(winter, date(2026, 12, 30)) == 2026
    assert season_edition(winter, date(2027, 1, 2)) == 2026
    assert season_edition(winter, date(2027, 1, 4)) is None
    assert season_edition({"easter_from": -1, "easter_to": 1}, date(2026, 4, 6)) == 2026
    assert season_edition({"easter_from": -1, "easter_to": 1}, date(2026, 4, 7)) is None


def test_add_years_leap_day():
    assert add_years(date(2028, 2, 29), 1) == date(2029, 3, 1)
    assert add_years(date(2026, 11, 7), 1) == date(2027, 11, 7)


# --- règles -----------------------------------------------------------------------------------

def test_distance_card_won_at_the_right_session(cards, table):
    sessions = [facts(ts(2026, 3, d), km=30) for d in (2, 3, 4, 5)]
    col = run(cards, table, *sessions)
    km100 = next(e for e in col.earned if e.card.id == "km_100")
    assert km100.start_ts == sessions[3].start_ts   # 120 km à la 4e séance, 90 km à la 3e
    assert col.progress["km_500"] == (120.0, 500.0)
    assert "premiere_seance" == col.earned[0].card.id


def test_challenge_card_uses_progression_threshold(cards, table):
    big = [facts(ts(2026, 3, 1) + i * 86400, km=101, minutes=200) for i in range(10)]
    col = run(cards, table, *big)
    km1000 = next(e for e in col.earned if e.card.id == "km_1000")
    assert km1000.start_ts == big[9].start_ts   # 1 010 km à la 10e séance
    assert col.has("seance_100km") and col.has("seance_50km") and col.has("seance_3h")
    assert not run(cards, table, *big[:9]).has("km_1000")


@pytest.mark.parametrize("hour, minute, minutes, won", [
    (6, 30, 30, True), (4, 0, 20, True), (6, 59, 30, True),
    (7, 0, 30, False), (6, 30, 10, False), (3, 59, 30, False),
])
def test_early_bird(cards, table, hour, minute, minutes, won):
    col = run(cards, table, facts(ts(2026, 5, 4, hour, minute), minutes=minutes))
    assert col.has("leve_tot") is won


def test_early_bird_uses_local_time(cards, table):
    """5 h 30 UTC = 7 h 30 à Paris en été : pas lève-tôt dans ce fuseau."""
    from zoneinfo import ZoneInfo

    f = facts(ts(2026, 7, 1, 5, 30))
    assert evaluate(progress(f), cards, table, tz=UTC, now=NOW).has("leve_tot")
    assert not evaluate(progress(f), cards, table, tz=ZoneInfo("Europe/Paris"), now=NOW).has("leve_tot")


def test_night_owl_wraps_midnight_and_count(cards, table):
    assert run(cards, table, facts(ts(2026, 5, 4, 23, 0))).has("noctambule")
    assert run(cards, table, facts(ts(2026, 5, 4, 1, 0))).has("noctambule")
    assert not run(cards, table, facts(ts(2026, 5, 4, 21, 59))).has("noctambule")
    early = [facts(ts(2026, 5, 1 + i, 6, 0)) for i in range(10)]
    assert run(cards, table, *early).has("leve_tot_10")
    col = run(cards, table, *early[:9])
    assert not col.has("leve_tot_10") and col.progress["leve_tot_10"] == (9.0, 10.0)


def test_seasonal_editions(cards, table):
    col = run(cards, table, facts(ts(2026, 10, 31)), facts(ts(2027, 10, 26)),
              facts(ts(2027, 10, 27)), facts(ts(2027, 12, 25)), facts(ts(2026, 11, 1)))
    assert [k for k in keys(col) if k.startswith("halloween")] == ["halloween:2026", "halloween:2027"]
    assert col.has("noel", 2027) and not col.has("noel", 2026)
    assert "halloween" not in col.progress, "pas d'avancement affiché pour une saison"


def test_seasonal_needs_minutes_and_count(cards, table):
    assert not run(cards, table, facts(ts(2026, 12, 24), minutes=10)).has("noel")
    july = [facts(ts(2026, 7, d)) for d in range(1, 11)]
    assert run(cards, table, *july).has("juillet", 2026)
    assert not run(cards, table, *july[:9], facts(ts(2027, 7, 1))).has("juillet")


def test_easter_card(cards, table):
    assert run(cards, table, facts(ts(2027, 3, 29))).has("paques", 2027)   # lundi de Pâques 2027
    assert not run(cards, table, facts(ts(2027, 4, 5))).has("paques")


def test_consecutive_weeks(cards, table):
    mondays = [date(2026, 1, 5) + timedelta(weeks=i) for i in range(4)]
    weekly = [facts(ts(d.year, d.month, d.day)) for d in mondays]
    assert run(cards, table, *weekly).has("semaines_4")
    gap = weekly[:2] + [facts(weekly[3].start_ts + 7 * 86400)] + weekly[3:]
    col = run(cards, table, *gap)
    assert not col.has("semaines_4") and col.progress["semaines_4"] == (2.0, 4.0)
    three = [facts(ts(2026, 1, d)) for d in (5, 7, 9)]       # lundi, mercredi, vendredi
    assert run(cards, table, *three).has("semaine_3")
    assert not run(cards, table, facts(ts(2026, 1, 9)), facts(ts(2026, 1, 12)),
                   facts(ts(2026, 1, 13))).has("semaine_3"), "deux semaines ISO différentes"


def test_twelve_weeks_two_per_week(cards, table):
    days = [date(2026, 1, 5) + timedelta(weeks=w, days=dd) for w in range(12) for dd in (0, 3)]
    col = run(cards, table, *[facts(ts(d.year, d.month, d.day)) for d in days])
    assert col.has("semaines_12")
    col = run(cards, table, *[facts(ts(d.year, d.month, d.day)) for d in days[:-1]])
    assert not col.has("semaines_12") and col.progress["semaines_12"] == (11.0, 12.0)


def test_seven_days_in_a_row(cards, table):
    week = [facts(ts(2026, 2, 1 + i)) for i in range(7)]
    assert run(cards, table, *week).has("jours_7")
    twice_a_day = week[:6] + [facts(ts(2026, 2, 6, 7))]     # deux séances le 6, rien le 7
    assert not run(cards, table, *twice_a_day).has("jours_7")


def test_anniversary(cards, table):
    first = facts(ts(2025, 11, 7))
    assert run(cards, table, first, facts(ts(2026, 11, 7))).has("premiere_annee")
    col = run(cards, table, first, facts(ts(2026, 11, 6)), now=ts(2026, 11, 6, 20))
    assert not col.has("premiere_annee")
    assert col.progress["premiere_annee"] == (364.0, 365.0)


def test_game_modes(cards, table):
    col = run(cards, table,
              facts(ts(2026, 4, 1), events=[{"kind": "ftp_test", "ftp_w": 250}]),
              facts(ts(2026, 4, 2), events=[{"kind": "survivor_summary", "place": 2, "of": 5}]),
              facts(ts(2026, 4, 3), events=[{"kind": "wtf_summary", "points": 3}]),
              facts(ts(2026, 4, 4), events=[{"kind": "rogue_run", "minutes": 20, "bosses": []}]),
              facts(ts(2026, 4, 5), events=[{"kind": "jersey", "jersey": "sprint"}]))
    assert {"ftp_premier", "wtf_premiere", "rogue_premiere", "sprint_first"} <= {e.card.id for e in col.earned}
    assert not col.has("survivant") and not col.has("ftp_4") and not col.has("rogue_boss_first")
    won = run(cards, table, facts(ts(2026, 4, 2), events=[{"kind": "survivor_summary", "place": 1}]))
    assert won.has("survivant")


# --- anti-triche -------------------------------------------------------------------------------

def write_journal(path: Path, start: float, minutes: float = 30.0, km: float = 120.0,
                  source: str = "live", profile_id: str | None = None) -> Path:
    n = int(minutes * 60)
    with JournalWriter(path, route_id="essai", source=source,
                       profile={"profile_id": profile_id} if profile_id else None) as w:
        w.event("start", start)
        for i in range(1, n + 1):
            w.record(Record(ts=start + i, t=float(i), distance=km * 1000 * i / n, alt=100.0, power=200.0))
        w.event("stop", start + n + 1)
    return path


def test_simulated_never_counts_in_player_profile(tmp_path, cards, table):
    write_journal(tmp_path / "a.jsonl", ts(2026, 10, 31, 6), source="simulated")
    write_journal(tmp_path / "b.jsonl", ts(2026, 11, 2, 6), source="replay")
    player = evaluate(recompute(tmp_path, table), cards, table, tz=UTC, now=NOW)
    assert player.earned == [] and player.sessions == 0
    trial = evaluate(recompute(tmp_path, table, counted=("live", "simulated")), cards, table, tz=UTC, now=NOW)
    assert trial.has("km_100") and trial.has("halloween", 2026) and trial.has("leve_tot")
    assert not any(e.journal == "b.jsonl" for e in trial.earned), "un rejeu ne compte jamais"


def test_short_session_and_other_profile_and_resume_twin(tmp_path, cards, table):
    write_journal(tmp_path / "court.jsonl", ts(2026, 3, 1), minutes=4)
    write_journal(tmp_path / "autre.jsonl", ts(2026, 3, 2), profile_id="_essai")
    write_journal(tmp_path / "x.jsonl", ts(2026, 3, 3), minutes=6, km=60)
    write_journal(tmp_path / "x_reprise-1.jsonl", ts(2026, 3, 3), minutes=6, km=60)
    col = evaluate(recompute(tmp_path, table), cards, table, tz=UTC, now=NOW)
    assert col.sessions == 1 and not col.has("km_100"), "60 km comptés une seule fois"


def test_future_sessions_ignored(cards, table):
    col = run(cards, table, facts(ts(2026, 3, 1), km=60), facts(ts(2031, 12, 25), km=60), now=ts(2026, 3, 2))
    assert col.ignored_future == 1 and col.sessions == 1
    assert not col.has("km_100") and not col.has("noel")


# --- cartes vues et annonce --------------------------------------------------------------------

def test_announcement_one_card_at_a_time(tmp_path, cards, table):
    col = run(cards, table, *[facts(ts(2026, 3, 1) + i * 86400, km=101, minutes=200) for i in range(3)])
    first = announcement(col, None)
    assert first.first_time and first.card is not None
    assert first.card.card.rarity == "epique" and first.others == len(col.earned) - 1
    path = seen_path(tmp_path)
    assert load_seen(path) is None
    save_seen(path, [e.key for e in col.earned])
    assert load_seen(path) == {e.key for e in col.earned}
    assert announcement(col, load_seen(path)) == type(first)(None, 0, False)

    more = run(cards, table, *[facts(ts(2026, 3, 1) + i * 86400, km=101, minutes=200) for i in range(3)],
               facts(ts(2026, 10, 30, 6)))
    ann = announcement(more, load_seen(path))
    assert not ann.first_time and ann.card is not None
    fresh = [e.key for e in new_cards(more, load_seen(path))]
    assert set(fresh) == {"halloween:2026", "leve_tot"} and ann.others == 1
    assert ann.card.key == "halloween:2026", "la plus rare des nouvelles"


def test_seen_file_damaged_announces_nothing(tmp_path, cards, table):
    col = run(cards, table, facts(ts(2026, 3, 1)))
    path = seen_path(tmp_path)
    for bad in ("{pas du json", json.dumps({"version": 99, "seen": []}), json.dumps([1, 2])):
        path.write_text(bad, encoding="utf-8")
        assert announcement(col, load_seen(path)).card is None
    assert col.earned, "la collection reste entière"


def test_empty_collection_first_time(cards, table):
    ann = announcement(run(cards, table), None)
    assert ann.card is None and ann.first_time


def test_card_line(cards, table):
    col = run(cards, table, facts(ts(2026, 12, 24)))
    line = card_line(next(e for e in col.earned if e.card.id == "noel"), UTC)
    assert line["key"] == "noel:2026" and line["date"] == "2026-12-24" and line["visual"] == "traineau"


# --- commande -----------------------------------------------------------------------------------

def test_cli_json(tmp_path):
    d = tmp_path / "journal"
    d.mkdir()
    write_journal(d / "a.jsonl", ts(2026, 3, 1, 6))
    write_journal(d / "b.jsonl", ts(2026, 3, 2), source="simulated")
    env = {"HOME": str(tmp_path), "TZ": "UTC", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    out = subprocess.run([sys.executable, "-m", "openride_core", "collection", "--dir", str(d), "--json"],
                         capture_output=True, text=True, check=True, env=env)
    data = json.loads(out.stdout)
    assert data["sessions"] == 1
    assert {e["id"] for e in data["earned"]} == {"premiere_seance", "km_100", "leve_tot", "seance_50km", "seance_100km"}
    assert data["announce"]["first_time"] is True and set(data["new"]) == {e["key"] for e in data["earned"]}
    text = subprocess.run([sys.executable, "-m", "openride_core", "collection", "--dir", str(d)],
                          capture_output=True, text=True, check=True, env=env).stdout
    assert "Lève-tôt" in text and "(nouvelle)" in text and "À gagner" in text
    assert not (tmp_path / "OpenRide" / "collection_vue.json").exists(), "la commande n'écrit rien"
