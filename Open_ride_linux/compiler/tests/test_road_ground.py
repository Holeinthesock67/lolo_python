"""Règle unique sol / route (21 novembre 2026, `road_ground.py`) : route de l'engine, sol sous la chaussée, talus
appuyés, à la génération (parcours compilés, carrés du monde ouvert, démonstrations)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from conftest import ORIGIN
from openride_compiler import constants as C
from openride_compiler import road_ground as RG
from openride_compiler import terrain
from openride_compiler.elevation import SyntheticProvider
from openride_compiler.frame import LocalFrame
from openride_compiler.pipeline import _heading
from openride_compiler.terrain import NEAR


def _bend(radius: float = 15.0, grade: float = 0.06, sag: bool = True) -> dict:
    """Route compilée (colonnes du format) : 200 m tout droit vers le nord, virage à droite de `radius` m sur 180°,
    200 m vers le sud ; points tous les 10 m comme le compilateur ; montée puis descente (creux si `sag`)."""
    pts = [(0.0, -float(d)) for d in np.arange(0.0, 200.0, C.DS_M)]
    arc = math.pi * radius
    for d in np.arange(C.DS_M - (200.0 % C.DS_M), arc, C.DS_M):
        a = math.pi - d / radius
        pts.append((radius + radius * math.cos(a), -200.0 - radius * math.sin(a)))
    pts += [(2 * radius, -200.0 + float(d)) for d in np.arange(0.0, 200.0, C.DS_M)]
    x, z = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    s = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(x), np.diff(z)))))
    mid = s[-1] / 2
    alt = 500.0 + (grade * np.abs(s - mid) if sag else grade * (mid - np.abs(s - mid)))
    n = len(x)
    return {"n": n, "ds_m": float(s[-1] / (n - 1)), "length_m": float(s[-1]), "type": "open",
            "x": x.tolist(), "z": z.tolist(), "alt_m": alt.tolist(), "lat": [0.0] * n, "lon": [0.0] * n,
            "grade_pct": [0.0] * n, "heading_deg": _heading(x, z, False).tolist()}


def test_road_curve_is_the_engine_road() -> None:
    """Même route que l'engine : `core/route.py` (traduction exacte de `route_data.gd`, vecteurs partagés)."""
    core_route = pytest.importorskip("openride_core.route")
    r = _bend()
    ref = core_route.Route(r)
    cx, cy, cz, rx, rz, i, u = RG.road_curve(r["x"], r["z"], r["alt_m"], r["heading_deg"])
    s_ref = (i + u) * r["ds_m"]
    for k in range(0, len(cx), 7):
        smp = ref.sample(min(s_ref[k], r["length_m"]))
        assert (cx[k], cy[k], cz[k]) == pytest.approx((smp.x, smp.y, smp.z), abs=1e-6)
        h = math.radians(smp.heading_deg)
        assert (rx[k], rz[k]) == pytest.approx((math.cos(h), math.sin(h)), abs=1e-9)


def test_engine_road_leaves_the_chords_in_a_bend() -> None:
    """Le constat du 21/11 : dans un virage serré et un creux, la route dessinée sort des segments droits que le
    générateur dégageait (1,23 m de côté et 0,20 m en hauteur au banc du lac d'Annecy)."""
    r = _bend(radius=12.0, grade=0.10)
    cx, cy, cz, *_ = RG.road_curve(r["x"], r["z"], r["alt_m"], r["heading_deg"])
    px, pz, pa = terrain.road_samples(r["x"], r["z"], r["alt_m"], half_width=0.0, step=0.25)
    d = np.min(np.hypot(cx[:, None] - px[None, :], cz[:, None] - pz[None, :]), axis=1)
    assert d.max() > 0.3


def _build(route: dict, relief) -> dict:
    prov = SyntheticProvider(*ORIGIN, relief)
    return terrain.build_level(route, LocalFrame.at(*ORIGIN), prov, NEAR, log=lambda m: None)


