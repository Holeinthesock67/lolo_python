"""Ceinture cardio Bluetooth (service Heart Rate standard 0x180D), facultative.

La fréquence cardiaque d'une ceinture passe avant celle du trainer : `bpm` vaut None si aucune
mesure n'est arrivée depuis `STALE_S`, et la séance garde alors celle du trainer. Même schéma
de connexion que le Click : recherche en continu, reconnexion après une coupure, une ligne de
journal par connexion et par coupure.

Lot M2 : mesure décodée en entier (contact du capteur, intervalles RR), choix de l'appareil
quand `hr_address` est vide (liste des appareils 0x180D, nom `hr_name`, sinon le meilleur RSSI
hors montres), niveau de batterie (service 0x180F) lu à la connexion.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from . import ftms
from .ble_util import backoff_delays, ble_lock, default_client_factory, find_device

log = logging.getLogger("hr")

STALE_S = 5.0   # une ceinture envoie une mesure par seconde
SCAN_S = 5.0
RR_KEEP = 30
LOW_BATTERY_PCT = 15
# Fragments de nom (minuscules) des montres qui diffusent leur fréquence : écartées au profit
# d'une ceinture, sauf s'il n'y a qu'elles.
WATCH_NAME_HINTS = ("forerunner", "fenix", "fēnix", "venu", "watch", "epix", "instinct",
                    "vivoactive", "enduro", "polar ignite", "polar vantage", "coros", "suunto")


@dataclass
class HrCandidate:
    """Appareil trouvé qui annonce le service Heart Rate."""
    name: str
    address: str
    rssi: int | None = None
    device: Any = None   # objet à passer à la connexion (BLEDevice, ou adresse)

    @property
    def is_watch(self) -> bool:
        return looks_like_watch(self.name)


def looks_like_watch(name: str | None) -> bool:
    low = (name or "").lower()
    return any(h in low for h in WATCH_NAME_HINTS)


def choose_device(cands: list[HrCandidate], hr_name: str = "") -> HrCandidate | None:
    """`hr_name` donné : premier nom qui le contient ; sinon meilleur RSSI, montres en dernier."""
    if not cands:
        return None
    if hr_name:
        needle = hr_name.lower()
        return next((c for c in cands if needle in (c.name or "").lower()), None)
    straps = [c for c in cands if not c.is_watch] or cands
    return max(straps, key=lambda c: c.rssi if c.rssi is not None else -999)


async def scan_hr_devices(timeout: float = SCAN_S) -> list[HrCandidate]:
    """Recherche BLE réelle : tous les appareils qui annoncent 0x180D, avec leur RSSI."""
    from bleak import BleakScanner

    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    out = []
    for dev, adv in found.values():
        if ftms.HR_SERVICE in (getattr(adv, "service_uuids", None) or ()):
            out.append(HrCandidate(dev.name or adv.local_name or "", dev.address,
                                   getattr(adv, "rssi", None), dev))
    return out


def _sim_scanner(world: Any) -> Callable[[float], Awaitable[list[HrCandidate]]]:
    async def scan(timeout: float) -> list[HrCandidate]:
        ads = await world.scan(timeout, service=ftms.HR_SERVICE)
        return [HrCandidate(a.name, a.address, a.rssi, a) for a in ads]
    return scan


class HeartRateProvider:
    """`name` : fragment du nom BLE ; vide, la recherche se fait sur le service 0x180D annoncé.

    `device_scanner(timeout)` liste les appareils 0x180D quand `address` est vide ; par défaut
    la vraie recherche (avec `find_device` réel) ou celle du Bluetooth simulé (`find_device`
    d'un `SimWorld`). Sans scanner (doublures de test), recherche du premier appareil 0x180D.
    """

    def __init__(
        self,
        address: str | None = None,
        name: str = "",
        *,
        device_finder: Callable[..., Awaitable[Any]] = find_device,
        client_factory: Callable[..., Any] = default_client_factory,
        clock: Callable[[], float] = time.monotonic,
        device_scanner: Callable[[float], Awaitable[list[HrCandidate]]] | None = None,
    ) -> None:
        self.address, self.name = address or None, name
        self._find, self._client_factory, self._clock = device_finder, client_factory, clock
        if device_scanner is None:
            world = getattr(device_finder, "__self__", None)
            if device_finder is find_device:
                device_scanner = scan_hr_devices
            elif world is not None and hasattr(world, "scan"):
                device_scanner = _sim_scanner(world)
        self._scan = device_scanner
        self._bpm: int | None = None
        self._last_at: float | None = None
        self._contact: bool | None = None
        self._rr: deque[float] = deque(maxlen=RR_KEEP)
        self._link_up = False
        self._advised = False
        self.battery_pct: int | None = None
        self.device_address: str | None = None   # appareil retenu à la dernière connexion
        self._stop = asyncio.Event()

    @property
    def bpm(self) -> int | None:
        if self._last_at is None or self._clock() - self._last_at > STALE_S:
            return None
        return self._bpm

    @property
    def connected(self) -> bool:
        return self._link_up

    @property
    def contact(self) -> bool | None:
        """Dernier état du contact du capteur ; None si la ceinture ne le gère pas."""
        return self._contact

    @property
    def last_rr_ms(self) -> list[float]:
        """Les `RR_KEEP` derniers intervalles RR (ms), non écrits au journal de séance."""
        return list(self._rr)

    def stop(self) -> None:
        self._stop.set()

    def _on_hr(self, _ch: Any, data: bytearray) -> None:
        try:
            m = ftms.parse_hr_measurement_full(bytes(data))
        except Exception:
            return
        if m.contact is not None and m.contact != self._contact:
            if not m.contact:
                log.warning("Ceinture cardio : contact absent (ceinture à mouiller ?), mesures "
                            "ignorées")
            elif self._contact is False:
                log.info("Ceinture cardio : contact retrouvé")
        self._contact = m.contact
        if m.contact is False:
            return   # valeur fausse : `bpm` devient None au bout de STALE_S
        self._rr.extend(m.rr_ms)
        self._bpm, self._last_at = (m.bpm or None), self._clock()   # 0 = pas de contact

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

    async def _pick(self) -> Any:
        """Appareil à contacter : adresse imposée, sinon choix parmi les appareils trouvés."""
        if self.address or self._scan is None:
            return await self._find(self.name, self.address, SCAN_S, service=ftms.HR_SERVICE)
        cands = await self._scan(SCAN_S)
        if cands:
            log.info("Appareils cardio trouvés : %s", " ; ".join(
                f"{c.name or '?'} ({c.address}, RSSI {c.rssi if c.rssi is not None else '?'})"
                + (", montre" if c.is_watch else "") for c in cands))
        choice = choose_device(cands, self.name)
        if choice is None:
            return None
        if not self._advised:
            self._advised = True
            log.info("Ceinture cardio retenue : %s (%s) ; pour la garder, mettre hr_address = "
                     "\"%s\" dans config.toml", choice.name or "?", choice.address, choice.address)
        return choice.device if choice.device is not None else choice.address

    async def _read_battery(self, client: Any) -> None:
        try:
            if client.services.get_characteristic(ftms.BATTERY_LEVEL) is None:
                return
            raw = bytes(await client.read_gatt_char(ftms.BATTERY_LEVEL))
        except Exception as exc:   # la batterie est facultative : jamais d'échec de connexion
            log.debug("Ceinture cardio : batterie illisible : %s", exc)
            return
        if not raw:
            return
        self.battery_pct = raw[0]
        if self.battery_pct < LOW_BATTERY_PCT:
            log.warning("Ceinture cardio : batterie faible (%d %%), pile à changer",
                        self.battery_pct)
        else:
            log.info("Ceinture cardio : batterie %d %%", self.battery_pct)

    async def _session(self) -> None:
        loop = asyncio.get_running_loop()
        dropped = asyncio.Event()
        async with AsyncExitStack() as stack:
            async with ble_lock():   # un seul scan/connexion BLE à la fois (BlueZ)
                dev = await self._pick()
                if dev is None:
                    raise ConnectionError("ceinture introuvable (portée, contact humide ?)")
                client = await stack.enter_async_context(self._client_factory(
                    dev, disconnected_callback=lambda _c: loop.call_soon_threadsafe(dropped.set),
                    timeout=15.0))
            self.device_address = str(getattr(dev, "address", dev))
            await self._read_battery(client)
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
