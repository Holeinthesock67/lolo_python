"""Socle commun des épreuves de piste (lot VD6, série VD) : coureurs, tours, cloche, journal, bilan.

Module pur, sans entrée-sortie : la séance donne à chaque pas l'instant chronométré `t` de la séance
(il ne bouge pas en pause : l'épreuve est figée) et, pour chaque coureur, sa distance cumulée `s`
sur la piste et sa vitesse `v` (`positions` = id → (s, v), le cycliste sous l'id `me`). La ligne
d'arrivée est à `line_s` modulo le tour (0 sur la piste de 250 m, `velodrome.build_venue`).

Interface commune de toutes les épreuves :

    ev.start(t, positions)            # départ (arrêté ou lancé : les coureurs roulent déjà ou non)
    messages = ev.step(t, positions)  # un pas en RUNNING ; rend les faits du pas (tour, cloche, arrivée…)
    ev.frame()                        # objet `track` de la trame `state` (plan §7.1)
    ev.summary()                      # bilan ; ev.take_journal() : lignes `track` du journal

Aucune épreuve ne touche à la pente : la piste est plate dans le sens de la marche, la séance garde
la pente du parcours (test `test_track_events`).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

ME = "me"                       # le cycliste, comme dans `survivor` et `jerseys`
LAP_M = 250.0                   # piste de référence (plan §3.1)
TIE_S = 0.001                   # écart de passage sous lequel deux coureurs sont à égalité
FINISH_GRACE_S = 60.0           # après la première arrivée, les retardataires ont une minute
RANKING_MAX = 12                # classement de la trame : 12 coureurs au plus (peloton PL1)

Positions = Mapping[str, tuple[float, float]]


class TrackError(ValueError):
    """Réglage d'épreuve refusé (plateau, distance, tours) ou appel hors d'ordre."""


@dataclass(frozen=True)
class Entrant:
    """Un engagé : identifiant, nom affiché, équipe (épreuves par équipes) et niveau (départage)."""
    id: str
    name: str
    team: str | None = None
    level: float = 0.0


@dataclass
class Rider:
    id: str
    name: str
    team: str | None
    level: float
    s: float = 0.0               # distance cumulée sur la piste
    v: float = 0.0
    start_s: float = 0.0         # distance au départ de l'épreuve
    out: str | None = None       # raison de la sortie (éliminé, déclassé, lâché, écarté)
    out_t: float | None = None

    @property
    def d(self) -> float:
        """Distance parcourue depuis son départ."""
        return self.s - self.start_s


def cross_time(t0: float, d0: float, t1: float, d1: float, mark: float) -> float:
    """Instant interpolé du passage de `mark` entre deux pas (d0 < mark ≤ d1)."""
    if d1 <= d0:
        return t1
    return t0 + (t1 - t0) * (mark - d0) / (d1 - d0)


def lines_crossed(d0: float, d1: float, period: float, offset: float = 0.0) -> list[float]:
    """Repères `offset + k × period` franchis entre d0 (exclu) et d1 (inclus)."""
    if d1 <= d0:
        return []
    k0 = math.floor((d0 - offset) / period) + 1
    k1 = math.floor((d1 - offset) / period + 1e-9)
    return [offset + k * period for k in range(k0, k1 + 1)]


def place_points(place: int) -> int:
    """Points de place de l'omnium : 40 au premier, 2 de moins par place, 1 au moins."""
    return max(40 - 2 * (place - 1), 1)


