"""Plan maison composé dans le menu (lot O30) : plans.create_from_library et commande IPC `create_plan`."""

import asyncio

import pytest
from test_contract_ipc import assert_valid
from test_menu_o12 import plan_session, wait_for
from test_plans import lib  # noqa: F401  (fixture)

from openride_core import plans


def test_sequence_fills_days_in_week_order(lib):  # noqa: F811
    pdir, wdir = lib
    plan = plans.create_from_library(["ss", "endu", "ftp_test:ramp"], ["samedi", "mardi"], plans_dir=pdir,
                                     workouts_dir=wdir)
    assert (plan.id, plan.name, plan.days_per_week) == ("mon-plan", "Mon plan", 2)
    assert [(d.week, d.day, d.workout) for d in plan.days] == [
        (1, "mardi", "ss"), (1, "samedi", "endu"), (2, "mardi", "ftp_test:ramp")]
    assert "Composé dans le menu" in (pdir / "mon-plan.toml").read_text(encoding="utf-8")


def test_weeks_repeat_the_sequence_and_names_follow(lib):  # noqa: F811
    pdir, wdir = lib
    plans.create_from_library(["ss"], ["lundi"], plans_dir=pdir, workouts_dir=wdir)
    assert plans.home_plan_name(pdir) == "Mon plan 2"
    plan = plans.create_from_library(["ss", "recup"], ["lundi", "jeudi"], 3, plans_dir=pdir, workouts_dir=wdir)
    assert plan.id == "mon-plan-2" and len(plan.days) == 6
    assert [d.workout for d in plan.days] == ["ss", "recup"] * 3
    assert {d.week for d in plan.days} == {1, 2, 3}


@pytest.mark.parametrize("workouts, days, weeks, error", [
    ([], ["lundi"], None, "entraînements"),
    (["ss"] * 43, ["lundi"], None, "entraînements"),
    (["ss"], [], None, "jours"),
    (["ss"], ["lundi", "lundi"], None, "jours"),
    (["ss"], ["jour1"], None, "jours"),
    (["absent"], ["lundi"], None, "absent"),
    (["casse"], ["lundi"], None, "casse"),
    (["ss", "endu", "recup"], ["lundi"], 2, "durée : de 3 à 12"),
    (["ss"], ["lundi"], 13, "durée"),
    ([3], ["lundi"], None, "identifiant"),
])
def test_refusals_write_nothing(lib, workouts, days, weeks, error):  # noqa: F811
    pdir, wdir = lib
    with pytest.raises(plans.PlanError, match=error):
        plans.create_from_library(workouts, days, weeks, plans_dir=pdir, workouts_dir=wdir)
    assert not list(pdir.iterdir())


def test_existing_name_is_refused(lib):  # noqa: F811
    pdir, wdir = lib
    plans.create_from_library(["ss"], ["lundi"], name="Hiver", plans_dir=pdir, workouts_dir=wdir)
    with pytest.raises(plans.PlanError, match="existe déjà"):
        plans.create_from_library(["endu"], ["mardi"], name="Hiver", plans_dir=pdir, workouts_dir=wdir)


def test_create_plan_command(tmp_path, monkeypatch):
    async def scenario():
        s, cap = plan_session(tmp_path, monkeypatch, 5984)
        s._on_command("create_plan", {"workouts": ["ss", "ftp_test:ramp"], "days": ["mardi", "jeudi"],
                                      "weeks": None, "name": None}, 1)
        msg = await wait_for(cap, "plans")
        assert_valid(msg)
        assert msg["created"] == {"id": "mon-plan", "name": "Mon plan"}
        assert "mon-plan" in [i["id"] for i in msg["items"]] and msg["active"] is None   # pas démarré
        s._on_command("create_plan", {"workouts": "ss", "days": ["mardi"], "weeks": None}, 2)
        assert cap.of("error")[-1]["code"] == "plan_invalid"
        s._on_command("create_plan", {"workouts": ["ss"], "days": ["mardi"], "weeks": True}, 3)
        assert cap.of("error")[-1]["code"] == "plan_invalid"
        s._on_command("list_plans", {}, 4)
        msg = await wait_for(cap, "plans", 2)
        assert "created" not in msg
        s.state.session_state = "RUNNING"
        s._on_command("create_plan", {"workouts": ["ss"], "days": ["mardi"], "weeks": None}, 5)
        assert cap.of("error")[-1]["code"] == "busy"

    asyncio.run(scenario())
