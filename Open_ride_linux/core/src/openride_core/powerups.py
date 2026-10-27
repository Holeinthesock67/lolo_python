"""Bonus du mode classique : légèreté, aérodynamique, puissance (lot T6, série T).

Module pur. Un bonus est obtenu au hasard à la fin de chaque segment et sous une arche tous
les 5 km ; un seul est gardé en réserve (un nouveau remplace l'ancien). Il s'active par le
bouton Z du Click (appui court) et agit pendant quelques secondes sur les paramètres de la
physique (`PhysicsParams`) ou sur la puissance prise en compte, donc sur la vitesse virtuelle
seulement : la résistance du trainer, la puissance du FIT, du journal et du bilan restent
celles mesurées. En ERG, les bonus sont désactivés. Cahier : `docs/lots/LOT_T6_bonus.md`.

Les valeurs se modifient dans `~/OpenRide/powerups.toml` (facultatif) :

    [lightweight]          # légèreté : masse totale × factor
    factor = 0.90
    duration_s = 15
    [aero]                 # aérodynamique : CdA × factor
    factor = 0.75
    duration_s = 15
    [power]                # puissance prise en compte par la physique × factor
    factor = 1.10
    duration_s = 15
    [obtain]
    arch_every_m = 5000    # 0 : pas d'arche
    per_segment = true
"""

from __future__ import annotations

import math
import random
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

from .config import OPENRIDE_HOME
from .physics import PhysicsParams

POWERUPS_FILE = OPENRIDE_HOME / "powerups.toml"

KINDS = ("lightweight", "aero", "power")
LABELS = {"lightweight": "Légèreté", "aero": "Aérodynamique", "power": "Puissance"}
SOURCES = ("segment", "arch")

FACTOR_MIN, FACTOR_MAX = 0.5, 1.5
DURATION_MIN_S, DURATION_MAX_S = 1.0, 120.0
ARCH_EVERY_MIN_M = 500.0


class PowerUpError(ValueError):
    """Fichier de valeurs invalide."""


@dataclass(frozen=True)
class PowerUpSpec:
    kind: str
    factor: float
    duration_s: float


@dataclass(frozen=True)
class PowerUpTable:
    specs: dict[str, PowerUpSpec]
    arch_every_m: float = 5000.0
    per_segment: bool = True


DEFAULT_TABLE = PowerUpTable(specs={
    "lightweight": PowerUpSpec("lightweight", 0.90, 15.0),
    "aero": PowerUpSpec("aero", 0.75, 15.0),
    "power": PowerUpSpec("power", 1.10, 15.0),
})


def _number(section: dict, key: str, default: float, lo: float, hi: float, where: str) -> float:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PowerUpError(f"{where}.{key} doit être un nombre")
    if not lo <= value <= hi:
        raise PowerUpError(f"{where}.{key} = {value} hors de [{lo}, {hi}]")
    return float(value)


def load_table(path: Path | None = None) -> PowerUpTable:
    """Valeurs des bonus : défauts du plan, remplacés par ceux du fichier s'il existe."""
    path = path or POWERUPS_FILE
    if not path.is_file():
        return DEFAULT_TABLE
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PowerUpError(f"{path} illisible : {exc}") from exc
    unknown = set(data) - set(KINDS) - {"obtain"}
    if unknown:
        raise PowerUpError(f"sections inconnues dans {path.name} : {', '.join(sorted(unknown))}")
    specs = {}
    for kind in KINDS:
        sec = data.get(kind, {})
        if not isinstance(sec, dict):
            raise PowerUpError(f"[{kind}] doit être une section")
        base = DEFAULT_TABLE.specs[kind]
        specs[kind] = PowerUpSpec(
            kind,
            _number(sec, "factor", base.factor, FACTOR_MIN, FACTOR_MAX, kind),
            _number(sec, "duration_s", base.duration_s, DURATION_MIN_S, DURATION_MAX_S, kind))
    obtain = data.get("obtain", {})
    if not isinstance(obtain, dict):
        raise PowerUpError("[obtain] doit être une section")
    every = _number(obtain, "arch_every_m", DEFAULT_TABLE.arch_every_m, 0.0, 1e6, "obtain")
    if 0.0 < every < ARCH_EVERY_MIN_M:
        raise PowerUpError(f"obtain.arch_every_m = {every} : 0 ou au moins {ARCH_EVERY_MIN_M:.0f} m")
    per_segment = obtain.get("per_segment", DEFAULT_TABLE.per_segment)
    if not isinstance(per_segment, bool):
        raise PowerUpError("obtain.per_segment doit valoir true ou false")
    return PowerUpTable(specs=specs, arch_every_m=every, per_segment=per_segment)


