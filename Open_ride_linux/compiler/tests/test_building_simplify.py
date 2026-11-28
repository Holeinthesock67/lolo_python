"""Lot MP1 : maisons des villages en pente, exclure ou simplifier (building_simplify.py)."""
from __future__ import annotations

import json

import numpy as np
import pytest
from openride_compiler import building_simplify as BS
from openride_compiler.osm_layers import OsmLayersResult, signed_area


def _rect(x0, z0, x1, z1):
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


def _house(bid, outer, base_y=0.0, building="house", holes=None):
    return {"id": bid, "outer": outer, "holes": holes or [], "base_y": base_y, "height_m": 6.0, "roof": "flat",
            "hint": {"building": building, "colour": None}}


def flat(xs, zs):
    return np.zeros(len(xs))


def slope(grade):
    """Pente réelle `grade` (m/m) le long de x."""
    return lambda xs, zs: np.asarray(xs, float) * grade


NO_WATER = BS.WaterIndex()


def _res(chunks, water=None):
    return OsmLayersResult(buildings_chunks=chunks, vegetation_chunks={}, poi_chunks={}, water_chunks=water or {},
                           roads_chunks={}, buildings_count=sum(len(v) for v in chunks.values()),
                           buildings_ignored=0, vegetation_count=0, vegetation_ignored=0, poi_count=0,
                           water_lines_count=0, water_areas_count=0, water_ignored=0, roads_count=0, osm_date=None)


FAR_ROUTE = {"x": [0.0, 1000.0], "z": [-500.0, -500.0], "alt_m": [0.0, 0.0]}


# --- géométrie ------------------------------------------------------------------------------------------

def test_oriented_rect_of_rotated_rectangle():
    a = np.radians(30)
    ux, uz = np.cos(a), np.sin(a)
    pts = []
    for u, v in ((-10, -4), (10, -4), (10, 4), (-10, 4)):
        pts.append([u * ux - v * uz + 5, u * uz + v * ux + 7])
    r = BS.oriented_rect(pts)
    assert r.length == pytest.approx(20, abs=1e-6)
    assert r.width == pytest.approx(8, abs=1e-6)
    assert (r.cx, r.cz) == pytest.approx((5, 7))
    assert BS.fill_ratio(pts, r) == pytest.approx(1.0)


def test_l_shape_fill_below_pitched_threshold():
    l_shape = [[0, 0], [12, 0], [12, 5], [5, 5], [5, 12], [0, 12]]
    r = BS.oriented_rect(l_shape)
    assert BS.fill_ratio(l_shape, r) < BS.FILL_MIN


# --- règles ---------------------------------------------------------------------------------------------

def test_flat_simple_house_is_kept_untouched():
    b = _house("w1", _rect(0, 0, 10, 8))
    d = BS.decide(b, flat, NO_WATER)
    assert d.action == "garde" and d.kept == [b]


def test_non_house_is_never_touched():
    church = _house("c", [[0, 0], [30, 0], [30, 5], [5, 5], [5, 30], [0, 30]], building="church")
    d = BS.decide(church, slope(0.2), NO_WATER)
    assert d.action == "garde" and d.kept == [church]


def test_l_house_becomes_rectangle_with_same_area():
    l_shape = [[0, 0], [12, 0], [12, 5], [5, 5], [5, 12], [0, 12]]
    d = BS.decide(_house("l", l_shape), flat, NO_WATER)
    assert d.action == "rectangle"
    ring = d.kept[0]["outer"]
    assert len(ring) == 4 and signed_area(ring) > 0
    assert abs(signed_area(ring)) == pytest.approx(abs(signed_area(l_shape)), rel=0.02)
    assert BS.fill_ratio(ring, BS.oriented_rect(ring)) == pytest.approx(1.0, abs=1e-3)
    assert d.kept[0]["holes"] == []


def test_too_complicated_shape_is_removed():
    # Croix fine (bras de 1 m sur 12 m) : remplit moins de la moitié de son rectangle
    cross = [[5.5, 0], [6.5, 0], [6.5, 5.5], [12, 5.5], [12, 6.5], [6.5, 6.5], [6.5, 12], [5.5, 12], [5.5, 6.5],
             [0, 6.5], [0, 5.5], [5.5, 5.5]]
    assert BS.fill_ratio(cross, BS.oriented_rect(cross)) < BS.FILL_DROP
    d = BS.decide(_house("x", cross), flat, NO_WATER)
    assert d.action == "retire" and d.reason == BS.REASON_SHAPE


def test_high_socle_is_removed_and_small_one_kept():
    # 10 m de large : 4 % → 0,4 m réels × 2,5 = 1,0 m affichés (gardée) ; 10 % → 2,5 m affichés (retirée)
    ok = BS.decide(_house("a", _rect(0, 0, 10, 8)), slope(0.04), NO_WATER)
    assert ok.action == "garde"
    bad = BS.decide(_house("b", _rect(0, 0, 10, 8)), slope(0.10), NO_WATER)
    assert bad.action == "retire" and bad.reason == BS.REASON_SOCLE


def test_socle_depends_on_display_relief():
    b = _house("a", _rect(0, 0, 10, 8))
    assert BS.decide(b, slope(0.10), NO_WATER, k=1.0).action == "garde"
    assert BS.decide(b, slope(0.10), NO_WATER, k=2.5).action == "retire"


