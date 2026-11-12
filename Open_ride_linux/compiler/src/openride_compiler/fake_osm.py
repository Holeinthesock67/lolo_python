"""Réponse Overpass fabriquée pour les parcours synthétiques (aucune donnée réelle, aucun réseau).

Sert aux parcours de démonstration des biomes livrés avec le jeu (`demo_biomes.py`, lot O37) et au parcours
d'essai « village simulé » des tests de l'engine (`engine/tests/make_sim_world.py`). `x` vers l'est, `z` vers le
sud (nord = −z), en mètres autour de l'origine. Deux formes de route, de même interface (`xz`, `heading`,
`locate`, `s_of`) : `SRoad`, deux grands S (`road_x`) vers le nord (parcours ouverts), et `LoopRoad`, une
boucle fermée (circuit de démonstration, lot O38).
"""

from __future__ import annotations

import math
import random

import numpy as np


def no_network(*_args, **_kwargs):
    raise OSError("réseau interdit pendant la génération d'un parcours synthétique")


def road_x(s: float) -> float:
    """Écart de la route vers l'est (m) : deux grands S."""
    return 60.0 * math.sin(2.0 * math.pi * s / 1800.0)


def road_heading(s: float) -> tuple[float, float]:
    """Vecteur unitaire (x, z) dans le sens de la route (vers le nord : z décroît)."""
    dx = 60.0 * 2.0 * math.pi / 1800.0 * math.cos(2.0 * math.pi * s / 1800.0)
    n = math.hypot(dx, 1.0)
    return dx / n, -1.0 / n


class Road:
    """Interface commune des formes de route : `xz(s)`, `heading(s)`, `locate(x, z)`, `s_of(x, z)`."""

    def point(self, s: float, offset: float) -> tuple[float, float]:
        """Point à `offset` m (positif : à droite du sens de marche) du point `s` de la route."""
        hx, hz = self.heading(s)
        x, z = self.xz(s)
        return x - hz * offset, z + hx * offset


class SRoad(Road):
    """Route ouverte en deux grands S vers le nord : le point d'abscisse `s` est en (`road_x(s)`, −s)."""

    loop = False

    def __init__(self, length_m: float) -> None:
        self.length_m = float(length_m)

    def xz(self, s: float) -> tuple[float, float]:
        return road_x(s), -s

    def heading(self, s: float) -> tuple[float, float]:
        return road_heading(s)

    def s_of(self, x, z):
        """Abscisse de la route la plus proche (approchée par la distance vers le nord, à 1 % près)."""
        return np.clip(-np.asarray(z, dtype=float), 0.0, self.length_m)

    def locate(self, x, z):
        """(abscisse, écart latéral signé, positif à droite du sens de marche) de chaque point (x, z)."""
        s = self.s_of(x, z)
        return s, np.asarray(x, dtype=float) - 60.0 * np.sin(2.0 * np.pi * s / 1800.0)


class LoopRoad(Road):
    """Boucle fermée parcourue dans le sens horaire (vue du ciel, nord en haut) : l'intérieur est à droite.

    Courbe étoilée autour de l'origine, de rayon modulé `radius · (1 + Σ a·cos(k·t + φ))` pour (k, a, φ) de
    `lobes`, remise à la longueur `length_m` ; départ au nord du centre. Abscisse curviligne exacte par
    ré-échantillonnage tous les `STEP` m, recherche du point le plus proche par arbre k-d (scipy)."""

    loop = True
    STEP = 2.0
    INSIDE = 1           # côté de l'intérieur de la boucle (droite du sens de marche)

    def __init__(self, length_m: float, lobes: tuple[tuple[int, float, float], ...] = ()) -> None:
        from scipy.spatial import cKDTree

        t = np.linspace(0.0, 2.0 * np.pi, 20001)
        r = 1.0 + sum(a * np.cos(k * t + phi) for k, a, phi in lobes)
        x, z = r * np.sin(t), -r * np.cos(t)
        seg = np.hypot(np.diff(x), np.diff(z))
        scale = length_m / float(seg.sum())
        cum = np.concatenate(([0.0], np.cumsum(seg))) * scale
        self.length_m = float(length_m)
        n = int(round(self.length_m / self.STEP))
        self._s = np.linspace(0.0, self.length_m, n + 1)
        self._x = np.interp(self._s, cum, x * scale)
        self._z = np.interp(self._s, cum, z * scale)
        self._x[-1], self._z[-1] = self._x[0], self._z[0]
        dx = np.gradient(np.concatenate((self._x[-2:-1], self._x, self._x[1:2])))[1:-1]
        dz = np.gradient(np.concatenate((self._z[-2:-1], self._z, self._z[1:2])))[1:-1]
        norm = np.hypot(dx, dz)
        self._hx, self._hz = dx / norm, dz / norm
        self._tree = cKDTree(np.column_stack((self._x[:-1], self._z[:-1])))

    def _at(self, s: float) -> int:
        return int(round((s % self.length_m) / self.STEP))

    def xz(self, s: float) -> tuple[float, float]:
        s = s % self.length_m
        return float(np.interp(s, self._s, self._x)), float(np.interp(s, self._s, self._z))

    def heading(self, s: float) -> tuple[float, float]:
        i = self._at(s)
        return float(self._hx[i]), float(self._hz[i])

    def radius_min(self) -> float:
        """Plus petit rayon de virage (m), mesuré sur 20 m."""
        k = int(round(10.0 / self.STEP))
        h = np.unwrap(np.arctan2(self._hx, -self._hz))
        turn = np.abs(h[2 * k:] - h[:-2 * k])
        return float(2 * k * self.STEP / max(float(turn.max()), 1e-9))

    def s_of(self, x, z):
        return self.locate(x, z)[0]

    def locate(self, x, z):
        x = np.asarray(x, dtype=float)
        z = np.asarray(z, dtype=float)
        _, i = self._tree.query(np.column_stack((x.ravel(), z.ravel())))
        i = i.reshape(x.shape)
        nx, nz = -self._hz[i], self._hx[i]                     # normale à droite du sens de marche
        return self._s[i], (x - self._x[i]) * nx + (z - self._z[i]) * nz


