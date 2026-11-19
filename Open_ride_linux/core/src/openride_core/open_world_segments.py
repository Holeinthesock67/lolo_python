"""Montées et sprints du monde ouvert, détectés en roulant (lot W20, série W).

Un parcours compilé porte sa couche `segments` (série T) ; le monde ouvert n'en a pas, puisque la route
se construit en roulant. Ce module, pur (aucune entrée-sortie hors du petit index ci-dessous, lu et écrit
par l'appelant), repère les montées et les sprints sur la route engagée avec les règles de `segments.py`,
dans une fenêtre qui va de 3 km derrière le cycliste au bout de la route connue :

- un segment n'est **retenu** que s'il commence devant le cycliste et finit au moins `FINAL_MARGIN_M`
  avant le bout de la route connue (une montée qui touche ce bout pourrait encore s'allonger) ; il n'est
  plus jamais redessiné ensuite ;
- il est **retiré** (s'il n'est pas déjà franchi) quand la route change sous lui : un choix de branche
  réécrit la route après un carrefour, et le début ou la fin du segment n'y est plus au même endroit ;
- sprints : au plus un tous les 10 km (règle du plan T §3.1), comptés sur toute la séance.

**Records d'une balade à l'autre.** Les records sont rangés sous le parcours commun `ow` (constante
`RECORDS_ROUTE_ID`), et chaque segment reçoit un identifiant stable : un segment dont le début et la fin
sont à moins de `MATCH_M` d'un segment déjà vu (même type) reprend son identifiant et son nom. L'index
de ces segments (`OwIndex`, fichier `segments_monde_ouvert.json` à côté de `records.json` du profil)
garde, par identifiant, le type, les deux extrémités (lat, lon) et le nom.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Sequence

from .segments import SPRINT_SPACING_M, Profile, Segment, SegmentError, detect_segments

RECORDS_ROUTE_ID = "ow"           # parcours commun des records du monde ouvert
INDEX_NAME = "segments_monde_ouvert.json"
BEHIND_M = 3000.0                 # fenêtre de détection derrière le cycliste
FINAL_MARGIN_M = 1000.0           # un segment retenu finit au moins à cette distance du bout connu
AHEAD_MIN_M = 20.0                # et commence au moins à cette distance devant le cycliste
MATCH_M = 60.0                    # extrémités à moins de 60 m : même segment qu'une balade précédente
MOVED_M = 5.0                     # extrémité déplacée de plus de 5 m par une révision : segment retiré
CATEGORY_LABEL = {"HC": "HC", "1": "1re cat.", "2": "2e cat.", "3": "3e cat.", "4": "4e cat."}


def _dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance approchée (m) entre deux points (lat, lon) proches."""
    lat = math.radians((a[0] + b[0]) / 2.0)
    dy = (a[0] - b[0]) * 111_195.0
    dx = (a[1] - b[1]) * 111_195.0 * math.cos(lat)
    return math.hypot(dx, dy)