def _gaps(tiles: dict, route: dict):
    """(excès du sol sur la chaussée de l'engine, manque d'appui au pied des talus) ; positifs = défaut."""
    up, lo = RG.corridor(route["x"], route["z"], route["alt_m"], route["heading_deg"])
    gather, _, step = RG.tiles_access(tiles, NEAR.tile_m)
    hu = RG.heights(gather, step, up[0], up[1])
    hl = RG.heights(gather, step, lo[0], lo[1])
    return (hu - up[2])[np.isfinite(hu)], (lo[2] - hl)[np.isfinite(hl)]


def test_ground_never_above_the_engine_road_on_a_flank() -> None:
    """Virage en creux sur un flanc à 40 % : avant, le dégagement le long des segments droits laissait le sol sur la
    chaussée dessinée ; la règle le tient sous toute la chaussée et les bas-côtés de l'engine."""
    r = _bend(radius=12.0, grade=0.10)
    tiles = _build(r, lambda x, z: 500.0 + 0.4 * np.asarray(x))
    over, _ = _gaps(tiles, r)
    assert over.max() <= 1e-3


def test_old_chord_rule_left_ground_on_the_engine_road() -> None:
    """Le même cas avec l'ancien dégagement (segments droits, chaussée seule) : du sol sur la route dessinée."""
    r = _bend(radius=12.0, grade=0.10)
    relief = lambda x, z: 500.0 + 0.4 * np.asarray(x)   # noqa: E731
    tiles = _build(r, relief)
    raw = {k: g.copy() for k, g in tiles.items()}
    # relief fondu sans la règle, puis ancien dégagement le long des segments droits
    import openride_compiler.terrain as T
    orig = T.fit_route_ground
    try:
        T.fit_route_ground = lambda *a, **k: {"lowered": 0, "raised": 0, "left_low": 0}
        raw = _build(r, relief)
    finally:
        T.fit_route_ground = orig
    px, pz, pa = terrain.road_samples(r["x"], r["z"], r["alt_m"])
    gather, scatter, step = RG.tiles_access(raw, NEAR.tile_m)
    e = np.empty(0)
    RG.fit(gather, scatter, step, (px, pz, pa - C.ROAD_SINK_M), (e, e, e))
    over, _ = _gaps(raw, r)
    assert over.max() > 0.01            # au-delà de la limite de la route dessinée (plus de 1 cm)


def _straight(n: int = 60, x0: float = 3.0) -> dict:
    x, z = np.full(n, x0), -np.arange(n) * C.DS_M
    return {"n": n, "ds_m": C.DS_M, "length_m": float(-z[-1]), "type": "open", "x": x.tolist(), "z": z.tolist(),
            "alt_m": [500.0] * n, "lat": [0.0] * n, "lon": [0.0] * n, "grade_pct": [0.0] * n,
            "heading_deg": [0.0] * n}


def test_road_on_a_drop_rests_on_its_banks() -> None:
    """Route le long d'une marche du maillage (sommets de la route à sa hauteur, sommets suivants 6 m plus bas : sol
    creusé sous un lac, relief sans fondu) : le talus de 2,5 m de l'engine pendait dans le vide (coupes « sans appui »
    des bancs) ; la règle remonte le sol sous le pied des talus, au plus FOOT_DROP_M / RELIEF_MAX sous la route (talus
    enterré même au relief ×3), sans jamais remettre de sol sur la chaussée."""
    r = _straight(n=12, x0=12.0)
    xs = np.arange(0.0, 41.0, 10.0)
    y = np.where(np.abs(xs - 12.0) < 9.0, 500.0 - C.ROAD_SINK_M, 494.0)[None, :].repeat(13, axis=0)
    y = y.astype(float)
    up, lo = RG.corridor(r["x"], r["z"], r["alt_m"], r["heading_deg"])
    z0 = -120.0
    before = y.copy()

    def gaps(g):
        def gather(gi, gj):
            li, lj = gi, gj - int(round(z0 / 10.0))
            out = np.full(len(gi), np.nan)
            ok = (li >= 0) & (li < g.shape[1]) & (lj >= 0) & (lj < g.shape[0])
            out[ok] = g[lj[ok], li[ok]]
            return out
        hu, hl = RG.heights(gather, 10.0, up[0], up[1]), RG.heights(gather, 10.0, lo[0], lo[1])
        return np.nanmax(hu - up[2]), np.nanmax(lo[2] - hl)
    assert gaps(before)[1] > 0.5                       # pied du talus droit bien plus bas que le talus ne descend
    res = RG.fit_grid(y, 0.0, z0, 10.0, up, lo)
    over, short = gaps(y)
    assert res["raised"] > 0 and over <= 1e-3 and short <= 1e-3


