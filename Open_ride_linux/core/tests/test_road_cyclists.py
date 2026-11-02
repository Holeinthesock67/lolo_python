"""Cyclistes du décor calculés par le core (lot AS7) : portage de `road_cyclists_model.gd`, parité avec
l'engine, sources d'abri, liste `riders` de `state`."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

from openride_core import draft
from openride_core import road_cyclists as rc
from openride_core.route import Route

ENGINE_TESTS = Path(__file__).resolve().parents[2] / "engine" / "tests"


def _parity_module():
    spec = importlib.util.spec_from_file_location("make_road_cyclists_parity",
                                                  ENGINE_TESTS / "make_road_cyclists_parity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PARITY = _parity_module()
FLAT_M = PARITY.FLAT_M
MIN_CENTRE_M = rc.MIN_CENTRE_M


@pytest.fixture(scope="module")
def route() -> Route:
    return Route(PARITY.route_dict())


def _ride(route: Route, budget: int, seed: int, hold: bool = True) -> dict:
    """Séance de `test_road_cyclists_model.gd` : 30 km/h en plaine, 14 km/h en montée, un bot à 32 km/h
    parti 200 m derrière ; relevé des contrôles."""
    m = rc.RoadCyclists(route, PARITY.CLIMBS, (), budget, seed, hold_after_pass=hold)
    dt = 1.0 / 15.0
    s, bot = 300.0, 100.0
    seen: set[str] = set()
    out = {"log": [], "flat": 0, "climb": 0, "too_close": 0, "wrong_side": 0, "bot_close": 0,
           "max_riders": 0, "max_kmh": 0.0, "salut": 0}
    while s < FLAT_M + 10000.0:
        v = 30.0 / 3.6 if s < FLAT_M else 14.0 / 3.6
        bot += (32.0 if bot < FLAT_M else 15.0) / 3.6 * dt
        m.update(s, v, dt, False, [bot])
        out["salut"] += bool(m.last_event)
        out["max_riders"] = max(out["max_riders"], m.rider_count())
        for g in m.groups:
            out["max_kmh"] = max(out["max_kmh"], g.speed_mps * 3.6)
            if g.id not in seen:
                seen.add(g.id)
                out["log"].append((g.id, g.case, g.size))
                if g.s < FLAT_M + (300.0 if g.case == "overtake" else 0.0) and s < FLAT_M:
                    out["flat"] += 1
                else:
                    out["climb"] += 1
        for r in m.riders():
            if (r.case == "oncoming" and r.lane_m >= 0.0) or (
                    r.case == "ahead" and abs(r.s - s) < 30.0 and r.lane_m <= rc.RIDER_LATERAL_M):
                out["wrong_side"] += 1
            if abs(r.s - s) < 2.0 and abs(r.lane_m - rc.RIDER_LATERAL_M) < MIN_CENTRE_M - 1e-3:
                out["too_close"] += 1
            if abs(r.s - bot) < 2.0 and abs(r.lane_m - rc.BOT_LATERAL_M) < MIN_CENTRE_M - 1e-3:
                out["bot_close"] += 1
        s += v * dt
    out.update(passed=m.passed_total, overtook=m.overtook_total)
    return out


def test_mix_is_32_bits() -> None:
    for h in (0, 1, 0xC1C1E5, 0xFFFFFFFF, 0x1_0000_0001, 123456789):
        assert 0 <= rc.mix(h) <= rc.MASK32
    assert rc.mix(0x1_0000_0001) == rc.mix(1)      # entrée ramenée à 32 bits, comme l'engine
    assert rc.hash3(7, 3, 0xC1C1E5) != rc.hash3(7, 4, 0xC1C1E5)


def test_parity_trace_is_up_to_date() -> None:
    """Le relevé lu par `test_road_cyclists_parity.gd` est celui que produit le portage aujourd'hui."""
    assert PARITY.OUT.read_text(encoding="utf-8") == PARITY.render(), \
        "relancer python3 engine/tests/make_road_cyclists_parity.py"


