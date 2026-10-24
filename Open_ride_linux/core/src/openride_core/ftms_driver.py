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
import re
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from . import ftms
from .ble_util import backoff_delays, ble_lock, default_client_factory, find_device, note_trainer_write
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
RELEASE_WRITE_TIMEOUT_S = 1.5  # chaque écriture du relâchement est bornée (arrêt jamais bloqué)
CP_RESPONSE_TIMEOUT_S = 1.0   # attente de l'indication 0x80 avant la commande suivante
MAX_CONTROL_RETRIES = 2  # reprises de contrôle tentées avant de déclarer le refus
DEFAULT_POWER_RANGE = (0.0, 2000.0)
ATT_RETRIES = 2          # renvois après une erreur ATT (3 essais en tout), lot M1
ATT_RETRY_DELAY_S = 0.25

_ATT_ERROR_RE = re.compile(r"ATT error:\s*0x([0-9a-f]{1,2})\b", re.IGNORECASE)


def att_error_code(exc: BaseException) -> int | None:
    """Code de l'erreur ATT lu dans le message BlueZ/bleak (« ... ATT error: 0x80 »).

    None pour toute autre exception (liaison perdue, délai dépassé, etc.) : celles-là
    déclenchent la reconnexion, sans renvoi.
    """
    m = _ATT_ERROR_RE.search(str(exc))
    return int(m.group(1), 16) if m else None


