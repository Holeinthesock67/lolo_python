"""Bluetooth simulé : home trainer FTMS, paire de Zwift Click et ceinture cardio, sans matériel.

Contrairement à `MockDriver` (qui remplace le pilote), ce module remplace la radio : les vrais
pilotes (`FtmsDriver`, `ZwiftClickProvider`, `HeartRateProvider`) tournent sans modification
contre des appareils simulés, par leurs points d'injection `device_finder` et `client_factory`.
Tout le chemin BLE est donc exercé : recherche, connexion, abonnements, Control Point avec
indications 0x80, prise et relâche du contrôle, reconnexions, appuis classés par le vrai
`PressClassifier`, relais du boîtier « − » filtré par `ClickPair`.

Comportements reproduits (essais réels du 23 et 24 octobre 2026) :
- **trainer** : Control Point « une procédure à la fois » (erreur ATT 0xFE si l'on écrit avant
  l'indication de réponse, 0xFD sans abonnement aux indications), refus 0x05 sans contrôle,
  « Start/Resume » refusé quand il tourne déjà, Reset qui rend le contrôle, Fitness Machine
  Status 0xFF (contrôle perdu), puissance ERG qui rejoint la cible en ~1,5 s, Indoor Bike Data
  à 4 Hz ;
- **Zwift Click** : deux boîtiers de même nom ; un boîtier endormi ne s'annonce qu'après un appui
  (l'appui qui le réveille est perdu) ; état des touches envoyé à ~10 Hz (type 0x23) ; le
  boîtier « − » relaie les appuis du « + » 5 à 40 ms plus tard ; il se rendort quand le lien
  tombe ;
- **ceinture** : service Heart Rate standard (0x180D), une mesure par seconde, fréquence qui suit
  la puissance du trainer simulé avec du retard ;
- **pannes scénarisées** : apparition tardive, connexions lentes ou refusées, erreur ATT 0x80
  ponctuelle, coupure, silence des données, contrôle FTMS perdu ou refusé.

Le déroulé vient d'un scénario (`sim_scenarios.py`) : réglages des appareils et liste
d'événements datés depuis le démarrage du monde simulé.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import random
import struct
from dataclasses import dataclass
from typing import Any, Callable, Collection

from . import ftms, zwift_click

log = logging.getLogger("ble_sim")

TRAINER_NAME = "HomeTrainer 0000 (sim)"
HR_NAME = "HRM (sim)"
WATCH_NAME = "Forerunner 265 (sim)"   # montre Garmin qui diffuse sa fréquence (lot M2)
WATCH_ADDRESS = "C0:FF:EE:00:57:A7"


class SimBleError(Exception):
    """Erreur d'un appareil simulé ; même texte que les erreurs BlueZ relayées par bleak."""


IN_PROGRESS = "[org.bluez.Error.InProgress] Operation already in progress"


def att_error(code: int) -> SimBleError:
    return SimBleError(f"[org.bluez.Error.Failed] Operation failed with ATT error: 0x{code:02x}")


class SimServices:
    def __init__(self, uuids: Collection[str]) -> None:
        self.uuids = set(uuids)

    def get_characteristic(self, uuid: str) -> object | None:
        return object() if uuid in self.uuids else None


@dataclass
class SimAdvertisement:
    """Ce que renvoie la recherche : un BLEDevice réduit à son nom et son adresse."""
    name: str
    address: str
    rssi: int | None = None


