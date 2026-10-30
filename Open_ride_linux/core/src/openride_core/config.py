"""Lecture de ~/OpenRide/config.toml (SRS §11).

Toute clé absente prend la valeur par défaut ci-dessous : un fichier vide ou absent
donne une configuration complète et utilisable.

Lecture stricte sur les types et les bornes (lot J3) : une valeur invalide lève `ConfigError`,
avec un message qui cite le fichier, la section et la clé. Une clé ou une section inconnue
(faute de frappe) donne un avertissement au journal, sans erreur.
"""

from __future__ import annotations

import logging
import re
import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("config")

OPENRIDE_HOME = Path.home() / "OpenRide"
DEFAULT_CONFIG_PATH = OPENRIDE_HOME / "config.toml"
GPX_DIR = OPENRIDE_HOME / "GPX"             # traces GPX à compiler (SRS §7, §11)
WORKOUTS_DIR = OPENRIDE_HOME / "Workouts"   # entraînements .zwo (SRS §6, §11)
PLANS_DIR = OPENRIDE_HOME / "Plans"         # plans d'entraînement .toml (lot O11)
ROUTES_DIR = Path.home() / ".local" / "share" / "openride" / "routes"
CACHE_DIR = Path.home() / ".cache" / "openride"


@dataclass
class RiderConfig:
    ftp_w: float = 250.0
    mass_kg: float = 75.0
    hr_max_bpm: int = 185   # fréquence cardiaque maximale : zones de FC du HUD


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
    difficulty_pct: float = 50.0
    grade_min_pct: float = -10.0
    grade_max_pct: float = 16.0
    power_smooth_tau_s: float = 0.7   # lissage temporel de la puissance (indépendant de la cadence BLE)
    grade_rate_pct_per_s: float = 2.0  # ancien réglage symétrique, lu seulement si up et down manquent (lot Q4)
    grade_rate_up_pct_per_s: float = 4.0   # vitesse maximale quand la pente envoyée augmente (lot Q4)
    grade_rate_down_pct_per_s: float = 8.0 # vitesse maximale quand elle diminue (lot Q4)
    trace_ftms: bool = False          # trace horodatée de chaque échange Control Point FTMS (lot Q3)
    hr_relay_freeze_s: float = 15.0   # détection cardio relayée figée (lot Q5)
    resend_s: float = 2.0             # la consigne SIM/ERG est renvoyée au moins toutes les resend_s secondes (30 octobre : essai à 10–15 s contre le pompage)


@dataclass
class GearingConfig:
    n_gears: int = 24
    start_gear: int = 12
    ratio_min: float = 0.65    # 0,40 à 3,00 avant le 28 octobre : petits braquets à plat, moitié haute inutile
    ratio_max: float = 2.00
    g_base_pct: float = 2.0
    long_press_gears: int = 10    # appui long en SIM : braquets sautés (3 était plus lent que des appuis courts)


@dataclass
class RenderConfig:
    quality: str = "low"
    theme: str = "default"
    visual_grade_scale: float = 2.5   # relief affiché ×2,5 (lot Y15) ; 1,0 : relief réel ; physique et HUD inchangés
    living: bool = True    # décor vivant de la série P (vent, nuages, sons) ; faux : rendu de la 1.0 (lot P16)
    chart: str = "reduced"  # courbes de la séance (lot O14) : hidden, reduced (cible et puissance) ou full
    camera: str = "follow_near"   # vue de caméra (lot V12) : subjective, follow_near, follow_far ou side ; reprise au lancement
    fps: str = "off"        # compteur d'images/s en haut à droite du HUD : off, on ou detail (+ temps CPU et GPU, essais)
    draft_gauge: str = "off"   # jauge d'abri au-dessus du bot qui t'abrite : off ou on (coupée par défaut)
    display: str = "fullscreen"   # fenêtre de l'engine : windowed, borderless (plein écran sans bordure) ou fullscreen (exclusif)


@dataclass
class EngineConfig:
    godot: str = ""   # chemin de Godot 4.7 (vide : variable GODOT ou ~/Applications/godot), lot N14


@dataclass
class IpcConfig:
    port_state: int = 5005
    port_commands: int = 5006


