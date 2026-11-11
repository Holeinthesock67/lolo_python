"""Effets des objets du Grand Prix sur la vitesse virtuelle (lot GP1, série GP).

Une ligne d'effet = (effet, facteur, durée). Les effets ne touchent que la vitesse virtuelle d'un
coureur, jamais la pente envoyée au trainer ni la puissance mesurée :

- `kick` : impulsion, v × facteur d'un coup (coup de fouet) ;
- `slip` : glissade, v × facteur d'un coup (bidon, musette) ;
- `speed_floor` : v ≥ facteur × v_éq pendant la durée (super-forme, voiture d'équipe) ;
- `cap` : v ≤ facteur × v_éq pendant la durée (averse du nuage d'orage) ;
- `immune` : aucun coup reçu pendant la durée ;
- `wind` : vent de face virtuel de `facteur` m/s pendant la durée, sans ressenti (vent contraire) ;
- `breakaway` : marque de l'Échappée de la série TT (lot TT4) ; son effet sur l'abri vient avec GP4.

Depuis le lot TT2, ces lignes sont celles de la table unique des bonus de la 4.0 : `EffectSpec` et les
listes d'effets sont dans `powerups.py` (un seul système, plan GP §5), ce module n'en garde que
l'application à la vitesse du Grand Prix. Aucun objet n'a de code à lui.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..physics import PhysicsParams, RiderPhysics, steady_speed
from ..powerups import DURATIONS, EFFECTS, HITS, IMPULSES, MULTIPLIERS, EffectSpec

__all__ = ["CHAOS", "DURATIONS", "EFFECTS", "GAIN_HORIZON_S", "HITS", "IMPULSES", "MULTIPLIERS", "Active",
           "EffectSpec", "apply_speed", "gain_s", "is_immune", "wind_of"]

CHAOS = {"soft": 0.7, "normal": 1.0, "wild": 1.3}      # doux, normal, fou (plan §4.4)
GAIN_HORIZON_S = 60.0                                  # écart mesuré 60 s après l'effet (plan §3)


@dataclass
class Active:
    """Effet en cours sur un coureur."""

    spec: EffectSpec
    until_t: float
    item: str
    by: str | None


def apply_speed(v: float, v_eq: float, impulses: list[EffectSpec], active: list[Active]) -> float:
    """Vitesse virtuelle après les impulsions du pas et les bornes des effets en cours."""
    for e in impulses:
        v *= e.factor
    floors = [a.spec.factor for a in active if a.spec.effect == "speed_floor"]
    caps = [a.spec.factor for a in active if a.spec.effect == "cap"]
    if floors:
        v = max(v, max(floors) * v_eq)
    if caps:
        v = min(v, min(caps) * v_eq)
    return max(v, 0.0)


def wind_of(active: list[Active]) -> float:
    return sum(a.spec.factor for a in active if a.spec.effect == "wind")


def is_immune(active: list[Active]) -> bool:
    return any(a.spec.effect == "immune" for a in active)


def gain_s(effects: tuple[EffectSpec, ...] | list[EffectSpec], power_w: float = 250.0, grade_pct: float = 0.0,
           params: PhysicsParams | None = None, dt: float = 0.02, horizon_s: float = GAIN_HORIZON_S) -> float:
    """Temps gagné (positif) ou perdu par un coureur qui reçoit `effects` à l'équilibre, mesuré
    `horizon_s` après sur un coureur identique sans effet : la méthode des chiffres du plan §3."""
    p = params or PhysicsParams()
    v_eq = steady_speed(power_w, grade_pct, p)
    a, b = RiderPhysics(p, 0.0, v_eq), RiderPhysics(replace(p), 0.0, v_eq)
    impulses = [e for e in effects if e.effect in IMPULSES]
    active = [Active(e, e.duration_s, "", None) for e in effects if e.effect in DURATIONS]
    a.v = apply_speed(a.v, v_eq, impulses, active)
    t = 0.0
    while t < horizon_s - 1e-9:
        t += dt
        live = [x for x in active if t <= x.until_t + 1e-9]
        a.p = replace(p, wind_mps=p.wind_mps + wind_of(live))
        a.step(power_w, grade_pct, dt=dt)
        b.step(power_w, grade_pct, dt=dt)
        a.v = apply_speed(a.v, v_eq, [], live)
    return (a.s - b.s) / v_eq