class SimDevice:
    """Appareil simulé : annonce, connexion (un seul client), GATT."""

    uuids: tuple[str, ...] = ()
    readvertise_s = 1.0      # délai avant de s'annoncer à nouveau après une déconnexion

    def __init__(self, world: "SimWorld", name: str, address: str, *, appear_at: float = 0.0,
                 connect_delay_s: float = 0.2, connect_failures: int = 0,
                 asleep: bool = False) -> None:
        self.world, self.name, self.address = world, name, address.upper()
        self.appear_at = appear_at
        self.connect_delay_s = connect_delay_s
        self.connect_failures = connect_failures
        self.asleep = asleep
        self.client: SimClient | None = None
        self.connections = 0
        self._hidden_until = 0.0
        self._tasks: list[asyncio.Task] = []

    # --- annonce et connexion ------------------------------------------------------------

    def advertising(self) -> bool:
        now = self.world.now()
        return (self.client is None and not self.asleep and now >= self.appear_at
                and now >= self._hidden_until)

    def reachable(self) -> bool:
        return not self.asleep and self.world.now() >= self.appear_at

    async def connect(self, client: "SimClient") -> None:
        await asyncio.sleep(self.connect_delay_s)
        if self.connect_failures > 0:
            self.connect_failures -= 1
            raise SimBleError(f"[org.bluez.Error.Failed] le-connection-abort-by-local ({self.name})")
        if not self.reachable():
            raise SimBleError(f"Device with address {self.address} was not found.")
        if self.client is not None:
            raise SimBleError(f"[org.bluez.Error.InProgress] {self.name} déjà connecté")
        self.client = client
        self.connections += 1
        log.debug("%s : connecté", self.name)
        self.on_connect()

    def detach(self, client: "SimClient") -> None:
        if self.client is not client:
            return
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        self.client = None
        self._hidden_until = self.world.now() + self.readvertise_s
        self.on_disconnect()

    def drop(self) -> None:
        """Coupure du lien côté appareil (le pilote l'apprend par son rappel de déconnexion)."""
        client = self.client
        if client is None:
            return
        log.info("Simulation : coupure de %s", self.name)
        self.detach(client)
        client.lost()

    def spawn(self, coro: Any) -> None:
        self._tasks.append(asyncio.get_running_loop().create_task(coro))

    def notify(self, uuid: str, data: bytes) -> None:
        if self.client is not None:
            self.client.deliver(uuid, data)

    # --- à surcharger --------------------------------------------------------------------

    def on_connect(self) -> None:
        pass

    def on_disconnect(self) -> None:
        pass

    def read(self, uuid: str) -> bytes:
        raise SimBleError(f"lecture de {uuid} non permise")

    def write(self, uuid: str, data: bytes) -> None:
        raise SimBleError(f"écriture de {uuid} non permise")

    def subscribed(self, uuid: str) -> None:
        pass


class SimClient:
    """Client façon `BleakClient` : gestionnaire de contexte asynchrone, GATT, rappel de coupure."""

    def __init__(self, device: SimDevice | None, address: str,
                 disconnected_callback: Callable[[Any], None] | None = None,
                 timeout: float = 15.0) -> None:
        self.device, self.address = device, address
        self._disconnected_cb = disconnected_callback
        self.timeout = timeout
        self.is_connected = False
        self._notify: dict[str, Callable[[Any, bytearray], None]] = {}
        self.services = SimServices(device.uuids if device else ())

    async def __aenter__(self) -> "SimClient":
        if self.device is None:
            await asyncio.sleep(min(self.timeout, 2.0))
            raise SimBleError(f"Device with address {self.address} was not found.")
        await asyncio.wait_for(self.device.connect(self), timeout=self.timeout)
        self.is_connected = True
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.disconnect()

    async def disconnect(self) -> bool:
        if self.is_connected and self.device is not None:
            self.is_connected = False
            self.device.detach(self)
        return True

    def lost(self) -> None:
        self.is_connected = False
        if self._disconnected_cb is not None:
            self._disconnected_cb(self)

    def _check(self) -> SimDevice:
        if not self.is_connected or self.device is None:
            raise SimBleError("Not connected")
        return self.device

    async def start_notify(self, uuid: str, callback: Callable[[Any, bytearray], None]) -> None:
        dev = self._check()
        if uuid not in dev.uuids:
            raise SimBleError(f"Characteristic {uuid} was not found!")
        self._notify[uuid] = callback
        dev.subscribed(uuid)

    async def stop_notify(self, uuid: str) -> None:
        self._notify.pop(uuid, None)

    async def read_gatt_char(self, uuid: str) -> bytearray:
        dev = self._check()
        await asyncio.sleep(0)
        return bytearray(dev.read(uuid))

    async def write_gatt_char(self, uuid: str, data: Any, response: bool = True) -> None:
        dev = self._check()
        await asyncio.sleep(self.device.world.write_latency_s if self.device else 0)
        self._check()
        dev.write(uuid, bytes(data))

    def deliver(self, uuid: str, data: bytes) -> None:
        cb = self._notify.get(uuid)
        if cb is not None and self.is_connected:
            cb(uuid, bytearray(data))


