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
  à 4 Hz ; avec `response: "realiste"` (lot X6), frein à retard pur et constantes de temps de
  serrage et de relâchement, volant d'inertie, effort de la route en SIM (pente, Crr et Cw reçus)
  et notifications avec gigue ;
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
import collections
import contextlib
import csv
import json
import logging
import math
import random
import statistics
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Collection

from . import ftms, zwift_click
from .physics import G, PhysicsParams, steady_speed
from .sim_rider import RiderOutput, SimRider

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


SPEED_PHYSICS = PhysicsParams()   # vitesse imposée : mêmes réglages que la configuration par défaut du core


# --- Réponse réaliste du trainer (lot X6) -------------------------------------------------

RESPONSES = ("instant", "realiste")
# Préréglage « realiste » : valeurs moyennes de l'essai du 25 octobre (relâchement du frein vers 12 s
# à 90 %, serrage plus rapide), sans marque ni numéro de série.
REALISTE = {"brake_delay_s": 0.6, "brake_tau_up_s": 2.0, "brake_tau_down_s": 4.9,
            "flywheel_kg_m2": 0.6, "notify_jitter_s": 0.04}
WHEEL_RADIUS_M = 0.336         # rayon de la roue : ramène l'inertie du volant à une masse à la jante
RIDER_TAU_S = 1.0              # le cycliste rattrape sa cadence (braquet fixe) en une seconde environ
RIDER_RESERVE = 2.5            # puissance maximale du cycliste : 2,5 × son effort habituel
SUBSTEP_S = 0.01


def load_calibration(path: str | Path) -> dict[str, float]:
    """Retard et constantes de temps tirés de `steps.csv` du banc de paliers (lot X5).

    Pour un 1er ordre à retard pur d : t10 = d + 0,105 τ et t63 = d + τ, donc τ = (t63 − t10) / 0,895.
    Médianes des paliers montants (serrage) et descendants (relâchement) ; retard : médiane de tous."""
    ups: list[float] = []
    downs: list[float] = []
    delays: list[float] = []
    with Path(path).expanduser().open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                t10, t63, delta = float(row["t10_s"]), float(row["t63_s"]), float(row["delta_w"])
            except (KeyError, TypeError, ValueError):
                continue   # palier de départ, ou sans mesure
            tau = (t63 - t10) / 0.895
            if tau <= 0:
                continue
            (ups if delta > 0 else downs).append(tau)
            delays.append(max(t63 - tau, 0.0))
    if not ups or not downs:
        raise ValueError(f"{path} : il faut au moins un palier montant et un descendant mesurés")
    return {"brake_delay_s": round(statistics.median(delays), 3), "brake_tau_up_s": round(statistics.median(ups), 3),
            "brake_tau_down_s": round(statistics.median(downs), 3)}


