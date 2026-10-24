"""Sources d'entrées utilisateur : Zwift Click (BLE) et clavier du terminal (SRS §4.2, §4.4).

Les deux fournissent la même interface : `events` (file asyncio d'`InputEvent`), `status`
(valeur d'`input_status` du contrat IPC) et une tâche `run()`.

Journal du Click (lot K8, diagnostic des coupures), une ligne par événement, émise par la
tâche du Click (jamais par la boucle à 50 Hz) :
- connexion : `Zwift Click connecté (adresse A, recherche 3.2 s, 2 tentative(s))` ; la recherche
  court depuis le lancement ou la coupure précédente ;
- coupure : `Zwift Click déconnecté (adresse A) après 75.0 s de connexion : dernière
  notification il y a 0.1 s, dernier appui il y a 12.3 s, 750 notification(s), dernière écriture au trainer il y a
  0.4 s, raison : R ; appuyez sur un bouton pour le réveiller` (« jamais » si l'événement n'a
  pas eu lieu ; bleak ne donne pas la raison BlueZ : R vaut « lien perdu (rappel bleak) »,
  « fin de session », « arrêt du core » ou le texte de l'erreur) ;
- toutes les 60 s de connexion : `Click : 600 notification(s) en 60 s (10.0 par seconde)`.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from contextlib import AsyncExitStack
from typing import Any, Awaitable, Callable

from . import zwift_click
from .ble_util import backoff_delays, ble_lock, default_client_factory, find_device, last_trainer_write_at
from .zwift_click import InputEvent, PressClassifier

log = logging.getLogger("input")

CLICK_CONNECTED_FMT = "Zwift Click connecté (adresse %s, recherche %.1f s, %d tentative(s))"
CLICK_DISCONNECTED_FMT = ("Zwift Click déconnecté (adresse %s) après %.1f s de connexion : dernière notification il y a %s, "
                          "dernier appui il y a %s, %d notification(s), dernière écriture au trainer il y a %s, "
                          "raison : %s ; appuyez sur un bouton pour le réveiller")
CLICK_RATE_FMT = "Click : %d notification(s) en %.0f s (%.1f par seconde)"
RATE_PERIOD_S = 60.0


def _ago(now: float, then: float | None) -> str:
    return "jamais" if then is None else f"{max(now - then, 0.0):.1f} s"


class ClickPair:
    """État partagé par les deux boîtiers d'un Zwift Click récent (« + » et « − », même nom BLE).

    `claimed` : adresses déjà tenues, pour que chaque fournisseur prenne un boîtier différent.
    Le boîtier « − » relaie aussi les appuis du « + » (mesuré le 24 octobre : même événement
    reçu des deux, à 5–40 ms d'écart) : `first_report` ne laisse passer que le premier.
    """

    DEDUP_S = 0.15   # bien moins qu'un appui court réel entre deux relâchements

    def __init__(self) -> None:
        self.claimed: set[str] = set()
        self._last: dict[InputEvent, float] = {}

    def first_report(self, ev: InputEvent, t: float) -> bool:
        last = self._last.get(ev)
        self._last[ev] = t
        return last is None or t - last > self.DEDUP_S


class ZwiftClickProvider:
    """Un boîtier Zwift Click. Pour la paire du Click récent, `build_inputs` crée deux
    fournisseurs qui partagent un `ClickPair`. `optional` : second boîtier, absent chez qui n'en
    a qu'un ; son absence ne s'écrit qu'en DEBUG.
    """

    def __init__(
        self,
        address: str | None = None,
        short_max_s: float = zwift_click.SHORT_MAX_S,
        long_min_s: float = zwift_click.LONG_MIN_S,
        *,
        device_finder: Callable[[str, str | None, float], Awaitable[Any]] = find_device,
        client_factory: Callable[..., Any] = default_client_factory,
        clock: Callable[[], float] = time.monotonic,
        pair: ClickPair | None = None,
        optional: bool = False,
    ) -> None:
        self.address = address or None
        self._pair, self._optional = pair, optional
        self._claimed = pair.claimed if pair is not None else None
        self._mine: str | None = None   # adresse du boîtier tenu, retirée de `claimed` à la coupure
        self.short_max_s, self.long_min_s = short_max_s, long_min_s
        self._find, self._client_factory, self._clock = device_finder, client_factory, clock
        self.events: asyncio.Queue[InputEvent] = asyncio.Queue()
        self.battery_pct: int | None = None
        self._classifier = PressClassifier(short_max_s, long_min_s)
        self._link_up = False
        self._ever_connected = False
        self._stop = asyncio.Event()
        # Diagnostic des coupures (lot K8)
        self._connected_at: float | None = None
        self._last_notify_at: float | None = None
        self._last_press_at: float | None = None
        self._notify_count = 0
        self._rate_since = 0.0
        self._rate_count = 0
        self._search_since = 0.0
        self._attempts = 0
        self._drop_reason = ""
        self._conn_address = "?"   # boîtier de la dernière connexion, repris dans la ligne de coupure

    @property
    def status(self) -> str:
        if self._link_up:
            return "CONNECTED"
        return "LOST"   # le clavier reste actif pendant ce temps (contrat IPC §6)

    def stop(self) -> None:
        self._stop.set()

    def _on_async(self, _ch: Any, data: bytearray) -> None:
        now = self._clock()
        self._last_notify_at = now
        self._notify_count += 1
        self._rate_count += 1
        raw = bytes(data)
        msg_type, fields = zwift_click.parse_async(raw)
        if msg_type == zwift_click.MSG_BATTERY_LEVEL:
            self.battery_pct = fields.get(2)
            return
        buttons = zwift_click.parse_click_buttons(raw)
        if buttons is None:
            return
        for ev in self._classifier.feed(buttons, now):
            if self._pair is not None and not self._pair.first_report(ev, now):
                log.debug("Click : %s relayé par l'autre boîtier, ignoré", ev.value)
                continue
            self._last_press_at = now
            log.info("Click : %s", ev.value)
            self.events.put_nowait(ev)

    async def run(self) -> None:
        # Le Click ne s'annonce que réveillé par un appui : on le cherche en continu, par
        # fenêtres de 5 s séparées de 0,5 à 2 s, pour qu'un appui tombe toujours dans une fenêtre.
        # Second boîtier : fenêtres plus espacées, pour laisser le Bluetooth au trainer.
        maximum = 5.0 if self._optional else 2.0
        delays = backoff_delays(first=0.5, maximum=maximum)
        self._search_since, self._attempts = self._clock(), 0
        while not self._stop.is_set():
            try:
                self._attempts += 1
                await self._session()
                self._log_drop(self._drop_reason)
                delays = backoff_delays(first=0.5, maximum=maximum)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._connected_at is not None:
                    self._log_drop(str(exc) or type(exc).__name__)
                elif self._optional and isinstance(exc, ConnectionError):
                    log.debug("Click (second boîtier) : %s", exc)
                else:
                    log.warning("Click : %s", exc)
            self._link_up = False
            if self._stop.is_set():
                break
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=next(delays))
            except asyncio.TimeoutError:
                pass

    def _log_drop(self, reason: str) -> None:
        now = self._clock()
        connected = now - self._connected_at if self._connected_at is not None else 0.0
        write_at = last_trainer_write_at()
        since_write = "jamais" if write_at is None else f"{max(time.monotonic() - write_at, 0.0):.1f} s"
        log.warning(CLICK_DISCONNECTED_FMT, self._conn_address, connected, _ago(now, self._last_notify_at),
                    _ago(now, self._last_press_at), self._notify_count, since_write, reason or "fin de session")
        self._connected_at = None
        self._search_since, self._attempts = now, 0

    async def _session(self) -> None:
        loop = asyncio.get_running_loop()
        dropped = asyncio.Event()
        # Un bouton « appuyé » à la coupure ne doit pas survivre à la reconnexion.
        self._classifier = PressClassifier(self.short_max_s, self.long_min_s)
        try:
            await self._connected_session(loop, dropped)
        finally:
            if self._claimed is not None and self._mine is not None:
                self._claimed.discard(self._mine)
            self._mine = None
            self._link_up = False

    async def _connected_session(self, loop: asyncio.AbstractEventLoop, dropped: asyncio.Event) -> None:
        async with AsyncExitStack() as stack:
            async with ble_lock():   # un seul scan/connexion BLE à la fois (BlueZ)
                if self._claimed is None:
                    dev = await self._find(zwift_click.CLICK_NAME, self.address, 5.0)
                else:
                    dev = await self._find(zwift_click.CLICK_NAME, self.address, 5.0,
                                           exclude=frozenset(self._claimed))
                if dev is None:
                    raise ConnectionError("Zwift Click introuvable (appuyez sur un bouton)")
                addr = str(getattr(dev, "address", dev)).upper()
                if self._claimed is not None:
                    if addr in self._claimed:   # adresse imposée déjà tenue par l'autre fournisseur
                        raise ConnectionError(f"Zwift Click {addr} déjà connecté")
                    self._claimed.add(addr)
                    self._mine = addr
                client = await stack.enter_async_context(self._client_factory(
                    dev, disconnected_callback=lambda _c: loop.call_soon_threadsafe(dropped.set),
                    timeout=15.0))
            await client.start_notify(zwift_click.ZWIFT_ASYNC, self._on_async)
            await client.start_notify(zwift_click.ZWIFT_SYNC_TX, lambda _c, _d: None)
            await client.write_gatt_char(zwift_click.ZWIFT_SYNC_RX, zwift_click.RIDE_ON,
                                         response=True)
            self._link_up = self._ever_connected = True
            now = self._clock()
            self._conn_address = str(self._mine or getattr(dev, "address", dev))
            log.info(CLICK_CONNECTED_FMT, self._conn_address, now - self._search_since, self._attempts)
            self._connected_at = self._rate_since = now
            self._last_notify_at = self._last_press_at = None
            self._notify_count = self._rate_count = 0
            while not (dropped.is_set() or self._stop.is_set()):
                await asyncio.sleep(0.2)
                now = self._clock()
                if now - self._rate_since >= RATE_PERIOD_S:
                    span = now - self._rate_since
                    log.info(CLICK_RATE_FMT, self._rate_count, span, self._rate_count / span)
                    self._rate_since, self._rate_count = now, 0
            self._drop_reason = ("lien perdu (rappel bleak)" if dropped.is_set()
                                 else "arrêt du core" if self._stop.is_set() else "fin de session")


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
