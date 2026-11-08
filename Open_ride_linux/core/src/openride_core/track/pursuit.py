"""Poursuites (lot VD6) : poursuite individuelle, et le socle des épreuves par équipes de départ arrêté.

Deux équipes (ou deux coureurs) partent arrêtées de part et d'autre de la piste (lignes de poursuite,
un demi-tour d'écart : la séance place les coureurs). Chaque coureur compte sa distance depuis son
départ. Une équipe est chronométrée au passage de son `count`-ième coureur sur la distance ; elle est
rejointe quand l'autre lui reprend un demi-tour (même mesure), et l'épreuve s'arrête alors.

Relais (épreuves par équipes) tous les `relay_m` de l'équipe : `rotate`, le meneur remonte et se
replace en dernière position (poursuite par équipes) ; `leave`, il s'écarte et sort du chrono (vitesse
par équipes). Poursuite par équipes : un coureur à plus de `DROP_M` du coureur chronométré est lâché
(jamais les `count` premiers : le chrono attend le 3e).
"""

from __future__ import annotations

from .base import ME, Entrant, Rider, TrackError, TrackEvent, cross_time

DISTANCES_M = (3000.0, 4000.0)
DROP_M = 30.0


class _Team:
    def __init__(self, tid: str, members: list[str]) -> None:
        self.id = tid
        self.order = list(members)       # meneur en tête
        self.crossed: dict[str, float] = {}
        self.time_t: float | None = None  # instant du chrono de l'équipe
        self.next_relay = 1
        self.status = "racing"            # racing, finished, caught


