"""Lot O11 : plans d'entraînement sur plusieurs semaines (`plans.py`, `openride-core plan`)."""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from openride_core import plans
from openride_core.__main__ import main
from openride_core.journal import JournalWriter, Record, read_journal
from openride_core.plans import DoneSession, PlanError
from openride_core.tools.workouts import estimate_metrics
from openride_core.workout import load_workout, workout_path

BUILTIN = Path(__file__).resolve().parents[1] / "workouts"


def zwo(name: str, minutes: float = 30, power: float = 0.7) -> str:
    return (f'<workout_file><name>{name}</name><workout>'
            f'<SteadyState Duration="{int(minutes * 60)}" Power="{power}"/></workout></workout_file>')


@pytest.fixture
def lib(tmp_path):
    """Bibliothèque : trois entraînements de 30, 45 et 60 min ; dossier des plans vide."""
    w = tmp_path / "Workouts"
    w.mkdir()
    (w / "endu.zwo").write_text(zwo("Endurance", 60, 0.65))
    (w / "ss.zwo").write_text(zwo("Sweet spot", 45, 0.9))
    (w / "recup.zwo").write_text(zwo("Récupération", 30, 0.5))
    (w / "casse.zwo").write_text("<pas du xml")
    p = tmp_path / "Plans"
    p.mkdir()
    return p, w


TWO_WEEKS = """[plan]
name = "Deux semaines"
days_per_week = 2
[[week]]
focus = "Base"
days = [ { day = "mardi", workout = "ss" }, { day = "jeudi", workout = "endu" } ]
[[week]]
days = [ { day = "mardi", workout = "ss" }, { day = "samedi", workout = "recup" } ]
"""

START = date(2026, 11, 2)   # lundi
TUE1, THU1, TUE2, SAT2 = date(2026, 11, 3), date(2026, 11, 5), date(2026, 11, 10), date(2026, 11, 14)


def test_load_and_schedule(lib):
    pdir, wdir = lib
    (pdir / "deux.toml").write_text(TWO_WEEKS)
    plan = plans.load_plan("deux", pdir, wdir)
    assert plan.weeks == 2 and len(plan.days) == 4 and plan.focus == ("Base", "")
    assert plan.durations_s == {"ss": 2700.0, "endu": 3600.0, "recup": 1800.0}
    assert [w for _, w in plans.schedule(plan, START)] == [TUE1, THU1, TUE2, SAT2]
    late_start = plans.schedule(plan, date(2026, 11, 4))   # mercredi : mardi de la semaine 1 omis
    assert [w for _, w in late_start] == [THU1, TUE2, SAT2]


def test_today_late_catch_up_and_partial(lib):
    """Critère 2."""
    pdir, wdir = lib
    (pdir / "deux.toml").write_text(TWO_WEEKS)
    plan = plans.load_plan("deux", pdir, wdir)
    history = [
        DoneSession(TUE1, "ss", 2700.0),              # faite le jour même
        DoneSession(date(2026, 11, 6), "endu", 3400), # jeudi rattrapé le vendredi (94 %)
        DoneSession(TUE2, "ss", 1350.0),              # arrêtée à 50 % : pas comptée
        DoneSession(TUE2, "recup", 1800.0),           # pas l'entraînement du jour
    ]
    res = plans.today(plan, START, history, on=TUE2)
    assert res["week"] == 2 and res["total"] == 4 and res["done"] == 2 and res["done_pct"] == 50.0
    assert [(t["workout"], t["done"]) for t in res["today"]] == [("ss", False)]
    assert res["late"] == []
    res = plans.today(plan, START, history, on=date(2026, 11, 12))
    assert [(t["workout"], t["date"], t["catch_up"]) for t in res["late"]] == [("ss", "2026-11-10", True)]
    res = plans.today(plan, START, history, on=date(2026, 11, 20))
    assert [t["catch_up"] for t in res["late"]] == [False, False] and res["finished"]
    res = plans.today(plan, START, history[:1], on=date(2026, 11, 7))
    assert [t["workout"] for t in res["late"]] == ["endu"] and res["next"]["date"] == "2026-11-10"
    assert res["today"] == []


