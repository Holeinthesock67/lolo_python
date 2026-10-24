"""Ceinture cardio Bluetooth (service Heart Rate standard 0x180D), facultative.

La fréquence cardiaque d'une ceinture passe avant celle du trainer : `bpm` vaut None si aucune
mesure n'est arrivée depuis `STALE_S`, et la séance garde alors celle du trainer. Même schéma
de connexion que le Click : recherche en continu, reconnexion après une coupure, une ligne de
journal par connexion et par coupure.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import AsyncExitStack
from typing import Any, Awaitable, Callable

from . import ftms
from .ble_util import backoff_delays, ble_lock, default_client_factory, find_device

log = logging.getLogger("hr")

STALE_S = 5.0   # une ceinture envoie une mesure par seconde


class HeartRateProvider:
    """`name` : fragment du nom BLE ; vide, la recherche se fait sur le service 0x180D annoncé."""

    def __init__(
        self,
        address: str | None = None,
        name: str = "",
        *,
        device_finder: Callable[..., Awaitable[Any]] = find_device,
        client_factory: Callable[..., Any] = default_client_factory,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.address, self.name = address or None, name
        self._find, self._client_factory, self._clock = device_finder, client_factory, clock
        self._bpm: int | None = None
        self._last_at: float | None = None
        self._link_up = False
        self._stop = asyncio.Event()

    @property
    def bpm(self) -> int | None:
        if self._last_at is None or self._clock() - self._last_at > STALE_S:
            return None
        return self._bpm

    @property
    def connected(self) -> bool:
        return self._link_up

    def stop(self) -> None:
        self._stop.set()

    def _on_hr(self, _ch: Any, data: bytearray) -> None:
        try:
            bpm = ftms.parse_hr_measurement(bytes(data))
        except Exception:
            return
        self._bpm, self._last_at = (bpm or None), self._clock()   # 0 = pas de contact

    async def run(self) -> None:
        delays = backoff_delays(first=1.0, maximum=10.0)
        while not self._stop.is_set():
            try:
                await self._session()
                delays = backoff_delays(first=1.0, maximum=10.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.info("Ceinture cardio : %s", exc)
            self._link_up = False
            if self._stop.is_set():
                break
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=next(delays))
            except asyncio.TimeoutError:
                pass

    async def _session(self) -> None:
        loop = asyncio.get_running_loop()
        dropped = asyncio.Event()
        async with AsyncExitStack() as stack:
            async with ble_lock():   # un seul scan/connexion BLE à la fois (BlueZ)
                dev = await self._find(self.name, self.address, 5.0, service=ftms.HR_SERVICE)
                if dev is None:
                    raise ConnectionError("ceinture introuvable (portée, contact humide ?)")
                client = await stack.enter_async_context(self._client_factory(
                    dev, disconnected_callback=lambda _c: loop.call_soon_threadsafe(dropped.set),
                    timeout=15.0))
            await client.start_notify(ftms.HR_MEASUREMENT, self._on_hr)
            self._link_up = True
            since = self._clock()
            log.info("Ceinture cardio connectée (%s)", getattr(dev, "name", None) or dev)
            try:
                while not (dropped.is_set() or self._stop.is_set()):
                    await asyncio.sleep(0.2)
            finally:
                self._link_up = False
            if dropped.is_set():
                log.warning("Ceinture cardio déconnectée après %.1f s", self._clock() - since)
