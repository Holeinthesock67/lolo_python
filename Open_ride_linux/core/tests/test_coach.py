"""Lot CO1 : séance conseillée calculée sur des historiques fabriqués (aucune donnée personnelle)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from openride_core import coach
from openride_core.coach import Inputs, SessionFacts

FTP = 250.0
TODAY = date(2026, 11, 7)
TABLE = coach.load_table()


def ts(day: date, hour: int = 18) -> float:
    return datetime(day.year, day.month, day.day, hour).timestamp()


def fact(days_ago: int, light=3000.0, intense=0.0, anaerobic=0.0, tss=50.0, hard=False,
         ftp_test=None, best=None, source="live") -> SessionFacts:
    return SessionFacts(ts(TODAY - timedelta(days=days_ago)), light + intense + anaerobic, tss,
                        {"light": light, "intense": intense, "anaerobic": anaerobic}, hard,
                        best or {"5s": None, "1min": None, "5min": None, "20min": None}, ftp_test, source)


def base_history(**kw) -> list[SessionFacts]:
    """Trois mois réguliers d'endurance (CTL ≈ 35), test de FTP il y a 10 jours : rien ne bloque."""
    facts = [fact(d, tss=80.0) for d in range(3, 90, 2)]
    facts.append(fact(10, light=1500, intense=600, tss=40, ftp_test=FTP))
    return facts


def advise(facts, **inputs):
    return coach.advise(facts, FTP, TODAY, Inputs(**inputs), TABLE)


# --- table et zones ---------------------------------------------------------------------------------

def test_table_needs_cover_all_zones_once():
    from openride_core.tools.session_summary import ZONES
    zones = [z for n in coach.NEEDS for z in TABLE["needs"][n]]
    assert sorted(zones) == sorted(name for name, _, _ in ZONES)
    for obj in (*coach.OBJECTIVES, "reprise"):
        t = TABLE["targets"][obj]
        assert sum(t[n] for n in coach.NEEDS) == 100


def write_journal(folder: Path, name: str, start: float, blocks, source="live") -> Path:
    """Journal à 1 Hz : blocs [(durée s, watts)]."""
    folder.mkdir(parents=True, exist_ok=True)
    lines = [{"kind": "header", "version": 1, "route_id": "demo", "workout_id": None, "source": source},
             {"kind": "event", "event": "start", "ts": start}]
    t = start
    for dur, w in blocks:
        for _ in range(int(dur)):
            lines.append({"kind": "record", "ts": t, "power": w, "cadence": 90, "speed": 8.0, "distance": 0.0})
            t += 1.0
    lines.append({"kind": "event", "event": "stop", "ts": t})
    path = folder / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


def test_zone_bounds_and_hard_session(tmp_path):
    # 136 W = 54,4 % (léger), 190 W = 76 % (intense), 301 W = 120,4 % (anaérobie) ; 6 × 15 s à 160 %.
    act = tmp_path / "Activities"
    blocks = [(600, 136.0), (300, 190.0), (60, 301.0)]
    blocks += [x for _ in range(6) for x in ((15, 400.0), (60, 120.0))]
    write_journal(act / ".journal", "a", ts(TODAY - timedelta(days=1)), blocks)
    facts = coach.collect_facts(act, FTP, TODAY, TABLE, tmp_path / "c.json")
    assert len(facts) == 1
    f = facts[0]
    assert f.need_s["anaerobic"] == 60 + 90 and f.need_s["intense"] == 300 and f.hard
    # Seuil exact de la table : 10 min en Z4–Z5 rendent une séance dure, 9 min non.
    write_journal(act / ".journal", "b", ts(TODAY - timedelta(days=2)), [(540, 250.0)])
    write_journal(act / ".journal", "c", ts(TODAY - timedelta(days=3)), [(600, 250.0)])
    by_day = {f.day: f for f in coach.collect_facts(act, FTP, TODAY, TABLE, tmp_path / "c.json")}
    assert not by_day[TODAY - timedelta(days=2)].hard and by_day[TODAY - timedelta(days=3)].hard


def test_replay_excluded_simulated_only_when_counted_and_cache(tmp_path):
    act = tmp_path / "Activities"
    write_journal(act / ".journal", "live", ts(TODAY - timedelta(days=1)), [(600, 150.0)])
    write_journal(act / ".journal", "rejeu", ts(TODAY - timedelta(days=2)), [(600, 150.0)], source="replay")
    write_journal(act / ".journal", "sim", ts(TODAY - timedelta(days=3)), [(600, 150.0)], source="simulated")
    cache = tmp_path / "c.json"
    assert len(coach.collect_facts(act, FTP, TODAY, TABLE, cache, counted_sources=("live",))) == 1
    both = coach.collect_facts(act, FTP, TODAY, TABLE, cache, counted_sources=("live", "simulated"))
    assert len(both) == 2
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert len(data) == 3                                        # les trois fichiers ont leurs faits en cache
    assert coach.collect_facts(act, FTP, TODAY, TABLE, cache, counted_sources=("live",)) == \
        [f for f in both if f.source == "live"]