@dataclass
class DriversConfig:
    trainer: str = "mock"          # "mock", "ftms" ou "sim" (HomeTrainer simulé, voir ble_sim.py)
    input: str = "keyboard"        # "click", "keyboard", "none" ou "sim" (Click simulé)
    trainer_address: str = ""      # adresse MAC (vide : recherche par nom)
    click_address: str = ""        # boîtier « + » du Click (lot N12 : `openride-core devices --save`)
    click_minus_address: str = ""  # boîtier « − » du Click (vide : l'autre boîtier trouvé)
    click_short_max_s: float = 0.5
    click_long_min_s: float = 0.9
    click_trace_raw: bool = False
    click_mute_after_s: float = 60.0
    click_rehandshake_s: float = 0.0
    mock_replay: str = ""          # chemin d'un journal (.jsonl) ou d'un .fit à rejouer en mode mock
    hr: str = "none"               # ceinture cardio : "none", "ble" ou "sim"
    hr_address: str = ""           # adresse MAC de la ceinture (vide : recherche par nom ou service)
    hr_name: str = ""              # fragment du nom BLE (vide : tout appareil annonçant le service 0x180D)
    sim_scenario: str = ""         # Bluetooth simulé : scénario intégré ou fichier JSON (vide : demo)


@dataclass
class OpenWorldConfig:
    """Monde ouvert de la 2.0 (série W, `docs/contracts/worldgen_v1.md` §6) ; lu par le générateur."""

    cache_dir: str = "~/OpenRide/Cache/monde"   # cache des cartes et du monde généré (plan W §4)
    cache_max_gb: float = 5.0                   # plafond du cache (décision W-Q3)
    horizon_m: float = 3000.0                   # route engagée devant le cycliste
    offer_m: float = 300.0                      # distance à laquelle un carrefour est proposé
    lock_m: float = 30.0                        # verrouillage du choix avant le carrefour
    preview_m: float = 500.0                    # amorce calculée pour chaque branche
    recenter_m: float = 10000.0                 # recentrage de l'origine de rendu dans l'engine
    network: bool = True                        # faux : cache seulement, aucun téléchargement
    prefetch_history: bool = True               # préchargement autour des départs habituels (W-Q4)
    prefetch_radius_km: float = 10.0


@dataclass
class WindConfig:
    """Vent du core (lot P2, SRS §5 et §11) ; coupé par défaut dans les versions 1.x."""
    mode: str = "off"              # "off", "fixed", "gusty" ou "theme" (vent du thème 1.2)
    speed_kmh: float = 0.0
    from_deg: float = 270.0        # d'où vient le vent, degrés depuis le nord
    gust_pct: float = 0.0          # amplitude des rafales (modes "gusty" et "theme")
    seed: int = 0                  # graine des rafales
    feel: str = "grade"            # "grade" (supplément de pente) ou "ftms" (champ vent de 0x11)
    max_grade_offset_pct: float = 4.0   # borne du supplément de pente, réglable dans le menu


@dataclass
class ProgressionConfig:
    """Progression de la série V (lot V11) ; faux : ni équipement ni `progression`, comme avant la 2.0."""
    enabled: bool = True


@dataclass
class AvatarConfig:
    """Position en danseuse de l'avatar (lot V6) : l'engine passe debout au-dessus de l'un des deux seuils."""
    standing_grade_pct: float = 8.0      # pente (%)
    standing_power_pct: float = 150.0    # puissance (% de la FTP)


@dataclass
class RogueConfig:
    """Mode Cyber-Rogue de la 2.0 (série R, SRS §11)."""

    w_prime_j: float = 20000.0   # réserve anaérobie W' (décision Q5)
    cp_w: float = 0.0            # puissance critique ; 0 : la FTP du cavalier
    grade_rate_up_pct_per_s: float = 8.0     # rampe de pente du trainer propre au mode (lot R8, valeur de R0)
    grade_rate_down_pct_per_s: float = 12.0


@dataclass
class PowerupsConfig:
    """Bonus du mode classique (série T, lots T6 et T7) ; valeurs dans `~/OpenRide/powerups.toml`."""
    mode: str = "on"               # "on" ou "off" (ni arche ni réserve ; segments toujours chronométrés)


