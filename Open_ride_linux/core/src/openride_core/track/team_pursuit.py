"""Poursuite par équipes (lot VD6) : 4 coureurs, 4 km départ arrêté, temps pris sur le 3e coureur.

Relais tous les demi-tours ou tous les tours (réglable) : le meneur remonte et se replace en dernière
position ; un coureur décroché de plus de 30 m du 3e est lâché (`pursuit.DROP_M`). Contre une équipe
de bots partie de l'autre côté de la piste.
"""

from __future__ import annotations

from .base import LAP_M, Entrant, TrackError
from .pursuit import Pursuit

RELAYS_LAPS = (0.5, 1.0)


class TeamPursuit(Pursuit):
    event_id = "team_pursuit"
    max_riders = 8
    team_size = 4
    count = 3
    relay_mode = "rotate"

    def __init__(self, entrants: list[Entrant], relay_laps: float = 0.5, **kw) -> None:
        if relay_laps not in RELAYS_LAPS:
            raise TrackError(f"poursuite par équipes : relais tous les {relay_laps!r} tours refusé (0,5 ou 1)")
        lap = float(kw.get("lap_m", LAP_M))
        kw.pop("distance_m", None)
        super().__init__(entrants, distance_m=4000.0, relay_m=relay_laps * lap, **kw)

    def _check_distance(self) -> None:
        if self.distance_m != 4000.0:
            raise TrackError("poursuite par équipes : 4 000 m")

    def _record_id(self) -> str:
        return "track:team_pursuit"
