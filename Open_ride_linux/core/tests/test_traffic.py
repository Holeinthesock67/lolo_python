"""Circulation calculée par le core, abri derrière un véhicule et aspiration au dépassement (lot AS6).

Critères du cahier `docs/lots/LOT_AS6_abri_vehicules.md` §7 : mêmes véhicules que traffic_model.gd sur
20 km (2, vecteurs partagés avec l'engine), abri derrière un tracteur (3), aspiration d'un camion qui
double (4), coût par pas (6) ; véhicule lent devant, sécurité des dépassements, liste `vehicles`.
"""

import json
import math
import time
from pathlib import Path

import pytest
from openride_core import draft
from openride_core import traffic as tr
from openride_core.route import Route
from openride_core.tools import traffic_vectors

VECTORS = Path(__file__).resolve().parents[2] / "engine" / "tests" / "data" / "traffic_slots_vectors.json"
DT = 0.02


def straight_route(length_m: float = 30000.0, grade=lambda s: 2.0) -> Route:
    ds = 10.0
    n = int(length_m / ds) + 1
    alts, a = [], 400.0
    for i in range(n):
        alts.append(a)
        a += ds * grade(i * ds) / 100.0
    return Route({"n": n, "ds_m": ds, "length_m": (n - 1) * ds, "type": "open",
                  "lat": [48.9] * n, "lon": [7.1] * n, "alt_m": alts, "x": [i * ds for i in range(n)],
                  "z": [0.0] * n, "grade_pct": [grade(i * ds) for i in range(n)], "heading_deg": [90.0] * n})


# --- critère 2 : mêmes tirages que l'engine ------------------------------------------------------

def test_vectors_file_is_up_to_date():
    assert traffic_vectors.main(["--check"]) == 0


