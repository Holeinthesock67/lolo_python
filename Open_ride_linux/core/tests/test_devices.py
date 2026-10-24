"""Inventaire des appareils Bluetooth (lot M3) : `openride-core devices`."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from openride_core import ble_util, ftms, zwift_click
from openride_core.__main__ import main
from openride_core.sim_scenarios import MINUS_ADDRESS, PLUS_ADDRESS
from openride_core.tools import devices
from openride_core.tools.devices import Found, classify

TRAINER = "5A:1A:00:00:00:00"
STRAP = "C0:FF:EE:00:18:0D"


@pytest.fixture(autouse=True)
def no_connection(monkeypatch):
    """Critère 6 : aucune connexion ; construire un client fait échouer le test."""
    import bleak

    class Forbidden:
        def __init__(self, *a, **k):
            raise AssertionError("BleakClient construit pendant `devices`")
    monkeypatch.setattr(bleak, "BleakClient", Forbidden)
    monkeypatch.setattr(ble_util, "default_client_factory", Forbidden)


def write_config(tmp_path, **drivers) -> Path:
    path = tmp_path / "config.toml"
    body = "".join(f'{k} = "{v}"\n' for k, v in drivers.items())
    path.write_text("[drivers]\n" + body, encoding="utf-8")
    return path


def run_cli(capsys, *args) -> tuple[int, str]:
    code = main(["devices", *args])
    return code, capsys.readouterr().out


def test_classify_rules():
    assert classify("HomeTrainer 0000", [ftms.FTMS_SERVICE]) == "trainer"
    assert classify("Zwift Click", []) == "click"
    assert classify("", [zwift_click.ZWIFT_SERVICE]) == "click"
    assert classify("HRM-Pro", [ftms.HR_SERVICE.upper()]) == "hr_strap"
    assert classify("Forerunner 265", [ftms.HR_SERVICE]) == "hr_watch"
    assert classify("Enceinte", []) == "other"


def test_demo_scenario_inventory(tmp_path, capsys):
    cfg = write_config(tmp_path)
    code, out = run_cli(capsys, "--sim-scenario", "demo", "--timeout", "1.0", "--json",
                        "--config", str(cfg))
    assert code == 0
    r = json.loads(out)
    roles = {(d["role"], d["address"]) for d in r["devices"]}
    assert roles == {("trainer", TRAINER), ("click", PLUS_ADDRESS), ("click", MINUS_ADDRESS),
                     ("hr_strap", STRAP)}
    p = r["proposed"]
    assert p["trainer_address"] == TRAINER and p["hr_address"] == STRAP
    assert {p["click_address"], p["click_other_address"]} == {PLUS_ADDRESS, MINUS_ADDRESS}
    code, text = run_cli(capsys, "--sim-scenario", "demo", "--timeout", "1.0", "--config", str(cfg))
    assert "[drivers]" in text
    for addr in (TRAINER, PLUS_ADDRESS, MINUS_ADDRESS, STRAP):
        assert addr in text
    assert f'trainer_address = "{TRAINER}"' in text and f'hr_address = "{STRAP}"' in text


def _fake(found, linked=()):
    async def scan(timeout):
        return list(found)

    async def connected():
        return list(linked)
    return scan, connected


def test_watch_and_strap(tmp_path, capsys):
    scan, conn = _fake([Found("Forerunner 265", "AA:00:00:00:00:01", -40, [ftms.HR_SERVICE]),
                        Found("HRM-Dual:12", "AA:00:00:00:00:02", -85, [ftms.HR_SERVICE])])
    code = devices.run(1.0, True, tmp_path / "absent.toml", scanner=scan, connected=conn)
    r = json.loads(capsys.readouterr().out)
    assert code == 0
    assert {d["address"]: d["role"] for d in r["devices"]} == {
        "AA:00:00:00:00:01": "hr_watch", "AA:00:00:00:00:02": "hr_strap"}
    assert r["proposed"]["hr_address"] == "AA:00:00:00:00:02"


def test_configured_but_absent(tmp_path, capsys):
    cfg = write_config(tmp_path, trainer_address="11:22:33:44:55:66")
    scan, conn = _fake([Found("HomeTrainer 0000", TRAINER, -60, [ftms.FTMS_SERVICE])])
    devices.run(1.0, False, cfg, scanner=scan, connected=conn)
    out = capsys.readouterr().out
    assert "trainer_address = 11:22:33:44:55:66 : configuré mais absent" in out
    assert f"trainer_address = {TRAINER} : présent mais non configuré" in out


def test_connected_but_silent_devices(tmp_path, capsys):
    scan, conn = _fake([], [Found("HomeTrainer 0000", TRAINER, None, [ftms.FTMS_SERVICE]),
                            Found("Zwift Click", PLUS_ADDRESS, None, [])])
    devices.run(1.0, False, tmp_path / "absent.toml", scanner=scan, connected=conn)
    out = capsys.readouterr().out
    assert "Connectés à BlueZ mais muets" in out and "openride-core release-trainer" in out
    assert f'trainer_address = "{TRAINER}"' in out   # proposé même muet


def test_other_devices_only_with_all(tmp_path, capsys):
    scan, conn = _fake([Found("Enceinte", "BB:00:00:00:00:01", -50, [])])
    devices.run(1.0, True, tmp_path / "absent.toml", scanner=scan, connected=conn)
    assert json.loads(capsys.readouterr().out)["devices"] == []
    devices.run(1.0, True, tmp_path / "absent.toml", show_all=True, scanner=scan, connected=conn)
    assert json.loads(capsys.readouterr().out)["devices"][0]["role"] == "other"


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source", "timeout_s", "devices", "connected", "proposed", "differences"],
    "properties": {
        "source": {"enum": ["ble", "sim"]},
        "timeout_s": {"type": "number"},
        "devices": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["role", "name", "address", "rssi", "services"],
            "properties": {"role": {"enum": list(devices.ROLES)}, "name": {"type": "string"},
                           "address": {"type": "string"},
                           "rssi": {"type": ["integer", "null"]},
                           "services": {"type": "array", "items": {"type": "string"}}}}},
        "connected": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["role", "name", "address", "advice"],
            "properties": {"role": {"enum": list(devices.ROLES)}, "name": {"type": "string"},
                           "address": {"type": "string"}, "advice": {"type": "string"}}}},
        "proposed": {
            "type": "object", "additionalProperties": False,
            "required": ["trainer_address", "click_address", "hr_address", "click_other_address"],
            "properties": {k: {"type": ["string", "null"]} for k in
                           ("trainer_address", "click_address", "hr_address", "click_other_address")}},
        "differences": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["key", "address", "issue"],
            "properties": {"key": {"enum": list(devices.CONFIG_KEYS)}, "address": {"type": "string"},
                           "issue": {"enum": ["configured_absent", "present_not_configured"]}}}},
    },
}


def test_json_schema(tmp_path, capsys):
    cfg = write_config(tmp_path, hr_address="00:00:00:00:00:00")
    scan, conn = _fake([Found("HomeTrainer 0000", TRAINER, -60, [ftms.FTMS_SERVICE]),
                        Found("Zwift Click", PLUS_ADDRESS, -70, [zwift_click.ZWIFT_SERVICE])],
                       [Found("Polar H10", STRAP, None, [ftms.HR_SERVICE])])
    devices.run(1.0, True, cfg, scanner=scan, connected=conn)
    r = json.loads(capsys.readouterr().out)
    jsonschema.validate(r, SCHEMA)
    assert r["differences"] and r["connected"]


def test_bad_scenario_is_a_clear_error(tmp_path, capsys):
    code = main(["devices", "--sim-scenario", "inexistant", "--config", str(tmp_path / "x.toml")])
    assert code == 1
    assert "scénario de simulation refusé" in capsys.readouterr().err
