"""Résistance au roulement des routes non revêtues (lot U21, option « gravel », SRS §5 et §11).

Module pur, bibliothèque standard seulement :
- `effective_surface(route_surface, mode)` : `paved` si `[gravel] mode` vaut `off`, la surface de la route
  si `auto`, sinon la surface imposée (`compacted`, `gravel` ou `dirt`) sur tout le parcours, trace revêtue
  comprise (décision U-Q8) ;
- `crr_factor(surface, cfg)` : 1 pour `paved`, `factor_compacted`, `factor_gravel` ou `factor_dirt` sinon ;
- `blended_factor(route, s, mode, cfg)` : facteur moyen sur les 20 m qui précèdent `s` (transition douce
  entre deux surfaces, sans marche) ;
- `grade_offset_pct(crr_base, factor, grade_pct)` : supplément de pente équivalent
  `(factor − 1) × crr_base × cos θ × 100`, ajouté en SIM à celui du vent et de l'abri sous la même borne
  `[wind] max_grade_offset_pct`.
"""

from __future__ import annotations

import math
from typing import Protocol

SURFACES = ("paved", "compacted", "gravel", "dirt")
MODES = ("off", "auto", "compacted", "gravel", "dirt")
BLEND_M = 20.0


class GravelSettings(Protocol):
    mode: str
    factor_compacted: float
    factor_gravel: float
    factor_dirt: float


class SurfaceRoute(Protocol):
    ds_m: float
    surface: list[str] | None

    def surface_at(self, s: float) -> str: ...


def effective_surface(route_surface: str, mode: str) -> str:
    if mode == "off":
        return "paved"
    if mode == "auto":
        return route_surface if route_surface in SURFACES else "paved"
    return mode


def crr_factor(surface: str, cfg: GravelSettings) -> float:
    if surface == "compacted":
        return float(cfg.factor_compacted)
    if surface == "gravel":
        return float(cfg.factor_gravel)
    if surface == "dirt":
        return float(cfg.factor_dirt)
    return 1.0


def grade_offset_pct(crr_base: float, factor: float, grade_pct: float) -> float:
    """Supplément de pente (points de %) qui donne la même force que le roulement en plus."""
    return (factor - 1.0) * crr_base * math.cos(math.atan(grade_pct / 100.0)) * 100.0


def combined_offset_pct(wind_pct: float, gravel_pct: float, max_offset_pct: float) -> float:
    """Supplément total du vent, de l'abri et du gravel, borné à ± `max_offset_pct` (`[wind]`)."""
    return max(-max_offset_pct, min(max_offset_pct, wind_pct + gravel_pct))


def blended_factor(route: SurfaceRoute, s: float, mode: str, cfg: GravelSettings, blend_m: float = BLEND_M) -> float:
    """Facteur moyen sur [s − 20 m, s] : la surface d'un point vaut jusqu'au point suivant (`Route.surface_at`)."""
    if mode == "off":
        return 1.0
    if mode != "auto" or route.surface is None:
        return crr_factor(effective_surface("paved", mode), cfg)
    start, ds = s - blend_m, route.ds_m
    cuts = [start] + [k * ds for k in range(math.floor(start / ds) + 1, math.ceil(s / ds))] + [s]
    total = 0.0
    for a, b in zip(cuts, cuts[1:]):
        total += (b - a) * crr_factor(effective_surface(route.surface_at(0.5 * (a + b)), mode), cfg)
    return total / blend_m
