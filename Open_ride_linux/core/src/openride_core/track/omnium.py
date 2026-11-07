"""Omnium (lot VD6) : scratch, tempo, élimination puis course aux points, classement aux points.

Les trois premières épreuves donnent des points de place (40 au premier, 2 de moins par place,
`base.place_points`) ; la course aux points finale ajoute ses points (tours pris compris, négatifs
aussi). Égalité : la place dans la course aux points. Entre deux épreuves, un tour neutralisé :
la suivante part lancée quand la médiane du peloton a fait un tour de plus.
"""

from __future__ import annotations

import statistics

from .base import ME, Entrant, TrackEvent, place_points
from .elimination import Elimination
from .points import Points
from .scratch import Scratch
from .tempo import Tempo

PROGRAM = (("scratch", Scratch, {"laps": 10}), ("tempo", Tempo, {"laps": 10}),
           ("elimination", Elimination, {}), ("points", Points, {"laps": 20}))
NEUTRAL_LAPS = 1


class Omnium(TrackEvent):
    event_id = "omnium"
    min_riders = 4
    max_riders = 12

    def __init__(self, entrants: list[Entrant], **kw) -> None:
        super().__init__(entrants, **kw)
        self._entrants = list(entrants)
        self._kw = {k: v for k, v in kw.items()}
        self.index = 0
        self.sub: TrackEvent | None = None
        self.totals: dict[str, int] = {e.id: 0 for e in entrants}
        self.results: list[dict] = []
        self._neutral_until: float | None = None
        # chaque épreuve du programme vérifie le plateau dès maintenant (rien ne part à moitié)
        for _, cls, opts in PROGRAM:
            cls(entrants, **opts, **kw)

    def _new_sub(self, t: float) -> None:
        sid, cls, opts = PROGRAM[self.index]
        kw = dict(self._kw)
        kw["seed"] = self.seed * 10 + self.index
        self.sub = cls(self._entrants, **opts, **kw)
        self.sub.start(t, {r.id: (r.s, r.v) for r in self.riders.values()})
        self._emit("sub_start", sub=sid, index=self.index + 1)

    def _on_start(self, t: float) -> None:
        self._new_sub(t)

    def _advance(self, t0: float, t1: float) -> None:
        if self.sub is None:
            assert self._neutral_until is not None
            if statistics.median(r.s for r in self.riders.values()) >= self._neutral_until:
                self._neutral_until = None
                self._new_sub(t1)
            return
        for msg in self.sub.step(t1, {r.id: (r.s, r.v) for r in self.riders.values()}):
            if msg.get("event") not in ("lap", "start"):
                self._emit(msg["event"], sub=PROGRAM[self.index][0],
                           **{k: v for k, v in msg.items() if k != "event"})
        self.sub.take_journal()
        if self.sub.finished:
            self._close_sub(t1)

    def _close_sub(self, t: float) -> None:
        assert self.sub is not None
        sid = PROGRAM[self.index][0]
        ranking = self.sub._ranking()
        if sid == "points":
            pts = self.sub.points() or {}
            gained = {rid: pts.get(rid, 0) for rid in ranking}
        else:
            gained = {rid: place_points(i + 1) for i, rid in enumerate(ranking)}
        for rid, n in gained.items():
            self.totals[rid] += n
        self.results.append({"sub": sid, "ranking": ranking, "points": gained})
        self.sub = None
        self.index += 1
        if self.index >= len(PROGRAM):
            self._end(t)
        else:
            self._neutral_until = statistics.median(r.s for r in self.riders.values()) + NEUTRAL_LAPS * self.lap_m

    def _ranking(self) -> list[str]:
        last = self.results[-1]["ranking"] if self.results else list(self.riders)
        order = {rid: i for i, rid in enumerate(last)}
        return sorted(self.riders, key=lambda rid: (-self.totals[rid], order.get(rid, len(order)), rid))

    def points(self) -> dict[str, int] | None:
        return dict(self.totals)

    def lap_info(self) -> tuple[int | None, int | None]:
        return self.sub.lap_info() if self.sub is not None else (None, None)

    def bell(self) -> bool:
        return self.sub.bell() if self.sub is not None else False

    def _frame_extra(self) -> dict:
        sub = self.sub.frame() if self.sub is not None else None
        out = {"sub": PROGRAM[min(self.index, len(PROGRAM) - 1)][0], "sub_index": min(self.index + 1, len(PROGRAM)),
               "subs": len(PROGRAM), "neutral": self.sub is None and not self.finished}
        if sub:
            out["eliminated"] = sub["eliminated"]
            for k in ("to_elim_m", "gap_last_s", "last", "alive", "next_sprint_lap", "laps_up"):
                if k in sub:
                    out[k] = sub[k]
        return out

    def _summary_extra(self) -> dict:
        return {"subs": [{"sub": r["sub"], "place": r["ranking"].index(ME) + 1 if ME in r["ranking"] else None,
                          "points": r["points"].get(ME, 0)} for r in self.results]}