class TrackEvent:
    """Épreuve de piste : socle commun. Les sous-classes écrivent `_on_start`, `_advance`, `_ranking`."""

    event_id = ""
    record_id: str | None = None          # table de records de l'épreuve (None : pas de record)
    min_riders = 1
    max_riders = 12

    def __init__(self, entrants: Sequence[Entrant], *, lap_m: float = LAP_M, line_s: float = 0.0,
                 seed: int = 0, clock: Callable[[], float] | None = None) -> None:
        if not math.isfinite(lap_m) or lap_m <= 0:
            raise TrackError(f"longueur du tour : {lap_m!r} refusée")
        ids = [e.id for e in entrants]
        if len(set(ids)) != len(ids):
            raise TrackError("identifiant en double")
        if ME not in ids:
            raise TrackError("le cycliste (« me ») doit être engagé")
        if not self.min_riders <= len(ids) <= self.max_riders:
            raise TrackError(f"{self.event_id} : {len(ids)} coureurs refusés ({self.min_riders} à {self.max_riders})")
        self.lap_m = float(lap_m)
        self.line_s = float(line_s)
        self.seed = seed
        self.clock = clock if clock is not None else (lambda: time.time())   # horloge lue à chaque ligne
        self.riders: dict[str, Rider] = {e.id: Rider(e.id, e.name, e.team, float(e.level)) for e in entrants}
        self.t0: float | None = None
        self.t: float = 0.0
        self.end_t: float | None = None
        self.journal: list[dict] = []
        self._msgs: list[dict] = []
        self._prev: dict[str, tuple[float, float]] = {}   # id → (t, s) au pas précédent
        # tours du cycliste sur la ligne d'arrivée (journal, FIT, tableau des tours)
        self.my_laps: list[float] = []
        self._my_line_t: float | None = None
        self._my_line_seen = False

    # --- état ---

    @property
    def started(self) -> bool:
        return self.t0 is not None

    @property
    def finished(self) -> bool:
        return self.end_t is not None

    @property
    def elapsed_s(self) -> float:
        return 0.0 if self.t0 is None else (self.end_t if self.end_t is not None else self.t) - self.t0

    def racing(self) -> list[Rider]:
        """Coureurs encore en course."""
        return [r for r in self.riders.values() if r.out is None]

    # --- pas ---

    def start(self, t: float, positions: Positions) -> None:
        if self.started:
            raise TrackError("épreuve déjà partie")
        self.t0 = self.t = float(t)
        for rid, r in self.riders.items():
            s, v = positions.get(rid, (0.0, 0.0))
            r.s = r.start_s = float(s)
            r.v = float(v)
            self._prev[rid] = (self.t, r.s)
        self._my_line_t = self.t
        self._on_start(self.t)
        self._emit("start", riders=len(self.riders))

    def step(self, t: float, positions: Positions) -> list[dict]:
        """Un pas de séance en RUNNING. Un instant qui n'avance pas (pause) ne change rien."""
        if not self.started:
            raise TrackError("step avant start")
        t = float(t)
        if self.finished or t <= self.t:
            return []
        t_prev = self.t
        for rid, (s, v) in positions.items():
            r = self.riders.get(rid)
            if r is None:
                continue
            self._prev[rid] = (t_prev, r.s)
            r.s, r.v = float(s), float(v)
        self.t = t
        self._my_line(t_prev, t)
        self._advance(t_prev, t)
        out, self._msgs = self._msgs, []
        return out

    def _my_line(self, t0: float, t1: float) -> None:
        """Tours du cycliste sur la ligne d'arrivée ; le premier passage à moins d'un demi-tour du départ
        (grille derrière la ligne) ouvre le premier tour sans en compter un."""
        me = self.riders[ME]
        s0 = self._prev[ME][1]
        for mark in lines_crossed(s0, me.s, self.lap_m, self.line_s):
            tc = cross_time(t0, s0, t1, me.s, mark)
            if not self._my_line_seen and mark - me.start_s < self.lap_m / 2:
                self._my_line_seen = True
                self._my_line_t = tc
                continue
            self._my_line_seen = True
            lap_s = tc - (self._my_line_t if self._my_line_t is not None else self.t0 or tc)
            self._my_line_t = tc
            self.my_laps.append(lap_s)
            self._emit("lap", rider=ME, lap=len(self.my_laps), lap_s=round(lap_s, 3))

    def _emit(self, kind: str, **data) -> None:
        msg = {"event": kind, **data}
        self._msgs.append(msg)
        self.journal.append({"kind": "track", "ts": round(self.clock(), 3), "t": round(self.t, 3),
                             "track": self.event_id, **msg})

    def _out(self, r: Rider, reason: str, t: float) -> None:
        if r.out is None:
            r.out, r.out_t = reason, t
            self._emit("out", rider=r.id, reason=reason)

    def _end(self, t: float) -> None:
        if self.end_t is None:
            self.end_t = t
            ranking = self._ranking()
            self._emit("finish", winner=ranking[0] if ranking else None,
                       place=ranking.index(ME) + 1 if ME in ranking else None)

    # --- à écrire par épreuve ---

    def _on_start(self, t: float) -> None:
        pass

    def _advance(self, t0: float, t1: float) -> None:
        raise NotImplementedError

    def _ranking(self) -> list[str]:
        """Identifiants du premier au dernier (coureurs, ou équipes pour les épreuves par équipes)."""
        raise NotImplementedError

    def _frame_extra(self) -> dict:
        return {}

    def _summary_extra(self) -> dict:
        return {}

    def lap_info(self) -> tuple[int | None, int | None]:
        """(tour en cours du cycliste, tours de l'épreuve) ; None quand l'épreuve n'en compte pas."""
        return len(self.my_laps) + 1, None

    def points(self) -> dict[str, int] | None:
        return None

    def bell(self) -> bool:
        return False

    def record(self) -> dict | None:
        """Résultat chronométré du cycliste pour les records (table, temps, distance) ; None sinon."""
        return None

    # --- trame, journal, bilan ---

    def frame(self) -> dict:
        """Objet `track` de la trame `state` : épreuve, tour, tours restants, cloche, classement, points (dans
        l'ordre du classement), éliminés (plan §7.1), et les champs propres à l'épreuve."""
        lap, laps = self.lap_info()
        pts = self.points()
        ranking = self._ranking()[:RANKING_MAX]
        out = {"event": self.event_id, "t_s": round(self.elapsed_s, 2),
               "lap": lap, "laps": laps,
               "laps_to_go": None if laps is None or lap is None else max(laps - lap + 1, 0),
               "bell": self.bell(), "ranking": ranking,
               "points": None if pts is None else [pts.get(k, 0) for k in ranking],
               "eliminated": [r.id for r in sorted(self.riders.values(), key=lambda r: (r.out_t or 0.0, r.id))
                              if r.out is not None],
               "finished": self.finished}
        out.update(self._frame_extra())
        return out

    def take_journal(self) -> list[dict]:
        lines, self.journal = self.journal, []
        return lines

    def summary(self) -> dict:
        ranking = self._ranking()
        me = self.riders[ME]
        key = me.team if me.team is not None and me.team in ranking else ME
        out = {"event": self.event_id, "place": ranking.index(key) + 1 if key in ranking else None,
               "of": len(ranking), "ranking": ranking[:RANKING_MAX],
               "names": {r.id: r.name[:16] for r in self.riders.values()},
               "elapsed_s": round(self.elapsed_s, 3), "laps": [round(x, 3) for x in self.my_laps],
               "best_lap_s": round(min(self.my_laps), 3) if self.my_laps else None,
               "finished": self.finished, "record": self.record()}
        pts = self.points()
        if pts is not None:
            out["points"] = [pts.get(k, 0) for k in ranking[:RANKING_MAX]]
        out.update(self._summary_extra())
        return out
