"""Chaîne de traitement GPX → couche route (lot B1 §3.2, format §3 et §4).

Lecture, projection UTM, nettoyage, type de parcours, ré-échantillonnage tous les 10 m,
altitude lissée, pente, cap et coordonnées géographiques. Tout est vectorisé avec numpy,
sauf le nettoyage qui compare chaque point au dernier point gardé.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from pyproj import CRS, Transformer
from scipy.signal import savgol_filter

from . import constants as C
from .errors import CompileError
from .gpx import GpxPoint

UTM_BANDS = "CDEFGHJKLMNPQRSTUVWX"


@dataclass
class CompiledRoute:
    route: dict                  # contenu de route.json
    utm_zone: str                # par exemple « 32T »
    grade_clamped_points: int


# --- projection -----------------------------------------------------------------------------

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


# --- étapes ---------------------------------------------------------------------------------

def _clean(xy: np.ndarray, ele: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Supprime les points à moins de MIN_STEP_M (horizontal) du dernier point gardé."""
    keep = [0]
    lx, ly = xy[0]
    for i in range(1, len(xy)):
        x, y = xy[i]
        if math.hypot(x - lx, y - ly) >= C.MIN_STEP_M:
            keep.append(i)
            lx, ly = x, y
    return xy[keep], ele[keep]


def _cumulative(xy: np.ndarray) -> np.ndarray:
    return np.concatenate(([0.0], np.cumsum(np.hypot(*np.diff(xy, axis=0).T))))