# --- home trainer FTMS --------------------------------------------------------------------

# Fitness Machine Feature : cadence (bit 1) et puissance (bit 14) mesurées ; cibles de puissance
# (bit 3) et simulation (bit 13), comme le HomeTrainer.
FEATURE_MACHINE = (1 << 1) | (1 << 14)
FEATURE_TARGET = (1 << 3) | (1 << 13)


@dataclass
class CpRecord:
    """Commande reçue par le Control Point simulé (pour les tests et le journal)."""
    t: float
    op: int
    payload: bytes
    result: int | None   # None : pas de réponse (erreur ATT ou réponse supprimée)


class SimTrainer(SimDevice):
    uuids = (ftms.FTMS_SERVICE, ftms.FEATURE, ftms.SUPPORTED_POWER_RANGE, ftms.INDOOR_BIKE_DATA,
             ftms.CONTROL_POINT, ftms.MACHINE_STATUS)

    def __init__(self, world: "SimWorld", name: str = TRAINER_NAME,
                 address: str = "5A:1A:00:00:00:00", *, ibd_hz: float = 4.0,
                 rider_power_w: float = 180.0, cadence_rpm: float = 88.0,
                 erg_tau_s: float = 1.5, cp_latency_s: float = 0.05,
                 power_range: tuple[int, int, int] = (0, 2000, 1),
                 refuse_control: bool = False,
                 relayed_hr: bool | int | None = None, **kw: Any) -> None:
        super().__init__(world, name, address, **kw)
        self.ibd_hz = ibd_hz
        self.rider_power_w, self.cadence_rpm = rider_power_w, cadence_rpm
        self.erg_tau_s, self.cp_latency_s = erg_tau_s, cp_latency_s
        self.power_range = power_range
        self.refuse_control = refuse_control
        self.relayed_hr_enabled = bool(relayed_hr)
        self.fixed_relayed_hr: int | None = (
            int(relayed_hr) if isinstance(relayed_hr, (int, float)) and not isinstance(relayed_hr, bool) else None
        )
        # État de la machine (survit aux connexions, comme un vrai trainer)
        self.mode: str | None = None          # "sim", "erg" ou None (aucune consigne)
        self.target_w: float | None = None
        self.grade_pct = 0.0
        self.started = False
        self.power_w = 0.0
        # État de la liaison
        self.control = False
        self.indications = False
        self._busy = False
        self.silent_until = 0.0
        self.pending_att_errors: list[int] = []
        self.pending_silent_responses = 0
        self.commands: list[CpRecord] = []

    @property
    def released(self) -> bool:
        """Personne n'a le contrôle et aucune consigne ne reste active."""
        return not self.control and self.mode is None

    def on_connect(self) -> None:
        self.indications = False
        self.control = False
        self._busy = False
        self.spawn(self._data_loop())

    def on_disconnect(self) -> None:
        self.control = False   # le contrôle FTMS ne survit pas à la liaison

    def read(self, uuid: str) -> bytes:
        if uuid == ftms.FEATURE:
            return struct.pack("<II", FEATURE_MACHINE, FEATURE_TARGET)
        if uuid == ftms.SUPPORTED_POWER_RANGE:
            return struct.pack("<hhH", *self.power_range)
        return super().read(uuid)

    def subscribed(self, uuid: str) -> None:
        if uuid == ftms.CONTROL_POINT:
            self.indications = True

    def write(self, uuid: str, data: bytes) -> None:
        if uuid != ftms.CONTROL_POINT:
            super().write(uuid, data)
        now = self.world.now()
        op = data[0] if data else -1
        if not self.indications:
            self.commands.append(CpRecord(now, op, data, None))
            raise att_error(ftms.ATT_CCCD_IMPROPERLY_CONFIGURED)
        if self._busy:
            self.commands.append(CpRecord(now, op, data, None))
            raise att_error(ftms.ATT_PROCEDURE_IN_PROGRESS)
        if self.pending_att_errors:
            code = self.pending_att_errors.pop(0)
            log.info("Simulation : erreur ATT 0x%02x sur l'écriture 0x%02x", code, op)
            self.commands.append(CpRecord(now, op, data, None))
            raise att_error(code)
        result = self._execute(op, data)
        silent = self.pending_silent_responses > 0
        if silent:
            self.pending_silent_responses -= 1
        self.commands.append(CpRecord(now, op, data, None if silent else result))
        if silent:
            return
        self._busy = True
        reply = bytes([ftms.OP_RESPONSE, op & 0xFF, result])
        asyncio.get_running_loop().call_later(self.cp_latency_s, self._respond, reply)

    def _respond(self, reply: bytes) -> None:
        self._busy = False
        self.notify(ftms.CONTROL_POINT, reply)

    def _execute(self, op: int, data: bytes) -> int:
        ok, refused, failed = 0x01, 0x05, 0x04
        if op == ftms.OP_REQUEST_CONTROL:
            if self.refuse_control:
                return refused
            self.control = True
            return ok
        if not self.control:
            return refused
        if op == ftms.OP_RESET:
            self.mode, self.target_w, self.grade_pct, self.started = None, None, 0.0, False
            self.control = False   # FTMS §4.16.2.2 : le Reset rend le contrôle
            # Pas d'état 0x01 : on ignore si le HomeTrainer l'envoie pour un Reset du client lui-même,
            # et le pilote le lit comme un Reset venu d'un tiers.
            return ok
        if op == ftms.OP_START_RESUME:
            if self.started:
                return failed   # mesuré sur le HomeTrainer : déjà démarré, sans gravité
            self.started = True
            return ok
        if op == ftms.OP_STOP_PAUSE:
            self.started = False
            return ok
        if op == ftms.OP_SET_TARGET_POWER and len(data) >= 3:
            lo, hi, _ = self.power_range
            self.mode, self.target_w = "erg", float(min(max(struct.unpack_from("<h", data, 1)[0], lo), hi))
            self._status(bytes([0x08]) + data[1:3])
            return ok
        if op == ftms.OP_SET_SIM_PARAMS and len(data) >= 7:
            self.mode, self.target_w = "sim", None
            self.grade_pct = struct.unpack_from("<h", data, 3)[0] / 100.0
            self._status(bytes([0x12]) + data[1:7])
            return ok
        if op in (ftms.OP_SET_TARGET_POWER, ftms.OP_SET_SIM_PARAMS):
            return 0x03   # paramètre invalide (trame trop courte)
        return 0x02       # opcode non pris en charge

    def _status(self, payload: bytes) -> None:
        self.notify(ftms.MACHINE_STATUS, payload)

    def lose_control(self) -> None:
        """Une autre application (ou l'interface du trainer) prend le contrôle."""
        if self.client is None:
            return
        log.info("Simulation : contrôle FTMS retiré (Fitness Machine Status 0xFF)")
        self.control = False
        self._status(bytes([ftms.STATUS_CONTROL_LOST]))

    def _rider_power(self, t: float) -> float:
        """Puissance du cycliste en SIM : un peu plus d'effort en montée, un peu de bruit."""
        if self.rider_power_w <= 0 or self.cadence_rpm <= 0:
            return 0.0
        p = self.rider_power_w * (1.0 + 0.04 * self.grade_pct) + 4.0 * math.sin(t * 0.9)
        return max(p, 0.0)

    async def _data_loop(self) -> None:
        period = 1.0 / self.ibd_hz
        last = self.world.now()
        while True:
            await asyncio.sleep(period)
            t = self.world.now()
            dt, last = t - last, t
            if self.mode == "erg" and self.target_w is not None and self.cadence_rpm > 0:
                goal = self.target_w + 2.0 * math.sin(t * 1.5)
            else:
                goal = self._rider_power(t)
            alpha = 1.0 - math.exp(-dt / max(self.erg_tau_s, 1e-3))
            self.power_w += alpha * (goal - self.power_w)
            if t < self.silent_until:
                continue
            cadence = self.cadence_rpm + (1.5 * math.sin(t * 0.7) if self.cadence_rpm > 0 else 0.0)
            speed_kmh = 3.6 * (max(self.power_w, 0.0) / 0.9) ** (1 / 3) if self.power_w > 0 else 0.0
            flags = 0x0004 | 0x0040   # vitesse (bit 0 à 0), cadence, puissance
            if self.relayed_hr_enabled:
                flags |= 0x0200
                if self.fixed_relayed_hr is not None:
                    hr_val = self.fixed_relayed_hr
                else:
                    hr_val = int(round(130 + 3.0 * math.sin(t * 0.5)))
                self.notify(ftms.INDOOR_BIKE_DATA, struct.pack(
                    "<HHHhB", flags, int(round(speed_kmh * 100)), int(round(max(cadence, 0.0) * 2)),
                    int(round(self.power_w)), max(30, min(240, hr_val))))
            else:
                self.notify(ftms.INDOOR_BIKE_DATA, struct.pack(
                    "<HHHh", flags, int(round(speed_kmh * 100)), int(round(max(cadence, 0.0) * 2)),
                    int(round(self.power_w))))


