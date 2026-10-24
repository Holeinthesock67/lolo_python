"""Lecture de ~/OpenRide/config.toml (SRS §11).

Toute clé absente prend la valeur par défaut ci-dessous : un fichier vide ou absent
donne une configuration complète et utilisable.

Lecture stricte sur les types et les bornes (lot J3) : une valeur invalide lève `ConfigError`,
avec un message qui cite le fichier, la section et la clé. Une clé ou une section inconnue
(faute de frappe) donne un avertissement au journal, sans erreur.
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("config")

OPENRIDE_HOME = Path.home() / "OpenRide"
DEFAULT_CONFIG_PATH = OPENRIDE_HOME / "config.toml"
GPX_DIR = OPENRIDE_HOME / "GPX"             # traces GPX à compiler (SRS §7, §11)
WORKOUTS_DIR = OPENRIDE_HOME / "Workouts"   # entraînements .zwo (SRS §6, §11)
ROUTES_DIR = Path.home() / ".local" / "share" / "openride" / "routes"
CACHE_DIR = Path.home() / ".cache" / "openride"


@dataclass
class RiderConfig:
    ftp_w: float = 250.0
    mass_kg: float = 75.0


@dataclass
class BikeConfig:
    mass_kg: float = 9.0
    cda_m2: float = 0.32
    crr: float = 0.004
    drivetrain_efficiency: float = 0.97


@dataclass
class TrainerConfig:
    device_name: str = "HomeTrainer"   # fragment du nom annoncé (ex. « HomeTrainer 0000 »)
    latency_tau_s: float = 0.8
    difficulty_pct: float = 100.0
    grade_min_pct: float = -10.0
    grade_max_pct: float = 16.0
    power_smooth_tau_s: float = 0.7   # lissage temporel de la puissance (indépendant de la cadence BLE)
    grade_rate_pct_per_s: float = 2.0  # vitesse maximale de variation de la pente envoyée


@dataclass
class GearingConfig:
    n_gears: int = 24
    start_gear: int = 12
    ratio_min: float = 0.40
    ratio_max: float = 3.00
    g_base_pct: float = 2.0
    long_press_gears: int = 10    # appui long en SIM : braquets sautés (3 était plus lent que des appuis courts)


@dataclass
class RenderConfig:
    quality: str = "low"
    theme: str = "default"


@dataclass
class IpcConfig:
    port_state: int = 5005
    port_commands: int = 5006


@dataclass
class DriversConfig:
    trainer: str = "mock"          # "mock", "ftms" ou "sim" (HomeTrainer simulé, voir ble_sim.py)
    input: str = "keyboard"        # "click", "keyboard", "none" ou "sim" (Click simulé)
    trainer_address: str = ""      # adresse MAC (vide : recherche par nom)
    click_address: str = ""
    click_short_max_s: float = 0.5
    click_long_min_s: float = 0.9
    mock_replay: str = ""          # chemin d'un journal (.jsonl) ou d'un .fit à rejouer en mode mock
    hr: str = "none"               # ceinture cardio : "none", "ble" ou "sim"
    hr_address: str = ""           # adresse MAC de la ceinture (vide : recherche par nom ou service)
    hr_name: str = ""              # fragment du nom BLE (vide : tout appareil annonçant le service 0x180D)
    sim_scenario: str = ""         # Bluetooth simulé : scénario intégré ou fichier JSON (vide : demo)


@dataclass
class Config:
    rider: RiderConfig = field(default_factory=RiderConfig)
    bike: BikeConfig = field(default_factory=BikeConfig)
    trainer: TrainerConfig = field(default_factory=TrainerConfig)
    gearing: GearingConfig = field(default_factory=GearingConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    ipc: IpcConfig = field(default_factory=IpcConfig)
    drivers: DriversConfig = field(default_factory=DriversConfig)

    @property
    def total_mass_kg(self) -> float:
        return self.rider.mass_kg + self.bike.mass_kg


class ConfigError(Exception):
    """Configuration invalide ; le message est lisible par l'utilisateur."""


