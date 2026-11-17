"""Parcours vu à rebours (lot N23) : abscisse `u = L - s`, même tracé, cap retourné, pente opposée.

Après un demi-tour (lot N17), le cycliste roule vers les s décroissants. La circulation (`traffic.py`) et les
cyclistes du décor (`road_cyclists.py`) sont écrits pour un cycliste qui avance vers les s croissants : ils
roulent tels quels sur ce parcours retourné, où « devant » est encore « u croissant ». Les positions passent
d'un repère à l'autre par `flip_s` (`u = L - s`, sa propre réciproque) et les écarts à l'axe changent de signe
(la droite du sens de marche est la gauche du sens du parcours). Même calcul dans l'engine
(`engine/scripts/route_mirror.gd`), pour que les cases tirées restent les mêmes des deux côtés.
"""

from __future__ import annotations

import dataclasses
from typing import Any


def flip_s(length_m: float, s: float) -> float:
    """Abscisse dans l'autre repère (`L - s`) ; l'opération est sa propre réciproque."""
    return length_m - s


class MirroredRoute:
    """`Route` lue dans l'autre sens : `sample(u)` est `base.sample(L - u)`, cap + 180°, pente opposée."""

    def __init__(self, base: Any) -> None:
        self.base = base
        self.length_m = float(base.length_m)

    @property
    def is_loop(self) -> bool:
        return bool(getattr(self.base, "is_loop", False))

    def wrap(self, u: float) -> float:
        return flip_s(self.length_m, self.base.wrap(flip_s(self.length_m, u)))

    def grade_at(self, u: float) -> float:
        return -self.base.grade_at(flip_s(self.length_m, u))

    def surface_at(self, u: float) -> str:
        if not hasattr(self.base, "surface_at"):
            return "paved"
        return self.base.surface_at(flip_s(self.length_m, u))

    def bank_at(self, u: float) -> float:
        return -self.base.bank_at(flip_s(self.length_m, u)) if hasattr(self.base, "bank_at") else 0.0

    def sample(self, u: float) -> Any:
        smp = self.base.sample(flip_s(self.length_m, u))
        changes = {"grade_pct": -smp.grade_pct, "heading_deg": (smp.heading_deg + 180.0) % 360.0}
        if hasattr(smp, "bank_deg"):
            changes["bank_deg"] = -smp.bank_deg
        if dataclasses.is_dataclass(smp):
            return dataclasses.replace(smp, **changes)
        return smp._replace(**changes)   # échantillons simplifiés des tests (NamedTuple)
