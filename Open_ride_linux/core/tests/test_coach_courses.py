"""Lot CO6 : courses disputées dans le conseil (cause de perte S5, course d'hier R1, départage R7,
course annoncée) ; journaux fabriqués, aucune donnée réelle."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from openride_core import coach
from openride_core.coach import Inputs

from test_coach import FTP, TABLE, TODAY, base_history, fact

DAY0 = datetime(2026, 11, 5, 18).timestamp()


def recs(blocks, t0=DAY0, mode="SIM", draft=False):
    """Relevés à 1 Hz : blocs [(durée s, watts, pente %)]."""
    out, t = [], t0
    for dur, w, g in blocks:
        for _ in range(int(dur)):
            r = {"ts": t, "power": w, "grade": g, "mode": mode}
            if draft:
                r["draft"] = 0.1
            out.append(r)
            t += 1.0
    return out


def survivor(records, place, gap_s, at_ts):
    games = [{"kind": "survivor_start", "ts": records[0]["ts"]}]
    if place != 1:
        games.append({"kind": "survivor", "ts": at_ts, "arch": 1, "rider": "me", "place": place, "gap_s": gap_s})
    games.append({"kind": "survivor_summary", "ts": records[-1]["ts"], "place": place, "of": 5})
    return games


# --- cause de perte, une par cas ----------------------------------------------------------------------

def test_dropped_on_a_climb_is_intense():
    r = recs([(600, 220, 1.0), (120, 260, 6.0)])
    race = coach.race_of(r, survivor(r, 5, 8.0, r[-1]["ts"]), TABLE)
    assert race == {"kind": "survivor", "place": 5, "cause": "intense"}


def test_beaten_by_less_than_two_seconds_is_anaerobic():
    r = recs([(720, 230, 0.5)])
    race = coach.race_of(r, survivor(r, 4, 1.2, r[-1]["ts"]), TABLE)
    assert race["cause"] == "anaerobic"


def test_power_fading_is_light():
    r = recs([(300, 260, 0.0), (300, 240, 0.0), (300, 230, 0.0), (300, 200, 0.0)])
    race = coach.race_of(r, survivor(r, 3, 6.0, r[-1]["ts"]), TABLE)
    assert race["cause"] == "light"


def test_no_readable_cause_and_winner():
    r = recs([(1200, 230, 0.5)])
    assert coach.race_of(r, survivor(r, 3, 6.0, r[-1]["ts"]), TABLE)["cause"] is None   # rien d'inventé
    assert coach.race_of(r, survivor(r, 1, None, 0), TABLE) == {"kind": "survivor", "place": 1, "cause": None}


def test_other_journals():
    fading = [(300, 260, 0.0), (300, 240, 0.0), (300, 230, 0.0), (300, 200, 0.0)]
    assert coach.race_of(recs(fading, draft=True), [], TABLE) == {"kind": "bots", "place": None, "cause": "light"}
    assert coach.race_of(recs(fading), [{"kind": "rogue_run", "minutes": 20}], TABLE)["kind"] == "rogue"
    assert coach.race_of(recs(fading), [], TABLE) is None                       # sortie seule
    assert coach.race_of(recs(fading, mode="ERG", draft=True), [], TABLE) is None   # entraînement ERG
    assert coach.race_of(recs([(1200, 230, 0.5)]), [{"kind": "segment", "type": "sprint"}], TABLE) is None


# --- règles -----------------------------------------------------------------------------------------------

def race_fact(days_ago, cause, kind="survivor", tss=70.0):
    f = fact(days_ago, light=2550, intense=390, anaerobic=60, tss=tss)
    return coach.SessionFacts(f.start_ts, f.duration_s, f.tss, f.need_s, f.hard, f.best_w, f.ftp_test_w,
                              f.source, f.workout, {"kind": kind, "place": 3, "cause": cause})


def test_race_yesterday_gives_r1_with_its_tss():
    r = coach.advise(base_history() + [race_fact(1, "intense", tss=95)], FTP, TODAY, Inputs(), TABLE, [])
    assert r["rule"] == "R1" and r["reason"] == "Tu as couru hier (TSS 95) : on récupère aujourd'hui."
    assert r["details"]["races"][0] == {"date": (TODAY - timedelta(days=1)).isoformat(), "kind": "survivor",
                                         "place": 3, "cause": "intense"}


def test_r7_tie_broken_by_race_causes():
    # Parts 85 / 13 / 2 (cible 80 / 16 / 4) : retards de 3 et 2 points, départagés par les courses.
    hist = [fact(d, light=2550, intense=390, anaerobic=60, tss=80) for d in range(3, 90, 2)]
    hist.append(fact(10, light=2550, intense=390, anaerobic=60, tss=40, ftp_test=FTP))
    plain = coach.recommend(coach.build_signals(hist, FTP, TODAY, TABLE), Inputs(), TODAY, TABLE)
    races = [race_fact(4, "anaerobic"), race_fact(8, "anaerobic"), race_fact(12, "intense")]
    sig = coach.build_signals(hist + races, FTP, TODAY, TABLE)
    r = coach.recommend(sig, Inputs(), TODAY, TABLE)
    assert plain["rule"] in ("R6", "R7")
    assert (r["need"], r["rule"]) == ("anaerobic", "R7")
    assert "battu au sprint 2 fois sur tes 3 dernières courses" in r["reason"]
    one = coach.build_signals(hist + races[2:], FTP, TODAY, TABLE)
    assert coach.race_weak(one, TABLE) is None                      # une seule fois : rien ne compte


def test_announced_race_yesterday_and_in_two_days(tmp_path, monkeypatch):
    path = tmp_path / "conseil.json"
    monkeypatch.setattr(coach, "advice_path", lambda: path)
    monkeypatch.setattr(coach, "collect_facts", lambda *a, **k: base_history())
    today = TODAY
    path.write_text(json.dumps({"next_race": {"date": (today - timedelta(days=1)).isoformat(), "kind": "course"}}),
                    encoding="utf-8")
    r = coach.advice_today(today, FTP, "endurance", 60, workouts_dir=tmp_path / "vide")
    assert r["rule"] == "R1" and r["details"]["next_race"] is None
    coach.save_next_race(coach.parse_race((today + timedelta(days=2)).isoformat(), None, today), path)
    assert coach.advice_today(today, FTP, "endurance", 60, workouts_dir=tmp_path / "vide")["rule"] == "R2"


def test_race_read_from_a_journal_and_cache_version(tmp_path):
    act = tmp_path / "Activities" / ".journal"
    act.mkdir(parents=True)
    t0 = datetime.combine(TODAY - timedelta(days=1), datetime.min.time()).timestamp() + 18 * 3600
    r = recs([(600, 220, 1.0), (120, 260, 6.0)], t0)
    lines = [{"kind": "header", "version": 1, "route_id": "demo", "workout_id": None, "source": "live"},
             {"kind": "event", "event": "start", "ts": t0}]
    lines += [{"kind": "record", "t": x["ts"] - t0, "distance": 0.0, "speed": 8.0, "cadence": 90, **x} for x in r]
    lines += survivor(r, 5, 8.0, r[-1]["ts"]) + [{"kind": "event", "event": "stop", "ts": r[-1]["ts"] + 1}]
    (act / "ds.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    cache = tmp_path / "coach.json"
    (f,) = coach.collect_facts(tmp_path / "Activities", FTP, TODAY, TABLE, cache)
    assert f.race == {"kind": "survivor", "place": 5, "cause": "intense"}
    entry = next(iter(json.loads(cache.read_text(encoding="utf-8")).values()))
    assert entry["v"] == coach.FACTS_VERSION
    entry["v"] = 1                                                     # cache d'avant CO6 : relu
    entry["facts"]["race"] = None
    cache.write_text(json.dumps({str((act / "ds.jsonl").resolve()): entry}), encoding="utf-8")
    (again,) = coach.collect_facts(tmp_path / "Activities", FTP, TODAY, TABLE, cache)
    assert again.race["cause"] == "intense"
    assert date.fromtimestamp(again.start_ts) == TODAY - timedelta(days=1)
