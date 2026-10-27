"""Plans, test de FTP et bibliothèque de parcours depuis le menu : côté core (lot O12, contrat 1.3)."""

import asyncio
import math
from datetime import date
from pathlib import Path

import jsonschema
from test_contract_ipc import assert_valid, make_session, schema
from test_plans import zwo

from openride_core import ipc_lists
from openride_core.catalog import RouteEntry
from openride_core.ftp_test import FtpResult
from openride_core.route_stats import compute_stats
from openride_core.workout import list_workouts

PLAN = ('[plan]\nname = "Essai"\ndays_per_week = 2\n'
        '[[week]]\ndays = [ { day = "jour1", workout = "ss" }, { day = "jour3", workout = "ftp_test:ramp" } ]\n')


def library(tmp_path: Path) -> tuple[Path, Path]:
    w = tmp_path / "Workouts"
    w.mkdir()
    (w / "ss.zwo").write_text(zwo("Sweet spot", 45, 0.9))
    p = tmp_path / "Plans"
    p.mkdir()
    (p / "essai.toml").write_text(PLAN)
    (p / "casse.toml").write_text("pas = du = toml")
    return p, w


def plan_session(tmp_path, monkeypatch, port):
    from openride_core.tools import history

    monkeypatch.setattr(history, "CACHE_PATH", tmp_path / "history-cache.json")
    s, cap = make_session(tmp_path, monkeypatch, port=port)
    s.plans_dir, s.workouts_dir = library(tmp_path)
    s.plan_state_path = tmp_path / "plan_state.toml"
    s.activities_dir = tmp_path / "act"
    s.server.send_error = lambda code, message: cap.frames.append({"type": "error", "v": 1, "code": code,
                                                                     "message": message})
    return s, cap


async def wait_for(cap, typ, count=1):
    for _ in range(200):
        if len(cap.of(typ)) >= count:
            return cap.of(typ)[-1]
        await asyncio.sleep(0.01)
    raise AssertionError(f"pas de message {typ}")


def test_plans_listed_started_and_day_launched(tmp_path, monkeypatch):
    async def scenario():
        s, cap = plan_session(tmp_path, monkeypatch, 5980)
        s._on_command("list_plans", {}, 1)
        msg = await wait_for(cap, "plans")
        assert_valid(msg)
        assert [i["id"] for i in msg["items"]] == ["casse", "essai"] and msg["active"] is None
        assert msg["items"][0]["error"] and not msg["items"][1]["active"]
        s._on_command("start_plan", {"id": "casse", "start_date": None}, 2)
        assert cap.of("error")[-1]["code"] == "plan_invalid"
        s._on_command("start_plan", {"id": "essai", "start_date": "le 3"}, 3)
        assert cap.of("error")[-1]["code"] == "plan_invalid"
        s._on_command("start_plan", {"id": "essai", "start_date": date.today().isoformat()}, 4)
        msg = await wait_for(cap, "plans", 2)
        assert_valid(msg)
        act = msg["active"]
        assert act["id"] == "essai" and act["week"] == 1 and act["plan_day"] == "ss"
        day = act["today"][0]
        assert (day["name"], day["duration_s"], day["done"]) == ("Sweet spot", 2700.0, False)
        assert day["tss"] == 60.8 and act["next"]["workout"] == "ftp_test:ramp"
        assert act["next"]["name"] == "Test de FTP : rampe" and act["next"]["tss"] > 0
        # Séance du jour lancée par `start` avec `plan_day`.
        s._on_command("select_route", {"route_id": "demo"}, 5)
        s._on_command("start", {"plan_day": True}, 6)
        assert s.state.session_state == "RUNNING" and s._workout_id == "ss" and s.state.mode == "ERG"
        assert s._rec.plan == {"id": "essai", "week": 1, "day": "jour1"}
        s._on_command("stop_plan", {}, 7)                      # pendant la séance : refusé
        assert cap.of("error")[-1]["code"] == "busy"
        s._on_command("end_session", {"save": False}, 8)
        s._on_command("stop_plan", {}, 9)
        msg = await wait_for(cap, "plans", 3)
        assert msg["active"] is None and not (tmp_path / "plan_state.toml").exists()
        s._on_command("select_route", {"route_id": "demo"}, 10)
        s._on_command("start", {"plan_day": True}, 11)         # plus de plan : rien ne démarre
        assert cap.of("error")[-1]["code"] == "plan_invalid" and s.state.session_state == "READY"
    asyncio.run(scenario())


