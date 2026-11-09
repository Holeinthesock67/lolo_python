"""Tempo (lot VD6) : 10 tours au moins ; à partir du 5e tour, 1 point au premier sur la ligne à chaque
tour, 20 points par tour pris."""

from __future__ import annotations

from .mass import PointsRace

FROM_LAP = 5


class Tempo(PointsRace):
    event_id = "tempo"
    laps_allowed = tuple(range(10, 41))

    def _on_line(self, k: int, uid: str, tc: float, rank: int) -> None:
        if k >= FROM_LAP and rank == 1:
            self._award(uid, 1, f"lap_{k}")
