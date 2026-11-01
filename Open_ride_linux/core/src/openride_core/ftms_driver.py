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
import struct
import re
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from . import ftms, latency_log
from .ble_util import backoff_delays, ble_lock, default_client_factory, find_device, note_trainer_write
from .config import BikeConfig, TrainerConfig
from .mock_driver import TrainerMetrics
from .physics import G, RHO0

log = logging.getLogger("ftms_driver")

STALE_S = 3.0            # sans donnée au-delà : trainer considéré perdu (contrat IPC §6)
FORCE_RECONNECT_S = 10.0  # sans donnée au-delà : on coupe et on reconnecte
RESEND_S = 2.0           # valeur par défaut de [trainer] resend_s : consigne renvoyée au moins toutes les 2 s
MIN_SEND_INTERVAL_S = 0.2
GRADE_EPSILON_PCT = 0.1
TRACE_IBD_EVERY_S = 0.9   # avec trace_ftms : une ligne de mesures par notification Indoor Bike Data (≈ 1 Hz)
# Frein lâché par le trainer (29 octobre : 449 W puis 0 W en 2 s, à 73 tr/min et 31 km/h, sans erreur
# ni statut) : puissance qui passe de plus de BRAKE_LOSS_FROM_W à moins de BRAKE_LOSS_TO_W en
# BRAKE_LOSS_WINDOW_S, pédales et volant encore en mouvement ; une reprise de contrôle au plus
# toutes les BRAKE_LOSS_COOLDOWN_S.
BRAKE_LOSS_FROM_W = 200.0
BRAKE_LOSS_TO_W = 10.0
BRAKE_LOSS_WINDOW_S = 3.0
BRAKE_LOSS_MIN_RPM = 40.0
BRAKE_LOSS_MIN_KMH = 15.0
BRAKE_LOSS_COOLDOWN_S = 10.0
BRAKE_BACK_W = 50.0   # puissance qui revient après la reprise : le frein est revenu
BRAKE_BACK_WINDOW_S = 15.0
ERG_EPSILON_W = 1.0
RELEASE_WRITE_TIMEOUT_S = 1.5  # chaque écriture du relâchement est bornée (arrêt jamais bloqué)
CP_RESPONSE_TIMEOUT_S = 1.0   # attente de l'indication 0x80 avant la commande suivante
MAX_CONTROL_RETRIES = 2  # reprises de contrôle tentées avant de déclarer le refus
DEFAULT_POWER_RANGE = (0.0, 2000.0)
# Consigne de résistance (lot RC1, étude « résistance calculée par le core », 31 octobre) : exprimée en %
# de la plage annoncée (0x2AD6), comme les « 32 % » de l'appli du fabricant ; plage FTMS par défaut
# 0 à 100 au pas de 1 si le trainer n'en annonce pas.
DEFAULT_RESISTANCE_RANGE = (0.0, 100.0, 1.0)
RESISTANCE_EPSILON = 0.05   # écart de niveau en dessous duquel la consigne n'est pas renvoyée
# Résistance calculée par le core (lots RC2-RC3, [trainer] control = "resistance") : la pente SIM
# (braquet, difficulté, vent et abri compris) n'est plus envoyée en 0x11 ; le pilote calcule lui-même la
# force que le trainer appliquerait en SIM à la vitesse de son volant, m g (sin θ + Crr cos θ) + ½ Cw v²,
# avec la masse du profil, et l'envoie comme niveau de résistance 0x04. Le trainer ne simule plus l'élan
# du vélo (phase à 0 W après un sprint, essais 7bk). Étalonnage 7rc1 (1er novembre, 70, 85 et 100 tr/min,
# 10 à 60 %) : le frein du trainer en mode résistance est proportionnel au niveau ET à la vitesse du
# volant, F ≈ k × niveau (%) × v (km/h), k ≈ 0,036 N (0,0355 à 0,0363 sur tous les paliers, décalage
# nul), soit P ≈ 0,01 × niveau × v². Une force fixe par % donnait un niveau 60 % trop fort en relance
# au-delà de 40 km/h. Le niveau envoyé est donc F / (k × v), v borné à ROAD_MIN_KMH au départ arrêté ;
# k part de [trainer] resistance_n_per_pct_kmh et se corrige en roulant sur la force mesurée (puissance
# / vitesse du volant), seulement quand le volant ne prend ni ne perd de vitesse.
ROAD_ADAPT_TAU_S = 5.0        # constante de temps de la correction de k
ROAD_MIN_KMH = 10.0           # vitesse du volant plancher du calcul du niveau (départ arrêté : F / (k × v) diverge)
ROAD_ADAPT_MIN_MPS = 3.0      # volant assez rapide pour mesurer la force
ROAD_ADAPT_MIN_W = 30.0
ROAD_ADAPT_MAX_ACCEL = 0.4    # m/s² : au-delà, la puissance accélère le volant, pas le frein
ROAD_ADAPT_RANGE = (0.2, 5.0) # bornes de la correction (× la valeur de départ)
DEFAULT_ROAD_MASS_KG = 84.0   # masse sans profil (PhysicsParams), remplacée par la session
ATT_RETRIES = 2          # renvois après une erreur ATT (3 essais en tout), lot M1
ATT_RETRY_DELAY_S = 0.25   # doublé à chaque renvoi : 0,25 s puis 0,5 s
CP_BUSY_GRACE_S = 0.5    # procédure précédente restée sans réponse : attente de plus avant d'écrire
# « Control Point occupé » : 0xFE (Procedure Already In Progress, FTMS) et 0x80, erreur applicative
# renvoyée par le HomeTrainer (24 et 28 octobre ; le 28, en même temps que la montre Garmin).
# La liaison reste ouverte : la consigne la plus récente est réessayée avec un délai croissant.
CP_BUSY_CODES = frozenset({0x80, ftms.ATT_PROCEDURE_IN_PROGRESS})
CP_BUSY_BACKOFF_S = (0.5, 1.0, 2.0, 4.0)
RELEASE_BUSY_RETRIES = 3   # relâche sur un Control Point occupé : 0,25, 0,5 puis 1 s d'attente