def test_ftp_test_line_is_read(tmp_path):
    act = tmp_path / "Activities" / ".journal"
    p = write_journal(act, "rampe", ts(TODAY - timedelta(days=5)), [(900, 200.0)])
    lines = p.read_text(encoding="utf-8").splitlines()
    lines.insert(-1, json.dumps({"kind": "ftp_test", "ts": 0, "test": "ramp", "ftp_w": 262}))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    f = coach.collect_facts(tmp_path / "Activities", FTP, TODAY, TABLE, tmp_path / "c.json")[0]
    assert f.ftp_test_w == 262.0


# --- signaux -----------------------------------------------------------------------------------------

def test_ctl_atl_form():
    facts = [fact(d, tss=60.0) for d in range(0, 120)]          # 60 TSS par jour depuis 120 jours
    s = coach.build_signals(facts, FTP, TODAY, TABLE)
    assert s["ctl"] == pytest.approx(60 * (1 - (41 / 42) ** 120), rel=1e-6)
    assert s["atl"] == pytest.approx(60.0, abs=0.01) and s["form"] < 0
    rest = coach.build_signals([fact(d, tss=60.0) for d in range(10, 120)], FTP, TODAY, TABLE)
    assert rest["form"] > 0                                      # dix jours sans rouler : frais


def test_power_profile_needs_recent_ftp_test():
    best = {"5s": 800.0, "1min": 420.0, "5min": 270.0, "20min": 250.0}
    facts = base_history() + [fact(5, best=best)]
    s = coach.build_signals(facts, FTP, TODAY, TABLE)
    assert s["profile"] == {"5s": 3.2, "1min": 1.68, "5min": 1.08, "20min": 1.0}
    assert coach.profile_weak(s, TABLE) == "intense"             # 5 min à 1,08 × pour 1,15 attendu
    old = [f for f in facts if not f.ftp_test_w]
    assert coach.build_signals(old, FTP, TODAY, TABLE)["profile"] is None


# --- règles ------------------------------------------------------------------------------------------

def test_r0_not_enough_sessions():
    r = advise([fact(2), fact(9)])
    assert (r["need"], r["rule"], r["alternatives"]) == ("light", "R0", ["ftp_test"])
    assert "Pas encore assez de séances" in r["reason"] and r["duration_min"] == 45


def test_rg_watch_first_with_notes():
    w = coach.parse_watch("seuil:50:240", TABLE)
    r = advise(base_history(), watch=w, raced_yesterday=True)
    assert (r["need"], r["rule"], r["duration_min"]) == ("intense", "RG", 50)
    assert r["reason"] == "Suggestion de ta montre : Seuil, 50 min." and "couru hier" in r["notes"][0]
    assert r["details"]["watch"] == {"type": "seuil", "duration_min": 50, "target_w": 240.0, "need": "intense"}
    rest = advise([], watch=coach.parse_watch("repos", TABLE))   # même sans historique
    assert (rest["need"], rest["duration_min"], rest["alternatives"]) == ("rest", 0, ["recovery"])
    for text, need in (("fond", "light"), ("recuperation", "recovery"), ("VO2max", "intense"),
                       ("sprint", "anaerobic"), ("anaérobie", "anaerobic")):
        assert advise(base_history(), watch=coach.parse_watch(text, TABLE))["need"] == need
    with pytest.raises(coach.CoachError):
        coach.parse_watch("marathon", TABLE)


def test_r1_race_yesterday_and_very_low_form():
    r = advise(base_history(), raced_yesterday=True, yesterday_tss=95)
    assert (r["need"], r["rule"]) == ("recovery", "R1") and "TSS 95" in r["reason"]
    tired = base_history() + [fact(d, tss=180.0, hard=True) for d in range(0, 6)]
    r = advise(tired)
    assert (r["need"], r["rule"]) == ("recovery", "R1") and r["details"]["form"] < -30


def test_r2_race_in_two_days():
    r = advise(base_history(), next_race=TODAY + timedelta(days=2))
    assert (r["need"], r["rule"]) == ("light", "R2") and "après-demain" in r["reason"]
    assert advise(base_history(), next_race=TODAY + timedelta(days=5))["rule"] != "R2"


def test_r3_two_hard_days():
    facts = base_history() + [fact(1, intense=1500, tss=70, hard=True), fact(2, intense=1500, tss=70, hard=True)]
    r = advise(facts)
    assert (r["need"], r["rule"]) == ("light", "R3") and "hier et avant-hier" in r["reason"]


def test_r4_old_or_missing_ftp_test():
    facts = [f for f in base_history() if not f.ftp_test_w] + [fact(60, ftp_test=FTP)]
    r = advise(facts)
    assert (r["need"], r["rule"]) == ("ftp_test", "R4") and "Ta FTP date du test du" in r["reason"]
    r = advise([f for f in base_history() if not f.ftp_test_w])
    assert r["rule"] == "R4" and "Aucun test de FTP" in r["reason"]