class Pursuit(TrackEvent):
    event_id = "pursuit"
    max_riders = 2
    team_size = 1
    count = 1
    relay_mode: str | None = None

    def __init__(self, entrants: list[Entrant], distance_m: float = 4000.0, relay_m: float | None = None,
                 **kw) -> None:
        super().__init__(entrants, **kw)
        self.distance_m = float(distance_m)
        self.relay_m = None if relay_m is None else float(relay_m)
        self._check_distance()
        groups: dict[str, list[str]] = {}
        for e in entrants:
            groups.setdefault(e.team if self.team_size > 1 else e.id, []).append(e.id)
        if len(groups) > 2:
            raise TrackError(f"{self.event_id} : deux équipes au plus")
        for tid, members in groups.items():
            if len(members) != self.team_size:
                raise TrackError(f"{self.event_id} : équipe {tid} de {len(members)} coureurs ({self.team_size} attendus)")
        self.teams = {tid: _Team(tid, m) for tid, m in groups.items()}
        self.mine = self._team_of(ME)
        self.winner: str | None = None
        self.record_id = self._record_id()

    def _check_distance(self) -> None:
        if self.distance_m not in DISTANCES_M:
            raise TrackError(f"poursuite : {self.distance_m:g} m refusés (3 000 ou 4 000 m)")

    def _record_id(self) -> str:
        return f"track:pursuit_{int(self.distance_m)}"

    def _team_of(self, rid: str) -> str:
        r = self.riders[rid]
        return r.team if self.team_size > 1 and r.team is not None else rid

    # --- mesure d'une équipe ---

    def _timed(self, team: _Team) -> list[Rider]:
        """Coureurs qui comptent encore pour le chrono, du plus avancé au moins avancé."""
        return sorted((self.riders[i] for i in team.order if self.riders[i].out is None),
                      key=lambda r: -r.d)

    def team_d(self, team: _Team) -> float:
        """Distance de l'équipe : celle de son coureur chronométré (le `count`-ième)."""
        timed = self._timed(team)
        if not timed:
            return 0.0
        return timed[min(self.count, len(timed)) - 1].d

    # --- pas ---

    def _advance(self, t0: float, t1: float) -> None:
        for team in self.teams.values():
            if team.status != "racing":
                continue
            self._relays(team, t1)
            for rid in team.order:
                r = self.riders[rid]
                if r.out is not None or rid in team.crossed:
                    continue
                d0 = self._prev[rid][1] - r.start_s
                if d0 < self.distance_m <= r.d:
                    team.crossed[rid] = cross_time(t0, d0, t1, r.d, self.distance_m)
            self._drops(team, t1)
            if len(team.crossed) >= self.count:
                team.time_t = sorted(team.crossed.values())[self.count - 1]
                team.status = "finished"
                self._emit("result", team=team.id, time_s=round(team.time_t - (self.t0 or 0.0), 3))
        self._catch(t1)
        if all(tm.status != "racing" for tm in self.teams.values()) and not self.finished:
            done = [tm for tm in self.teams.values() if tm.status == "finished"]
            if self.winner is None and done:
                self.winner = min(done, key=lambda tm: tm.time_t or 0.0).id
            self._end(max((tm.time_t for tm in done if tm.time_t is not None), default=t1))

    def _relays(self, team: _Team, t: float) -> None:
        if self.relay_m is None or self.relay_mode is None:
            return
        racing = [i for i in team.order if self.riders[i].out is None]
        if not racing:
            return
        lead = self.riders[racing[0]]
        while lead.d >= team.next_relay * self.relay_m and len(racing) > 1:
            team.next_relay += 1
            if self.relay_mode == "rotate":
                team.order.remove(lead.id)
                team.order.append(lead.id)
            else:
                self._out(lead, "swing", t)
            racing = [i for i in team.order if self.riders[i].out is None]
            self._emit("relay", team=team.id, rider=lead.id, lead=racing[0])
            lead = self.riders[racing[0]]

    def _drops(self, team: _Team, t: float) -> None:
        if self.relay_mode != "rotate":
            return
        timed = self._timed(team)
        if len(timed) <= self.count:
            return
        ref = timed[self.count - 1].d
        for r in timed[self.count:]:
            if r.id not in team.crossed and ref - r.d > DROP_M:
                self._out(r, "dropped", t)

    def _catch(self, t: float) -> None:
        racing = [tm for tm in self.teams.values() if tm.status == "racing"]
        if len(self.teams) != 2 or len(racing) != 2:
            return
        a, b = racing
        gap = self.team_d(a) - self.team_d(b)
        if abs(gap) >= self.lap_m / 2:
            front, back = (a, b) if gap > 0 else (b, a)
            back.status = "caught"
            front.status = "finished"
            self.winner = front.id
            self._emit("caught", team=back.id, by=front.id)
            self._end(t)

    # --- classement ---

    def _ranking(self) -> list[str]:
        rank = {"finished": 0, "racing": 1, "caught": 2}

        def key(tm: _Team) -> tuple:
            return (0 if tm.id == self.winner else 1, rank[tm.status], tm.time_t if tm.time_t is not None else 0.0,
                    -self.team_d(tm), tm.id)
        return [tm.id for tm in sorted(self.teams.values(), key=key)]

    def lap_info(self) -> tuple[int | None, int | None]:
        laps = int(round(self.distance_m / self.lap_m))
        d = max(self.team_d(self.teams[self.mine]), 0.0)
        return min(int(d // self.lap_m) + 1, laps), laps

    def bell(self) -> bool:
        lap, laps = self.lap_info()
        return lap is not None and lap == laps and not self.finished

    def team_time_s(self, tid: str) -> float | None:
        tm = self.teams[tid]
        return None if tm.time_t is None or tm.status != "finished" else tm.time_t - (self.t0 or 0.0)

    def _frame_extra(self) -> dict:
        mine = self.teams[self.mine]
        d = self.team_d(mine)
        out: dict = {"d_m": round(max(d, 0.0), 1), "to_go_m": round(max(self.distance_m - d, 0.0), 1),
                     "gap_m": None, "gap_s": None, "lead": None}
        others = [tm for tm in self.teams.values() if tm.id != self.mine]
        if others:
            gap = d - self.team_d(others[0])
            out["gap_m"] = round(gap, 1)
            v = max(self.riders[ME].v, 1.0)
            out["gap_s"] = round(gap / v, 2)
        if self.team_size > 1:
            racing = [i for i in mine.order if self.riders[i].out is None]
            out["lead"] = racing[0] if racing else None
            out["order"] = racing
        return out

    def record(self) -> dict | None:
        t = self.team_time_s(self.mine)
        if t is None:
            return None
        return {"id": self.record_id, "time_s": round(t, 3), "distance_m": self.distance_m}

    def _summary_extra(self) -> dict:
        return {"distance_m": self.distance_m, "winner": self.winner,
                "times_s": {tid: (None if self.team_time_s(tid) is None else round(self.team_time_s(tid), 3))
                            for tid in self.teams},
                "status": {tid: tm.status for tid, tm in self.teams.items()}}