class TrainerResponse:
    """Modèle de réponse réaliste (lot X6), sans asyncio : `step(dt, …)` avance le temps.

    - **Frein** : la force demandée (ERG : cible / vitesse ; SIM : effort de la route à la vitesse du
      volant, m g (sin θ + Crr cos θ) + Cw (v + vent)², avec la pente, le Crr, le Cw et le vent reçus ;
      sans consigne : route plate) est vue avec un retard pur `brake_delay_s`, puis rejointe avec la
      constante `brake_tau_up_s` quand elle augmente et `brake_tau_down_s` quand elle baisse.
    - **Volant** : masse équivalente à la jante `flywheel_kg_m2 / r²` ; m v dv/dt = P_cycliste − F_frein v.
    - **Cycliste** : tient sa cadence à braquet fixe (vitesse de l'effort habituel sur le plat, ou
      stratégie `vitesse` du cycliste), en rattrapant l'écart en ~1 s, sans dépasser `rider_max_w`.
    - Puissance mesurée par le trainer : celle du cycliste (frein + accélération du volant)."""

    def __init__(self, *, brake_delay_s: float, brake_tau_up_s: float, brake_tau_down_s: float,
                 flywheel_kg_m2: float, physics: PhysicsParams = SPEED_PHYSICS) -> None:
        self.delay_s = max(brake_delay_s, 0.0)
        self.tau_up_s, self.tau_down_s = max(brake_tau_up_s, 1e-3), max(brake_tau_down_s, 1e-3)
        self.mass_eq_kg = max(flywheel_kg_m2, 1e-3) / WHEEL_RADIUS_M ** 2
        self.physics = physics
        self.force_n: float | None = None   # force du frein ; None avant le premier pas
        self.v = 0.0
        self.power_w = 0.0
        self.t = 0.0
        self._commands: collections.deque = collections.deque()   # (t, consigne) en attente du retard
        self._applied: tuple = (None, None, 0.0, None, None, 0.0)

    def _command_force(self, cmd: tuple, v: float) -> float:
        mode, target_w, grade_pct, crr, cw, wind = cmd
        if mode == "erg" and target_w is not None:
            return target_w / max(v, 1.0)
        theta = math.atan((grade_pct if mode == "sim" else 0.0) / 100.0)
        p = self.physics
        cw = cw if cw is not None else 1.225 * p.cda_m2   # Cw FTMS = ρ · CdA
        crr = crr if crr is not None else p.crr
        va = v + wind
        return p.mass_kg * G * (math.sin(theta) + crr * math.cos(theta)) + 0.5 * cw * va * abs(va)

    def step(self, dt: float, cmd: tuple, v_ride: float, rider_max_w: float) -> float:
        """Avance de `dt` s avec la consigne courante `cmd` (mode, cible W, pente %, Crr, Cw, vent m/s) ;
        renvoie la puissance mesurée."""
        if not self._commands or self._commands[-1][1] != cmd:
            self._commands.append((self.t, cmd))
        if self.force_n is None:   # départ : roule déjà à sa vitesse, frein établi
            self.v = v_ride
            self._applied = cmd
            self.force_n = max(self._command_force(cmd, self.v), 0.0)
        n = max(1, int(math.ceil(dt / SUBSTEP_S)))
        h = dt / n
        for _ in range(n):
            self.t += h
            while self._commands and self._commands[0][0] <= self.t - self.delay_s:
                self._applied = self._commands.popleft()[1]
            goal = max(self._command_force(self._applied, self.v), 0.0)
            tau = self.tau_up_s if goal > self.force_n else self.tau_down_s
            self.force_n += (goal - self.force_n) * (1.0 - math.exp(-h / tau))
            v = max(self.v, 0.5)
            brake_w = self.force_n * v
            rider_w = brake_w + self.mass_eq_kg * v * (v_ride - v) / RIDER_TAU_S
            rider_w = min(max(rider_w, 0.0), rider_max_w) if v_ride > 0 else 0.0
            self.v = max(self.v + (rider_w - brake_w) / (self.mass_eq_kg * v) * h, 0.0)
            self.power_w = rider_w
        return self.power_w


