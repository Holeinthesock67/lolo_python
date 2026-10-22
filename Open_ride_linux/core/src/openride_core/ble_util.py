"""Utilitaires BLE communs aux pilotes (recherche d'appareil, temporisation de reconnexion)."""

from __future__ import annotations

import logging
from typing import Any, Iterator

log = logging.getLogger("ble")


async def find_device(name: str, address: str | None, timeout: float) -> Any | None:
    """Cherche un appareil par adresse, sinon par fragment de nom. Renvoie None si absent."""
    from bleak import BleakScanner

    if address:
        return await BleakScanner.find_device_by_address(address, timeout=timeout)
    needle = name.lower()
    return await BleakScanner.find_device_by_filter(
        lambda d, ad: needle in (d.name or ad.local_name or "").lower(), timeout=timeout)


def backoff_delays(first: float = 1.0, factor: float = 2.0, maximum: float = 10.0) -> Iterator[float]:
    """Délais croissants de reconnexion : 1, 2, 4, 8, 10, 10, …"""
    d = first
    while True:
        yield d
        d = min(d * factor, maximum)


def default_client_factory(device: Any, **kwargs: Any) -> Any:
    from bleak import BleakClient

    return BleakClient(device, **kwargs)
