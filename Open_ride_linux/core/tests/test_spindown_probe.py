"""Sonde d'étalonnage FTMS (lot ET1) : trames 0x13 et 0x14, et `openride-ble-diag spindown` sur le BLE simulé."""

from __future__ import annotations

import asyncio
import struct

import pytest

from openride_core import ftms
from openride_core.ble_sim import SimClient, SimTrainer, SimWorld
from openride_core.tools.spindown import probe


def test_spin_down_frames():
    assert ftms.cmd_spin_down() == b"\x13\x01" and ftms.cmd_spin_down(False) == b"\x13\x02"
    reply = bytes([0x80, 0x13, 0x01]) + struct.pack("<HH", 2850, 3420)
    assert ftms.parse_spin_down_targets(reply) == (28.5, 34.2)
    assert ftms.parse_spin_down_targets(bytes([0x80, 0x13, 0x02])) is None
    assert ftms.parse_spin_down_status(b"\x14\x04") == "STOP_PEDALING"
    assert ftms.parse_spin_down_status(b"\x08\x00") is None
    assert ftms.parse_training_status(b"\x00\x09") == "SPEED_TOO_LOW"
    assert ftms.parse_cp_offset_features(struct.pack("<I", 1 << 9)) == {
        "offset_compensation": True, "enhanced_offset_compensation": False}


def _run(spin_down, duration_s=5.0):
    said: list[str] = []

    async def go():
        world = SimWorld()
        tr = SimTrainer(world, spin_down=spin_down, spin_down_stop_s=0.2)
        world.trainer = tr
        async with SimClient(tr, tr.address) as client:
            report = await probe(client, duration_s=duration_s, say=said.append)
        return report, tr

    report, tr = asyncio.run(go())
    return report, tr, said


def test_probe_success_gives_steps_and_releases_control():
    report, tr, said = _run("ok")
    assert report["spin_down_announced"] is True and report["verdict"] == "success"
    assert report["target_kmh"] == [30.0, 35.0]
    steps = [e["status"] for e in report["events"] if e["kind"] == "spin_down_status"]
    assert steps == ["SPIN_DOWN_REQUESTED", "STOP_PEDALING", "SUCCESS"]
    assert any("Arrêtez de pédaler" in s for s in said) and any("35 km/h" in s for s in said)
    assert report["commands"][-1]["command"].startswith("reset") and tr.released   # contrôle rendu


def test_probe_error_and_refused():
    assert _run("error")[0]["verdict"] == "error"
    report, tr, said = _run("refuse")
    assert report["verdict"] == "refused" and tr.released
    assert any("sans le faire" in s for s in said)


def test_probe_not_announced_sends_nothing():
    report, tr, said = _run(None)
    assert report["verdict"] == "not_announced" and report["commands"] == [] and tr.commands == []


@pytest.mark.parametrize("key", ["name", "address"])
def test_report_has_no_identity(key):
    report = _run("ok")[0]
    assert key not in report and "5A:1A" not in str(report)
