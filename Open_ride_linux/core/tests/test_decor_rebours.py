"""Circulation et cyclistes du décor à rebours (lot N23, après le demi-tour du lot N17).

Avant N23, les modèles ne tiraient de nouvelles cases que quand le cycliste avançait vers les s croissants : à
rebours, plus aucune voiture ni aucun cycliste du décor. Ils roulent désormais sur le parcours retourné
(`route_mirror.MirroredRoute`, u = L - s) ; la session convertit leurs places dans le repère du parcours.
"""

from __future__ import annotations

import pytest
from test_traffic import straight_route
from test_u_turn import make_session, ride_until, u_turn

from openride_core import road_cyclists as rc
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
    # Les véhicules déjà là ne bougent pas au demi-tour : mêmes places dans le repère du parcours
    assert [(v.id, v.s, v.dir, v.lateral) for v in map(t.on_route, t.vehicles)] == pytest.approx(before)

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
    assert c.climbs == []                             # montées du retour : lot N24
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
        s._frame_count = 0
        s._fill_vehicles_frame()
        s._fill_riders_frame()
        seen_v.extend({**v, "rel": v["s"] - s.physics.s} for v in s.state.vehicles or [])
        seen_r.extend({**r, "rel": r["s"] - s.physics.s} for r in s.state.riders or [])
        return s.physics.s <= 800.0

    ride_until(s, look)
    assert s.traffic is traffic                       # même circulation, retournée, pas recréée
    assert traffic.spawned_total > spawned
    assert seen_v and seen_r
    # Liste `vehicles` et `riders` toujours dans le repère du parcours, autour du cycliste
    assert all(abs(v["rel"]) < tr.NEAR_M for v in seen_v) and all(abs(r["rel"]) < rc.NEAR_M for r in seen_r)
    # Le tracteur du banc est posé devant le cycliste dans son sens de marche : vers les s décroissants
    assert any(v["dir"] == -1 and v["rel"] < 0.0 for v in seen_v)
    assert traffic.bench_forced >= 2
