"""Tests unitaires de `openride_core.ble_util` sans adaptateur Bluetooth ni bus D-Bus réel (lot H2)."""

from __future__ import annotations

import asyncio
import logging
import sys
import types
from dataclasses import dataclass
from itertools import islice
from typing import Any

import pytest

from openride_core import ble_util


@dataclass
class FakeDevice:
    address: str
    name: str | None = None


@dataclass
class FakeAdv:
    local_name: str | None = None


@dataclass
class FakeVariant:
    value: Any


def install_fake_bleak(monkeypatch: pytest.MonkeyPatch,
                       by_address: dict[str, FakeDevice] | None = None,
                       candidates: list[tuple[FakeDevice, FakeAdv]] | None = None,
                       recorded: dict[str, Any] | None = None) -> None:
    """Remplace `bleak.BleakScanner` (et `BleakClient`) par des doublures."""
    by_address = by_address or {}
    candidates = candidates or []
    recorded = recorded if recorded is not None else {}

    class FakeScanner:
        @staticmethod
        async def find_device_by_address(address: str, timeout: float = 10.0) -> FakeDevice | None:
            recorded["address"] = address
            recorded["timeout"] = timeout
            return by_address.get(address)

        @staticmethod
        async def find_device_by_filter(filterfunc: Any, timeout: float = 10.0) -> FakeDevice | None:
            recorded["timeout"] = timeout
            for dev, adv in candidates:
                if filterfunc(dev, adv):
                    return dev
            return None

    class FakeBleakClient:
        def __init__(self, device: Any, **kwargs: Any) -> None:
            self.device = device
            self.kwargs = kwargs

    fake_mod = types.ModuleType("bleak")
    fake_mod.BleakScanner = FakeScanner          # type: ignore[attr-defined]
    fake_mod.BleakClient = FakeBleakClient       # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "bleak", fake_mod)


def install_fake_dbus(monkeypatch: pytest.MonkeyPatch,
                      objects: dict[str, dict[str, dict[str, FakeVariant]]] | None = None,
                      connect_error: Exception | None = None,
                      introspect_error: Exception | None = None,
                      call_error: Exception | None = None) -> dict[str, Any]:
    """Injecte un faux module `dbus_fast` et `dbus_fast.aio` dans `sys.modules`."""
    state: dict[str, Any] = {"connected": False, "disconnected": 0, "bus_type": None}
    managed = objects or {}

    class BusType:
        SYSTEM = "SYSTEM"

    class FakeInterface:
        async def call_get_managed_objects(self) -> dict[str, Any]:
            if call_error is not None:
                raise call_error
            return managed

    class FakeProxy:
        def get_interface(self, iface_name: str) -> FakeInterface:
            assert iface_name == "org.freedesktop.DBus.ObjectManager"
            return FakeInterface()

    class MessageBus:
        def __init__(self, bus_type: Any = None) -> None:
            state["bus_type"] = bus_type

        async def connect(self) -> "MessageBus":
            if connect_error is not None:
                raise connect_error
            state["connected"] = True
            return self

        async def introspect(self, service: str, path: str) -> str:
            assert service == "org.bluez" and path == "/"
            if introspect_error is not None:
                raise introspect_error
            return "<node/>"

        def get_proxy_object(self, service: str, path: str, intro: str) -> FakeProxy:
            assert service == "org.bluez" and path == "/" and intro == "<node/>"
            return FakeProxy()

        def disconnect(self) -> None:
            state["disconnected"] += 1

    dbus_mod = types.ModuleType("dbus_fast")
    dbus_mod.BusType = BusType                   # type: ignore[attr-defined]
    aio_mod = types.ModuleType("dbus_fast.aio")
    aio_mod.MessageBus = MessageBus              # type: ignore[attr-defined]
    dbus_mod.aio = aio_mod                       # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "dbus_fast", dbus_mod)
    monkeypatch.setitem(sys.modules, "dbus_fast.aio", aio_mod)
    return state


# --- find_device --------------------------------------------------------------------------

