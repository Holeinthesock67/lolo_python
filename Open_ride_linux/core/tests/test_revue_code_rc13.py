"""Revue de code, vague 2, lot RC13 : coach et plans (constats C1-01, C1-02, C1-03, C1-04, C2-02, C6-02, C6-05).

Chaque test échoue sur `main` d'avant la correction et passe après. Journaux fabriqués, FTP fictive de 250 W,
aucune donnée réelle."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import timedelta
from pathlib import Path

from test_coach import FTP, TABLE, TODAY, base_history, ts
from test_contract_ipc import run_steps
from test_menu_o7 import bot_session
from test_plans import START, THU1, TUE1, TWO_WEEKS, lib  # noqa: F401  (fixture)
from test_workout import make_session, run, workouts_dir  # noqa: F401  (fixture)

from openride_core import coach, plans
from openride_core.bots import GhostBot, bots_from_menu, last_ride
from openride_core.coach import Inputs
from openride_core.ftp_test import RESUME_GRACE_S, RampWatch, ramp_workout
from openride_core.physics import PhysicsParams
from openride_core.plans import DoneSession
from openride_core.tools.session_summary import compute_summary, load_session, normalized_power
from openride_core.tools.workouts import estimate_metrics
from openride_core.workout import Block, ErgController, Workout


def journal(folder: Path, name: str, start: float, blocks, draft_every: int = 0, pause=None) -> Path:
    """Journal à 1 Hz : blocs [(durée s, watts)] ; `draft_every` : clé `draft` un relevé sur N (1 = tous, comme
    avec des bots ; 0 = aucun) ; `pause` : (après N relevés, durée s) de pause."""
    folder.mkdir(parents=True, exist_ok=True)
    lines = [{"kind": "header", "version": 1, "route_id": "demo", "workout_id": None, "source": "live"},
             {"kind": "event", "event": "start", "ts": start}]
    t, n = start, 0
    for dur, w in blocks:
        for _ in range(int(dur)):
            if pause and n == pause[0]:
                lines.append({"kind": "event", "event": "pause", "ts": t})
                t += pause[1]
                lines.append({"kind": "event", "event": "resume", "ts": t})
            rec = {"kind": "record", "ts": t, "power": w, "cadence": 90, "speed": 8.0, "distance": float(n * 8),
                   "mode": "SIM"}
            if draft_every and n % draft_every == 0:
                rec["draft"] = 0.12
            lines.append(rec)
            t += 1.0
            n += 1
    lines.append({"kind": "event", "event": "stop", "ts": t})
    path = folder / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    return path


# --- C1-01 : une sortie tranquille avec des bots n'est pas une course --------------------------------------

def _yesterday_facts(tmp_path, blocks, draft_every):
    act = tmp_path / "Activities"
    journal(act / ".journal", "hier", ts(TODAY - timedelta(days=1)), blocks, draft_every)
    (f,) = coach.collect_facts(act, FTP, TODAY, TABLE, tmp_path / "c.json")
    return f


def test_c1_01_group_ride_with_bots_is_not_a_race(tmp_path):
    # « Sortie en groupe avec des bots » du conseil : 40 min à 65 % de la FTP, bots sur tous les relevés.
    f = _yesterday_facts(tmp_path, [(2400, 0.65 * FTP)], draft_every=1)
    assert f.race is None and not f.hard
    r = coach.advise(base_history() + [f], FTP, TODAY, Inputs(), TABLE, [])
    assert r["rule"] != "R1"


def test_c1_01_one_vehicle_shelter_is_not_a_race(tmp_path):
    # Sortie seule, dure, abritée par un véhicule sur quelques relevés seulement : pas de bots, pas de course.
    f = _yesterday_facts(tmp_path, [(300, 150.0), (900, 250.0), (300, 150.0)], draft_every=60)
    assert f.hard and f.race is None


def test_c1_01_hard_race_against_bots_still_counts(tmp_path):
    f = _yesterday_facts(tmp_path, [(300, 150.0), (900, 250.0), (300, 150.0)], draft_every=1)
    assert f.hard and f.race is not None and f.race["kind"] == "bots"
    r = coach.advise(base_history() + [f], FTP, TODAY, Inputs(), TABLE, [])
    assert r["rule"] == "R1"


def test_c1_01_facts_cache_is_recomputed():
    assert coach.FACTS_VERSION >= 3   # faits d'avant la correction (course « bots » trop large) relus


# --- C1-02 : la séance du jour faite n'est pas créditée à la séance manquée d'avant ------------------------

SAME_WORKOUT = """[plan]
name = "Même séance"
days_per_week = 2
[[week]]
days = [ { day = "mardi", workout = "ss" }, { day = "jeudi", workout = "ss" } ]
"""


def test_c1_02_today_done_and_missed_one_stays_late(lib):  # noqa: F811
    pdir, wdir = lib
    (pdir / "meme.toml").write_text(SAME_WORKOUT)
    plan = plans.load_plan("meme", pdir, wdir)
    history = [DoneSession(THU1, "ss", 2700.0)]      # mardi manqué, entraînement roulé jeudi
    res = plans.today(plan, START, history, on=THU1)
    assert [(t["workout"], t["done"]) for t in res["today"]] == [("ss", True)]
    assert [(x["date"], x["catch_up"]) for x in res["late"]] == [(TUE1.isoformat(), True)]
    assert plans.plan_tag(plan, START, "ss", on=THU1)["day"] == "jeudi"   # même séance que le journal
    # Rattrapage seul (vendredi) : toujours crédité à la première séance non faite.
    friday = THU1 + timedelta(days=1)
    res = plans.today(plan, START, history + [DoneSession(friday, "ss", 2700.0)], on=friday)
    assert res["done"] == 2 and res["late"] == []


# --- C1-03 : un test de FTP roulé jusqu'au bout est fait, même pour une FTP sous 180 W -----------------------

def test_c1_03_ftp_test_of_a_weaker_rider_counts_done(lib):  # noqa: F811
    pdir, wdir = lib
    (pdir / "test.toml").write_text(TWO_WEEKS.replace('workout = "endu"', 'workout = "ftp_test:ramp"'))
    plan = plans.load_plan("test", pdir, wdir)
    assert plan.durations_s["ftp_test:ramp"] == 1320.0          # durée affichée inchangée (FTP supposée 250 W)
    # Test complet d'un cycliste à 150 W : 5 min d'échauffement, 6 paliers, 5 min de retour au calme.
    full_150 = 300 + 6 * 60 + 300
    res = plans.today(plan, START, [DoneSession(THU1, "ftp_test:ramp", full_150)], on=THU1)
    assert [(t["workout"], t["done"]) for t in res["today"]] == [("ftp_test:ramp", True)]
    # Échauffement seul, ou paliers trop courts pour un résultat : pas fait.
    for short in (300.0, 300.0 + 200.0):
        res = plans.today(plan, START, [DoneSession(THU1, "ftp_test:ramp", short)], on=THU1)
        assert [t["done"] for t in res["today"]] == [False]


# --- C1-04 : après une pause, la rampe ne s'arrête pas pendant que le cycliste repart -----------------------

def _watch_at(step_w):
    w = ramp_workout()
    erg = ErgController(w, 250.0)
    erg.goto(next(i for i, b in enumerate(w.blocks) if b.start_w == step_w and b.type == "steady"))
    erg.step(3.0)
    return RampWatch(w), erg


def test_c1_04_counters_reset_and_grace_after_resume():
    watch, erg = _watch_at(200)
    for _ in range(30):                                  # 3 s sans pédaler, puis pause de la séance
        assert watch.update(0.1, 0.0, 0.0, erg) is None
    erg.paused = True
    assert watch.update(0.1, 0.0, 0.0, erg) is None
    erg.paused = False
    t = 0.0
    while t < RESUME_GRACE_S + 4.0:                      # on repart de l'arrêt, cadence lue à 30 tr/min
        assert watch.update(0.1, 120.0, 30.0, erg) is None, t
        t += 0.1
    while watch.reason is None and t < 30.0:             # après la grâce : 5 s sous 50 tr/min, fin « cadence »
        watch.update(0.1, 120.0, 30.0, erg)
        t += 0.1
    assert watch.reason == "cadence" and t >= RESUME_GRACE_S + 5.0 - 0.15


def test_c1_04_session_pause_arms_the_ramp_grace(tmp_path, monkeypatch, workouts_dir):  # noqa: F811
    async def scenario():
        s, _driver, errors = make_session(tmp_path, monkeypatch, workouts_dir, port=5980)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s.route.type = "loop"
        s._on_command("select_workout", {"workout_id": "ftp_test:ramp"}, 2)
        s._on_command("start", {}, 3)
        assert not errors and s._ramp_watch is not None
        s.erg.goto(3)                                   # 3e palier
        run(s, 4.0, dt=0.1)
        s._on_command("pause", {}, 4)
        assert s.state.session_state == "PAUSED"
        assert s._ramp_watch._grace_s == RESUME_GRACE_S and s._ramp_watch._low_cadence_s == 0.0
    asyncio.run(scenario())


# --- C2-02 : le fantôme ajouté à la pause n'est pas la séance en cours -------------------------------------

def test_c2_02_last_ride_skips_the_current_journal(tmp_path):
    jdir = tmp_path / "journal"
    old = journal(jdir, "ancienne", ts(TODAY - timedelta(days=3)), [(120, 200.0)])
    os.utime(old, (old.stat().st_atime - 3 * 86400, old.stat().st_mtime - 3 * 86400))
    cur = journal(jdir, "en_cours", ts(TODAY), [(60, 200.0)])
    assert last_ride("demo", jdir) == cur
    assert last_ride("demo", jdir, exclude=cur) == old
    (ghost,) = bots_from_menu([{"kind": "ghost"}], PhysicsParams(), FTP, "demo", jdir, exclude_journal=cur)
    assert isinstance(ghost, GhostBot) and ghost.path == old


def test_c2_02_set_bots_ghost_in_pause_replays_the_previous_ride(tmp_path, monkeypatch):
    async def scenario():
        s, cap = bot_session(tmp_path, monkeypatch, 5984)
        s._on_command("select_route", {"route_id": "demo"}, 1)
        s._on_command("start", {}, 2)
        run_steps(s, 3000)
        s._on_command("end_session", {"save": True}, 3)
        (old,) = sorted(s.journal_dir.glob("*.jsonl"))
        os.utime(old, (old.stat().st_atime - 3 * 86400, old.stat().st_mtime - 3 * 86400))
        s._on_command("select_route", {"route_id": "demo"}, 4)
        s._on_command("start", {}, 5)
        run_steps(s, 1500, t0=1000.0)
        s._on_command("pause", {}, 6)
        s._on_command("set_bots", {"bots": [{"kind": "ghost"}]}, 7)
        assert [b.kind for b in s.bots] == ["ghost"], cap.of("error")
        assert s.bots[0].path.resolve() == old.resolve() != s._rec.path.resolve()
        s._on_command("end_session", {"save": False}, 8)
    asyncio.run(scenario())


# --- C6-02 : les meilleures puissances n'enjambent pas une pause ---------------------------------------------

def test_c6_02_best_power_does_not_span_a_pause(tmp_path):
    # 45 s à 600 W, pause de 10 min, 15 s à 600 W, puis 10 min à 150 W : aucune minute continue à 600 W.
    path = journal(tmp_path, "pause", ts(TODAY), [(45, 600.0), (15, 600.0), (600, 150.0)], pause=(45, 600))
    best = compute_summary(load_session(path), FTP)["best_power_w"]
    assert best["5s"] == 600.0
    assert best["1min"] < 400.0                                   # 600 W avant la correction
    # Trou de relevés sans événement (plantage puis reprise) : même coupure.
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if json.loads(ln).get("event") not in ("pause", "resume")]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    assert compute_summary(load_session(path), FTP)["best_power_w"]["1min"] < 400.0


def test_c6_02_continuous_effort_unchanged(tmp_path):
    path = journal(tmp_path, "suite", ts(TODAY), [(300, 150.0), (60, 400.0), (300, 150.0)])
    assert compute_summary(load_session(path), FTP)["best_power_w"]["1min"] == 400.0


# --- C6-05 : TSS estimé des entraînements courts et intenses ----------------------------------------------

def _abs(type_, dur, w):
    return Block(type_, float(dur), None, None, float(w), float(w))


def test_c6_05_estimated_tss_matches_the_session_formula():
    # 10 × (10 s à 600 W, 50 s à 100 W) entre 10 min d'échauffement et 10 min de retour au calme.
    blocks = [_abs("warmup", 600, 125)]
    for _ in range(10):
        blocks += [_abs("steady", 10, 600), _abs("steady", 50, 100)]
    blocks.append(_abs("cooldown", 600, 100))
    w = Workout("sprints", "Sprints", tuple(blocks), "")
    samples = [b.start_w for b in blocks for _ in range(int(b.duration_s))]
    np_bilan = normalized_power(samples)
    m = estimate_metrics(w, FTP)
    assert abs(m["np_w"] - np_bilan) < 0.5
    tss_bilan = w.duration_s / 3600.0 * (np_bilan / FTP) ** 2 * 100.0
    assert abs(m["tss"] - tss_bilan) < 0.2                          # presque le double avant la correction


def test_c6_05_steady_workout_unchanged():
    w = Workout("endu", "Endurance", (_abs("steady", 3600, 175),), "")
    assert estimate_metrics(w, FTP)["tss"] == round(3600 / 3600 * (175 / FTP) ** 2 * 100, 1)

