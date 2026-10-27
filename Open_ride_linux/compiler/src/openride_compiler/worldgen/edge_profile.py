"""Profil d'arête du monde ouvert (lot W5, `docs/2.0/PLAN_SERIE_W.md` §3.1 et §5.4).

Chaque arête du graphe (W4) reçoit un profil fait comme celui d'une route compilée (pas de 10 m,
altitude lissée, pente bornée, cap), mais qui ne dépend que de l'arête : la route engagée et le
fondu du terrain de tous les carrés (W7) utilisent le même, donc le terrain ne dépend pas du chemin.

1. rééchantillonnage au pas de 10 m (dernier point à `length_m`, comme `sample_positions`) ;
2. altitude du relief en chaque point ;
3. ponts et tunnels : interpolation linéaire entre les deux bouts de la portion, prolongée de 10 m
   de chaque côté pour sortir de la rampe d'accès ;
4. lissage Savitzky-Golay de `pipeline.py` (moyenne glissante sur 3 points sous 11 points) ;
5. raccord aux altitudes des nœuds par une rampe linéaire sur toute l'arête ;
6. pente par différences centrées (environ 20 m), bornée à ± 25 % ; cap lissé sur environ 30 m.

Tout en numpy, sans entrée-sortie.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Sequence

import numpy as np

from .. import constants as C
from ..elevation import ElevationProvider
from ..frame import LocalFrame
from ..pipeline import _grade, _heading, _smooth_altitude, sample_positions
from .graph import Edge

EDGE_PROFILE_VERSION = 1
SPAN_MARGIN_M = 10.0
NODE_RADIUS_M = 10.0
PART_M = 1000.0
COLUMNS = ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg")


class NodeAltitudes:
    """Altitude de chaque nœud : moyenne du relief au nœud et en 4 points à 10 m, gardée par identifiant.

    Deux arêtes qui se touchent lisent la même valeur au nœud commun.
    """

    def __init__(self, provider: ElevationProvider, frame: LocalFrame) -> None:
        self.provider = provider
        self.frame = frame
        self.values: dict[int, float] = {}

    def __call__(self, node_id: int, x: float, z: float) -> float:
        if node_id not in self.values:
            self.values[node_id] = node_altitude((x, z), self.provider, self.frame)
        return self.values[node_id]


def node_altitude(xz: tuple[float, float], provider: ElevationProvider, frame: LocalFrame) -> float:
    x, z = xz
    r = NODE_RADIUS_M
    xs = np.array([x, x + r, x - r, x, x])
    zs = np.array([z, z, z, z + r, z - r])
    lat, lon = frame.to_latlon(xs, zs)
    return float(np.mean(provider.elevations(lat, lon)))


@dataclass(frozen=True)
class EdgeProfile:
    edge_id: str
    s: np.ndarray
    x: np.ndarray
    z: np.ndarray
    alt_m: np.ndarray
    grade_pct: np.ndarray
    heading_deg: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    clamped_points: int
    versions: dict[str, Any] = field(default_factory=dict)
    forward: bool = True

    @property
    def length_m(self) -> float:
        return float(self.s[-1])

    def reversed(self) -> "EdgeProfile":
        """Même profil parcouru dans l'autre sens : pentes opposées, cap + 180°, sans recalcul."""
        return replace(self, s=self.length_m - self.s[::-1], x=self.x[::-1], z=self.z[::-1],
                       alt_m=self.alt_m[::-1], grade_pct=-self.grade_pct[::-1],
                       heading_deg=(self.heading_deg[::-1] + 180.0) % 360.0,
                       lat=self.lat[::-1], lon=self.lon[::-1], forward=not self.forward)


def _resample(points: Sequence[tuple[float, float]], s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    p = np.asarray(points, dtype=float)
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])
    return np.interp(s, cum, p[:, 0]), np.interp(s, cum, p[:, 1])


def _moving_average_3(a: np.ndarray) -> np.ndarray:
    if len(a) < 3:
        return a.copy()
    out = a.copy()
    out[1:-1] = (a[:-2] + a[1:-1] + a[2:]) / 3.0
    return out