def test_tile_borders_stay_identical() -> None:
    r = _bend(radius=12.0, grade=0.10)
    tiles = _build(r, lambda x, z: 500.0 + 0.4 * np.asarray(x))
    for (ix, iz), g in tiles.items():
        if (ix + 1, iz) in tiles:
            assert np.array_equal(g[:, -1], tiles[(ix + 1, iz)][:, 0])
        if (ix, iz + 1) in tiles:
            assert np.array_equal(g[-1, :], tiles[(ix, iz + 1)][0, :])


def test_core_twin_gives_the_same_ground() -> None:
    """La jumelle du core (`openride_core/road_ground.py`, terrain synthétique des démonstrations, bibliothèque
    standard) applique la même règle : mêmes points de contrôle, mêmes sommets au float près."""
    core_rg = pytest.importorskip("openride_core.road_ground")
    for name in ("ROAD_HALF_WIDTH_M", "ROAD_SINK_M", "SHOULDER_WIDTH_M", "SKIRT_DROP_M", "SKIRT_OUT_M", "RELIEF_MAX",
                 "FOOT_GAP_M", "ALONG_STEP_M", "ACROSS_STEP_M", "TILE_ROUNDS",
                 "PROJECT_STEPS", "FOOT_COVER_M", "SAME_PART_M", "COVER_MARGIN_M", "RESCUE_CLEAR_M", "RESCUE_SLOPE"):
        mine = getattr(RG, name) if hasattr(RG, name) else getattr(C, name)
        assert getattr(core_rg, name) == pytest.approx(mine), name
    r = _bend(radius=12.0, grade=0.10)
    tiles = _build(r, lambda x, z: 500.0 + 0.4 * np.asarray(x))
    import openride_compiler.terrain as T
    orig = T.fit_route_ground
    try:
        T.fit_route_ground = lambda *a, **k: {"lowered": 0, "raised": 0, "left_low": 0}
        raw = _build(r, lambda x, z: 500.0 + 0.4 * np.asarray(x))
    finally:
        T.fit_route_ground = orig
    lists = {k: g.astype(float).ravel().tolist() for k, g in raw.items()}
    up, lo = core_rg.corridor(r)
    core_rg.fit_tiles(lists, 10.0, up, lo)
    for k, g in tiles.items():
        assert np.allclose(np.asarray(lists[k]).reshape(g.shape), g, atol=2e-4), k


def _serpentine(gap: float, length: float = 200.0) -> dict:
    """Trois passages parallèles de la même route à `gap` m d'axe à axe (nord, sud, nord), demi-tours de rayon
    gap / 2, à plat à 500 m : la balade qui repasse trois ou quatre fois au même endroit (Funchal, 26/11)."""
    rad = gap / 2
    pts: list[tuple[float, float]] = []

    def line(x: float, z0: float, z1: float) -> list:
        n = int(abs(z1 - z0) // C.DS_M)
        return [(x, z0 + (z1 - z0) * k / n) for k in range(n)]

    def arc(cx: float, cz: float, a0: float, a1: float) -> list:
        n = max(int(abs(a1 - a0) * rad // 2.0), 2)
        return [(cx + rad * math.cos(a0 + (a1 - a0) * k / n), cz + rad * math.sin(a0 + (a1 - a0) * k / n))
                for k in range(n)]

    pts += line(-gap, 0.0, -length) + arc(-rad, -length, math.pi, 2 * math.pi)
    pts += line(0.0, -length, 0.0) + arc(rad, 0.0, math.pi, 0.0)
    pts += line(gap, 0.0, -length) + [(gap, -length)]
    x, z = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
    s = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(x), np.diff(z)))))
    n = len(x)
    return {"n": n, "ds_m": float(s[-1] / (n - 1)), "length_m": float(s[-1]), "type": "open",
            "x": x.tolist(), "z": z.tolist(), "alt_m": [500.0] * n, "lat": [0.0] * n, "lon": [0.0] * n,
            "grade_pct": [0.0] * n, "heading_deg": _heading(x, z, False).tolist()}


