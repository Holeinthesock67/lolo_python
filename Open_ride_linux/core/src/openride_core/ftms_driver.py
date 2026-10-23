"""Pilote réel du home trainer FTMS (HomeTrainer), SRS §4.1.

Même interface que `MockDriver` (poll / set_target_power / set_sim_grade) pour que la boucle
du core ne change pas. Toute la partie BLE tourne dans `run()` (tâche asyncio) ; `poll()` est
synchrone et ne fait que lire le dernier état.

Points mesurés au sprint 0 : Indoor Bike Data ~1 Hz au repos, ~8 Hz après des commandes SIM ;
puissance 0 à 1000 W ; FC à 0 = pas de mesure (-> None).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from . import ftms
from .ble_util import backoff_delays, ble_lock, default_client_factory, find_device
from .config import BikeConfig, TrainerConfig
from .mock_driver import TrainerMetrics
from .physics import RHO0

log = logging.getLogger("ftms_driver")

STALE_S = 3.0            # sans donnée au-delà : trainer considéré perdu (contrat IPC §6)
FORCE_RECONNECT_S = 10.0  # sans donnée au-delà : on coupe et on reconnecte
RESEND_S = 2.0           # la consigne est renvoyée au moins toutes les 2 s
MIN_SEND_INTERVAL_S = 0.2
GRADE_EPSILON_PCT = 0.1
ERG_EPSILON_W = 1.0


@dataclass
class _Want:
    mode: str = "sim"   # "sim" ou "erg"
    value: float = 0.0


class FtmsDriver:
    def __init__(
        self,
        trainer: TrainerConfig,
        bike: BikeConfig,
        address: str | None = None,
        *,
        device_finder: Callable[[str, str | None, float], Awaitable[Any]] = find_device,
        client_factory: Callable[..., Any] = default_client_factory,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cfg = trainer
        self.address = address or None
        self._find = device_finder
        self._client_factory = client_factory
        self._clock = clock
        # Cw = 0,5 · ρ · CdA (kg/m), cf. ftms.cmd_set_sim_params.
        self._crr = bike.crr
        self._cw = 0.5 * RHO0 * bike.cda_m2

        self._want = _Want()
        self._last_sent: tuple[str, float] | None = None
        self._last_sent_at = 0.0
        self._stop = asyncio.Event()

        self._link_up = False
        self._ever_connected = False
        self._last_data_at: float | None = None
        self._raw_power = 0.0
        self._power = 0.0
        self._cadence = 0.0
        self._hr_ibd: int | None = None
        self._hr_service: int | None = None
        self._last_poll_at: float | None = None
        self.control_refused = False
        self.supports_sim = True
        self.supports_erg = True
        self.reconnect_count = 0

    # --- interface synchrone, commune avec MockDriver ---------------------------------

    @property
    def status(self) -> str:
        """Valeur de `trainer_status` du contrat IPC."""
        if self._link_up and self._fresh():
            return "CONNECTED"
        return "LOST" if self._ever_connected else "RECONNECTING"

    def _fresh(self) -> bool:
        return self._last_data_at is not None and self._clock() - self._last_data_at <= STALE_S

    def set_target_power(self, watts: float) -> bool:
        self._want = _Want("erg", max(0.0, float(watts)))
        return True

    def set_sim_grade(self, grade_pct: float) -> bool:
        lo, hi = self.cfg.grade_min_pct, self.cfg.grade_max_pct
        self._want = _Want("sim", min(max(float(grade_pct), lo), hi))
        return True

    def poll(self, t_session: float = 0.0) -> TrainerMetrics:
        now = self._clock()
        dt = 0.0 if self._last_poll_at is None else max(now - self._last_poll_at, 0.0)
        self._last_poll_at = now
        connected = self.status == "CONNECTED"
        if not connected:
            self._power = 0.0
            return TrainerMetrics(connected=False)
        # Lissage temporel : le résultat ne dépend ni de la cadence de poll ni de celle du BLE.
        tau = self.cfg.power_smooth_tau_s
        alpha = 1.0 if tau <= 0 else 1.0 - math.exp(-dt / tau)
        self._power += alpha * (self._raw_power - self._power)
        hr = self._hr_service if self._hr_service else self._hr_ibd
        return TrainerMetrics(
            power_w=round(self._power, 1),
            cadence_rpm=self._cadence,
            speed_kmh=0.0,   # la vitesse virtuelle vient de la physique du core
            hr_bpm=hr,
            connected=True,
        )

    def stop(self) -> None:
        self._stop.set()

    # --- notifications ----------------------------------------------------------------

    def _on_ibd(self, _ch: Any, data: bytearray) -> None:
        try:
            d = ftms.parse_indoor_bike_data(bytes(data))
        except Exception:
            log.warning("Indoor Bike Data illisible : %s", bytes(data).hex())
            return
        self._last_data_at = self._clock()
        if d.power_w is not None:
            self._raw_power = max(float(d.power_w), 0.0)
        if d.cadence_rpm is not None:
            self._cadence = d.cadence_rpm
        self._hr_ibd = d.heart_rate_bpm or None   # 0 = pas de mesure

    def _on_hr(self, _ch: Any, data: bytearray) -> None:
        try:
            bpm = ftms.parse_hr_measurement(bytes(data))
        except Exception:
            return
        self._hr_service = bpm or None

    def _on_cp(self, _ch: Any, data: bytearray) -> None:
        resp = ftms.parse_control_response(bytes(data))
        if resp is None:
            return
        if resp.ok:
            self.control_refused = False
            return
        if resp.request_op == ftms.OP_START_RESUME:
            # « Démarrer » refusé = le trainer tourne déjà (mesuré sur le HomeTrainer) : sans gravité.
            log.debug("Start/Resume refusé (%s) : trainer déjà démarré", resp.result_name)
            return
        log.warning("Commande 0x%02x refusée : %s", resp.request_op, resp.result_name)
        if resp.result == 0x05:  # CONTROL_NOT_PERMITTED : le contrôle a été perdu
            self.control_refused = True
            self._last_sent = None   # forcera la reprise du contrôle

    # --- boucle de connexion ----------------------------------------------------------

    async def run(self) -> None:
        delays = backoff_delays()
        while not self._stop.is_set():
            try:
                await self._session()
                delays = backoff_delays()   # connexion réussie puis perdue : on repart à 1 s
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("Trainer : %s", exc)
            self._link_up = False
            if self._stop.is_set():
                break
            self.reconnect_count += 1
            delay = next(delays)
            log.info("Reconnexion au trainer dans %.0f s", delay)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def _session(self) -> None:
        loop = asyncio.get_running_loop()
        dropped = asyncio.Event()

        def on_disconnect(_client: Any) -> None:
            loop.call_soon_threadsafe(dropped.set)

        async with AsyncExitStack() as stack:
            async with ble_lock():   # un seul scan/connexion BLE à la fois (BlueZ)
                dev = await self._find(self.cfg.device_name, self.address, 8.0)
                if dev is None:
                    raise ConnectionError("trainer introuvable")
                client = await stack.enter_async_context(
                    self._client_factory(dev, disconnected_callback=on_disconnect, timeout=15.0))
            services = client.services
            if services.get_characteristic(ftms.INDOOR_BIKE_DATA) is None:
                raise ConnectionError("pas de service FTMS sur cet appareil")
            if services.get_characteristic(ftms.FEATURE) is not None:
                feats = ftms.parse_features(bytes(await client.read_gatt_char(ftms.FEATURE)))
                self.supports_sim, self.supports_erg = feats.supports_sim, feats.supports_erg
            await client.start_notify(ftms.CONTROL_POINT, self._on_cp)
            await client.start_notify(ftms.INDOOR_BIKE_DATA, self._on_ibd)
            if services.get_characteristic(ftms.HR_MEASUREMENT) is not None:
                await client.start_notify(ftms.HR_MEASUREMENT, self._on_hr)

            self._last_data_at = self._clock()
            self._link_up = self._ever_connected = True
            self._last_sent = None
            log.info("Trainer connecté (%s)", getattr(dev, "name", dev))
            try:
                await self._take_control(client)
                while not (dropped.is_set() or self._stop.is_set()):
                    if self._clock() - (self._last_data_at or 0.0) > FORCE_RECONNECT_S:
                        raise ConnectionError("plus de données du trainer")
                    await self._flush_command(client)
                    await asyncio.sleep(0.05)
            finally:
                self._link_up = False
                if client.is_connected:
                    await self._release(client)

    async def _write(self, client: Any, payload: bytes) -> None:
        await client.write_gatt_char(ftms.CONTROL_POINT, payload, response=True)

    async def _take_control(self, client: Any) -> None:
        await self._write(client, ftms.cmd_request_control())
        await self._write(client, ftms.cmd_start_resume())

    async def _flush_command(self, client: Any) -> None:
        now = self._clock()
        if now - self._last_sent_at < MIN_SEND_INTERVAL_S:
            return
        mode, value = self._want.mode, self._want.value
        prev = self._last_sent
        eps = GRADE_EPSILON_PCT if mode == "sim" else ERG_EPSILON_W
        changed = prev is None or prev[0] != mode or abs(prev[1] - value) >= eps
        if not changed and now - self._last_sent_at < RESEND_S:
            return
        if prev is None:   # première consigne ou contrôle perdu
            await self._take_control(client)
        if mode == "erg":
            payload = ftms.cmd_set_target_power(value)
        else:
            payload = ftms.cmd_set_sim_params(value, self._crr, self._cw)
        await self._write(client, payload)
        self._last_sent, self._last_sent_at = (mode, value), now

    async def _release(self, client: Any) -> None:
        """Relâche la résistance en partant (pente 0 %), même après une erreur."""
        try:
            await self._write(client, ftms.cmd_set_sim_params(0.0, self._crr, self._cw))
        except Exception as exc:
            log.debug("Relâche de la résistance impossible : %s", exc)