class SimTrainer(SimDevice):
    uuids = (ftms.FTMS_SERVICE, ftms.FEATURE, ftms.SUPPORTED_POWER_RANGE, ftms.INDOOR_BIKE_DATA,
             ftms.CONTROL_POINT, ftms.MACHINE_STATUS)

    def __init__(self, world: "SimWorld", name: str = TRAINER_NAME,
                 address: str = "5A:1A:00:00:00:00", *, ibd_hz: float = 4.0,
                 rider: SimRider | None = None,
                 erg_tau_s: float = 1.5, cp_latency_s: float = 0.05,
                 power_range: tuple[int, int, int] = (0, 2000, 1),
                 refuse_control: bool = False, busy_window_s: float = 0.0,
                 relayed_hr: bool | int | None = None,
                 response: str = "instant", brake_delay_s: float | None = None,
                 brake_tau_up_s: float | None = None, brake_tau_down_s: float | None = None,
                 flywheel_kg_m2: float | None = None, notify_jitter_s: float | None = None,
                 rider_max_w: float | None = None, calibration: str | None = None, **kw: Any) -> None:
        super().__init__(world, name, address, **kw)
        self.ibd_hz = ibd_hz
        self.rider = rider or SimRider()   # cycliste virtuel (lot X27, section `rider` du scénario)
        # Réponse (lot X6) : « instant » (premier ordre de `erg_tau_s`) ou « realiste » (TrainerResponse).
        self.response = response
        self.rider_max_w = rider_max_w
        self.model: TrainerResponse | None = None
        self.notify_jitter_s = 0.0
        if response == "realiste":
            params = dict(REALISTE)
            if calibration:
                params.update(load_calibration(calibration))
            given = {"brake_delay_s": brake_delay_s, "brake_tau_up_s": brake_tau_up_s,
                     "brake_tau_down_s": brake_tau_down_s, "flywheel_kg_m2": flywheel_kg_m2,
                     "notify_jitter_s": notify_jitter_s}
            params.update({k: float(v) for k, v in given.items() if v is not None})
            self.notify_jitter_s = params.pop("notify_jitter_s")
            self.model = TrainerResponse(**params)
        self._jitter_rng = random.Random(address)   # à part : ne décale pas le tirage du monde
        self.wind_mps, self.crr, self.cw = 0.0, None, None   # reçus dans la trame SIM
        self._v_ride_cache: tuple[float, float] = (-1.0, 0.0)
        self.erg_tau_s, self.cp_latency_s = erg_tau_s, cp_latency_s
        self.power_range = power_range
        self.refuse_control = refuse_control
        # Control Point encore occupé `busy_window_s` après chaque réponse : erreur ATT 0x80 aux
        # écritures rapprochées (rafale de braquets du 28 octobre).
        self.busy_window_s = float(busy_window_s)
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
        self._busy_until = 0.0
        self.other_device_until = 0.0   # un autre appareil (montre) occupe le Control Point
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
        if now < max(self._busy_until, self.other_device_until):
            self.commands.append(CpRecord(now, op, data, None))
            raise att_error(0x80)
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
        self._busy_until = self.world.now() + self.busy_window_s
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
            self.wind_mps = struct.unpack_from("<h", data, 1)[0] / 1000.0
            self.grade_pct = struct.unpack_from("<h", data, 3)[0] / 100.0
            self.crr, self.cw = data[5] / 10000.0, data[6] / 100.0
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

    def _ride_speed(self, rider: RiderOutput) -> float:
        """Vitesse tenue par le cycliste à braquet fixe (modèle réaliste) : `speed_kmh` de la stratégie
        `vitesse`, sinon la vitesse de son effort sur le plat (arrondi au watt) ; 0 sans pédaler."""
        if rider.cadence_rpm <= 0:
            return 0.0
        if self.rider.speed_kmh is not None:
            return self.rider.speed_kmh / 3.6
        watts = round(max(rider.power_w, 0.0))
        if self._v_ride_cache[0] != watts:
            self._v_ride_cache = (watts, steady_speed(watts, 0.0, SPEED_PHYSICS))
        return self._v_ride_cache[1]

    def _step_power(self, t: float, dt: float, rider: RiderOutput) -> float:
        """Puissance mesurée après `dt` s, et vitesse affichée en km/h."""
        if self.model is not None:
            cmd = (self.mode, self.target_w, self.grade_pct, self.crr, self.cw, self.wind_mps)
            cap = self.rider_max_w if self.rider_max_w is not None else RIDER_RESERVE * max(rider.power_w, 1.0)
            self.power_w = self.model.step(dt, cmd, self._ride_speed(rider), cap)
            return 3.6 * self.model.v
        if self.mode == "erg" and self.target_w is not None and rider.cadence_rpm > 0:
            goal = self.target_w + 2.0 * math.sin(t * 1.5)
        else:
            goal = rider.power_w
        alpha = 1.0 - math.exp(-dt / max(self.erg_tau_s, 1e-3))
        self.power_w += alpha * (goal - self.power_w)
        return 3.6 * (max(self.power_w, 0.0) / 0.9) ** (1 / 3) if self.power_w > 0 else 0.0

    async def _data_loop(self) -> None:
        period = 1.0 / self.ibd_hz
        last = self.world.now()
        while True:
            jitter = self._jitter_rng.uniform(-self.notify_jitter_s, self.notify_jitter_s) if self.notify_jitter_s else 0.0
            await asyncio.sleep(max(period + jitter, 0.0))
            t = self.world.now()
            dt, last = t - last, t
            erg = self.mode == "erg" and self.target_w is not None
            rider = self.rider.step(t, dt, self.grade_pct, self.target_w if erg else None)
            if rider.press:   # braquet changé par le cycliste virtuel (stratégie `cadence`)
                asyncio.get_running_loop().create_task(self.world.press(rider.press))
            speed_kmh = self._step_power(t, dt, rider)
            if t < self.silent_until:
                continue
            cadence = rider.cadence_rpm + (1.5 * math.sin(t * 0.7) if rider.cadence_rpm > 0 else 0.0)
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

