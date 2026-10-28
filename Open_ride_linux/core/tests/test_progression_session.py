"""Lot V11 : progression branchée dans la séance du core (contrat IPC révision 1.4)."""

import asyncio
import json
from dataclasses import replace

import pytest

from openride_core import fit_export, garage
from openride_core.config import Config
from openride_core.ipc_lists import route_entry_to_dict
from openride_core.journal import read_journal
from openride_core.mock_driver import MockDriver
from openride_core.catalog import RouteEntry
from openride_core.input_providers import NullProvider
from openride_core.physics import PhysicsParams
from openride_core.profile import DEFAULT_EQUIPPED
from openride_core.progression import FactsCache, load_table, recompute
from openride_core.session import CoreSession

from test_contract_ipc import assert_valid
from test_progression import write_journal

GARAGE_ERRORS = ("item_locked", "not_enough_coins", "avatar_invalid", "busy", "bad_args")


def make(tmp_path, monkeypatch, *, enabled=True, rich=True, port=5990, live=True, min_session_s=None):
    """Session avec dossiers temporaires ; `rich` : historique qui donne niveau 9 et des pièces."""
    monkeypatch.setattr(fit_export, "ACTIVITIES_DIR", tmp_path / "act")
    cfg = Config()
    cfg.progression.enabled = enabled
    cfg.ipc.port_state, cfg.ipc.port_commands = port, port + 1
    jd = tmp_path / "journal"
    jd.mkdir()
    if rich:
        write_journal(jd / "a.jsonl", km=300, climb_m=3000, minutes=300, start_ts=1_000_000.0)
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], journal_dir=jd,
                    routes_root=tmp_path / "routes", profile_path=tmp_path / "profile.json")
    if min_session_s is not None and s.progress_svc.enabled:
        s.progress_svc.table.data["rules"]["min_session_s"] = min_session_s
        s.progress_svc.progress = s.progress_svc._recompute()
    if live:
        s._journal_source = lambda: "live"
    frames = []
    s.server.send_raw = frames.append
    return s, frames


def of(frames, kind):
    """Trames d'un type ; celles du contrat 1.4 sont validées par leur schéma JSON."""
    found = [f for f in frames if f["type"] == kind]
    if kind in ("garage", "progression", "xp_result", "hello_ack", "error"):
        for f in found:
            assert_valid(f)
    return found


def ride(s, seconds, t0=10.0):
    s._on_command("select_route", {}, 1)
    s._on_command("start", {}, 2)
    for i in range(int(seconds * 50)):
        s._step(0.02, t0 + i * 0.02)


# --- démarrage ---------------------------------------------------------------------------------

def test_hello_ack_carries_progression(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch)
    prog = s.server.hello_config["progression"]
    assert prog["level"] > 1 and prog["coins"] > 0 and prog["equipped"] == DEFAULT_EQUIPPED
    assert prog["avatar"]["standing_grade_pct"] == 8 and prog["avatar"]["standing_power_pct"] == 150
    assert prog["xp_next_level"] > prog["xp"] and prog["lives"] == 0
    s.server._handle_message({"type": "hello", "v": 1, "engine_version": "t"})
    assert len(json.dumps(of(frames, "hello_ack")[0])) < 1400


def test_standing_thresholds_come_from_avatar_section(tmp_path, monkeypatch):
    from openride_core.config import from_dict
    cfg = from_dict({"avatar": {"standing_grade_pct": 6, "standing_power_pct": 120}})
    assert (cfg.avatar.standing_grade_pct, cfg.avatar.standing_power_pct) == (6, 120)
    svc = garage.ProgressionService(cfg, tmp_path, None, tmp_path / "profile.json")
    svc.load()
    avatar = svc.progression_dict()["avatar"]
    assert avatar["standing_grade_pct"] == 6 and avatar["standing_power_pct"] == 120
    assert Config().avatar.standing_grade_pct == 8 and Config().avatar.standing_power_pct == 150


