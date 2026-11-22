"""Garde-fou d'altitude du monde ouvert (21 novembre 2026) : défauts des sources d'altitude corrigés à la génération.

Contrôle bloquant de la CI : sur un relief de synthèse qui porte les défauts d'un modèle de surface (bosses de toits
et d'arbres sur la route, valeurs absentes, pic isolé, marche), la route engagée du monde ouvert n'a ni pente au-delà
de ± 15 %, ni changement de pente au-delà de 4 % par pas de 10 m, aux nœuds compris ; sans le garde-fou, le même
monde échoue (le contrôle voit bien le défaut).
"""

from __future__ import annotations

import numpy as np
import pytest

from openride_compiler.elevation import SyntheticProvider
from openride_compiler.worldgen import altitude_guard as AG
from openride_compiler.worldgen import edge_profile as EP
from openride_compiler.worldgen.graph import Edge

from test_worldgen_process import E_REF, N_REF, FRAME, impasse_db, line_db, lonlat, open_msg, session  # noqa: E402

S = np.arange(0.0, 301.0, 10.0)


def hump(s: np.ndarray, center: float, height: float, width: float) -> np.ndarray:
    return height * np.exp(-0.5 * ((s - center) / width) ** 2)


# --- règle sur un profil seul ------------------------------------------------------------------------------------

def test_conforming_profile_is_left_untouched() -> None:
    alt = 400.0 + 0.06 * S + 3.0 * np.sin(S / 150.0)
    out, st = AG.guard(alt, S)
    assert np.array_equal(out, alt) and st.moved == 0 and st.left == 0


def test_surface_hump_is_flattened_within_bounds() -> None:
    """Constat du banc ea1_lac : bosse de 7 m sur 118 m (0 → 21 % en 10 m, puis −17 %) entre deux nœuds."""
    s = np.append(np.arange(0.0, 111.0, 10.0), 118.4)
    alt = 450.8 + 3.4 * s / s[-1] + hump(s, 60.0, 7.0, 25.0)
    assert any(kind == "cassure" for _s, kind, _v in AG.check(alt, s))
    out, st = AG.guard(alt, s, 0.0, 2.0)
    assert out[0] == alt[0] and out[-1] == alt[-1]                     # nœuds inchangés
    assert not AG.check(out, s, 0.0, 2.0) and st.left == 0
    g = 100.0 * np.diff(out) / np.diff(s)
    assert abs(g[0]) <= AG.END_TOL_PCT + 0.05                          # départ à la pente du nœud
    assert float(np.max(np.abs(np.diff(g)))) <= AG.CURVE_MAX_PCT + 0.05


@pytest.mark.parametrize("defect", ["marche", "pic", "creux", "rampe"])
def test_steps_spikes_holes_and_ramps(defect: str) -> None:
    alt = 300.0 + 0.03 * S
    if defect == "marche":
        alt = alt + np.where(S >= 150.0, 6.0, 0.0)
    elif defect == "pic":
        alt = alt + np.where(S == 150.0, 30.0, 0.0)
    elif defect == "creux":
        alt = alt - np.where((S >= 140.0) & (S <= 160.0), 12.0, 0.0)
    else:
        alt = alt + np.where(S >= 150.0, 0.21 * (S - 150.0), 0.0)        # 0 → 21 % d'un pas à l'autre
    assert AG.check(alt, S)
    out, st = AG.guard(alt, S)
    assert not AG.check(out, S) and st.left == 0 and st.moved > 0
    assert out[0] == alt[0] and out[-1] == alt[-1]


def test_repair_fills_missing_values_and_isolated_spikes() -> None:
    raw = 200.0 + 0.02 * S
    bad = raw.copy()
    bad[5], bad[6], bad[12] = np.nan, -32767.0, -9999.0
    bad[20] += 40.0                                                    # pic isolé (toit, pylône)
    fixed, st = AG.repair(bad)
    assert st.repaired == 3 and st.spikes == 1
    assert np.allclose(fixed, raw, atol=0.5)
    with pytest.raises(ValueError):
        AG.repair(np.full(5, np.nan))


def test_too_steep_on_average_is_never_made_worse() -> None:
    """Arête plus raide en moyenne que 15 % (ruelle) : pente permise = pente moyenne, profil régulier gardé."""
    s = np.arange(0.0, 61.0, 10.0)
    alt = 100.0 + 0.32 * s
    out, st = AG.guard(alt, s, 20.0, 20.0)
    before = len(AG.check(alt, s, 20.0, 20.0, grade_max_pct=33.0))
    assert len(AG.check(out, s, 20.0, 20.0, grade_max_pct=33.0)) <= before
    assert np.all(np.abs(np.diff(np.diff(out) / 10.0)) <= AG.CURVE_MAX_PCT / 100.0 + 1e-6)


