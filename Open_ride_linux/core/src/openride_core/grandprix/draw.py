"""Tirage des objets selon le retard sur le premier (lot GP1, plan `docs/4.0/PLAN_SERIE_GP.md` §4.2).

Le tirage dépend du retard en secondes sur le premier, pas de la place seule. Un objet désactivé au
menu sort du tirage ; un objet inutile n'est jamais tiré ; les poids restants sont remis à 100 %.
"""

from __future__ import annotations

import random
from typing import Iterable, Mapping, NamedTuple

from .items import BRACKET_LIMITS_S, BRACKETS


class DrawContext(NamedTuple):
    """Ce que voit le coureur au moment de la boîte."""

    place: int               # 1 : en tête
    gap_s: float             # retard sur le premier
    ahead: int               # coureurs devant
    storm_flying: bool       # un nuage d'orage est déjà en vol


def bracket(ctx: DrawContext) -> str:
    if ctx.place <= 1:
        return BRACKETS[0]
    lo, hi = BRACKET_LIMITS_S
    if ctx.gap_s < lo:
        return BRACKETS[1]
    if ctx.gap_s <= hi:
        return BRACKETS[2]
    return BRACKETS[3]


def useless(item: str, ctx: DrawContext) -> bool:
    """Objets qui ne serviraient à rien maintenant (tirage contextuel, comme TT2)."""
    if item in ("homing", "headwind", "stealth") and ctx.ahead == 0:
        return True
    if item == "storm" and (ctx.place <= 2 or ctx.storm_flying):
        return True
    return False


def weights_for(ctx: DrawContext, weights: Mapping[str, Mapping[str, float]],
                enabled: Iterable[str]) -> dict[str, float]:
    """Poids remis à 100 % des objets tirables dans ce contexte (vide : rien à tirer)."""
    on = set(enabled)
    row = {k: w for k, w in weights[bracket(ctx)].items() if k in on and w > 0.0 and not useless(k, ctx)}
    total = sum(row.values())
    return {k: 100.0 * w / total for k, w in sorted(row.items())} if total > 0.0 else {}


def draw(ctx: DrawContext, weights: Mapping[str, Mapping[str, float]], enabled: Iterable[str],
         rng: random.Random) -> str | None:
    row = weights_for(ctx, weights, enabled)
    if not row:
        return None
    return rng.choices(list(row), weights=list(row.values()))[0]