# Boutons du Click simulé (Click V2, `zwift_click.KEYPAD_BITS`) : nom accepté par `press` -> (boîtier, touche).
# Boîtier droit (« + ») : +, A, B, Y, Z ; boîtier gauche (« − ») : −, flèches.
CLICK_BUTTONS: dict[str, tuple[str, str]] = {
    "+": ("+", "+"), "-": ("-", "-"),
    **{b: ("+", b) for b in ("A", "B", "Y", "Z")},
    **{b: ("-", b) for b in ("LEFT", "UP", "RIGHT", "DOWN")},
}
_BUTTON_ALIASES = {"−": "-", "MINUS": "-", "MOINS": "-", "PLUS": "+"}


def click_button(name: str) -> tuple[str, str]:
    """(boîtier, touche) d'un bouton du Click simulé ; KeyError si le nom est inconnu."""
    key = str(name).strip().upper()
    return CLICK_BUTTONS[_BUTTON_ALIASES.get(key, key)]


class SimWorld:
    """Les appareils simulés d'une séance, leur horloge et la recherche BLE.

    `find_device` et `client_factory` ont la signature attendue par les pilotes réels.
    `run()` déroule les événements du scénario ; l'horloge part au premier appel de `now()`.
    `control_file` (facultatif) : fichier suivi pendant la séance, une ligne JSON par événement à
    appliquer tout de suite (même format qu'un événement du scénario, sans « t ») ; le banc des menus
    (`engine/tests/menu_bench.py`) y écrit ses appuis du Click.
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
        self.control_file: str | None = None
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
        """Appui sur un bouton du Click simulé (`CLICK_BUTTONS`), avec le relais du « + » par le boîtier « − »."""
        role, button = click_button(button)
        own = self._box(role)
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
        if self.control_file:
            asyncio.get_running_loop().create_task(self._follow_control(self.control_file))
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

    async def _follow_control(self, path: str, period_s: float = 0.02) -> None:
        """Applique chaque ligne JSON ajoutée à `path` (créé vide s'il manque) jusqu'à l'arrêt du monde."""
        with open(path, "a+", encoding="utf-8") as f:
            f.seek(0)
            pending = ""
            while not self._stop.is_set():
                pending += f.read()
                *lines, pending = pending.split("\n")
                for line in filter(str.strip, lines):
                    try:
                        await self.apply(json.loads(line))
                    except Exception as exc:   # ligne illisible : signalée, la séance continue
                        log.warning("Simulation : commande %r impossible : %s", line, exc)
                await asyncio.sleep(period_s)

    async def apply(self, ev: dict[str, Any]) -> None:
        action = ev["action"]
        log.info("Simulation (t=%.1f s) : %s", self.now(), _describe(ev))
        if action == "press":
            click_button(ev.get("button", "+"))   # bouton inconnu : KeyError avant l'appui
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
        elif isinstance(dev, SimTrainer) and action == "other_device":
            dev.other_device_until = self.now() + float(ev["seconds"])
        elif isinstance(dev, SimTrainer) and action == "cp_silent":
            dev.pending_silent_responses += int(ev.get("count", 1))
        elif isinstance(dev, (SimTrainer, SimClickBox)) and action == "silence":
            dev.silent_until = self.now() + float(ev["seconds"])
        elif isinstance(dev, SimTrainer) and action == "control_lost":
            dev.lose_control()
        elif isinstance(dev, SimTrainer) and action == "refuse_control":
            dev.refuse_control = bool(ev.get("value", True))
        elif isinstance(dev, SimTrainer) and action == "rider":
            dev.rider.update(**{k: ev[k] for k in ("watts", "cadence_rpm") if k in ev})
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
