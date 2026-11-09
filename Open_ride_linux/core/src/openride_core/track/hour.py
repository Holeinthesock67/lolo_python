"""Record de l'heure (lot VD6) : distance couverte en 60 minutes, tableau des tours.

Seul en piste, départ arrêté. La distance à l'heure pile est interpolée entre deux pas ; la pause
fige l'horloge de l'épreuve (le temps chronométré de la séance ne bouge pas).
"""

from __future__ import annotations

from .base import ME, Entrant, TrackError, TrackEvent

DURATIONS_S = (3600.0,)


class Hour(TrackEvent):
    event_id = "hour"
    record_id = "track:hour"
    max_riders = 1

    def __init__(self, entrants: list[Entrant], duration_s: float = 3600.0, **kw) -> None:
        if float(duration_s) not in DURATIONS_S:
            raise TrackError(f"record de l'heure : {duration_s!r} s refusé")
        super().__init__(entrants, **kw)
        self.duration_s = float(duration_s)
        self.distance_m: float | None = None

    def _advance(self, t0: float, t1: float) -> None:
        assert self.t0 is not None
        end = self.t0 + self.duration_s
        if t1 < end:
            return
        me = self.riders[ME]
        d0 = self._prev[ME][1] - me.start_s
        d = d0 + (me.d - d0) * (end - t0) / (t1 - t0)
        self.distance_m = d
        self._emit("result", rider=ME, distance_m=round(d, 1))
        self._end(end)

    def _ranking(self) -> list[str]:
        return [ME]

    def _frame_extra(self) -> dict:
        d = self.distance_m if self.distance_m is not None else self.riders[ME].d
        el = self.elapsed_s
        return {"d_m": round(max(d, 0.0), 1), "time_left_s": round(max(self.duration_s - el, 0.0), 1),
                "avg_kmh": round(3.6 * max(d, 0.0) / el, 2) if el > 0 else None}

    def record(self) -> dict | None:
        if self.distance_m is None:
            return None
        return {"id": self.record_id, "time_s": self.duration_s, "distance_m": round(self.distance_m, 1)}

    def _summary_extra(self) -> dict:
        return {"distance_m": None if self.distance_m is None else round(self.distance_m, 1),
                "duration_s": self.duration_s}
