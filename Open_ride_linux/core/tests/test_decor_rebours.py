"""Circulation et cyclistes du décor à rebours (lot N23, après le demi-tour du lot N17).

Avant N23, les modèles ne tiraient de nouvelles cases que quand le cycliste avançait vers les s croissants : à
rebours, plus aucune voiture ni aucun cycliste du décor. Ils roulent désormais sur le parcours retourné
(`route_mirror.MirroredRoute`, u = L - s) ; la session convertit leurs places dans le repère du parcours.
"""

from __future__ import annotations

import pytest
from test_traffic import straight_route
from test_road_cyclists import road_round
from test_u_turn import make_session, ride_until, u_turn

from openride_core import road_cyclists as rc
from openride_core import session as session_mod
from openride_core import traffic as tr
from openride_core.route_mirror import MirroredRoute, flip_s

DT = 0.1


def test_mirrored_route_reads_the_same_road_backwards() -> None:
    base = straight_route(6000.0, grade=lambda s: 4.0 if s < 3000.0 else -2.0)
    back = MirroredRoute(base)
    for u in (0.0, 1234.5, 4500.0, 6000.0):
        a, b = back.sample(u), base.sample(6000.0 - u)
        assert (a.x, a.y, a.z, a.alt_m) == pytest.approx((b.x, b.y, b.z, b.alt_m))
        assert a.grade_pct == pytest.approx(-b.grade_pct)
        assert a.heading_deg == pytest.approx((b.heading_deg + 180.0) % 360.0)
        assert back.grade_at(u) == pytest.approx(-base.grade_at(6000.0 - u))
    assert flip_s(6000.0, flip_s(6000.0, 1500.0)) == pytest.approx(1500.0)


def _ride(model, s: float, s_end: float, v: float, update) -> float:
    """Le cycliste roule de `s` vers `s_end` (vers les s décroissants si `s_end < s`) à `v` m/s."""
    step = v * DT if s_end > s else -v * DT
    while (s_end - s) * step > 0.0:
        update(s)
        s += step
    return s


def _traffic_out_and_back(seed: int, seen_dirs: set[int]) -> tuple[int, int]:
    """Aller de 1 à 15 km, demi-tour, retour jusqu'à 2 km : véhicules tirés à l'aller et au retour."""
    route = straight_route(30000.0, grade=lambda s: 0.0)
    t = tr.Traffic(route=route, seed=seed)
    s = _ride(t, 1000.0, 15000.0, 8.3, lambda s: t.update(s, 8.3, DT))
    before = [(v.id, v.s, v.dir, v.lateral) for v in t.vehicles]
    out = t.spawned_total
    assert t.set_direction(-1) and not t.set_direction(-1)
    # Les véhicules déjà là ne bougent pas au demi-tour : mêmes places dans le repère du parcours ; lot AS10 : celui
    # qui doublait le cycliste vient en face et rejoint sa voie d'un coup, comme le cycliste
    def place(vid: str, s: float, d: int, lat: float) -> tuple[str, int, float, float]:
        kind = next(v.kind for v in t.vehicles if v.id == vid)
        if d == 1 and -lat > tr.oncoming_lateral(kind):     # en face dans le repère du modèle retourné
            lat = -tr.oncoming_lateral(kind)
        return vid, d, round(s, 6), round(lat, 6)

    after = [(v.id, v.dir, round(v.s, 6), round(v.lateral, 6)) for v in map(t.on_route, t.vehicles)]
    assert after == [place(*b) for b in before]

    def back(s: float) -> None:
        t.update(t.model_s(s), 8.3, DT)
        for v in map(t.on_route, t.near(t.model_s(s))):
            assert 0.0 <= v.s <= route.length_m
            seen_dirs.add(v.dir)
            if v.dir == 1 and abs(v.s - s) < 20.0:   # croise le cycliste : sur l'autre moitié de la route
                assert v.lateral > 0.0

    _ride(t, s, 2000.0, 8.3, back)
    return out, t.spawned_total - out


def test_traffic_keeps_coming_after_u_turn() -> None:
    seen_dirs: set[int] = set()
    out = back = 0
    for seed in range(1, 9):
        a, b = _traffic_out_and_back(seed, seen_dirs)
        out, back = out + a, back + b
    assert back >= out // 2 and back >= 5             # la route vit à rebours (rien avant N23)
    assert seen_dirs == {1, -1}                       # croisés et dépassés