def test_long_row_on_slope_is_split_into_steps():
    # Rangée de 50 m × 8 m sur 4 % le long de x : 2 m de dénivelé → 5 paliers de 10 m, chacun à sa hauteur
    b = _house("row", _rect(0, 0, 50, 8), base_y=0.0)
    d = BS.decide(b, slope(0.045), NO_WATER)
    assert d.action == "paliers"
    assert len(d.kept) == 5
    bases = sorted(p["base_y"] for p in d.kept)
    assert bases[0] == pytest.approx(0.0, abs=0.05)
    assert bases[-1] == pytest.approx(40 * 0.045, abs=0.05)
    assert len({p["id"] for p in d.kept}) == 5
    total = sum(abs(signed_area(p["outer"])) for p in d.kept)
    assert total == pytest.approx(400.0, rel=0.01)


def test_long_complicated_row_on_slope_is_removed():
    l_row = [[0, 0], [50, 0], [50, 8], [10, 8], [10, 30], [0, 30]]
    d = BS.decide(_house("lr", l_row), slope(0.05), NO_WATER)
    assert d.action == "retire" and d.reason == BS.REASON_LONG


def test_long_row_too_steep_even_in_steps_is_removed():
    d = BS.decide(_house("row", _rect(0, 0, 50, 8)), slope(0.20), NO_WATER)
    assert d.action == "retire" and d.reason == BS.REASON_LONG


def test_house_at_lake_shore_is_removed():
    lake = {0: {"lines": [], "areas": [{"id": "l", "kind": "lake", "level_y": 0.0,
                                         "outer": _rect(20, -50, 200, 50), "holes": []}]}}
    w = BS.WaterIndex.from_chunks(lake)
    assert BS.decide(_house("in", _rect(25, 0, 35, 8)), flat, w).reason == BS.REASON_WATER
    assert BS.decide(_house("near", _rect(8, 0, 18, 8)), flat, w).reason == BS.REASON_WATER
    assert BS.decide(_house("far", _rect(0, 0, 10, 8)), flat, w).action == "garde"


def test_house_on_stream_is_removed():
    stream = {0: {"lines": [{"id": "s", "kind": "stream", "width_m": 2.0,
                             "points": [[5, -20, 0], [5, 20, 0]]}], "areas": []}}
    w = BS.WaterIndex.from_chunks(stream)
    assert BS.decide(_house("s", _rect(0, 0, 10, 8)), flat, w).reason == BS.REASON_WATER
    assert BS.decide(_house("ok", _rect(20, 0, 30, 8)), flat, w).action == "garde"


# --- passe complète et rapport --------------------------------------------------------------------------

def test_simplify_buildings_counts_and_report(tmp_path):
    houses = [_house(f"h{i}", _rect(i * 15, 0, i * 15 + 10, 8)) for i in range(10)]
    church = _house("c", _rect(0, 30, 20, 50), building="church")
    res = _res({0: houses + [church]})
    rep = BS.simplify_buildings(res, FAR_ROUTE, flat, lambda x, z: 0)
    assert rep.houses == 10 and rep.kept == 10 and rep.removed_total == 0
    assert res.buildings_count == 11
    assert len(rep.villages) == 1 and not rep.villages[0]["alerte"]
    BS.write_report(tmp_path, rep)
    data = json.loads((tmp_path / BS.REPORT_FILE).read_text(encoding="utf-8"))
    assert data["lot"] == "MP1" and data["maisons"] == 10 and data["villages_en_alerte"] == 0


def test_village_guard_flags_emptied_village():
    # Village de 10 maisons sur pente forte : toutes retirées → alerte (> 30 %)
    houses = [_house(f"h{i}", _rect(i * 15, 0, i * 15 + 10, 8), base_y=i * 15 * 0.15) for i in range(10)]
    res = _res({0: houses})
    rep = BS.simplify_buildings(res, FAR_ROUTE, slope(0.15), lambda x, z: 0)
    assert rep.removed[BS.REASON_SOCLE] == 10
    assert res.buildings_count == 0 and res.buildings_chunks == {}
    assert len(rep.alerts) == 1 and rep.alerts[0]["part"] == 1.0
    assert any("ALERTE" in ln for ln in rep.lines())


def test_small_hamlet_is_not_a_village():
    houses = [_house(f"h{i}", _rect(i * 15, 0, i * 15 + 10, 8)) for i in range(BS.VILLAGE_MIN - 1)]
    rep = BS.simplify_buildings(_res({0: houses}), FAR_ROUTE, flat, lambda x, z: 0)
    assert rep.villages == []


def test_houses_on_drawn_road_are_counted_not_removed():
    # La route passe à 1 m du mur d'une maison : l'engine (CD1) la retire, le compilateur la compte
    route = {"x": [-50.0, 100.0], "z": [-1.0, -1.0], "alt_m": [0.0, 0.0]}
    houses = [_house("near", _rect(0, 0, 10, 8)), _house("far", _rect(0, 30, 10, 38))]
    res = _res({0: houses})
    rep = BS.simplify_buildings(res, route, flat, lambda x, z: 0)
    assert rep.road_removed == 1
    assert res.buildings_count == 2


def test_split_pieces_go_to_their_own_chunk():
    b = _house("row", _rect(0, 0, 50, 8))
    res = _res({0: [b]})
    rep = BS.simplify_buildings(res, FAR_ROUTE, slope(0.045), lambda x, z: 0 if x < 25 else 1)
    assert rep.split == 1 and rep.split_pieces == 5
    assert sorted(res.buildings_chunks) == [0, 1]
    assert res.buildings_count == 5
