"""Utilitaires BLE communs aux pilotes (recherche d'appareil, temporisation de reconnexion)."""

from __future__ import annotations

import asyncio
import logging
import time
import weakref
from typing import Any, Iterator

log = logging.getLogger("ble")

_locks: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock]" = (
    weakref.WeakKeyDictionary())


_last_trainer_write_at: float | None = None


def note_trainer_write() -> None:
    """Note l'heure (time.monotonic) d'une écriture au trainer, pour le diagnostic du Click (lot K8)."""
    global _last_trainer_write_at
    _last_trainer_write_at = time.monotonic()


def last_trainer_write_at() -> float | None:
    return _last_trainer_write_at


def ble_lock() -> asyncio.Lock:
    """Verrou commun : BlueZ n'accepte qu'un scan ou une connexion à la fois.

    Tenu pendant la recherche et l'établissement de la connexion, relâché dès qu'elle est
    établie (la suite de la session BLE n'a pas besoin d'exclusivité).
    """
    loop = asyncio.get_running_loop()
    lock = _locks.get(loop)
    if lock is None:
        lock = _locks[loop] = asyncio.Lock()
    return lock


async def known_bluez_address(name: str) -> str | None:
    """Adresse d'un appareil déjà connu de BlueZ (même déjà connecté, donc muet en scan)."""
    try:
        from dbus_fast import BusType
        from dbus_fast.aio import MessageBus

        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        try:
            intro = await bus.introspect("org.bluez", "/")
            om = bus.get_proxy_object("org.bluez", "/", intro).get_interface(
                "org.freedesktop.DBus.ObjectManager")
            objects = await om.call_get_managed_objects()
        finally:
            bus.disconnect()
        needle = name.lower()
        for ifaces in objects.values():
            dev = ifaces.get("org.bluez.Device1")
            if not dev:
                continue
            label = " ".join(str(dev[k].value) for k in ("Name", "Alias") if k in dev).lower()
            if needle in label and "Address" in dev:
                return str(dev["Address"].value)
    except Exception as exc:   # BlueZ absent, droits, version : on retombe sur le scan seul
        log.debug("Liste BlueZ indisponible : %s", exc)
    return None


async def find_device(name: str, address: str | None, timeout: float) -> Any | None:
    """Cherche un appareil par adresse, sinon par fragment de nom.

    Scan d'abord ; si rien n'est annoncé, repli sur les appareils connus de BlueZ, car un
    appareil déjà connecté (Click resté accroché) n'émet plus de publicité. Renvoie un
    BLEDevice, ou une adresse (str) que BleakClient sait connecter directement, ou None.
    """
    from bleak import BleakScanner

    if address:
        dev = await BleakScanner.find_device_by_address(address, timeout=timeout)
        return dev or address
    needle = name.lower()
    dev = await BleakScanner.find_device_by_filter(
        lambda d, ad: needle in (d.name or ad.local_name or "").lower(), timeout=timeout)
    if dev is not None:
        return dev
    known = await known_bluez_address(name)
    if known:
        log.info("%s non annoncé : connexion directe à l'appareil connu de BlueZ (%s)", name, known)
    return known


def backoff_delays(first: float = 1.0, factor: float = 2.0, maximum: float = 10.0) -> Iterator[float]:
    """Délais croissants de reconnexion : 1, 2, 4, 8, 10, 10, …"""
    d = first
    while True:
        yield d
        d = min(d * factor, maximum)


def default_client_factory(device: Any, **kwargs: Any) -> Any:
    from bleak import BleakClient

    return BleakClient(device, **kwargs)
