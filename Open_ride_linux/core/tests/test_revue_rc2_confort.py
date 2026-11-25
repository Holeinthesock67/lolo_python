"""Constats de confort de la revue de code du 22 novembre, lot S6 (BLE et pilotes), S6-05 à S6-13.
Doublures seulement : aucune adresse ni aucun nom d'appareil réels (préfixes fabriqués)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import stat
import struct
from types import SimpleNamespace

import pytest

from openride_core import ftms, zwift_click
from openride_core.ble_util import short_address
from openride_core.config import BikeConfig, TrainerConfig
from openride_core.ftms_driver import FtmsDriver, _parse_optional
from openride_core.hr_monitor import HeartRateProvider, HrCandidate
from openride_core.input_providers import ClickPair
from openride_core.tools import ble_diag
from openride_core.zwift_click import InputEvent

FAKE = "C0:FF:EE:00:00:"   # préfixe fabriqué


def _ibd(power_w: int, cadence_raw: int) -> bytearray:
    return bytearray(struct.pack("<HHHh", 0x0004 | 0x0040, 3000, cadence_raw, power_w))


def _driver(**trainer):
    now = [100.0]
    return FtmsDriver(TrainerConfig(**trainer), BikeConfig(), clock=lambda: now[0]), now


# --- S6-05 : rien de l'ancienne liaison --------------------------------------------------------

def test_connected_only_after_the_first_measure_frame():
    drv, now = _driver()
    drv._link_up = drv._ever_connected = True
    drv._last_data_at = now[0]           # posé à la connexion
    assert drv.status != "CONNECTED"     # trainer endormi : aucune trame encore
    drv._on_ibd(None, _ibd(180, 170))
    assert drv.status == "CONNECTED"


# --- S6-06 : consigne non finie -----------------------------------------------------------------

def test_nan_targets_keep_the_previous_one():
    drv, _ = _driver()
    drv.set_sim_grade(3.0)
    assert drv.set_sim_grade(math.nan) is False and drv._want.value == 3.0
    drv.power_increment = 5.0
    drv.set_target_power(200)
    assert drv.set_target_power(math.nan) is False and drv._want.value == 200


# --- S6-07 : capacités illisibles ---------------------------------------------------------------

@pytest.mark.parametrize("parser", [ftms.parse_features, ftms.parse_power_range, ftms.parse_resistance_range])
def test_short_optional_characteristic_keeps_the_defaults(parser, caplog):
    assert _parse_optional(parser, b"\x01\x02", "essai") is None
    assert any("illisible" in r.getMessage() for r in caplog.records)


# --- S6-08 : trainer sans SIM -------------------------------------------------------------------

def test_release_without_sim_lowers_the_erg_target():
    drv, now = _driver()
    drv.supports_sim, drv.supports_erg = False, True
    drv.power_range = (25.0, 1000.0)
    sent: list[bytes] = []

    class _Cp:
        async def write(self, payload, **_kw):
            sent.append(bytes(payload))

    async def _call(cp, build):
        await cp.write(build())
    drv._call_retrying = _call
    drv._last_sent, drv._last_sent_at = ("erg", 220.0), -10.0   # cible ERG en cours
    drv.set_sim_grade(0.0)                                       # pause : relâche
    asyncio.run(drv._flush_command(_Cp()))
    assert sent == [ftms.cmd_set_target_power(25.0)]


# --- S6-09 : trames de boutons incohérentes ------------------------------------------------------

def _keypad(mask: int) -> bytes:
    out, v = bytearray(), mask
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            break
    return bytes([zwift_click.MSG_KEYPAD_STATUS, 0x08]) + bytes(out)


def test_incoherent_button_frames_are_ignored():
    plus = zwift_click.KEYPAD_ALL_RELEASED & ~(1 << zwift_click.KEYPAD_PLUS_BIT)
    assert zwift_click.parse_click_buttons(_keypad(plus)).plus_pressed
    assert zwift_click.parse_click_buttons(_keypad(0)) is None            # tous « appuyés »
    assert zwift_click.parse_click_buttons(_keypad(plus)[:-2]) is None    # varint coupé
    assert zwift_click.parse_click_buttons(bytes([zwift_click.MSG_KEYPAD_STATUS])).plus_pressed is False
    assert zwift_click.parse_click_buttons(bytes([zwift_click.MSG_CLICK_NOTIFICATION])) is None


# --- S6-10 : même appui classé deux fois par la paire --------------------------------------------

def test_pair_dedups_two_classifications_of_one_press():
    pair = ClickPair()
    assert pair.first_report(InputEvent.PLUS_SHORT, 10.00)
    assert not pair.first_report(InputEvent.PLUS_UNCLEAR, 10.02)
    assert pair.first_report(InputEvent.MINUS_SHORT, 10.03)   # autre bouton : gardé
    assert pair.first_report(InputEvent.PLUS_SHORT, 11.00)    # appui suivant : gardé


# --- S6-11 : adresses au journal -----------------------------------------------------------------

def test_short_address_keeps_three_bytes():
    assert short_address(FAKE + "18") == "…:00:00:18"
    assert short_address(None) == "?"


def test_heart_rate_devices_listed_once_with_short_addresses(caplog):
    cands = [HrCandidate(name="HRM (sim)", address=FAKE + "0D", rssi=-60)]

    async def scan(_t):
        return cands

    async def scenario():
        hr = HeartRateProvider(device_scanner=scan)
        with caplog.at_level(logging.DEBUG, logger="hr"):
            await hr._pick()
            await hr._pick()
    asyncio.run(scenario())
    lines = [r for r in caplog.records if r.getMessage().startswith("Appareils cardio trouvés")]
    assert [r.levelno for r in lines] == [logging.INFO, logging.DEBUG]
    assert FAKE + "0D" not in lines[0].getMessage() and "…:00:00:0D" in lines[0].getMessage()


# --- S6-12 et S6-13 : openride-ble-diag ----------------------------------------------------------

def test_diag_reports_go_to_a_private_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(ble_diag, "REPORT_DIR", tmp_path / "rapports" / "diag")
    path = ble_diag.save_report("essai", {"x": 1})
    assert path.parent == tmp_path / "rapports" / "diag"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_diag_scan_keeps_only_recognised_devices(tmp_path, monkeypatch):
    monkeypatch.setattr(ble_diag, "REPORT_DIR", tmp_path / "diag")
    adv = lambda uuids, manu: SimpleNamespace(rssi=-50, local_name=None, service_uuids=uuids,  # noqa: E731
                                              manufacturer_data=manu)
    found = {"a": (SimpleNamespace(name="Trainer (sim)", address=FAKE + "01"), adv([ftms.FTMS_SERVICE], {})),
             "b": (SimpleNamespace(name="Voisin", address=FAKE + "02"), adv([], {76: b""}))}

    async def discover(**_kw):
        return found
    monkeypatch.setattr(ble_diag.BleakScanner, "discover", discover)
    reports: list[dict] = []
    monkeypatch.setattr(ble_diag, "save_report", lambda kind, rep: reports.append(rep))
    asyncio.run(ble_diag.cmd_scan(argparse.Namespace(timeout=1.0, all=False)))
    asyncio.run(ble_diag.cmd_scan(argparse.Namespace(timeout=1.0, all=True)))
    assert [d["name"] for d in reports[0]["devices"]] == ["Trainer (sim)"]
    assert len(reports[1]["devices"]) == 2


def test_diag_targets_are_bounded():
    assert ble_diag.bounded(30000, 0.0, 1000.0, "--erg") == 1000.0
    assert ble_diag.bounded(-40, -10.0, 20.0, "--sim-grade") == -10.0
    assert ble_diag.bounded(5, -10.0, 20.0, "--sim-grade") == 5