def test_generic_days(lib):
    pdir, wdir = lib
    (pdir / "libre.toml").write_text('[plan]\nname = "Libre"\ndays_per_week = 2\n'
                                     '[[week]]\ndays = [ { day = "jour1", workout = "endu" }, { day = "jour3", workout = "ss" } ]\n'
                                     '[[week]]\ndays = [ { day = "jour2", workout = "recup" } ]\n')
    plan = plans.load_plan("libre", pdir, wdir)
    start = date(2026, 11, 4)
    assert [w for _, w in plans.schedule(plan, start)] == [start, start + timedelta(2), start + timedelta(8)]
    assert plans.today(plan, start, [], on=start + timedelta(8))["week"] == 2


@pytest.mark.parametrize("body, message", [
    (TWO_WEEKS.replace('"endu"', '"absent"'), "entraînement « absent »"),
    (TWO_WEEKS.replace('"endu"', '"casse"'), "entraînement « casse »"),
    (TWO_WEEKS.replace('"jeudi"', '"jeudy"'), "jour 'jeudy' inconnu"),
    (TWO_WEEKS.replace('"jeudi"', '"mardi"'), "mardi cité deux fois"),
    (TWO_WEEKS.replace('"jeudi"', '"jour2"'), "mélangés"),
    (TWO_WEEKS.replace('workout = "endu"', 'workout = "ftp_test:sprint"'), "test de FTP"),
    ("[plan]\nname = \"vide\"\ndays_per_week = 3\n", "aucune semaine"),
    ("pas = du = toml", "TOML invalide"),
])
def test_invalid_plan_listed_and_start_refused(lib, tmp_path, body, message):
    """Critère 3."""
    pdir, wdir = lib
    (pdir / "bad.toml").write_text(body)
    (pdir / "deux.toml").write_text(TWO_WEEKS)
    infos = {i.id: i for i in plans.list_plans(pdir, wdir)}
    assert infos["deux"].error is None and message in infos["bad"].error
    with pytest.raises(PlanError, match="bad.toml"):
        plans.start_plan("bad", START, pdir, wdir, tmp_path / "state.toml")
    assert not (tmp_path / "state.toml").exists()


def test_ftp_test_days_wait_for_o10(lib, monkeypatch):
    pdir, wdir = lib
    monkeypatch.setattr(plans, "ftp_tests_available", lambda: False)
    (pdir / "test.toml").write_text(TWO_WEEKS.replace('workout = "endu"', 'workout = "ftp_test:ramp"'))
    with pytest.raises(PlanError, match="lot O10"):
        plans.load_plan("test", pdir, wdir)


def test_start_stop_state(lib, tmp_path):
    pdir, wdir = lib
    (pdir / "deux.toml").write_text(TWO_WEEKS)
    state = tmp_path / "plan_state.toml"
    st = plans.start_plan("deux", START, pdir, wdir, state)
    assert plans.load_state(state) == st
    assert plans.stop_plan(state) and plans.load_state(state) is None and not plans.stop_plan(state)
    state.write_text("[active]\nplan = 3\n")
    assert plans.load_state(state) is None


def test_import_folder(lib, tmp_path):
    """Critère 4 : 12 .zwo w1d1 à w4d3, ordre naturel, sans écraser la bibliothèque."""
    pdir, wdir = lib
    src = tmp_path / "Plan téléchargé"
    src.mkdir()
    for w in range(1, 5):
        for d in range(1, 4):
            (src / f"w{w}d{d}.zwo").write_text(zwo(f"S{w} J{d}", 20 + w + d))
    (src / "lisez-moi.txt").write_text("x")
    (wdir / "base-ete_w1d1.zwo").write_text(zwo("À moi", 99))   # même nom, autre contenu
    with pytest.raises(PlanError, match="autre contenu"):
        plans.import_folder(src, "Base été", ["mardi", "jeudi", "samedi"], pdir, wdir)
    assert not (pdir / "base-ete.toml").exists() and not (wdir / "base-ete_w1d2.zwo").exists()
    (wdir / "base-ete_w1d1.zwo").unlink()
    plan, copied = plans.import_folder(src, "Base été", ["mardi", "jeudi", "samedi"], pdir, wdir)
    assert plan.id == "base-ete" and plan.weeks == 4 and len(copied) == 12
    assert [(d.week, d.day, d.workout) for d in plan.days[:4]] == [
        (1, "mardi", "base-ete_w1d1"), (1, "jeudi", "base-ete_w1d2"), (1, "samedi", "base-ete_w1d3"),
        (2, "mardi", "base-ete_w2d1")]
    assert plan.days[-1].workout == "base-ete_w4d3"
    assert (wdir / "endu.zwo").read_text() == zwo("Endurance", 60, 0.65)
    with pytest.raises(PlanError, match="existe déjà"):
        plans.import_folder(src, "Base été", ["mardi"], pdir, wdir)