@dataclass
class BotsConfig:
    """Bots à profil du mode classique (série T, lot T13) : calibrés au départ sur la FTP du cycliste."""
    level_pct: int = 100           # niveau des bots, en % de la FTP (50 à 150 ; 110 : plus forts que toi)


@dataclass
class AudioConfig:
    """Volumes du menu Réglages, en % (0 : coupé), un par catégorie de docs/AUDIO.md ; appliqués tout de
    suite par l'engine sur ses bus audio (audio_mix.gd)."""
    master_pct: int = 100          # volume général (bus Master)
    ride_pct: int = 100            # vélo : vent dans les oreilles, roue libre, « clac » de reprise
    ambience_pct: int = 100        # ambiance : fonds, cloches, points sonores, véhicules, foule, passants
    events_pct: int = 100          # bips et événements : appuis du Click, bloc ERG, consignes, jingles


@dataclass
class LogConfig:
    latence: bool = False   # journal de latence des appuis du Click, `[latence]` (lot X7, docs/OUTILS_DE_TEST.md)


@dataclass
class Config:
    rider: RiderConfig = field(default_factory=RiderConfig)
    bike: BikeConfig = field(default_factory=BikeConfig)
    trainer: TrainerConfig = field(default_factory=TrainerConfig)
    gearing: GearingConfig = field(default_factory=GearingConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    ipc: IpcConfig = field(default_factory=IpcConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    drivers: DriversConfig = field(default_factory=DriversConfig)
    open_world: OpenWorldConfig = field(default_factory=OpenWorldConfig)
    wind: WindConfig = field(default_factory=WindConfig)
    progression: ProgressionConfig = field(default_factory=ProgressionConfig)
    avatar: AvatarConfig = field(default_factory=AvatarConfig)
    rogue: RogueConfig = field(default_factory=RogueConfig)
    powerups: PowerupsConfig = field(default_factory=PowerupsConfig)
    bots: BotsConfig = field(default_factory=BotsConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    log: LogConfig = field(default_factory=LogConfig)

    @property
    def total_mass_kg(self) -> float:
        return self.rider.mass_kg + self.bike.mass_kg


class ConfigError(Exception):
    """Configuration invalide ; le message est lisible par l'utilisateur."""


# Bornes (inclusives) des valeurs numériques : (section, clé) -> (minimum, maximum).
BOUNDS: dict[tuple[str, str], tuple[float, float]] = {
    ("rider", "ftp_w"): (50, 600),
    ("rider", "mass_kg"): (20, 200),
    ("rider", "hr_max_bpm"): (120, 230),
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
    ("trainer", "grade_rate_up_pct_per_s"): (0.1, 100),
    ("trainer", "grade_rate_down_pct_per_s"): (0.1, 100),
    ("trainer", "hr_relay_freeze_s"): (5, 120),
    ("trainer", "resend_s"): (0.5, 60),
    ("gearing", "n_gears"): (2, 40),
    ("gearing", "start_gear"): (1, 40),
    ("gearing", "ratio_min"): (0.1, 5),
    ("gearing", "ratio_max"): (0.1, 5),
    ("gearing", "g_base_pct"): (-10, 10),
    ("gearing", "long_press_gears"): (1, 10),
    ("ipc", "port_state"): (1024, 65535),
    ("ipc", "port_commands"): (1024, 65535),
    ("render", "visual_grade_scale"): (1.0, 3.0),
    ("drivers", "click_short_max_s"): (0.05, 5),
    ("drivers", "click_long_min_s"): (0.05, 5),
    ("open_world", "cache_max_gb"): (0.5, 500),
    ("open_world", "horizon_m"): (1000, 10000),
    ("open_world", "offer_m"): (50, 2000),
    ("open_world", "lock_m"): (5, 200),
    ("open_world", "preview_m"): (100, 2000),
    ("open_world", "recenter_m"): (1000, 100000),
    ("open_world", "prefetch_radius_km"): (0, 100),
    ("drivers", "click_mute_after_s"): (1, 600),
    ("drivers", "click_rehandshake_s"): (0, 600),
    ("wind", "speed_kmh"): (0, 60),
    ("wind", "from_deg"): (0, 360),
    ("wind", "gust_pct"): (0, 100),
    ("wind", "max_grade_offset_pct"): (0, 8),
    ("avatar", "standing_grade_pct"): (3, 15),
    ("avatar", "standing_power_pct"): (100, 300),
    ("rogue", "w_prime_j"): (5000, 60000),
    ("rogue", "cp_w"): (0, 1000),
    ("rogue", "grade_rate_up_pct_per_s"): (0.1, 100),
    ("rogue", "grade_rate_down_pct_per_s"): (0.1, 100),
    ("bots", "level_pct"): (50, 150),
    ("audio", "master_pct"): (0, 100),
    ("audio", "ride_pct"): (0, 100),
    ("audio", "ambience_pct"): (0, 100),
    ("audio", "events_pct"): (0, 100),
}
# Adresses Bluetooth : vides (recherche) ou de la forme AA:BB:CC:DD:EE:FF (lot N12).
ADDRESS_KEYS = (("drivers", "trainer_address"), ("drivers", "click_address"),
                ("drivers", "click_minus_address"), ("drivers", "hr_address"))
ADDRESS_RE = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")

# Valeurs permises des champs textuels à choix fermé.
CHOICES: dict[tuple[str, str], tuple[str, ...]] = {
    ("render", "quality"): ("low", "medium", "high"),
    ("render", "chart"): ("hidden", "reduced", "full"),
    ("render", "fps"): ("off", "on", "detail"),
    ("render", "draft_gauge"): ("off", "on"),
    ("render", "display"): ("windowed", "borderless", "fullscreen"),
    ("render", "camera"): ("subjective", "follow_near", "follow_far", "side"),
    ("drivers", "trainer"): ("mock", "ftms", "sim"),
    ("drivers", "input"): ("click", "keyboard", "none", "sim"),
    ("drivers", "hr"): ("none", "ble", "sim"),
    ("wind", "mode"): ("off", "fixed", "gusty", "theme"),
    ("wind", "feel"): ("grade", "ftms"),
    ("powerups", "mode"): ("on", "off"),
}


def _convert(current: Any, value: Any, where: str) -> Any:
    """Valeur TOML vers le type de la valeur par défaut ; un booléen n'est jamais un nombre."""
    if isinstance(current, bool):
        if not isinstance(value, bool):
            raise ConfigError(f"{where} : booléen attendu, reçu {value!r}")
        return value
    if isinstance(value, bool):
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
    if section == "trainer" and "grade_rate_pct_per_s" in data:
        if "grade_rate_up_pct_per_s" not in data and "grade_rate_down_pct_per_s" not in data:
            log.warning(
                "%s, [trainer] grade_rate_pct_per_s : réglage remplacé par grade_rate_up_pct_per_s "
                "et grade_rate_down_pct_per_s",
                source,
            )
            dc.grade_rate_up_pct_per_s = dc.grade_rate_pct_per_s
            dc.grade_rate_down_pct_per_s = dc.grade_rate_pct_per_s
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
    for sec, key in ADDRESS_KEYS:
        value = getattr(getattr(cfg, sec), key)
        if value and not ADDRESS_RE.match(value):
            raise ConfigError(f"{source}, [{sec}] {key} : adresse Bluetooth {value!r} mal formée "
                              "(attendu AA:BB:CC:DD:EE:FF)")
    g, t, ipc = cfg.gearing, cfg.trainer, cfg.ipc
    if not 1 <= g.start_gear <= g.n_gears:
        raise ConfigError(f"{source}, [gearing] start_gear : {g.start_gear} hors de 1 à n_gears ({g.n_gears})")
    if g.ratio_min >= g.ratio_max:
        raise ConfigError(f"{source}, [gearing] ratio_min : doit être inférieur à ratio_max")
    if t.grade_min_pct >= t.grade_max_pct:
        raise ConfigError(f"{source}, [trainer] grade_min_pct : doit être inférieur à grade_max_pct")
    ow = cfg.open_world
    if not ow.cache_dir.strip():
        raise ConfigError(f"{source}, [open_world] cache_dir : dossier vide")
    if ow.lock_m >= ow.offer_m:
        raise ConfigError(f"{source}, [open_world] lock_m : doit être inférieur à offer_m")
    if ow.preview_m > ow.horizon_m:
        raise ConfigError(f"{source}, [open_world] preview_m : ne doit pas dépasser horizon_m")
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
