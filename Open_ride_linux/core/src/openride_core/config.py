"""Lecture de ~/OpenRide/config.toml (SRS §11).

Toute clé absente prend la valeur par défaut ci-dessous : un fichier vide ou absent
donne une configuration complète et utilisable.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

OPENRIDE_HOME = Path.home() / "OpenRide"
DEFAULT_CONFIG_PATH = OPENRIDE_HOME / "config.toml"
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
    device_name: str = "Victory"   # fragment du nom annoncé (ex. « Victory 9908 »)
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
    ratio_min: float = 0.50
    ratio_max: float = 2.25
    g_base_pct: float = 2.0
    long_press_gears: int = 3     # appui long en SIM : nombre de braquets sautés


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
    trainer: str = "mock"          # "mock" ou "ftms"
    input: str = "keyboard"        # "click", "keyboard" ou "none"
    trainer_address: str = ""      # adresse MAC (vide : recherche par nom)
    click_address: str = ""
    click_short_max_s: float = 0.5
    click_long_min_s: float = 0.9


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


def _merge(dc: Any, data: dict[str, Any]) -> Any:
    """Recopie dans la dataclass `dc` les clés connues de `data` (les inconnues sont ignorées)."""
    for f in fields(dc):
        if f.name not in data:
            continue
        current = getattr(dc, f.name)
        value = data[f.name]
        if is_dataclass(current) and isinstance(value, dict):
            _merge(current, value)
        else:
            # Conversion vers le type de la valeur par défaut (ex. int TOML -> float).
            setattr(dc, f.name, type(current)(value))
    return dc


def from_dict(data: dict[str, Any]) -> Config:
    return _merge(Config(), data)


def load(path: Path | None = None) -> Config:
    """Charge la configuration ; un fichier absent donne les valeurs par défaut."""
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return Config()
    with path.open("rb") as fh:
        return from_dict(tomllib.load(fh))