def test_traffic_u_turn_twice_is_the_forward_model_again() -> None:
    route = straight_route(20000.0, grade=lambda s: 0.0)
    t = tr.Traffic(route=route, seed=5)
    t.set_direction(-1)
    t.set_direction(1)
    assert t.route is route and t.base_route is route
    back = tr.Traffic(route=MirroredRoute(route), seed=5)
    t.set_direction(-1)
    # Mêmes cases dans le repère retourné que l'engine, qui tire sur la même route retournée
    assert [t.slot_event(k) for k in range(60)] == [back.slot_event(k) for k in range(60)]


def test_road_cyclists_keep_coming_after_u_turn() -> None:
    route = straight_route(30000.0, grade=lambda s: 0.0)
    c = rc.RoadCyclists(route, climbs=[(4000.0, 6000.0)], seed=rc.SEED)
    s = _ride(c, 1000.0, 12000.0, 8.3, lambda s: c.update(s, 8.3, DT))
    spawned = c.spawned_total
    places = {r.id: (r.s, r.lane_m) for r in c.riders()}
    assert c.set_direction(-1, s)
    assert c.climbs == []                             # parcours plat : pas de montée du retour (lot N24)
    for r in map(c.on_route, c.riders()):             # rien ne saute au demi-tour
        assert (r.s, r.lane_m) == pytest.approx(places[r.id])
    dirs: set[int] = set()

    def back(s: float) -> None:
        c.update(c.model_s(s), 8.3, DT)
        dirs.update(r.dir for r in map(c.on_route, c.near(c.model_s(s))))

    _ride(c, s, 2000.0, 8.3, back)
    assert c.spawned_total >= spawned + 5
    assert 1 in dirs and -1 in dirs
    c.set_direction(1, 2000.0)
    assert c.route is route and c.climbs == [(4000.0, 6000.0)]


def test_session_shows_vehicles_and_cyclists_after_u_turn(tmp_path, monkeypatch) -> None:
    s, _ = make_session(tmp_path, monkeypatch, 7150)
    s.cfg.ride.traffic_bench_s = 20.0   # passages forcés du banc (tracteur devant, camion qui double), à rebours aussi
    ride_until(s, lambda: s.physics.s >= 4000.0)
    u_turn(s)
    traffic = s.traffic
    spawned = traffic.spawned_total
    seen_v: list[dict] = []
    seen_r: list[dict] = []

    def look() -> bool:   # listes `vehicles` et `riders` d'une trame qui les porte, à chaque pas
        vehicles, riders = road_round(s)   # lot AS11 : un tour des parties `road_part`
        seen_v.extend({**v, "rel": v["s"] - s.physics.s} for v in vehicles)
        seen_r.extend({**r, "rel": r["s"] - s.physics.s} for r in riders)
        return s.physics.s <= 800.0

    ride_until(s, look)
    assert s.traffic is traffic                       # même circulation, retournée, pas recréée
    assert traffic.spawned_total > spawned
    assert seen_v and seen_r
    # Liste `vehicles` et `riders` toujours dans le repère du parcours, autour du cycliste (lot AS11 : tous les usagers
    # du core, de REMOVE_BEHIND_M derrière à REMOVE_AHEAD_M devant dans son sens de marche, plus seulement les proches)
    reach = max(tr.REMOVE_BEHIND_M, tr.REMOVE_AHEAD_M, rc.REMOVE_BEHIND_M, rc.REMOVE_AHEAD_M) + 50.0
    assert all(abs(v["rel"]) < reach for v in seen_v) and all(abs(r["rel"]) < reach for r in seen_r)
    assert any(abs(v["rel"]) < tr.NEAR_M for v in seen_v) and any(abs(r["rel"]) < rc.NEAR_M for r in seen_r)
    # Le tracteur du banc est posé devant le cycliste dans son sens de marche : vers les s décroissants
    assert any(v["dir"] == -1 and v["rel"] < 0.0 for v in seen_v)
    assert traffic.bench_forced >= 2