def test_progression_off_changes_nothing(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch, enabled=False)
    assert "progression" not in s.server.hello_config
    assert s.physics.p == PhysicsParams.from_config(s.cfg)
    s._on_command("buy", {"item_id": "frame_climber"}, 3)
    s._on_command("list_garage", {}, 4)
    assert [f["code"] for f in of(frames, "error")] == ["bad_args", "bad_args"]
    ride(s, 30)
    s._on_command("end_session", {"save": True}, 5)
    assert not of(frames, "xp_result") and not of(frames, "progression")
    assert "loadout" not in next(read_journal(s._rec.path if s._rec else sorted((tmp_path / "journal").glob("*.jsonl"))[-1]))


def test_broken_table_switches_progression_off(tmp_path, monkeypatch):
    bad = tmp_path / "progression.toml"
    bad.write_text("[levels]\ncount = 'x'\n", encoding="utf-8")
    monkeypatch.setattr(garage, "USER_TABLE_PATH", bad)
    svc = garage.ProgressionService(Config(), tmp_path, table_path=bad, profile_path=tmp_path / "p.json")
    assert svc.enabled is False and svc.progression_dict() is None


# --- Garage -------------------------------------------------------------------------------------

def test_list_garage_states(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch)
    s._on_command("list_garage", {}, 7)
    msgs = of(frames, "garage")
    assert [m["request_cmd_id"] for m in msgs] == [7] * len(msgs) and msgs[0]["part"] == 1
    items = {i["id"]: i for m in msgs for i in m["items"]}
    assert items["frame_allround"]["state"] == "equipped"
    assert items["frame_climber"]["state"] == "buyable" and items["frame_climber"]["price"] == 150
    assert items["frame_aero"]["state"] in ("locked", "buyable")
    assert set(items["frame_climber"]) >= {"id", "slot", "name", "state", "level_required", "price",
                                           "challenge", "mass_delta_kg", "cda_delta_pct", "terrain", "look"}


def test_buy_then_equip_writes_profile_and_replies(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch)
    before = s.progress_svc.balance()
    base = PhysicsParams.from_config(s.cfg)
    s._on_command("equip", {"slot": "frame", "item_id": "frame_climber"}, 3)      # pas encore achetée
    assert of(frames, "error")[-1]["code"] == "item_locked"
    s._on_command("buy", {"item_id": "frame_climber"}, 4)
    reply = of(frames, "progression")[-1]
    assert reply["request_cmd_id"] == 4 and reply["coins"] == before - 150
    assert s.server.hello_config["progression"]["coins"] == before - 150
    s._on_command("equip", {"slot": "frame", "item_id": "frame_climber"}, 5)
    reply = of(frames, "progression")[-1]
    assert reply["equipped"]["frame"] == "frame_climber" and reply["request_cmd_id"] == 5
    saved = json.loads((tmp_path / "profile.json").read_text(encoding="utf-8"))
    assert saved["equipped"]["frame"] == "frame_climber" and saved["purchases"][0]["item_id"] == "frame_climber"
    assert s.physics.p.mass_kg == pytest.approx(base.mass_kg - 1.5)   # vaut pour la séance suivante
    s._on_command("buy", {"item_id": "frame_climber"}, 6)             # déjà possédée
    assert of(frames, "error")[-1]["code"] == "item_locked"


def test_buy_refusals_leave_profile_untouched(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch, rich=False)
    s._on_command("buy", {"item_id": "frame_climber"}, 3)    # niveau 1
    s._on_command("buy", {"item_id": "inconnue"}, 4)
    s._on_command("buy", {}, 5)
    assert [f["code"] for f in of(frames, "error")] == ["item_locked", "item_locked", "bad_args"]
    assert not (tmp_path / "profile.json").exists() and not of(frames, "progression")


def test_not_enough_coins(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch)
    s.progress_svc.profile.purchases.append({"item_id": "wheels_light", "price": s.progress_svc.balance(), "ts": 1})
    s._on_command("buy", {"item_id": "frame_climber"}, 3)
    assert of(frames, "error")[-1]["code"] == "not_enough_coins"


