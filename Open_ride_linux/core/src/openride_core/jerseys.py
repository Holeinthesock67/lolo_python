"""Points et maillots de la séance : maillot vert (sprints) et à pois (montées) (lot T14, série T).

Module pur, sans branchement dans la séance (il vient avec le contrat T1). Cahier :
`docs/lots/LOT_T14_points_maillots.md`.

Règles (plan de la série T §3.4, décisions T-Q5 et du 27 octobre) :
- les points se gagnent à l'ordre d'arrivée sur la ligne de fin d'un segment, bots compris ;
  chaque passage est une course à part (un tour d'une boucle, ou un segment) ;
- barème des montées par catégorie : HC 20, 15, 10, 6, 4 ; 1re 10, 8, 6, 4, 2 ; 2e 5, 3, 2, 1 ;
  3e 2, 1 ; 4e 1 ; sprints : 15, 10, 6, 4, 2 ;
- maillot à pois (`kom`) au plus de points de montée, maillot vert (`sprint`) au plus de points
  de sprint, attribués pendant la séance ; égalité : celui qui a atteint ce total le premier ;
- un passage annulé par une pause ne marque pas ; un passage avec bonus marque comme les autres.

Les identifiants de maillot `kom` et `sprint` sont ceux que lit la série V (`progression.py`,
lignes `jersey` du journal, lot V5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol

CLIMB_POINTS: dict[str, tuple[int, ...]] = {
    "HC": (20, 15, 10, 6, 4),
    "1": (10, 8, 6, 4, 2),
    "2": (5, 3, 2, 1),
    "3": (2, 1),
    "4": (1,),
}
SPRINT_POINTS: tuple[int, ...] = (15, 10, 6, 4, 2)
JERSEYS = {"sprint": "sprint", "climb": "kom"}   # type de segment → maillot


class SegmentLike(Protocol):
    id: str
    type: str
    category: str | None


def scale(seg: SegmentLike) -> tuple[int, ...]:
    """Barème d'un segment (places 1, 2, 3…)."""
    if seg.type == "sprint":
        return SPRINT_POINTS
    if seg.type == "climb":
        return CLIMB_POINTS.get(str(seg.category), CLIMB_POINTS["4"])
    raise ValueError(f"type de segment inconnu : {seg.type}")


@dataclass(frozen=True)
class Finish:
    rider_id: str
    segment_id: str
    lap: int
    t_end: float               # temps chronométré de la séance au franchissement de la ligne


@dataclass(frozen=True)
class Award:
    rider_id: str
    segment_id: str
    lap: int
    place: int
    points: int
    jersey: str                # "sprint" ou "kom"


@dataclass
class Standings:
    """Points de la séance et porteurs des maillots."""

    segments: Iterable[SegmentLike]
    awards: list[Award] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._segs = {s.id: s for s in self.segments}
        self._arrived: dict[tuple[str, int], list[str]] = {}
        self._points: dict[str, dict[str, int]] = {"sprint": {}, "kom": {}}
        self._reached: dict[str, dict[str, float]] = {"sprint": {}, "kom": {}}

    def finish(self, finishes: Iterable[Finish]) -> list[Award]:
        """Arrivées d'un pas de la séance (cycliste et bots), rangées par heure de franchissement."""
        out: list[Award] = []
        for f in sorted(finishes, key=lambda f: f.t_end):
            seg = self._segs.get(f.segment_id)
            if seg is None:
                raise KeyError(f"segment inconnu : {f.segment_id}")
            arrived = self._arrived.setdefault((f.segment_id, f.lap), [])
            if f.rider_id in arrived:
                continue          # une seule arrivée par coureur et par passage
            arrived.append(f.rider_id)
            place = len(arrived)
            table = scale(seg)
            jersey = JERSEYS[seg.type]
            points = table[place - 1] if place <= len(table) else 0
            if points:
                total = self._points[jersey].get(f.rider_id, 0) + points
                self._points[jersey][f.rider_id] = total
                self._reached[jersey][f.rider_id] = f.t_end
            award = Award(f.rider_id, f.segment_id, f.lap, place, points, jersey)
            self.awards.append(award)
            out.append(award)
        return out

    def points(self, rider_id: str) -> dict[str, int]:
        return {j: self._points[j].get(rider_id, 0) for j in ("sprint", "kom")}

    def leader(self, jersey: str) -> str | None:
        """Porteur du maillot (`sprint` ou `kom`), None tant que personne n'a de point."""
        pts = self._points[jersey]
        if not pts:
            return None
        return min(pts, key=lambda r: (-pts[r], self._reached[jersey][r]))

    def state_dict(self) -> dict:
        """Forme proposée pour la trame `state` (contrat T1) : porteurs et points."""
        riders = sorted(set(self._points["sprint"]) | set(self._points["kom"]))
        return {"jerseys": {"sprint": self.leader("sprint"), "kom": self.leader("kom")},
                "points": {r: self.points(r) for r in riders}}
