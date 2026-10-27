"""Lot N13 : recherche et appairage depuis le menu (contrat IPC révision 1.2), Bluetooth simulé.

Adresses simulées uniquement (`C1:1C:00:00:00:0x`).
"""

from __future__ import annotations

import asyncio
import json
import tomllib
from pathlib import Path

import pytest

from openride_core import pairing
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession
from openride_core.sim_scenarios import MINUS_ADDRESS, PLUS_ADDRESS

READY = {"trainer": {"appear_at": 0.0, "connect_delay_s": 0.05},
         "click": {"appear_at": 0.05, "connect_delay_s": 0.05},
         "hr": {"appear_at": 0.0, "connect_delay_s": 0.05, "tau_s": 1.0}}


async def wait_for(cond, timeout=8.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError("condition jamais remplie")
        await asyncio.sleep(0.02)


def test_scan_identify_then_pair_in_simulated_bluetooth(tmp_path: Path, monkeypatch):
    """Critère 1 : recherche, appui « + », enregistrement ; config.toml contient les appareils simulés."""
    from openride_core.sim_scenarios import SCENARIOS

    monkeypatch.setitem(SCENARIOS, "test_appairage", {**READY, "events": []})
    cfg = Config()
    cfg.drivers.trainer = cfg.drivers.input = cfg.drivers.hr = "sim"
    cfg.drivers.sim_scenario = "test_appairage"
    cfg.ipc.port_state, cfg.ipc.port_commands = 5794, 5795
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("# ma configuration\n[rider]\nftp_w = 210\n", encoding="utf-8")
    sent: list[dict] = []

    async def scenario():
        s = CoreSession(cfg, journal_dir=tmp_path / "journal", routes_root=tmp_path / "routes",
                        config_path=cfg_path)
        task = asyncio.create_task(s.run())
        await wait_for(lambda: s.server._tx_sock is not None)
        raw = s.server.send_raw
        s.server.send_raw = lambda m, max_size=None: (sent.append(m), raw(m, max_size))
        await wait_for(lambda: s.state.input_status == "CONNECTED" and s.state.trainer_status == "CONNECTED")
        s._on_command("scan_devices", {"timeout_s": 1.0}, 1)
        await wait_for(lambda: any(m.get("type") == "scan_results" and m["done"] for m in sent))
        first = [m for m in sent if m.get("type") == "scan_results"]
        assert first[0]["done"] is False and first[0]["request_cmd_id"] == 1
        items = first[-1]["items"]
        roles = {it["role"] for it in items}
        assert {"trainer", "click", "hr_strap"} <= roles, items
        assert not any(it["configured"] for it in items)
        s._on_command("identify_click_plus", {}, 2)
        relayed = len([m for m in sent if m.get("type") == "input"])
        await s.sim.press("+")
        await wait_for(lambda: any(m.get("type") == "scan_results" and m["request_cmd_id"] == 2 for m in sent))
        ident = [m for m in sent if m.get("type") == "scan_results" and m["request_cmd_id"] == 2][-1]
        assert ident["plus_address"] == PLUS_ADDRESS
        await asyncio.sleep(0.3)
        assert len([m for m in sent if m.get("type") == "input"]) == relayed, "appui d'identification relayé au menu"
        trainer = next(it for it in items if it["role"] == "trainer")
        strap = next(it for it in items if it["role"] == "hr_strap")
        s._on_command("pair_devices", {"trainer": trainer["address"], "click_plus": PLUS_ADDRESS,
                                       "click_minus": MINUS_ADDRESS, "hr": strap["address"]}, 3)
        assert all(it["configured"] for it in s._scan_items if it["address"] in
                   {trainer["address"], PLUS_ADDRESS, MINUS_ADDRESS, strap["address"]})
        s.stop_event.set()
        await asyncio.wait_for(task, 10)
        for m in sent:
            if m.get("type") == "scan_results":
                assert len(json.dumps(m, separators=(",", ":")).encode()) <= 1400
    asyncio.run(scenario())
    text = cfg_path.read_text(encoding="utf-8")
    assert text.startswith("# ma configuration")
    d = tomllib.loads(text)
    assert d["drivers"]["click_address"] == PLUS_ADDRESS and d["drivers"]["click_minus_address"] == MINUS_ADDRESS
    assert d["drivers"]["hr_address"] and d["trainer"]["device_name"]


def _session(tmp_path: Path, **kwargs) -> tuple[CoreSession, list[dict]]:
    cfg = Config()
    s = CoreSession(cfg, driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "j",
                    routes_root=tmp_path / "r", **kwargs)
    sent: list[dict] = []
    s.server.send_raw = lambda m, max_size=None: sent.append(m)
    s.server.send_error = lambda code, message: sent.append({"type": "error", "code": code, "message": message})
    return s, sent


def test_busy_during_session_and_bad_pairing(tmp_path: Path):
    s, sent = _session(tmp_path, config_path=tmp_path / "config.toml")
    s.state.session_state = "RUNNING"
    s._on_command("scan_devices", {}, 1)
    assert sent[-1]["type"] == "error" and sent[-1]["code"] == "busy"
    s.state.session_state = "IDLE"
    s._on_command("pair_devices", {"trainer": "pas-une-adresse"}, 2)
    assert sent[-1]["code"] == "pairing_failed" and "mal formée" in sent[-1]["message"]
    assert not (tmp_path / "config.toml").exists()
    s._on_command("pair_devices", {"click_plus": PLUS_ADDRESS, "click_minus": PLUS_ADDRESS}, 3)
    assert sent[-1]["code"] == "pairing_failed"


def test_identify_times_out(tmp_path: Path, monkeypatch):
    s, sent = _session(tmp_path)
    monkeypatch.setattr(pairing, "IDENTIFY_TIMEOUT_S", -1.0)
    s._on_command("identify_click_plus", {}, 4)
    s._drain_inputs()
    assert sent[-1]["type"] == "scan_results" and sent[-1]["plus_address"] is None and sent[-1]["done"]
    assert s._identify is None


def test_scan_items_and_message_limits():
    inv = {"devices": [{"role": "click", "name": "Zwift Click", "address": f"C1:1C:00:00:00:{i:02X}", "rssi": -50 - i}
                       for i in range(20)]
           + [{"role": "trainer", "name": "HomeTrainer avec un nom beaucoup trop long", "address": "c1:1c:00:00:00:a0",
               "rssi": -70}, {"role": "other", "name": "Lampe", "address": "C1:1C:00:00:00:B0", "rssi": -30}],
           "connected": [{"role": "hr_strap", "name": "Ceinture", "address": "C1:1C:00:00:00:C0"}]}
    items = pairing.scan_items(inv, {"C1:1C:00:00:00:A0"})
    assert len(items) == pairing.SCAN_MAX_ITEMS and items[0]["role"] == "trainer"
    assert items[0]["configured"] and len(items[0]["name"]) == pairing.SCAN_NAME_MAX
    assert all(it["role"] != "other" for it in items)
    big = [{**it, "name": "x" * 200} for it in items]
    msg = pairing.scan_results_message(7, big, True)
    assert len(json.dumps(msg, separators=(",", ":")).encode()) <= 1400 and msg["items"]
    with pytest.raises(pairing.PairingError):
        pairing.paired_from_args({"trainer": 12}, items)
    p = pairing.paired_from_args({"trainer": "c1:1c:00:00:00:a0", "hr": None}, items)
    assert p.trainer_address == "C1:1C:00:00:00:A0" and p.trainer_name == items[0]["name"] and p.hr_address == ""


def test_scan_waits_for_bluetooth_busy_with_another_search(tmp_path: Path, monkeypatch):
    """Écran Appareils (26 octobre) : BlueZ « InProgress » pendant la recherche du Click, nouvel essai."""
    s, sent = _session(tmp_path)
    calls: list[float] = []

    async def busy_once(sim, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise RuntimeError("[org.bluez.Error.InProgress] Operation already in progress")
        return {"devices": [{"role": "trainer", "name": "Victory", "address": "C1:1C:00:00:00:01", "rssi": -50}],
                "connected": []}

    monkeypatch.setattr(pairing, "scan_inventory", busy_once)
    asyncio.run(s._scan_devices(5, 1.0))
    assert len(calls) == 2
    assert not any(m.get("type") == "error" for m in sent)
    assert sent[-1]["done"] and [it["role"] for it in sent[-1]["items"]] == ["trainer"]

    async def always_busy(sim, timeout):
        raise RuntimeError("[org.bluez.Error.InProgress] Operation already in progress")

    monkeypatch.setattr(pairing, "scan_inventory", always_busy)
    asyncio.run(s._scan_devices(6, 1.0))
    assert [m["code"] for m in sent if m.get("type") == "error"] == ["scan_failed"]