def test_slot_events_match_shared_vectors():
    doc = json.loads(VECTORS.read_text(encoding="utf-8"))
    route = Route(doc["route"])
    villages = [(v["x"], v["z"]) for v in doc["villages"]]
    total = 0
    for case in doc["cases"]:
        t = tr.Traffic(route=route, seed=case["seed"], villages=villages, snow_line_m=doc["snow_line_m"])
        got = [t.slot_event(k) for k in range(int(route.length_m // tr.SLOT_M) + 1)]
        got = [{"slot": e["slot"], "kind": e["kind"], "color": e["color"], "dir": e["dir"]} for e in got if e]
        want = [{k: e[k] for k in ("slot", "kind", "color", "dir")} for e in case["events"]]
        assert got == want
        total += len(want)
    assert route.length_m >= 20000.0 and total >= 30
    kinds = {e["kind"] for c in doc["cases"] for e in c["events"]}
    assert {"tractor", "truck", "van"} <= kinds
    # ni au-dessus de la neige (12–13 km) ni sur la pente de 10 % (6–7 km)
    slots = [e["slot"] * tr.SLOT_M for c in doc["cases"] for e in c["events"]]
    assert not any(6000.0 <= s < 7000.0 or 12000.0 <= s < 13000.0 for s in slots)


def test_hash_matches_vegetation_placer():
    # valeurs de vegetation_placer.gd (_mix et hash3 sur 32 bits)
    assert tr._mix(0) == 0
    assert 0 <= tr.hash3(7, 3, tr.SEED_SALT) <= tr.MASK32
    assert tr.hash3(7, 3, tr.SEED_SALT) == tr.hash3(7, 3 + (1 << 32), tr.SEED_SALT)
    assert tr.pick_kind(0.0) == "car_a" and tr.pick_kind(0.999) == "tractor"
    assert math.isclose(sum(k["share"] for k in tr.KINDS.values()), 1.0)


# --- séance simulée -------------------------------------------------------------------------------

def ride(seed: int, v_rider: float = 8.3, length_m: float = 30000.0, bots=()):
    route = straight_route(length_m)
    t = tr.Traffic(route=route, seed=seed)
    s, worst_side, max_live, log = 1000.0, 99.0, 0, []
    while s < length_m - 1500.0:
        others = [tr.Other(s=s + b, lateral=draft.BOT_LANE_M) for b in bots]
        t.update(s, v_rider, 0.1, others=others)
        max_live = max(max_live, len(t.vehicles))
        for v in t.vehicles:
            # un véhicule lent devant est doublé par le cycliste (placement d'AS2, session) : hors de ce compte
            if not v.slow and abs(v.s - s) < v.length / 2 + tr.CYCLIST_HALF_LENGTH_M:
                worst_side = min(worst_side, abs(v.lateral - tr.RIDER_LATERAL_M) - v.half_width - tr.RIDER_HALF_WIDTH_M)
        s += v_rider * 0.1
    log = [(v.id, v.kind, v.dir) for v in t.vehicles]
    return t, worst_side, max_live, log


def test_ride_is_safe_deterministic_and_budget_fixed():
    spawned = 0
    for seed in range(1, 9):
        t, side, live, _ = ride(seed)
        spawned += t.spawned_total
        assert side >= tr.LATERAL_CLEARANCE_M - 0.05     # jamais à moins de 1,5 m du cycliste
        assert live <= tr.BUDGET
    assert spawned >= 10
    assert ride(3)[0].spawned_total == ride(3)[0].spawned_total and ride(3)[3] == ride(3)[3]


def test_slow_tractor_ahead_is_caught_up():
    route = straight_route()
    t = tr.Traffic(route=route, seed=0)
    ev = None
    for seed in range(200):
        t.seed = seed
        for k in range(4, 100):
            e = t.slot_event(k)
            if e and e["kind"] == "tractor" and e["dir"] == 1:
                ev = (seed, k, e)
                break
        if ev:
            break
    seed, k, e = ev
    t = tr.Traffic(route=route, seed=seed)
    s = k * tr.SLOT_M - 1.0
    t.update(s, 9.0, DT)
    t.update(s + 2.0, 9.0, DT)                       # la case k est atteinte
    slow = [v for v in t.vehicles if v.slow]
    assert len(slow) == 1 and slow[0].kind == "tractor" and slow[0].s > s + 100.0
    assert slow[0].lateral == tr.RIGHT_LANE_M and slow[0].cruise_mps < 9.0
    # le cycliste à 9 m/s le rattrape puis le double ; le tracteur ne le suit pas
    v = slow[0]
    s += 2.0
    for _ in range(3000):
        s += 0.9
        t.update(s, 9.0, 0.1)
    assert v.passed and v.s < s and v.speed_mps <= v.cruise_mps + 1e-9
    assert t.overtakes_total == 0                    # un véhicule doublé par le cycliste n'est pas un dépassement


def test_van_is_slow_only_in_steep_climb():
    flat = tr.Traffic(route=straight_route(grade=lambda s: 2.0))
    steep = tr.Traffic(route=straight_route(grade=lambda s: 7.0))
    ev = {"dir": 1, "kind": "van", "cruise_mps": 15.0, "u_speed": 0.5}
    assert flat.slow_cruise(ev, 500.0) is None
    assert steep.slow_cruise(ev, 500.0) == pytest.approx(22.0 / 3.6)
    assert steep.slow_cruise(dict(ev, kind="car_a"), 500.0) is None
    assert steep.slow_cruise(dict(ev, dir=-1), 500.0) is None


def test_near_list_and_state_frame():
    t = tr.Traffic(route=straight_route())
    for rel in (-200.0, -40.0, 10.0, 60.0, 120.0, 149.0):
        t.place_for_test(5000.0, "car_a", 1, rel, 50.0)
    near = t.near(5000.0)
    assert [round(v.s - 5000.0) for v in near] == [10, -40, 60, 120]
    item = tr.state_list(near)[0]
    assert set(item) == {"id", "kind", "color", "s", "dir", "v", "lane_m"}
    assert item["lane_m"] == tr.RIGHT_LANE_M and item["dir"] == 1


# --- critère 3 : abri derrière un véhicule lent ---------------------------------------------------

def test_tractor_draft_at_three_metres():
    t = tr.Traffic(route=straight_route())
    v = t.place_for_test(5000.0, "tractor", 1, 0.0, 25.0)
    v.s = 5000.0 + v.length / 2 + draft.BIKE_LENGTH_M / 2 + 3.0       # 3 m entre son arrière et la roue avant
    # placement dans la roue : le cycliste prend la ligne du tracteur
    alpha, src = tr.vehicle_draft(5000.0, v.lateral, [v], rider_v=25 / 3.6)
    assert 0.35 <= alpha <= 0.50 and src == "veh:" + v.id
    # cycliste à sa place (1,2 m), tracteur au milieu de la voie (1,5 m) : toujours derrière la carrosserie
    assert tr.vehicle_draft(5000.0, tr.RIDER_LATERAL_M, [v])[0] == pytest.approx(alpha)
    # à côté du tracteur : rien
    assert tr.vehicle_draft(5000.0, v.lateral - v.half_width - 1.2, [v]) == (0.0, None)


def test_vehicle_draft_curve_by_kind():
    for kind, (at3, reach) in tr.DRAFT.items():
        assert tr.vehicle_coefficient(kind, 3.0) == pytest.approx(min(at3, tr.VEHICLE_ALPHA_CAP))
        assert tr.vehicle_coefficient(kind, reach) == pytest.approx(tr.DRAFT_TAIL)
        assert tr.vehicle_coefficient(kind, reach + 0.1) == 0.0 and tr.vehicle_coefficient(kind, -0.1) == 0.0
        assert tr.vehicle_coefficient(kind, 0.0) <= tr.VEHICLE_ALPHA_CAP
        prev = 1.0
        for g in range(0, int(reach) + 1):
            c = tr.vehicle_coefficient(kind, float(g))
            assert c <= prev + 1e-12
            prev = c
    assert tr.vehicle_coefficient("truck", 10.0) > tr.vehicle_coefficient("car_a", 10.0) > tr.vehicle_coefficient("moto", 5.0)


def test_oncoming_and_behind_vehicles_do_not_shelter():
    t = tr.Traffic(route=straight_route())
    a = t.place_for_test(5000.0, "truck", -1, 10.0, 50.0)
    b = t.place_for_test(5000.0, "truck", 1, -20.0, 50.0)
    assert tr.vehicle_draft(5000.0, tr.RIDER_LATERAL_M, [a, b]) == (0.0, None)


# --- critère 4 : aspiration au dépassement --------------------------------------------------------

def suction_series(kind: str, clear_m: float, rider_v: float = 8.3, kmh: float = 50.0):
    t = tr.Traffic(route=straight_route())
    v = t.place_for_test(5000.0, kind, 1, -40.0, kmh)
    v.lateral = tr.RIDER_LATERAL_M - (clear_m + v.half_width + tr.RIDER_HALF_WIDTH_M)
    v.slow = False
    s, series = 5000.0, []
    for i in range(int(16.0 / DT)):
        series.append((i * DT, tr.pass_suction(s, rider_v, tr.RIDER_LATERAL_M, [v]), v.s - v.length / 2 - s))
        v.s += v.speed_mps * DT
        s += rider_v * DT
    return series


def test_truck_overtaking_suction_peak_and_decay():
    series = suction_series("truck", 1.8)
    peak_t, peak, rear = max(series, key=lambda p: p[1])
    assert 0.2 <= peak <= 0.3
    assert abs(rear) < 0.5                                    # pic quand l'arrière passe le cycliste
    after = [p for p in series if p[0] > peak_t and p[1] < 0.005]
    assert after and after[0][0] - peak_t < 2.0               # retour à 0 en moins de 2 s
    before = [p for p in series if p[0] < peak_t and p[1] < 0.005]
    assert before and peak_t - before[-1][0] < 2.0            # montée en moins de 2 s
    assert max(p[1] for p in suction_series("truck", 2.6)) == 0.0     # rien au-delà de 2,5 m
    assert max(p[1] for p in suction_series("car_a", 1.5)) == pytest.approx(0.15, abs=0.005)


def test_suction_ignores_slower_and_oncoming():
    t = tr.Traffic(route=straight_route())
    a = t.place_for_test(5000.0, "truck", -1, 5.0, 50.0)
    a.lateral = -0.5
    b = t.place_for_test(5000.0, "tractor", 1, 2.0, 20.0)
    assert tr.pass_suction(5000.0, 8.3, tr.RIDER_LATERAL_M, [a, b]) == 0.0


# --- critère 6 : coût ----------------------------------------------------------------------------

def test_cost_per_step_with_four_vehicles():
    t = tr.Traffic(route=straight_route())
    for rel, kind in ((-60.0, "truck"), (20.0, "tractor"), (90.0, "car_a"), (140.0, "bus")):
        t.place_for_test(5000.0, kind, 1 if kind != "bus" else -1, rel, 25.0 if kind == "tractor" else 55.0)
    others = [tr.Other(s=5000.0 + d, lateral=draft.BOT_LANE_M) for d in (-3.0, 4.0, 8.0, 15.0, 30.0)]
    s, n = 5000.0, 2000
    t0 = time.perf_counter()
    for _ in range(n):
        t.update(s, 8.3, DT, others=others)
        near = t.near(s)
        tr.vehicle_draft(s, tr.RIDER_LATERAL_M, near)
        tr.pass_suction(s, 8.3, tr.RIDER_LATERAL_M, near)
        s += 8.3 * DT
    ms = (time.perf_counter() - t0) * 1000.0 / n
    assert ms < 0.2, f"{ms:.3f} ms par pas"


# --- séance : réglage, trame `state`, abri derrière un tracteur ---------------------------------

def tractor_session(tmp_path, monkeypatch, port, vehicle_draft="on"):
    from test_draft import FlatRoute, make_session

    s, _ = make_session(tmp_path, monkeypatch, port, 200.0, [])
    s.cfg.ride.vehicle_draft = vehicle_draft
    s.route = FlatRoute()
    s.physics.v = 25 / 3.6
    s._on_command("start", {}, 2)
    t = s._traffic_for(s.route)
    t._last_rider_s = s.physics.s
    t._next_slot = 10 ** 6                    # aucune case tirée : seul le tracteur posé roule
    v = t.place_for_test(s.physics.s, "tractor", 1, 0.0, 25.0)
    v.s = s.physics.s + v.length / 2 + draft.BIKE_LENGTH_M / 2 + 3.0
    return s, v


def hold_behind(s, v, seconds):
    from test_draft import run

    for i in range(int(seconds / DT)):
        s.physics.v = v.speed_mps                 # le cycliste roule à la vitesse du tracteur, à 3 m
        s.physics.s = v.s - v.length / 2 - draft.BIKE_LENGTH_M / 2 - 3.0
        run(s, DT, t0=100.0 + i * DT)


def test_session_tractor_shelters_rider_and_frame(tmp_path, monkeypatch):
    s, v = tractor_session(tmp_path, monkeypatch, 6180)
    hold_behind(s, v, 5.0)
    frame = s.state.to_dict()
    assert 0.35 <= frame["draft"] <= 0.50 and frame["draft_bot"] == "veh:" + v.id
    assert abs(frame["lane_m"] - v.lateral) < 0.1            # placement : dans sa ligne
    s._frame_count = 0
    s._fill_vehicles_frame()
    assert s.state.to_dict()["vehicles"][0]["kind"] == "tractor"


def test_session_vehicle_draft_off(tmp_path, monkeypatch):
    s, v = tractor_session(tmp_path, monkeypatch, 6184, vehicle_draft="off")
    hold_behind(s, v, 5.0)
    assert s.state.to_dict()["draft"] == 0.0


def test_vehicle_draft_setting():
    from openride_core import settings
    from openride_core.config import Config

    item = next(it for it in settings.current(Config()) if it["key"] == "ride.vehicle_draft")
    assert item["value"] == "on" and item["choices"] == ["on", "off"] and item["group"] == "ride"
    assert settings.get("ride.vehicle_draft").scope == "profil"


def test_state_frame_with_four_vehicles_and_five_bots_fits():
    from openride_core import ipc_budget

    worst = ipc_budget.worst_state("1.5")
    assert len(worst["vehicles"]) == tr.NEAR_MAX and len(worst["bots"]) == 5
    assert ipc_budget.size(worst) <= ipc_budget.STATE_LIMIT_1_3
    with_devices = ipc_budget.worst_state("1.4")
    with_devices["vehicles"] = worst["vehicles"]
    assert ipc_budget.size(with_devices) <= ipc_budget.STATE_LIMIT_1_3


def test_rider_passes_slow_tractor_on_the_left():
    t = tr.Traffic(route=straight_route())
    rider = draft.Lane(draft.RIDER_LANE_M, draft.RIDER_LANE_M)
    v = t.place_for_test(5000.0, "tractor", 1, 20.0, 20.0)
    s, worst = 5000.0, 99.0
    for _ in range(int(30.0 / DT)):
        t.update(s, 9.0, DT, others=[tr.Other(s, rider.m)])
        lane = draft.Lane(v.lateral, v.lateral, auto=False, half_width=v.half_width, length=v.length)
        draft.update_lanes([(s, 9.0, rider), (v.s, v.speed_mps, lane)], DT)
        s += 9.0 * DT
        if abs(v.s - s) < v.length / 2 + draft.BIKE_LENGTH_M / 2:
            worst = min(worst, abs(rider.m - v.lateral) - v.half_width - tr.RIDER_HALF_WIDTH_M)
    assert v.s < s and worst < 99.0
    assert worst >= draft.SIDE_CLEAR_M - draft.RIDER_WIDTH_M - 0.05      # longé comme un vélo, sans contact
    assert rider.m >= draft.PASS_LANE_MIN_M
