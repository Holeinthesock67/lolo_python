"""Réserve anaérobie W'bal (modèle différentiel de Skiba, 2015), lot R2.

    P > CP : dW'bal/dt = −(P − CP)
    sinon  : dW'bal/dt = (W' − W'bal) · (CP − P) / W'

Module pur. La recharge est intégrée de façon exacte sur le pas (exponentielle), donc le résultat
ne dépend pas du pas de calcul.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .balance import DEFAULT_BALANCE, RogueBalance


@dataclass(frozen=True)
class WbalState:
    w_bal_j: float
    depleted_s: float = 0.0     # temps passé à 0


def wbal_initial(w_prime_j: float) -> WbalState:
    return WbalState(w_bal_j=w_prime_j)


def wbal_step(state: WbalState, power_w: float, cadence_rpm: float, dt: float, *,
              cp_w: float, w_prime_j: float, posture: str | None = None,
              balance: RogueBalance = DEFAULT_BALANCE) -> WbalState:
    """Avance W'bal de `dt` secondes.

    `posture` : si donnée, le bonus de recharge exige la posture `FLUIDE` ; sinon seule la cadence compte.
    """
    if not (dt > 0 and math.isfinite(dt)) or cp_w <= 0 or w_prime_j <= 0:
        return state
    power_w = max(0.0, power_w) if math.isfinite(power_w) else 0.0
    w = min(max(state.w_bal_j, 0.0), w_prime_j)
    if power_w > cp_w:
        w -= (power_w - cp_w) * dt
    else:
        k = (cp_w - power_w) / w_prime_j
        if (posture in (None, "FLUIDE") and math.isfinite(cadence_rpm)
                and balance.fluid_regen_rpm_min <= cadence_rpm <= balance.fluid_regen_rpm_max):
            k *= balance.fluid_regen_mult
        w = w_prime_j - (w_prime_j - w) * math.exp(-k * dt)
    w = min(max(w, 0.0), w_prime_j)
    depleted = state.depleted_s + dt if w <= 0.0 else 0.0
    return WbalState(w_bal_j=w, depleted_s=depleted)
