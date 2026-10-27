"""Vent réglable du core (lot P2, contrat IPC révision 1.3, SRS §5 et §11).

Module pur (aucune E/S) : `WindModel` donne le vent au temps de séance `t_s`, `head_component`
le projette sur le cap de la route et `grade_offset_pct` traduit l'écart de force aérodynamique
en supplément de pente pour le trainer (`[wind] feel = "grade"`).

Modes (`[wind] mode`) :
- `off` : aucun vent (défaut des versions 1.x) ;
- `fixed` : vent constant `speed_kmh` venant de `from_deg` ;
- `gusty` : même vent de base, avec des rafales d'amplitude `gust_pct` et une direction qui
  oscille de ± 15° au plus ;
- `theme` : vent `wind` du thème (`speed_kmh`, `from_deg`, `gust_pct`), en rafales.

Les rafales sont une somme de trois sinusoïdes de périodes 20 à 90 s, dont les phases viennent
de `seed` : même graine, même suite de vents (rejeu d'une séance).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .physics import G, PhysicsParams, air_density

KMH = 1.0 / 3.6
GUST_PERIODS_S = (23.0, 47.0, 89.0)     # périodes des rafales, entre 20 et 90 s
GUST_WEIGHTS = (0.5, 0.3, 0.2)          # somme 1 : la rafale ne dépasse pas gust_pct
DIR_SWING_DEG = 15.0                    # oscillation maximale de la direction en rafales
DIR_PERIODS_S = (61.0, 37.0)


@dataclass(frozen=True)
class WindSample:
    speed_mps: float    # vitesse au sol, rafale comprise (≥ 0)
    from_deg: float     # direction d'où vient le vent, degrés depuis le nord, sens horaire
    gust: float         # force de la rafale en cours, de 0 à 1


CALM = WindSample(0.0, 0.0, 0.0)


class WindModel:
    """Vent au temps de séance `t_s` ; `active` est faux en mode `off` (aucun champ `wind`)."""

    def __init__(self, mode: str = "off", speed_kmh: float = 0.0, from_deg: float = 0.0,
                 gust_pct: float = 0.0, seed: int = 0) -> None:
        self.mode = mode
        self.base_mps = max(speed_kmh, 0.0) * KMH
        self.from_deg = from_deg % 360.0
        self.gusty = mode in ("gusty", "theme")
        self.gust_frac = max(min(gust_pct, 100.0), 0.0) / 100.0 if self.gusty else 0.0
        rng = random.Random(seed)
        self._phases = [rng.uniform(0.0, 2.0 * math.pi) for _ in GUST_PERIODS_S]
        self._dir_phases = [rng.uniform(0.0, 2.0 * math.pi) for _ in DIR_PERIODS_S]

    @classmethod
    def from_config(cls, wind_cfg, theme_wind: dict | None = None) -> WindModel:
        """`theme_wind` : objet `wind` du thème 1.2, lu seulement en mode `theme`."""
        if wind_cfg.mode == "theme":
            tw = theme_wind or {}
            return cls("theme", float(tw.get("speed_kmh", 0.0)), float(tw.get("from_deg", 0.0)),
                       float(tw.get("gust_pct", 0.0)), wind_cfg.seed)
        return cls(wind_cfg.mode, wind_cfg.speed_kmh, wind_cfg.from_deg, wind_cfg.gust_pct,
                   wind_cfg.seed)

    @property
    def active(self) -> bool:
        return self.mode != "off"

    def sample(self, t_s: float) -> WindSample:
        if not self.active or self.base_mps <= 0.0:
            return CALM if not self.active else WindSample(0.0, self.from_deg, 0.0)
        if not self.gust_frac:
            return WindSample(self.base_mps, self.from_deg, 0.0)
        # Rafale : somme pondérée de sinusoïdes ramenée de [−1, 1] à [0, 1].
        wave = sum(w * math.sin(2.0 * math.pi * t_s / p + ph)
                   for w, p, ph in zip(GUST_WEIGHTS, GUST_PERIODS_S, self._phases))
        gust = 0.5 * (wave + 1.0)
        speed = self.base_mps * (1.0 + self.gust_frac * (2.0 * gust - 1.0))
        swing = DIR_SWING_DEG * self.gust_frac * 0.5 * sum(
            math.sin(2.0 * math.pi * t_s / p + ph) for p, ph in zip(DIR_PERIODS_S, self._dir_phases))
        return WindSample(max(speed, 0.0), (self.from_deg + swing) % 360.0, gust)


def head_component(sample: WindSample, heading_deg: float) -> float:
    """Composante de face le long du cap `heading_deg` : positive de face, négative de dos."""
    return sample.speed_mps * math.cos(math.radians(sample.from_deg - heading_deg))


def aero_force_delta(v: float, head_mps: float, alpha_draft: float, alt_m: float,
                     p: PhysicsParams) -> float:
    """Écart de force aérodynamique (N) dû au vent et à l'aspiration, à vitesse `v` donnée.

    Calculé avec les `PhysicsParams` courants (CdA, masse) : un bonus qui change le CdA change
    aussi le supplément de pente, sans deuxième voie.
    """
    k = 0.5 * air_density(alt_m) * p.cda_m2
    va = v + head_mps
    return k * ((1.0 - alpha_draft) * va * abs(va) - v * abs(v))


def grade_offset_pct(v: float, head_mps: float, alpha_draft: float, alt_m: float,
                     p: PhysicsParams, max_offset_pct: float) -> float:
    """Supplément de pente 100 · ΔF / (m g), borné à ± `max_offset_pct` (`feel = "grade"`)."""
    offset = 100.0 * aero_force_delta(v, head_mps, alpha_draft, alt_m, p) / (p.mass_kg * G)
    return max(-max_offset_pct, min(max_offset_pct, offset))


def wind_frame(sample: WindSample, head_mps: float) -> dict[str, float]:
    """Objet `wind` de la trame `state`, aux arrondis du contrat (révision 1.3)."""
    return {"speed_mps": round(sample.speed_mps, 2), "from_deg": round(sample.from_deg % 360.0, 1),
            "head_mps": round(head_mps, 2), "gust": round(sample.gust, 2)}
