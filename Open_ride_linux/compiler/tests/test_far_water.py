"""Lot EA2 : grands lacs écrits avec les tuiles lointaines de 5 km du monde ouvert, sol lointain abaissé."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

from openride_compiler import constants as C
from openride_compiler.worldgen import squares
from openride_compiler.worldgen.osmdb import OsmDb, OsmDbWriter
from openride_compiler.worldgen.squares import FarKey, SquareKey, generate_far, generate_square
from openride_compiler.worldgen.store import WorldCache

ZONE = "31T"
FRAME = squares.zone_frame(ZONE)
E_MID, N_MID = 683_000, 4_892_500      # centre du lac, dans la tuile lointaine (136, 978)
LEVEL = 200.0


def lonlat(e, n):
    lat, lon = FRAME.to_latlon(np.array([e]), np.array([-n]))
    return float(lon[0]), float(lat[0])


class BowlProvider:
    """MNT aplati sur un disque de 900 m de rayon (lac), berge qui monte de 6 m en 30 m, plateau à 230 m au loin."""

    name = "bol-ea2"
    native_resolution_m = 30.0

    def __init__(self) -> None:
        self.calls = 0

    def elevations(self, lat, lon):
        self.calls += 1
        x, z = FRAME.to_xz(np.asarray(lat, float), np.asarray(lon, float))
        d = np.hypot(x - E_MID, z + N_MID)
        return LEVEL + np.clip((d - 900.0) / 30.0, 0.0, 1.0) * 6.0 + np.clip((d - 3000.0) / 500.0, 0.0, 1.0) * 24.0


def rect_ll(e0, n0, e1, n1):
    return [lonlat(e0, n0), lonlat(e1, n0), lonlat(e1, n1), lonlat(e0, n1), lonlat(e0, n0)]


def make_db(tmp_path, pieces=True, pond=True) -> OsmDb:
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/ea2")
    if pieces:
        # lac de 1,9 km² coupé en deux morceaux de moins de 1 km² au bord d'une tuile vectorielle (E = E_MID + 120)
        w.add_area("v0", "water", {"natural": "water", "water": "lake"},
                   rect_ll(E_MID - 800, N_MID - 600, E_MID + 120, N_MID + 600))
        w.add_area("v1", "water", {"natural": "water", "water": "lake"},
                   rect_ll(E_MID + 120, N_MID - 600, E_MID + 800, N_MID + 600))
    if pond:
        # étang de 0,04 km², seul : pas dessiné au loin
        w.add_area("p0", "water", {"natural": "water", "water": "pond"},
                   rect_ll(E_MID + 1500, N_MID + 1500, E_MID + 1700, N_MID + 1700))
    w.finish(osm_date="2026-11-16T00:00:00Z")
    return OsmDb(tmp_path / "osm.sqlite")


def cache(path) -> WorldCache:
    return WorldCache(path, 10**9, log=lambda _m: None)


def grid(path) -> np.ndarray:
    return np.frombuffer(path.read_bytes(), dtype="<f4").reshape(101, 101)


def far_key() -> FarKey:
    return FarKey(ZONE, E_MID // 5000, N_MID // 5000)


def sample(key: FarKey, e: float, n: float) -> tuple[int, int]:
    """(ligne j, colonne i) de l'échantillon lointain le plus proche de (E, N)."""
    x0, z0 = key.corner
    return int(round((-n - z0) / 50.0)), int(round((e - x0) / 50.0))


def test_cut_lake_is_one_big_lake_drawn_far_with_sunk_ground(tmp_path) -> None:
    db, c, pv, key = make_db(tmp_path), cache(tmp_path / "cache"), BowlProvider(), far_key()
    path = generate_far(key, pv, c, db)
    water = c.far_water_path(ZONE, key.ix, key.i_n)
    assert water.is_file()
    lv, y = grid(water), grid(path)
    j, i = sample(key, E_MID, N_MID)
    assert lv[j, i] == pytest.approx(LEVEL)                         # premier morceau
    j2, i2 = sample(key, E_MID + 500, N_MID)
    assert lv[j2, i2] == pytest.approx(LEVEL)                       # second morceau : même niveau
    assert y[j, i] == pytest.approx(LEVEL - C.WATER_SINK_M)         # sol abaissé sous l'eau (règle EA1)
    jp, ip = sample(key, E_MID + 1600, N_MID + 1600)
    assert np.isnan(lv[jp, ip])                                     # étang trop petit
    jb, ib = sample(key, E_MID, N_MID + 2000)
    assert np.isnan(lv[jb, ib]) and y[jb, ib] > LEVEL               # berge
    wet = np.isfinite(lv)
    assert wet.sum() * 50 * 50 == pytest.approx(1600 * 1200, rel=0.1)
    assert np.all(y[wet] <= lv[wet] - C.WATER_SINK_M + 1e-3)