# Bornes (inclusives) des valeurs numériques : (section, clé) -> (minimum, maximum).
BOUNDS: dict[tuple[str, str], tuple[float, float]] = {
    ("rider", "ftp_w"): (50, 600),
    ("rider", "mass_kg"): (20, 200),
    ("bike", "mass_kg"): (3, 30),
    ("bike", "cda_m2"): (0.1, 1.0),
    ("bike", "crr"): (0.001, 0.02),
    ("bike", "drivetrain_efficiency"): (0.8, 1.0),
    ("trainer", "latency_tau_s"): (0, 5),
    ("trainer", "difficulty_pct"): (0, 100),
    ("trainer", "grade_min_pct"): (-30, 0),
    ("trainer", "grade_max_pct"): (0, 30),
    ("trainer", "power_smooth_tau_s"): (0, 5),
    ("trainer", "grade_rate_pct_per_s"): (0.1, 100),
    ("gearing", "n_gears"): (2, 40),
    ("gearing", "start_gear"): (1, 40),
    ("gearing", "ratio_min"): (0.1, 5),
    ("gearing", "ratio_max"): (0.1, 5),
    ("gearing", "g_base_pct"): (-10, 10),
    ("gearing", "long_press_gears"): (1, 10),
    ("ipc", "port_state"): (1024, 65535),
    ("ipc", "port_commands"): (1024, 65535),
    ("drivers", "click_short_max_s"): (0.05, 5),
    ("drivers", "click_long_min_s"): (0.05, 5),
}
# Valeurs permises des champs textuels à choix fermé.
CHOICES: dict[tuple[str, str], tuple[str, ...]] = {
    ("render", "quality"): ("low", "medium", "high"),
    ("drivers", "trainer"): ("mock", "ftms", "sim"),
    ("drivers", "input"): ("click", "keyboard", "none", "sim"),
    ("drivers", "hr"): ("none", "ble", "sim"),
}


def _convert(current: Any, value: Any, where: str) -> Any:
    """Valeur TOML vers le type de la valeur par défaut ; un booléen n'est jamais un nombre."""
    if isinstance(current, bool) or isinstance(value, bool):
        raise ConfigError(f"{where} : valeur {value!r} invalide")
    if isinstance(current, float):
        if not isinstance(value, (int, float)):
            raise ConfigError(f"{where} : nombre attendu, reçu {value!r}")
        return float(value)
    if isinstance(current, int):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if not isinstance(value, int):
            raise ConfigError(f"{where} : entier attendu, reçu {value!r}")
        return value
    if isinstance(current, str):
        if not isinstance(value, str):
            raise ConfigError(f"{where} : texte attendu, reçu {value!r}")
        return value
    return type(current)(value)


def _merge(dc: Any, data: dict[str, Any], source: str = "config.toml", section: str = "") -> Any:
    """Recopie dans la dataclass `dc` les clés connues de `data` ; signale les clés inconnues."""
    known = {f.name for f in fields(dc)}
    for key in data:
        if key not in known:
            name = f"[{section}] {key}" if section else f"[{key}]"
            log.warning("%s : clé inconnue %s ignorée (faute de frappe ?)", source, name)
    for f in fields(dc):
        if f.name not in data:
            continue
        current = getattr(dc, f.name)
        value = data[f.name]
        if is_dataclass(current):
            if not isinstance(value, dict):
                raise ConfigError(f"{source}, [{f.name}] : section attendue, reçu {value!r}")
            _merge(current, value, source, f.name)
        else:
            setattr(dc, f.name, _convert(current, value, f"{source}, [{section}] {f.name}"))
    return dc


def validate(cfg: Config, source: str = "config.toml") -> Config:
    """Contrôle les bornes et les cohérences ; lève `ConfigError` au premier défaut trouvé."""
    for (sec, key), (lo, hi) in BOUNDS.items():
        value = getattr(getattr(cfg, sec), key)
        if not lo <= value <= hi:
            raise ConfigError(f"{source}, [{sec}] {key} : {value:g} hors de {lo:g} à {hi:g}")
    for (sec, key), allowed in CHOICES.items():
        value = getattr(getattr(cfg, sec), key)
        if value not in allowed:
            raise ConfigError(f"{source}, [{sec}] {key} : {value!r} n'est pas parmi {', '.join(allowed)}")
    g, t, ipc = cfg.gearing, cfg.trainer, cfg.ipc
    if not 1 <= g.start_gear <= g.n_gears:
        raise ConfigError(f"{source}, [gearing] start_gear : {g.start_gear} hors de 1 à n_gears ({g.n_gears})")
    if g.ratio_min >= g.ratio_max:
        raise ConfigError(f"{source}, [gearing] ratio_min : doit être inférieur à ratio_max")
    if t.grade_min_pct >= t.grade_max_pct:
        raise ConfigError(f"{source}, [trainer] grade_min_pct : doit être inférieur à grade_max_pct")
    if ipc.port_state == ipc.port_commands:
        raise ConfigError(f"{source}, [ipc] port_commands : doit différer de port_state")
    return cfg


def from_dict(data: dict[str, Any], source: str = "config.toml") -> Config:
    return validate(_merge(Config(), data, source), source)


def load(path: Path | None = None) -> Config:
    """Charge la configuration ; un fichier absent donne les valeurs par défaut.

    Lève `ConfigError` si le fichier est illisible, mal formé ou contient une valeur invalide.
    """
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return Config()
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} : TOML invalide : {exc}") from None
    except OSError as exc:
        raise ConfigError(f"{path} : lecture impossible : {exc}") from None
    return from_dict(data, str(path))
