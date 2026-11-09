"""Socle des courses en peloton (lot VD6) : scratch, course aux points, tempo, keirin, américaine.

Départ groupé derrière la ligne (grille de la séance) ou lancé (omnium) : l'origine de la course est la
première ligne d'arrivée devant le coureur le plus avancé, la course compte `laps` tours depuis elle.

Tours pris : un coureur (ou une équipe, à l'américaine) qui compte un tour d'avance sur la médiane des
autres a pris un tour (+20 points quand l'épreuve en donne), un tour de retard, il en a perdu un
(−20). Le classement se lit alors à tours égaux : un coureur qui a pris un tour passe les lignes
« avec » le peloton (distance ajustée = distance − tours d'avance × tour), et finit devant lui.

Cloche quand la tête de la course entame le dernier tour. Arrivée de chacun au passage de la ligne au
bout des `laps` tours (distance ajustée) ; une minute après la première arrivée, l'épreuve se clôt.
"""

from __future__ import annotations

import math
import statistics

from .base import FINISH_GRACE_S, ME, Entrant, TrackError, TrackEvent, cross_time

LAP_POINTS = 20


class Unit:
    """Un concurrent classé : un coureur, ou une équipe de l'américaine."""

    def __init__(self, uid: str, members: list[str]) -> None:
        self.id = uid
        self.members = members
        self.d = 0.0                 # distance depuis l'origine de la course
        self.d_prev = 0.0
        self.gained = 0
        self.lost = 0
        self.next_mark = 1           # prochaine ligne à passer (distance ajustée)
        self.finish_t: float | None = None

    @property
    def net(self) -> int:
        return self.gained - self.lost