# --- Zwift Click --------------------------------------------------------------------------

def keypad_message(plus: bool, minus: bool, other_bits: Collection[int] = ()) -> bytes:
    """Trame 0x23 du Click récent : tableau de bits, 0 = appuyé (bit 12 « + », bit 8 « − » ;
    `other_bits` : autres touches appuyées, par exemple B et Y du boîtier droit)."""
    mask = zwift_click.KEYPAD_ALL_RELEASED
    if plus:
        mask &= ~(1 << zwift_click.KEYPAD_PLUS_BIT)
    if minus:
        mask &= ~(1 << zwift_click.KEYPAD_MINUS_BIT)
    for bit in other_bits:
        mask &= ~(1 << bit)
    return bytes([zwift_click.MSG_KEYPAD_STATUS, 0x08]) + _varint(mask & 0xFFFFFFFF)


def battery_message(pct: int) -> bytes:
    return bytes([zwift_click.MSG_BATTERY_LEVEL, 0x10]) + _varint(pct)


def _varint(v: int) -> bytes:
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


class SimClickBox(SimDevice):
    """Un boîtier du Zwift Click récent (« + » ou « − »), nom BLE « Zwift Click »."""

    uuids = (zwift_click.ZWIFT_SERVICE, zwift_click.ZWIFT_ASYNC, zwift_click.ZWIFT_SYNC_RX,
             zwift_click.ZWIFT_SYNC_TX)

    def __init__(self, world: "SimWorld", role: str, address: str, *, status_hz: float = 10.0,
                 battery_pct: int = 80, sleep_on_drop: bool = True,
                 mute_after_s: float | None = None, unlock_on_ride_on: bool = False, **kw: Any) -> None:
        kw.setdefault("asleep", True)   # un Click ne s'annonce qu'après un appui
        super().__init__(world, zwift_click.CLICK_NAME, address, **kw)
        self.role = role
        self.status_hz, self.battery_pct = status_hz, battery_pct
        self.sleep_on_drop = sleep_on_drop
        self.mute_after_s = mute_after_s
        self.unlock_on_ride_on = unlock_on_ride_on
        self.ride_on_count = 0
        self.pressed: set[str] = set()
        self.ride_on = False
        self.presses_lost = 0
        self._connected_at: float | None = None
        self.silent_until = 0.0   # boîtier muet, lien gardé (action « silence », lot X8)
        self._timed_wake = self.asleep and self.appear_at > 0

    @property
    def is_muted(self) -> bool:
        if self.mute_after_s is None or self._connected_at is None:
            return False
        return (self.world.now() - self._connected_at) >= self.mute_after_s

    def advertising(self) -> bool:
        if self._timed_wake and self.world.now() >= self.appear_at:
            self._timed_wake = self.asleep = False   # réveil daté par le scénario (« appear_at »)
        return super().advertising()

    def on_connect(self) -> None:
        self._connected_at = self.world.now()
        self.ride_on = False
        self.pressed.clear()
        self.spawn(self._status_loop())

    def on_disconnect(self) -> None:
        self.ride_on = False
        self._connected_at = None

    def drop(self) -> None:
        had_client = self.client is not None
        super().drop()
        if had_client and self.sleep_on_drop:
            self.asleep = True

    def write(self, uuid: str, data: bytes) -> None:
        if uuid != zwift_click.ZWIFT_SYNC_RX:
            super().write(uuid, data)
        if data == zwift_click.RIDE_ON:
            self.ride_on_count += 1
            self.ride_on = True
            if self.unlock_on_ride_on and self.ride_on_count >= 2:
                self.mute_after_s = None
            self.notify(zwift_click.ZWIFT_SYNC_TX, b"RideOn\x01\x03")
            self.notify(zwift_click.ZWIFT_ASYNC, battery_message(self.battery_pct))

    def set_button(self, button: str, down: bool) -> None:
        """Change l'état d'une touche ; un boîtier endormi se réveille et l'appui est perdu."""
        if down:
            self.pressed.add(button)
        else:
            self.pressed.discard(button)
        if self.client is None:
            if down and self.asleep:
                self.asleep = False
                self.presses_lost += 1
                log.info("Simulation : Click %s réveillé par l'appui (appui perdu)", self.role)
            return
        if self.is_muted:
            return
        self._send_status()

    def _send_status(self) -> None:
        if self.ride_on and self.world.now() >= self.silent_until:
            if self.is_muted:   # lot Q6 : notifications sans bouton, lien gardé
                self.notify(zwift_click.ZWIFT_ASYNC, bytes([zwift_click.MSG_EMPTY, 0x00]))
            else:
                other = [zwift_click.KEYPAD_BITS[b] for b in self.pressed if b not in ("+", "-")]
                self.notify(zwift_click.ZWIFT_ASYNC, keypad_message("+" in self.pressed, "-" in self.pressed, other))

    async def _status_loop(self) -> None:
        while True:
            await asyncio.sleep(1.0 / self.status_hz)
            self._send_status()


