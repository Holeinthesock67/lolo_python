"""Navigateur du monde ouvert (lot W6) : balade, destination, boucle, sur des graphes de test."""

from __future__ import annotations

import math
import time

import pytest

from openride_compiler.worldgen.graph import RoadGraph
from openride_compiler.worldgen.navigator import Navigator, drive, nearest
from test_world_graph import FRAME, Builder, bbox_xz

BIG = bbox_xz(-6000, -6000, 6000, 6000)


@pytest.fixture(scope="module")
def grid(tmp_path_factory) -> RoadGraph:
    """Grille de 200 m sur 10 × 10 km, toutes les voies en petites routes (`m`)."""
    b = Builder(tmp_path_factory.mktemp("grille") / "g.sqlite")
    step, half = 200, 5000
    pts = {(i, j): b.node(i * step - half, j * step - half) for i in range(51) for j in range(51)}
    for i in range(51):
        b.way(10_000 + i, [pts[(i, j)] for j in range(51)])
        b.way(20_000 + i, [pts[(j, i)] for j in range(51)])
    return RoadGraph.build(b.open(), BIG, FRAME)


def _length(g: RoadGraph, choices) -> float:
    return sum(g.edges[c.branch_edge_id].length_m for c in choices)


def _cross(tmp_path, side_class: str, side_angle_deg: float) -> tuple[RoadGraph, int, str]:
    b = Builder(tmp_path / "c.sqlite")
    c = b.node(0, 0)
    b.way(1, [b.node(0, 500), c], highway="primary")
    b.way(2, [c, b.node(0, -3000)], highway="primary")                           # tout droit vers le nord
    a = math.radians(side_angle_deg)
    b.way(3, [c, b.node(3000 * math.sin(a), -3000 * math.cos(a))], highway=side_class)
    g = RoadGraph.build(b.open(), BIG, FRAME)
    return g, g.cluster[c], "1:0"


@pytest.mark.parametrize("angle,expected", [(20, "3:0"), (120, "2:0")])
def test_ride_prefers_small_road_unless_far_off(tmp_path, angle, expected) -> None:
    g, node, arriving = _cross(tmp_path, "unclassified", angle)
    nav = Navigator(g, "ride", (0, 500), 0.0, seed=1)
    c = nav.choose(node, arriving, [arriving])
    assert c.branch_edge_id == expected and c.scores["total"] >= 0


def test_dead_end_avoided(tmp_path) -> None:
    b = Builder(tmp_path / "d.sqlite")
    c = b.node(0, 0)
    b.way(1, [b.node(0, 500), c])
    b.way(2, [c, b.node(0, -300)])                                              # impasse tout droit
    b.way(3, [c, b.node(2600, -1500), b.node(9000, -1500)])                     # route à 60°, sort de l'emprise
    g = RoadGraph.build(b.open(), bbox_xz(-5000, -5000, 5000, 5000), FRAME)
    nav = Navigator(g, "ride", (0, 500), 0.0, seed=1)
    assert nav.choose(g.cluster[c], "1:0", ["1:0"]).branch_edge_id == "3:0"
    end = g.cluster[g.edges["2:0"].raw_b]
    u = nav.choose(end, "2:0", ["1:0", "2:0"])                                   # bout de l'impasse : demi-tour
    assert u.branch_edge_id == "2:0" and u.phase == "u_turn" and u.to_node == g.cluster[c]


def test_destination_reached_on_grid(grid) -> None:
    start, target = (-3000.0, 0.0), (2800.0, -1600.0)
    nav = Navigator(grid, "destination", start, 90.0, seed=3, target_xz=target)
    choices = drive(nav, nearest(grid.nodes.values(), start), 20_000, until_arrived=True)
    assert choices[-1].arrived
    length = _length(grid, choices[:-1])
    crow = math.dist(start, target)
    assert length <= 1.3 * crow, (length, crow)
    last = grid.nodes[choices[-2].to_node]
    assert math.dist((last.x, last.z), target) <= 200.0


def test_loop_of_20_km_for_20_seeds(grid) -> None:
    start = (0.0, 0.0)
    home = nearest(grid.nodes.values(), start)
    lengths = []
    for seed in range(20):
        nav = Navigator(grid, "loop", start, 45.0 + 17 * seed, seed=seed, loop_m=20_000)
        choices = drive(nav, home, 40_000, until_arrived=True)
        assert choices[-1].arrived, seed
        ride = choices[:-1]
        end = grid.nodes[ride[-1].to_node]
        assert math.dist((end.x, end.z), start) <= 200.0
        lengths.append(_length(grid, ride))
    print("boucles de 20 km :", [round(x / 1000, 1) for x in lengths])
    assert all(18_000 <= x <= 23_000 for x in lengths), lengths


def test_same_seed_same_choices_and_seeds_differ(grid) -> None:
    home = nearest(grid.nodes.values(), (0.0, 0.0))
    runs = {}
    for seed in (1, 1, 2, 3):
        nav = Navigator(grid, "ride", (0.0, 0.0), 45.0, seed=seed)
        runs.setdefault(seed, []).append([c.branch_edge_id for c in drive(nav, home, 8000)])
    assert runs[1][0] == runs[1][1]
    assert runs[1][0] != runs[2][0] or runs[1][0] != runs[3][0]


def test_ride_of_30_km_never_repeats(grid) -> None:
    home = nearest(grid.nodes.values(), (0.0, 0.0))
    nav = Navigator(grid, "ride", (0.0, 0.0), 30.0, seed=11)
    choices = drive(nav, home, 30_000)
    ids = [c.branch_edge_id for c in choices]
    assert _length(grid, choices) >= 30_000 and len(ids) == len(set(ids))


def test_choose_is_fast_on_5000_edges(grid) -> None:
    assert grid.stats()["edges"] > 5000
    home = nearest(grid.nodes.values(), (0.0, 0.0))
    for mode, kw in (("ride", {}), ("destination", {"target_xz": (4000.0, -4000.0)}), ("loop", {"loop_m": 20_000})):
        nav = Navigator(grid, mode, (0.0, 0.0), 0.0, seed=5, **kw)
        history = [c.branch_edge_id for c in drive(nav, home, 9000)]
        node = grid.cluster[grid.edges[history[-1]].raw_b]
        t0 = time.perf_counter()
        nav.choose(node, history[-1], history)
        dt = time.perf_counter() - t0
        print(f"choose ({mode}) : {dt * 1000:.1f} ms")
        assert dt < 0.050 * 3          # seuil indicatif de 50 ms, marge pour les machines lentes


def test_ride_heading_drift_is_bounded() -> None:
    nav = Navigator.__new__(Navigator)
    for seed in range(10):
        Navigator.__init__(nav, RoadGraph(FRAME), "ride", (0, 0), 90.0, seed)
        values = [nav.ride_heading(d) for d in range(0, 100_000, 500)]
        assert values[0] == pytest.approx(90.0)
        assert all(abs((v - 90.0 + 180) % 360 - 180) <= 20.0 + 1e-9 for v in values)
