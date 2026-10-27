"""Chronométrage des segments (sprints et montées) pendant une séance (lot T4, série T).

Module pur : la séance (ou le rejeu d'un journal) appelle `SegmentTimer.step` à chaque pas
de physique pendant `RUNNING`, avec le temps chronométré `t` et la distance cumulée `s`
(celle de `RiderPhysics`, qui ne reboucle pas : sur une boucle, le tour k commence à k × L).
Cahier : `docs/lots/LOT_T4_chronometrage_segments.md`.

Règles (plan de la série T §3.2) :
- l'entrée et la sortie sont interpolées linéairement entre deux pas : à 50 Hz et 10 m/s,
  l'erreur reste sous 0,02 s ;
- une pause pendant un segment l'annule, quelle qu'en soit la raison (`trainer_lost` aussi) ;
- boucle : chaque tour donne un passage ; aller-retour : `s` ne fait que croître, le segment
  ne se chronomètre donc que dans le sens où il a été défini ;
- chaque passage garde temps, puissance moyenne (mesurée), W/kg, vitesse moyenne et bonus
  utilisés ; il se relit depuis le journal des séances (`passes_from_journal`).

Les segments sont lus par attributs (`id`, `name`, `type`, `s_start`, `s_end`) : un
`segments.Segment` (lot T2) convient, comme tout objet de même forme.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Protocol

from .journal import read_journal

TIMER_STEP_S = 0.02     # pas de 50 Hz de la boucle du core


class SegmentLike(Protocol):
    id: str
    name: str
    type: str
    s_start: float
    s_end: float


@dataclass(frozen=True)
class SegmentPass:
    segment_id: str
    lap: int                    # 0 pour un parcours ouvert ou le premier tour
    t_start: float              # temps chronométré de la séance à l'entrée (s)
    t_end: float
    time_s: float
    avg_power_w: float          # puissance mesurée (jamais la puissance bonifiée)
    avg_wkg: float | None       # None sans masse du cycliste
    avg_speed_kmh: float
    bonuses: tuple[str, ...]    # bonus actifs pendant le passage (ordre d'apparition)

    @property
    def with_bonus(self) -> bool:
        return bool(self.bonuses)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bonuses"] = list(self.bonuses)
        for k in ("t_start", "t_end"):
            d[k] = round(d[k], 3)
        d["time_s"] = round(d["time_s"], 2)
        d["avg_power_w"] = round(d["avg_power_w"], 1)
        d["avg_speed_kmh"] = round(d["avg_speed_kmh"], 2)
        if d["avg_wkg"] is not None:
            d["avg_wkg"] = round(d["avg_wkg"], 2)
        return d


@dataclass
class _Active:
    seg: SegmentLike
    lap: int
    s0: float                   # abscisse cumulée de l'entrée
    s1: float                   # abscisse cumulée de la sortie
    t_start: float
    energy_j: float = 0.0
    bonuses: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LiveSegment:
    """Ce que le HUD affiche : segment en cours ou prochain."""
    segment_id: str
    name: str
    type: str
    state: str                  # "approach" (prochain) ou "active" (en cours)
    distance_m: float           # jusqu'au départ (approche) ou jusqu'à l'arrivée (en cours)
    elapsed_s: float | None     # chrono du passage en cours, None en approche


def _interp_t(t0: float, s0: float, t1: float, s1: float, s: float) -> float:
    if s1 <= s0:
        return t1
    return t0 + (t1 - t0) * (s - s0) / (s1 - s0)


class SegmentTimer:
    """Chronomètre tous les segments d'un parcours, plusieurs à la fois s'ils se chevauchent."""

    def __init__(self, segments: Iterable[SegmentLike], length_m: float, loop: bool = False,
                 rider_mass_kg: float | None = None) -> None:
        self.segments = sorted(segments, key=lambda seg: seg.s_start)
        for seg in self.segments:
            if not 0.0 <= seg.s_start < seg.s_end <= length_m + 0.01:
                raise ValueError(f"segment {seg.id} hors du parcours : {seg.s_start}–{seg.s_end}")
        self.length_m = float(length_m)
        self.loop = loop
        self.rider_mass_kg = rider_mass_kg
        self._prev: tuple[float, float] | None = None    # (t, s) du pas précédent
        self._active: list[_Active] = []
        self.passes: list[SegmentPass] = []
        self.cancelled: list[tuple[str, int, str]] = []   # (segment, tour, raison)
        self._fresh = True   # premier pas de la séance : un départ en s = 0 compte

    # --- pas de séance -------------------------------------------------------------------

    def _laps_crossed(self, s_lo: float, s_hi: float, point: float) -> Iterator[int]:
        """Tours k tels que k × L + point soit franchi dans ]s_lo, s_hi]."""
        if self._fresh and s_lo == point:
            yield 0
            if not self.loop:
                return
        if not self.loop:
            if s_lo < point <= s_hi:
                yield 0
            return
        L = self.length_m
        k = int((s_lo - point) // L) + 1
        while k * L + point <= s_hi:
            if k >= 0 and k * L + point > s_lo:
                yield k
            k += 1

    def step(self, t: float, s: float, power_w: float | None = None,
             bonus: str | None = None) -> list[SegmentPass]:
        """Un pas de `RUNNING` ; rend les passages terminés pendant ce pas."""
        done: list[SegmentPass] = []
        prev = self._prev
        self._prev = (t, s)
        if prev is None:
            return done
        t0, s0 = prev
        if s <= s0 or t < t0:
            return done
        dt = t - t0
        p = max(float(power_w or 0.0), 0.0)

        # Sorties d'abord (énergie jusqu'à l'instant interpolé), puis entrées.
        still: list[_Active] = []
        for a in self._active:
            if s >= a.s1:
                t_out = _interp_t(t0, s0, t, s, a.s1)
                a.energy_j += p * (t_out - t0)
                if bonus and bonus not in a.bonuses:
                    a.bonuses.append(bonus)
                done.append(self._close(a, t_out))
            else:
                a.energy_j += p * dt
                if bonus and bonus not in a.bonuses:
                    a.bonuses.append(bonus)
                still.append(a)
        self._active = still

        crossed = [(seg, lap) for seg in self.segments for lap in self._laps_crossed(s0, s, seg.s_start)]
        self._fresh = False
        for seg, lap in crossed:
            base = lap * self.length_m
            t_in = _interp_t(t0, s0, t, s, base + seg.s_start)
            a = _Active(seg=seg, lap=lap, s0=base + seg.s_start, s1=base + seg.s_end,
                        t_start=t_in)
            if bonus:
                a.bonuses.append(bonus)
            if s >= a.s1:   # segment entier franchi pendant le pas (cas limite)
                t_out = _interp_t(t0, s0, t, s, a.s1)
                a.energy_j = p * (t_out - t_in)
                done.append(self._close(a, t_out))
            else:
                a.energy_j = p * (t - t_in)
                self._active.append(a)
        self.passes.extend(done)
        return done

    def _close(self, a: _Active, t_out: float) -> SegmentPass:
        time_s = max(t_out - a.t_start, 1e-9)
        avg_p = a.energy_j / time_s
        mass = self.rider_mass_kg
        return SegmentPass(
            segment_id=a.seg.id, lap=a.lap, t_start=a.t_start, t_end=t_out, time_s=time_s,
            avg_power_w=avg_p, avg_wkg=avg_p / mass if mass else None,
            avg_speed_kmh=3.6 * (a.s1 - a.s0) / time_s, bonuses=tuple(a.bonuses))

    def pause(self, reason: str = "user") -> None:
        """Pause de la séance : les passages en cours sont annulés."""
        for a in self._active:
            self.cancelled.append((a.seg.id, a.lap, reason))
        self._active = []
        self._prev = None    # la reprise ne doit pas faire croire à un franchissement

    # --- affichage -----------------------------------------------------------------------

    def live(self, t: float, s: float) -> LiveSegment | None:
        """Segment en cours (le dernier entré) ou, à défaut, le prochain départ."""
        if self._active:
            a = self._active[-1]
            return LiveSegment(a.seg.id, a.seg.name, a.seg.type, "active",
                               max(a.s1 - s, 0.0), max(t - a.t_start, 0.0))
        best: tuple[float, SegmentLike] | None = None
        for seg in self.segments:
            start = seg.s_start
            if self.loop:
                L = self.length_m
                start = (s // L) * L + seg.s_start
                if start <= s:
                    start += L
            if start <= s:
                continue
            if best is None or start - s < best[0]:
                best = (start - s, seg)
        if best is None:
            return None
        return LiveSegment(best[1].id, best[1].name, best[1].type, "approach", best[0], None)


def passes_from_journal(path: Path, segments: Iterable[SegmentLike], length_m: float,
                        loop: bool = False, rider_mass_kg: float | None = None) -> list[SegmentPass]:
    """Rejoue un journal `.jsonl` (relevés à 1 Hz, événements de pause) et rend ses passages.

    Le journal ne note pas les bonus : `bonuses` est vide à la relecture (T6 les ajoutera).
    """
    timer = SegmentTimer(segments, length_m, loop, rider_mass_kg)
    for line in read_journal(path):
        kind = line.get("kind")
        if kind == "event" and line.get("event") == "pause":
            timer.pause("journal")
        elif kind == "record":
            try:
                t, s = float(line["t"]), float(line["distance"])
            except (KeyError, TypeError, ValueError):
                continue
            timer.step(t, s, line.get("power"))
    return timer.passes