def test_ftp_test_from_menu_and_accept(tmp_path, monkeypatch):
    async def scenario():
        s, cap = plan_session(tmp_path, monkeypatch, 5984)
        cfg_path = tmp_path / "config.toml"
        cfg_path.write_text("[rider]\nftp_w = 250  # FTP\n", encoding="utf-8")
        s.config_path = cfg_path
        s._on_command("accept_ftp", {}, 1)
        assert cap.of("error")[-1]["code"] == "ftp_result_missing"
        s._on_command("select_route", {"route_id": "demo"}, 2)
        s._on_command("start", {"ftp_test": "sprint"}, 3)
        assert cap.of("error")[-1]["code"] == "bad_args" and s.state.session_state == "READY"
        s._on_command("start", {"ftp_test": "ramp"}, 4)
        assert s.state.erg["workout_name"] == "Test de FTP : rampe" and s._ramp_watch is not None
        s._on_command("accept_ftp", {}, 5)
        assert cap.of("error")[-1]["code"] == "busy"
        s._on_command("end_session", {"save": False}, 6)
        summary = s.state.summary
        assert summary["ftp_test"] == {"test": "ramp", "ftp_w": None, "previous_ftp_w": 250,
                                       "warnings": ["too_short"], "reliable": False}
        assert not list(jsonschema.Draft202012Validator(schema("state")["properties"]["summary"]).iter_errors(summary))
        s._on_command("accept_ftp", {"force": True}, 7)
        assert cap.of("error")[-1]["code"] == "ftp_result_missing"   # rien à écrire sans FTP calculée
        # Résultat douteux (coupure du trainer) : confirmation demandée, puis écrit avec force.
        s._ftp_result = FtpResult("20min", 262, "", 276, 1200, None, ("trainer_dropout",), 250)
        s._on_command("accept_ftp", {}, 8)
        assert cap.of("error")[-1]["code"] == "ftp_result_doubtful" and "262" not in cfg_path.read_text()
        s._on_command("accept_ftp", {"force": True}, 9)
        msg = await wait_for(cap, "settings")
        assert_valid(msg)
        assert next(i["value"] for i in msg["items"] if i["key"] == "rider.ftp_w") == 262
        assert s.cfg.rider.ftp_w == 262 and s.server.hello_config["ftp_w"] == 262
        assert cfg_path.read_text(encoding="utf-8").startswith("[rider]\nftp_w = 262")
        s._ftp_result = FtpResult("ramp", 640, "", 853, 1500, 700, (), 262)   # hors des bornes de config.toml
        s._on_command("accept_ftp", {}, 10)
        assert cap.of("error")[-1]["code"] == "setting_invalid" and s.cfg.rider.ftp_w == 262
    asyncio.run(scenario())


def test_routes_carry_stats_and_library():
    n = 201
    route = {"n": n, "ds_m": 10.0, "length_m": 2000.0, "alt_m": [500.0 + 0.06 * 10.0 * i for i in range(n)]}
    stats = compute_stats(route)
    entry = RouteEntry("col", "Col", "ready", 2000.0, "open", True, None, stats=stats,
                       library={"description": "Montée régulière.", "region": "Vosges", "tags": ["col"],
                                "credits": "moi"})
    item = ipc_lists.route_entry_to_dict(entry, 250.0)
    st = item["stats"]
    assert st["gain_m"] == 120.0 and st["main_climb"]["gain_m"] == 120.0 and st["difficulty"] == 2
    assert math.isclose(st["duration_s"], ipc_lists.route_stats_to_dict(stats, 250.0)["duration_s"])
    assert item["library"] == {"description": "Montée régulière.", "region": "Vosges", "tags": ["col"]}
    plain = ipc_lists.route_entry_to_dict(RouteEntry("x", "x", "to_compile", None, None, False, None))
    assert "stats" not in plain and "library" not in plain
    msg = ipc_lists.chunk_list_message("routes", 1, [item, plain], False)[0]
    assert_valid(msg)
    # Fiche d'une ancienne version : ignorée, comme dans le catalogue.
    assert "stats" not in ipc_lists.route_entry_to_dict(
        RouteEntry("y", "y", "ready", 1.0, "open", True, None, stats={**stats, "version": 0}))


def test_workouts_unit(tmp_path):
    (tmp_path / "a.zwo").write_text(zwo("Relatif", 10, 0.8))
    (tmp_path / "b.erg").write_text("[COURSE HEADER]\nVERSION = 2\nUNITS = ENGLISH\nDESCRIPTION = x\n"
                                    "MINUTES WATTS\n[END COURSE HEADER]\n[COURSE DATA]\n0.00\t200\n10.00\t200\n"
                                    "[END COURSE DATA]\n", encoding="utf-8")
    items = [ipc_lists.workout_info_to_dict(w, 250.0) for w in list_workouts(tmp_path)]
    assert [(i["id"], i["unit"]) for i in items] == [("a", "ftp"), ("b", "watts")]
    assert items[1]["profile"] == [[600.0, 0.8, 0.8]]       # toujours en fraction de la FTP du core
    assert_valid(ipc_lists.chunk_list_message("workouts", 1, items, False)[0])
