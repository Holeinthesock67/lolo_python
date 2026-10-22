"""Sources d'entrées utilisateur : Zwift Click (BLE) et clavier du terminal (SRS §4.2, §4.4).

Les deux fournissent la même interface : `events` (file asyncio d'`InputEvent`), `status`
(valeur d'`input_status` du contrat IPC) et une tâche `run()`.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from contextlib import AsyncExitStack
from typing import Any, Awaitable, Callable

from . import zwift_click
from .ble_util import backoff_delays, ble_lock, default_client_factory, find_device
from .zwift_click import InputEvent, PressClassifier

log = logging.getLogger("input")


class ZwiftClickProvider:
    def __init__(
        self,
        address: str | None = None,
        short_max_s: float = zwift_click.SHORT_MAX_S,
        long_min_s: float = zwift_click.LONG_MIN_S,
        *,
        device_finder: Callable[[str, str | None, float], Awaitable[Any]] = find_device,
        client_factory: Callable[..., Any] = default_client_factory,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.address = address or None
        self.short_max_s, self.long_min_s = short_max_s, long_min_s
        self._find, self._client_factory, self._clock = device_finder, client_factory, clock
        self.events: asyncio.Queue[InputEvent] = asyncio.Queue()
        self.battery_pct: int | None = None
        self._classifier = PressClassifier(short_max_s, long_min_s)
        self._link_up = False
        self._ever_connected = False
        self._stop = asyncio.Event()

    @property
    def status(self) -> str:
        if self._link_up:
            return "CONNECTED"
        return "LOST"   # le clavier reste actif pendant ce temps (contrat IPC §6)

    def stop(self) -> None:
        self._stop.set()

    def _on_async(self, _ch: Any, data: bytearray) -> None:
        raw = bytes(data)
        msg_type, fields = zwift_click.parse_async(raw)
        if msg_type == zwift_click.MSG_BATTERY_LEVEL:
            self.battery_pct = fields.get(2)
            return
        buttons = zwift_click.parse_click_buttons(raw)
        if buttons is None:
            return
        for ev in self._classifier.feed(buttons, self._clock()):
            log.info("Click : %s", ev.value)
            self.events.put_nowait(ev)

    async def run(self) -> None:
        delays = backoff_delays()
        while not self._stop.is_set():
            try:
                await self._session()
                delays = backoff_delays()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("Click : %s", exc)
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
        # Un bouton « appuyé » à la coupure ne doit pas survivre à la reconnexion.
        self._classifier = PressClassifier(self.short_max_s, self.long_min_s)
        async with AsyncExitStack() as stack:
            async with ble_lock():   # un seul scan/connexion BLE à la fois (BlueZ)
                dev = await self._find(zwift_click.CLICK_NAME, self.address, 6.0)
                if dev is None:
                    raise ConnectionError("Zwift Click introuvable (appuyez sur un bouton)")
                client = await stack.enter_async_context(self._client_factory(
                    dev, disconnected_callback=lambda _c: loop.call_soon_threadsafe(dropped.set),
                    timeout=15.0))
            await client.start_notify(zwift_click.ZWIFT_ASYNC, self._on_async)
            await client.start_notify(zwift_click.ZWIFT_SYNC_TX, lambda _c, _d: None)
            await client.write_gatt_char(zwift_click.ZWIFT_SYNC_RX, zwift_click.RIDE_ON,
                                         response=True)
            self._link_up = self._ever_connected = True
            log.info("Zwift Click connecté")
            while not (dropped.is_set() or self._stop.is_set()):
                await asyncio.sleep(0.2)
        self._link_up = False


class KeyboardProvider:
    """Entrées au clavier du terminal du core (développement et repli).

    `+`/`=` : + court   `-` : − court   `u` : + long   `d` : − long   (sans Entrée).
    """

    KEYS = {"+": InputEvent.PLUS_SHORT, "=": InputEvent.PLUS_SHORT,
            "-": InputEvent.MINUS_SHORT, "u": InputEvent.PLUS_LONG, "d": InputEvent.MINUS_LONG}
    status = "KEYBOARD"

    def __init__(self) -> None:
        self.events: asyncio.Queue[InputEvent] = asyncio.Queue()
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        if not sys.stdin.isatty():
            log.info("Pas de terminal interactif : entrées clavier désactivées")
            await self._stop.wait()
            return
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        loop = asyncio.get_running_loop()

        def on_key() -> None:
            for ch in sys.stdin.read(1):
                ev = self.KEYS.get(ch)
                if ev is not None:
                    self.events.put_nowait(ev)

        try:
            tty.setcbreak(fd)
            loop.add_reader(fd, on_key)
            log.info("Clavier : + - (braquet), u / d (appui long + / −)")
            await self._stop.wait()
        finally:
            loop.remove_reader(fd)
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


class NullProvider:
    status = "KEYBOARD"

    def __init__(self) -> None:
        self.events: asyncio.Queue[InputEvent] = asyncio.Queue()
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        await self._stop.wait()