def test_find_device_by_address_found(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = FakeDevice(address="F4:C4:59:15:E1:E7", name="Zwift Click")
    recorded: dict[str, Any] = {}
    install_fake_bleak(monkeypatch, by_address={"F4:C4:59:15:E1:E7": expected}, recorded=recorded)

    res = asyncio.run(ble_util.find_device("Click", "F4:C4:59:15:E1:E7", timeout=4.5))
    assert res is expected
    assert recorded["address"] == "F4:C4:59:15:E1:E7"
    assert recorded["timeout"] == 4.5


def test_find_device_by_address_absent_returns_address(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_bleak(monkeypatch, by_address={})

    res = asyncio.run(ble_util.find_device("Click", "F4:C4:59:15:E1:E7", timeout=3.0))
    assert res == "F4:C4:59:15:E1:E7"


def test_find_device_by_name_fragment_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    victory = FakeDevice(address="AA:BB:CC:DD:EE:FF", name="Victory 9908")
    other = FakeDevice(address="11:22:33:44:55:66", name="Autre Capteur")
    install_fake_bleak(monkeypatch, candidates=[(other, FakeAdv()), (victory, FakeAdv())])

    res = asyncio.run(ble_util.find_device("victory", None, timeout=5.0))
    assert res is victory


def test_find_device_by_adv_local_name_when_device_name_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    dev = FakeDevice(address="AA:BB:CC:DD:EE:01", name=None)
    adv = FakeAdv(local_name="Zwift Click V2")
    install_fake_bleak(monkeypatch, candidates=[(dev, adv)])

    res = asyncio.run(ble_util.find_device("click", None, timeout=5.0))
    assert res is dev


def test_find_device_skips_excluded_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    plus = FakeDevice(address="F4:C4:59:1F:E3:6A", name="Zwift Click")
    minus = FakeDevice(address="F4:C4:59:15:E1:E7", name="Zwift Click")
    install_fake_bleak(monkeypatch, candidates=[(plus, FakeAdv()), (minus, FakeAdv())])

    res = asyncio.run(ble_util.find_device("Click", None, timeout=5.0, exclude={"f4:c4:59:1f:e3:6a"}))
    assert res is minus


def test_find_device_bluez_fallback_skips_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_bleak(monkeypatch, candidates=[])
    install_fake_dbus(monkeypatch, objects={
        f"/org/bluez/hci0/dev_{a.replace(':', '_')}": {
            "org.bluez.Device1": {"Name": FakeVariant("Zwift Click"), "Address": FakeVariant(a)}}
        for a in ("F4:C4:59:1F:E3:6A", "F4:C4:59:15:E1:E7")})

    res = asyncio.run(ble_util.find_device("Click", None, timeout=5.0, exclude={"F4:C4:59:1F:E3:6A"}))
    assert res == "F4:C4:59:15:E1:E7"


def test_find_device_falls_back_to_bluez_and_logs_info(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    install_fake_bleak(monkeypatch, candidates=[])
    install_fake_dbus(monkeypatch, objects={
        "/org/bluez/hci0/dev_F4_C4_59_15_E1_E7": {
            "org.bluez.Device1": {
                "Name": FakeVariant("Zwift Click"),
                "Address": FakeVariant("F4:C4:59:15:E1:E7"),
            }
        }
    })

    with caplog.at_level(logging.INFO, logger="ble"):
        res = asyncio.run(ble_util.find_device("Click", None, timeout=5.0))

    assert res == "F4:C4:59:15:E1:E7"
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("non annoncé" in m and "F4:C4:59:15:E1:E7" in m for m in infos)


def test_find_device_returns_none_when_neither_scan_nor_bluez_finds_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_bleak(monkeypatch, candidates=[])
    install_fake_dbus(monkeypatch, objects={})

    res = asyncio.run(ble_util.find_device("Introuvable", None, timeout=2.0))
    assert res is None


def test_find_device_forwards_timeout_to_scanner(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded_filter: dict[str, Any] = {}
    install_fake_bleak(monkeypatch, candidates=[], recorded=recorded_filter)
    install_fake_dbus(monkeypatch, objects={})
    asyncio.run(ble_util.find_device("Victory", None, timeout=7.25))
    assert recorded_filter["timeout"] == 7.25

    recorded_addr: dict[str, Any] = {}
    install_fake_bleak(monkeypatch, by_address={}, recorded=recorded_addr)
    asyncio.run(ble_util.find_device("Victory", "12:34:56:78:9A:BC", timeout=6.5))
    assert recorded_addr["timeout"] == 6.5


# --- known_bluez_address ------------------------------------------------------------------

def test_known_bluez_address_matches_by_alias_only(monkeypatch: pytest.MonkeyPatch) -> None:
    state = install_fake_dbus(monkeypatch, objects={
        "/org/bluez/hci0/dev_AA_BB": {
            "org.bluez.Device1": {
                "Alias": FakeVariant("Mon Victory 9908"),
                "Address": FakeVariant("AA:BB:CC:00:11:22"),
            }
        }
    })

    res = asyncio.run(ble_util.known_bluez_address("victory"))
    assert res == "AA:BB:CC:00:11:22"
    assert state["disconnected"] == 1


def test_known_bluez_address_ignores_objects_without_device1_or_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_dbus(monkeypatch, objects={
        "/org/bluez/hci0": {
            "org.bluez.Adapter1": {"Address": FakeVariant("00:00:00:00:00:00")}
        },
        "/org/bluez/hci0/dev_sans_adresse": {
            "org.bluez.Device1": {"Name": FakeVariant("Victory Sans Adresse")}
        },
        "/org/bluez/hci0/dev_autre": {
            "org.bluez.Device1": {
                "Name": FakeVariant("Autre Appareil"),
                "Address": FakeVariant("11:11:11:11:11:11"),
            }
        },
    })

    res = asyncio.run(ble_util.known_bluez_address("victory"))
    assert res is None


def test_known_bluez_address_when_dbus_fast_missing_or_bus_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Cas 1 : dbus_fast absent (ImportError).
    monkeypatch.setitem(sys.modules, "dbus_fast", None)
    monkeypatch.setitem(sys.modules, "dbus_fast.aio", None)
    with caplog.at_level(logging.DEBUG, logger="ble"):
        res_missing = asyncio.run(ble_util.known_bluez_address("Click"))
    assert res_missing is None
    assert any("Liste BlueZ indisponible" in r.getMessage() and r.levelno == logging.DEBUG
               for r in caplog.records)

    # Cas 2 : erreur lors de la connexion au bus.
    caplog.clear()
    install_fake_dbus(monkeypatch, connect_error=RuntimeError("bus D-Bus refusé"))
    with caplog.at_level(logging.DEBUG, logger="ble"):
        res_err = asyncio.run(ble_util.known_bluez_address("Click"))
    assert res_err is None
    assert any("bus D-Bus refusé" in r.getMessage() and r.levelno == logging.DEBUG
               for r in caplog.records)


def test_known_bluez_address_always_disconnects_bus_on_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    state1 = install_fake_dbus(monkeypatch, introspect_error=RuntimeError("échec introspect"))
    with caplog.at_level(logging.DEBUG, logger="ble"):
        assert asyncio.run(ble_util.known_bluez_address("Click")) is None
    assert state1["disconnected"] == 1

    state2 = install_fake_dbus(monkeypatch, call_error=RuntimeError("échec get_managed_objects"))
    with caplog.at_level(logging.DEBUG, logger="ble"):
        assert asyncio.run(ble_util.known_bluez_address("Click")) is None
    assert state2["disconnected"] == 1


# --- ble_lock & backoff_delays ------------------------------------------------------------

def test_ble_lock_same_within_loop_and_distinct_across_loops() -> None:
    async def get_pair() -> tuple[asyncio.Lock, asyncio.Lock]:
        return ble_util.ble_lock(), ble_util.ble_lock()

    loop1 = asyncio.new_event_loop()
    loop2 = asyncio.new_event_loop()
    try:
        l1_a, l1_b = loop1.run_until_complete(get_pair())
        l2_a, l2_b = loop2.run_until_complete(get_pair())
        assert l1_a is l1_b
        assert l2_a is l2_b
        assert l1_a is not l2_a
    finally:
        loop1.close()
        loop2.close()


def test_backoff_delays_sequence() -> None:
    assert list(islice(ble_util.backoff_delays(), 6)) == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]


def test_default_client_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_bleak(monkeypatch)
    client = ble_util.default_client_factory("AA:BB:CC:DD:EE:FF", timeout=12.0)
    assert client.device == "AA:BB:CC:DD:EE:FF"
    assert client.kwargs == {"timeout": 12.0}
