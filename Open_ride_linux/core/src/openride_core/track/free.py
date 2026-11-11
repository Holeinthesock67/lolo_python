"""Séance libre sur la piste (lot VD6) : tours illimités, temps au tour, meilleur tour.

La seule épreuve qui accepte l'ERG ; bots et fantôme facultatifs (ils roulent, rien ne les classe).
"""

from __future__ import annotations

from .base import ME, TrackEvent


class Free(TrackEvent):
    event_id = "free"
    record_id = "track:best_lap"

    def _advance(self, t0: float, t1: float) -> None:
        pass                      # jamais finie : la séance s'arrête quand le cycliste le décide

    def _ranking(self) -> list[str]:
        return [ME]

    def _frame_extra(self) -> dict:
        return {"last_lap_s": round(self.my_laps[-1], 3) if self.my_laps else None,
                "best_lap_s": round(min(self.my_laps), 3) if self.my_laps else None}

    def record(self) -> dict | None:
        if not self.my_laps:
            return None
        return {"id": self.record_id, "time_s": round(min(self.my_laps), 3), "distance_m": self.lap_m}