def test_r5_plan_session_today():
    plan = {"plan": "reprise-4-semaines", "name": "Reprise 4 semaines", "week": 2, "workout": "tempo_2x15"}
    r = advise(base_history(), plan_today=plan)
    assert (r["need"], r["rule"], r["need_label"]) == ("plan", "R5", "séance du plan")
    assert r["reason"] == "Séance du plan « Reprise 4 semaines », semaine 2 : tempo_2x15."


def test_r6_biggest_deficit_with_reason():
    r = advise(base_history())                                   # presque tout en léger : retard en intense
    assert (r["need"], r["rule"]) == ("intense", "R6")
    assert "de ton temps en aérobie intense sur 4 semaines (cible 16 %)" in r["reason"]
    assert "forme" in r["reason"] and r["alternatives"] == ["anaerobic"]
    d = r["details"]
    assert d["deficits_pts"]["intense"] == pytest.approx(16 - d["shares_pct"]["intense"], abs=0.1)
    assert d["objective"] == "endurance"


def test_r6_guards_block_intensity():
    hard_yesterday = base_history() + [fact(1, light=2000, intense=300, tss=60, hard=True)]
    r = advise(hard_yesterday)
    assert (r["need"], r["rule"]) == ("light", "R6") and "dernière séance dure hier" in r["reason"]
    week = base_history() + [fact(d, light=2000, intense=300, tss=55, hard=True) for d in (2, 4)]
    r = advise(week)
    assert r["need"] == "light" and "déjà 2 séances dures cette semaine" in r["reason"]
    assert advise(week, objective="courses")["need"] in ("intense", "anaerobic")   # 3 par semaine


def test_r6_balanced_history_gives_endurance():
    facts = [fact(d, light=3400, intense=760, anaerobic=200, tss=80) for d in range(3, 90, 2)]
    facts.append(fact(10, ftp_test=FTP))
    r = advise(facts)                                            # 78 / 17 / 5 % : seul le léger est en retard
    assert (r["need"], r["rule"]) == ("light", "R6") and "aérobie léger sur 4 semaines (cible 80 %)" in r["reason"]
    over = [fact(d, light=3000, intense=800, anaerobic=250, tss=80) for d in range(3, 90, 2)] + [fact(10, ftp_test=FTP)]
    r = advise(over)                                             # trop d'intensité : léger quand même, dit tel quel
    assert r["need"] == "light" and r["rule"] == "R6"


def test_r7_tie_broken_by_power_profile_then_least_recent():
    # Retards voisins en intense et en anaérobie (objectif « courses » : 20 et 8 %).
    def history(best=None):
        facts = [fact(d, light=3000, intense=330, anaerobic=0, tss=80) for d in range(3, 90, 2)]
        facts.append(fact(10, light=800, intense=700, ftp_test=FTP, best=best))   # seule séance intense
        return facts
    base = advise(history(), objective="courses")
    dif = base["details"]["deficits_pts"]
    assert 0 < dif["intense"] - dif["anaerobic"] < 3 and base["rule"] == "R7"
    assert base["need"] == "anaerobic"                           # jamais fait : le moins récent
    assert base["details"]["last_by_need"]["intense"] == (TODAY - timedelta(days=10)).isoformat()
    weak_5min = {"5s": 800.0, "1min": 420.0, "5min": 260.0, "20min": 250.0}
    r = advise(history(weak_5min), objective="courses")
    assert (r["need"], r["rule"]) == ("intense", "R7") and "profil de puissance" in r["reason"]


def test_reprise_targets_when_ctl_low():
    facts = [fact(d, light=1800, intense=0, tss=15) for d in range(3, 28, 4)] + [fact(10, ftp_test=FTP, tss=15)]
    r = advise(facts, objective="courses")
    assert r["details"]["objective"] == "reprise" and r["details"]["targets_pct"]["anaerobic"] == 0


def test_cli_json(tmp_path):
    act = tmp_path / "Activities"
    for d in range(2, 26, 3):
        write_journal(act / ".journal", f"s{d}", ts(TODAY - timedelta(days=d)), [(2400, 150.0)])
    env_home = {"HOME": str(tmp_path)}
    cmd = [sys.executable, "-m", "openride_core", "coach", "--date", TODAY.isoformat(), "--ftp", "250",
           "--dir", str(act), "--json"]
    import os
    out = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, **env_home}, check=True)
    r = json.loads(out.stdout)
    assert r["rule"] == "R4" and r["details"]["sessions_28d"] == 8 and r["details"]["shares_pct"]["light"] == 100.0
    watch = subprocess.run(cmd + ["--montre", "sprint:30"], capture_output=True, text=True,
                           env={**os.environ, **env_home}, check=True)
    assert json.loads(watch.stdout)["need"] == "anaerobic"
    bad = subprocess.run(cmd + ["--montre", "marathon"], capture_output=True, text=True, env={**os.environ, **env_home})
    assert bad.returncode == 1 and "type de suggestion inconnu" in bad.stderr