def _close_loop(xy: np.ndarray, ele: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ajoute le premier point à la fin ; retire d'abord les derniers points trop proches du départ."""
    end = len(xy)
    while end > 1 and math.hypot(*(xy[end - 1] - xy[0])) < C.MIN_STEP_M:
        end -= 1
    return np.vstack((xy[:end], xy[:1])), np.concatenate((ele[:end], ele[:1]))


def sample_positions(length_m: float, ds_m: float = C.DS_M) -> np.ndarray:
    """Abscisses s_i = i·ds pour i < n−1, et s_{n−1} = length_m (format §4).

    n = ⌊length / ds⌋ + 1, plus 1 si un reste d'au moins LENGTH_EPS_M existe.
    """
    k = int(length_m // ds_m)
    rem = length_m - k * ds_m
    n = k + 1 if rem < C.LENGTH_EPS_M else k + 2
    s = np.arange(n, dtype=float) * ds_m
    s[-1] = length_m
    return s


def _smooth_altitude(alt_raw: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Savitzky-Golay (fenêtre 11, ordre 2, mode « interp ») sur les points ré-échantillonnés.

    Le filtre suppose un pas régulier, or le dernier point est à `length_m`, souvent à moins
    de 10 m de l'avant-dernier. Les valeurs dont la fenêtre contient ce dernier point sont donc
    recalculées comme le fait le mode « interp » (polynôme d'ordre 2 ajusté sur les 11 derniers
    points), mais avec leurs vraies abscisses. Avec un pas régulier, le résultat est identique.
    """
    alt = savgol_filter(alt_raw, C.SAVGOL_WINDOW, C.SAVGOL_ORDER, mode="interp")
    w, half = C.SAVGOL_WINDOW, C.SAVGOL_WINDOW // 2
    ss, aa = s[-w:], alt_raw[-w:]
    if not np.allclose(np.diff(ss), ss[1] - ss[0]):
        ref = ss[-1]
        coeffs = np.polyfit(ss - ref, aa, C.SAVGOL_ORDER)
        alt[-(half + 1):] = np.polyval(coeffs, ss[-(half + 1):] - ref)
    return alt


def _grade(alt: np.ndarray, s: np.ndarray, loop: bool) -> np.ndarray:
    """Pente en % par différences centrées (environ 20 m), simples aux extrémités d'un tracé ouvert.

    Boucle : différences centrées circulaires sur les n − 1 points distincts, le dernier
    point reprend la valeur du premier.
    """
    if loop:
        a, ss, length = alt[:-1], s[:-1], s[-1]
        da = np.roll(a, -1) - np.roll(a, 1)
        dsv = np.roll(ss, -1) - np.roll(ss, 1)
        dsv[0] += length
        dsv[-1] += length
        g = 100.0 * da / dsv
        return np.append(g, g[0])
    g = np.empty_like(alt)
    g[1:-1] = (alt[2:] - alt[:-2]) / (s[2:] - s[:-2])
    g[0] = (alt[1] - alt[0]) / (s[1] - s[0])
    g[-1] = (alt[-1] - alt[-2]) / (s[-1] - s[-2])
    return 100.0 * g


def _heading(x: np.ndarray, z: np.ndarray, loop: bool) -> np.ndarray:
    """Cap en degrés dans [0, 360) : atan2(Δx, −Δz) sur les voisins, puis moyenne circulaire sur 3 points."""
    if loop:
        xr, zr = x[:-1], z[:-1]
        dx, dz = np.roll(xr, -1) - np.roll(xr, 1), np.roll(zr, -1) - np.roll(zr, 1)
    else:
        dx, dz = np.empty_like(x), np.empty_like(z)
        dx[1:-1], dz[1:-1] = x[2:] - x[:-2], z[2:] - z[:-2]
        dx[0], dz[0] = x[1] - x[0], z[1] - z[0]
        dx[-1], dz[-1] = x[-1] - x[-2], z[-1] - z[-2]
    raw = np.arctan2(dx, -dz)
    ux, uy = np.sin(raw), np.cos(raw)
    half = C.HEADING_SMOOTH_POINTS // 2
    if loop:
        sx = sum(np.roll(ux, k) for k in range(-half, half + 1))
        sy = sum(np.roll(uy, k) for k in range(-half, half + 1))
    else:
        kernel = np.ones(C.HEADING_SMOOTH_POINTS)
        sx = np.convolve(ux, kernel, mode="same")    # aux extrémités : moyenne des points présents
        sy = np.convolve(uy, kernel, mode="same")
    h = np.degrees(np.arctan2(sx, sy)) % 360.0
    return np.append(h, h[0]) if loop else h


# --- chaîne complète ------------------------------------------------------------------------

def compile_route(points: list[GpxPoint], out_and_back: bool = False) -> CompiledRoute:
    """Transforme les points d'un GPX en couche route (dictionnaire de route.json). Lève CompileError."""
    if len(points) < 2:
        raise CompileError(f"trace trop courte (0 m < {C.MIN_LENGTH_M:.0f} m)")
    lat = np.array([p.lat for p in points])
    lon = np.array([p.lon for p in points])
    ele = np.array([np.nan if p.ele is None else p.ele for p in points])

    # Projection UTM de la zone du premier point, translatée : x vers l'est, z vers le sud.
    number, band, south = utm_zone_of(lat[0], lon[0])
    tr = utm_transformer(number, south)
    east, north = tr.transform(lon, lat)
    e0, n0 = float(east[0]), float(north[0])
    xy = np.column_stack((np.asarray(east) - e0, -(np.asarray(north) - n0)))

    xy, ele = _clean(xy, ele)
    length = float(_cumulative(xy)[-1]) if len(xy) > 1 else 0.0
    if length < C.MIN_LENGTH_M:
        raise CompileError(f"trace trop courte ({length:.0f} m < {C.MIN_LENGTH_M:.0f} m)")
    if np.isnan(ele).any():
        raise CompileError("altitude absente : la source MNT arrive avec le lot B2")

    if out_and_back:
        kind = "out_and_back"
        xy = np.vstack((xy, xy[-2::-1]))
        ele = np.concatenate((ele, ele[-2::-1]))
    elif math.hypot(*(xy[-1] - xy[0])) < C.LOOP_GAP_M:
        kind = "loop"
        xy, ele = _close_loop(xy, ele)
    else:
        kind = "open"
    loop = kind == "loop"

    # Ré-échantillonnage tous les 10 m de distance horizontale cumulée.
    s_in = _cumulative(xy)
    length = float(s_in[-1])
    s = sample_positions(length)
    x = np.interp(s, s_in, xy[:, 0])
    z = np.interp(s, s_in, xy[:, 1])
    alt_raw = np.interp(s, s_in, ele)
    if loop:
        x[-1], z[-1] = x[0], z[0]
    if len(s) < C.SAVGOL_WINDOW:   # impossible au-delà de 500 m, gardé par sécurité
        raise CompileError(f"trace trop courte ({length:.0f} m < {C.MIN_LENGTH_M:.0f} m)")

    alt = _smooth_altitude(alt_raw, s)
    if loop:
        alt[-1] = alt[0]

    grade = _grade(alt, s, loop)
    clamped = int(np.count_nonzero(np.abs(grade) > C.GRADE_LIMIT_PCT))
    grade = np.clip(grade, -C.GRADE_LIMIT_PCT, C.GRADE_LIMIT_PCT)
    heading = _heading(x, z, loop)

    out_lon, out_lat = tr.transform(x + e0, n0 - z, direction="INVERSE")

    def r(values, digits: int) -> list[float]:
        return [round(float(v), digits) for v in values]

    route = {
        "version": C.ROUTE_VERSION,
        "ds_m": C.DS_M,
        "n": int(len(s)),
        "length_m": round(length, 3),
        "type": kind,
        "lat": r(out_lat, 7),
        "lon": r(out_lon, 7),
        "alt_m": r(alt, 2),
        "alt_raw_m": r(alt_raw, 2),
        "x": r(x, 2),
        "z": r(z, 2),
        "grade_pct": r(grade, 2),
        "heading_deg": [round(float(h), 2) % 360.0 for h in heading],
    }
    return CompiledRoute(route=route, utm_zone=f"{number}{band}", grade_clamped_points=clamped)