def test_set_avatar(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch)
    avatar = dict(s.server.hello_config["progression"]["avatar"], height="XL", number=42)
    s._on_command("set_avatar", {"avatar": avatar}, 3)
    reply = of(frames, "progression")[-1]
    assert reply["avatar"]["height"] == "XL" and reply["avatar"]["number"] == 42
    assert reply["avatar"]["standing_grade_pct"] == 8     # lus de la configuration, pas modifiables
    s._on_command("set_avatar", {"avatar": dict(avatar, skin=99)}, 4)
    s._on_command("set_avatar", {"avatar": "x"}, 5)
    assert [f["code"] for f in of(frames, "error")] == ["avatar_invalid", "avatar_invalid"]
    assert json.loads((tmp_path / "profile.json").read_text(encoding="utf-8"))["avatar"]["height"] == "XL"


def test_profile_write_failure_changes_nothing(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch)
    monkeypatch.setattr(garage, "save_profile", lambda *a, **k: (_ for _ in ()).throw(OSError("disque plein")))
    before = s.progress_svc.balance()
    s._on_command("buy", {"item_id": "frame_climber"}, 3)
    assert of(frames, "error")[-1]["code"] == "recording_failed"
    assert s.progress_svc.balance() == before and not s.progress_svc.profile.purchases


def test_garage_refused_during_session(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch)
    ride(s, 2)
    for name, args in (("list_garage", {}), ("buy", {"item_id": "frame_climber"}),
                       ("equip", {"slot": "frame", "item_id": "frame_allround"}), ("set_avatar", {"avatar": {}})):
        s._on_command(name, args, 9)
    assert [f["code"] for f in of(frames, "error")] == ["busy"] * 4
    assert not of(frames, "garage") and not of(frames, "progression")


# --- physique et journal ----------------------------------------------------------------------

def _equipped_session(tmp_path, monkeypatch, equipped, port):
    s, _ = make(tmp_path, monkeypatch, port=port)
    if equipped:
        s.progress_svc.profile.purchases += [{"item_id": "frame_aero", "price": 0, "ts": 1},
                                             {"item_id": "wheels_disc", "price": 0, "ts": 1}]
        s.progress_svc.profile.equipped.update(frame="frame_aero", wheels="wheels_disc")
        s._base_params = s._equipped_params()
        s.physics.p = s._base_params
    s._on_command("select_route", {}, 1)
    step = s.physics.step                             # sur le plat : l'aéro l'emporte sur la masse
    s.physics.step = lambda power, grade, *a, **k: step(power, 0.0, *a, **k)
    s._on_command("start", {}, 2)
    return s


def test_equipment_raises_virtual_speed_on_flat(tmp_path, monkeypatch):
    out = {}
    for name, equipped, port in (("base", False, 5992), ("aero", True, 5994)):
        (tmp_path / name).mkdir()
        s = _equipped_session(tmp_path / name, monkeypatch, equipped, port)
        for i in range(15000):                        # 5 min à 200 W : l'aéro compte une fois lancé
            s._step(0.02, 10.0 + i * 0.02)
        out[name] = s.physics.s
    assert out["aero"] > out["base"]


def test_equipment_does_not_change_grade_sent_to_trainer(tmp_path, monkeypatch):
    grades = {}
    for name, equipped, port in (("base", False, 5996), ("aero", True, 5998)):
        (tmp_path / name).mkdir()
        s = _equipped_session(tmp_path / name, monkeypatch, equipped, port)
        seen = []
        for i in range(1500):
            s.physics.s, s.physics.v = i * 0.15, 6.0   # même position et même vitesse à chaque pas
            s._step(0.02, 10.0 + i * 0.02)
            seen.append(round(s._grade_sent, 6))
        grades[name] = seen
    assert grades["aero"] == grades["base"] and any(g != 0 for g in grades["base"])