def test_rider_passes_slow_tractor_after_u_turn(tmp_path, monkeypatch) -> None:
    """À rebours, le cycliste se place encore parmi les véhicules de son sens (placement d'AS2) : il double le
    tracteur lent posé devant lui au lieu de lui rouler dessus (banc `circulation_rebours` du 14/11 : 4 contacts)."""
    s, _ = make_session(tmp_path, monkeypatch, 7160)
    ride_until(s, lambda: s.physics.s >= 3000.0)
    u_turn(s)
    ride_until(s, lambda: s.physics.s <= 2900.0 and s.physics.v > 6.0)
    traffic = s.traffic
    tractor = traffic.place_for_test(traffic.model_s(s.physics.s), "tractor", 1, 30.0, s.physics.v * 3.6 * 0.6)
    worst = 99.0

    def watch() -> bool:
        nonlocal worst
        rel = tractor.s - traffic.model_s(s.physics.s)
        if abs(rel) < tractor.length / 2 + tr.CYCLIST_HALF_LENGTH_M:
            worst = min(worst, abs(tractor.lateral - s._lane.m) - tractor.half_width - tr.RIDER_HALF_WIDTH_M)
        return rel < -30.0

    ride_until(s, watch)
    assert worst < 99.0                               # il l'a bien longé
    assert worst > 0.3                                # sans le toucher



@pytest.mark.parametrize("kind", ["tractor", "car_a", "truck"])
def test_vehicles_met_before_u_turn_never_touch_the_rider_after_it(tmp_path, monkeypatch, kind: str) -> None:
    """Lot AS10 (banc rAS10b, « montees_retour » : « tractor / cycliste » 30/27/14) : le véhicule croisé avant le
    demi-tour roule ensuite devant le cycliste, dans son sens ; il était marqué « a fini de doubler » et prenait la
    voie de gauche à moins de 30 m devant lui, où le cycliste plus rapide le doublait. Celui qui doublait le
    cycliste vient en face, sur sa voie. Aucun ne touche le cycliste, qui double le plus lent à gauche."""
    s, _ = make_session(tmp_path, monkeypatch, 7340 + 10 * ["tractor", "car_a", "truck"].index(kind))
    ride_until(s, lambda: s.physics.s >= 3000.0, dt=DT)
    t = s.traffic
    t.budget = 0                                             # seulement les véhicules posés ici
    t.vehicles.clear()
    me = s.physics.s
    t.place_for_test(me, kind, -1, -40.0, 25.0)              # croisé, 40 m derrière
    over = t.place_for_test(me, "truck", 1, -3.0, 60.0, lateral=tr.lane_lateral("truck"))
    over.committed = True                                    # il doublait le cycliste
    u_turn(s)
    worst, ahead_left = 99.0, 0

    def look() -> bool:
        nonlocal worst, ahead_left
        u = t.model_s(s.physics.s)
        for v in t.vehicles:
            if abs(v.s - u) < v.length * 0.5 + 0.85:
                worst = min(worst, abs(v.lateral - s._lane.m) - v.half_width - tr.RIDER_HALF_WIDTH_M)
            if v.dir == 1 and 0.0 < v.s - u < 30.0 and v.lateral < tr.RIGHT_LANE_M - 0.05:   # 30 m : ancienne PASS_ZONE_M
                ahead_left += 1                              # devant lui dans son sens, mais pas sur sa voie
        return s.physics.s <= 1500.0

    ride_until(s, look, dt=DT)
    assert ahead_left == 0
    assert worst > 0.0


def test_cyclists_use_the_climbs_of_the_way_back() -> None:
    """Lot N24 : à rebours, les montées des cyclistes du décor sont celles du retour, détectées sur le parcours
    retourné comme climb_detector.gd `detect_back` : une colline montée de 0 à 3 km se redescend de 3 à 6 km."""
    route = straight_route(9000.0, grade=lambda s: 6.0 if s < 3000.0 else (-6.0 if s < 6000.0 else 0.0))
    c = rc.RoadCyclists(route, climbs=rc.detect_climbs(route), seed=rc.SEED)
    (start, summit), = c.climbs
    assert summit == pytest.approx(3000.0, abs=150.0)
    c.set_direction(-1, 8000.0)
    (u0, u1), = c.climbs
    assert c.climbs == rc.detect_climbs(MirroredRoute(route))
    # Repère retourné : la montée du retour va de s ≈ 6 km (pied) à s ≈ 3 km (sommet)
    assert flip_s(route.length_m, u0) == pytest.approx(6000.0, abs=150.0)
    assert flip_s(route.length_m, u1) == pytest.approx(3000.0, abs=150.0)
    c.set_direction(1, 8000.0)
    assert c.climbs == [(start, summit)]
