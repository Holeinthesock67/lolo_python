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

from . import latency_log, zwift_click
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
    KEEP_S = 5.0     # heures de relâchement gardées par événement

    def __init__(self) -> None:
        self.claimed: set[str] = set()
        self._seen: dict[InputEvent, list[float]] = {}

    def first_report(self, ev: InputEvent, t: float) -> bool:
        """`t` : heure du relâchement. Une rafale finie (R14) publie plusieurs tapes à la fois, dans
        le désordre entre les deux boîtiers : on compare donc à toutes les heures récentes."""
        seen = [s for s in self._seen.get(ev, []) if abs(t - s) <= self.KEEP_S]
        relayed = any(abs(t - s) <= self.DEDUP_S for s in seen)
        self._seen[ev] = seen + [t]
        return not relayed


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
        repeat_gap_s: float = 0.0,   # la séance passe `[drivers] click_repeat_gap_s` (0 par défaut)
        device_finder: Callable[[str, str | None, float], Awaitable[Any]] = find_device,
        client_factory: Callable[..., Any] = default_client_factory,
        clock: Callable[[], float] = time.monotonic,
        pair: ClickPair | None = None,
        optional: bool = False,
        trace_raw: bool | None = None,
        mute_after_s: float | None = None,
        rehandshake_s: float | None = None,
        reset_locked: str = "off",
        side: str | None = None,
        side_of: Callable[[str], str | None] | None = None,
    ) -> None:
        self.address = address or None
        self._pair, self._optional = pair, optional
        self._claimed = pair.claimed if pair is not None else None
        self._mine: str | None = None   # adresse du boîtier tenu, retirée de `claimed` à la coupure
        self.short_max_s, self.long_min_s, self.repeat_gap_s = short_max_s, long_min_s, repeat_gap_s
        self._find, self._client_factory, self._clock = device_finder, client_factory, clock
        self.events: asyncio.Queue[InputEvent] = asyncio.Queue()
        self.battery_pct: int | None = None
        self._classifier = PressClassifier(short_max_s, long_min_s, repeat_gap_s)
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
        # Lot Q6 : trace brute, détection du boîtier muet et reprise (réglages [drivers] passés par la séance)
        self.trace_raw: bool = False if trace_raw is None else trace_raw
        self.mute_after_s: float = 60.0 if mute_after_s is None else float(mute_after_s)
        self.rehandshake_s: float = 0.0 if rehandshake_s is None else float(rehandshake_s)
        # Verrou du boîtier gauche (`[drivers] click_reset_locked`, zwift_click.LOCK_POLICIES).
        if reset_locked not in zwift_click.LOCK_POLICIES:
            raise ValueError(f"reset_locked : {reset_locked!r} n'est pas parmi {', '.join(zwift_click.LOCK_POLICIES)}")
        self.reset_locked = reset_locked
        self._lock_mode: int | None = None   # dernier mode du message d'état (boîtier gauche)
        self._reset_sent = False
        # Lot K9 : réponses `ff 04 00` du choix « keep » et fenêtres de boutons en clair du boîtier gauche.
        self._wake = asyncio.Event()
        self._keep_due = False
        self._keep_replies = 0
        self._window_start: float | None = None
        self._window_presses = 0
        self.windows: list[dict[str, Any]] = []   # une entrée par fenêtre fermée (verrou ou coupure)
        self._explicit_side = side
        self._side_of = side_of
        self.msg_counts: dict[str, int] = dict.fromkeys(zwift_click.MESSAGE_TYPES, 0)
        self._mute_reported = False
        self._rehandshake_step = 0
        self._last_rehandshake_at: float = 0.0
        self._last_raw_trace_at: float = 0.0
        self._pending_raw_key: tuple[str, str, int, bytes] | None = None
        self._pending_raw_count = 0

    @property
    def side(self) -> str:
        """« droit » (boîtier « + »), « gauche » (boîtier « − ») ou « inconnu » pour le journal."""
        if self._explicit_side in ("droit", "gauche", "inconnu"):
            return self._explicit_side
        addr = self._mine or self.address or self._conn_address or ""
        if addr and addr != "?" and self._side_of is not None:
            return self._side_of(addr) or "inconnu"
        return "inconnu"

    def _trace_raw_notification(self, now: float, char: str, msg_type: int,
                                category: str, raw: bytes, has_button: bool) -> None:
        if has_button:
            self._flush_raw_trace()
            log.info("Click %s %s type 0x%02x (%s) : %s",
                     self.side, char, msg_type, category, raw.hex())
            self._last_raw_trace_at = now
            return

        key = (self.side, char, msg_type, raw)
        if self._pending_raw_key == key:
            self._pending_raw_count += 1
        else:
            self._flush_raw_trace()
            self._pending_raw_key = key
            self._pending_raw_count = 1
            if self._last_raw_trace_at == 0.0:
                self._last_raw_trace_at = now

        if now - self._last_raw_trace_at >= 2.0:
            self._flush_raw_trace()
            self._last_raw_trace_at = now

    def _flush_raw_trace(self) -> None:
        if not self._pending_raw_key or self._pending_raw_count == 0:
            return
        side, char, msg_type, raw = self._pending_raw_key
        category = zwift_click.classify_message(raw)
        if self._pending_raw_count > 1:
            log.info("Click %s %s type 0x%02x (%s) : %s (%d messages)",
                     side, char, msg_type, category, raw.hex(), self._pending_raw_count)
        else:
            log.info("Click %s %s type 0x%02x (%s) : %s",
                     side, char, msg_type, category, raw.hex())
        self._pending_raw_key = None
        self._pending_raw_count = 0

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
        category = zwift_click.classify_message(raw)
        self.msg_counts[category] = self.msg_counts.get(category, 0) + 1

        msg_type, fields = zwift_click.parse_async(raw)
        char_name = "ASYNC" if _ch is None else getattr(_ch, "uuid", str(_ch))
        if char_name == zwift_click.ZWIFT_ASYNC or "00000002" in char_name:
            char_name = "ASYNC"

        buttons = None
        if category == "etat":
            mode = zwift_click.parse_status(raw)
            if mode != self._lock_mode:
                self._lock_mode = mode
                log.info("Click %s : état du boîtier, mode %s (%s)", self.side, mode,
                         "verrouillé par Zwift" if mode == zwift_click.STATUS_MODE_LOCKED else "boutons en clair")
                if mode == zwift_click.STATUS_MODE_LOCKED:
                    self._close_window(now, "verrou")
        elif category == "defi":
            self._request_keep()
        elif msg_type == zwift_click.MSG_BATTERY_LEVEL:
            self.battery_pct = fields.get(2)
        else:
            buttons = zwift_click.parse_click_buttons(raw)

        has_button = False
        if buttons is not None:
            if buttons.plus_pressed or buttons.minus_pressed or buttons.y_pressed:
                has_button = True
                self._mute_reported = False
                self._rehandshake_step = 0

            self._emit(self._classifier.feed_timed(buttons, now), now)
            if self.repeat_gap_s > 0:
                # Fin de rafale à l'heure exacte (relâchement + écart) : le boîtier qui a vu le
                # relâchement le premier publie le premier, comme sans regroupement.
                try:
                    asyncio.get_running_loop().call_later(self.repeat_gap_s + 0.01, self._poll_bursts)
                except RuntimeError:   # appel hors boucle (tests) : la boucle du fournisseur s'en charge
                    pass

        if self.trace_raw:
            self._trace_raw_notification(now, char_name, msg_type, category, raw, has_button)

    def _poll_bursts(self) -> None:
        now = self._clock()
        self._emit(self._classifier.poll_timed(now), now)

    def _emit(self, timed: list[tuple[InputEvent, float]], now: float) -> None:
        """Publie les événements du classeur ; la paire compare les heures de relâchement, pas l'heure
        de publication (une rafale finit `repeat_gap_s` après, au tour de boucle suivant)."""
        for ev, released_at in timed:
            if self._pair is not None and not self._pair.first_report(ev, released_at):
                log.debug("Click : %s relayé par l'autre boîtier, ignoré", ev.value)
                continue
            self._last_press_at = now
            self._window_presses += 1
            log.info("Click : %s", ev.value)
            self.events.put_nowait(ev)
            latency_log.new_press(self)   # lot X7 : sans effet hors `--latence`

    def _on_sync_tx(self, _ch: Any, data: bytearray) -> None:
        """Réponse à l'activation : l'écho `RideOn` dit le boîtier déverrouillé (§3.3 de la recherche)."""
        raw = bytes(data)
        if self.trace_raw:
            log.info("Click %s SYNC_TX : %s", self.side, raw.hex())
        if raw.startswith(zwift_click.RIDE_ON):
            self._request_keep()

    def _log_summary(self) -> None:
        c = self.msg_counts
        log.info("Click %s résumé : %d boutons, %d maintien, %d batterie, %d état, %d défi, %d inconnu",
                 self.side, c.get("boutons", 0), c.get("maintien", 0), c.get("batterie", 0), c.get("etat", 0),
                 c.get("defi", 0), c.get("inconnu", 0))

    def _request_keep(self) -> None:
        """Choix « keep » : demande une réponse `ff 04 00`, écrite par la boucle de la session."""
        if self.reset_locked == "keep" and self._link_up:
            self._keep_due = True
            self._wake.set()

    def _close_window(self, now: float, cause: str) -> None:
        """Ferme la fenêtre de boutons en clair du boîtier gauche (verrou ou coupure) et la journalise."""
        if self._window_start is None:
            return
        window = {"duration_s": round(now - self._window_start, 1), "cause": cause, "policy": self.reset_locked,
                  "presses": self._window_presses, "keep_replies": self._keep_replies}
        self._window_start = None
        self.windows.append(window)
        log.info("Click %s : fenêtre de boutons de %.1f s, fin par %s (choix %s, %d appuis, %d réponses ff 04 00)",
                 self.side, window["duration_s"], cause, self.reset_locked, window["presses"], window["keep_replies"])

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
        if self.trace_raw:
            self._flush_raw_trace()
        connected = now - self._connected_at if self._connected_at is not None else 0.0
        if self._lock_mode is not None:   # seul le boîtier gauche envoie le message d'état
            self._close_window(now, "arrêt" if self._stop.is_set() else "coupure")
        write_at = last_trainer_write_at()
        since_write = "jamais" if write_at is None else f"{max(time.monotonic() - write_at, 0.0):.1f} s"
        log.warning(CLICK_DISCONNECTED_FMT, self._conn_address, connected, _ago(now, self._last_notify_at),
                    _ago(now, self._last_press_at), self._notify_count, since_write, reason or "fin de session")
        if self.trace_raw:
            self._log_summary()
        self._connected_at = None
        self._search_since, self._attempts = now, 0

    async def _session(self) -> None:
        loop = asyncio.get_running_loop()
        dropped = asyncio.Event()
        # Un bouton « appuyé » à la coupure ne doit pas survivre à la reconnexion.
        self._classifier = PressClassifier(self.short_max_s, self.long_min_s, self.repeat_gap_s)
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
            self._keep_due, self._keep_replies = False, 0
            self._link_up = self._ever_connected = True   # avant l'activation : l'écho peut répondre aussitôt
            await client.start_notify(zwift_click.ZWIFT_SYNC_TX, self._on_sync_tx)
            if self.reset_locked == "keep":   # essai D : activation complète
                for i, frame in enumerate(zwift_click.ACTIVATION):
                    if i:
                        await asyncio.sleep(zwift_click.ACTIVATION_GAP_S)
                    await client.write_gatt_char(zwift_click.ZWIFT_SYNC_RX, frame, response=True)
            else:
                await client.write_gatt_char(zwift_click.ZWIFT_SYNC_RX, zwift_click.RIDE_ON,
                                             response=True)
            now = self._clock()
            self._conn_address = str(self._mine or getattr(dev, "address", dev))
            log.info(CLICK_CONNECTED_FMT, self._conn_address, now - self._search_since, self._attempts)
            self._connected_at = self._rate_since = now
            self._last_notify_at = self._last_press_at = None
            self._notify_count = self._rate_count = 0
            self._lock_mode, self._reset_sent = None, False
            self._window_start, self._window_presses = now, 0
            while not (dropped.is_set() or self._stop.is_set()):
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=0.2)
                except asyncio.TimeoutError:
                    pass
                self._wake.clear()
                now = self._clock()
                self._emit(self._classifier.poll_timed(now), now)   # fin des rafales (R14)
                # Choix « keep » : `ff 04 00` à l'écho et à chaque défi, pour garder le boîtier déverrouillé.
                if self._keep_due:
                    self._keep_due = False
                    try:
                        await client.write_gatt_char(zwift_click.ZWIFT_SYNC_RX, zwift_click.KEEP_UNLOCKED,
                                                     response=True)
                        self._keep_replies += 1
                        log.debug("Click %s : maintien du déverrouillage (ff 04 00, %d)", self.side, self._keep_replies)
                    except Exception as exc:
                        log.info("Click %s : échec de ff 04 00 (%s)", self.side, exc)
                if now - self._rate_since >= RATE_PERIOD_S:
                    span = now - self._rate_since
                    log.info(CLICK_RATE_FMT, self._rate_count, span, self._rate_count / span)
                    if self.trace_raw:
                        self._log_summary()
                    self._rate_since, self._rate_count = now, 0

                if self.trace_raw and self._pending_raw_count > 0 and (now - self._last_raw_trace_at >= 2.0):
                    self._flush_raw_trace()
                    self._last_raw_trace_at = now

                # Boîtier gauche verrouillé par Zwift : un redémarrage (0x18) redonne des boutons en clair
                # pendant environ une minute ; la reconnexion est celle d'une coupure ordinaire.
                if (self.reset_locked != "off" and not self._reset_sent
                        and self._lock_mode == zwift_click.STATUS_MODE_LOCKED):
                    self._reset_sent = True
                    if self.reset_locked == "keep":
                        log.warning("Click %s : maintien échoué après %.1f s (%d réponses ff 04 00), "
                                    "redémarrage du boîtier (0x18)", self.side, now - self._connected_at,
                                    self._keep_replies)
                    else:
                        log.warning("Click %s : verrouillé par Zwift, redémarrage du boîtier (0x18)", self.side)
                    try:
                        await client.write_gatt_char(zwift_click.ZWIFT_SYNC_RX, zwift_click.RESET_POD, response=True)
                    except Exception as exc:   # le boîtier peut couper la liaison avant d'acquitter
                        log.info("Click %s : liaison coupée pendant le redémarrage (%s)", self.side, exc)

                # Détection du boîtier muet
                if self._notify_count > 0:
                    ref_press = self._last_press_at if self._last_press_at is not None else self._connected_at
                    if ref_press is not None and (now - ref_press >= self.mute_after_s):
                        if not self._mute_reported:
                            self._mute_reported = True
                            log.warning("Click %s : connecté mais muet depuis %.0f s", self.side, self.mute_after_s)
                            self._last_rehandshake_at = now
                            if self.rehandshake_s > 0:
                                self._rehandshake_step = 1
                                log.info("Click %s : tentative de reprise 1/3 (renvoi de RideOn)", self.side)
                                try:
                                    await client.write_gatt_char(zwift_click.ZWIFT_SYNC_RX, zwift_click.RIDE_ON, response=True)
                                except Exception as exc:
                                    log.warning("Click %s : échec renvoi RideOn : %s", self.side, exc)

                        elif self.rehandshake_s > 0 and 1 <= self._rehandshake_step < 3:
                            if now - self._last_rehandshake_at >= self.rehandshake_s:
                                self._rehandshake_step += 1
                                self._last_rehandshake_at = now
                                if self._rehandshake_step == 2:
                                    log.info("Click %s : tentative de reprise 2/3 (réabonnement notifications)", self.side)
                                    try:
                                        await client.stop_notify(zwift_click.ZWIFT_ASYNC)
                                        await client.start_notify(zwift_click.ZWIFT_ASYNC, self._on_async)
                                    except Exception as exc:
                                        log.warning("Click %s : échec réabonnement : %s", self.side, exc)
                                elif self._rehandshake_step == 3:
                                    log.info("Click %s : tentative de reprise 3/3 (déconnexion et reconnexion)", self.side)
                                    try:
                                        await client.disconnect()
                                    except Exception as exc:
                                        log.warning("Click %s : échec déconnexion : %s", self.side, exc)
                                    dropped.set()
                                    break

            self._drop_reason = ("lien perdu (rappel bleak)" if dropped.is_set()
                                 else "arrêt du core" if self._stop.is_set() else "fin de session")