_ATT_ERROR_RE = re.compile(r"ATT error:\s*0x([0-9a-f]{1,2})\b", re.IGNORECASE)


class ControlPointBusy(Exception):
    """Écriture refusée par un Control Point occupé (CP_BUSY_CODES) après tous les renvois."""

    def __init__(self, op: int, code: int) -> None:
        super().__init__(f"Control Point occupé (ATT 0x{code:02x} sur 0x{op:02x})")
        self.op, self.code = op, code


def att_error_code(exc: BaseException) -> int | None:
    """Code de l'erreur ATT lu dans le message BlueZ/bleak (« ... ATT error: 0x80 »).

    None pour toute autre exception (liaison perdue, délai dépassé, etc.) : celles-là
    déclenchent la reconnexion, sans renvoi.
    """
    m = _ATT_ERROR_RE.search(str(exc))
    return int(m.group(1), 16) if m else None



OP_NAMES: dict[int, str] = {
    ftms.OP_REQUEST_CONTROL: "REQUEST_CONTROL",
    ftms.OP_RESET: "RESET",
    ftms.OP_SET_TARGET_RESISTANCE: "RESISTANCE",
    ftms.OP_SET_TARGET_POWER: "ERG",
    ftms.OP_START_RESUME: "START_RESUME",
    ftms.OP_STOP_PAUSE: "STOP_PAUSE",
    ftms.OP_SET_SIM_PARAMS: "SIM",
}


def resistance_level(pct: float, lo: float, hi: float, step: float) -> float:
    """Niveau FTMS pour `pct` % de la plage [lo, hi], arrondi au pas annoncé et borné."""
    level = lo + min(max(float(pct), 0.0), 100.0) / 100.0 * (hi - lo)
    if step > 0:
        level = lo + math.floor((level - lo) / step + 0.5) * step
    return round(min(max(level, lo), hi), 1)


def describe_want(mode: str, value: float) -> str:
    """Consigne lisible pour le journal."""
    if mode == "erg":
        return f"{value:.0f} W"
    if mode == "resistance":
        return f"résistance niveau {value:g}"
    return f"pente {value:.2f} %"


def format_cp_write(payload: bytes) -> tuple[str, str, str]:
    """Décode une trame Control Point pour la trace (lot Q3).

    Renvoie (opération, valeurs_lisibles, représentation_hex).
    """
    if not payload:
        return "?", "", ""
    op = payload[0]
    if op == ftms.OP_REQUEST_CONTROL:
        return "REQUEST_CONTROL", "", "00"
    if op == ftms.OP_RESET:
        return "RESET", "", "01"
    if op == ftms.OP_START_RESUME:
        return "START_RESUME", "", "07"
    if op == ftms.OP_STOP_PAUSE:
        if len(payload) >= 2 and payload[1] == 0x01:
            return "STOP", "", "08 01"
        if len(payload) >= 2 and payload[1] == 0x02:
            return "PAUSE", "", "08 02"
        return "STOP_PAUSE", "", payload.hex(" ")
    if op == ftms.OP_SET_TARGET_RESISTANCE:
        if len(payload) >= 3:
            return "RESISTANCE", f"niveau {struct.unpack_from('<h', payload, 1)[0] / 10:g}", payload.hex(" ")
        if len(payload) == 2:
            return "RESISTANCE", f"niveau {payload[1] / 10:g}", payload.hex(" ")
        return "RESISTANCE", "", payload.hex(" ")
    if op == ftms.OP_SET_TARGET_POWER:
        if len(payload) >= 3:
            w = struct.unpack_from("<h", payload, 1)[0]
            return "ERG", f"cible {w} W", f"{payload[0:1].hex()} {payload[1:3].hex()}"
        return "ERG", "", payload.hex(" ")
    if op == ftms.OP_SET_SIM_PARAMS:
        if len(payload) >= 7:
            wind, grade, crr, cw = struct.unpack_from("<hhBB", payload, 1)
            grade_pct = grade / 100.0
            crr_val = crr / 10000.0
            cw_val = cw / 100.0
            vals = [f"pente {grade_pct:.2f} %", f"crr {crr_val:.4f}", f"cw {cw_val:.3f}"]
            if wind != 0:
                vals.insert(0, f"vent {wind / 1000.0:.1f} m/s")
            hex_parts = f"{payload[0:1].hex()} {payload[1:3].hex()} {payload[3:5].hex()} {payload[5:6].hex()} {payload[6:7].hex()}"
            return "SIM", " ".join(vals), hex_parts
        return "SIM", "", payload.hex(" ")
    return f"0x{op:02x}", "", payload.hex(" ")