@pytest.mark.parametrize("gap", [5.0, 8.0])
def test_route_that_passes_again_keeps_its_banks(gap: float) -> None:
    """Bancs d'Almería et de Funchal (26/11) : la balade repasse au même endroit, à quelques mètres de côté et à la
    même hauteur. Chaque passage couvrait les pieds de talus des autres, qui étaient retirés : plus aucun pied ne
    demandait d'appui et la route du milieu flottait à 10 m au-dessus du sol. Un pied n'est retiré que si sa borne
    contredit celle de la chaussée qui le couvre."""
    r = _serpentine(gap)
    up, lo = RG.corridor_s(r["x"], r["z"], r["alt_m"], r["heading_deg"])

    def lowest(keep_compatible: bool) -> float:
        y = np.full((31, 9), 490.0)        # sol 10 m sous la route : x de −40 à 40, z de −250 à 50, maille de 10 m
        feet = RG.drop_covered_feet(up, lo, up[3], lo[3], keep_compatible=keep_compatible)
        RG.fit_grid(y, -40.0, -250.0, 10.0, up[:3], feet, rounds=RG.TILE_ROUNDS)

        def gather(gi, gj):
            li, lj = gi + 4, gj + 25
            out = np.full(len(gi), np.nan)
            ok = (li >= 0) & (li < 9) & (lj >= 0) & (lj < 31)
            out[ok] = y[lj[ok], li[ok]]
            return out
        hu = RG.heights(gather, 10.0, up[0], up[1])
        mid = (np.asarray(up[1]) < -40.0) & (np.asarray(up[1]) > -160.0)
        return float(np.nanmin((hu - up[2])[mid]))
    assert lowest(False) < -9.0                                   # règle d'avant : la route du milieu flotte
    assert lowest(True) >= -RG.FOOT_GAP_M - RG.SHOULDER_DROP_M - 1e-3   # sol sous la chaussée : talus appuyé


def test_road_over_another_drops_its_feet() -> None:
    """Pied de talus d'une route qui passe 6 m au-dessus d'une autre (sa borne contredit la chaussée d'en dessous) :
    toujours retiré."""
    low = _straight(n=12, x0=0.0)
    high = _straight(n=12, x0=4.0)
    high["alt_m"] = [506.0] * high["n"]
    ul, ll = RG.corridor_s(low["x"], low["z"], low["alt_m"], low["heading_deg"])
    uh, lh = RG.corridor_s(high["x"], high["z"], high["alt_m"], high["heading_deg"])
    up = [np.concatenate([a, b]) for a, b in zip(ul, uh)]
    up[3] = np.concatenate([ul[3], uh[3] + 1e7])
    lo = [np.concatenate([a, b]) for a, b in zip(ll, lh)]
    lo[3] = np.concatenate([ll[3], lh[3] + 1e7])
    fx, _, fl = RG.drop_covered_feet(up, lo, up[3], lo[3])
    fx, fl = np.asarray(fx), np.asarray(fl)
    foot = RG.FOOT_OFFSET_M
    assert not ((np.abs(fx - (4.0 - foot)) < 0.1) & (fl > 505.0)).any()   # pied gauche de la route haute : retiré
    assert ((np.abs(fx - foot) < 0.1) & (fl < 500.0)).any()      # pied droit de la basse, sous la haute : gardé


def test_core_twin_keeps_the_same_feet_on_a_route_that_passes_again() -> None:
    core_rg = pytest.importorskip("openride_core.road_ground")
    r = _serpentine(5.0)
    up, lo = RG.corridor_s(r["x"], r["z"], r["alt_m"], r["heading_deg"])
    mine = RG.drop_covered_feet(up, lo, up[3], lo[3])
    cu, cl, us, ls = core_rg.corridor_s(r)
    theirs = core_rg.drop_covered_feet(cu, cl, us, ls)
    assert abs(len(theirs) - len(mine[0])) <= 0.02 * len(mine[0])
    assert len(mine[0]) > 0.9 * len(lo[0])          # passages à la même hauteur : pieds presque tous gardés
