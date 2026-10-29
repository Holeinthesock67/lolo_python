"""Cycliste virtuel du Bluetooth simulé (lot X27).

Le trainer simulé (`ble_sim.SimTrainer`) demande à chaque trame au cycliste sa puissance, sa cadence et un
éventuel appui du Click (changement de braquet). Section `rider` d'un scénario (`docs/SIMULATION_BLE.md`) :

    "rider": {"strategy": "pente", "ftp_w": 250, "pct_ftp": 75, "seed": 3}

Stratégies :
- `constante` (défaut) : `watts`, un peu plus en montée (+4 % par point de pente) ;
- `pente` : `pct_ftp` % de `ftp_w` sur le plat, qui suit la pente (+6 % par point, de 40 à 150 %) ;
- `cadence` : comme `pente`, et cadence tenue entre `cadence_low` et `cadence_high` par des appuis du Click
  (la cadence baisse quand la pente reçue monte : braquet plus dur ou montée) ;
- `rampe` : `ramp_start_w` puis +`ramp_w_per_min` par minute ; en ERG, la cible du trainer ; le cycliste
  lâche (cadence 0) quand la puissance dépasse `ramp_fail_pct_ftp` % de la FTP (test de FTP, lot O10) ;
- `sprint` : comme `pente`, avec des sprints de `sprint_s` s à `sprint_w` (2,5 × FTP par défaut) aux temps
  `sprint_at_s` ;
- `fatigue` : `fatigue_pct_ftp` % de la FTP tant que la réserve W′bal (`w_prime_j`, CP = FTP) le permet,
  puis la CP × `recover_frac` jusqu'à ce que la réserve remonte au-dessus de `resume_pct` % ;
- `vitesse` : la puissance qui tient `speed_kmh` sur la pente reçue, avec la physique du core (lot X35).

Le bruit des stratégies (hors `constante`, qui garde la sinusoïde d'avant ce lot) vient d'un générateur à
graine (`seed`) : un même scénario donne la même séance.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from .physics import PhysicsParams, resistive_force
from .rogue.wbal import wbal_initial, wbal_step

STRATEGIES = ("constante", "pente", "cadence", "rampe", "sprint", "fatigue", "vitesse")
# Clés de la section `rider` d'un scénario (et de l'action `rider` pour celles qui changent en cours).
RIDER_KEYS = {"strategy", "watts", "cadence_rpm", "ftp_w", "pct_ftp", "cadence_low", "cadence_high",
              "ramp_start_w", "ramp_w_per_min", "ramp_fail_pct_ftp", "sprint_at_s", "sprint_w", "sprint_s",
              "fatigue_pct_ftp", "w_prime_j", "recover_frac", "resume_pct", "speed_kmh", "seed"}
SPEED_PHYSICS = PhysicsParams()   # vitesse imposée : mêmes réglages que la configuration par défaut du core
CADENCE_PER_GRADE = 2.5           # rpm perdus par point de pente reçue (stratégie `cadence`)
PRESS_GAP_S = 2.0                 # attente entre deux appuis du Click (le braquet agit sur la pente reçue)
NOISE_FRAC = 0.02                 # bruit des stratégies : ± 2 % de la puissance


@dataclass(frozen=True)
class RiderOutput:
    power_w: float
    cadence_rpm: float
    press: str | None = None      # « + » ou « - » : appui du Click demandé


class SimRider:
    def __init__(self, strategy: str = "constante", *, watts: float = 180.0, cadence_rpm: float = 88.0,
                 ftp_w: float = 250.0, pct_ftp: float = 75.0, cadence_low: float = 80.0, cadence_high: float = 95.0,
                 ramp_start_w: float = 100.0, ramp_w_per_min: float = 20.0, ramp_fail_pct_ftp: float = 133.0,
                 sprint_at_s: list[float] | tuple[float, ...] = (), sprint_w: float | None = None,
                 sprint_s: float = 10.0, fatigue_pct_ftp: float = 110.0, w_prime_j: float = 20000.0,
                 recover_frac: float = 0.85, resume_pct: float = 30.0, speed_kmh: float | None = None,
                 seed: int = 0) -> None:
        if strategy not in STRATEGIES:
            raise ValueError(f"stratégie de cycliste inconnue : {strategy!r} ({', '.join(STRATEGIES)})")
        if strategy == "vitesse" and not speed_kmh:
            raise ValueError("stratégie vitesse : speed_kmh manquant")
        self.strategy = strategy
        self.watts, self.cadence_rpm = float(watts), float(cadence_rpm)
        self.ftp_w, self.pct_ftp = float(ftp_w), float(pct_ftp)
        self.cadence_low, self.cadence_high = float(cadence_low), float(cadence_high)
        self.ramp_start_w, self.ramp_w_per_min = float(ramp_start_w), float(ramp_w_per_min)
        self.ramp_fail_pct_ftp = float(ramp_fail_pct_ftp)
        self.sprint_at_s = tuple(float(x) for x in sprint_at_s)
        self.sprint_w = float(sprint_w) if sprint_w is not None else 2.5 * self.ftp_w
        self.sprint_s = float(sprint_s)
        self.fatigue_pct_ftp, self.w_prime_j = float(fatigue_pct_ftp), float(w_prime_j)
        self.recover_frac, self.resume_pct = float(recover_frac), float(resume_pct)
        self.speed_kmh = float(speed_kmh) if speed_kmh else None
        self.rng = random.Random(seed)
        self.failed = False            # rampe : le cycliste a lâché
        self.wbal = wbal_initial(self.w_prime_j)
        self.recovering = False        # fatigue : réserve vidée, en récupération
        self._last_press = -math.inf

    @classmethod
    def from_spec(cls, spec: dict[str, Any] | None) -> "SimRider":
        return cls(**(spec or {}))

    def update(self, **values: Any) -> None:
        """Action `rider` d'un scénario : change `watts` et `cadence_rpm` en cours de séance."""
        if "watts" in values:
            self.watts = float(values["watts"])
        if "cadence_rpm" in values:
            self.cadence_rpm = float(values["cadence_rpm"])

    @property
    def wbal_pct(self) -> float:
        return 100.0 * self.wbal.w_bal_j / self.w_prime_j

    def _noise(self, p: float) -> float:
        return p * (1.0 + self.rng.uniform(-NOISE_FRAC, NOISE_FRAC))

    def _grade_power(self, grade_pct: float) -> float:
        return self.ftp_w * self.pct_ftp / 100.0 * min(max(1.0 + 0.06 * grade_pct, 0.4), 1.5)

    def step(self, t: float, dt: float, grade_pct: float, erg_target_w: float | None = None) -> RiderOutput:
        """Puissance, cadence et appui du Click à l'instant `t` (s), pente reçue par le trainer `grade_pct`,
        cible ERG du trainer s'il en a une (le trainer la tient tant que le cycliste pédale)."""
        s = self.strategy
        cadence = self.cadence_rpm
        if self.cadence_rpm <= 0 or self.failed:
            return RiderOutput(0.0, 0.0)
        press = None
        if s == "constante":
            if self.watts <= 0:   # roue libre en pédalant : cadence gardée (en ERG, le trainer tient sa cible)
                return RiderOutput(0.0, cadence)
            p = self.watts * (1.0 + 0.04 * grade_pct) + 4.0 * math.sin(t * 0.9)
        elif s == "pente":
            p = self._noise(self._grade_power(grade_pct))
        elif s == "cadence":
            p = self._noise(self._grade_power(grade_pct))
            cadence = self.cadence_rpm - CADENCE_PER_GRADE * grade_pct
            if t - self._last_press >= PRESS_GAP_S:
                if cadence < self.cadence_low:
                    press = "-"
                elif cadence > self.cadence_high:
                    press = "+"
                if press:
                    self._last_press = t
        elif s == "rampe":
            p = self.ramp_start_w + self.ramp_w_per_min * t / 60.0
            demanded = erg_target_w if erg_target_w is not None else p
            if demanded > self.ftp_w * self.ramp_fail_pct_ftp / 100.0:
                self.failed = True
                return RiderOutput(0.0, 0.0)
        elif s == "sprint":
            in_sprint = any(a <= t < a + self.sprint_s for a in self.sprint_at_s)
            p = self._noise(self.sprint_w if in_sprint else self._grade_power(grade_pct))
        elif s == "fatigue":
            if self.recovering and self.wbal_pct >= self.resume_pct:
                self.recovering = False
            if not self.recovering and self.wbal.w_bal_j <= 0.0:
                self.recovering = True
            p = self.ftp_w * (self.recover_frac if self.recovering else self.fatigue_pct_ftp / 100.0)
            self.wbal = wbal_step(self.wbal, p, 0.0, dt, cp_w=self.ftp_w, w_prime_j=self.w_prime_j)
            p = self._noise(p)
        else:   # vitesse
            v = self.speed_kmh / 3.6
            p = resistive_force(v, grade_pct, 0.0, SPEED_PHYSICS) * v / SPEED_PHYSICS.efficiency
            p += 2.0 * math.sin(t * 0.9)
        return RiderOutput(max(p, 0.0), cadence, press)
