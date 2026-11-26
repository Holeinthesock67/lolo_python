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

Courbe du cycliste (série PP, lot PP6) : `Effort.curve`, facultative, remplace la courbe type par celle du
cycliste en cours (meilleur effort par durée, libre ou ERG, des 6 dernières semaines, sinon des 6 derniers mois,
en % de sa FTP : `personal_curve`), bornée à ± `CURVE_BOUND_PCT` % de la courbe type ; hors des durées de la
courbe du cycliste, la courbe type reste. La cote Elo reste un multiplicateur par-dessus (niveau), la courbe ne la
recale jamais. `hold_s` donne l'inverse : la durée que le cycliste tient à une part de sa FTP.
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
# Course conseillée (lot GP-niv, CO9) : l'objectif des bots suit le besoin du jour, sans toucher au réglage commun.
NEED_OBJECTIVE: dict[str, str] = {"light": "endurance", "intense": "threshold", "anaerobic": "max",
                                  "recovery": "recovery"}
ITERATIONS = 3


@dataclass(frozen=True)
class Effort:
    """Course que les bots vont courir : objectif, longueur (m) et durée fixe (s) si l'épreuve en a une ; courbe
    du cycliste en cours (lot PP6, ((durée s, % de la FTP), …) croissantes en durée), None : courbe type."""
    objective: str = DEFAULT_OBJECTIVE
    course_m: float | None = None      # None : un passage du parcours
    duration_s: float | None = None    # durée fixe : remplace la durée estimée
    curve: tuple[tuple[float, float], ...] | None = None


def curve_pct(duration_s: float) -> float:
    """% de la FTP tenu à fond pendant `duration_s` (courbe type, interpolation sur le logarithme de la durée)."""
    return _interp_log(POWER_CURVE, duration_s)


CURVE_BOUND_PCT = 15.0     # courbe du cycliste : au plus ± 15 % de la courbe type (cadrage PP6 §4)
HOLD_MIN_S, HOLD_MAX_S = 5.0, 10800.0


def _interp_log(pts: tuple[tuple[float, float], ...], duration_s: float) -> float:
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


def curve_pct_for(curve: tuple[tuple[float, float], ...] | None, duration_s: float) -> float:
    """% de la FTP tenu pendant `duration_s` : courbe du cycliste (lot PP6) entre sa plus courte et sa plus longue
    durée, bornée à ± `CURVE_BOUND_PCT` % de la courbe type ; ailleurs, ou sans courbe, la courbe type."""
    generic = curve_pct(duration_s)
    if not curve or len(curve) < 2 or not curve[0][0] <= duration_s <= curve[-1][0]:
        return generic
    k = CURVE_BOUND_PCT / 100.0
    return min(max(_interp_log(curve, duration_s), generic * (1.0 - k)), generic * (1.0 + k))


def hold_s(pct: float, curve: tuple[tuple[float, float], ...] | None = None) -> float:
    """Durée (s) que le cycliste tient à `pct` % de sa FTP (inverse de `curve_pct_for`, décroissante), bornée à
    `HOLD_MIN_S` et `HOLD_MAX_S` ; partagée par la fiche de la course, le Grand Prix et le Dernier survivant."""
    lo, hi = math.log(HOLD_MIN_S), math.log(HOLD_MAX_S)
    if curve_pct_for(curve, HOLD_MIN_S) <= pct:
        return HOLD_MIN_S
    if curve_pct_for(curve, HOLD_MAX_S) >= pct:
        return HOLD_MAX_S
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if curve_pct_for(curve, math.exp(mid)) > pct:
            lo = mid
        else:
            hi = mid
    return math.exp(0.5 * (lo + hi))


def personal_curve(weeks6: list[dict], months6: list[dict], ftp_w: float
                   ) -> tuple[tuple[float, float], ...] | None:
    """Courbe du cycliste en % de sa FTP depuis les points des fenêtres de `power_curve.window_curve` (meilleur
    effort par durée, libre ou ERG) : 6 semaines, sinon 6 mois ; None sans FTP ou avec moins de deux durées.
    La courbe est rendue décroissante (une durée plus longue ne tient jamais plus qu'une plus courte)."""
    if ftp_w <= 0:
        return None
    by_s: dict[int, float] = {}
    for pts in (months6, weeks6):          # les 6 semaines remplacent les 6 mois là où elles ont un effort
        for p in pts or []:
            if p.get("watts") is not None and p.get("seconds"):
                by_s[int(p["seconds"])] = float(p["watts"])
    out: list[tuple[float, float]] = []
    for s_ in sorted(by_s, reverse=True):
        pct = round(100.0 * by_s[s_] / ftp_w, 1)
        if out and pct < out[-1][1]:
            pct = out[-1][1]
        out.append((float(s_), pct))
    out.reverse()
    return tuple(out) if len(out) >= 2 else None


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
    pct = level * share * curve_pct_for(effort.curve, duration)
    if effort.duration_s:
        return pct, duration
    for _ in range(ITERATIONS):
        duration = time_of(ftp_w * pct / 100.0) * laps
        pct = level * share * curve_pct_for(effort.curve, duration)
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
