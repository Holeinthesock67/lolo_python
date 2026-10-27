"""Détection automatique des montées et des sprints d'un parcours (lot T2, série T).

Module pur : il ne lit que le profil de la couche route (abscisses `s`, altitude `alt_m`,
pente lissée `grade_pct`, celle que la route utilise déjà) et rend une liste de `Segment`.
La couche `segments` du `.world` (T1, T3), le chronométrage (T4) et les points des maillots
(T14) s'appuient dessus. Cahier : `docs/lots/LOT_T2_detection_segments.md`.

Règles (plan de la série T §3.1) :
- montée : au moins 500 m, pente moyenne d'au moins 3 %, gain d'au moins 30 m ; les montées
  séparées par moins de 200 m de replat sont fusionnées ; catégorie 4 à HC selon le produit
  longueur (m) × pente moyenne (%) ;
- sprint proposé : tronçon de 200 à 500 m dont toute la pente est entre −1 et +2 %, hors
  montée, au plus un tous les 10 km ;
- segments manuels : ajoutés aux automatiques ou à leur place (`merge_manual`).
"""

from __future__ import annotations

import bisect
from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

# --- montées -------------------------------------------------------------------------------
CLIMB_POINT_GRADE_PCT = 1.5      # un point « monte » à partir de cette pente lissée
CLIMB_MIN_LENGTH_M = 500.0
CLIMB_MIN_AVG_GRADE_PCT = 3.0
CLIMB_MIN_GAIN_M = 30.0
CLIMB_MERGE_GAP_M = 200.0        # replat au-dessous duquel deux montées sont fusionnées

# Seuils de catégorie sur longueur (m) × pente moyenne (%), du plus dur au plus facile.
# Toute montée retenue est au moins de 4e catégorie.
CATEGORY_THRESHOLDS: tuple[tuple[str, float], ...] = (
    ("HC", 80_000.0),
    ("1", 64_000.0),
    ("2", 32_000.0),
    ("3", 16_000.0),
)
CATEGORY_FLOOR = "4"

# --- sprints proposés ----------------------------------------------------------------------
SPRINT_MIN_GRADE_PCT = -1.0
SPRINT_MAX_GRADE_PCT = 2.0
SPRINT_MIN_LENGTH_M = 200.0
SPRINT_MAX_LENGTH_M = 500.0
SPRINT_SPACING_M = 10_000.0      # au plus un sprint proposé tous les 10 km (entre deux débuts)
SPRINT_MIN_START_M = 1_000.0     # pas de sprint proposé dans le premier kilomètre
SPRINT_CLIMB_CLEARANCE_M = 200.0  # écart minimal entre un sprint proposé et une montée

SEGMENT_TYPES = ("sprint", "climb")
SEGMENT_SOURCES = ("auto", "manual")
MERGE_MODES = ("add", "replace")


class SegmentError(ValueError):
    """Profil ou segment manuel invalide."""


@dataclass(frozen=True)
class Segment:
    id: str
    name: str
    type: str                  # "sprint" ou "climb"
    s_start: float             # m, abscisse curviligne de la route
    s_end: float
    length_m: float
    avg_grade_pct: float
    gain_m: float              # dénivelé entre le début et la fin (négatif en descente)
    category: str | None       # "4", "3", "2", "1", "HC" pour une montée ; None pour un sprint
    source: str                # "auto" ou "manual"

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("s_start", "s_end", "length_m", "gain_m"):
            d[k] = round(d[k], 1)
        d["avg_grade_pct"] = round(d["avg_grade_pct"], 2)
        return d


def climb_category(length_m: float, avg_grade_pct: float) -> str:
    """Catégorie d'une montée (4 à HC) selon longueur × pente moyenne."""
    score = length_m * avg_grade_pct
    for cat, threshold in CATEGORY_THRESHOLDS:
        if score >= threshold:
            return cat
    return CATEGORY_FLOOR


