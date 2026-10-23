"""Pilote de home trainer simulé (SRS §10 & §12).

Permet de développer et tester tout le système sans matériel ni connexion Bluetooth :
- puissance constante, profil en rampe, ou pilotage au clavier/commandes ;
- simulation de pertes/déconnexions et retours ;
- cadence et fréquence cardiaque synthétisées de façon cohérente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable


@dataclass
class TrainerMetrics:
    power_w: float = 0.0
    cadence_rpm: float = 0.0
    speed_kmh: float = 0.0
    hr_bpm: int | None = None
    connected: bool = True


class MockDriver:
    """Simulateur de Home Trainer pour tests et développement sans vélo."""

    def __init__(
        self,
        base_power_w: float = 200.0,
        base_cadence_rpm: float = 85.0,
        base_hr_bpm: int = 140,
        ramp_amplitude_w: float = 50.0,
        ramp_period_s: float = 60.0,
    ) -> None:
        self.base_power_w = base_power_w
        self.base_cadence_rpm = base_cadence_rpm
        self.base_hr_bpm = base_hr_bpm
        self.ramp_amplitude_w = ramp_amplitude_w
        self.ramp_period_s = ramp_period_s

        self.target_power_w: float | None = None
        self.sim_grade_pct: float = 0.0
        self.connected: bool = True
        self.on_metrics_callback: Callable[[TrainerMetrics], None] | None = None

    def set_target_power(self, watts: float) -> bool:
        """Mode ERG."""
        self.target_power_w = max(0.0, watts)
        return True

    def set_sim_grade(self, grade_pct: float) -> bool:
        """Mode SIM (quitte le mode ERG, comme le trainer réel)."""
        self.target_power_w = None
        self.sim_grade_pct = grade_pct
        return True

    def simulate_disconnect(self) -> None:
        self.connected = False

    def simulate_reconnect(self) -> None:
        self.connected = True

    def poll(self, t_session: float) -> TrainerMetrics:
        """Génère un échantillon à l'instant `t_session`."""
        if not self.connected:
            metrics = TrainerMetrics(connected=False)
            if self.on_metrics_callback:
                self.on_metrics_callback(metrics)
            return metrics

        if self.target_power_w is not None:
            # En mode ERG, légère oscillation naturelle autour de la cible
            power = self.target_power_w + 3.0 * math.sin(t_session * 1.5)
        else:
            # En mode SIM libre / profil par défaut
            power = self.base_power_w + self.ramp_amplitude_w * math.sin(
                2 * math.pi * t_session / self.ramp_period_s
            )

        power = max(0.0, power)
        cadence = self.base_cadence_rpm + 3.0 * math.sin(t_session * 0.8)
        hr = int(self.base_hr_bpm + 0.15 * (power - self.base_power_w))

        metrics = TrainerMetrics(
            power_w=round(power, 1),
            cadence_rpm=round(cadence, 1),
            speed_kmh=0.0,  # La vitesse virtuelle est calculée par le physics engine du core
            hr_bpm=max(40, min(220, hr)),
            connected=True,
        )
        if self.on_metrics_callback:
            self.on_metrics_callback(metrics)
        return metrics
