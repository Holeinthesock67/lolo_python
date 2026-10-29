"""Encodage et décodage du protocole Bluetooth FTMS (Fitness Machine Service 1.0).

Fonctions pures, sans dépendance à bleak : utilisées par l'outil de diagnostic du sprint 0
et par le futur FtmsDriver (SRS §4.1). Tous les champs sont en petit-boutiste.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

# UUID 16 bits normalisés, sous forme complète pour bleak.
def uuid16(short: int) -> str:
    return f"0000{short:04x}-0000-1000-8000-00805f9b34fb"


FTMS_SERVICE = uuid16(0x1826)
FEATURE = uuid16(0x2ACC)
INDOOR_BIKE_DATA = uuid16(0x2AD2)
TRAINING_STATUS = uuid16(0x2AD3)
SUPPORTED_RESISTANCE_RANGE = uuid16(0x2AD6)
SUPPORTED_POWER_RANGE = uuid16(0x2AD8)
CONTROL_POINT = uuid16(0x2AD9)
MACHINE_STATUS = uuid16(0x2ADA)
HR_SERVICE = uuid16(0x180D)
HR_MEASUREMENT = uuid16(0x2A37)
BATTERY_SERVICE = uuid16(0x180F)
BATTERY_LEVEL = uuid16(0x2A19)
CYCLING_POWER_SERVICE = uuid16(0x1818)
BATTERY_SERVICE = uuid16(0x180F)
DEVICE_INFO_SERVICE = uuid16(0x180A)

# Opcodes du Control Point
OP_REQUEST_CONTROL = 0x00
OP_RESET = 0x01
OP_SET_TARGET_POWER = 0x05
OP_START_RESUME = 0x07
OP_STOP_PAUSE = 0x08
OP_SET_SIM_PARAMS = 0x11
OP_RESPONSE = 0x80

# Codes d'erreur ATT renvoyés par l'écriture elle-même (FTMS §4.16.3, CSS partie B §1.2).
ATT_PROCEDURE_IN_PROGRESS = 0xFE
ATT_CCCD_IMPROPERLY_CONFIGURED = 0xFD

RESULT_CODES = {
    0x01: "SUCCESS",
    0x02: "OP_CODE_NOT_SUPPORTED",
    0x03: "INVALID_PARAMETER",
    0x04: "OPERATION_FAILED",
    0x05: "CONTROL_NOT_PERMITTED",
}

# Fitness Machine Status (0x2ADA), FTMS §4.17 tableau 4.26 : codes utiles à un vélo.
MACHINE_STATUS_CODES = {
    0x01: "RESET",
    0x02: "STOPPED_OR_PAUSED_BY_USER",
    0x03: "STOPPED_BY_SAFETY_KEY",
    0x04: "STARTED_OR_RESUMED_BY_USER",
    0x07: "TARGET_RESISTANCE_CHANGED",
    0x08: "TARGET_POWER_CHANGED",
    0x12: "SIM_PARAMS_CHANGED",
    0x13: "WHEEL_CIRCUMFERENCE_CHANGED",
    0x14: "SPIN_DOWN_STATUS",
    0xFF: "CONTROL_PERMISSION_LOST",
}
STATUS_CONTROL_LOST = 0xFF

MACHINE_FEATURE_BITS = {
    0: "average_speed", 1: "cadence", 2: "total_distance", 3: "inclination",
    4: "elevation_gain", 5: "pace", 6: "step_count", 7: "resistance_level",
    8: "stride_count", 9: "expended_energy", 10: "heart_rate", 11: "metabolic_equivalent",
    12: "elapsed_time", 13: "remaining_time", 14: "power_measurement",
    15: "force_on_belt_and_power_output", 16: "user_data_retention",
}

TARGET_FEATURE_BITS = {
    0: "speed_target", 1: "inclination_target", 2: "resistance_target", 3: "power_target",
    4: "heart_rate_target", 5: "expended_energy_config", 6: "step_number_config",
    7: "stride_number_config", 8: "distance_config", 9: "training_time_config",
    10: "time_two_hr_zones", 11: "time_three_hr_zones", 12: "time_five_hr_zones",
    13: "indoor_bike_simulation", 14: "wheel_circumference_config", 15: "spin_down_control",
    16: "targeted_cadence_config",
}


@dataclass
class Features:
    machine: list[str] = field(default_factory=list)
    target: list[str] = field(default_factory=list)

    @property
    def supports_sim(self) -> bool:
        return "indoor_bike_simulation" in self.target

    @property
    def supports_erg(self) -> bool:
        return "power_target" in self.target


def parse_features(data: bytes) -> Features:
    machine, target = struct.unpack_from("<II", data, 0)
    return Features(
        machine=[name for bit, name in MACHINE_FEATURE_BITS.items() if machine >> bit & 1],
        target=[name for bit, name in TARGET_FEATURE_BITS.items() if target >> bit & 1],
    )


@dataclass
class PowerRange:
    min_w: int
    max_w: int
    increment_w: int


def parse_power_range(data: bytes) -> PowerRange:
    return PowerRange(*struct.unpack_from("<hhH", data, 0))


def parse_machine_status(data: bytes) -> tuple[int, str] | None:
    """Décode 0x2ADA : (code, nom) ; None si la trame est vide."""
    if not data:
        return None
    return data[0], MACHINE_STATUS_CODES.get(data[0], f"0x{data[0]:02x}")


@dataclass
class IndoorBikeData:
    speed_kmh: float | None = None
    avg_speed_kmh: float | None = None
    cadence_rpm: float | None = None
    avg_cadence_rpm: float | None = None
    total_distance_m: int | None = None
    resistance_level: int | None = None
    power_w: int | None = None
    avg_power_w: int | None = None
    total_energy_kcal: int | None = None
    heart_rate_bpm: int | None = None
    elapsed_time_s: int | None = None
    remaining_time_s: int | None = None


# Taille de chaque champ optionnel d'Indoor Bike Data, par bit de drapeau (GATT Specification
# Supplement). Le niveau de résistance (bit 5) fait 2 octets (sint16) dans la définition XML
# d'origine, suivie par la plupart des trainers, mais 1 octet (uint8) dans le supplément actuel.
_IBD_SIZES = ((1, 2), (2, 2), (3, 2), (4, 3), (5, 2), (6, 2), (7, 2), (8, 5), (9, 1), (10, 1),
              (11, 2), (12, 2))
ENERGY_NOT_AVAILABLE = 0xFFFF   # FTMS §4.9.1.10 : « Data Not Available »


def _resistance_size(flags: int, length: int) -> int:
    """2 octets sauf si la longueur de la trame ne s'explique qu'avec 1 octet."""
    if not flags & 0x0020:
        return 0
    expected = 2 + (0 if flags & 0x0001 else 2)
    expected += sum(size for bit, size in _IBD_SIZES if flags >> bit & 1)
    return 1 if length == expected - 1 else 2


def parse_indoor_bike_data(data: bytes) -> IndoorBikeData:
    """Décode la caractéristique 0x2AD2 (champs présents selon les drapeaux).

    Un enregistrement peut être réparti sur plusieurs notifications (bit 0 « More Data » à 1,
    FTMS §4.19) : chaque trame ne porte alors qu'une partie des champs, les autres restent None.
    """
    flags = struct.unpack_from("<H", data, 0)[0]
    off = 2
    out = IndoorBikeData()

    def take(fmt: str):
        nonlocal off
        val = struct.unpack_from("<" + fmt, data, off)[0]
        off += struct.calcsize(fmt)
        return val

    # Bit 0 « More Data » inversé : 0 signifie que la vitesse instantanée est présente.
    if not flags & 0x0001:
        out.speed_kmh = take("H") / 100.0
    if flags & 0x0002:
        out.avg_speed_kmh = take("H") / 100.0
    if flags & 0x0004:
        out.cadence_rpm = take("H") / 2.0
    if flags & 0x0008:
        out.avg_cadence_rpm = take("H") / 2.0
    if flags & 0x0010:
        lo, hi = struct.unpack_from("<HB", data, off)
        off += 3
        out.total_distance_m = lo | hi << 16
    if flags & 0x0020:
        out.resistance_level = take("h" if _resistance_size(flags, len(data)) == 2 else "B")
    if flags & 0x0040:
        out.power_w = take("h")
    if flags & 0x0080:
        out.avg_power_w = take("h")
    if flags & 0x0100:
        energy = take("H")
        out.total_energy_kcal = None if energy == ENERGY_NOT_AVAILABLE else energy
        off += 3  # énergie par heure (uint16) et par minute (uint8)
    if flags & 0x0200:
        out.heart_rate_bpm = take("B")
    if flags & 0x0400:
        off += 1  # équivalent métabolique
    if flags & 0x0800:
        out.elapsed_time_s = take("H")
    if flags & 0x1000:
        out.remaining_time_s = take("H")
    return out


def parse_hr_measurement(data: bytes) -> int:
    """Décode 0x2A37 : fréquence cardiaque en bpm (uint8 ou uint16 selon le bit 0)."""
    if data[0] & 0x01:
        return struct.unpack_from("<H", data, 1)[0]
    return data[1]


@dataclass
class HrMeasurement:
    """Heart Rate Measurement 0x2A37 décodée en entier (Heart Rate Service 1.0, lot M2).

    `contact` : True ou False si la ceinture gère le contact du capteur, None sinon.
    `rr_ms` : intervalles RR en millisecondes (transmis en 1/1024 s).
    """
    bpm: int
    contact: bool | None = None
    energy_kj: int | None = None
    rr_ms: list[float] = field(default_factory=list)


def parse_hr_measurement_full(data: bytes) -> HrMeasurement:
    """Décode tous les champs de 0x2A37 ; trame trop courte : ValueError.

    Drapeaux : bit 0 format 16 bits, bits 1-2 contact (2 = géré absent, 3 = géré présent),
    bit 3 énergie dépensée (uint16, kJ), bit 4 intervalles RR (uint16, 1/1024 s).
    """
    try:
        flags = data[0]
        if flags & 0x01:
            bpm, i = struct.unpack_from("<H", data, 1)[0], 3
        else:
            bpm, i = data[1], 2
        energy = None
        if flags & 0x08:
            energy = struct.unpack_from("<H", data, i)[0]
            i += 2
    except (IndexError, struct.error):
        raise ValueError(f"Heart Rate Measurement trop courte : {bytes(data).hex()}") from None
    contact = bool(flags & 0x02) if flags & 0x04 else None
    rr: list[float] = []
    if flags & 0x10:
        for j in range(i, len(data) - 1, 2):
            rr.append(struct.unpack_from("<H", data, j)[0] * 1000.0 / 1024.0)
    return HrMeasurement(bpm=bpm, contact=contact, energy_kj=energy, rr_ms=rr)


# --- Commandes du Control Point -------------------------------------------------------

def cmd_request_control() -> bytes:
    return bytes([OP_REQUEST_CONTROL])


def cmd_reset() -> bytes:
    """Opcode 0x01 : remet les consignes à zéro ; en cas de succès, le client perd le contrôle
    (FTMS §4.16.2.2), ce qui le rend aux autres applications."""
    return bytes([OP_RESET])


def cmd_start_resume() -> bytes:
    return bytes([OP_START_RESUME])


def cmd_stop() -> bytes:
    return bytes([OP_STOP_PAUSE, 0x01])


def cmd_pause() -> bytes:
    return bytes([OP_STOP_PAUSE, 0x02])


def _sint16(value: float) -> int:
    return max(-32768, min(32767, int(round(value))))


def cmd_set_target_power(watts: float) -> bytes:
    """Opcode 0x05 : sint16 en watts, résolution 1 W."""
    return struct.pack("<Bh", OP_SET_TARGET_POWER, _sint16(watts))


def cmd_set_sim_params(grade_pct: float, crr: float = 0.004, cw_kg_m: float = 0.39,
                       wind_mps: float = 0.0) -> bytes:
    """Opcode 0x11. Résolutions : vent 0,001 m/s, pente 0,01 %, Crr 0,0001, Cw 0,01 kg/m.

    Cw (« wind resistance coefficient ») = ρ · CdA, sans le ½ (définition d'ANT+ FE-C reprise par
    FTMS : le trainer calcule lui-même la force 0,5 · Cw · v²) ; pour CdA 0,32 m² à 1,225 kg/m³,
    Cw ≈ 0,39 kg/m, valeur par défaut (Zwift envoie 0,51).
    """
    return struct.pack(
        "<BhhBB",
        OP_SET_SIM_PARAMS,
        _sint16(wind_mps * 1000),
        _sint16(grade_pct * 100),
        max(0, min(255, int(round(crr * 10000)))),
        max(0, min(255, int(round(cw_kg_m * 100)))),
    )


@dataclass
class ControlResponse:
    request_op: int
    result: int

    @property
    def ok(self) -> bool:
        return self.result == 0x01

    @property
    def result_name(self) -> str:
        return RESULT_CODES.get(self.result, f"UNKNOWN_0x{self.result:02x}")


def parse_control_response(data: bytes) -> ControlResponse | None:
    if len(data) < 3 or data[0] != OP_RESPONSE:
        return None
    return ControlResponse(request_op=data[1], result=data[2])
