"""Lot RC20 (revue de code, vagues 2 et 5) : un banc de performance ou de recette qui n'a rien mesuré ne passe pas.

O3-01 : `perf_probe watch` n'accepte pas le fichier d'une séance précédente ; O3-02 : budgets sans mesure après
la chauffe = échec quand ils sont demandés ; O3-03 : recette U18 en échec si un banc échoue ou ne mesure rien ;
C7-04 (test_matrice_boutons.py), C7-09 (trainer_steps), C7-10 (recette_v10)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

from openride_core import config
from openride_core.journal import JournalWriter, Record
from openride_core.physics import PhysicsParams
from openride_core.profile import DEFAULT_EQUIPPED
from openride_core.tools import recette_v10 as rv
from openride_core.tools import trainer_steps as ts

TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"
sys.path.insert(0, str(TESTS))


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, TESTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


pp = _load("perf_probe")


def rows(n: int, start: float = 0.0, fps: float = 12.0, gpu: float = 45.0, preset: str = "high") -> list[dict]:
    return [{"t_s": start + i, "fps": fps, "frame_p99_ms": 90.0, "gpu_ms": gpu, "frame_max_ms": 120.0,
             "preset": preset} for i in range(n)]


# --- O3-02 ---------------------------------------------------------------------------------------------

def test_budgets_without_a_second_after_warmup_fail():
    """Reproduction de la revue : 19 secondes en high, 12 images/s et 45 ms de GPU, toutes dans la chauffe."""
    checks = pp.budget_checks(rows(19))
    engine = [c for c in checks if "saturé" not in c[1]]
    assert len(engine) == 3 and all(ok is False for ok, _, _ in engine), checks
    assert all("pas de mesure après la chauffe de 20 s" in msg and "0 jugé" in msg for _, _, msg in engine)
    assert pp._budget_verdict({"budgets": checks}, strict=True) == 1


def test_budgets_without_measure_stay_info_under_xvfb():
    checks = pp.budget_checks(rows(19), real_window=False)
    assert all(ok is None for ok, _, _ in checks), checks


def test_missing_fps_column_is_judged_and_fails(tmp_path, capsys):
    src = tmp_path / "moteur.csv"
    src.write_text("t_s;preset;gpu_ms\n" + "".join(f"{i};high;5.0\n" for i in range(60)), encoding="utf-8")
    assert pp.main(["report", str(src), "--out", str(tmp_path / "r"), "--budgets"]) == 1
    assert "pas de mesure après la chauffe" in capsys.readouterr().out


def test_no_budget_line_at_all_fails_when_requested(capsys):
    assert pp._budget_verdict({"budgets": []}, strict=True) == 1
    assert "aucun relevé" in capsys.readouterr().out
    assert pp._budget_verdict({"budgets": []}, strict=False) == 0


def test_hitches_all_in_warmup_fail():
    checks = pp.hitch_checks(rows(25))
    assert any(label == "à-coups : images lentes" and ok is False for ok, label, _ in checks), checks


def test_short_endurance_run_fails():
    checks = pp.endurance_checks(rows(15), real_window=True)
    labels = {label: ok for ok, label, _ in checks}
    assert labels["endurance : images/s"] is False and labels["endurance : saccades"] is False


def test_long_enough_run_still_passes():
    good = rows(80, fps=60.0, gpu=9.0, preset="medium")
    for r in good:
        r["frame_p99_ms"], r["frame_max_ms"] = 18.0, 20.0
    checks = [c for c in pp.budget_checks(good) if "saturé" not in c[1]] + pp.hitch_checks(good)
    assert all(ok is True for ok, _, _ in checks), checks


# --- O3-01 ---------------------------------------------------------------------------------------------

def test_watch_ignores_the_file_of_a_previous_session(tmp_path, capsys):
    old = tmp_path / "moteur.csv"
    old.write_text("t_s;fps;preset\n" + "".join(f"{i};60;low\n" for i in range(80)), encoding="utf-8")
    day_ago = time.time() - 24 * 3600
    os.utime(old, (day_ago, day_ago))
    code = pp.watch(old, tmp_path / "out", duration_s=None, wait_s=1.0, budgets=True, quality="low")
    out = capsys.readouterr().out
    assert code == 1 and "séance précédente ignoré" in out and "Pas de fichier écrit" in out
    assert not (tmp_path / "out").exists()


def test_fresh_file_is_accepted(tmp_path):
    f = tmp_path / "moteur.csv"
    f.write_text("t_s\n", encoding="utf-8")
    assert pp._fresh(f, time.time() - 5.0)
    assert not pp._fresh(tmp_path / "absent.csv", 0.0)


# --- O3-03 ---------------------------------------------------------------------------------------------

def test_recette_u18_fails_when_every_bench_failed(tmp_path, capsys):
    """Reproduction de la revue : tous les bancs en « Godot introuvable », aucune mesure : plus de « OK »."""
    ru = _load("recette_u18")
    for name in ("low/tour", "low/cote", "medium/tour", "high/tour"):
        (tmp_path / name).mkdir(parents=True)
        (tmp_path / name / "sim_bench.txt").write_text("Godot introuvable\n", encoding="utf-8")
    (tmp_path / ru.CODES_FILE).write_text(json.dumps({"low/tour": 2, "low/cote": 2, "medium/tour": 2,
                                                      "high/tour": 2}), encoding="utf-8")
    assert ru.main(["analyser", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "RÉSULTAT : ÉCHEC" in out
    crit = {c["critere"]: c for c in json.loads((tmp_path / "resume.json").read_text(encoding="utf-8"))["criteres"]}
    assert crit["bancs sim_bench sans erreur"]["ok"] is False and "low/tour (code 2" in \
        crit["bancs sim_bench sans erreur"]["mesure"]
    assert all(c["ok"] is False for k, c in crit.items() if k.startswith("U18 §5.1") or k.startswith("U18 §5.2"))


def test_recette_u18_without_codes_file_still_fails_without_measure(tmp_path, capsys):
    ru = _load("recette_u18")
    assert ru.main(["analyser", str(tmp_path)]) == 1
    assert "bancs sim_bench" not in (tmp_path / "resume.md").read_text(encoding="utf-8")


# --- C7-09 ---------------------------------------------------------------------------------------------

def test_trainer_steps_without_any_compared_step_fails():
    assert ts.model_verdict([])[0] == 1
    code, msg = ts.model_verdict([(None, "palier 1 : pas comparé au modèle (décrochage)")])
    assert code == 1 and "aucun palier comparé" in msg
    assert ts.model_verdict([(True, "palier 1"), (None, "palier 2")]) == (0, "")
    assert ts.model_verdict([(True, "palier 1"), (False, "palier 2")])[0] == 1


# --- C7-10 ---------------------------------------------------------------------------------------------

AERO = {"frame": "frame_tt", "wheels": "wheels_disc"}
BASE = {"frame": DEFAULT_EQUIPPED["frame"], "wheels": DEFAULT_EQUIPPED["wheels"]}


def _block(path, route_id, loadout, speed, gear=12):
    with JournalWriter(path, route_id=route_id, source="live", progression={"loadout": loadout}) as w:
        w.event("start", 1_760_000_000.0)
        for i in range(1, 601):
            w.record(Record(ts=1_760_000_000.0 + i, t=float(i), distance=speed * i, speed=speed, power=200.0,
                            cadence=90.0, grade=0.0, gear=gear, grade_sent=0.0))
        w.event("stop", 1_760_000_601.0)


def test_recette_v10_verdict_is_incomplete_without_the_grade_comparison(tmp_path):
    from openride_core.equipment import apply_equipment, load_catalogue
    from openride_core.progression import load_table

    jdir = tmp_path / "journal"
    _block(jdir / "a.jsonl", "recette-v10-depart", BASE, 9.0, gear=10)
    _block(jdir / "b.jsonl", "recette-v10-equipe", AERO, 9.3, gear=14)   # aucun braquet commun
    plain = PhysicsParams.from_config(config.Config())
    equipped = apply_equipment(plain, AERO, load_catalogue(load_table(None)))
    ok, lines = rv.verdict(rv.last_blocks(jdir), plain, equipped)
    assert not ok and any(line.startswith("INCOMPLET : pente envoyée") for line in lines), lines


def test_recette_v10_verdict_is_incomplete_without_the_time_gain(tmp_path, monkeypatch):
    from openride_core import equipment

    jdir = tmp_path / "journal"
    _block(jdir / "a.jsonl", "recette-v10-depart", BASE, 9.0)
    _block(jdir / "b.jsonl", "recette-v10-equipe", AERO, 9.3)
    monkeypatch.setattr(equipment, "equipment_time_gain", lambda *a, **k: None)
    plain = PhysicsParams.from_config(config.Config())
    ok, lines = rv.verdict(rv.last_blocks(jdir), plain, plain)
    assert not ok and any(line.startswith("INCOMPLET : temps gagné") for line in lines), lines