def test_same_guarantees_as_engine_model(route: Route) -> None:
    """Contrôles de `test_road_cyclists_model.gd`, sur le portage."""
    r = _ride(route, 16, 7, hold=False)
    assert 15 <= r["flat"] <= 30
    assert 20 <= r["climb"] <= 40
    assert r["too_close"] == 0 and r["wrong_side"] == 0 and r["bot_close"] == 0
    assert r["passed"] >= 1 and r["overtook"] >= 1
    assert r["max_riders"] <= 16
    assert r["max_kmh"] <= rc.MAX_KMH + 0.01
    assert _ride(route, 16, 7, hold=False)["log"] == r["log"]
    assert _ride(route, 16, 8, hold=False)["log"] != r["log"]
    salut = 0
    for seed in range(1, 4):
        rs = _ride(route, 8, seed)
        salut += rs["salut"]
        assert rs["too_close"] == 0 and rs["wrong_side"] == 0 and rs["bot_close"] == 0, seed
        assert rs["max_riders"] <= 8
    assert salut >= 1


def test_spawns_do_not_depend_on_hold(route: Route) -> None:
    """Le maintien de vitesse d'AS7 ne change pas les groupes tirés sur les 20 km de plaine (critère 2)."""
    a = [e for e in _ride(route, 16, 7, hold=False)["log"]]
    b = [e for e in _ride(route, 16, 7, hold=True)["log"]]
    assert a[:15] == b[:15]


def test_speed_on_grade_and_cadence() -> None:
    p = rc.power_for(25.0 / 3.6)
    assert rc.speed_on_grade(p, 0.0) == pytest.approx(25.0 / 3.6, abs=0.01)
    assert rc.speed_on_grade(p, 6.0) < 15.0 / 3.6
    assert rc.speed_on_grade(p, -10.0) <= rc.MAX_KMH / 3.6
    assert 75.0 < rc.cadence_rpm(30.0 / 3.6) < 90.0 and rc.cadence_rpm(60.0 / 3.6) == 0.0


def test_pause_freezes(route: Route) -> None:
    m = rc.RoadCyclists(route, PARITY.CLIMBS, (), 16, 7)
    s = 1000.0
    while not m.groups and s < FLAT_M:
        m.update(s, 8.0, 0.1)
        s += 0.8
    before = repr(m.groups)
    for _ in range(50):
        m.update(s, 0.0, 0.1, True)
    assert m.groups and repr(m.groups) == before


def _catch_group(route: Route, case: str, rider_kmh: float, group_kmh: float, size: int,
                 rel_m: float = 12.0) -> tuple[rc.RoadCyclists, float]:
    m = rc.RoadCyclists(route, (), (), 0, 7)      # budget 0 : seul le groupe posé
    s = 1000.0
    m.place_for_test(s, rider_kmh / 3.6, case, rel_m, size, kmh=group_kmh)
    return m, s


def test_ahead_group_gives_draft_behind_its_last_rider(route: Route) -> None:
    """Critère 3 : groupe `ahead` de 3 cyclistes à 24 km/h rattrapé à 25 km/h : abri derrière le dernier
    entre 0,30 et le plafond de groupe 0,55 (lot AS4) (en une dimension avant AS2 : l'écart latéral est vérifié
    après AS2)."""
    m, s = _catch_group(route, "ahead", 25.0, 24.0, 3)
    v = 25.0 / 3.6
    dt = 1.0 / 15.0
    best = 0.0
    best_id = None
    for _ in range(int(60 / dt)):
        m.update(s, v, dt)
        last = min(r.s for r in m.riders())
        if last - s < draft.BIKE_LENGTH_M + 0.3:
            break
        a, src = draft.draft_for(s, m.sources(), rider_v=v)
        if last - s <= draft.BIKE_LENGTH_M + 1.0:
            best, best_id = max(best, a), src
        s += v * dt
    assert 0.30 <= best <= draft.ALPHA_GROUP_CAP
    assert rc.is_source_id(best_id) and best_id.startswith("rider:c")


