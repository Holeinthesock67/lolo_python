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


# --- Largeur roulable (cyclistes du décor sur le gravel, correctif du 7 novembre) ----------------------------
# Mêmes règles que le ruban de l'engine (`engine/scripts/road_surface.gd`, lot U22) : largeur de la surface non
# revêtue du thème (`surfaces.<id>.width_m`, défauts ci-dessous), raccord en biseau de BEVEL_M avec le bitume
# (part non revêtue sur BEVEL_SAMPLES points centrés), bords irréguliers de ± EDGE_NOISE_M retirés.
UNPAVED = ("compacted", "gravel", "dirt")
DEFAULT_WIDTH_M = {"compacted": 4.0, "gravel": 3.5, "dirt": 3.0}
BEVEL_M = 5.0
BEVEL_SAMPLES = 11
EDGE_NOISE_M = 0.25


def surface_widths(theme_surfaces: dict | None) -> dict[str, float]:
    """Largeur (m) de chaque surface non revêtue : `surfaces` du thème, sinon les défauts (bornée à 1–8 m)."""
    out = {}
    raw = theme_surfaces if isinstance(theme_surfaces, dict) else {}
    for sid in UNPAVED:
        entry = raw.get(sid)
        w = entry.get("width_m") if isinstance(entry, dict) else None
        if isinstance(w, bool) or not isinstance(w, (int, float)):
            w = DEFAULT_WIDTH_M[sid]
        out[sid] = min(max(float(w), 1.0), 8.0)
    return out


def rideable_half_m(route: SurfaceRoute, s: float, mode: str, widths: dict[str, float],
                    road_width_m: float) -> float:
    """Demi-largeur sûre de la chaussée en `s` (m) : celle du bitume, ou sur une portion non revêtue la
    demi-largeur du ruban de l'engine sans ses bords irréguliers (le plus étroit des deux côtés possibles)."""
    half = road_width_m * 0.5
    if mode == "off" or mode not in MODES:
        return half
    count: dict[str, int] = {}
    unpaved = 0
    for j in range(BEVEL_SAMPLES):
        sv = s - BEVEL_M * 0.5 + BEVEL_M * j / (BEVEL_SAMPLES - 1)
        e = effective_surface(route.surface_at(sv), mode) if mode == "auto" else mode
        if e in UNPAVED:
            unpaved += 1
            count[e] = count.get(e, 0) + 1
    if unpaved == 0:
        return half
    main = ""
    for sid in UNPAVED:   # surface la plus présente dans le biseau, ordre fixe en cas d'égalité
        if count.get(sid, 0) > count.get(main, 0):
            main = sid
    weight = unpaved / BEVEL_SAMPLES
    target = widths.get(main, DEFAULT_WIDTH_M[main]) * 0.5
    return half + (target - half) * weight - EDGE_NOISE_M * weight