# --- ceinture cardio ----------------------------------------------------------------------

class SimHrStrap(SimDevice):
    """Ceinture (ou montre qui diffuse sa fréquence) : 0x2A37 à 1 Hz, contact, RR, batterie.

    `contact` : True (présent), False (absent), None (non géré par l'appareil) ;
    `battery_pct` : None retire le service Battery 0x180F ; `rssi` : force du signal annoncé.
    """

    def __init__(self, world: "SimWorld", name: str = HR_NAME, address: str = "C0:FF:EE:00:18:0D",
                 *, rest_bpm: int = 62, max_bpm: int = 185, ftp_w: float = 250.0,
                 tau_s: float = 20.0, bpm: int | None = None, contact: bool | None = True,
                 battery_pct: int | None = 80, rssi: int = -60, **kw: Any) -> None:
        super().__init__(world, name, address, **kw)
        self.rest_bpm, self.max_bpm, self.ftp_w, self.tau_s = rest_bpm, max_bpm, ftp_w, tau_s
        self.fixed_bpm = bpm
        self.bpm = float(bpm if bpm is not None else rest_bpm + 25)
        self.contact = contact
        self.battery_pct = battery_pct
        self.rssi = rssi
        self.uuids = (ftms.HR_SERVICE, ftms.HR_MEASUREMENT)
        if battery_pct is not None:
            self.uuids += (ftms.BATTERY_SERVICE, ftms.BATTERY_LEVEL)

    def on_connect(self) -> None:
        self.spawn(self._loop())

    def read(self, uuid: str) -> bytes:
        if uuid == ftms.BATTERY_LEVEL and self.battery_pct is not None:
            return bytes([max(0, min(100, int(self.battery_pct)))])
        return super().read(uuid)

    def _goal(self) -> float:
        if self.fixed_bpm is not None:
            return float(self.fixed_bpm)
        trainer = self.world.trainer
        power = trainer.power_w if trainer is not None else 0.0
        frac = min(max(power / self.ftp_w, 0.0), 1.3)
        return self.rest_bpm + 25 + (self.max_bpm - self.rest_bpm - 25) * frac / 1.3

    def measurement(self) -> bytes:
        """Trame 0x2A37 : bpm sur 8 bits, contact s'il est géré, un intervalle RR cohérent."""
        bpm = max(30, min(240, int(round(self.bpm))))
        flags = 0x10   # intervalles RR présents
        if self.contact is not None:
            flags |= 0x04 | (0x02 if self.contact else 0)
        rr = int(round(60.0 / bpm * 1024))
        return bytes([flags, bpm]) + struct.pack("<H", rr)

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            alpha = 1.0 - math.exp(-1.0 / max(self.tau_s, 1e-3))
            self.bpm += alpha * (self._goal() - self.bpm)
            self.notify(ftms.HR_MEASUREMENT, self.measurement())


