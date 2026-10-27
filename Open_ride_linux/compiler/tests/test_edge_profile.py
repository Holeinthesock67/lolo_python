"""Profil d'arête du monde ouvert (lot W5) : relief analytique, sans réseau."""

from __future__ import annotations

import json
import time
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from openride_compiler.elevation import SyntheticProvider
from openride_compiler.worldgen.edge_profile import NodeAltitudes, concat, edge_profile, split_parts
from openride_compiler.worldgen.graph import Edge

LAT0, LON0 = 44.15, 5.25
SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "world" / "route_part.schema.json"


def provider(func) -> SyntheticProvider:
    return SyntheticProvider(LAT0, LON0, func)


def edge(eid: str, pts: list[tuple[float, float]], a: int = 1, b: int = 2, spans=None) -> Edge:
    p = np.asarray(pts, dtype=float)
    length = float(np.sum(np.hypot(*np.diff(p, axis=0).T)))
    return Edge(eid, a, b, a, b, [tuple(map(float, q)) for q in pts], length, "m", 0, spans or [], None, [a, b])


def straight(length: float, a: int = 1, b: int = 2, x0: float = 0.0, spans=None, eid: str = "1:0") -> Edge:
    return edge(eid, [(x0, 0.0), (x0 + length / 2, 0.0), (x0 + length, 0.0)], a, b, spans)


def test_inclined_plane_gives_constant_grade() -> None:
    prov = provider(lambda x, z: 500.0 + 0.05 * x)
    p = edge_profile(straight(1000.0), prov, prov.frame)
    assert p.s[0] == 0 and p.s[-1] == pytest.approx(1000.0) and np.allclose(np.diff(p.s)[:-1], 10.0)
    assert np.allclose(p.grade_pct[2:-2], 5.0, atol=0.05)
    assert np.allclose(p.heading_deg, 90.0, atol=1e-6) and p.clamped_points == 0
    assert p.versions == {"edge_profile": 1, "relief": "synthetic"}


def test_bridge_over_valley_stays_straight() -> None:
    def valley(x, z):
        d = np.abs(np.asarray(x) - 500.0)
        return 300.0 - 40.0 * np.where(d < 90.0, np.cos(np.pi * d / 180.0) ** 2, 0.0) + 0 * np.asarray(z)

    prov = provider(valley)
    p = edge_profile(straight(1000.0, spans=[[400.0, 600.0, "bridge"]]), prov, prov.frame)
    on = (p.s >= 400) & (p.s <= 600)
    line = np.interp(p.s[on], [400.0, 600.0], np.interp([400.0, 600.0], p.s, p.alt_m))
    assert np.max(np.abs(p.alt_m[on] - line)) <= 0.5
    without = edge_profile(straight(1000.0), prov, prov.frame)
    assert without.alt_m[50] < 270.0                                   # sans pont, la route descend


def test_shared_node_has_one_altitude() -> None:
    prov = provider(lambda x, z: 400.0 + 30.0 * np.sin(np.asarray(x) / 150.0) + 0.02 * np.asarray(z))
    alts = NodeAltitudes(prov, prov.frame)
    e1 = edge("1:0", [(0, 0), (300, 40), (620, 0)], a=1, b=2)
    e2 = edge("2:0", [(620, 0), (700, -300), (900, -500)], a=2, b=3)
    p1 = edge_profile(e1, prov, prov.frame, alts)
    p2 = edge_profile(e2, prov, prov.frame, alts)
    assert abs(p1.alt_m[-1] - p2.alt_m[0]) < 1e-6
    assert p1.alt_m[-1] == pytest.approx(alts.values[2], abs=1e-6)


def test_reversed_profile() -> None:
    prov = provider(lambda x, z: 400.0 + 30.0 * np.sin(np.asarray(x) / 150.0))
    p = edge_profile(edge("1:0", [(0, 0), (300, 40), (627, 0)]), prov, prov.frame)
    r = p.reversed()
    assert np.allclose(r.grade_pct, -p.grade_pct[::-1]) and np.allclose(r.alt_m, p.alt_m[::-1])
    assert np.allclose(r.x, p.x[::-1]) and np.allclose(r.z, p.z[::-1])
    assert np.allclose((r.heading_deg - p.heading_deg[::-1]) % 360.0, 180.0)
    assert r.s[0] == 0 and r.s[-1] == pytest.approx(p.s[-1]) and not r.forward and r.reversed().forward


def test_concat_three_edges_and_parts() -> None:
    prov = provider(lambda x, z: 400.0 + 25.0 * np.sin(np.asarray(x) / 200.0) * np.cos(np.asarray(z) / 300.0))
    alts = NodeAltitudes(prov, prov.frame)
    e1 = edge("1:0", [(0, 0), (1234.5, 0)], 1, 2)
    e2 = edge("2:0", [(1234.5, 0), (1234.5, -777.7)], 2, 3)
    e3 = edge("3:0", [(2000.0, -2000.0), (1234.5, -777.7)], 4, 3)        # parcourue à rebours
    profs = [edge_profile(e1, prov, prov.frame, alts), edge_profile(e2, prov, prov.frame, alts),
             edge_profile(e3, prov, prov.frame, alts).reversed()]
    route = concat(profs, s0=3000.0)
    n = len(route["s"])
    assert all(len(route[k]) == n for k in ("x", "z", "alt_m", "lat", "lon", "grade_pct", "heading_deg"))
    total = sum(p.length_m for p in profs)
    assert route["length_m"] == pytest.approx(total)
    assert np.allclose(np.diff(route["s"])[:-1], 10.0) and 0 < np.diff(route["s"])[-1] <= 10.0
    assert route["s"][0] == 3000.0 and route["edges"] == ["1:0", "2:0", "3:0"]
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    parts = split_parts(route)
    assert [p["s0_m"] for p in parts] == [3000.0 + 1000.0 * k for k in range(len(parts))]
    assert len(parts) == int(np.ceil(total / 1000.0))
    for a, b in zip(parts, parts[1:]):
        assert a["x"][-1] == b["x"][0]                                    # bord partagé
    for p in parts:
        assert list(validator.iter_errors(p)) == []
        assert p["n"] == len(p["lat"]) and p["n"] <= 101
    with pytest.raises(ValueError):
        split_parts({**route, "s": route["s"] + 5.0})


def test_deterministic_and_fast() -> None:
    prov = provider(lambda x, z: 1000.0 + 200.0 * np.sin(np.asarray(x) / 700.0) * np.cos(np.asarray(z) / 900.0))
    e = edge("9:0", [(0, 0), (400, 300), (700, 650)])
    a = edge_profile(e, prov, prov.frame)
    b = edge_profile(e, prov, prov.frame)
    for name in ("s", "x", "z", "alt_m", "grade_pct", "heading_deg", "lat", "lon"):
        assert np.array_equal(getattr(a, name), getattr(b, name))
    one_km = straight(1000.0)
    t0 = time.perf_counter()
    for _ in range(20):
        edge_profile(one_km, prov, prov.frame)
    dt = (time.perf_counter() - t0) / 20
    print(f"profil d'une arête de 1 km : {dt * 1000:.1f} ms")
    assert dt < 0.020 * 3           # seuil indicatif de 20 ms, marge pour les machines lentes


def test_short_edge_and_grade_limit() -> None:
    prov = provider(lambda x, z: 100.0 + 0.4 * np.asarray(x))                 # 40 % : bornée à 25 %
    p = edge_profile(straight(60.0), prov, prov.frame)
    assert len(p.s) == 7 and np.all(np.abs(p.grade_pct) <= 25.0) and p.clamped_points > 0