class Profile:
    """Profil (s, altitude, pente) lu sur une couche route, avec interpolation linéaire."""

    def __init__(self, s: Sequence[float], alt_m: Sequence[float],
                 grade_pct: Sequence[float]) -> None:
        if not (len(s) == len(alt_m) == len(grade_pct)) or len(s) < 2:
            raise SegmentError("profil incomplet : il faut au moins 2 points de même longueur")
        if any(b <= a for a, b in zip(s, s[1:])):
            raise SegmentError("abscisses du profil non strictement croissantes")
        self.s = [float(v) for v in s]
        self.alt = [float(v) for v in alt_m]
        self.grade = [float(v) for v in grade_pct]
        self.length_m = self.s[-1]

    @classmethod
    def from_route(cls, route) -> "Profile":
        """Profil d'un `route.Route` (ou de tout objet ayant `s`, `alt_m`, `grade_pct`)."""
        return cls(route.s, route.alt_m, route.grade_pct)

    def alt_at(self, s: float) -> float:
        s = min(max(s, self.s[0]), self.s[-1])
        i = min(max(bisect.bisect_right(self.s, s) - 1, 0), len(self.s) - 2)
        u = (s - self.s[i]) / (self.s[i + 1] - self.s[i])
        return self.alt[i] + (self.alt[i + 1] - self.alt[i]) * u


def _runs(flags: Sequence[bool]) -> list[tuple[int, int]]:
    """Plages [i, j] (indices de points inclus) où `flags` est vrai."""
    out: list[tuple[int, int]] = []
    start = None
    for i, f in enumerate(flags):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(flags) - 1))
    return out


def _climb_stats(p: Profile, s0: float, s1: float) -> tuple[float, float, float]:
    length = s1 - s0
    gain = p.alt_at(s1) - p.alt_at(s0)
    avg = 100.0 * gain / length if length > 0 else 0.0
    return length, gain, avg


def _qualifies(p: Profile, s0: float, s1: float) -> bool:
    length, gain, avg = _climb_stats(p, s0, s1)
    return (length >= CLIMB_MIN_LENGTH_M and gain >= CLIMB_MIN_GAIN_M
            and avg >= CLIMB_MIN_AVG_GRADE_PCT)


def detect_climbs(p: Profile) -> list[tuple[float, float]]:
    """Intervalles [s_début, s_fin] des montées retenues, dans l'ordre du parcours."""
    runs = [(p.s[i], p.s[j]) for i, j in _runs([g >= CLIMB_POINT_GRADE_PCT for g in p.grade])
            if j > i]
    # Groupes de plages séparées par moins de CLIMB_MERGE_GAP_M.
    groups: list[list[tuple[float, float]]] = []
    for r in runs:
        if groups and r[0] - groups[-1][-1][1] < CLIMB_MERGE_GAP_M:
            groups[-1].append(r)
        else:
            groups.append([r])

    climbs: list[tuple[float, float]] = []
    for group in groups:
        s0, s1 = group[0][0], group[-1][1]
        if _qualifies(p, s0, s1):
            climbs.append((s0, s1))
            continue
        # La fusion a fait chuter la moyenne : on garde les morceaux qui tiennent seuls,
        # en refusionnant les voisins qui restent ensemble au-dessus des seuils.
        pending: tuple[float, float] | None = None
        for r in group:
            if pending is not None and _qualifies(p, pending[0], r[1]):
                pending = (pending[0], r[1])
                continue
            if pending is not None and _qualifies(p, *pending):
                climbs.append(pending)
            pending = r
        if pending is not None and _qualifies(p, *pending):
            climbs.append(pending)
    return climbs


