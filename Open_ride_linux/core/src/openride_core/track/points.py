"""Course aux points (lot VD6) : sprint tous les 10 tours (5, 3, 2, 1 points, double au dernier),
20 points par tour pris, 20 de moins par tour perdu (barème de la piste, plan §5)."""

from __future__ import annotations

from .base import TrackError
from .mass import PointsRace

SPRINT_EVERY = 10
SPRINT_POINTS = (5, 3, 2, 1)


class Points(PointsRace):
    event_id = "points"
    laps_allowed = tuple(range(10, 61, 10))

    def _on_line(self, k: int, uid: str, tc: float, rank: int) -> None:
        if k % SPRINT_EVERY == 0 and rank <= len(SPRINT_POINTS):
            n = SPRINT_POINTS[rank - 1] * (2 if k == self.laps else 1)
            self._award(uid, n, f"sprint_{k // SPRINT_EVERY}")

    def _frame_extra(self) -> dict:
        out = super()._frame_extra()
        lap, _ = self.lap_info()
        nxt = min(((lap or 1) + SPRINT_EVERY - 1) // SPRINT_EVERY * SPRINT_EVERY, self.laps)
        out["next_sprint_lap"] = nxt
        return out
