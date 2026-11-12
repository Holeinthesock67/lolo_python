"""Contre-la-montre de piste (lot VD6) : kilomètre et 500 m départ arrêté, 200 m lancé.

Seul en piste (le fantôme est celui de la séance, `replay.py`). Le 200 m lancé se court sur deux tours
et demi : 425 m d'élan puis 200 m chronométrés jusqu'à la ligne (plan §5).
"""

from __future__ import annotations

import math

from .base import ME, Entrant, TrackError, TrackEvent, cross_time

VARIANTS = {"kilo": (1000.0, 1000.0), "500": (500.0, 500.0), "flying_200": (625.0, 200.0)}  # (distance, chronométrés)


class TimeTrial(TrackEvent):
    max_riders = 1

    def __init__(self, entrants: list[Entrant], variant: str = "kilo", **kw) -> None:
        if variant not in VARIANTS:
            raise TrackError(f"contre-la-montre : {variant!r} refusé ({', '.join(VARIANTS)})")
        self.event_id = variant
        self.record_id = f"track:{variant}"
        super().__init__(entrants, **kw)
        self.distance_m, self.timed_m = VARIANTS[variant]
        self.timing_t: float | None = None     # départ du chrono (instant du départ, ou ligne des 200 m)
        self.time_s: float | None = None

    def _on_start(self, t: float) -> None:
        if self.timed_m >= self.distance_m:
            self.timing_t = t

    def _advance(self, t0: float, t1: float) -> None:
        me = self.riders[ME]
        d1 = me.d
        d0 = self._prev[ME][1] - me.start_s
        mark = self.distance_m - self.timed_m
        if self.timing_t is None and d0 < mark <= d1:
            self.timing_t = cross_time(t0, d0, t1, d1, mark)
            self._emit("timing", rider=ME, d_m=mark)
        if self.timing_t is not None and d0 < self.distance_m <= d1:
            tc = cross_time(t0, d0, t1, d1, self.distance_m)
            self.time_s = tc - self.timing_t
            self._emit("result", rider=ME, time_s=round(self.time_s, 3))
            self._end(tc)

    def _ranking(self) -> list[str]:
        return [ME]

    def lap_info(self) -> tuple[int | None, int | None]:
        laps = math.ceil(self.distance_m / self.lap_m - 1e-9)
        return min(int(max(self.riders[ME].d, 0.0) // self.lap_m) + 1, laps), laps

    def _frame_extra(self) -> dict:
        d = max(self.riders[ME].d, 0.0)
        running = None
        if self.time_s is not None:
            running = self.time_s
        elif self.timing_t is not None:
            running = self.t - self.timing_t
        return {"d_m": round(min(d, self.distance_m), 1), "to_go_m": round(max(self.distance_m - d, 0.0), 1),
                "timed": self.timing_t is not None, "time_s": None if running is None else round(running, 3)}

    def record(self) -> dict | None:
        if self.time_s is None:
            return None
        return {"id": self.record_id, "time_s": round(self.time_s, 3), "distance_m": self.timed_m}

    def _summary_extra(self) -> dict:
        return {"time_s": None if self.time_s is None else round(self.time_s, 3), "distance_m": self.timed_m}