# Clavier du terminal = Click, touche pour touche (lot O17, tableau du clavier de la spécification générale
# §7.1). Le terminal ne dit pas quand une touche est relâchée : la durée d'un appui n'est pas mesurable, les
# appuis longs passent par les synonymes (Page haut et bas, Maj+A, Entrée, Maj+Z) ; Échap vaut Y.
TERMINAL_KEYS: dict[str, InputEvent] = {
    "+": InputEvent.PLUS_SHORT, "=": InputEvent.PLUS_SHORT, "-": InputEvent.MINUS_SHORT,
    "\x1b[5~": InputEvent.PLUS_LONG, "\x1b[6~": InputEvent.MINUS_LONG,
    "a": InputEvent.A_SHORT, "A": InputEvent.A_LONG, "\r": InputEvent.A_LONG, "\n": InputEvent.A_LONG,
    "y": InputEvent.Y_SHORT, "Y": InputEvent.Y_SHORT, "\x1b": InputEvent.Y_SHORT,
    "z": InputEvent.Z_SHORT, "Z": InputEvent.Z_LONG,
    "\x1b[D": InputEvent.LEFT_SHORT, "\x1b[C": InputEvent.RIGHT_SHORT,
    "\x1b[A": InputEvent.UP_SHORT, "\x1b[B": InputEvent.DOWN_SHORT,
}