def test_oncoming_group_gives_no_draft(route: Route) -> None:
    """Critère 4 : un groupe en face n'abrite pas."""
    m, s = _catch_group(route, "oncoming", 25.0, 25.0, 3, rel_m=30.0)
    v = 25.0 / 3.6
    for _ in range(60):
        m.update(s, v, 1.0 / 15.0)
        assert m.riders() and not m.sources()
        assert draft.draft_for(s, m.sources(), rider_v=v) == (0.0, None)
        s += v / 15.0


def test_overtake_group_holds_its_speed_once_merged(route: Route) -> None:
    """Un groupe `overtake` rabattu garde sa vitesse : on peut accélérer et prendre sa roue."""
    m, s = _catch_group(route, "overtake", 25.0, 8.0, 2, rel_m=-30.0)
    g = m.groups[0]
    v = 25.0 / 3.6
    dt = 1.0 / 15.0
    for _ in range(int(120 / dt)):
        m.update(s, v, dt)
        s += v * dt
        if g.held:
            break
    assert g.passed and g.held
    held_v = g.speed_mps
    assert held_v == pytest.approx(33.0 / 3.6, abs=0.3)
    v = 40.0 / 3.6         # le cycliste accélère : le groupe ne suit plus sa vitesse
    for _ in range(int(5 / dt)):
        m.update(s, v, dt)
        s += v * dt
    assert g.speed_mps == pytest.approx(held_v, abs=0.05)
    free = rc.RoadCyclists(route, (), (), 0, 7, hold_after_pass=False)
    free.place_for_test(1000.0, 25.0 / 3.6, "overtake", 30.0, 1, kmh=8.0)
    free.groups[0].passed = True
    for _ in range(30):
        free.update(1000.0, 40.0 / 3.6, dt)
    assert free.groups[0].speed_mps == pytest.approx(48.0 / 3.6, abs=0.05)


def test_state_list_is_short_and_near(route: Route) -> None:
    """Liste `riders` de `state` : au plus 6 cyclistes à moins de 60 m, du plus proche au plus loin."""
    m = rc.RoadCyclists(route, (), (), 0, 7)
    s = 5000.0
    m.place_for_test(s, 8.0, "ahead", 10.0, 4, abreast=True)
    m.place_for_test(s, 8.0, "oncoming", 45.0, 3)
    m.place_for_test(s, 8.0, "ahead", 200.0, 2)
    lst = m.state_list(s)
    assert len(lst) == rc.STATE_MAX
    assert all(abs(e["s"] - s) < rc.NEAR_M for e in lst)
    d = [abs(e["s"] - s) for e in lst]
    assert d == sorted(d)
    assert set(lst[0]) == {"id", "s", "v", "lane_m", "look"}
    assert any(e["v"] < 0 for e in lst)       # en face : vitesse négative, dans le sens du parcours
    assert all(isinstance(e["look"], int) and 0 <= e["look"] <= 0xFFFF for e in lst)
    # Six cyclistes au centimètre : de quoi tenir dans la trame avec 5 bots et 4 véhicules (critère 5)
    assert len(json.dumps(lst, separators=(",", ":"))) < 6 * 70


def test_sources_ids_and_draft_bot() -> None:
    assert rc.source_id("c12-0") == "rider:c12-0"
    assert rc.is_source_id("rider:c12-0") and not rc.is_source_id("bot1") and not rc.is_source_id(None)


def test_no_spawn_on_vehicle(route: Route) -> None:
    """Pas de groupe en face quand un véhicule (lot AS6) est sur la route, ni d'apparition sur un véhicule."""
    m = rc.RoadCyclists(route, (), (), 16, 7)
    m.vehicles = [{"s": -math.inf, "dir": 1}]
    s = 300.0
    while s < 10000.0:
        m.update(s, 8.0, 0.2)
        s += 1.6
    assert m.spawned_total > 0
    assert all(g.case != "oncoming" for g in m.groups)