def _subtract(lo: float, hi: float, holes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Morceaux de [lo, hi] hors des intervalles `holes` (triés)."""
    pieces = [(lo, hi)]
    for h0, h1 in holes:
        nxt = []
        for a, b in pieces:
            if h1 <= a or h0 >= b:
                nxt.append((a, b))
                continue
            if h0 > a:
                nxt.append((a, h0))
            if h1 < b:
                nxt.append((h1, b))
        pieces = nxt
    return pieces


def detect_sprints(p: Profile, climbs: Iterable[tuple[float, float]] = ()) -> list[tuple[float, float]]:
    """Sprints proposés : fin de chaque replat assez long, au plus un tous les 10 km."""
    holes = sorted((c0 - SPRINT_CLIMB_CLEARANCE_M, c1 + SPRINT_CLIMB_CLEARANCE_M)
                   for c0, c1 in climbs)
    holes.insert(0, (float("-inf"), SPRINT_MIN_START_M))
    flat = [SPRINT_MIN_GRADE_PCT <= g <= SPRINT_MAX_GRADE_PCT for g in p.grade]
    candidates: list[tuple[float, float]] = []
    for i, j in _runs(flat):
        for lo, hi in _subtract(p.s[i], p.s[j], holes):
            if hi - lo >= SPRINT_MIN_LENGTH_M:
                length = min(hi - lo, SPRINT_MAX_LENGTH_M)
                candidates.append((hi - length, hi))   # arrivée au bout du replat

    chosen: list[tuple[float, float]] = []
    for c in candidates:
        if not chosen or c[0] - chosen[-1][0] >= SPRINT_SPACING_M:
            chosen.append(c)
    return chosen


def _make(p: Profile, kind: str, s0: float, s1: float, index: int, source: str,
          name: str | None = None) -> Segment:
    length, gain, avg = _climb_stats(p, s0, s1)
    prefix = "sprint" if kind == "sprint" else "climb"
    label = "Sprint" if kind == "sprint" else "Montée"
    return Segment(
        id=f"{prefix}{index}" if source == "auto" else f"m{prefix}{index}",
        name=(name or f"{label} {index}")[:24],
        type=kind, s_start=s0, s_end=s1, length_m=length, avg_grade_pct=avg, gain_m=gain,
        category=climb_category(length, avg) if kind == "climb" else None,
        source=source,
    )


def detect_segments(p: Profile, auto_sprints: bool = True) -> list[Segment]:
    """Montées et (si demandé) sprints proposés, triés par début."""
    climbs = detect_climbs(p)
    out = [_make(p, "climb", a, b, k, "auto") for k, (a, b) in enumerate(climbs, 1)]
    if auto_sprints:
        out += [_make(p, "sprint", a, b, k, "auto")
                for k, (a, b) in enumerate(detect_sprints(p, climbs), 1)]
    return sorted(out, key=lambda seg: seg.s_start)


def manual_segments(p: Profile, entries: Iterable[dict]) -> list[Segment]:
    """Segments déclarés à la main : dictionnaires `{type, start_km, end_km, name?}`."""
    out: list[Segment] = []
    counters = {"sprint": 0, "climb": 0}
    for e in entries:
        try:
            kind = str(e["type"])
            s0 = float(e["start_km"]) * 1000.0
            s1 = float(e["end_km"]) * 1000.0
        except (KeyError, TypeError, ValueError) as exc:
            raise SegmentError(f"segment manuel incomplet : {e!r}") from exc
        if kind not in SEGMENT_TYPES:
            raise SegmentError(f"type de segment inconnu : {kind}")
        if not 0.0 <= s0 < s1 <= p.length_m + 0.01:
            raise SegmentError(f"segment manuel hors du parcours ou vide : {s0:.0f}–{s1:.0f} m")
        counters[kind] += 1
        out.append(_make(p, kind, s0, min(s1, p.length_m), counters[kind], "manual",
                         e.get("name")))
    return sorted(out, key=lambda seg: seg.s_start)


def merge_manual(auto: list[Segment], manual: list[Segment], mode: str = "add") -> list[Segment]:
    """`add` : automatiques qui ne chevauchent aucun manuel du même type, plus les manuels ;
    `replace` : les manuels seuls."""
    if mode not in MERGE_MODES:
        raise SegmentError(f"mode de fusion inconnu : {mode}")
    if mode == "replace":
        return sorted(manual, key=lambda seg: seg.s_start)

    def overlaps(a: Segment, b: Segment) -> bool:
        return a.type == b.type and a.s_start < b.s_end and b.s_start < a.s_end

    kept = [a for a in auto if not any(overlaps(a, m) for m in manual)]
    return sorted(kept + manual, key=lambda seg: seg.s_start)
