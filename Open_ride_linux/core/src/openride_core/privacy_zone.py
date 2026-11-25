"""Zone privée au départ (audit de cohérence du 22 novembre, lot PZ1) : aucune position à moins de
500 m du départ de la séance dans les fichiers exportés.

Réglage `privacy.hide_start` (« Zone privée au départ », coupé par défaut, suit le profil) :
- FIT (`fit_export.write_fit`) : un relevé à moins de `RADIUS_M` du premier point GPS de la séance perd sa
  latitude et sa longitude, y compris quand une boucle repasse près du départ ; temps, distance, vitesse,
  puissance, cadence, FC et altitude restent, donc les totaux, le coach, l'historique et le fantôme ne
  changent pas ;
- GPX du monde ouvert (`open_world_save.save_ride`) : le début et la fin de la trace sont coupés tant
  qu'ils restent dans la zone ; pas de trou au milieu, que le compilateur relierait d'un trait droit.

Module pur, sans entrées-sorties.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

RADIUS_M = 500.0
EARTH_R_M = 6_371_000.0


def radius_m(cfg: Any) -> float:
    """Rayon de la zone pour la configuration `cfg` : `RADIUS_M` si `privacy.hide_start` vaut `on`, 0 sinon."""
    privacy = getattr(cfg, "privacy", None)
    return RADIUS_M if getattr(privacy, "hide_start", "off") == "on" else 0.0


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance à vol d'oiseau (haversine), en mètres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * math.asin(min(1.0, math.sqrt(a)))


def _has_pos(r: dict) -> bool:
    return r.get("lat") is not None and r.get("lon") is not None


def mask_records(records: Sequence[dict], radius: float) -> tuple[list[dict], int]:
    """Relevés du FIT sans position dans la zone : `(relevés, nombre de relevés masqués)`.

    Le départ est le premier relevé qui porte une position. Les relevés d'entrée ne sont jamais modifiés :
    ceux de la zone sont copiés sans `lat` ni `lon`."""
    if radius <= 0:
        return list(records), 0
    start = next((r for r in records if _has_pos(r)), None)
    if start is None:
        return list(records), 0
    lat0, lon0 = start["lat"], start["lon"]
    out, n = [], 0
    for r in records:
        if _has_pos(r) and distance_m(lat0, lon0, r["lat"], r["lon"]) < radius:
            out.append({k: v for k, v in r.items() if k not in ("lat", "lon")})
            n += 1
        else:
            out.append(r)
    return out, n


def trim_points(points: Sequence[tuple[float, float, float]], radius: float) -> list[tuple[float, float, float]]:
    """Points `(lat, lon, altitude)` d'une trace sans le début ni la fin situés dans la zone du départ
    (premier point). Une trace qui ne sort jamais de la zone devient vide."""
    pts = list(points)
    if radius <= 0 or not pts:
        return pts
    lat0, lon0 = pts[0][0], pts[0][1]
    inside = [distance_m(lat0, lon0, p[0], p[1]) < radius for p in pts]
    if all(inside):
        return []
    first = inside.index(False)
    last = len(pts) - 1 - inside[::-1].index(False)
    return pts[first:last + 1]