class ArchSchedule:
    """Arches de bonus à position fixe sur la route (tous les `every_m`, répétées à chaque tour)."""

    def __init__(self, every_m: float, length_m: float, loop: bool = False) -> None:
        self.length_m = float(length_m)
        self.loop = loop
        self.positions: list[float] = []
        if every_m > 0:
            k = 1
            while k * every_m < self.length_m - 1e-6:
                self.positions.append(k * every_m)
                k += 1

    def crossed(self, s_prev: float, s: float) -> int:
        """Nombre d'arches franchies entre deux positions cumulées (`s_prev` exclu, `s` inclus)."""
        if s <= s_prev or not self.positions:
            return 0
        if not self.loop:
            return sum(1 for p in self.positions if s_prev < p <= s)
        L = self.length_m
        count = 0
        for p in self.positions:
            # Nombre de k tels que s_prev < k·L + p <= s.
            count += math.floor((s - p) / L) - math.floor((s_prev - p) / L)
        return count


@dataclass(frozen=True)
class PowerUpUse:
    kind: str
    t_start: float           # temps chronométré de la séance à l'activation
    duration_s: float

    def to_dict(self) -> dict:
        return {"kind": self.kind, "t_start": round(self.t_start, 2),
                "duration_s": round(self.duration_s, 2)}


@dataclass
class PowerUps:
    """Réserve, bonus actif et effets ; `step` n'est appelé que pendant `RUNNING`."""

    table: PowerUpTable = DEFAULT_TABLE
    seed: int | None = None
    erg: bool = False
    reserve: str | None = None
    active: str | None = None
    remaining_s: float = 0.0
    uses: list[PowerUpUse] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    # --- obtention et activation ---------------------------------------------------------

    def award(self, source: str) -> str | None:
        """Bonus au hasard en réserve (remplace l'ancien) ; None en ERG ou si la source est coupée."""
        if source not in SOURCES:
            raise ValueError(f"source de bonus inconnue : {source}")
        if self.erg or (source == "segment" and not self.table.per_segment):
            return None
        self.reserve = self._rng.choice(KINDS)
        return self.reserve

    def activate(self, t: float) -> bool:
        """Appui court sur Z : active la réserve s'il n'y a pas déjà un bonus actif."""
        if self.erg or self.reserve is None or self.active is not None:
            return False
        spec = self.table.specs[self.reserve]
        self.active, self.reserve = self.reserve, None
        self.remaining_s = spec.duration_s
        self.uses.append(PowerUpUse(spec.kind, t, spec.duration_s))
        return True

    def step(self, dt: float) -> None:
        if self.active is None:
            return
        self.remaining_s -= dt
        if self.remaining_s <= 1e-9:
            self.active, self.remaining_s = None, 0.0

    def set_erg(self, on: bool) -> None:
        """ERG : bonus actif arrêté, obtention et activation refusées ; la réserve est gardée."""
        self.erg = bool(on)
        if self.erg and self.active is not None:
            self.active, self.remaining_s = None, 0.0

    # --- effets --------------------------------------------------------------------------

    def params(self, base: PhysicsParams) -> PhysicsParams:
        """Paramètres de la physique pendant le bonus (masse ou CdA) ; `base` sinon."""
        if self.active == "lightweight":
            return replace(base, mass_kg=base.mass_kg * self.table.specs["lightweight"].factor)
        if self.active == "aero":
            return replace(base, cda_m2=base.cda_m2 * self.table.specs["aero"].factor)
        return base

    def power(self, measured_w: float) -> float:
        """Puissance prise en compte par la physique (jamais écrite au journal ni au FIT)."""
        if self.active == "power":
            return measured_w * self.table.specs["power"].factor
        return measured_w

    def state_dict(self) -> dict:
        """Forme proposée pour le champ `powerup` de la trame `state` (contrat T1)."""
        return {"reserve": self.reserve, "active": self.active,
                "remaining_s": round(self.remaining_s, 1) if self.active else 0.0}