def split_terminal_keys(data: str) -> list[str]:
    """Découpe ce que le terminal a envoyé en touches : un caractère, ou une séquence d'échappement
    (`ESC [ … lettre ou ~`, `ESC O lettre` : flèches, Page haut et bas). Échap seul reste une touche."""
    keys: list[str] = []
    i = 0
    while i < len(data):
        if data[i] == "\x1b" and i + 1 < len(data) and data[i + 1] in "[O":
            j = i + 2
            while j < len(data) and not (data[j].isalpha() or data[j] == "~"):
                j += 1
            seq = data[i:j + 1]
            keys.append("\x1b[" + seq[2:] if seq[1] == "O" else seq)   # ESC O A (mode application) = ESC [ A
            i = j + 1
        else:
            keys.append(data[i])
            i += 1
    return keys


class KeyboardProvider:
    """Entrées au clavier du terminal du core (développement et repli) : TERMINAL_KEYS, sans Entrée."""

    KEYS = TERMINAL_KEYS
    status = "KEYBOARD"

    def __init__(self) -> None:
        self.events: asyncio.Queue[InputEvent] = asyncio.Queue()
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    def on_key(self, key: str) -> None:
        ev = self.KEYS.get(key)
        if ev is not None:
            self.events.put_nowait(ev)

    def on_data(self, data: str) -> None:
        for key in split_terminal_keys(data):
            self.on_key(key)

    async def run(self) -> None:
        if not sys.stdin.isatty():
            log.info("Pas de terminal interactif : entrées clavier désactivées")
            await self._stop.wait()
            return
        import os
        import termios
        import tty

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        loop = asyncio.get_running_loop()

        def on_readable() -> None:
            # Une séquence d'échappement arrive d'un bloc : tout lire d'un coup la garde entière.
            self.on_data(os.read(fd, 64).decode("utf-8", "replace"))

        try:
            tty.setcbreak(fd)
            loop.add_reader(fd, on_readable)
            log.info("Clavier = Click : + - (Page haut et bas : appui long), a A (ou Entrée), y (ou Échap), "
                     "z Z, flèches")
            await self._stop.wait()
        finally:
            loop.remove_reader(fd)
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