def test_natural_order():
    names = ["semaine 10.zwo", "semaine 9.zwo", "w1d10.zwo", "w1d2.zwo", "W1D1.zwo"]
    assert sorted(names, key=plans.natural_key) == ["semaine 9.zwo", "semaine 10.zwo", "W1D1.zwo", "w1d2.zwo", "w1d10.zwo"]


def test_import_refuses_bad_days(lib, tmp_path):
    pdir, wdir = lib
    for days in ([], ["mardi", "mardi"], ["martedi"]):
        with pytest.raises(PlanError, match="--days"):
            plans.import_folder(tmp_path, "x", days, pdir, wdir)


def test_summary_matches_workouts_list(lib):
    """Critère 5 : durée et TSS par semaine = somme de estimate_metrics des entraînements."""
    pdir, wdir = lib
    (pdir / "deux.toml").write_text(TWO_WEEKS)
    plan = plans.load_plan("deux", pdir, wdir)
    weeks = plans.plan_summary(plan, 250.0, wdir)
    tss = {wid: estimate_metrics(load_workout(workout_path(wdir, wid)), 250.0)["tss"] for wid in ("ss", "endu", "recup")}
    assert weeks[0]["duration_s"] == 6300.0 and weeks[0]["tss"] == pytest.approx(tss["ss"] + tss["endu"], abs=0.11)
    assert weeks[1]["sessions"] == 2 and weeks[1]["tss"] == pytest.approx(tss["ss"] + tss["recup"], abs=0.11)


def test_builtin_plans_are_valid(tmp_path):
    """Critère 6 : les plans de référence s'installent, passent `plan show` et `workouts check`."""
    pdir, wdir = tmp_path / "Plans", tmp_path / "Workouts"
    copied, kept = plans.install_builtin(pdir, wdir)
    assert {"ftp_6_semaines.toml", "reprise_4_semaines.toml"} <= set(copied) and kept == []
    for info in plans.list_plans(pdir, wdir):
        assert info.error is None, info
        assert main(["plan", "show", info.id, "--plans-dir", str(pdir), "--workouts-dir", str(wdir)]) == 0
    from openride_core.tools import workouts as wtools

    for f in sorted(wdir.iterdir()):
        assert wtools.main(["check", str(f)]) == 0
    again, kept = plans.install_builtin(pdir, wdir)
    assert again == [] and "ftp_6_semaines.toml" in kept


# --- journal, historique et ligne de commande --------------------------------------------------

