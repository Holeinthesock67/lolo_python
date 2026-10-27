"""Mode classique de la série T branché dans la séance (lot T7).

Réunit, pour une séance, les modules purs de la série T et remplit les champs de la révision 1.4
du contrat IPC qui les concernent :

- segments chronométrés (T4) pour le cycliste et pour chaque bot à puissance constante ;
- records personnels et classement local du passage (T5), écrits hors de la boucle à 50 Hz ;
- bonus (T6) : arches, bonus de fin de segment, activation par `Z_SHORT`, effets sur la physique ;
- points et maillots (T14) ; écarts en temps de passage et voisins (T16).

Le fantôme (bot `ghost`) n'est ni chronométré ni classé : ton meilleur temps le représente (T5).
Noms du contrat (révision 1.4) : le bonus `lightweight` du module s'appelle `light`, la réserve
`held`, et le cycliste `"me"` dans `jerseys`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from .gaps import RIDER_ID, GapTracker
from .jerseys import Finish, Standings
from .physics import PhysicsParams
from .powerups import ArchSchedule, PowerUps, PowerUpTable
from .records import DATE_FORMAT, RecordBook
from .segment_timing import SegmentPass, SegmentTimer

CONTRACT_POWERUP = {"lightweight": "light", "aero": "aero", "power": "power"}
SEGMENT_RESULT_REPEAT = 3        # message `segment_result` répété 3 fois, à une seconde d'intervalle
SUMMARY_PASSES = 10              # passages gardés dans `summary.segments`
ME = "me"                        # le cycliste dans `jerseys` (contrat 1.4)


def _contract_rider(rider_id: str | None) -> str | None:
    return ME if rider_id == RIDER_ID else rider_id


@dataclass
class _Pending:
    """Message `segment_result` à envoyer encore `left` fois, la prochaine fois à `at` (s)."""
    msg: dict
    at: float
    left: int


@dataclass
class ClassicRace:
    """Segments, records, bonus, maillots et écarts d'une séance sur un parcours."""

    route_id: str
    segments: tuple
    length_m: float
    loop: bool = False
    rider_mass_kg: float | None = None
    book: RecordBook = field(default_factory=RecordBook)
    table: PowerUpTable | None = None
    powerups_on: bool = True
    seed: int | None = None
    passes: list[dict] = field(default_factory=list)       # passages du cycliste, pour le bilan
    journal: list[dict] = field(default_factory=list)      # lignes à écrire au journal
    book_dirty: bool = False

    def __post_init__(self) -> None:
        segs = list(self.segments)
        self._by_id = {s.id: s for s in segs}
        self.timer = SegmentTimer(segs, self.length_m, self.loop, self.rider_mass_kg)
        self._bot_timers: dict[str, SegmentTimer] = {}
        self._bot_times: dict[tuple[str, int], dict[str, float]] = {}   # (segment, tour) → {bot: temps}
        self.standings = Standings(segs)
        self.gaps = GapTracker(self.length_m, self.loop)
        self.powerups = PowerUps(self.table, seed=self.seed) if self.table else PowerUps(seed=self.seed)
        every = self.powerups.table.arch_every_m if self.powerups_on else 0.0
        self.arches = ArchSchedule(every, self.length_m, self.loop)
        self._prev_s: float | None = None
        self._pending: list[_Pending] = []
        self._gaps_report = None
        self.erg = False

    def start(self, t: float, s: float, bots: Iterable[Any] = ()) -> None:
        """Position de départ du cycliste et des bots : un segment qui commence là est chronométré."""
        self.timer.step(t, s)
        for bot in bots:
            if getattr(bot, "kind", "") != "ghost":
                self._bot_timer(bot.id).step(t, bot.s)
        self._prev_s = s

    def _bot_timer(self, bot_id: str) -> SegmentTimer:
        timer = self._bot_timers.get(bot_id)
        if timer is None:
            timer = self._bot_timers[bot_id] = SegmentTimer(list(self.segments), self.length_m, self.loop)
        return timer

    # --- pas de séance (50 Hz, RUNNING seulement) -----------------------------------------

    def params(self, base: PhysicsParams) -> PhysicsParams:
        """`PhysicsParams` du pas : bonus de masse ou de CdA compris."""
        return self.powerups.params(base) if self.powerups_on else base

    def power(self, measured_w: float) -> float:
        """Puissance prise en compte par la physique (jamais écrite au journal ni au FIT)."""
        return self.powerups.power(measured_w) if self.powerups_on else measured_w

    def set_erg(self, on: bool) -> None:
        self.erg = bool(on)
        self.powerups.set_erg(self.erg)

    def activate(self, t: float) -> bool:
        """Appui court sur Z : active le bonus en réserve."""
        if not self.powerups_on or not self.powerups.activate(t):
            return False
        use = self.powerups.uses[-1]
        self.journal.append({"kind": "powerup", "ts": round(time.time(), 3), "powerup": use.kind,
                             "t": round(use.t_start, 2), "duration_s": round(use.duration_s, 2)})
        return True

    def step(self, t: float, dt: float, s: float, power_w: float, bots: Iterable[Any]) -> None:
        """Un pas de `RUNNING` : `t` temps chronométré, `s` distance cumulée, `power_w` mesurée."""
        if self.powerups_on:
            self.powerups.step(dt)
            if self._prev_s is not None and not self.erg:
                for _ in range(self.arches.crossed(self._prev_s, s)):
                    self.powerups.award("arch")
        self._prev_s = s
        active = self.powerups.active if self.powerups_on else None
        finishes: list[Finish] = []
        mine = self.timer.step(t, s, power_w, active)
        finishes += [Finish(RIDER_ID, p.segment_id, p.lap, p.t_end) for p in mine]
        for bot in bots:
            if getattr(bot, "kind", "") == "ghost":
                continue
            for p in self._bot_timer(bot.id).step(t, bot.s):
                self._bot_times.setdefault((p.segment_id, p.lap), {})[bot.id] = p.time_s
                finishes.append(Finish(bot.id, p.segment_id, p.lap, p.t_end))
        points: dict[tuple[str, int], int] = {}
        for award in self.standings.finish(finishes):
            if award.rider_id == RIDER_ID:
                points[(award.segment_id, award.lap)] = award.points
        for p in mine:
            self._passed(t, p, points.get((p.segment_id, p.lap), 0))

    def _passed(self, t: float, p: SegmentPass, points: int) -> None:
        seg = self._by_id[p.segment_id]
        if self.powerups_on and not self.erg:
            self.powerups.award("segment")
        rows = self.book.ranking(self.route_id, p.segment_id, p,
                                 self._bot_times.get((p.segment_id, p.lap), {}))
        rank = next(i for i, r in enumerate(rows, 1) if r.kind == "you")
        added = self.book.add(self.route_id, p.segment_id, p, datetime.now().strftime(DATE_FORMAT))
        self.book_dirty = True
        msg = {"type": "segment_result", "v": 1, "segment_id": p.segment_id, "name": seg.name[:48],
               "kind": seg.type, "time_s": round(p.time_s, 2), "with_powerup": p.with_bonus,
               "pr": added.is_record, "pr_time_s": None if added.previous_best_s is None
               else round(added.previous_best_s, 2),
               "rank": rank, "rank_total": len(rows), "points": points, "equipment_gain_s": None}
        self._pending.append(_Pending(msg, t, SEGMENT_RESULT_REPEAT))
        self.passes.append({"segment_id": p.segment_id, "kind": seg.type, "time_s": round(p.time_s, 2),
                            "with_powerup": p.with_bonus, "pr": added.is_record, "rank": rank,
                            "rank_total": len(rows), "points": points})
        self.journal.append({"kind": "segment", "ts": round(time.time(), 3), "segment_id": p.segment_id,
                             "lap": p.lap, "type": seg.type, "category": seg.category,
                             "time_s": round(p.time_s, 2), "bonuses": list(p.bonuses), "pr": added.is_record})

    def pause(self, reason: str) -> None:
        """Pause : les passages en cours du cycliste sont annulés (toutes les raisons)."""
        self.timer.pause(reason)
        self._prev_s = None

    def due_results(self, t: float) -> list[dict]:
        """Messages `segment_result` à envoyer maintenant (3 fois, à une seconde d'intervalle)."""
        out: list[dict] = []
        for item in self._pending:
            if t >= item.at:
                out.append(item.msg)
                item.left -= 1
                item.at = t + 1.0
        self._pending = [i for i in self._pending if i.left > 0]
        return out

    # --- trame state (30 Hz) -------------------------------------------------------------

    def frame(self, t: float, s: float, v: float, bots: Iterable[Any]) -> dict[str, Any]:
        """Champs de la révision 1.4 : `segment`, `powerup`, `jerseys`, voisins et ajouts des bots."""
        out: dict[str, Any] = {}
        live = self.timer.live(t, s)
        if live is not None:
            seg = self._by_id[live.segment_id]
            active = live.state == "active"
            gap = None
            if active:
                length = max(seg.s_end - seg.s_start, 1e-9)
                fraction = 1.0 - live.distance_m / length
                gap = self.book.live_gap(self.route_id, seg.id, self.powerups.active is not None,
                                         live.elapsed_s or 0.0, fraction)
            out["segment"] = {
                "id": seg.id, "kind": seg.type, "category": seg.category,
                "d_to_start_m": 0.0 if active else round(live.distance_m, 1),
                "elapsed_s": round(live.elapsed_s, 1) if active and live.elapsed_s is not None else None,
                "gap_to_pr_s": None if gap is None else round(gap, 1)}
        if self.powerups_on and not self.erg:
            pu = self.powerups
            out["powerup"] = {"held": CONTRACT_POWERUP.get(pu.reserve) if pu.reserve else None,
                              "active": CONTRACT_POWERUP.get(pu.active) if pu.active else None,
                              "remaining_s": round(pu.remaining_s, 1) if pu.active else 0.0}
        if self.segments:
            out["jerseys"] = {"sprint": _contract_rider(self.standings.leader("sprint")),
                              "kom": _contract_rider(self.standings.leader("kom"))}
        bots = list(bots)
        if bots:
            report = self.gaps.step(t, (s, v), {b.id: (b.s, b.v) for b in bots})
            out["bot_ahead"], out["bot_behind"] = report.bot_ahead, report.bot_behind
            sprint, kom = self.standings.leader("sprint"), self.standings.leader("kom")
            out["bots_extra"] = {
                b.id: {"jersey": "sprint" if sprint == b.id else ("kom" if kom == b.id else None),
                       "gap_s": round(report.gaps[b.id].gap_s, 1)} for b in bots}
        return out

    # --- fin de séance -------------------------------------------------------------------

    def summary(self) -> dict[str, Any] | None:
        """`summary.segments` : 10 derniers passages, `more`, porteurs des maillots."""
        if not self.segments:
            return None
        return {"passes": self.passes[-SUMMARY_PASSES:], "more": len(self.passes) > SUMMARY_PASSES,
                "jerseys": {"sprint": _contract_rider(self.standings.leader("sprint")),
                            "kom": _contract_rider(self.standings.leader("kom"))}}

    def jersey_lines(self) -> list[dict]:
        """Lignes `jersey` du journal : maillots portés par le cycliste à la fin (lues par V5)."""
        ts = round(time.time(), 3)
        return [{"kind": "jersey", "ts": ts, "jersey": j} for j in ("sprint", "kom")
                if self.standings.leader(j) == RIDER_ID]

    def take_journal(self) -> list[dict]:
        lines, self.journal = self.journal, []
        return lines