class ControlPoint:
    """Fitness Machine Control Point (0x2AD9) : une procédure à la fois (FTMS §4.16.3).

    Une procédure n'est finie qu'à l'indication de réponse (0x80) ; écrire avant expose à
    l'erreur ATT « Procedure Already In Progress ». Chaque écriture attend donc cette
    indication, au plus `CP_RESPONSE_TIMEOUT_S`, puis on continue même sans réponse ; si elle
    manque encore, l'écriture suivante l'attend `CP_BUSY_GRACE_S` de plus avant de partir.
    """

    def __init__(self, client: Any,
                 on_response: Callable[[ftms.ControlResponse], None] | None = None,
                 *,
                 trace: bool = False,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.client = client
        self._on_response = on_response
        self.trace = trace
        self._clock = clock
        self._waiting: tuple[int, asyncio.Future] | None = None
        self._idle = asyncio.Event()   # aucune procédure en attente de sa réponse 0x80
        self._idle.set()
        self.last_calls: dict[int, float] = {}
        self.last_call_at: float = 0.0

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
        if not self._idle.is_set():   # réponse de la commande précédente encore attendue
            await self.wait_idle(CP_BUSY_GRACE_S)
        fut = asyncio.get_running_loop().create_future()
        self._waiting = (payload[0], fut)
        t_start = self._clock()
        self.last_calls[payload[0]] = t_start
        self.last_call_at = t_start
        try:
            note_trainer_write()
            was_idle = self._idle.is_set()
            latency_log.cp_written()   # lot X7 : étage « cp » des appuis qui attendent cette écriture
            self._idle.clear()
            if self.trace:
                op_name, vals, hex_str = format_cp_write(payload)
                args = f" {vals}" if vals else ""
                log.info("FTMS > %s%s (%s)", op_name, args, hex_str)
            write = self.client.write_gatt_char(ftms.CONTROL_POINT, payload, response=True)
            try:
                if write_timeout is None:
                    await write
                else:
                    await asyncio.wait_for(write, timeout=write_timeout)
            except BaseException:
                if was_idle:   # écriture refusée : aucune procédure lancée par celle-ci
                    self._idle.set()
                raise
            try:
                resp = await asyncio.wait_for(fut, timeout=CP_RESPONSE_TIMEOUT_S)
                if self.trace and resp is not None:
                    dt_ms = int(round((self._clock() - t_start) * 1000))
                    op_name = OP_NAMES.get(payload[0], f"0x{payload[0]:02x}")
                    log.info("FTMS < réponse %s %s en %d ms", op_name, resp.result_name, dt_ms)
                return resp
            except asyncio.TimeoutError:
                dt_ms = int(round((self._clock() - t_start) * 1000))
                if self.trace:
                    log.info("FTMS < sans réponse après %d ms", dt_ms)
                else:
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
    mode: str = "sim"   # "sim" (pente %), "erg" (W) ou "resistance" (niveau FTMS)
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
        self._cw = RHO0 * bike.cda_m2   # Cw FTMS = CdA × ρ, sans le ½ (voir ftms.cmd_set_sim_params)
        self._wind_mps = 0.0   # champ vent de la commande 0x11 ([wind] feel = "ftms", lot P2)

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
        self._trainer_speed_kmh: float | None = None
        self._trainer_resistance: int | None = None
        self._trace_ibd_at = float("-inf")
        self._last_brake_loss_at = float("-inf")
        self.event_sink: Callable[[dict], None] | None = None   # lignes `ftms` du journal (posé par la session)
        self.brake_losses = 0   # pertes de frein détectées (reprise de contrôle tentée à chacune)
        self._loaded_at = float("-inf")   # dernier instant à plus de BRAKE_LOSS_FROM_W
        self._loaded_w = 0.0
        self._brake_lost_at: float | None = None
        self._hr_ibd: int | None = None
        self._hr_service: int | None = None
        self._hr_relay_val: int | None = None
        self._hr_relay_last_change_at: float | None = None
        self._hr_frozen = False
        self._last_poll_at: float | None = None
        self.control_refused = False
        self._refusals = 0
        self.power_range = DEFAULT_POWER_RANGE   # remplacée par la plage annoncée (0x2AD8)
        self.power_increment = 1.0
        self.supports_sim = True
        self._cp: ControlPoint | None = None
        self.supports_erg = True
        self.supports_resistance = False   # vrai si Fitness Machine Feature annonce resistance_target
        self.resistance_range = DEFAULT_RESISTANCE_RANGE   # (min, max, pas), remplacée par 0x2AD6
        self.resistance_wide = True   # niveau sur un sint16 (False : uint8 de la norme, voir ftms.cmd_set_target_resistance)
        self.road_mass_kg = DEFAULT_ROAD_MASS_KG   # masse totale du profil (posée par la session)
        self.k_road = trainer.resistance_n_per_pct_kmh   # force du frein par % et par km/h du volant, corrigée en roulant
        self._road_speed: tuple[float, float] | None = None   # (instant, vitesse du volant m/s) précédents
        self._road_fallback_warned = False
        self.reconnect_count = 0
        self.att_retries = 0   # renvois après une erreur ATT ponctuelle (lot M1)
        # Control Point occupé (CP_BUSY_CODES) après les renvois : consigne gardée et réessayée.
        self.busy = False      # vrai jusqu'à la prochaine consigne acceptée (bandeau de l'engine)
        self.busy_deferrals = 0
        self._busy_streak = 0
        self._busy_retry_at = 0.0

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

    def set_resistance_pct(self, pct: float) -> bool:
        """Consigne de résistance en % de la plage annoncée (lot RC1), arrondie au pas du trainer.
        Refusée (False) si le trainer n'annonce pas resistance_target."""
        if not self.supports_resistance:
            log.warning("Trainer : consigne de résistance non annoncée (Fitness Machine Feature)")
            return False
        self._want = _Want("resistance", resistance_level(pct, *self.resistance_range))
        return True

    def _road_control(self) -> str | None:
        """Mode d'envoi de la pente SIM : "resistance" (niveau calculé), "erg" (puissance calculée,
        [trainer] control = "power") ou None (pente 0x11, SIM du trainer)."""
        mode = {"resistance": "resistance", "power": "erg"}.get(self.cfg.control)
        if mode is None:
            return None
        if not (self.supports_resistance if mode == "resistance" else self.supports_erg):
            if not self._road_fallback_warned:
                log.warning("Trainer : pilotage %s demandé mais consigne non annoncée, pilotage SIM gardé",
                            self.cfg.control)
                self._road_fallback_warned = True
            return None
        return mode

    def _road_value(self, mode: str, grade_pct: float) -> float:
        """Consigne calculée pour la pente : niveau de résistance ou puissance (force × vitesse du volant)."""
        if mode == "resistance":
            return self._road_level(grade_pct)
        speed = (self._trainer_speed_kmh or 0.0) / 3.6
        lo, hi = self.power_range
        return float(round(min(max(self.road_force_n(grade_pct, speed) * speed, lo), hi)))

    def road_force_n(self, grade_pct: float, speed_mps: float) -> float:
        """Force que le trainer appliquerait en SIM à la vitesse du volant : même formule, masse du profil."""
        theta = math.atan(grade_pct / 100.0)
        va = speed_mps + self._wind_mps
        return (self.road_mass_kg * G * (math.sin(theta) + self._crr * math.cos(theta))
                + 0.5 * self._cw * va * abs(va))

    def _road_level(self, grade_pct: float) -> float:
        """Niveau de résistance FTMS qui donne la force de la route au volant (0 en descente)."""
        kmh = self._trainer_speed_kmh or 0.0
        force = max(self.road_force_n(grade_pct, kmh / 3.6), 0.0)
        return resistance_level(force / (max(self.k_road, 1e-6) * max(kmh, ROAD_MIN_KMH)), *self.resistance_range)

    def _adapt_road(self, now: float, power_w: float) -> None:
        """Corrige k (force par % et par km/h) sur la force mesurée (puissance / vitesse du volant), volant stable."""
        speed = None if self._trainer_speed_kmh is None else self._trainer_speed_kmh / 3.6
        prev, self._road_speed = self._road_speed, (None if speed is None else (now, speed))
        sent = self._last_sent
        if (speed is None or prev is None or sent is None or sent[0] != "resistance"
                or self._road_control() != "resistance"):
            return
        dt = now - prev[0]
        lo, hi, _ = self.resistance_range
        pct = 100.0 * (sent[1] - lo) / (hi - lo) if hi > lo else 0.0
        if (dt <= 0 or speed < ROAD_ADAPT_MIN_MPS or power_w < ROAD_ADAPT_MIN_W or pct < 2.0
                or abs(speed - prev[1]) / dt > ROAD_ADAPT_MAX_ACCEL):
            return
        observed = power_w / speed / (pct * speed * 3.6)
        base = self.cfg.resistance_n_per_pct_kmh
        self.k_road += (observed - self.k_road) * (1.0 - math.exp(-dt / ROAD_ADAPT_TAU_S))
        self.k_road = min(max(self.k_road, base * ROAD_ADAPT_RANGE[0]), base * ROAD_ADAPT_RANGE[1])

    def set_sim_grade(self, grade_pct: float, immediate: bool = False) -> bool:
        """`immediate` : changement de braquet, envoyé même sous GRADE_EPSILON_PCT (sans attendre
        le renvoi de RESEND_S, qui retardait jusqu'à 2 s un petit braquet sur le plat)."""
        lo, hi = self.cfg.grade_min_pct, self.cfg.grade_max_pct
        self._want = _Want("sim", min(max(float(grade_pct), lo), hi))
        self._immediate = self._immediate or immediate
        return True

    def set_wind(self, wind_mps: float) -> None:
        """Vent de face transmis avec la prochaine consigne SIM (au plus tard au renvoi)."""
        self._wind_mps = float(wind_mps)

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
        self._check_hr_freeze(now)
        effective = self._hr_service if self._hr_service is not None else self._hr_ibd
        hr = None if self._hr_frozen else effective
        return TrainerMetrics(
            power_w=round(self._power, 1),
            cadence_rpm=self._cadence,
            speed_kmh=0.0,   # la vitesse virtuelle vient de la physique du core
            hr_bpm=hr,
            connected=True,
            hr_frozen=self._hr_frozen,
        )

    def stop(self) -> None:
        self._stop.set()

    # --- notifications ----------------------------------------------------------------

    def _check_hr_freeze(self, now: float) -> None:
        if self._hr_relay_val is not None and not self._hr_frozen:
            if self._hr_relay_last_change_at is not None:
                if now - self._hr_relay_last_change_at >= self.cfg.hr_relay_freeze_s:
                    self._hr_frozen = True
                    log.warning(
                        "Cardio relayée par le trainer figée à %d bpm depuis %.0f s : ignorée",
                        self._hr_relay_val,
                        self.cfg.hr_relay_freeze_s,
                    )

    def _update_relayed_hr(self, candidate: int | None) -> None:
        now = self._clock()
        if candidate is None:
            self._hr_relay_val = None
            self._hr_relay_last_change_at = None
            self._hr_frozen = False
            return

        if self._hr_relay_val is None:
            self._hr_relay_val = candidate
            self._hr_relay_last_change_at = now
            self._hr_frozen = False
            return

        if candidate != self._hr_relay_val:
            if self._hr_frozen:
                self._hr_frozen = False
                log.info("Cardio relayée de nouveau valide")
            self._hr_relay_val = candidate
            self._hr_relay_last_change_at = now
        else:
            self._check_hr_freeze(now)

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
        if d.speed_kmh is not None:
            self._trainer_speed_kmh = d.speed_kmh
        if d.resistance_level is not None:
            self._trainer_resistance = d.resistance_level
        self._trace_ibd(self._last_data_at)
        if d.power_w is not None:
            self._check_brake_loss(self._last_data_at, max(float(d.power_w), 0.0))
            self._adapt_road(self._last_data_at, max(float(d.power_w), 0.0))
        if d.heart_rate_bpm is not None:   # absent d'une trame partielle : on garde la valeur
            self._hr_ibd = d.heart_rate_bpm or None   # 0 = pas de mesure
            self._update_relayed_hr(self._hr_service if self._hr_service is not None else self._hr_ibd)

    def _emit(self, event: str, **fields: Any) -> None:
        """Ligne `ftms` du journal JSONL (statuts du trainer, perte de frein) ; jamais bloquante."""
        if self.event_sink is None:
            return
        try:
            self.event_sink({"kind": "ftms", "ts": round(time.time(), 3), "event": event, **fields})
        except Exception:
            log.debug("Ligne ftms du journal perdue", exc_info=True)

    def _check_brake_loss(self, now: float, power_w: float) -> None:
        """Détecte un frein lâché par le trainer et tente une reprise du contrôle (voir BRAKE_LOSS_*)."""
        if power_w >= BRAKE_LOSS_FROM_W:
            self._loaded_at, self._loaded_w = now, power_w
        if self._brake_lost_at is not None:
            if power_w >= BRAKE_BACK_W and self._cadence >= BRAKE_LOSS_MIN_RPM:
                log.info("Trainer : puissance revenue (%.0f W) %.1f s après la reprise du contrôle",
                         power_w, now - self._brake_lost_at)
                self._emit("power_back", after_s=round(now - self._brake_lost_at, 1), power_w=round(power_w))
                self._brake_lost_at = None
            elif now - self._brake_lost_at > BRAKE_BACK_WINDOW_S:
                log.warning("Trainer : la puissance n'est pas revenue %.0f s après la reprise du contrôle",
                            BRAKE_BACK_WINDOW_S)
                self._emit("power_not_back", after_s=BRAKE_BACK_WINDOW_S)
                self._brake_lost_at = None
        want = self._want
        loaded = want.mode != "erg" or want.value >= 100.0   # ERG à 0 W (repos d'un bloc) : pas de frein attendu
        speed_ok = self._trainer_speed_kmh is None or self._trainer_speed_kmh >= BRAKE_LOSS_MIN_KMH
        if (power_w < BRAKE_LOSS_TO_W and now - self._loaded_at <= BRAKE_LOSS_WINDOW_S and loaded
                and self._cadence >= BRAKE_LOSS_MIN_RPM and speed_ok
                and now - self._last_brake_loss_at >= BRAKE_LOSS_COOLDOWN_S):
            self._last_brake_loss_at = now
            self._brake_lost_at = now
            self.brake_losses += 1
            speed = "—" if self._trainer_speed_kmh is None else f"{self._trainer_speed_kmh:.0f} km/h"
            log.warning("Trainer : le frein a lâché (%.0f W puis %.0f W à %.0f tr/min, volant %s) ; "
                        "contrôle repris et consigne renvoyée", self._loaded_w, power_w, self._cadence, speed)
            self._emit("brake_loss", from_w=round(self._loaded_w), to_w=round(power_w),
                       cadence_rpm=round(self._cadence), speed_kmh=self._trainer_speed_kmh)
            self._forget_sent()   # nouvelle prise de contrôle et renvoi de la consigne au prochain tour

    def _trace_ibd(self, now: float) -> None:
        """Avec trace_ftms : ce que le trainer annonce lui-même (vitesse du volant, niveau de
        résistance) à côté de la consigne envoyée, pour séparer une chute de résistance du trainer
        d'une consigne trop basse du core (décrochage du 29 octobre, braquet 1 après un sprint)."""
        if not self.cfg.trace_ftms or now - self._trace_ibd_at < TRACE_IBD_EVERY_S:
            return
        self._trace_ibd_at = now
        sent = self._last_sent
        want = "aucune" if sent is None else describe_want(*sent)
        speed = "—" if self._trainer_speed_kmh is None else f"{self._trainer_speed_kmh:.1f} km/h"
        level = "—" if self._trainer_resistance is None else str(self._trainer_resistance)
        log.info("FTMS ~ mesures : puissance %.0f W, cadence %.0f tr/min, vitesse du trainer %s, "
                 "niveau de résistance %s, consigne envoyée %s",
                 self._raw_power, self._cadence, speed, level, want)

    def _on_hr(self, _ch: Any, data: bytearray) -> None:
        try:
            bpm = ftms.parse_hr_measurement(bytes(data))
        except Exception:
            return
        self._hr_service = bpm or None
        self._update_relayed_hr(self._hr_service if self._hr_service is not None else self._hr_ibd)

    def _is_status_echo(self, status_code: int, now: float) -> bool:
        if self._cp is None:
            return False
        if status_code == ftms.STATUS_CONTROL_LOST:
            return False
        status_to_op = {
            0x01: ftms.OP_RESET,
            0x02: ftms.OP_STOP_PAUSE,
            0x04: ftms.OP_START_RESUME,
            0x08: ftms.OP_SET_TARGET_POWER,
            0x12: ftms.OP_SET_SIM_PARAMS,
        }
        expected_op = status_to_op.get(status_code)
        if expected_op is not None:
            last_t = self._cp.last_calls.get(expected_op, 0.0)
            return (now - last_t) < 2.0
        return (now - self._cp.last_call_at) < 2.0

    def _on_training_status(self, _ch: Any, data: bytearray) -> None:
        log.info("FTMS < Training Status %s", bytes(data).hex())
        self._emit("training_status", data=bytes(data).hex())

    def _on_status(self, _ch: Any, data: bytearray) -> None:
        status = ftms.parse_machine_status(bytes(data))
        if status is None:
            return
        code, name = status
        now = self._clock()
        is_echo = self._is_status_echo(code, now)
        self._emit("status", code=f"0x{code:02X}", name=name, data=bytes(data[1:]).hex(), echo=is_echo)
        if self.cfg.trace_ftms:
            valeurs = ""
            if code == 0x08 and len(data) >= 3:
                w = struct.unpack_from("<h", data, 1)[0]
                valeurs = f"cible {w} W"
            elif code == 0x12 and len(data) >= 7:
                _, grade, _, _ = struct.unpack_from("<hhBB", data, 1)
                valeurs = f"pente {grade / 100.0:.2f} %"
            elif len(data) > 1:
                valeurs = f"octets {bytes(data[1:]).hex()}"   # ex. Spin Down Status : 1 demandé, 2 réussi, 3 erreur, 4 arrêter de pédaler
            qualification = "écho probable de notre commande" if is_echo else "par un tiers"
            vals_str = f" {valeurs}" if valeurs else ""
            log.info("FTMS < statut %s%s (%s)", name, vals_str, qualification)

        if code == ftms.STATUS_CONTROL_LOST:
            # Contrôle retiré (autre application, interface du trainer) : on le redemande à la
            # prochaine consigne ; un refus passe ensuite par le compteur de `_on_response`.
            log.warning("Trainer : contrôle FTMS perdu (Fitness Machine Status 0xFF)")
            self._forget_sent()
        elif code == 0x01:
            if is_echo:
                log.info("Trainer : consignes remises à zéro (Reset, écho de notre commande)")
            else:
                log.info("Trainer : consignes remises à zéro par un tiers (Reset), renvoi")
                self._forget_sent()
        elif code in (0x02, 0x03):
            # Arrêt voulu sur le trainer (ou clé de sécurité) : pas de redémarrage forcé.
            log.info("Trainer : état machine %s", name)
        elif code == 0x14:
            # Spin Down Status : étalonnage lancé par le trainer, volant lancé puis frein relâché
            # (hypothèse du décrochage du 29 octobre) ; toujours au journal, pas seulement en trace.
            log.info("Trainer : étalonnage (Spin Down Status) %s", bytes(data[1:]).hex())
        else:
            log.debug("Trainer : état machine %s %s", name, bytes(data[1:]).hex())

    def _on_response(self, resp: ftms.ControlResponse) -> None:
        if resp.ok:
            # Seule une consigne acceptée prouve que le contrôle est retrouvé : une prise de
            # contrôle acceptée suivie d'une consigne refusée ne doit pas remettre le compteur à 0.
            if resp.request_op in (ftms.OP_SET_SIM_PARAMS, ftms.OP_SET_TARGET_POWER):
                self._refusals = 0
                self.control_refused = False
                if self.busy:
                    log.info("Control Point de nouveau libre : consigne acceptée")
                self.busy = False
                self._busy_streak = 0
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
        if self.brake_losses:
            log.info("Trainer : %d perte(s) de frein détectée(s).", self.brake_losses)
        if self.cfg.control == "resistance":
            log.info("Trainer : résistance calculée, frein estimé k = %.4f N par %% et par km/h (départ %.4f)",
                     self.k_road, self.cfg.resistance_n_per_pct_kmh)
        if self.busy_deferrals:
            log.info("Control Point occupé : %d consigne(s) reportée(s), liaison gardée.",
                     self.busy_deferrals)

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
                self.supports_resistance = feats.supports_resistance
                if self.cfg.control != "sim":
                    ok = self.supports_resistance if self.cfg.control == "resistance" else self.supports_erg
                    log.info("Trainer : pilotage par %s calculée%s",
                             "résistance" if self.cfg.control == "resistance" else "puissance",
                             "" if ok else " impossible (consigne non annoncée), SIM gardé")
                log.info("Trainer : fonctions FTMS : %s ; consignes : %s",
                         ", ".join(feats.machine) or "aucune", ", ".join(feats.target) or "aucune")
            if services.get_characteristic(ftms.SUPPORTED_RESISTANCE_RANGE) is not None:
                rr = ftms.parse_resistance_range(
                    bytes(await client.read_gatt_char(ftms.SUPPORTED_RESISTANCE_RANGE)))
                if rr.max_level > rr.min_level:
                    self.resistance_range = (rr.min_level, rr.max_level, max(rr.increment, 0.1))
                log.info("Plage de résistance du trainer : %g à %g, pas de %g",
                         rr.min_level, rr.max_level, rr.increment)
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
                cp = ControlPoint(client, self._on_response, trace=self.cfg.trace_ftms, clock=self._clock)
                self._cp = cp
                await cp.enable()
            else:
                log.warning("Trainer sans Control Point FTMS : mesures seules, aucune consigne")
            if services.get_characteristic(ftms.MACHINE_STATUS) is not None:
                await client.start_notify(ftms.MACHINE_STATUS, self._on_status)
            if self.cfg.trace_ftms and services.get_characteristic(ftms.TRAINING_STATUS) is not None:
                try:   # Training Status : seulement pour le journal (protection éventuelle du trainer)
                    await client.start_notify(ftms.TRAINING_STATUS, self._on_training_status)
                except Exception as exc:
                    log.debug("Training Status indisponible : %s", exc)
            await client.start_notify(ftms.INDOOR_BIKE_DATA, self._on_ibd)
            if services.get_characteristic(ftms.HR_MEASUREMENT) is not None:
                await client.start_notify(ftms.HR_MEASUREMENT, self._on_hr)

            self._last_data_at = self._clock()
            self._link_up = self._ever_connected = True
            self._last_sent = None
            self.busy, self._busy_streak, self._busy_retry_at = False, 0, 0.0
            log.info("Trainer connecté (%s)", getattr(dev, "name", dev))
            try:
                if cp is not None:
                    try:
                        await self._take_control(cp)
                    except ControlPointBusy as exc:
                        self._defer(exc)   # prise de contrôle refaite par _flush_command
                while not (dropped.is_set() or self._stop.is_set()):
                    if self._clock() - (self._last_data_at or 0.0) > FORCE_RECONNECT_S:
                        raise ConnectionError("plus de données du trainer")
                    if cp is not None:
                        await self._flush_command(cp)
                    await asyncio.sleep(0.05)
            finally:
                self._link_up = False
                self._hr_ibd = None
                self._hr_service = None
                self._hr_relay_val = None
                self._hr_relay_last_change_at = None
                self._hr_frozen = False
                if cp is not None and client.is_connected:
                    await self._release(cp)

    async def _take_control(self, cp: ControlPoint) -> None:
        await self._call_retrying(cp, ftms.cmd_request_control)
        await self._call_retrying(cp, ftms.cmd_start_resume)

    async def _call_retrying(self, cp: ControlPoint, build: Callable[[], bytes]) -> None:
        """Écrit `build()` ; renvoie après une erreur ATT ponctuelle, au plus ATT_RETRIES fois.

        `build` est rappelé à chaque essai : un renvoi porte la consigne la plus récente. Control
        Point toujours occupé au troisième essai (CP_BUSY_CODES) : `ControlPointBusy`, la liaison
        reste ouverte. Toute autre exception, ou une autre erreur ATT au troisième essai, remonte
        jusqu'à `run` (reconnexion).
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
                if code is None:
                    raise
                if attempt >= ATT_RETRIES:
                    if code in CP_BUSY_CODES:
                        raise ControlPointBusy(payload[0], code) from exc
                    raise
                attempt += 1
                self.att_retries += 1
                log.warning("Trainer : écriture 0x%02x refusée (ATT 0x%02x), renvoi %d/%d",
                            payload[0], code, attempt, ATT_RETRIES)
                if code in CP_BUSY_CODES:
                    await cp.wait_idle()   # fin de la procédure en cours d'abord
                elif code == ftms.ATT_CCCD_IMPROPERLY_CONFIGURED:
                    await cp.enable()      # indications à nouveau demandées
                await asyncio.sleep(ATT_RETRY_DELAY_S * 2 ** (attempt - 1))
                continue
            if attempt:
                log.info("Trainer : écriture 0x%02x acceptée au renvoi %d", payload[0], attempt)
            return

    def _defer(self, exc: ControlPointBusy) -> None:
        """Control Point occupé : la consigne attend, réessayée après un délai croissant.

        La liaison n'est pas coupée : les mesures continuent d'arriver, donc pas de pause
        automatique. Seule la consigne la plus récente partira (`_want` n'en garde qu'une).
        """
        delay = CP_BUSY_BACKOFF_S[min(self._busy_streak, len(CP_BUSY_BACKOFF_S) - 1)]
        self._busy_streak += 1
        self.busy_deferrals += 1
        self._busy_retry_at = self._clock() + delay
        if not self.busy:
            log.warning("%s : autre appareil sur le trainer (montre ?) ; liaison gardée, consigne "
                        "réessayée dans %.1f s", exc, delay)
        else:
            log.info("%s : nouvel essai dans %.1f s", exc, delay)
        self.busy = True

    async def _flush_command(self, cp: ControlPoint) -> None:
        now = self._clock()
        if now - self._last_sent_at < MIN_SEND_INTERVAL_S or now < self._busy_retry_at:
            return
        mode, value = self._want.mode, self._want.value
        road = self._road_control() if mode == "sim" else None
        if road is not None:
            mode, value = road, self._road_value(road, value)
        prev = self._last_sent
        eps = {"sim": GRADE_EPSILON_PCT, "resistance": max(RESISTANCE_EPSILON, self.resistance_range[2])}.get(
            mode, ERG_EPSILON_W)
        changed = prev is None or prev[0] != mode or abs(prev[1] - value) >= eps
        immediate, self._immediate = self._immediate, False
        changed = changed or (immediate and mode == "sim" and prev[1] != value)
        if not changed and now - self._last_sent_at < self.cfg.resend_s:
            return
        supported = {"erg": self.supports_erg, "resistance": self.supports_resistance}.get(mode, self.supports_sim)
        if not supported:   # opcode exclu par Fitness Machine Feature (FTMS tableau 4.15)
            if prev != (mode, value):
                log.warning("Trainer : mode %s non annoncé (Fitness Machine Feature), consigne "
                            "non envoyée", mode.upper())
            self._last_sent, self._last_sent_at = (mode, value), now
            return
        forgotten = self._forgotten
        sent = (mode, value)

        def build() -> bytes:
            nonlocal sent
            want = self._want   # au renvoi : la consigne la plus récente, du même mode
            if want.mode == "sim" and road is not None:   # consigne calculée : la pente la plus récente
                want = _Want(mode, self._road_value(mode, want.value))
            elif want.mode != mode:
                want = _Want(mode, value)
            sent = (want.mode, want.value)
            if want.mode == "erg":
                return ftms.cmd_set_target_power(want.value)
            if want.mode == "resistance":
                return ftms.cmd_set_target_resistance(want.value, self.resistance_wide)
            return ftms.cmd_set_sim_params(want.value, self._crr, self._cw, self._wind_mps)

        try:
            if prev is None:   # première consigne ou contrôle perdu
                await self._take_control(cp)
            await self._call_retrying(cp, build)
        except ControlPointBusy as exc:
            self._immediate = self._immediate or immediate   # consigne gardée pour le prochain essai
            self._last_sent_at = self._clock()
            self._defer(exc)
            return
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


async def release_control(cp: ControlPoint, crr: float = 0.004, cw_kg_m: float = 0.39,
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
        for attempt in range(RELEASE_BUSY_RETRIES + 1):
            try:
                await cp.call(payload, write_timeout=RELEASE_WRITE_TIMEOUT_S)
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if att_error_code(exc) in CP_BUSY_CODES and attempt < RELEASE_BUSY_RETRIES:
                    await cp.wait_idle()   # Control Point occupé : la relâche réessaie
                    await asyncio.sleep(ATT_RETRY_DELAY_S * 2 ** attempt)
                    continue
                ok = False
                log.warning("Relâche du trainer, %s impossible : %s", label, exc or type(exc).__name__)
                break
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
            cp = ControlPoint(client, trace=trainer.trace_ftms)
            try:
                # Sans abonnement aux indications, le trainer doit refuser toute écriture
                # (erreur ATT 0xFD, FTMS §4.16.3).
                await cp.enable()
                await cp.call(ftms.cmd_request_control(), write_timeout=RELEASE_WRITE_TIMEOUT_S)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.debug("Prise de contrôle avant relâche refusée : %s", exc)
            ok = await release_control(cp, bike.crr, RHO0 * bike.cda_m2)
    log.info("Trainer déconnecté.")
    return ok
