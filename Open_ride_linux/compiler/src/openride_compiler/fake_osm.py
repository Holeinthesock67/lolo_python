"""Réponse Overpass fabriquée pour les parcours synthétiques (aucune donnée réelle, aucun réseau).

Sert aux parcours de démonstration des biomes livrés avec le jeu (`demo_biomes.py`, lot O37) et au parcours
d'essai « village simulé » des tests de l'engine (`engine/tests/make_sim_world.py`). La route suit deux
grands S (`road_x`) vers le nord ; `x` vers l'est, `z` vers le sud (nord = −z), en mètres autour de l'origine.
"""

from __future__ import annotations

import math
import random


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

    def __init__(self, frame: Frame, rng: random.Random) -> None:
        self.frame = frame
        self.rng = rng
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
        hx, hz = road_heading(s)
        nx, nz = -hz, hx                       # normale à droite du sens de marche
        cx = road_x(s) + nx * offset
        cz = -s + nz * offset
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
            hx, hz = road_heading(s)
            nx, nz = -hz, hx
            inner.append((road_x(s) + nx * off0, -s + nz * off0))
            outer.append((road_x(s) + nx * off1, -s + nz * off1))
        return inner + outer[::-1]

    def building(self, s: float, offset: float, tags: dict, length: float, depth: float) -> None:
        self.way(self.rect_along(s, offset, length, depth), tags)
        self.counts["buildings"] += 1


COLOURS = ["#d9cfc1", "#e8dcc4", "#c9b59a", "#f0e6d2", "#b9a48a", "#e3c9a8", "#d4d0c8"]
