"""Lot B1 : chaîne de traitement (critères 2 à 7 et 11)."""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from conftest import circle, gpx_text, straight_north, to_latlon
from openride_compiler.errors import CompileError
from openride_compiler.gpx import GpxPoint, parse_gpx
from openride_compiler.pipeline import compile_route, sample_positions, utm_zone_of


def points(x, z, alt=None):
    lat, lon = to_latlon(x, z)
    return parse_gpx(gpx_text(lat, lon, None if alt is None else list(alt)).encode())


def heading_err(h, ref):
    return abs((h - ref + 180.0) % 360.0 - 180.0)


# Critère 2 : ligne droite ------------------------------------------------------------------

def test_straight_line_north_5pct():
    c = compile_route(points(*straight_north()))
    r = c.route
    assert r["type"] == "open"
    assert abs(r["length_m"] - 2000.0) <= 2.0
    assert r["n"] == 201
    assert all(len(r[k]) == 201 for k in ("lat", "lon", "alt_m", "alt_raw_m", "x", "z",
                                           "grade_pct", "heading_deg"))
    assert all(abs(g - 5.0) <= 0.1 for g in r["grade_pct"][1:-1])
    assert all(heading_err(h, 0.0) <= 0.5 for h in r["heading_deg"])
    assert all(b < a for a, b in zip(r["z"], r["z"][1:]))
    assert r["x"][0] == 0.0 and r["z"][0] == 0.0
    assert c.utm_zone == "32T"
    assert c.grade_clamped_points == 0


def test_straight_line_samples_every_10m():
    r = compile_route(points(*straight_north(length=1235.0))).route
    s = np.hypot(np.array(r["x"]), np.array(r["z"]))
    assert r["n"] == 125
    assert np.allclose(s[:-1], np.arange(124) * 10.0, atol=0.02)
    assert abs(s[-1] - r["length_m"]) < 0.02


def test_east_heading_and_ranges():
    s = np.arange(0.0, 1500.1, 7.0)
    r = compile_route(points(s, np.zeros_like(s), 300.0 + 0 * s)).route
    assert all(heading_err(h, 90.0) <= 0.5 for h in r["heading_deg"])
    assert all(0.0 <= h < 360.0 for h in r["heading_deg"])
    assert all(x2 > x1 for x1, x2 in zip(r["x"], r["x"][1:]))


def test_sample_positions():
    assert len(sample_positions(2000.0)) == 201
    assert len(sample_positions(2000.0004)) == 201
    s = sample_positions(2005.0)
    assert len(s) == 202 and s[-1] == 2005.0 and s[-2] == 2000.0


# Critère 3 : boucle ------------------------------------------------------------------------

def test_circle_is_loop_and_closed():
    r = compile_route(points(*circle())).route
    assert r["type"] == "loop"
    for k in ("x", "z", "lat", "lon", "alt_m", "grade_pct", "heading_deg"):
        assert r[k][-1] == r[k][0], k
    assert abs(r["length_m"] - 2 * math.pi * 1000) < 10.0
    # cap horaire régulier : départ vers l'est (le cercle tourne vers la droite)
    assert heading_err(r["heading_deg"][0], 90.0) < 1.0


# Critère 4 et 5 : refus ----------------------------------------------------------------------

def test_short_trace_refused():
    with pytest.raises(CompileError, match=r"trace trop courte \(400 m < 500 m\)"):
        compile_route(points(*straight_north(length=400.0)))


def test_missing_altitude_refused():
    x, z, _ = straight_north()
    with pytest.raises(CompileError, match="altitude absente : la source MNT arrive avec le lot B2"):
        compile_route(points(x, z))


def test_partial_altitude_refused():
    x, z, alt = straight_north()
    alt = list(alt)
    alt[100] = None
    with pytest.raises(CompileError, match="altitude absente"):
        compile_route(points(x, z, alt))


def test_single_point_refused():
    with pytest.raises(CompileError, match="trace trop courte"):
        compile_route([GpxPoint(45.0, 6.0, 100.0)])


# Critère 6 : doublons et arrêts --------------------------------------------------------------

