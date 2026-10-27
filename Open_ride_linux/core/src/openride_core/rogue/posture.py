"""Posture de combat déduite de la cadence, avec hystérésis (lot R2).

ROC (< 70 rpm), FLUIDE (70 à 100), VELOCE (> 100), ARRET (< 20 rpm ou < 10 W). Un changement n'est
adopté qu'après `posture_hold_s` continues dans la nouvelle plage ; ARRET est immédiat. Module pur.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .balance import DEFAULT_BALANCE, RogueBalance

ROC, FLUIDE, VELOCE, ARRET = "ROC", "FLUIDE", "VELOCE", "ARRET"


@dataclass(frozen=True)
class PostureState:
    posture: str = ARRET
    cadence_smooth_rpm: float = 0.0
    candidate: str | None = None
    candidate_s: float = 0.0


def _classify(c: float, b: RogueBalance) -> str:
    if c < b.roc_enter_rpm:
        return ROC
    if c > b.veloce_enter_rpm:
        return VELOCE
    return FLUIDE


def posture_step(state: PostureState, cadence_rpm: float, power_w: float, dt: float,
                 balance: RogueBalance = DEFAULT_BALANCE) -> PostureState:
    b = balance
    if not (dt > 0 and math.isfinite(dt)):
        return state
    cad = cadence_rpm if math.isfinite(cadence_rpm) else 0.0
    pwr = power_w if math.isfinite(power_w) else 0.0

    # Arrêt : immédiat ; la cadence lissée suit la cadence brute tant qu'on est à l'arrêt.
    if state.posture == ARRET:
        if cad >= b.stop_exit_rpm and pwr >= b.stop_power_w:
            if state.candidate is None:           # reprise : on repart de la cadence mesurée
                state = PostureState(ARRET, cad)
        else:
            return PostureState(ARRET, cad)
    elif cad < b.stop_enter_rpm or pwr < b.stop_power_w:
        return PostureState(ARRET, cad)

    alpha = 1.0 - math.exp(-dt / b.cadence_smooth_s) if b.cadence_smooth_s > 0 else 1.0
    smooth = state.cadence_smooth_rpm + alpha * (cad - state.cadence_smooth_rpm)

    cur = state.posture
    if cur == ROC:
        target = ROC if smooth < b.roc_exit_rpm else _classify(smooth, b)
    elif cur == VELOCE:
        target = VELOCE if smooth > b.veloce_exit_rpm else _classify(smooth, b)
    else:   # FLUIDE ou ARRET (reprise)
        target = _classify(smooth, b)
    if target == cur:
        return PostureState(cur, smooth)
    held = state.candidate_s + dt if state.candidate == target else dt
    if held >= b.posture_hold_s:
        return PostureState(target, smooth)
    return PostureState(cur, smooth, target, held)
