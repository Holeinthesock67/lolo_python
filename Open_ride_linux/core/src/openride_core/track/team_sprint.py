"""Vitesse par équipes (lot VD6) : 3 coureurs, 3 tours départ arrêté, chacun mène un tour puis s'écarte.

Le joueur choisit sa place (1, 2 ou 3) : la séance range les engagés de son équipe dans cet ordre.
Le chrono de l'équipe est celui du dernier coureur sur la ligne au bout des 3 tours ; contre une autre
équipe de bots partie de l'autre côté de la piste.
"""

from __future__ import annotations

from .base import LAP_M, Entrant, TrackError
from .pursuit import Pursuit


class TeamSprint(Pursuit):
    event_id = "team_sprint"
    max_riders = 6
    team_size = 3
    count = 1
    relay_mode = "leave"

    def __init__(self, entrants: list[Entrant], **kw) -> None:
        lap = float(kw.get("lap_m", LAP_M))
        super().__init__(entrants, distance_m=3 * lap, relay_m=lap, **kw)

    def _check_distance(self) -> None:
        if abs(self.distance_m - 3 * self.lap_m) > 1e-6:
            raise TrackError("vitesse par équipes : 3 tours")

    def _record_id(self) -> str:
        return "track:team_sprint"
