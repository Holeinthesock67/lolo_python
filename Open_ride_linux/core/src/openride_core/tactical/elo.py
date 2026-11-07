"""Classement Elo des coureurs de la Course tactique (lot CT0, base de l'équilibrage adaptatif de CT13).

Elo multijoueur par paires : une course à n coureurs compte comme n(n − 1)/2 duels, gagnés par celui qui
arrive devant. Chaque coureur gagne `k / (n − 1) × Σ (S − E)` points, `E` étant la chance de battre
l'autre d'après l'écart de points (`expected`). La somme des points ne change pas d'une course à l'autre.
Module pur.
"""

from __future__ import annotations

from collections.abc import Iterable

ELO_START = 1500.0
ELO_K = 24.0


def expected(r_a: float, r_b: float) -> float:
    """Chance que A batte B (formule d'Elo, 400 points = 10 contre 1)."""
    return 1.0 / (1.0 + 10.0 ** ((r_b - r_a) / 400.0))


def update(ratings: dict[str, float], order: Iterable[str], k: float = ELO_K) -> dict[str, float]:
    """Nouveaux points après une course (`order` : coureurs du premier au dernier ; les nouveaux partent
    à `ELO_START`)."""
    order = list(order)
    out = dict(ratings)
    for r in order:
        out.setdefault(r, ELO_START)
    n = len(order)
    if n < 2:
        return out
    before = {r: out[r] for r in order}
    for i, a in enumerate(order):
        delta = 0.0
        for j, b in enumerate(order):
            if a != b:
                delta += (1.0 if i < j else 0.0) - expected(before[a], before[b])
        out[a] = before[a] + k / (n - 1) * delta
    return out