def test_duplicates_and_stops_do_not_change_length():
    x, z, alt = straight_north()
    ref = compile_route(points(x, z, alt)).route
    xs, zs, alts = list(x), list(z), list(alt)
    # 50 points identiques (arrêt) au milieu, plus des doublons isolés et du bruit sous le mètre
    k = 200
    xs[k:k] = [xs[k]] * 50
    zs[k:k] = [zs[k]] * 50
    alts[k:k] = [alts[k]] * 50
    for j in (10, 60, 300):
        xs.insert(j, xs[j]); zs.insert(j, zs[j]); alts.insert(j, alts[j])
    xs.insert(120, xs[120] + 0.3); zs.insert(120, zs[120] - 0.2); alts.insert(120, alts[120])
    r = compile_route(points(xs, zs, alts)).route
    assert abs(r["length_m"] - ref["length_m"]) <= 1.0


# Critère 7 : pente limitée -------------------------------------------------------------------

def test_step_is_clamped():
    s = np.arange(0.0, 1000.1, 10.0)
    alt = np.where(s >= 500.0, 130.0, 100.0)       # marche de 30 m sur 10 m
    c = compile_route(points(np.zeros_like(s), -s, alt))
    g = c.route["grade_pct"]
    assert c.grade_clamped_points > 0
    assert max(g) == 25.0
    assert all(-25.0 <= v <= 25.0 for v in g)
    assert c.route["alt_raw_m"][50] == 130.0


# Aller-retour --------------------------------------------------------------------------------

def test_out_and_back():
    x, z, alt = straight_north(length=1000.0)
    r = compile_route(points(x, z, alt), out_and_back=True).route
    assert r["type"] == "out_and_back"
    assert abs(r["length_m"] - 2000.0) < 0.01
    assert r["n"] == 201
    assert abs(r["x"][-1]) < 0.01 and abs(r["z"][-1]) < 0.01
    assert all(abs(v - 5.0) <= 0.1 for v in r["grade_pct"][5:90])
    assert all(abs(v + 5.0) <= 0.1 for v in r["grade_pct"][110:195])
    assert heading_err(r["heading_deg"][150], 180.0) < 0.5


def test_southern_hemisphere_zone():
    assert utm_zone_of(-33.9, 18.4) == (34, "H", True)
    assert utm_zone_of(45.09, 6.06) == (32, "T", False)
    with pytest.raises(CompileError):
        utm_zone_of(85.0, 0.0)


# Critère 11 : performance --------------------------------------------------------------------

def test_30km_compiles_under_10s():
    s = np.arange(0.0, 30000.0, 1.0)                     # 30 000 points d'entrée
    x = 300.0 * np.sin(s / 3000.0)
    z = -s
    alt = 800.0 + 600.0 * np.sin(s / 9000.0)
    pts = points(x, z, alt)
    t0 = time.perf_counter()
    r = compile_route(pts).route
    assert time.perf_counter() - t0 < 10.0
    assert 30000.0 < r["length_m"] < 30100.0


# Lissage : dernier segment plus court que 10 m ----------------------------------------------

@pytest.mark.parametrize("length", [2000.97, 2000.05, 2009.5])
def test_short_last_segment_does_not_distort_grade(length):
    s = np.append(np.arange(0.0, length - 1.0, 3.0), length)
    r = compile_route(points(np.zeros_like(s), -s, 1000.0 - 0.065 * s)).route
    assert abs(r["length_m"] - length) < 0.01
    assert all(abs(g + 6.5) <= 0.1 for g in r["grade_pct"]), r["grade_pct"][-4:]
    assert abs(r["alt_m"][-1] - (1000.0 - 0.065 * length)) < 0.02


def test_smoothing_matches_scipy_on_regular_grid():
    from scipy.signal import savgol_filter

    from openride_compiler.pipeline import _smooth_altitude
    s = np.arange(0.0, 501.0, 10.0)
    raw = 100.0 + 5.0 * np.sin(s / 37.0) + 0.01 * s ** 1.5
    assert np.array_equal(_smooth_altitude(raw, s), savgol_filter(raw, 11, 2, mode="interp"))
    s2 = s.copy(); s2[-1] = 493.0
    out = _smooth_altitude(raw, s2)
    assert np.array_equal(out[:-6], savgol_filter(raw, 11, 2, mode="interp")[:-6])
