"""Braquets virtuels (SRS §4.3).

Le braquet n'agit que sur la pente envoyée au trainer, jamais sur la vitesse virtuelle. Depuis le 15 novembre,
chaque clic ajoute le même écart de pente, en montée, sur le plat comme en descente :
    G_eff = G_terrain × difficulté + (k − k_neutre) × pas + décalage du lieu
avec un pas de 0,5 point par clic (braquet 1 : −5,5 %, braquet 24 : +6 %), un braquet neutre 12 et le décalage
`[velodrome] gear_offset_pct` sur une piste (0 ailleurs) : donnée du lieu, pas une exception de la loi.
La difficulté ne touche que le terrain : un clic se sent toujours autant. G_eff ne change jamais de signe par
rapport au terrain du mauvais côté : un petit braquet adoucit une montée sans la transformer en descente, un
grand braquet peut durcir une descente (on appuie), comme sur un vrai vélo.

Jusqu'au 15 novembre, le braquet multipliait la pente (G_eff = (G + 2) × R_k − 2) : un clic ne valait que
0,16 point sur le plat, et en descente le grand braquet devenait le plus facile.
"""

from __future__ import annotations

import math

from .config import GearingConfig, TrainerConfig


class Gearing:
    def __init__(self, cfg: GearingConfig, trainer: TrainerConfig | None = None) -> None:
        if cfg.n_gears < 2:
            raise ValueError("n_gears doit valoir au moins 2")
        if cfg.step_pct <= 0:
            raise ValueError("step_pct doit être positif")
        self.cfg = cfg
        trainer = trainer or TrainerConfig()
        self.grade_min = trainer.grade_min_pct
        self.grade_max = trainer.grade_max_pct
        self.offsets = [(k - cfg.neutral_gear) * cfg.step_pct for k in range(1, cfg.n_gears + 1)]
        self.k = min(max(cfg.start_gear, 1), cfg.n_gears)

    @property
    def n_gears(self) -> int:
        return self.cfg.n_gears

    @property
    def offset_pct(self) -> float:
        """Écart de pente du braquet courant (points de pente)."""
        return self.offsets[self.k - 1]

    def shift_up(self, n: int = 1) -> int:
        self.k = min(self.k + n, self.cfg.n_gears)
        return self.k

    def shift_down(self, n: int = 1) -> int:
        self.k = max(self.k - n, 1)
        return self.k

    def effective_grade(self, terrain_grade_pct: float, difficulty: float = 1.0, place_offset_pct: float = 0.0) -> float:
        """Pente à envoyer au trainer pour le braquet courant, bornée à la plage autorisée.

        `difficulty` (coefficient de difficulté, SRS §5) multiplie la pente du terrain seule ; l'écart du braquet
        et `place_offset_pct` (`[velodrome] gear_offset_pct` sur une piste) s'ajoutent ensuite. La vitesse
        virtuelle, elle, utilise toujours la pente réelle. Un résultat NaN donne 0 % : le bornage `min`/`max`
        le laisserait passer jusqu'à l'encodage FTMS.
        """
        g = terrain_grade_pct * difficulty + self.offset_pct + place_offset_pct
        if math.isnan(g):
            return 0.0
        # Essai du 24 octobre : un petit braquet ne doit pas faire d'une montée une descente.
        if terrain_grade_pct > 0:
            g = max(g, 0.0)
        return min(max(g, self.grade_min), self.grade_max)