class Frame:
    """Repère UTM local centré sur `origin` (lat, lon)."""

    def __init__(self, origin: tuple[float, float]) -> None:
        from .pipeline import utm_transformer, utm_zone_of
        number, _, south = utm_zone_of(*origin)
        self.tr = utm_transformer(number, south)
        self.e0, self.n0 = self.tr.transform(origin[1], origin[0])

    def latlon(self, x: float, z: float) -> tuple[float, float]:
        lon, lat = self.tr.transform(x + self.e0, self.n0 - z, direction="INVERSE")
        return float(lat), float(lon)


class Overpass:
    """Réponse Overpass fabriquée : éléments au format `out geom`."""

    def __init__(self, frame: Frame, rng: random.Random, road: Road | None = None) -> None:
        self.frame = frame
        self.rng = rng
        self.road = road or SRoad(math.inf)
        self.elements: list[dict] = []
        self.next_id = 900_000
        self.counts = {"buildings": 0, "vegetation": 0, "water_lines": 0, "water_areas": 0, "poi": 0}

    def _id(self) -> int:
        self.next_id += 1
        return self.next_id

    def _geom(self, ring_xz: list[tuple[float, float]], close: bool = True) -> list[dict]:
        pts = list(ring_xz) + ([ring_xz[0]] if close else [])
        out = []
        for x, z in pts:
            lat, lon = self.frame.latlon(x, z)
            out.append({"lat": round(lat, 8), "lon": round(lon, 8)})
        return out

    def way(self, ring_xz, tags: dict, close: bool = True) -> None:
        self.elements.append({"type": "way", "id": self._id(), "tags": tags, "geometry": self._geom(ring_xz, close)})

    def node(self, x: float, z: float, tags: dict) -> None:
        lat, lon = self.frame.latlon(x, z)
        self.elements.append({"type": "node", "id": self._id(), "lat": round(lat, 8), "lon": round(lon, 8),
                              "tags": tags})
        self.counts["poi"] += 1

    def rect_along(self, s: float, offset: float, length: float, depth: float) -> list[tuple[float, float]]:
        """Rectangle aligné sur la route, centré à `offset` m (positif : à droite) du point `s`."""
        hx, hz = self.road.heading(s)
        nx, nz = -hz, hx                       # normale à droite du sens de marche
        x, z = self.road.xz(s)
        cx = x + nx * offset
        cz = z + nz * offset
        corners = []
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append((cx + hx * a * length / 2 + nx * b * depth / 2,
                            cz + hz * a * length / 2 + nz * b * depth / 2))
        return corners

    def band(self, s0: float, s1: float, off0: float, off1: float) -> list[tuple[float, float]]:
        """Bande le long de la route entre deux distances latérales (forêts, vergers)."""
        steps = max(2, int((s1 - s0) / 50.0))
        inner, outer = [], []
        for k in range(steps + 1):
            s = s0 + (s1 - s0) * k / steps
            hx, hz = self.road.heading(s)
            nx, nz = -hz, hx
            x, z = self.road.xz(s)
            inner.append((x + nx * off0, z + nz * off0))
            outer.append((x + nx * off1, z + nz * off1))
        return inner + outer[::-1]

    def point(self, s: float, offset: float) -> tuple[float, float]:
        return self.road.point(s, offset)

    def building(self, s: float, offset: float, tags: dict, length: float, depth: float) -> None:
        self.way(self.rect_along(s, offset, length, depth), tags)
        self.counts["buildings"] += 1


COLOURS = ["#d9cfc1", "#e8dcc4", "#c9b59a", "#f0e6d2", "#b9a48a", "#e3c9a8", "#d4d0c8"]