def test_node_grade_follows_relief_gradient() -> None:
    assert AG.node_grade(0.05, 0.0, 10.0, 0.0) == pytest.approx(5.0)
    assert AG.node_grade(0.05, 0.0, -3.0, 0.0) == pytest.approx(-5.0)
    assert AG.node_grade(0.05, 0.02, 0.0, 1.0) == pytest.approx(2.0)


# --- profil des arêtes : deux arêtes qui se suivent ont la même pente au nœud -------------------------------------

def _edge(eid: str, x0: float, x1: float, a: int, b: int) -> Edge:
    pts = [(x0, 0.0), ((x0 + x1) / 2, 0.0), (x1, 0.0)]
    return Edge(eid, a, b, a, b, pts, abs(x1 - x0), "t", 0, [], None, [a, b])


def test_consecutive_edges_meet_without_kink() -> None:
    lat, lon = FRAME.to_latlon(np.array([0.0]), np.array([0.0]))

    def relief(x, z):
        x = np.asarray(x, dtype=float)
        return 500.0 + 0.08 * x + hump(x, 990.0, 6.0, 30.0) + 0 * np.asarray(z)   # bosse juste avant le nœud

    prov = SyntheticProvider(float(lat[0]), float(lon[0]), relief)
    na = EP.NodeAltitudes(prov, prov.frame)
    p1 = EP.edge_profile(_edge("1:0", 0.0, 1000.0, 1, 2), prov, prov.frame, na)
    p2 = EP.edge_profile(_edge("2:0", 1000.0, 2000.0, 2, 3), prov, prov.frame, na)
    joined = EP.concat([p1, p2])
    assert not AG.check(joined["alt_m"], joined["s"])
    assert p1.guard.moved > 0 and p1.versions["altitude_guard"] == AG.GUARD_VERSION


