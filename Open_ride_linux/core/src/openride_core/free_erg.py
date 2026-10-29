"""ERG d'une session libre (lot O18) : cible constante, ou cadence verrouillée dans une plage.

Deux contrôleurs, choisis en séance depuis l'écran de pause (commande `set_ride_mode`, contrat IPC
révision 1.5) et pilotés par la session comme l'`ErgController` d'un entraînement (mêmes attributs
`paused`, `finished`, `target_active`, `target_w`, `bias_pct`, mêmes méthodes `step`,
`change_bias` et `to_dict`), sans blocs : Z garde son rôle de la séance libre.

- `FreeErg` : cible fixe en watts × biais du Click (± 2 %, long ± 10 %, borné à 80–120 %, comme un
  entraînement).
- `CadenceLock` : cadence cible et plage ± `CADENCE_BAND_PCT` %. Cadence lissée (`CADENCE_TAU_S`) ;
  au-dessus de la plage, la puissance monte, au-dessous elle baisse, d'autant plus vite que l'écart
  est grand (`GAIN_W_PER_S_PER_RPM`, au plus `RATE_MAX_W_PER_S`), entre `POWER_MIN_W` et
  `POWER_MAX_FTP` × FTP ; dans la plage, elle ne bouge pas (pas d'oscillation autour de la cible).
  Les appuis ± changent la cadence cible de 2 % par pas (long : 10 %), par le même biais borné à
  80–120 % qu'une cible de puissance (demande du propriétaire du 28 octobre).

Module pur, sans entrées-sorties.
"""

from __future__ import annotations

import math
from typing import Any

from .workout import BIAS_DEFAULT_PCT, BIAS_MAX_PCT, BIAS_MIN_PCT, BIAS_STEP_PCT, ERG_MIN_W

POWER_MIN_W = ERG_MIN_W          # consigne ERG minimale commune (lot O19)
POWER_MAX_W = 1000
POWER_MAX_FTP = 1.5               # plafond de la cadence verrouillée : 150 % de la FTP
POWER_STEP_W = 5                  # pas de la puissance cible dans le menu, arrondi de la cible de départ
DEFAULT_FTP_FRAC = 0.6            # cible de départ sans puissance mesurée : 60 % de la FTP
CADENCE_MIN_RPM, CADENCE_MAX_RPM = 50, 120
CADENCE_DEFAULT_RPM = 85          # cadence cible de départ sans cadence mesurée
CADENCE_ROUND_RPM = 5
CADENCE_BAND_PCT = 15             # plage de cadence : ± 15 % autour de la cible
CADENCE_TAU_S = 2.0               # lissage de la cadence mesurée
GAIN_W_PER_S_PER_RPM = 1.5        # vitesse de correction par tr/min hors plage
RATE_MAX_W_PER_S = 10.0

FREE_NAME = "ERG libre"
CADENCE_NAME = "ERG cadence"


def _finite(x: Any) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def start_power(power_3s: Any, ftp_w: float) -> int:
    """Cible de départ : puissance des 3 dernières secondes arrondie à 5 W, sinon 60 % de la FTP."""
    p = _finite(power_3s)
    if p is None or p < POWER_MIN_W:
        p = ftp_w * DEFAULT_FTP_FRAC
    return clamp_power(POWER_STEP_W * round(p / POWER_STEP_W))


def start_cadence(cadence_rpm: Any) -> int:
    """Cadence cible de départ : cadence mesurée arrondie à 5 tr/min, sinon 85 tr/min."""
    c = _finite(cadence_rpm)
    if c is None or c < CADENCE_MIN_RPM:
        return CADENCE_DEFAULT_RPM
    return clamp_cadence(CADENCE_ROUND_RPM * round(c / CADENCE_ROUND_RPM))


def clamp_power(w: float) -> int:
    return int(min(max(round(w), POWER_MIN_W), POWER_MAX_W))


def clamp_cadence(rpm: float) -> int:
    return int(min(max(round(rpm), CADENCE_MIN_RPM), CADENCE_MAX_RPM))