class ControlPoint:
    """Fitness Machine Control Point (0x2AD9) : une procédure à la fois (FTMS §4.16.3).

    Une procédure n'est finie qu'à l'indication de réponse (0x80) ; écrire avant expose à
    l'erreur ATT « Procedure Already In Progress ». Chaque écriture attend donc cette
    indication, au plus `CP_RESPONSE_TIMEOUT_S`, puis on continue même sans réponse.
    """

    def __init__(self, client: Any,
                 on_response: Callable[[ftms.ControlResponse], None] | None = None) -> None:
        self.client = client
        self._on_response = on_response
        self._waiting: tuple[int, asyncio.Future] | None = None
        self._idle = asyncio.Event()   # aucune procédure en attente de sa réponse 0x80
        self._idle.set()

    async def enable(self) -> None:
        """Abonnement aux indications : obligatoire avant toute écriture (FTMS §4.16.3)."""
        await self.client.start_notify(ftms.CONTROL_POINT, self.on_indication)

    def on_indication(self, _ch: Any, data: bytearray) -> None:
        resp = ftms.parse_control_response(bytes(data))
        if resp is None:
            return
        self._idle.set()
        if self._waiting is not None:
            op, fut = self._waiting
            if op == resp.request_op and not fut.done():
                fut.set_result(resp)
        if self._on_response is not None:
            self._on_response(resp)

    async def call(self, payload: bytes, write_timeout: float | None = None) -> ftms.ControlResponse | None:
        """Écrit une commande et attend sa réponse ; None si le trainer n'a pas répondu à temps."""
        fut = asyncio.get_running_loop().create_future()
        self._waiting = (payload[0], fut)
        try:
            note_trainer_write()
            self._idle.clear()
            write = self.client.write_gatt_char(ftms.CONTROL_POINT, payload, response=True)
            if write_timeout is None:
                await write
            else:
                await asyncio.wait_for(write, timeout=write_timeout)
            try:
                return await asyncio.wait_for(fut, timeout=CP_RESPONSE_TIMEOUT_S)
            except asyncio.TimeoutError:
                log.info("Pas de réponse du Control Point à 0x%02x", payload[0])
                return None
        finally:
            self._waiting = None

    async def wait_idle(self, timeout: float = CP_RESPONSE_TIMEOUT_S) -> bool:
        """Attend la réponse 0x80 de la procédure en cours (au plus `timeout`) ; False sinon."""
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False


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
        self._forgotten = 0   # compte les oublis de consigne (contrôle perdu ou refusé), voir _forget_sent
        self._immediate = False   # consigne de braquet en attente d'envoi (voir set_sim_grade)
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
        self._refusals = 0
        self.power_range = DEFAULT_POWER_RANGE   # remplacée par la plage annoncée (0x2AD8)
        self.power_increment = 1.0
        self.supports_sim = True
        self.supports_erg = True
        self.reconnect_count = 0
        self.att_retries = 0   # renvois après une erreur ATT ponctuelle (lot M1)

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
        lo, hi = self.power_range
        watts = min(max(float(watts), lo), hi)
        if self.power_increment > 1.0:   # multiple du pas annoncé, sans sortir de la plage
            steps = math.floor((watts - lo) / self.power_increment + 0.5)
            watts = min(lo + steps * self.power_increment, hi)
        self._want = _Want("erg", watts)
        return True

    def reset_control(self) -> None:
        """Oublie un refus de contrôle et force une nouvelle prise de contrôle."""
        self._refusals = 0
        self.control_refused = False
        self._forget_sent()

    def _forget_sent(self) -> None:
        """Force une nouvelle prise de contrôle et le renvoi de la consigne.

        Souvent appelé pendant qu'une commande attend sa réponse (refus 0x05, état 0xFF) :
        `_flush_command` ne doit pas alors réécrire `_last_sent` au retour de l'écriture, sinon
        la reprise de contrôle n'a jamais lieu (trouvé avec le Bluetooth simulé, ble_sim.py).
        """
        self._last_sent = None
        self._forgotten += 1

    def set_sim_grade(self, grade_pct: float, immediate: bool = False) -> bool:
        """`immediate` : changement de braquet, envoyé même sous GRADE_EPSILON_PCT (sans attendre
        le renvoi de RESEND_S, qui retardait jusqu'à 2 s un petit braquet sur le plat)."""
        lo, hi = self.cfg.grade_min_pct, self.cfg.grade_max_pct
        self._want = _Want("sim", min(max(float(grade_pct), lo), hi))
        self._immediate = self._immediate or immediate
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
        if d.heart_rate_bpm is not None:   # absent d'une trame partielle : on garde la valeur
            self._hr_ibd = d.heart_rate_bpm or None   # 0 = pas de mesure

    def _on_hr(self, _ch: Any, data: bytearray) -> None:
        try:
            bpm = ftms.parse_hr_measurement(bytes(data))
        except Exception:
            return
        self._hr_service = bpm or None

    def _on_status(self, _ch: Any, data: bytearray) -> None:
        status = ftms.parse_machine_status(bytes(data))
        if status is None:
            return
        code, name = status
        if code == ftms.STATUS_CONTROL_LOST:
            # Contrôle retiré (autre application, interface du trainer) : on le redemande à la
            # prochaine consigne ; un refus passe ensuite par le compteur de `_on_response`.
            log.warning("Trainer : contrôle FTMS perdu (Fitness Machine Status 0xFF)")
            self._forget_sent()
        elif code == 0x01:
            log.info("Trainer : consignes remises à zéro par un tiers (Reset), renvoi")
            self._forget_sent()
        elif code in (0x02, 0x03):
            # Arrêt voulu sur le trainer (ou clé de sécurité) : pas de redémarrage forcé.
            log.info("Trainer : état machine %s", name)
        else:
            log.debug("Trainer : état machine %s %s", name, bytes(data[1:]).hex())

    def _on_response(self, resp: ftms.ControlResponse) -> None:
        if resp.ok:
            # Seule une consigne acceptée prouve que le contrôle est retrouvé : une prise de
            # contrôle acceptée suivie d'une consigne refusée ne doit pas remettre le compteur à 0.
            if resp.request_op in (ftms.OP_SET_SIM_PARAMS, ftms.OP_SET_TARGET_POWER):
                self._refusals = 0
                self.control_refused = False
            return
        if resp.request_op == ftms.OP_START_RESUME:
            # « Démarrer » refusé = le trainer tourne déjà (mesuré sur le HomeTrainer) : sans gravité.
            log.debug("Start/Resume refusé (%s) : trainer déjà démarré", resp.result_name)
            return
        if resp.request_op == ftms.OP_RESET:
            # Reset refusé : la déconnexion qui suit rend quand même le contrôle.
            log.debug("Reset refusé (%s)", resp.result_name)
            return
        log.warning("Commande 0x%02x refusée : %s", resp.request_op, resp.result_name)
        if resp.result == 0x05:  # CONTROL_NOT_PERMITTED : le contrôle a été perdu
            self._refusals += 1
            if self._refusals > MAX_CONTROL_RETRIES:
                # Deux reprises de contrôle ont échoué : la session passera en ERROR.
                self.control_refused = True
            else:
                self._forget_sent()   # forcera une nouvelle prise de contrôle

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
        if self.reconnect_count or self.att_retries:
            log.info("Trainer : %d reconnexion(s), %d renvoi(s) après erreur ATT.",
                     self.reconnect_count, self.att_retries)

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
            if services.get_characteristic(ftms.SUPPORTED_POWER_RANGE) is not None:
                pr = ftms.parse_power_range(
                    bytes(await client.read_gatt_char(ftms.SUPPORTED_POWER_RANGE)))
                if pr.max_w > pr.min_w:
                    self.power_range = (float(max(pr.min_w, 0)), float(pr.max_w))
                    self.power_increment = float(max(pr.increment_w, 1))
                    log.info("Plage de puissance du trainer : %d à %d W, pas de %d W",
                             pr.min_w, pr.max_w, pr.increment_w)
            cp: ControlPoint | None = None
            if services.get_characteristic(ftms.CONTROL_POINT) is not None:
                cp = ControlPoint(client, self._on_response)
                await cp.enable()
            else:
                log.warning("Trainer sans Control Point FTMS : mesures seules, aucune consigne")
            if services.get_characteristic(ftms.MACHINE_STATUS) is not None:
                await client.start_notify(ftms.MACHINE_STATUS, self._on_status)
            await client.start_notify(ftms.INDOOR_BIKE_DATA, self._on_ibd)
            if services.get_characteristic(ftms.HR_MEASUREMENT) is not None:
                await client.start_notify(ftms.HR_MEASUREMENT, self._on_hr)

            self._last_data_at = self._clock()
            self._link_up = self._ever_connected = True
            self._last_sent = None
            log.info("Trainer connecté (%s)", getattr(dev, "name", dev))
            try:
                if cp is not None:
                    await self._take_control(cp)
                while not (dropped.is_set() or self._stop.is_set()):
                    if self._clock() - (self._last_data_at or 0.0) > FORCE_RECONNECT_S:
                        raise ConnectionError("plus de données du trainer")
                    if cp is not None:
                        await self._flush_command(cp)
                    await asyncio.sleep(0.05)
            finally:
                self._link_up = False
                if cp is not None and client.is_connected:
                    await self._release(cp)

    async def _take_control(self, cp: ControlPoint) -> None:
        await self._call_retrying(cp, ftms.cmd_request_control)
        await self._call_retrying(cp, ftms.cmd_start_resume)

    async def _call_retrying(self, cp: ControlPoint, build: Callable[[], bytes]) -> None:
        """Écrit `build()` ; renvoie après une erreur ATT ponctuelle, au plus ATT_RETRIES fois.

        `build` est rappelé à chaque essai : un renvoi porte la consigne la plus récente. Toute
        autre exception, ou une erreur ATT au troisième essai, remonte jusqu'à `run` (reconnexion).
        """
        attempt = 0
        while True:
            payload = build()
            try:
                await cp.call(payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                code = att_error_code(exc)
                if code is None or attempt >= ATT_RETRIES:
                    raise
                attempt += 1
                self.att_retries += 1
                log.warning("Trainer : écriture 0x%02x refusée (ATT 0x%02x), renvoi %d/%d",
                            payload[0], code, attempt, ATT_RETRIES)
                if code == ftms.ATT_PROCEDURE_IN_PROGRESS:
                    await cp.wait_idle()   # fin de la procédure en cours d'abord
                elif code == ftms.ATT_CCCD_IMPROPERLY_CONFIGURED:
                    await cp.enable()      # indications à nouveau demandées
                await asyncio.sleep(ATT_RETRY_DELAY_S)
                continue
            if attempt:
                log.info("Trainer : écriture 0x%02x acceptée au renvoi %d", payload[0], attempt)
            return

    async def _flush_command(self, cp: ControlPoint) -> None:
        now = self._clock()
        if now - self._last_sent_at < MIN_SEND_INTERVAL_S:
            return
        mode, value = self._want.mode, self._want.value
        prev = self._last_sent
        eps = GRADE_EPSILON_PCT if mode == "sim" else ERG_EPSILON_W
        changed = prev is None or prev[0] != mode or abs(prev[1] - value) >= eps
        changed = changed or (self._immediate and mode == "sim" and prev[1] != value)
        self._immediate = False
        if not changed and now - self._last_sent_at < RESEND_S:
            return
        supported = self.supports_erg if mode == "erg" else self.supports_sim
        if not supported:   # opcode exclu par Fitness Machine Feature (FTMS tableau 4.15)
            if prev != (mode, value):
                log.warning("Trainer : mode %s non annoncé (Fitness Machine Feature), consigne "
                            "non envoyée", mode.upper())
            self._last_sent, self._last_sent_at = (mode, value), now
            return
        forgotten = self._forgotten
        if prev is None:   # première consigne ou contrôle perdu
            await self._take_control(cp)
        sent = (mode, value)

        def build() -> bytes:
            nonlocal sent
            want = self._want   # au renvoi : la consigne la plus récente, du même mode
            if want.mode != mode:
                want = _Want(mode, value)
            sent = (want.mode, want.value)
            if want.mode == "erg":
                return ftms.cmd_set_target_power(want.value)
            return ftms.cmd_set_sim_params(want.value, self._crr, self._cw)

        await self._call_retrying(cp, build)
        self._last_sent_at = now
        if self._forgotten == forgotten:   # sinon refus ou contrôle perdu pendant l'écriture
            self._last_sent = sent

    async def _release(self, cp: ControlPoint) -> None:
        """Rend le trainer libre en partant, même après une erreur.

        Pente 0 % d'abord (aucune consigne ERG ne reste active), puis Reset, qui retire le
        contrôle FTMS à OpenRide : une autre application peut le prendre aussitôt. Chaque
        écriture est bornée dans le temps ; la déconnexion BLE suit (sortie du `async with`).
        """
        await release_control(cp, self._crr, self._cw, sim=self.supports_sim)


async def release_control(cp: ControlPoint, crr: float = 0.004, cw_kg_m: float = 0.20,
                          sim: bool = True) -> bool:
    """Pente 0 % (si le mode SIM existe) puis Reset ; True si les écritures ont abouti.

    Le Reset suffirait (il remet les consignes à leur valeur par défaut, FTMS §4.16.2.2) ; la
    pente 0 % est une sécurité si le Reset est refusé. Chaque commande attend sa réponse avant
    la suivante, sinon le Reset risquerait l'erreur « Procedure Already In Progress ».
    """
    ok = True
    steps = [("reset (contrôle rendu)", ftms.cmd_reset())]
    if sim:
        steps.insert(0, ("pente 0 %", ftms.cmd_set_sim_params(0.0, crr, cw_kg_m)))
    for label, payload in steps:
        try:
            await cp.call(payload, write_timeout=RELEASE_WRITE_TIMEOUT_S)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            ok = False
            log.warning("Relâche du trainer, %s impossible : %s", label, exc or type(exc).__name__)
    if ok:
        log.info("Trainer relâché : pente 0 %, contrôle FTMS rendu.")
    return ok


async def release_trainer(
    trainer: TrainerConfig,
    bike: BikeConfig,
    address: str | None = None,
    *,
    device_finder: Callable[[str, str | None, float], Awaitable[Any]] = find_device,
    client_factory: Callable[..., Any] = default_client_factory,
) -> bool:
    """Dépannage : se connecte au trainer, annule toute consigne, rend le contrôle et déconnecte.

    Sert après un arrêt brutal du core (processus tué, PC éteint en pleine séance) : BlueZ peut
    garder la liaison ouverte et le trainer reste alors réservé. La connexion reprend cette
    liaison (appareil connu de BlueZ) puis la ferme proprement.
    """
    async with ble_lock():
        dev = await device_finder(trainer.device_name, address or None, 8.0)
        if dev is None:
            log.warning("Trainer introuvable : il est déjà libre ou éteint.")
            return False
        async with client_factory(dev, timeout=15.0) as client:
            if client.services.get_characteristic(ftms.CONTROL_POINT) is None:
                log.warning("Pas de Control Point FTMS sur cet appareil.")
                return False
            cp = ControlPoint(client)
            try:
                # Sans abonnement aux indications, le trainer doit refuser toute écriture
                # (erreur ATT 0xFD, FTMS §4.16.3).
                await cp.enable()
                await cp.call(ftms.cmd_request_control(), write_timeout=RELEASE_WRITE_TIMEOUT_S)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.debug("Prise de contrôle avant relâche refusée : %s", exc)
            ok = await release_control(cp, bike.crr, 0.5 * RHO0 * bike.cda_m2)
    log.info("Trainer déconnecté.")
    return ok
