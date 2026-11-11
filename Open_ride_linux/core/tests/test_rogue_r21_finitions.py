"""Lot R21 : fin du Cyber-Rogue (événement `purge`, achat d'une vie, contrat IPC révision 1.14)."""

from dataclasses import replace

from openride_core import ipc_budget

from openride_core.rogue.combat import CombatInputs, combat_start, combat_step
from openride_core.rogue.rooms import generate_room

from test_progression_session import make, of
from test_contract_ipc import assert_valid, assert_valid_1_4_state
from test_rogue_combat import B, DT, RIDER


def test_purge_during_hack_emits_purge_event_once():
    room = generate_room("saboteur", "", "threshold", 300.0, RIDER, 1)
    purge = next(m for m in room.markers if m.kind == "purge")
    base = dict(power_w=200, cadence_rpm=85, posture="FLUIDE", gear=6, ftp_w=250, v_mps=8)
    st = combat_start(room, 1)
    st, _ = combat_step(replace(st, adrenaline=80.0), CombatInputs(s_m=purge.s_m - 80, **base), room, B, DT)
    assert st.hack_kind is not None
    st, ev = combat_step(st, CombatInputs(s_m=purge.s_m, buttons=frozenset({"Z_SHORT"}), **base), room, B, DT)
    assert "purge" in ev and st.hack_kind is None
    # Z sur la balise sans piratage : pas de purge réussie, pas de son
    st, ev = combat_step(st, CombatInputs(s_m=purge.s_m + 0.1, buttons=frozenset({"Z_SHORT"}), **base), room, B, DT)
    assert "purge" not in ev


def test_purge_event_is_in_the_state_schema():
    d = ipc_budget.worst_rogue_state()
    d["rogue"]["events"] = ["purge", "hit", "crit", "firewall_contact"]
    assert_valid_1_4_state(d)


def test_buy_life_adds_a_life_and_spends_coins(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch)
    svc = s.progress_svc
    price, top = svc.ct.life_price, svc.ct.max_lives
    hello = s.server.hello_config["rogue"]
    assert hello["life_price"] == price and hello["max_lives"] == top and hello["lives"] == 0
    assert_valid({"type": "hello_ack", "v": 1, "core_version": "0", "config": s.server.hello_config})
    before = svc.balance()
    s._on_command("buy_life", {}, 3)
    reply = of(frames, "progression")[-1]
    assert reply["request_cmd_id"] == 3 and reply["lives"] == 1 and reply["coins"] == before - price
    assert s.server.hello_config["rogue"]["lives"] == 1
    assert s.server.hello_config["progression"]["lives"] == 1


def test_buy_life_refused_when_full_or_too_poor(tmp_path, monkeypatch):
    s, frames = make(tmp_path, monkeypatch)
    top = s.progress_svc.ct.max_lives
    s.progress_svc.ct = replace(s.progress_svc.ct, life_price=1)
    for i in range(top):
        s._on_command("buy_life", {}, 10 + i)
    assert of(frames, "progression")[-1]["lives"] == top
    s._on_command("buy_life", {}, 20)
    assert of(frames, "error")[-1]["code"] == "item_locked"
    (tmp_path / "pauvre").mkdir()
    poor, frames2 = make(tmp_path / "pauvre", monkeypatch, rich=False, port=5994)
    poor._on_command("buy_life", {}, 3)
    assert of(frames2, "error")[-1]["code"] == "not_enough_coins"
    assert "progression" not in [f["type"] for f in frames2 if f.get("request_cmd_id") == 3]


def test_buy_life_is_a_valid_command():
    assert_valid({"type": "cmd", "v": 1, "cmd_id": 4, "name": "buy_life", "args": {}})
