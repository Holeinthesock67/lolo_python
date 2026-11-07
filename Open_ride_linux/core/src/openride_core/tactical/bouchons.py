"""Bouchons des règles de la Course tactique, pour le simulateur d'équilibrage (lot CT0).

Chaque fonction est pure et suit la règle décidée le 29 octobre (`docs/5.0/PLAN_SERIE_CT.md`). Elle sera
remplacée par le module du lot qui la livre, avec la même signature autant que possible :

- `burnout_step` : CT2 (`tactical/surchauffe.py`) ;
- `sling_charge`, `sling_power` : CT4 (catapulte) ;
- `relay_credit_j`, `credits_pct`, `ability_for` : CT6 (crédits et capacités du catalogue 4.0) ;
- les virages (CT7) ne sont pas simulés : les circuits générés de CT8 n'ont pas encore de courbure.

La réserve W′ reste celle de `rogue/wbal.py` (Skiba), sans copie.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..draft import ALPHA_MAX
from .balance import TacticalBalance

ABILITIES = ("breakaway", "shield", "aero")   # 25 %, 50 % et 100 % de la jauge (§3 règle 3 du plan)


@dataclass(frozen=True)
class Burnout:
    """État du Burnout : temps passé à réserve vide (`empty_s`) et Burnout restant (`left_s`)."""

    empty_s: float = 0.0
    left_s: float = 0.0

    @property
    def active(self) -> bool:
        return self.left_s > 0.0


def burnout_step(state: Burnout, w_bal_j: float, dt: float, bal: TacticalBalance,
                 shielded: bool = False) -> tuple[Burnout, bool]:
    """Avance le Burnout de `dt` ; rend le nouvel état et vrai si un Burnout vient de commencer.

    Réserve à 0 pendant `burnout_tolerance_s` : Burnout de `burnout_s`. Repasser sous la CP avant (la réserve
    remonte au-dessus de 0) remet le compte à zéro : « couper à 1 % » évite la pénalité. Le bouclier d'inertie
    empêche le Burnout de commencer."""
    if state.left_s > 0.0:
        return Burnout(0.0, max(state.left_s - dt, 0.0)), False
    if w_bal_j > 0.0:
        return Burnout(), False
    empty = state.empty_s + dt
    if shielded or empty < bal.burnout_tolerance_s - 1e-9:
        return Burnout(empty, 0.0), False
    return Burnout(0.0, bal.burnout_s), True


def burnout_cap_w(cp_w: float, bal: TacticalBalance) -> float:
    """Puissance prise en compte au plus pendant un Burnout (jamais la résistance du trainer)."""
    return cp_w * bal.burnout_cap_pct / 100.0


def sling_charge(charge_pct: float, alpha: float, dt: float, bal: TacticalBalance) -> float:
    """Charge de la catapulte : proportionnelle à l'abri reçu (pleine en `sling_full_s` roue dans la roue,
    environ deux fois plus lente à 3 m) ; elle se vide sans abri."""
    if alpha > 0.0:
        charge_pct += 100.0 * (alpha / ALPHA_MAX) / bal.sling_full_s * dt
    else:
        charge_pct -= bal.sling_decay_pct_s * dt
    return min(max(charge_pct, 0.0), 100.0)


def sling_power(power_w: float, charge_pct: float, bal: TacticalBalance) -> float:
    """Puissance prise en compte pendant l'impulsion d'une catapulte lancée à `charge_pct`."""
    return power_w * (1.0 + bal.sling_gain_pct / 100.0 * charge_pct / 100.0)


def relay_credit_j(saved_w: float, dt: float) -> float:
    """Travail aérodynamique donné aux suiveurs pendant `dt` (somme des watts qu'ils économisent)."""
    return max(saved_w, 0.0) * dt


def credits_pct(work_j: float, bal: TacticalBalance) -> float:
    """Jauge de capacités (0 à 100 %) pour un travail donné aux autres."""
    return min(100.0 * work_j / (bal.credits_full_kj * 1000.0), 100.0)


def ability_cost(name: str, bal: TacticalBalance) -> float:
    return {"breakaway": bal.breakaway_cost_pct, "shield": bal.shield_cost_pct, "aero": bal.aero_cost_pct}[name]


def ability_duration(name: str, bal: TacticalBalance) -> float:
    return {"breakaway": bal.breakaway_s, "shield": bal.shield_s, "aero": bal.aero_s}[name]


def ability_for(gauge_pct: float, long_press: bool, bal: TacticalBalance) -> str | None:
    """Capacité déclenchée (§3 règle 3) : Z long l'Overdrive aéro à jauge pleine ; Z court la plus haute que la
    jauge peut payer sous 100 %."""
    if long_press:
        return "aero" if gauge_pct >= bal.aero_cost_pct - 1e-9 else None
    for name in ("shield", "breakaway"):
        if gauge_pct >= ability_cost(name, bal) - 1e-9:
            return name
    return None