# --- monde simulé -------------------------------------------------------------------------

class SimWorld:
    """Les appareils simulés d'une séance, leur horloge et la recherche BLE.

    `find_device` et `client_factory` ont la signature attendue par les pilotes réels.
    `run()` déroule les événements du scénario ; l'horloge part au premier appel de `now()`.
    """

    write_latency_s = 0.01

    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.trainer: SimTrainer | None = None
        self.clicks: list[SimClickBox] = []
        self.hr: SimHrStrap | None = None
        self.hr_watch: SimHrStrap | None = None   # montre qui diffuse sa fréquence (lot M2)
        self.events: list[dict[str, Any]] = []
        self.relay_delay_s: tuple[float, float] = (0.005, 0.040)
        self.name = "sim"
        self._t0: float | None = None
        self._stop = asyncio.Event()
        self._discovering = False

    @property
    def devices(self) -> list[SimDevice]:
        return [d for d in (self.trainer, *self.clicks, self.hr, self.hr_watch) if d is not None]

    def now(self) -> float:
        loop_time = asyncio.get_running_loop().time()
        if self._t0 is None:
            self._t0 = loop_time
        return loop_time - self._t0

    def device(self, key: str) -> SimDevice:
        """« trainer », « hr », « hr_watch », « click_plus » / « click+ », « click_minus » / « click- »."""
        k = key.lower().replace("_", "").replace(" ", "")
        if k == "trainer" and self.trainer is not None:
            return self.trainer
        if k == "hr" and self.hr is not None:
            return self.hr
        if k == "hrwatch" and self.hr_watch is not None:
            return self.hr_watch
        for box in self.clicks:
            if k in (f"click{box.role}", "clickplus" if box.role == "+" else "clickminus"):
                return box
        raise KeyError(f"appareil simulé inconnu : {key!r}")

    @contextlib.contextmanager
    def discovery(self):
        """Comme BlueZ : une seule recherche à la fois ; une seconde lève InProgress."""
        if self._discovering:
            raise SimBleError(IN_PROGRESS)
        self._discovering = True
        try:
            yield
        finally:
            self._discovering = False

    # --- points d'injection des pilotes ---------------------------------------------------

    async def find_device(self, name: str, address: str | None, timeout: float,
                          exclude: Collection[str] = (), service: str | None = None) -> Any | None:
        with self.discovery():
            return await self._find_device(name, address, timeout, exclude, service)

    async def _find_device(self, name: str, address: str | None, timeout: float,
                           exclude: Collection[str], service: str | None) -> Any | None:
        skip = {a.upper() for a in exclude}
        needle = (name or "").lower()
        end = self.now() + timeout
        while True:
            for dev in self.devices:
                if not dev.advertising() or dev.address in skip:
                    continue
                if address:
                    if dev.address == address.upper():
                        return SimAdvertisement(dev.name, dev.address)
                elif (needle and needle in dev.name.lower()) or (service and service in dev.uuids):
                    return SimAdvertisement(dev.name, dev.address)
            if self.now() >= end:
                # Comme `find_device` : une adresse imposée est rendue telle quelle (connexion directe).
                return address or None
            await asyncio.sleep(0.1)

    async def scan(self, timeout: float, service: str | None = None) -> list[SimAdvertisement]:
        """Recherche de tous les appareils annoncés (avec leur RSSI), filtrés par service.

        Rend la main 0,3 s après le premier appareil trouvé (pas les 5 s d'une vraie recherche),
        pour que les séances simulées restent rapides.
        """
        with self.discovery():
            return await self._scan(timeout, service)

    async def _scan(self, timeout: float, service: str | None) -> list[SimAdvertisement]:
        end = self.now() + timeout
        found_at: float | None = None
        while True:
            found = [SimAdvertisement(d.name, d.address, getattr(d, "rssi", None))
                     for d in self.devices
                     if d.advertising() and (service is None or service in d.uuids)]
            if found and found_at is None:
                found_at = self.now()
            if self.now() >= end or (found_at is not None and self.now() - found_at >= 0.3):
                return found
            await asyncio.sleep(0.1)

    def client_factory(self, device: Any, **kwargs: Any) -> SimClient:
        address = str(getattr(device, "address", device)).upper()
        target = next((d for d in self.devices if d.address == address), None)
        return SimClient(target, address, kwargs.get("disconnected_callback"),
                         kwargs.get("timeout", 15.0))

    # --- Click : appuis --------------------------------------------------------------------

    def _box(self, role: str) -> SimClickBox | None:
        return next((b for b in self.clicks if b.role == role), None)

    async def press(self, button: str, duration_s: float = 0.12) -> None:
        """Appui sur « + » ou « − » du Click simulé, avec le relais du boîtier « − »."""
        button = "-" if button in ("-", "−", "minus", "moins") else "+"
        own = self._box(button)
        relay = self._box("-") if button == "+" else None
        delay = self.rng.uniform(*self.relay_delay_s) if relay is not None else 0.0
        loop = asyncio.get_running_loop()
        for box, offset in ((own, 0.0), (relay, delay)):
            if box is None:
                continue
            loop.call_later(offset, box.set_button, button, True)
            loop.call_later(offset + duration_s, box.set_button, button, False)
        await asyncio.sleep(duration_s + delay)

    # --- scénario -------------------------------------------------------------------------

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        self.now()
        pending = sorted(self.events, key=lambda e: float(e["t"]))
        for ev in pending:
            wait = float(ev["t"]) - self.now()
            if wait > 0:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=wait)
                except asyncio.TimeoutError:
                    pass
            if self._stop.is_set():
                return
            try:
                await self.apply(ev)
            except Exception as exc:   # un événement raté ne doit pas arrêter la séance
                log.warning("Simulation : événement %s impossible : %s", ev, exc)
        await self._stop.wait()

    async def apply(self, ev: dict[str, Any]) -> None:
        action = ev["action"]
        log.info("Simulation (t=%.1f s) : %s", self.now(), _describe(ev))
        if action == "press":
            # Pas d'attente : deux appuis rapprochés du scénario ne doivent pas se décaler.
            asyncio.get_running_loop().create_task(
                self.press(ev.get("button", "+"), float(ev.get("duration_s", 0.12))))
            return
        dev = self.device(ev.get("device", "trainer"))
        if action == "drop":
            dev.drop()
        elif action == "wake":
            dev.asleep = False
        elif action == "sleep":
            dev.asleep = True
        elif action == "connect_failures":
            dev.connect_failures = int(ev.get("count", 1))
        elif action == "connect_delay":
            dev.connect_delay_s = float(ev["seconds"])
        elif isinstance(dev, SimTrainer) and action == "att_error":
            dev.pending_att_errors.extend([int(ev.get("code", 0x80))] * int(ev.get("count", 1)))
        elif isinstance(dev, SimTrainer) and action == "cp_silent":
            dev.pending_silent_responses += int(ev.get("count", 1))
        elif isinstance(dev, (SimTrainer, SimClickBox)) and action == "silence":
            dev.silent_until = self.now() + float(ev["seconds"])
        elif isinstance(dev, SimTrainer) and action == "control_lost":
            dev.lose_control()
        elif isinstance(dev, SimTrainer) and action == "refuse_control":
            dev.refuse_control = bool(ev.get("value", True))
        elif isinstance(dev, SimTrainer) and action == "rider":
            if "watts" in ev:
                dev.rider_power_w = float(ev["watts"])
            if "cadence_rpm" in ev:
                dev.cadence_rpm = float(ev["cadence_rpm"])
        elif isinstance(dev, SimTrainer) and action == "bpm":
            dev.relayed_hr_enabled = True
            dev.fixed_relayed_hr = None if ev.get("bpm") is None else int(ev["bpm"])
        elif isinstance(dev, SimHrStrap) and action == "bpm":
            dev.fixed_bpm = None if ev.get("bpm") is None else int(ev["bpm"])
        elif isinstance(dev, SimHrStrap) and action == "contact":
            dev.contact = None if ev.get("value", True) is None else bool(ev.get("value", True))
        else:
            raise ValueError(f"action {action!r} sans effet sur {ev.get('device', 'trainer')}")


def _describe(ev: dict[str, Any]) -> str:
    rest = ", ".join(f"{k}={v}" for k, v in ev.items() if k not in ("t", "action"))
    return f"{ev['action']}" + (f" ({rest})" if rest else "")