def write_session(directory: Path, start: datetime, workout_id: str | None, seconds: int, plan=None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{start:%Y-%m-%d_%H-%M-%S}.jsonl"
    ts0 = start.timestamp()
    with JournalWriter(path, route_id="demo", workout_id=workout_id, plan=plan) as j:
        j.event("start", ts0)
        for t in range(seconds):
            j.record(Record(ts=ts0 + t, t=float(t), distance=8.0 * t, speed=8.0, power=200.0))
        j.event("stop", ts0 + seconds)
    return path


def test_journal_header_plan_field(tmp_path):
    tag = {"id": "deux", "week": 1, "day": "mardi"}
    path = write_session(tmp_path, datetime(2026, 11, 3, 18), "ss", 5, tag)
    head = next(iter(read_journal(path)))
    assert head["plan"] == tag and head["workout_id"] == "ss"
    old = write_session(tmp_path, datetime(2026, 11, 3, 19), "ss", 5)
    assert "plan" not in next(iter(read_journal(old)))   # sans plan : en-tête inchangé


@pytest.fixture(autouse=True)
def history_cache(tmp_path, monkeypatch):
    """Cache de l'historique dans le dossier temporaire, jamais dans ~/.cache."""
    from openride_core.tools import history

    monkeypatch.setattr(history, "CACHE_PATH", tmp_path / "history-cache.json")


def test_history_reports_workout_and_plan(tmp_path):
    from openride_core.tools.history import compute_history, format_text

    acts = tmp_path / "Activities"
    write_session(acts / ".journal", datetime(2026, 11, 3, 18), "ss", 120, {"id": "deux", "week": 1, "day": "mardi"})
    write_session(acts / ".journal", datetime(2026, 11, 4, 18), None, 60)
    res = compute_history(acts, 250.0, cache_path=tmp_path / "cache.json")
    by_day = {s["date"][:10]: s for s in res["sessions"]}
    assert by_day["2026-11-03"]["workout"] == "ss" and by_day["2026-11-03"]["plan"]["week"] == 1
    assert by_day["2026-11-04"]["workout"] is None and by_day["2026-11-04"]["plan"] is None
    assert "[plan deux, semaine 1, mardi]" in format_text(res)
    done = plans.history_sessions(acts)
    assert sorted((d.day, d.workout_id) for d in done) == [(date(2026, 11, 3), "ss"), (date(2026, 11, 4), None)]


def test_active_tag_for_the_session(lib, tmp_path, monkeypatch):
    pdir, wdir = lib
    (pdir / "deux.toml").write_text(TWO_WEEKS)
    monkeypatch.setattr(plans, "PLANS_DIR", pdir)
    monkeypatch.setattr(plans.config_mod, "WORKOUTS_DIR", wdir)
    monkeypatch.setattr(plans, "STATE_PATH", tmp_path / "state.toml")
    assert plans.active_tag("ss", TUE1) is None   # aucun plan actif
    plans.start_plan("deux", START, pdir, wdir)
    assert plans.active_tag("ss", TUE1) == {"id": "deux", "week": 1, "day": "mardi"}
    assert plans.active_tag("endu", date(2026, 11, 7)) == {"id": "deux", "week": 1, "day": "jeudi"}   # rattrapage
    assert plans.active_tag("endu", date(2026, 11, 9)) is None    # plus de 3 jours après
    assert plans.active_tag("recup", TUE1) is None and plans.active_tag(None, TUE1) is None
    (pdir / "deux.toml").write_text("abîmé = = =")
    assert plans.active_tag("ss", TUE1) is None   # plan abîmé : la séance démarre quand même


def test_cli_today_with_history(lib, tmp_path, capsys):
    pdir, wdir = lib
    (pdir / "deux.toml").write_text(TWO_WEEKS)
    acts = tmp_path / "Activities"
    today_ = date.today()
    start = today_ - timedelta(days=today_.weekday())   # lundi de cette semaine
    common = ["--plans-dir", str(pdir), "--workouts-dir", str(wdir), "--state", str(tmp_path / "s.toml"),
              "--activities-dir", str(acts)]
    assert main(["plan", "today", *common]) == 0
    assert "Aucun plan actif" in capsys.readouterr().out
    assert main(["plan", "start", "deux", "--date", start.isoformat(), *common]) == 0
    assert "actif" in capsys.readouterr().out
    write_session(acts / ".journal", datetime.combine(start + timedelta(days=1), datetime.min.time()).replace(hour=18),
                  "ss", 2700)
    assert main(["plan", "today", "--json", *common]) == 0
    res = json.loads(capsys.readouterr().out)
    assert res["plan"] == "deux" and res["week"] == 1
    if today_ > start + timedelta(days=1):
        assert res["done"] == 1
    assert main(["plan", "list", *common]) == 0
    assert "* deux" in capsys.readouterr().out
    assert main(["plan", "stop", *common]) == 0 and "arrêté" in capsys.readouterr().out
    assert main(["plan", "start", "inconnu", *common]) == 1
    assert "introuvable" in capsys.readouterr().err
    assert main(["plan", "start", "deux", "--date", "hier", *common]) == 1


def test_cli_import(lib, tmp_path, capsys):
    pdir, wdir = lib
    src = tmp_path / "telecharge"
    src.mkdir()
    for i in range(1, 5):
        shutil.copy(wdir / "recup.zwo", src / f"jour{i}.zwo")
    common = ["--plans-dir", str(pdir), "--workouts-dir", str(wdir)]
    assert main(["plan", "import", str(src), "--name", "Essai", "--days", "jour1,jour3", *common]) == 0
    assert "2 semaine(s), 4 séance(s)" in capsys.readouterr().out
    assert main(["plan", "import", str(src), *common]) == 1
    assert "usage" in capsys.readouterr().err
