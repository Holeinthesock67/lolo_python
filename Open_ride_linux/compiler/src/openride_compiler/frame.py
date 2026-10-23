"""Repère local d'un parcours (format §3) : UTM de la zone de l'origine, translaté.

x vers l'est, z vers le sud (z = −(nord − nord_0)), origine au premier point de la route.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pyproj import CRS, Transformer

from .errors import CompileError

UTM_BANDS = "CDEFGHJKLMNPQRSTUVWX"


def utm_zone_of(lat: float, lon: float) -> tuple[int, str, bool]:
    """Zone UTM standard (numéro, bande de latitude, hémisphère sud) d'un point.

    Règle simple : zones de 6° sans les exceptions de Norvège et du Svalbard.
    """
    if not -80.0 <= lat <= 84.0:
        raise CompileError(f"départ hors du domaine UTM (latitude {lat:.4f}, de −80 à 84)")
    number = min(int((lon + 180.0) // 6.0) + 1, 60)
    band = UTM_BANDS[min(int((lat + 80.0) // 8.0), len(UTM_BANDS) - 1)]
    return number, band, lat < 0.0


def utm_transformer(number: int, south: bool) -> Transformer:
    crs = CRS.from_epsg((32700 if south else 32600) + number)
    return Transformer.from_crs(CRS.from_epsg(4326), crs, always_xy=True)


@dataclass
class LocalFrame:
    """Passage entre coordonnées géographiques et repère du monde d'un parcours."""

    number: int
    band: str
    south: bool
    e0: float
    n0: float
    transformer: Transformer

    @classmethod
    def at(cls, lat: float, lon: float) -> "LocalFrame":
        """Repère dont l'origine est (lat, lon), dans la zone UTM de ce point."""
        number, band, south = utm_zone_of(lat, lon)
        tr = utm_transformer(number, south)
        e0, n0 = tr.transform(lon, lat)
        return cls(number, band, south, float(e0), float(n0), tr)

    @classmethod
    def from_manifest(cls, manifest: dict) -> "LocalFrame":
        """Repère d'un `.world` existant, à partir de `origin` (lat, lon, utm_zone)."""
        try:
            origin = manifest["origin"]
            lat, lon = float(origin["lat"]), float(origin["lon"])
            zone = str(origin.get("utm_zone") or "")
        except (KeyError, TypeError, ValueError) as exc:
            raise CompileError(f"manifeste : origine illisible ({exc})") from exc
        number, band, south = utm_zone_of(lat, lon)
        if zone and zone != f"{number}{band}":
            try:
                number, band = int(zone[:-1]), zone[-1]
            except ValueError as exc:
                raise CompileError(f"manifeste : utm_zone illisible {zone!r}") from exc
            south = band < "N"
        tr = utm_transformer(number, south)
        e0, n0 = tr.transform(lon, lat)
        return cls(number, band, south, float(e0), float(n0), tr)

    @property
    def zone(self) -> str:
        return f"{self.number}{self.band}"

    def to_xz(self, lat, lon) -> tuple[np.ndarray, np.ndarray]:
        east, north = self.transformer.transform(np.asarray(lon, float), np.asarray(lat, float))
        return np.asarray(east) - self.e0, -(np.asarray(north) - self.n0)

    def to_latlon(self, x, z) -> tuple[np.ndarray, np.ndarray]:
        lon, lat = self.transformer.transform(np.asarray(x, float) + self.e0,
                                              self.n0 - np.asarray(z, float), direction="INVERSE")
        return np.asarray(lat), np.asarray(lon)