class SimClickKeyboard(KeyboardProvider):
    """Clavier du terminal qui appuie sur le Zwift Click simulé (`--input sim`).

    Mêmes touches que `KeyboardProvider`. Chaque appui passe par le Bluetooth simulé, sur le bouton du
    Click V2 qui donne l'événement (+, −, A, Y, Z, flèches ; appui court 0,12 s, long 1 s) : un boîtier
    endormi ou déconnecté perd l'appui, comme le vrai.
    """

    PRESSES = {ev: ("+" if ev.value.startswith("PLUS") else "-" if ev.value.startswith("MINUS")
                    else ev.value.rsplit("_", 1)[0], 1.0 if ev.value.endswith("_LONG") else 0.12)
               for ev in set(TERMINAL_KEYS.values())}

    def __init__(self, world: Any) -> None:
        super().__init__()
        self._world = world

    def on_key(self, key: str) -> None:
        press = self.PRESSES.get(self.KEYS.get(key))   # type: ignore[arg-type]
        if press is None:
            super().on_key(key)
            return
        asyncio.get_running_loop().create_task(self._world.press(*press))


class NullProvider:
    status = "KEYBOARD"

    def __init__(self) -> None:
        self.events: asyncio.Queue[InputEvent] = asyncio.Queue()
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        await self._stop.wait()
