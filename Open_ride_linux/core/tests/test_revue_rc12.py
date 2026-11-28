"""Revue de code, vague 2, lot RC12 : circulation et cyclistes du décor (constats C5-02, C5-03, C5-06).

- C5-02 : un véhicule qui se rabat ne sort jamais de la chaussée pour passer un bot par la droite, il attend
  derrière (bloc « jamais hors de la route » de `traffic_model.gd` `_clear_of_others`).
- C5-03 : un véhicule engagé finit son dépassement quand le cycliste (ou un bot) roule près de l'axe : il compare
  sa place à la place réellement visée, plus à gauche que sa voie (`minf(left, goal)` de l'engine).
- C5-06 : un groupe du décor ne recule jamais derrière un bot arrêté sur la ligne.
"""

from __future__ import annotations

import pytest

from openride_core import draft
from openride_core import road_cyclists as rc
from openride_core import traffic as tr
from openride_core.route import Route


def _flat_route(length_m: float) -> Route:
    ds = 10.0
    n = int(length_m / ds) + 1
    return Route({"n": n, "ds_m": ds, "length_m": (n - 1) * ds, "type": "open",
                  "lat": [48.9] * n, "lon": [7.1] * n, "alt_m": [200.0] * n, "x": [i * ds for i in range(n)],
                  "z": [0.0] * n, "grade_pct": [0.0] * n, "heading_deg": [90.0] * n})


def _traffic_with(vehicle: tr.Vehicle) -> tr.Traffic:
    """Circulation sur 30 km de plat, sans autre véhicule que `vehicle` (budget 1)."""
    t = tr.Traffic(route=_flat_route(30000.0), seed=1, budget=1)
    t.vehicles = [vehicle]
    return t


# --- C5-02 : jamais hors de la route --------------------------------------------------------------

@pytest.mark.parametrize("kind", ["truck", "car_a"])
@pytest.mark.parametrize("bot_lat", [1.2, 1.5])
def test_vehicle_back_on_the_right_never_leaves_the_road_to_pass_a_bot(kind: str, bot_lat: float) -> None:
    """Le véhicule a doublé le cycliste et revient à droite ; un bot roule 40 m devant le cycliste, près de l'axe.
    Sur main : passé par la droite, dans l'herbe (camion à 4,4-4,7 m de l'axe). Corrigé : il reste sur la chaussée
    et ses accotements (plus VERGE_M) et attend derrière le bot."""
    s, v_rider, dt = 2000.0, 8.3, 0.02
    lo, hi = tr.KINDS[kind]["kmh"]
    veh = tr.Vehicle(id="v1", kind=kind, color=0, s=s + 15.0, dir=1, cruise_mps=hi / 3.6, speed_mps=hi / 3.6,
                     lateral=tr.lane_lateral(kind), passed=True, committed=True)
    t = _traffic_with(veh)
    edge = 3.0 + 0.5 + 0.25 - veh.half_width     # chaussée, accotement, VERGE_M (traffic_model.gd)
    bot = s + 40.0
    worst, passed_bot = 0.0, False
    for _ in range(int(40.0 / dt)):
        others = [tr.Other(bot, bot_lat), tr.Other(s, tr.RIDER_LATERAL_M)]
        t.update(s, v_rider, dt, others=others)
        if t.vehicles:
            v = t.vehicles[0]
            worst = max(worst, abs(v.lateral))
            passed_bot = passed_bot or v.s > bot + v.length
        s += v_rider * dt
        bot += v_rider * dt
    assert worst <= edge + 1e-6, f"{kind} à {worst:.2f} m de l'axe (bord {edge:.2f} m)"
    assert not passed_bot          # sans la place sur la route, il attend derrière le bot


def test_road_edge_matches_engine() -> None:
    """Même bord que traffic_model.gd : RoadBuilder.ROAD_WIDTH_M / 2 + SHOULDER_WIDTH_M + VERGE_M."""
    assert tr.VERGE_M == 0.25
    assert tr.ROAD_EDGE_M == pytest.approx(3.0 + 0.5 + 0.25)


# --- C5-03 : dépassement engagé, usager près de l'axe -------------------------------------------

@pytest.mark.parametrize("rider_lat,bot_lat", [(0.9, None), (draft.RIDER_LANE_M, 0.9)])
def test_committed_overtaker_finishes_when_someone_rides_near_the_axis(rider_lat, bot_lat) -> None:
    """Cycliste à 0,9 m de l'axe, ou bot 3 m devant lui à 0,9 m : la voiture doit se mettre plus à gauche que sa
    voie de dépassement. Sur main elle reste bloquée derrière, voie d'en face, sans fin (100 s, 0 dépassement) ;
    corrigé : elle double."""
    s, v_rider, dt = 2000.0, 8.3, 0.02
    veh = tr.Vehicle(id="v1", kind="car_a", color=0, s=s - 80.0, dir=1, cruise_mps=60.0 / 3.6,
                     speed_mps=60.0 / 3.6, lateral=tr.RIGHT_LANE_M)
    t = _traffic_with(veh)
    for _ in range(int(100.0 / dt)):
        others = [tr.Other(s, rider_lat)]
        if bot_lat is not None:
            others.append(tr.Other(s + 3.0, bot_lat))
        t.update(s, v_rider, dt, others=others)
        if t.overtakes_total:
            break
        s += v_rider * dt
    assert t.overtakes_total == 1
    assert not t._overtaking() or veh.s > s         # la voie se libère : la circulation peut reprendre


# --- C5-06 : jamais à reculons -------------------------------------------------------------------

def test_decor_group_never_rolls_backwards_behind_a_stopped_bot() -> None:
    """Groupe `ahead` qui arrive sur un bot arrêté sur la ligne (5 000 m), serré à droite (2,4 m de l'axe). Sur
    main : vitesse du pas à −0,5 m/s, groupe figé à 4 m de la ligne et `v` négatif dans `state`. Corrigé : jamais
    sous 0."""
    route = _flat_route(5000.0)
    m = rc.RoadCyclists(route, (), (), 0, 7)       # budget 0 : seul le groupe posé
    s, v, dt = 4900.0, 22.0 / 3.6, 0.02
    g = m.place_for_test(s, v, "ahead", 40.0, 2, kmh=20.0)
    bot = (route.length_m, 2.4)
    worst, worst_state = 0.0, 0.0
    for _ in range(int(40.0 / dt)):
        m.update(s, v, dt, bots=[bot])
        if g in m.groups:
            worst = min(worst, g.step_mps)
        for r in m.riders():
            worst_state = min(worst_state, r.v)
        s = min(s + v * dt, route.length_m - 30.0)
    assert worst >= 0.0
    assert worst_state >= 0.0
