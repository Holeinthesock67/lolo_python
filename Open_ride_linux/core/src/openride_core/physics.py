"""Physique 1D sur rail (SRS §5).

La vitesse est déduite de l'énergie cinétique :
    d/dt (1/2 m v²) = η P − F_res(v) · v
    F_res(v) = 1/2 ρ CdA (1 − α) (v + v_w)|v + v_w| + m g (sin θ + Crr cos θ)

Ce module est pur (aucune E/S) : il est piloté à 50 Hz par la boucle du core.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

G = 9.80665
RHO0 = 1.225          # kg/m³ au niveau de la mer
H_SCALE_M = 8400.0    # hauteur d'échelle de l'atmosphère
V_FLOOR = 0.5         # m/s, vitesse plancher d'amorçage
V_MAX = 80.0          # m/s, plafond anti-aberration
DT_DEFAULT = 0.02     # 50 Hz


@dataclass
class PhysicsParams:
    mass_kg: float = 84.0
    cda_m2: float = 0.32
    crr: float = 0.004
    efficiency: float = 0.97
    wind_mps: float = 0.0   # vent de face positif

    @classmethod
    def from_config(cls, cfg) -> "PhysicsParams":
        return cls(
            mass_kg=cfg.total_mass_kg,
            cda_m2=cfg.bike.cda_m2,
            crr=cfg.bike.crr,
            efficiency=cfg.bike.drivetrain_efficiency,
        )


WHEEL_CIRCUMFERENCE_M = 2.105   # circonférence par défaut d'une roue de 700 × 28c


def gear_speed_mps(cadence_rpm: float, chainring: float, sprocket: float,
                   wheel_m: float = WHEEL_CIRCUMFERENCE_M) -> float:
    """Vitesse (m/s) au braquet réel plateau × pignon (dents) : celle du volant d'un trainer à
    entraînement direct, qui tourne avec les pédales."""
    return cadence_rpm / 60.0 * chainring / sprocket * wheel_m


def gear_cadence_rpm(speed_mps: float, chainring: float, sprocket: float,
                     wheel_m: float = WHEEL_CIRCUMFERENCE_M) -> float:
    """Cadence (rpm) qui donne `speed_mps` au braquet réel : réciproque de `gear_speed_mps`."""
    return speed_mps * 60.0 * sprocket / (chainring * wheel_m)


def air_density(alt_m: float) -> float:
    return RHO0 * math.exp(-alt_m / H_SCALE_M)


def resistive_force(v: float, grade_pct: float, alt_m: float, p: PhysicsParams,
                    alpha_draft: float = 0.0) -> float:
    """Somme des forces résistantes en newtons (négative si la gravité entraîne le vélo)."""
    theta = math.atan(grade_pct / 100.0)
    va = v + p.wind_mps
    aero = 0.5 * air_density(alt_m) * p.cda_m2 * (1.0 - alpha_draft) * va * abs(va)
    gravity_rolling = p.mass_kg * G * (math.sin(theta) + p.crr * math.cos(theta))
    return aero + gravity_rolling


def draft_saving_w(v: float, alt_m: float, p: PhysicsParams, alpha_draft: float) -> float:
    """Puissance aérodynamique économisée à l'abri (lot AS5) : sans abri moins avec abri, à la vitesse `v`
    et au vent de face `p.wind_mps` du moment ; 0 quand l'air pousse (vent de dos plus rapide que le vélo)."""
    va = v + p.wind_mps
    if va <= 0.0 or v <= 0.0 or alpha_draft <= 0.0:
        return 0.0
    return 0.5 * air_density(alt_m) * p.cda_m2 * alpha_draft * va * va * v


class RiderPhysics:
    """État du coureur sur la route : position `s` (m) et vitesse `v` (m/s)."""

    def __init__(self, params: PhysicsParams, s: float = 0.0, v: float = 0.0) -> None:
        self.p = params
        self.s = s
        self.v = v

    @property
    def kinetic_energy(self) -> float:
        return 0.5 * self.p.mass_kg * self.v * self.v

    def step(self, power_w: float, grade_pct: float, alt_m: float = 0.0,
             dt: float = DT_DEFAULT, alpha_draft: float = 0.0) -> float:
        """Avance d'un pas `dt` et renvoie la nouvelle vitesse."""
        m = self.p.mass_kg
        power_w = max(power_w, 0.0)

        # Amorçage : sans cela, à v = 0 le terme F·v est nul et le vélo ne repartirait jamais.
        if self.v < V_FLOOR:
            gravity_drives = resistive_force(0.0, grade_pct, alt_m, self.p, alpha_draft) < 0.0
            if power_w > 0.0 or gravity_drives:
                self.v = V_FLOOR

        energy = 0.5 * m * self.v * self.v
        f_res = resistive_force(self.v, grade_pct, alt_m, self.p, alpha_draft)
        energy += (self.p.efficiency * power_w - f_res * self.v) * dt
        # Jamais de recul : énergie bornée à 0 (montée à 0 W -> arrêt).
        self.v = min(math.sqrt(max(energy, 0.0) * 2.0 / m), V_MAX)
        self.s += self.v * dt
        return self.v


def steady_speed(power_w: float, grade_pct: float, params: PhysicsParams,
                 alt_m: float = 0.0) -> float:
    """Vitesse d'équilibre η P = F_res(v) v, par dichotomie (outil de test et de calibrage)."""
    lo, hi = 0.0, V_MAX
    target = params.efficiency * power_w
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if resistive_force(mid, grade_pct, alt_m, params) * mid < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)