class FreeErg:
    """Cible de puissance constante d'une session libre, biais du Click compris."""

    kind = "free"
    name = FREE_NAME

    def __init__(self, target_w: float) -> None:
        if _finite(target_w) is None:
            raise ValueError(f"cible invalide : {target_w!r} W")
        self.base_w: float = float(clamp_power(target_w))
        self.bias_pct = BIAS_DEFAULT_PCT
        self.paused = False   # posé par la session, comme pour un entraînement
        self.finished = False

    @property
    def target_active(self) -> bool:
        return not self.paused

    @property
    def target_w(self) -> int:
        return max(round(self.base_w * self.bias_pct / 100.0), ERG_MIN_W)

    def step(self, dt: float, cadence_rpm: float | None = None) -> None:
        if not (math.isfinite(dt) and dt >= 0):
            raise ValueError(f"pas de temps invalide : {dt!r} s (attendu un nombre fini ≥ 0)")

    def change_bias(self, steps: int) -> None:
        self.bias_pct = min(max(self.bias_pct + steps * BIAS_STEP_PCT, BIAS_MIN_PCT), BIAS_MAX_PCT)

    def to_dict(self) -> dict[str, Any]:
        """Objet `erg` du contrat IPC §3 : un seul bloc `steady` sans durée, `kind` = `free`."""
        return {
            "kind": self.kind,
            "workout_name": self.name,
            "block_index": 1,
            "block_count": 1,
            "block_type": "steady",
            "block_remaining_s": 0.0,
            "block_total_s": 0.0,
            "target_w": self.target_w,
            "next_target_w": None,
            "bias_pct": self.bias_pct,
            "paused": self.paused,
        }


class CadenceLock(FreeErg):
    """Puissance adaptée pour garder la cadence dans la plage cible ± 15 %."""

    kind = "cadence"
    name = CADENCE_NAME

    def __init__(self, cadence_rpm: float, start_w: float, ftp_w: float) -> None:
        if not (math.isfinite(ftp_w) and ftp_w > 0):
            raise ValueError(f"FTP invalide : {ftp_w!r} W (attendu un nombre fini > 0)")
        self.max_w = float(min(max(round(ftp_w * POWER_MAX_FTP), POWER_MIN_W), POWER_MAX_W))
        super().__init__(start_w)
        self.base_w = min(self.base_w, self.max_w)
        self.base_cadence = clamp_cadence(cadence_rpm)
        self.cadence_f: float | None = None   # cadence lissée ; None avant la première mesure

    @property
    def cadence_target(self) -> int:
        """Cadence cible, biais du Click compris (± 2 % par appui court)."""
        return clamp_cadence(self.base_cadence * self.bias_pct / 100.0)

    @property
    def low_rpm(self) -> float:
        return self.cadence_target * (1.0 - CADENCE_BAND_PCT / 100.0)

    @property
    def high_rpm(self) -> float:
        return self.cadence_target * (1.0 + CADENCE_BAND_PCT / 100.0)

    @property
    def target_w(self) -> int:
        return round(self.base_w)   # le biais s'applique à la cadence cible, pas à la puissance

    @property
    def zone(self) -> str:
        """`low` (trop lent), `in` (dans la plage) ou `high` (trop vite)."""
        c = self.cadence_f
        if c is None or self.low_rpm <= c <= self.high_rpm:
            return "in"
        return "high" if c > self.high_rpm else "low"

    def step(self, dt: float, cadence_rpm: float | None = None) -> None:
        super().step(dt)
        if self.paused or dt == 0:
            return
        c = _finite(cadence_rpm)
        c = max(c, 0.0) if c is not None else 0.0
        if self.cadence_f is None:
            self.cadence_f = c
        else:
            self.cadence_f += (c - self.cadence_f) * (1.0 - math.exp(-dt / CADENCE_TAU_S))
        f = self.cadence_f
        if f > self.high_rpm:
            excess = f - self.high_rpm
        elif f < self.low_rpm:
            excess = f - self.low_rpm
        else:
            return
        rate = min(max(GAIN_W_PER_S_PER_RPM * excess, -RATE_MAX_W_PER_S), RATE_MAX_W_PER_S)
        self.base_w = min(max(self.base_w + rate * dt, float(POWER_MIN_W)), self.max_w)

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        out.update({
            "cadence_target_rpm": self.cadence_target,
            "cadence_low_rpm": round(self.low_rpm, 1),
            "cadence_high_rpm": round(self.high_rpm, 1),
            "cadence_zone": self.zone,
        })
        return out
