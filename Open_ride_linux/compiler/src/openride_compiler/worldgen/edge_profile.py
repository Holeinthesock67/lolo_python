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
6. garde-fou d'altitude (`altitude_guard.py`, 21 novembre 2026) : relief lu réparé (trous, pics) avant le lissage,
   puis profil ramené sous ± 15 % de pente et sous 4 % de changement de pente par pas de 10 m, pente des bouts
   à celle du nœud dans le sens de l'arête, altitudes des nœuds inchangées ;
7. pente par différences centrées (environ 20 m), bornée à ± 15 % (`AG.GRADE_MAX_PCT`) ; cap lissé sur environ 30 m.

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
from . import altitude_guard as AG
from .graph import Edge

EDGE_PROFILE_VERSION = 3          # 2 : garde-fou d'altitude (altitude_guard.py) ; 3 : plan du relief aux nœuds
SPAN_MARGIN_M = 10.0
NODE_RADIUS_M = 25.0            # plan du relief au nœud (22 novembre, banc de #961 : 10 m trop bruité)
NODE_OUTLIER_M = 1.5
PART_M = 1000.0
COLUMNS = ("lat", "lon", "alt_m", "x", "z", "grade_pct", "heading_deg")


class NodeAltitudes:
    """Altitude de chaque nœud : plan du relief ajusté autour du nœud (`node_sample`), gardée par identifiant ; et
    pente de ce plan au nœud (gradient en m/m, `grade`), pente visée au bout des arêtes.

    Deux arêtes qui se touchent lisent la même valeur au nœud commun.
    """

    def __init__(self, provider: ElevationProvider, frame: LocalFrame) -> None:
        self.provider = provider
        self.frame = frame
        self.values: dict[int, float] = {}
        self.gradients: dict[int, tuple[float, float]] = {}

    def _read(self, node_id: int, x: float, z: float) -> None:
        if node_id not in self.values:
            alt, grad = node_sample((x, z), self.provider, self.frame)
            self.values[node_id] = alt
            self.gradients[node_id] = grad

    def __call__(self, node_id: int, x: float, z: float) -> float:
        self._read(node_id, x, z)
        return self.values[node_id]

    def grade(self, node_id: int, x: float, z: float, dx: float, dz: float) -> float:
        """Pente du relief au nœud (%) dans la direction (dx, dz)."""
        self._read(node_id, x, z)
        return AG.node_grade(*self.gradients[node_id], dx, dz)