def test_far_level_matches_the_near_squares(tmp_path) -> None:
    db, c, pv, key = make_db(tmp_path), cache(tmp_path / "cache"), BowlProvider(), far_key()
    generate_far(key, pv, c, db)
    lv = grid(c.far_water_path(ZONE, key.ix, key.i_n))
    sq = generate_square(SquareKey(ZONE, E_MID // 1000, N_MID // 1000), db, pv, c)
    near_levels = {a["level_y"] for a in json.loads((sq / "water.json").read_text())["areas"]}
    assert near_levels and set(np.unique(lv[np.isfinite(lv)]).round(2)) <= near_levels


def test_small_water_only_writes_relief_alone(tmp_path) -> None:
    db, c, pv, key = make_db(tmp_path, pieces=False), cache(tmp_path / "cache"), BowlProvider(), far_key()
    path = generate_far(key, pv, c, db)
    assert not c.far_water_path(ZONE, key.ix, key.i_n).exists()
    gx, gz = squares.grid_xz(key, 50)
    lat, lon = FRAME.to_latlon(gx.ravel(), gz.ravel())
    assert np.array_equal(grid(path).ravel(), pv.elevations(lat, lon).astype("<f4"))   # relief intact


def test_one_piece_under_the_threshold_is_not_a_big_lake(tmp_path) -> None:
    w = OsmDbWriter(tmp_path / "osm.sqlite", "test", "test/ea2")
    w.add_area("v0", "water", {"natural": "water", "water": "lake"},
               rect_ll(E_MID - 800, N_MID - 600, E_MID + 120, N_MID + 600))   # 1,1 km² : grand lac à lui seul
    w.add_area("v1", "water", {"natural": "water", "water": "lake"},
               rect_ll(E_MID - 300, N_MID - 300, E_MID + 300, N_MID + 300))   # 0,36 km², aucun sommet à moins de 5 m de v0
    w.add_area("s0", "water", {"natural": "water", "water": "lake"},
               rect_ll(E_MID + 300, N_MID + 1200, E_MID + 1200, N_MID + 1900))  # 0,63 km², à 600 m : seul
    w.finish(osm_date="2026-11-16T00:00:00Z")
    lakes = squares.far_lakes(far_key(), OsmDb(tmp_path / "osm.sqlite"), BowlProvider(), FRAME)
    assert sorted(a["id"] for a in lakes) == ["v0"]


def test_partial_water_is_redone_and_cache_versions(tmp_path) -> None:
    db, c, pv, key = make_db(tmp_path), cache(tmp_path / "cache"), BowlProvider(), far_key()
    generate_far(key, pv, c, db, water_complete=False)
    assert c.get(key.cache_key).versions["water"] == "partial"
    pv.calls = 0
    generate_far(key, pv, c, db)                     # données complètes : refaite
    assert pv.calls > 0 and c.get(key.cache_key).versions["water"] == "ok"
    pv.calls = 0
    generate_far(key, pv, c, db)
    assert pv.calls == 0                             # puis gardée
    assert c.get(key.cache_key).versions["far_water"] == squares.FAR_WATER_VERSION


def test_link_and_eviction_carry_the_water_grid(tmp_path) -> None:
    db, c, pv, key = make_db(tmp_path), cache(tmp_path / "cache"), BowlProvider(), far_key()
    generate_far(key, pv, c, db)
    water = c.far_water_path(ZONE, key.ix, key.i_n)
    session = tmp_path / "ow.world"
    e0, n0 = key.ix * 5000, (key.i_n + 1) * 5000     # tuile lointaine (0, 0) de la séance
    assert c.link_far(session, ZONE, e0, n0, 0, 0) is not None
    link = session / "water" / "far" / "tile_0_0.f32"
    assert os.path.realpath(link) == os.path.realpath(water)
    c._delete(c.get(key.cache_key))
    assert not water.exists() and not c.far_path(ZONE, key.ix, key.i_n).exists()