def test_journal_header_has_loadout_and_ftp(tmp_path, monkeypatch):
    s, _ = make(tmp_path, monkeypatch)
    s.progress_svc.profile.equipped["frame"] = "frame_climber"
    s.progress_svc.profile.purchases.append({"item_id": "frame_climber", "price": 0, "ts": 1})
    ride(s, 3)
    head = next(read_journal(s._rec.path))
    assert head["ftp_w"] == 250.0
    assert head["loadout"] == {"frame": "frame_climber", "wheels": "wheels_standard",
                               "mass_delta_kg": -1.5, "cda_delta_pct": 0.0}
    assert head["source"] == "live"


# --- bilan de fin de séance ---------------------------------------------------------------------

def test_xp_result_after_eligible_session(tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.setattr("openride_core.session.XP_RESULT_PERIOD_S", 0.01)
        s, frames = make(tmp_path, monkeypatch, min_session_s=30)
        level0, coins0 = s.progress_svc.progress.level.level, s.progress_svc.balance()
        ride(s, 40)
        s._on_command("end_session", {"save": True}, 3)
        await asyncio.sleep(0.5)
        results = of(frames, "xp_result")
        assert len(results) == 10                         # répété une fois par seconde, 10 fois au plus
        r = results[0]
        assert r["eligible"] is True and r["reason"] is None and r["total"] > 0
        assert r["level_before"] == level0 and r["level_after"] >= level0
        assert r["coins_gained"] > 0 and r["coins_total"] == coins0 + r["coins_gained"]
        assert r["xp_total"] == s.progress_svc.progress.total_xp
        assert [g["source"] for g in r["gains"]][:1] == ["distance"] or r["gains"]
        assert r["equipment_gain_s"] == 0.0               # équipement de départ : rien de gagné
        assert len(json.dumps(r)) <= 1400 and r["more"] is False
        assert s.server.hello_config["progression"]["xp"] == r["xp_total"]
    asyncio.run(scenario())


def test_xp_result_stops_when_session_leaves_finished(tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.setattr("openride_core.session.XP_RESULT_PERIOD_S", 0.05)
        s, frames = make(tmp_path, monkeypatch, min_session_s=30)
        ride(s, 40)
        s._on_command("end_session", {"save": True}, 3)
        await asyncio.sleep(0.12)
        s._on_command("select_route", {}, 4)              # retour au menu : plus de bilan
        seen = len(of(frames, "xp_result"))
        await asyncio.sleep(0.3)
        assert 1 <= seen == len(of(frames, "xp_result")) < 10
    asyncio.run(scenario())


@pytest.mark.parametrize("seconds, live, reason", [(20, True, "too_short"), (40, False, "simulated")])
def test_xp_result_refused_sessions(tmp_path, monkeypatch, seconds, live, reason):
    async def scenario():
        monkeypatch.setattr("openride_core.session.XP_RESULT_PERIOD_S", 0.01)
        s, frames = make(tmp_path, monkeypatch, min_session_s=30, live=live)
        level, coins = s.progress_svc.progress.level.level, s.progress_svc.balance()
        ride(s, seconds)
        s._on_command("end_session", {"save": True}, 3)
        await asyncio.sleep(0.2)
        r = of(frames, "xp_result")[0]
        assert (r["eligible"], r["reason"], r["gains"], r["total"], r["coins_gained"]) == (False, reason, [], 0, 0)
        assert r["level_before"] == r["level_after"] == level and r["coins_total"] == coins
    asyncio.run(scenario())


def test_xp_result_lists_unlocked_items_and_challenges(tmp_path, monkeypatch):
    async def scenario():
        s, frames = make(tmp_path, monkeypatch, rich=False, min_session_s=30)
        svc = s.progress_svc
        old = svc.progress
        write_journal(tmp_path / "journal" / "big.jsonl", km=1100, climb_m=11000, minutes=600, start_ts=2_000_000.0)
        svc.refresh()
        msg = svc.xp_result("big.jsonl", old)
        assert msg["level_after"] > msg["level_before"] and msg["unlocked"]
        assert all(i in svc.catalogue.items for i in msg["unlocked"])
        assert {c["id"] for c in msg["challenges"]} >= {"km_1000", "climb_10000"}
        assert len(msg["unlocked"]) <= 8 and len(msg["challenges"]) <= 4
    asyncio.run(scenario())


# --- liste des parcours et cache ------------------------------------------------------------------

def test_routes_carry_terrain():
    from openride_core.route_stats import compute_stats

    def entry(length_m, gain_m):
        n = int(length_m / 10) + 1
        route = {"n": n, "ds_m": 10.0, "length_m": length_m,
                 "alt_m": [500.0 + gain_m * i / (n - 1) for i in range(n)]}
        return RouteEntry("r", "R", "ready", length_m, "open", True, None, stats=compute_stats(route))
    assert route_entry_to_dict(entry(20_000, 50))["terrain"] == "flat"
    assert route_entry_to_dict(entry(20_000, 300))["terrain"] == "rolling"
    assert route_entry_to_dict(entry(10_000, 700))["terrain"] == "climb"
    plain = route_entry_to_dict(RouteEntry("x", "x", "to_compile", None, None, False, None))
    assert plain["terrain"] is None


def test_facts_cache_skips_unchanged_journals(tmp_path, monkeypatch):
    import openride_core.progression as prog
    table = load_table(None)
    for i in range(3):
        write_journal(tmp_path / f"j{i}.jsonl", km=20, start_ts=1_000_000.0 + i * 10_000)
    cache_path = tmp_path / ".progression.json"
    first = recompute(tmp_path, table, cache=FactsCache(cache_path))
    calls = []
    real = prog.session_facts
    monkeypatch.setattr(prog, "session_facts", lambda *a, **k: calls.append(a[0].name) or real(*a, **k))
    second = recompute(tmp_path, table, cache=FactsCache(cache_path))
    assert calls == [] and second.total_xp == first.total_xp and second.level == first.level
    assert [r.facts for r in second.sessions] == [r.facts for r in first.sessions]
    write_journal(tmp_path / "j1.jsonl", km=40, start_ts=1_000_000.0 + 10_000)    # un journal change
    recompute(tmp_path, table, cache=FactsCache(cache_path))
    assert calls == ["j1.jsonl"]
    cache_path.write_text("pas du json", encoding="utf-8")                          # cache abîmé : tout se relit
    calls.clear()
    assert recompute(tmp_path, table, cache=FactsCache(cache_path)).total_xp > 0 and len(calls) == 3


def test_recompute_500_sessions_under_two_seconds_with_cache(tmp_path):
    import time
    table = load_table(None)
    for i in range(500):
        write_journal(tmp_path / f"s{i:03}.jsonl", km=10, minutes=3, start_ts=1_000_000.0 + i * 10_000)
    cache_path = tmp_path / ".progression.json"
    recompute(tmp_path, table, cache=FactsCache(cache_path))
    t0 = time.perf_counter()
    assert len(recompute(tmp_path, table, cache=FactsCache(cache_path)).sessions) == 500
    assert time.perf_counter() - t0 < 2.0


def test_catalogue_looks_known_to_engine(tmp_path, monkeypatch):
    """Lot V7 : chaque `look` du catalogue livré figure dans equipment_meshes.gd (sinon pièce par défaut)."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "engine" / "scripts" / "equipment_meshes.gd").read_text(encoding="utf-8")
    block = src[src.index("const LOOKS := {"):src.index("const DEFAULT_LOOK")]
    known = {m[0]: set(re.findall(r'"([a-z_]+)"', m[1]))
             for m in re.findall(r'"(\w+)": \[([^\]]*)\]', block)}
    s, _frames = make(tmp_path, monkeypatch)
    items = s.progress_svc.garage_items()
    assert items
    for it in items:
        assert it["look"] in known[it["slot"]], f"look {it['look']!r} ({it['id']}) absent d'equipment_meshes.gd"