def _node_points(xz: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """Nœud et deux couronnes de 8 points (à `NODE_RADIUS_M` / 2 et `NODE_RADIUS_M`)."""
    x, z = xz
    ang = np.arange(8) * (np.pi / 4)
    r = np.concatenate([[0.0], np.full(8, NODE_RADIUS_M / 2), np.full(8, NODE_RADIUS_M)])
    a = np.concatenate([[0.0], ang, ang])
    return x + r * np.cos(a), z + r * np.sin(a)


def _plane(dx: np.ndarray, dz: np.ndarray, h: np.ndarray) -> np.ndarray:
    m = np.column_stack([np.ones_like(dx), dx, dz])
    return np.linalg.lstsq(m, h, rcond=None)[0]


def node_sample(xz: tuple[float, float], provider: ElevationProvider,
                frame: LocalFrame) -> tuple[float, tuple[float, float]]:
    """(altitude, gradient (gx, gz) en m/m) du relief au point : plan ajusté sur 17 points jusqu'à `NODE_RADIUS_M`,
    les points à plus de `NODE_OUTLIER_M` du plan (toit, haie, arbre du modèle de surface) écartés une fois.

    Deux nœuds proches (arête de 10 m) lisent presque les mêmes points : leurs altitudes et leurs pentes s'accordent,
    et la corde de l'arête courte suit la pente des arêtes voisines (constat du banc de #961, 22 novembre : 5 points
    à 10 m donnaient +6,5 % à un nœud et −12,8 % au suivant, 10 m plus loin).
    Valeurs absentes de la source écartées (garde-fou d'altitude)."""
    xs, zs = _node_points(xz)
    lat, lon = frame.to_latlon(xs, zs)
    h = np.asarray(provider.elevations(lat, lon), dtype=float)
    ok = np.isfinite(h) & (h >= AG.ALT_MIN_M) & (h <= AG.ALT_MAX_M)
    if not ok.any():
        raise ValueError("relief absent au nœud")
    dx, dz = xs - xz[0], zs - xz[1]
    if np.count_nonzero(ok) < 6:
        return float(h[ok].mean()), (0.0, 0.0)
    c = _plane(dx[ok], dz[ok], h[ok])
    res = np.abs(h - (c[0] + c[1] * dx + c[2] * dz))
    keep = ok & (res <= max(NODE_OUTLIER_M, 2.0 * float(np.median(res[ok]))))
    if 6 <= np.count_nonzero(keep) < np.count_nonzero(ok):
        c = _plane(dx[keep], dz[keep], h[keep])
    return float(c[0]), (float(c[1]), float(c[2]))


def node_altitude(xz: tuple[float, float], provider: ElevationProvider, frame: LocalFrame) -> float:
    return node_sample(xz, provider, frame)[0]


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
    guard: AG.GuardStats = AG.GuardStats()     # garde-fou d'altitude : ce qu'il a corrigé

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
    alt, read_stats = AG.repair(np.asarray(provider.elevations(lat, lon), dtype=float))   # 6. relief lu réparé

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

    t0 = t1 = None                                                      # 6. garde-fou d'altitude
    if len(s) >= 2:
        t0 = node_alt.grade(edge.raw_a, xa, za, x[1] - x[0], z[1] - z[0])
        t1 = node_alt.grade(edge.raw_b, xb, zb, x[-1] - x[-2], z[-1] - z[-2])
    alt, guard_stats = AG.guard(alt, s, t0, t1)

    grade = _grade(alt, s, False)                                       # 7.
    clamped = int(np.count_nonzero(np.abs(grade) > AG.GRADE_MAX_PCT))
    grade = np.clip(grade, -AG.GRADE_MAX_PCT, AG.GRADE_MAX_PCT)
    heading = _heading(x, z, False)
    versions = {"edge_profile": EDGE_PROFILE_VERSION, "altitude_guard": AG.GUARD_VERSION,
                "relief": getattr(provider, "name", "inconnu")}
    return EdgeProfile(edge.id, s, x, z, alt, grade, heading, np.asarray(lat), np.asarray(lon), clamped, versions,
                       guard=read_stats.merged(guard_stats))


# Boucle de retournement au bout d'une impasse (14 novembre) : arc d'entrée à droite de rayon TURN_ENTRY_M,
# boucle à gauche de rayon TURN_LOOP_M centrée sur l'axe de la route, arc de sortie à droite ; le tracé revient
# au bout de l'impasse dans l'autre sens, sans cassure de cap (cos α = r / (r + R) ferme la boucle sur l'axe).
TURN_ENTRY_M = 15.0
TURN_LOOP_M = 18.0
TURN_STEP_M = 1.0


def turnaround_points(end_xz: tuple[float, float], prev_xz: tuple[float, float],
                      r: float = TURN_ENTRY_M, big_r: float = TURN_LOOP_M) -> np.ndarray:
    """Tracé de la boucle (repère de zone, x = E, z = −N), du bout `end_xz` de l'impasse, atteint en venant de
    `prev_xz`, jusqu'à ce même point dans l'autre sens ; points tous les `TURN_STEP_M` environ."""
    ex, en = end_xz[0], -end_xz[1]                       # repère (E, N) : angles dans le sens trigonométrique
    dx, dn = ex - prev_xz[0], en + prev_xz[1]
    th0 = math.atan2(dn, dx)
    alpha = math.acos(r / (r + big_r))
    pieces = ((r * alpha, -1.0 / r), (big_r * (math.pi + 2 * alpha), 1.0 / big_r), (r * alpha, -1.0 / r))
    pts = [(ex, en)]
    x, n, th = ex, en, th0
    for length, k in pieces:                             # arcs exacts : chaque pas tourne de k·ds
        steps = max(1, int(math.ceil(length / TURN_STEP_M)))
        ds = length / steps
        for _ in range(steps):
            th1 = th + k * ds
            x, n = x + (math.sin(th1) - math.sin(th)) / k, n - (math.cos(th1) - math.cos(th)) / k
            th = th1
            pts.append((x, n))
    pts[-1] = (ex, en)                                   # fermeture exacte (l'erreur numérique est sous le mm)
    p = np.asarray(pts, dtype=float)
    p[:, 1] = -p[:, 1]
    return p


def with_turnaround(back: EdgeProfile, prev_xz: tuple[float, float], provider: ElevationProvider,
                    frame: LocalFrame) -> EdgeProfile:
    """Profil `back` (l'arête de l'impasse parcourue en sens inverse) précédé de la boucle de retournement : la
    route engagée tourne au bout de l'impasse au lieu d'y faire demi-tour sur place. Altitude du relief sous la
    boucle, décalée pour valoir celle du bout de l'impasse à l'entrée et à la sortie.

    Altitude lue sur l'axe de l'impasse prolongé, au droit de chaque point de la boucle (21/11) : la boucle est
    symétrique par rapport à cet axe, ses arcs d'entrée et de sortie se côtoient à quelques mètres ; lus au point même
    sur un dévers, ils avaient jusqu'à 5 m d'écart, deux chaussées l'une au-dessus de l'autre qu'aucun sol ne pouvait
    porter (règle sol / route)."""
    end_xz = (float(back.x[0]), float(back.z[0]))
    pts = turnaround_points(end_xz, prev_xz)
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    s = sample_positions(float(cum[-1]))
    x, z = np.interp(s, cum, pts[:, 0]), np.interp(s, cum, pts[:, 1])
    lat, lon = frame.to_latlon(x, z)
    ax, az = end_xz[0] - prev_xz[0], end_xz[1] - prev_xz[1]
    norm = math.hypot(ax, az) or 1.0
    ax, az = ax / norm, az / norm
    t = (x - end_xz[0]) * ax + (z - end_xz[1]) * az
    alat, alon = frame.to_latlon(end_xz[0] + t * ax, end_xz[1] + t * az)
    alt, read_stats = AG.repair(np.asarray(provider.elevations(alat, alon), dtype=float))
    alt = _smooth_altitude(alt, s) if len(s) >= C.SAVGOL_WINDOW else _moving_average_3(alt)
    end = float(back.alt_m[0])                           # rampe : entrée et sortie à l'altitude du bout de l'impasse
    alt = alt + (end - alt[0]) * (1.0 - s / s[-1]) + (end - alt[-1]) * (s / s[-1])
    # Garde-fou d'altitude : la boucle part et revient avec la pente de l'impasse à son bout (raccords sans cassure).
    arrive = -float(back.grade_pct[0]) if len(back.s) >= 2 else None   # pente en arrivant au bout, à l'aller
    alt, guard_stats = AG.guard(alt, s, arrive, None if arrive is None else -arrive)
    grade = np.clip(_grade(alt, s, False), -AG.GRADE_MAX_PCT, AG.GRADE_MAX_PCT)
    heading = _heading(x, z, False)
    n = float(s[-1])
    return replace(back,
                   s=np.concatenate([s, back.s[1:] + n]), x=np.concatenate([x, back.x[1:]]),
                   z=np.concatenate([z, back.z[1:]]), alt_m=np.concatenate([alt, back.alt_m[1:]]),
                   grade_pct=np.concatenate([grade, back.grade_pct[1:]]),
                   heading_deg=np.concatenate([heading, back.heading_deg[1:]]),
                   lat=np.concatenate([np.asarray(lat), back.lat[1:]]),
                   lon=np.concatenate([np.asarray(lon), back.lon[1:]]),
                   versions={**back.versions, "turnaround": 1},
                   guard=back.guard.merged(read_stats.merged(guard_stats)))


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
    g = np.clip(_grade(out["alt_m"], s, False), -AG.GRADE_MAX_PCT, AG.GRADE_MAX_PCT)
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