class MassRace(TrackEvent):
    min_riders = 4               # le cycliste et 3 bots au moins
    max_riders = 12
    laps_allowed: tuple[int, ...] = tuple(range(10, 61))
    lap_points = 0               # points d'un tour pris (0 : le scratch classe aux tours, sans points)

    def __init__(self, entrants: list[Entrant], laps: int = 20, **kw) -> None:
        super().__init__(entrants, **kw)
        if isinstance(laps, bool) or not isinstance(laps, int) or laps not in self.laps_allowed:
            raise TrackError(f"{self.event_id} : {laps!r} tours refusés ({self.laps_allowed[0]} à {self.laps_allowed[-1]})")
        self.laps = laps
        self.units: dict[str, Unit] = {uid: Unit(uid, m) for uid, m in self._groups(entrants).items()}
        self.origin = 0.0
        self.line_order: dict[int, list[str]] = {}
        self.finish_order: list[str] = []
        self.pts: dict[str, int] = {uid: 0 for uid in self.units}
        self.bell_rung = False
        self._first_finish: float | None = None

    def _groups(self, entrants: list[Entrant]) -> dict[str, list[str]]:
        return {e.id: [e.id] for e in entrants}

    def unit_of(self, rid: str) -> str:
        for u in self.units.values():
            if rid in u.members:
                return u.id
        raise KeyError(rid)

    def _active(self, u: Unit) -> bool:
        return any(self.riders[m].out is None for m in u.members)

    # --- distance d'une unité ---

    def _unit_d(self, u: Unit) -> float:
        return self.riders[u.members[0]].s - self.origin

    def _on_start(self, t: float) -> None:
        lead = max(r.s for r in self.riders.values())
        self.origin = self.line_s + math.ceil((lead - self.line_s) / self.lap_m - 1e-9) * self.lap_m
        for u in self.units.values():
            u.d = u.d_prev = self._unit_d(u)

    def adjusted(self, u: Unit) -> float:
        return u.d - u.net * self.lap_m

    # --- pas ---

    def _advance(self, t0: float, t1: float) -> None:
        for u in self.units.values():
            u.d_prev, u.d = u.d, self._unit_d(u)
        crossings: list[tuple[float, int, str]] = []
        for u in self.units.values():
            if not self._active(u) or u.finish_t is not None:
                continue
            a0, a1 = u.d_prev - u.net * self.lap_m, u.d - u.net * self.lap_m
            while u.next_mark <= self.laps and a0 < u.next_mark * self.lap_m <= a1:
                crossings.append((cross_time(t0, a0, t1, a1, u.next_mark * self.lap_m), u.next_mark, u.id))
                u.next_mark += 1
        for tc, k, uid in sorted(crossings, key=lambda c: (c[0], c[1], c[2] != ME, c[2])):
            self._line(k, uid, tc)
        self._lap_changes(t1)
        self._pace(t0, t1)
        active = [u for u in self.units.values() if self._active(u)]
        if active and all(u.finish_t is not None for u in active):
            self._end(max(u.finish_t for u in active))
        elif self._first_finish is not None and t1 - self._first_finish >= FINISH_GRACE_S:
            self._end(t1)

    def _line(self, k: int, uid: str, tc: float) -> None:
        order = self.line_order.setdefault(k, [])
        order.append(uid)
        if k == self.laps - 1 and not self.bell_rung:
            self.bell_rung = True
            self._emit("bell", laps_to_go=1)
        self._on_line(k, uid, tc, len(order))
        if k == self.laps:
            u = self.units[uid]
            u.finish_t = tc
            self.finish_order.append(uid)
            if self._first_finish is None:
                self._first_finish = tc
            self._emit("arrival", unit=uid, place=len(self.finish_order))

    def _on_line(self, k: int, uid: str, tc: float, rank: int) -> None:
        pass

    def _pace(self, t0: float, t1: float) -> None:
        pass

    def _lap_changes(self, t: float) -> None:
        active = [u for u in self.units.values() if self._active(u) and u.finish_t is None]
        if len(active) < 3:
            return
        for u in active:
            med = statistics.median(o.d for o in active if o is not u)
            diff = u.d - med
            while diff >= (u.gained + 1) * self.lap_m:
                u.gained += 1
                self.pts[u.id] += self.lap_points
                self._emit("lap_gained", unit=u.id, points=self.lap_points)
            while -diff >= (u.lost + 1) * self.lap_m:
                u.lost += 1
                self.pts[u.id] -= self.lap_points
                self._emit("lap_lost", unit=u.id, points=-self.lap_points)

    def _award(self, uid: str, n: int, why: str) -> None:
        if n:
            self.pts[uid] += n
            self._emit("points", unit=uid, points=n, why=why)

    # --- classement ---

    def _final_rank(self, uid: str) -> int:
        return self.finish_order.index(uid) if uid in self.finish_order else len(self.units)

    def _key(self, u: Unit) -> tuple:
        """Scratch : tours d'avance, puis ordre d'arrivée, puis distance ajustée."""
        return (-u.net, self._final_rank(u.id), -self.adjusted(u), u.id)

    def _ranking(self) -> list[str]:
        active = sorted((u for u in self.units.values() if self._active(u)), key=self._key)
        out = sorted((u for u in self.units.values() if not self._active(u)),
                     key=lambda u: (-max(self.riders[m].out_t or 0.0 for m in u.members), u.id))
        return [u.id for u in active] + [u.id for u in out]

    def lap_info(self) -> tuple[int | None, int | None]:
        marks = [u.next_mark for u in self.units.values() if self._active(u)]
        return (min(max(marks), self.laps) if marks else self.laps), self.laps

    def bell(self) -> bool:
        return self.bell_rung

    def points(self) -> dict[str, int] | None:
        return dict(self.pts) if self.lap_points else None

    def _frame_extra(self) -> dict:
        u = self.units[self.unit_of(ME)]
        return {"laps_up": u.net, "my_lap": min(u.next_mark, self.laps)}

    def _summary_extra(self) -> dict:
        return {"laps_total": self.laps,
                "laps_up": {u.id: u.net for u in self.units.values() if u.net}}


class PointsRace(MassRace):
    """Socle des épreuves aux points : classement aux points, puis place à l'arrivée."""

    lap_points = LAP_POINTS

    def _key(self, u: Unit) -> tuple:
        return (-self.pts[u.id], self._final_rank(u.id), -self.adjusted(u), u.id)