def edge_profile(edge: Edge, provider: ElevationProvider, frame: LocalFrame,
                 node_alt: NodeAltitudes | None = None) -> EdgeProfile:
    node_alt = node_alt or NodeAltitudes(provider, frame)
    length = float(edge.length_m)
    s = sample_positions(length)
    x, z = _resample(edge.points, s)
    lat, lon = frame.to_latlon(x, z)
    alt = np.asarray(provider.elevations(lat, lon), dtype=float).copy()

    for s0, s1, _kind in edge.spans:                                    # 3. ponts et tunnels
        a, b = max(0.0, s0 - SPAN_MARGIN_M), min(length, s1 + SPAN_MARGIN_M)
        if b <= a:
            continue
        ya, yb = np.interp([a, b], s, alt)
        inside = (s >= a) & (s <= b)
        alt[inside] = ya + (yb - ya) * (s[inside] - a) / (b - a)

    alt = _smooth_altitude(alt, s) if len(s) >= C.SAVGOL_WINDOW else _moving_average_3(alt)   # 4.

    xa, za = edge.points[0]                                             # 5. raccord aux nœuds
    xb, zb = edge.points[-1]
    da = node_alt(edge.raw_a, xa, za) - alt[0]
    db = node_alt(edge.raw_b, xb, zb) - alt[-1]
    alt = alt + da + (db - da) * (s / length if length > 0 else 0.0)

    grade = _grade(alt, s, False)                                       # 6.
    clamped = int(np.count_nonzero(np.abs(grade) > C.GRADE_LIMIT_PCT))
    grade = np.clip(grade, -C.GRADE_LIMIT_PCT, C.GRADE_LIMIT_PCT)
    heading = _heading(x, z, False)
    versions = {"edge_profile": EDGE_PROFILE_VERSION, "relief": getattr(provider, "name", "inconnu")}
    return EdgeProfile(edge.id, s, x, z, alt, grade, heading, np.asarray(lat), np.asarray(lon), clamped, versions)


def concat(profiles: Iterable[EdgeProfile], s0: float = 0.0) -> dict[str, Any]:
    """Profils mis bout à bout, rééchantillonnés au pas de 10 m, en colonnes du format `route.json`.

    Le point de jonction n'est pas doublé ; la pente est recalculée sur l'altitude jointe et le cap
    sur la géométrie jointe. Renvoie `s` (à partir de `s0`), les colonnes et `length_m`.
    """
    parts = list(profiles)
    if not parts:
        raise ValueError("aucun profil à joindre")
    cols: dict[str, list[np.ndarray]] = {k: [] for k in ("s", "x", "z", "alt_m", "lat", "lon")}
    offset = 0.0
    for k, p in enumerate(parts):
        cut = 0 if k == 0 else 1
        cols["s"].append(p.s[cut:] + offset)
        for name in ("x", "z", "alt_m", "lat", "lon"):
            cols[name].append(getattr(p, name)[cut:])
        offset += p.length_m
    joined = {k: np.concatenate(v) for k, v in cols.items()}
    s = sample_positions(offset)
    out: dict[str, Any] = {"length_m": offset}
    for name in ("x", "z", "alt_m", "lat", "lon"):
        out[name] = np.interp(s, joined["s"], joined[name])
    g = np.clip(_grade(out["alt_m"], s, False), -C.GRADE_LIMIT_PCT, C.GRADE_LIMIT_PCT)
    out["grade_pct"] = g
    out["heading_deg"] = _heading(out["x"], out["z"], False)
    out["s"] = s + s0
    out["edges"] = [p.edge_id for p in parts]
    return out


def _round(name: str, a: np.ndarray) -> list[float]:
    digits = {"lat": 7, "lon": 7, "alt_m": 2, "x": 2, "z": 2, "grade_pct": 2, "heading_deg": 1}[name]
    return [round(float(v), digits) for v in a]


def split_parts(route: dict[str, Any], part_m: float = PART_M) -> list[dict[str, Any]]:
    """Découpe des colonnes jointes (`s` à partir d'un multiple de 1 000 m) en parties du format §13.

    La partie k va de s = 1000 k à s = 1000 (k + 1) inclus (bord partagé avec la suivante).
    """
    s = np.asarray(route["s"], dtype=float)
    k0 = int(math.floor(s[0] / part_m + 1e-9))
    if abs(s[0] - k0 * part_m) > 1e-6:
        raise ValueError(f"la route doit commencer à un multiple de {part_m:.0f} m (s = {s[0]})")
    out = []
    k = k0
    while True:
        lo, hi = k * part_m, (k + 1) * part_m
        idx = np.nonzero((s >= lo - 1e-6) & (s <= hi + 1e-6))[0]
        if len(idx) < 2:
            break
        part = {"version": "1.0", "ds_m": C.DS_M, "n": int(len(idx)),
                "length_m": round(float(s[idx[-1]] - s[idx[0]]), 3), "type": "open", "s0_m": float(lo)}
        for name in COLUMNS:
            part[name] = _round(name, np.asarray(route[name])[idx])
        out.append(part)
        if s[idx[-1]] >= s[-1] - 1e-6:
            break
        k += 1
    return out
