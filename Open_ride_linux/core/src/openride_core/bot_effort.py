"""Effort visé par les bots selon la durée de la course et l'objectif de la séance (lot BT1, décisions du
propriétaire du 15 novembre 2026). Module pur, sans état.

Puissance cible des bots = FTP × courbe(durée de la course) × objectif × niveau des bots :

- **courbe** : part de la FTP qu'un humain tient à fond pendant la durée de la course (`POWER_CURVE`,
  1 h = 100 %, interpolée sur le logarithme de la durée, bornée aux extrémités de la table) ;
- **objectif** : part de cette courbe visée (`OBJECTIVES` : 55, 65, 80, 92 et 100 %, validées le 15/11) ;
  réglage commun `bots.objective`, Tempo par défaut ; au vélodrome, l'objectif suit l'épreuve
  (`TRACK_EFFORT`) ;
- **niveau** : réglage fin `bots.level_pct` (100 % : un plateau juste pour cet objectif).

La durée dépend de la puissance : `target_pct` la recalcule `ITERATIONS` fois avec le temps du cycliste de
référence à la puissance cible (`time_of`, un passage du parcours, multiplié par `course_m / route_m`), sauf
quand l'épreuve dure un temps fixe (`duration_s` : l'heure, la séance libre du vélodrome).
Cahier : `docs/lots/LOT_BT1_effort_des_bots.md`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

# Durée à fond (s) -> % de la FTP tenu (note du 15/11 ; de 2 à 60 min, l'allure du modèle CP + W'/t).
POWER_CURVE: tuple[tuple[float, float], ...] = (
    (60.0, 160.0), (300.0, 120.0), (600.0, 110.0), (1200.0, 105.0), (3600.0, 100.0), (7200.0, 88.0),
    (10800.0, 80.0))
OBJECTIVES: dict[str, float] = {"recovery": 55.0, "endurance": 65.0, "tempo": 80.0, "threshold": 92.0,
                                "max": 100.0}
DEFAULT_OBJECTIVE = "tempo"
ITERATIONS = 3


@dataclass(frozen=True)
class Effort:
    """Course que les bots vont courir : objectif, longueur (m) et durée fixe (s) si l'épreuve en a une."""
    objective: str = DEFAULT_OBJECTIVE
    course_m: float | None = None      # None : un passage du parcours
    duration_s: float | None = None    # durée fixe : remplace la durée estimée


def curve_pct(duration_s: float) -> float:
    """% de la FTP tenu à fond pendant `duration_s` (interpolation sur le logarithme de la durée)."""
    pts = POWER_CURVE
    if duration_s <= pts[0][0]:
        return pts[0][1]
    if duration_s >= pts[-1][0]:
        return pts[-1][1]
    x = math.log(duration_s)
    for (t0, p0), (t1, p1) in zip(pts, pts[1:]):
        if duration_s <= t1:
            k = (x - math.log(t0)) / (math.log(t1) - math.log(t0))
            return p0 + k * (p1 - p0)
    return pts[-1][1]


def share_pct(objective: str) -> float:
    """Part de la courbe visée par l'objectif ; un objectif inconnu vaut le défaut (Tempo)."""
    return OBJECTIVES.get(objective, OBJECTIVES[DEFAULT_OBJECTIVE])


def target_pct(level_pct: float, effort: Effort, ftp_w: float, time_of: Callable[[float], float],
               route_m: float) -> tuple[float, float]:
    """(% de la FTP visé par les bots, durée estimée de la course en s) pour le niveau `level_pct`.

    `time_of(puissance)` : temps d'un passage du parcours (`route_m` mètres) à puissance constante."""
    share = share_pct(effort.objective) / 100.0
    level = level_pct / 100.0
    laps = (effort.course_m / route_m) if effort.course_m and route_m > 0 else 1.0
    duration = effort.duration_s if effort.duration_s else 3600.0
    pct = level * share * curve_pct(duration)
    if effort.duration_s:
        return pct, duration
    for _ in range(ITERATIONS):
        duration = time_of(ftp_w * pct / 100.0) * laps
        pct = level * share * curve_pct(duration)
    return pct, duration


# Vélodrome (choix du propriétaire, 15/11) : À fond pour les contre-la-montre, Tempo pour les courses en
# groupe et la séance libre. Par épreuve : (objectif, longueur en m ou None, durée fixe en s ou None) ;
# longueur None et durée None : `laps` tours de l'épreuve (réglage), sinon `TRACK_DEFAULT_LAPS`.
TRACK_EFFORT: dict[str, tuple[str, float | None, float | None]] = {
    "free": ("tempo", None, 3600.0),
    "pursuit": ("max", 4000.0, None),
    "kilo": ("max", 1000.0, None),
    "500": ("max", 500.0, None),
    "flying_200": ("max", 200.0, None),
    "hour": ("max", None, 3600.0),
    "scratch": ("tempo", None, None),
    "points": ("tempo", None, None),
    "tempo": ("tempo", None, None),
    "elimination": ("tempo", None, None),
    "keirin": ("max", None, None),
    "omnium": ("tempo", None, None),
    "team_sprint": ("max", 750.0, None),
    "team_pursuit": ("max", 4000.0, None),
    "madison": ("tempo", None, None),
}
TRACK_DEFAULT_LAPS = 40    # élimination et omnium : environ 10 km


def track_effort(event: str, settings: dict, lap_m: float) -> Effort:
    """Effort des bots d'une épreuve de piste (`settings` : réglages de l'épreuve, `distance_m`, `laps`)."""
    objective, course_m, duration_s = TRACK_EFFORT.get(event, ("tempo", None, None))
    if "distance_m" in settings:
        course_m = float(settings["distance_m"])
    if course_m is None and duration_s is None and "every_laps" in settings and "opponents" in settings:
        # élimination : une élimination tous les `every_laps` tours, une par adversaire
        course_m = float(settings["every_laps"]) * float(settings["opponents"]) * lap_m
    if course_m is None and duration_s is None:
        course_m = float(settings.get("laps", TRACK_DEFAULT_LAPS)) * lap_m
    return Effort(objective, course_m, duration_s)
