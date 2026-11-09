"""Keirin (lot VD6) : derny devant le peloton jusqu'à 3 tours de l'arrivée, puis sprint.

Le derny (véhicule d'AS6, la séance le dessine et en donne l'abri) part juste devant le coureur le plus
avancé à 30 km/h et accélère régulièrement jusqu'à 50 km/h ; il s'écarte quand il atteint la ligne des
3 derniers tours. Un coureur qui le dépasse avant est déclassé (sorti de la course). Classement du scratch.
"""

from __future__ import annotations

from .base import Entrant
from .mass import MassRace

PACER_START_KMH = 30.0
PACER_END_KMH = 50.0
PACER_LEAD_M = 5.0
PACER_LEAVES_LAPS = 3


class Keirin(MassRace):
    event_id = "keirin"
    max_riders = 7               # le cycliste et 3 à 6 bots
    laps_allowed = (6, 8)

    def __init__(self, entrants: list[Entrant], laps: int = 8, **kw) -> None:
        super().__init__(entrants, laps=laps, **kw)
        self.pacer_d = 0.0
        self.pacer_v = PACER_START_KMH / 3.6
        self.pacer_on = True

    @property
    def leave_d(self) -> float:
        return (self.laps - PACER_LEAVES_LAPS) * self.lap_m

    def _on_start(self, t: float) -> None:
        super()._on_start(t)
        self.pacer_d = max(u.d for u in self.units.values()) + PACER_LEAD_M

    def _pace(self, t0: float, t1: float) -> None:
        if not self.pacer_on:
            return
        # règle d'abord sur la position du pas : passer devant le derny déclasse
        for r in self.racing():
            if r.s - self.origin > self.pacer_d:
                self._out(r, "passed_pacer", t1)
        frac = min(max(self.pacer_d / self.leave_d, 0.0), 1.0) if self.leave_d > 0 else 1.0
        self.pacer_v = (PACER_START_KMH + (PACER_END_KMH - PACER_START_KMH) * frac) / 3.6
        self.pacer_d += self.pacer_v * (t1 - t0)
        if self.pacer_d >= self.leave_d:
            self.pacer_on = False
            self._emit("pacer_off", laps_to_go=PACER_LEAVES_LAPS)

    def _frame_extra(self) -> dict:
        out = super()._frame_extra()
        out["pacer"] = {"s": round(self.origin + self.pacer_d, 2), "v": round(self.pacer_v, 2), "on": self.pacer_on}
        return out
