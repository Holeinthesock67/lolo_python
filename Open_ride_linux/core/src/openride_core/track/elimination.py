"""Élimination (lot VD6) : le dernier sort tous les 2 tours, avec les règles du Dernier survivant.

Les règles sont celles de DS (`survivor.SurvivorRace`, sans copie de code) : une « arche » sur la ligne
d'arrivée tous les 2 tours, une par adversaire ; dès que tous les coureurs en course sauf un l'ont
passée, le dernier est éliminé ; le dernier en course gagne. Ce module n'en fait que l'habillage de piste.
"""

from __future__ import annotations

import math

from ..survivor import SurvivorRace
from .base import ME, Entrant, TrackEvent

EVERY_LAPS = 2


class Elimination(TrackEvent):
    event_id = "elimination"
    min_riders = 4
    max_riders = 12

    def __init__(self, entrants: list[Entrant], **kw) -> None:
        super().__init__(entrants, **kw)
        self._bots = [(e.id, e.name, float(e.level)) for e in entrants if e.id != ME]
        self.race: SurvivorRace | None = None
        self.origin = 0.0

    @property
    def laps(self) -> int:
        return EVERY_LAPS * len(self._bots)

    def _on_start(self, t: float) -> None:
        lead = max(r.s for r in self.riders.values())
        self.origin = self.line_s + math.ceil((lead - self.line_s) / self.lap_m - 1e-9) * self.lap_m
        arches = [self.origin + EVERY_LAPS * self.lap_m * k for k in range(1, len(self._bots) + 1)]
        self.race = SurvivorRace(arches, self._bots, spacing_km=EVERY_LAPS * self.lap_m / 1000.0, seed=self.seed)
        self.race.start(t, self._positions())

    def _positions(self) -> dict[str, tuple[float, float]]:
        return {r.id: (r.s, r.v) for r in self.racing()}

    def _advance(self, t0: float, t1: float) -> None:
        assert self.race is not None
        for rid in self.race.step(t1, self._positions()):
            self._out(self.riders[rid], "eliminated", t1)
        self.race.take_journal()           # le journal de la piste garde ses propres lignes
        if self.race.finished:
            self._end(t1)

    def _ranking(self) -> list[str]:
        if self.race is None:
            return list(self.riders)
        rc = self.race.racers
        alive = list(self.race.frame()["alive"])
        out = sorted((rid for rid in rc if rc[rid].out_arch is not None), key=lambda rid: -(rc[rid].out_arch or 0))
        return alive + out

    def lap_info(self) -> tuple[int | None, int | None]:
        lead = max((r.s for r in self.racing()), default=self.origin)
        return min(max(int((lead - self.origin) // self.lap_m) + 1, 1), self.laps), self.laps

    def bell(self) -> bool:
        lap, _ = self.lap_info()
        return lap is not None and lap % EVERY_LAPS == 0 and not self.finished

    def _frame_extra(self) -> dict:
        if self.race is None:
            return {}
        f = self.race.frame()
        return {"to_elim_m": f["d_m"], "gap_last_s": f["gap_last_s"], "last": f["last"], "alive": len(f["alive"])}
