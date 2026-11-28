"""Lot DPS1 : règle de dépassement des cyclistes du décor sur les démonstrations de 42 km du lot DPB1 (Chênes,
Banquise, hauts plateaux, steppe, toundra, forêt boréale). Deux causes : le cycliste n'était pas compté comme un usager
quand un groupe en double un autre (`_rider_lane_group`), et un groupe `overtake` se rabattait devant le cycliste
derrière un groupe plus lent qu'il rattrapait aussitôt (`_lane_closing`). La Route du Sud et les autres
démonstrations restent couvertes par `test_decor_cyclists_never_touch` (test_biome_demo_world.py)."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from openride_core import road_cyclists as rc
from openride_core.route import Route

# Pentes des six routes du lot DPB1 (route.json compilé, pas de 10 m, au millième de %) : le modèle des cyclistes du
# décor ne lit que la pente et la longueur du parcours.
PROFILES = Path(__file__).resolve().parent / "data" / "decor_profils_dps1.json"


def _route(name: str) -> Route:
    return _route_of(json.loads(PROFILES.read_text(encoding="utf-8"))[name])


def _route_of(p: dict) -> Route:
    grade, ds = p["grade_pct"], float(p["ds_m"])
    n = len(grade)
    s = [i * ds for i in range(n - 1)] + [float(p["length_m"])]
    alt = [0.0]
    for i in range(1, n):
        alt.append(alt[-1] + grade[i - 1] / 100.0 * (s[i] - s[i - 1]))
    return Route({"n": n, "ds_m": ds, "length_m": p["length_m"], "type": "open",
                  "lat": [45.0] * n, "lon": [6.0] * n, "alt_m": alt, "x": s, "z": [0.0] * n,
                  "grade_pct": grade, "heading_deg": [0.0] * n})


def _contacts(route: Route, kmh: float, seed: int = rc.SEED) -> list[tuple]:
    """Mêmes contrôles que `test_decor_cyclists_never_touch` : 1,7 m en long et 0,6 m en travers."""
    model = rc.RoadCyclists(route, rc.climbs_for(route, []), [], seed=seed)
    s, v, dt = 0.0, kmh / 3.6, 1.0 / 30.0
    bad = []
    while s < route.length_m - 50.0:
        model.update(s, v, dt)
        riders = model.state_list(s)
        for r in riders:
            if abs(r["s"] - s) < 1.7 and abs(r["lane_m"] - rc.RIDER_LATERAL_M) < 0.6:
                bad.append((round(s), r["id"]))
        for a, b in itertools.combinations(riders, 2):
            if (a["id"].rsplit("-", 1)[0] != b["id"].rsplit("-", 1)[0]
                    and abs(a["s"] - b["s"]) < 1.7 and abs(a["lane_m"] - b["lane_m"]) < 0.6):
                bad.append((round(s), a["id"], b["id"]))
        s += v * dt
    return bad


ROUTES = ["chenes", "banquise", "hauts_plateaux", "steppe", "toundra", "foret_boreale"]


@pytest.mark.slow
@pytest.mark.parametrize("name", ROUTES)
@pytest.mark.parametrize("kmh", [25.0, 40.0, 50.0])
def test_hill_lines_never_touch(name: str, kmh: float) -> None:
    """Avant DPS1, sur main : Chênes 89 contacts (50 km/h), Banquise 27 (40 et 50), hauts plateaux 7 (40), steppe 5
    (50), toundra 70 (25) ; forêt boréale 20 avec la seule première cause corrigée."""
    bad = _contacts(_route(name), kmh)
    assert not bad, (name, kmh, len(bad), bad[:3])


@pytest.mark.slow
@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("name", ["chenes", "toundra"])
def test_other_draws_never_touch(name: str, seed: int) -> None:
    """Le fond : d'autres tirages que celui du jeu, à 30 et 55 km/h. Avant DPS1, sur main, les mêmes routes en avaient
    des centaines (371 contacts au tirage 1, 176 au tirage 2 sur l'ensemble des démonstrations)."""
    for kmh in (30.0, 55.0):
        bad = _contacts(_route(name), kmh, seed)
        assert not bad, (name, seed, kmh, len(bad), bad[:3])


def _flat_model() -> rc.RoadCyclists:
    model = rc.RoadCyclists(_route_of({"ds_m": 10.0, "length_m": 2000.0, "grade_pct": [0.0] * 201}), [], [],
                            seed=rc.SEED)
    model.rider_lane = rc.RIDER_LATERAL_M
    return model


def test_rider_counts_as_a_lane_while_alongside_during_the_pass() -> None:
    """Le cycliste compte comme une ligne à éviter s'il est près maintenant, ou s'il rattrape le groupe avant la fin
    du dépassement ; loin et plus lent, ou loin devant, non."""
    model = _flat_model()
    slow = model.place_for_test(0.0, 8.0, "ahead", 40.0, size=2, kmh=20.0)
    fast = model.place_for_test(0.0, 8.0, "ahead", 37.0, size=1, kmh=30.0)
    slow.step_mps, fast.step_mps = 8.0, 8.5
    lane = model._rider_lane_group(fast, [slow], fast.s - 10.0, 8.0, 8.5)
    assert lane is not None and lane.lateral() == pytest.approx(rc.RIDER_LATERAL_M)
    # 40 m derrière, 5 m/s plus vite, dépassement de ~ 15 s à 0,5 m/s d'écart : à hauteur avant la fin
    assert model._rider_lane_group(fast, [slow], fast.s - 40.0, 13.0, 8.5) is not None
    assert model._rider_lane_group(fast, [slow], fast.s - 400.0, 13.0, 8.5) is None
    assert model._rider_lane_group(fast, [slow], fast.s - 40.0, 8.0, 8.5) is None       # plus lent : ne rattrape pas
    assert model._rider_lane_group(fast, [slow], fast.s + 80.0, 13.0, 8.5) is None      # loin devant, plus vite


def test_overtake_does_not_merge_in_front_of_a_slower_group() -> None:
    """Un `overtake` qui a doublé le cycliste ne se rabat pas derrière un groupe plus lent sur sa place de retour
    qu'il rattraperait en moins de MERGE_LOOK_S ; loin, ou aussi rapide, il se rabat."""
    model = _flat_model()
    g = model.place_for_test(0.0, 11.0, "overtake", 5.0, size=1, kmh=45.0)
    slow = model.place_for_test(0.0, 11.0, "ahead", 20.0, size=2, kmh=15.0)
    slow.step_mps = 4.0
    for m in slow.members:
        m.lateral = model._edge_lateral(g.half)
    assert model._lane_closing(g, 13.0)
    slow.s = g.s + 200.0
    assert not model._lane_closing(g, 13.0)
    slow.s, slow.step_mps = g.s + 15.0, 13.5
    assert not model._lane_closing(g, 13.0)


def test_guard_holds_a_group_behind_the_one_it_touches() -> None:
    """Garde finale : un groupe qui touche un groupe plus avancé de son sens recule derrière lui, à sa vitesse au plus."""
    model = _flat_model()
    lead = model.place_for_test(0.0, 8.0, "ahead", 40.0, size=1, kmh=20.0)
    back = model.place_for_test(0.0, 8.0, "ahead", 39.0, size=1, kmh=30.0)
    lead.step_mps, back.step_mps = 5.0, 8.0
    back.members[0].lateral = lead.members[0].lateral
    model._guard(-500.0, 8.0)
    assert lead.s - back.s >= rc.GUARD_LEN_M
    assert back.step_mps == pytest.approx(5.0)
    assert model.guard_total >= 1 and model.guard_kinds.get("recul/autre/ahead", 0) >= 1


def test_guard_moves_a_rider_caught_from_behind_off_the_riders_line() -> None:
    """Garde finale : un cycliste du décor que le cycliste rattrape sur sa ligne s'écarte à MIN_CENTRE_M de lui, du
    côté le plus proche ; le cycliste ne bouge jamais."""
    model = _flat_model()
    g = model.place_for_test(0.0, 8.0, "ahead", 1.0, size=1, kmh=20.0)
    g.members[0].lateral = rc.RIDER_LATERAL_M + 0.3
    model._guard(0.0, 11.0)
    assert abs(g.members[0].lateral - rc.RIDER_LATERAL_M) >= rc.GUARD_RIDER_WIDTH_M
    assert g.members[0].lateral > rc.RIDER_LATERAL_M
    assert model.guard_kinds.get("écart/cycliste/ahead", 0) == 1


def test_guard_leaves_free_riders_alone() -> None:
    model = _flat_model()
    model.place_for_test(0.0, 8.0, "ahead", 40.0, size=3, kmh=20.0)
    model.place_for_test(0.0, 8.0, "oncoming", 60.0, size=2)
    model._guard(0.0, 8.0)
    assert model.guard_total == 0