@dataclass
class OwIndex:
    """Segments du monde ouvert déjà vus (identifiant → type, extrémités, nom)."""

    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    dirty: bool = False

    @classmethod
    def load(cls, path: Path | None) -> "OwIndex":
        if path is None or not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = {str(k): v for k, v in data.get("segments", {}).items()
                     if isinstance(v, dict) and v.get("type") in ("climb", "sprint")
                     and len(v.get("a", ())) == 2 and len(v.get("b", ())) == 2}
        except (OSError, ValueError, AttributeError, TypeError):
            return cls()                     # index illisible : de nouveaux identifiants, rien de cassé
        return cls(items)

    def save(self, path: Path) -> None:
        """Écriture atomique (fichier temporaire puis renommage)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"version": 1, "segments": self.items}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, path)
        self.dirty = False

    def match(self, kind: str, a: tuple[float, float], b: tuple[float, float]) -> str | None:
        best: tuple[float, str] | None = None
        for sid, it in self.items.items():
            if it["type"] != kind:
                continue
            da, db = _dist_m(a, tuple(it["a"])), _dist_m(b, tuple(it["b"]))
            if da <= MATCH_M and db <= MATCH_M and (best is None or da + db < best[0]):
                best = (da + db, sid)
        return best[1] if best else None

    def add(self, kind: str, a: tuple[float, float], b: tuple[float, float], category: str | None) -> str:
        key = f"{kind}:{a[0]:.5f},{a[1]:.5f}:{b[0]:.5f},{b[1]:.5f}"
        sid = ("owc" if kind == "climb" else "ows") + hashlib.sha1(key.encode()).hexdigest()[:10]
        n = 1 + sum(1 for it in self.items.values() if it["type"] == kind)
        label = "Montée" if kind == "climb" else "Sprint"
        name = f"{label} n°{n}" + (f" ({CATEGORY_LABEL.get(category, category)})" if category else "")
        self.items[sid] = {"type": kind, "a": [round(a[0], 6), round(a[1], 6)],
                           "b": [round(b[0], 6), round(b[1], 6)], "name": name}
        self.dirty = True
        return sid


@dataclass(frozen=True)
class RouteWindow:
    """Profil de la route connue, en distance de séance (s croissant), avec lat et lon."""

    s: Sequence[float]
    alt_m: Sequence[float]
    grade_pct: Sequence[float]
    lat: Sequence[float]
    lon: Sequence[float]

    def at(self, s: float) -> tuple[float, float]:
        """(lat, lon) au point le plus proche de `s`."""
        i = min(max(bisect.bisect_left(self.s, s), 0), len(self.s) - 1)
        if i > 0 and abs(self.s[i - 1] - s) < abs(self.s[i] - s):
            i -= 1
        return float(self.lat[i]), float(self.lon[i])


def route_window(route: Any, s_from: float) -> RouteWindow | None:
    """Fenêtre de la route d'un `LiveRoute` (ou d'une `Route` de base `base_m`) à partir de `s_from`."""
    inner = route._current() if hasattr(route, "_current") else route
    base = float(getattr(route, "base_m", 0.0))
    s = inner.s
    lo = max(bisect.bisect_right(s, s_from - base) - 1, 0)
    if len(s) - lo < 2:
        return None
    return RouteWindow([base + v for v in s[lo:]], inner.alt_m[lo:], inner.grade_pct[lo:],
                       inner.lat[lo:], inner.lon[lo:])


@dataclass
class LiveSegments:
    """Segments retenus de la séance en monde ouvert (s en distance de séance)."""

    index: OwIndex = field(default_factory=OwIndex)
    accepted: list[Segment] = field(default_factory=list)
    ends: dict[str, tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=dict)
    _last_sprint_s: float = -math.inf

    def update(self, win: RouteWindow | None, s_now: float) -> tuple[list[Segment], list[str]]:
        """Nouveaux segments retenus et identifiants retirés, d'après la route connue `win`."""
        if win is None:
            return [], []
        removed = self._check_moved(win, s_now)
        added: list[Segment] = []
        known_end = win.s[-1]
        origin = win.s[0]
        try:
            prof = Profile([v - origin for v in win.s], win.alt_m, win.grade_pct)
            found = detect_segments(prof)
        except SegmentError:
            return [], removed
        for seg in found:
            s0, s1 = origin + seg.s_start, origin + seg.s_end
            if s0 < s_now + AHEAD_MIN_M or s1 > known_end - FINAL_MARGIN_M:
                continue
            if any(a.type == seg.type and s0 < a.s_end and a.s_start < s1 for a in self.accepted):
                continue
            if seg.type == "sprint" and s0 - self._last_sprint_s < SPRINT_SPACING_M:
                continue
            a_pt, b_pt = win.at(s0), win.at(s1)
            sid = self.index.match(seg.type, a_pt, b_pt) or self.index.add(seg.type, a_pt, b_pt, seg.category)
            if any(x.id == sid for x in self.accepted):
                continue                      # même segment repassé dans la séance : le premier suffit
            name = str(self.index.items[sid]["name"])
            out = replace(seg, id=sid, name=name[:24], s_start=s0, s_end=s1)
            self.accepted.append(out)
            self.ends[sid] = (a_pt, b_pt)
            if seg.type == "sprint":
                self._last_sprint_s = s0
            added.append(out)
        self.accepted.sort(key=lambda x: x.s_start)
        return added, removed

    def _check_moved(self, win: RouteWindow, s_now: float) -> list[str]:
        """Segments pas encore finis dont la route a changé (choix de branche) : retirés."""
        removed = []
        for seg in list(self.accepted):
            if seg.s_end <= s_now or seg.s_start < win.s[0]:
                continue
            if seg.s_end > win.s[-1]:
                moved = True                   # route raccourcie sous le segment
            else:
                a_pt, b_pt = self.ends[seg.id]
                moved = _dist_m(win.at(seg.s_start), a_pt) > MOVED_M or _dist_m(win.at(seg.s_end), b_pt) > MOVED_M
            if moved:
                self.accepted.remove(seg)
                del self.ends[seg.id]
                removed.append(seg.id)
        if removed and not any(s.type == "sprint" for s in self.accepted):
            self._last_sprint_s = -math.inf
        elif removed:
            self._last_sprint_s = max(s.s_start for s in self.accepted if s.type == "sprint")
        return removed


# --- couche `segments.json` du monde vivant (lot W21) -----------------------------------------------

LIVE_FILE = "segments.json"          # même nom et même schéma que la couche segments d'un `.world` (§8 bis)
LIVE_KEEP_BEHIND_M = 2000.0          # segments finis plus loin derrière : retirés du fichier
LIVE_MAX = 200                       # `maxItems` du schéma


def live_layer(segments: Sequence[Segment], base_m: float, s_now: float) -> dict[str, Any]:
    """Couche `segments.json` du monde vivant : segments retenus, en distance de la route du générateur
    (`s` − `base_m`), sans ceux finis plus de 2 km derrière ni ceux d'avant une relance du générateur."""
    keep = [seg for seg in segments if seg.s_end >= s_now - LIVE_KEEP_BEHIND_M and seg.s_start >= base_m]
    out = []
    for seg in keep[-LIVE_MAX:]:
        d = seg.to_dict()
        d["s_start"] = round(seg.s_start - base_m, 1)
        d["s_end"] = round(seg.s_end - base_m, 1)
        out.append(d)
    return {"version": "1.0", "segments": out}


def write_live_layer(folder: Path, layer: dict[str, Any]) -> None:
    """Écriture atomique dans le dossier de séance (l'engine la relit quand le fichier change)."""
    tmp = Path(folder) / f"{LIVE_FILE}.{threading.get_ident()}.tmp"   # deux écritures en même temps : chacune le sien
    tmp.write_text(json.dumps(layer, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, Path(folder) / LIVE_FILE)