def _chain_edge(eid: str, x0: float, x1: float, a: int, b: int) -> Edge:
    xs = np.linspace(x0, x1, max(2, int(abs(x1 - x0) // 40) + 2))
    return Edge(eid, a, b, a, b, [(float(v), 0.0) for v in xs], abs(x1 - x0), "t", 0, [], None, [a, b])


@pytest.mark.parametrize("center,height,width", [(108.0, 5.0, 8.0), (118.0, 3.0, 5.0), (122.0, 5.0, 8.0)])
def test_short_edge_between_close_nodes_has_no_grave_kink(center, height, width) -> None:
    """Constat du banc de #961 (22 novembre, s = 5 350 m) : arête de 9,9 m entre deux nœuds, trop courte pour être
    façonnée ; une haie ou un arbre du modèle de surface près du premier nœud donnait +6,5 % au nœud, −10,5 % sur la
    corde et −12,8 % au nœud suivant (cassure de 17 %). Le plan du relief ajusté aux nœuds accorde les deux nœuds."""
    lat, lon = FRAME.to_latlon(np.array([0.0]), np.array([0.0]))

    def relief(x, z):
        x, z = np.asarray(x, dtype=float), np.asarray(z, dtype=float)
        return 450.0 + 0.03 * x + hump(x, center, height, width) * np.exp(-0.5 * (z / width) ** 2)

    prov = SyntheticProvider(float(lat[0]), float(lon[0]), relief)
    na = EP.NodeAltitudes(prov, prov.frame)
    parts = [EP.edge_profile(_chain_edge("1:0", 0.0, 116.6, 1, 2), prov, prov.frame, na),
             EP.edge_profile(_chain_edge("2:0", 116.6, 126.5, 2, 3), prov, prov.frame, na),
             EP.edge_profile(_chain_edge("3:0", 126.5, 600.0, 3, 4), prov, prov.frame, na)]
    joined = EP.concat(parts)
    alt, s = np.asarray(joined["alt_m"], dtype=float), np.asarray(joined["s"], dtype=float)
    g = 100.0 * np.diff(alt) / np.diff(s)
    assert float(np.max(np.abs(np.diff(g)))) <= 2.0 * AG.CURVE_MAX_PCT       # aucun défaut grave du contrôle du PC
    assert float(np.max(np.abs(g))) <= AG.GRADE_MAX_PCT


def test_node_plane_ignores_surface_outliers() -> None:
    """Plan du relief au nœud : un toit de 6 m sur le nœud ne le soulève pas, la pente du fond est gardée."""
    lat, lon = FRAME.to_latlon(np.array([0.0]), np.array([0.0]))

    def relief(x, z):
        x, z = np.asarray(x, dtype=float), np.asarray(z, dtype=float)
        return 300.0 + 0.05 * x + np.where(x * x + z * z < 16.0, 6.0, 0.0)

    prov = SyntheticProvider(float(lat[0]), float(lon[0]), relief)
    alt, (gx, gz) = EP.node_sample((0.0, 0.0), prov, prov.frame)
    assert alt == pytest.approx(300.0, abs=0.05)
    assert gx == pytest.approx(0.05, abs=1e-3) and gz == pytest.approx(0.0, abs=1e-3)


# --- contrôle bloquant : la route engagée du monde ouvert ----------------------------------------------------------

class SurfaceRelief(SyntheticProvider):
    """Relief de synthèse avec les défauts d'un modèle de surface : pente de fond, bosses de toits et d'arbres posées
    sur la route (une juste sur un nœud), cuvette, marche, et valeurs absentes."""

    def __init__(self) -> None:
        lat, lon = FRAME.to_latlon(np.array([float(E_REF)]), np.array([-float(N_REF)]))
        super().__init__(float(lat[0]), float(lon[0]), self.height)

    @staticmethod
    def height(x, z):
        x = np.asarray(x, dtype=float)
        z = np.asarray(z, dtype=float)
        h = 600.0 + 0.04 * x + 8.0 * np.sin(x / 400.0)
        for c, hh, w in ((450.0, 7.0, 25.0), (1000.0, 6.0, 20.0), (1730.0, -5.0, 15.0), (2400.0, 9.0, 30.0)):
            h = h + hump(x, c, hh, w) * np.exp(-0.5 * (z / 40.0) ** 2)
        h = h + np.where((x > 3100.0) & (np.abs(z) < 60.0), 5.0, 0.0)             # marche (talus, mur)
        hole = (np.abs(x - 2950.0) < 6.0) & (np.abs(z) < 30.0)
        return np.where(hole, -32767.0, h)


def _ride(tmp_path, db, km: float) -> dict:
    s, _rec = session(tmp_path, db, provider=SurfaceRelief())
    s.handle(open_msg(E_REF + 100, N_REF, 90.0))
    for k in range(1, int(km * 4) + 1):
        s.handle({"type": "progress", "s_m": 250.0 * k, "v_mps": 8})
        if s.has_work():
            s.work()
    return s._route_columns()


@pytest.mark.parametrize("kind", ["ligne", "impasse"])
def test_open_world_route_has_no_altitude_defect(tmp_path, kind) -> None:
    db = line_db(tmp_path / "ligne.sqlite") if kind == "ligne" else impasse_db(tmp_path / "impasse.sqlite", end_km=4)
    route = _ride(tmp_path, db, 8.0)
    alt, s = np.asarray(route["alt_m"], dtype=float), np.asarray(route["s"], dtype=float)
    defects = AG.check(alt, s)
    assert not defects, defects[:10]
    assert np.isfinite(alt).all() and float(alt.min()) > 0.0


def short_link_db(path):
    """Route est-ouest avec, à 2 km, deux carrefours à 10 m l'un de l'autre (une branche au nord au premier, une au
    sud au second) : l'arête de 10 m entre eux est fondue dans un seul nœud de choix (`graph.MERGE_M`)."""
    from openride_compiler.worldgen.osmdb import OsmDbWriter
    w = OsmDbWriter(path, "test", "test/raccord")
    a, b = E_REF + 2000, E_REF + 2010
    west = [1000 + k for k in range(30)] + [5000]
    w.add_road(1, {"highway": "tertiary"}, west, [lonlat(E_REF - 1000 + 100 * k, N_REF) for k in range(31)])
    w.add_road(2, {"highway": "tertiary"}, [5000, 5001], [lonlat(a, N_REF), lonlat(b, N_REF)])
    w.add_road(3, {"highway": "tertiary"}, [5001] + [2000 + k for k in range(40)],
               [lonlat(b + 100 * k, N_REF) for k in range(41)])
    w.add_road(4, {"highway": "residential"}, [5000, 3000], [lonlat(a, N_REF), lonlat(a, N_REF + 300)])
    w.add_road(5, {"highway": "residential"}, [5001, 3001], [lonlat(b, N_REF), lonlat(b, N_REF - 300)])
    w.finish(osm_date="2026-10-20T00:00:00Z")
    return path


def test_merged_short_edge_is_ridden_not_jumped(tmp_path) -> None:
    """Constat du banc de #961 (22 novembre, s = 5 350 m, cassure de −8,2 %) : l'arête courte fondue dans un nœud
    de choix n'était pas parcourue, la route sautait d'un carrefour à l'autre (15 m de géométrie dans un pas de 10 m)
    et l'altitude changeait sans distance. Un raccord droit à sa vraie longueur la remplace."""

    class Step(SyntheticProvider):            # 1,2 m de dénivelé entre les deux carrefours (haie, talus)
        def __init__(self) -> None:
            lat, lon = FRAME.to_latlon(np.array([float(E_REF)]), np.array([-float(N_REF)]))
            super().__init__(float(lat[0]), float(lon[0]), self.height)

        @staticmethod
        def height(x, z):
            x = np.asarray(x, dtype=float)
            return 450.0 + 0.02 * x - 0.6 * (1.0 + np.tanh((x - 2005.0) / 4.0)) + 0 * np.asarray(z)

    s, _rec = session(tmp_path, short_link_db(tmp_path / "raccord.sqlite"), provider=Step())
    s.handle(open_msg(E_REF + 100, N_REF, 90.0))
    for k in range(1, 17):
        s.handle({"type": "progress", "s_m": 250.0 * k, "v_mps": 8})
        if s.has_work():
            s.work()
    route = s._route_columns()
    x, z = np.asarray(route["x"], dtype=float), np.asarray(route["z"], dtype=float)
    alt, rs = np.asarray(route["alt_m"], dtype=float), np.asarray(route["s"], dtype=float)
    assert float(x.max()) > 2500.0                                        # le carrefour double est passé
    step = np.hypot(np.diff(x), np.diff(z))
    assert float(np.max(step - np.diff(rs))) < 0.05, "la route saute d'un carrefour à l'autre"   # corde ≤ arc
    defects = AG.check(alt, rs)
    assert not defects, defects[:10]


def test_check_catches_the_defects_without_guard(tmp_path, monkeypatch) -> None:
    """Le contrôle bloquant voit bien les défauts : sans garde-fou, le même monde échoue."""
    monkeypatch.setattr(AG, "guard", lambda alt, s, *_a: (np.asarray(alt, dtype=float), AG.GuardStats()))
    monkeypatch.setattr(AG, "repair", lambda alt: (np.asarray(alt, dtype=float), AG.GuardStats()))
    route = _ride(tmp_path, line_db(tmp_path / "ligne.sqlite"), 4.0)
    defects = AG.check(np.asarray(route["alt_m"], dtype=float), np.asarray(route["s"], dtype=float))
    assert any(kind == "cassure" for _s, kind, _v in defects)


# --- contrôle du PC : scripts/controle_profil_altitude.py ---------------------------------------------------------

def _script():
    import importlib.util
    import sys
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "scripts" / "controle_profil_altitude.py"
    spec = importlib.util.spec_from_file_location("controle_profil_altitude", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["controle_profil_altitude"] = mod
    spec.loader.exec_module(mod)
    return mod


def _write_session(folder, alt: np.ndarray, x: np.ndarray | None = None) -> None:
    import json
    (folder / "route").mkdir(parents=True)
    n = len(alt)
    x = 10.0 * np.arange(n) if x is None else x
    for k, lo in enumerate(range(0, n - 1, 100)):
        hi = min(lo + 100, n - 1)
        part = {"s0_m": 10.0 * lo, "ds_m": 10.0, "length_m": 10.0 * (hi - lo), "alt_m": [round(float(v), 2) for v in alt[lo:hi + 1]],
                "x": [round(float(v), 2) for v in x[lo:hi + 1]], "z": [0.0] * (hi + 1 - lo)}
        (folder / "route" / f"part_{k}.json").write_text(json.dumps(part), encoding="utf-8")


def test_pc_script_flags_the_bench_ramp_and_passes_a_clean_ride(tmp_path) -> None:
    mod = _script()
    s = np.arange(0.0, 2501.0, 10.0)
    clean = 400.0 + 0.04 * s + 4.0 * np.sin(s / 300.0)
    bad = clean + np.where(s >= 1200.0, 0.21 * (s - 1200.0), 0.0) * (s <= 1230.0) + np.where(s > 1230.0, 6.3, 0.0)
    _write_session(tmp_path / "seances" / "ow-20261121-000000.world", clean)
    _write_session(tmp_path / "seances" / "ow-20261121-000100.world", bad)
    assert mod.main(["--out", str(tmp_path / "ok"), str(tmp_path / "seances" / "ow-20261121-000000.world")]) == 0
    assert mod.main(["--out", str(tmp_path / "ko"), str(tmp_path / "seances" / "ow-20261121-000100.world")]) == 1
    resume = (tmp_path / "ko" / "resume.txt").read_text(encoding="utf-8")
    assert "[GRAVE] s = 1200 m : cassure +21" in resume
    assert mod.main(["--out", str(tmp_path / "rien"), "--seances", str(tmp_path / "vide")]) == 2
    jump = 10.0 * np.arange(len(s)) + np.where(s >= 1500.0, 9.9, 0.0)    # arête courte sautée (banc de #961)
    _write_session(tmp_path / "seances" / "ow-20261121-000200.world", clean, jump)
    assert mod.main(["--out", str(tmp_path / "saut"), str(tmp_path / "seances" / "ow-20261121-000200.world")]) == 1
    assert "[GRAVE] s = 1490 m : saut +9.9 m" in (tmp_path / "saut" / "resume.txt").read_text(encoding="utf-8")
