"""Américaine (lot VD6) : équipes de 2, course aux points, relais environ tous les tours et demi.

Un seul coureur de chaque équipe est en course à la fois : la distance de l'équipe avance avec lui
(`Unit.d` cumule ses mètres). Tous les `RELAY_M`, il lance son coéquipier (message `relay` : l'équipe,
le relayé, le relayeur et la vitesse du relayé, que la séance donne au relayeur : lancer simulé) puis
remonte en haut de la piste à allure libre. Barème de la course aux points, par équipe.
"""

from __future__ import annotations

from .base import Entrant, TrackError
from .mass import Unit
from .points import Points

RELAY_M = 375.0


class Madison(Points):
    event_id = "madison"
    min_riders = 8               # 4 équipes : la tienne et 3 à 5 autres
    max_riders = 12
    laps_allowed = tuple(range(20, 61, 10))

    def __init__(self, entrants: list[Entrant], laps: int = 30, **kw) -> None:
        super().__init__(entrants, laps=laps, **kw)
        self.active: dict[str, int] = {u.id: 0 for u in self.units.values()}
        self._since: dict[str, float] = {u.id: 0.0 for u in self.units.values()}

    def _groups(self, entrants: list[Entrant]) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for e in entrants:
            if e.team is None:
                raise TrackError(f"américaine : {e.id} sans équipe")
            groups.setdefault(e.team, []).append(e.id)
        for tid, m in groups.items():
            if len(m) != 2:
                raise TrackError(f"américaine : équipe {tid} de {len(m)} coureurs (2 attendus)")
        return groups

    def racer(self, team: str) -> str:
        """Coureur de l'équipe en course en ce moment."""
        u = self.units[team]
        return u.members[self.active.get(team, 0)]

    def _on_start(self, t: float) -> None:
        super()._on_start(t)
        for u in self.units.values():          # départ : le premier coureur de chaque équipe est lancé
            u.d = u.d_prev = self.riders[self.racer(u.id)].s - self.origin

    def _unit_d(self, u: Unit) -> float:
        rid = self.racer(u.id)
        moved = max(self.riders[rid].s - self._prev[rid][1], 0.0)
        return u.d + moved

    def _advance(self, t0: float, t1: float) -> None:
        before = {u.id: u.d for u in self.units.values()}
        super()._advance(t0, t1)
        for u in self.units.values():
            self._since[u.id] += u.d - before[u.id]
            if self._since[u.id] >= RELAY_M and u.finish_t is None:
                self._since[u.id] -= RELAY_M
                frm = self.racer(u.id)
                self.active[u.id] = 1 - self.active[u.id]
                self._emit("relay", team=u.id, rider=frm, to=self.racer(u.id), v=round(self.riders[frm].v, 2))

    def _frame_extra(self) -> dict:
        out = super()._frame_extra()
        out["racers"] = {tid: self.racer(tid) for tid in self.units}
        return out
