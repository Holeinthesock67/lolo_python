"""Boîtes de ravitaillement du Grand Prix (lot GP1, plan `docs/4.0/PLAN_SERIE_GP.md` §4.1).

Une rangée de trois boîtes (une par voie) tous les `box_every_km`, la première à 500 m du départ,
jamais à moins de 200 m de l'arrivée ; sur un circuit, les rangées restent aux mêmes endroits d'un
tour à l'autre (et jamais à moins de 200 m de la ligne). Une boîte prise se reforme 2 s plus tard.
"""

from __future__ import annotations

from dataclasses import dataclass

LANES = 3
BOX_EVERY_KM = (1.0, 1.5, 2.0, 3.0)
FIRST_ROW_M = 500.0
FINISH_CLEAR_M = 200.0
REFORM_S = 2.0
ROULETTE_S = 2.0


def row_positions(length_m: float, every_m: float, lap_m: float | None = None) -> list[float]:
    """Abscisses des rangées sur toute la course (cumulées sur un circuit)."""
    if every_m <= 0.0:
        return []
    span = lap_m if lap_m else length_m
    one = []
    x = FIRST_ROW_M
    while x <= span - FINISH_CLEAR_M + 1e-6:
        one.append(x)
        x += every_m
    if not lap_m:
        return one
    out, lap = [], 0
    while lap * lap_m < length_m:
        out.extend(lap * lap_m + p for p in one if lap * lap_m + p <= length_m - FINISH_CLEAR_M + 1e-6)
        lap += 1
    return out


@dataclass
class BoxRows:
    rows: list[float]

    def __post_init__(self) -> None:
        self.taken: dict[tuple[int, int], float] = {}     # (rangée, voie) -> reformée à t

    def present(self, row: int, lane: int, t: float) -> bool:
        return t >= self.taken.get((row, lane), -1.0)

    def crossed(self, s0: float, s1: float) -> list[int]:
        """Rangées franchies entre s0 (exclu) et s1 (inclus)."""
        return [i for i, x in enumerate(self.rows) if s0 < x <= s1]

    def take(self, row: int, lane: int, t: float) -> bool:
        if not self.present(row, lane, t):
            return False
        self.taken[(row, lane)] = t + REFORM_S
        return True

    def ahead(self, s: float, ahead_m: float) -> list[float]:
        return [x for x in self.rows if s < x <= s + ahead_m]
