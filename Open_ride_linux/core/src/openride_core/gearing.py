"""Braquets virtuels (SRS §4.3).

Le braquet n'agit que sur la pente envoyée au trainer, jamais sur la vitesse virtuelle :
    G_eff = (G_terrain + G_base) * R_k - G_base
avec R_k en progression géométrique entre R_min et R_max.
"""

from __future__ import annotations

from .config import GearingConfig, TrainerConfig


class Gearing:
    def __init__(self, cfg: GearingConfig, trainer: TrainerConfig | None = None) -> None:
        if cfg.n_gears < 2:
            raise ValueError("n_gears doit valoir au moins 2")
        if not 0 < cfg.ratio_min < cfg.ratio_max:
            raise ValueError("il faut 0 < ratio_min < ratio_max")
        self.cfg = cfg
        trainer = trainer or TrainerConfig()
        self.grade_min = trainer.grade_min_pct
        self.grade_max = trainer.grade_max_pct
        step = (cfg.ratio_max / cfg.ratio_min) ** (1.0 / (cfg.n_gears - 1))
        self.ratios = [cfg.ratio_min * step**i for i in range(cfg.n_gears)]
        self.k = min(max(cfg.start_gear, 1), cfg.n_gears)

    @property
    def n_gears(self) -> int:
        return self.cfg.n_gears

    @property
    def ratio(self) -> float:
        return self.ratios[self.k - 1]

    def shift_up(self) -> int:
        self.k = min(self.k + 1, self.cfg.n_gears)
        return self.k

    def shift_down(self) -> int:
        self.k = max(self.k - 1, 1)
        return self.k

    def effective_grade(self, terrain_grade_pct: float) -> float:
        """Pente à envoyer au trainer pour le braquet courant, bornée à la plage autorisée."""
        g_base = self.cfg.g_base_pct
        g = (terrain_grade_pct + g_base) * self.ratio - g_base
        return min(max(g, self.grade_min), self.grade_max)
