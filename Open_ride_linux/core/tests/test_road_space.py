"""Lot AS11 : règle unique de la chaussée (`road_space`) et règle commune de dépassement (`draft.pass_window`)."""
from __future__ import annotations

import pytest

from openride_core import draft, road_cyclists as rc, road_space as rs, traffic as tr
from openride_core.road_space import Body


def test_no_overlap_no_correction():
    bodies = [Body("me", "rider", 100.0, 1.2, 8.0, move_s=False), Body("v1", "vehicle", 120.0, 1.5, 12.0,
              half_len=2.25, half_width=0.9)]
    rep = rs.resolve(bodies)
    assert rep.corrections == [] and rep.unresolved == 0


def test_lower_priority_user_is_moved_never_the_rider():
    me = Body("me", "rider", 100.0, 1.2, 8.0, move_s=False)
    car = Body("v1", "vehicle", 101.0, 1.3, 8.0, half_len=2.25, half_width=0.9)
    rep = rs.resolve([car, me])
    assert me.s == 100.0 and me.lat == 1.2
    assert [c.id for c in rep.corrections] == ["v1"] and rep.unresolved == 0
    assert not rs.contacts([me, car])


def test_racers_touch_only_on_contact_and_group_never_with_itself():
    a = Body("b1", "bot", 100.0, 0.0, 8.0)
    b = Body("b2", "bot", 101.75, 0.0, 8.0)          # roue dans la roue, 5 cm d'écart : pas de contact
    assert not rs.overlaps(a, b)
    rider = Body("tc0", "escort", 100.0, 0.0, 8.0, half_len=2.25, half_width=0.9, group="me")
    me = Body("me", "rider", 100.0, 0.0, 8.0, group="me")
    assert not rs.contacts([rider, me])


def test_pass_window_is_common_and_shorter_than_the_old_fixed_zones():
    start, end = tr.pass_zone("car_a", 2.8)
    assert -60.0 < start < 0.0 < end < 30.0               # avant AS11 : −60 à +30 m au milieu de la route
    r_start, r_end = rc.overtake_window(2.2)
    assert r_start < 0.0 < r_end < rc.MERGE_AHEAD_M        # avant AS11 : rabattement 20 m devant
    assert draft.pass_window(1.7, 1.7, 2.2, rc.MIN_CENTRE_M, rc.SIDE_SPEED_MPS) == pytest.approx((r_start, r_end))
    # plus on se rapproche vite, plus on sort tôt et plus on se rabat loin
    assert tr.pass_zone("car_a", 6.0)[0] < start and tr.pass_zone("car_a", 6.0)[1] > end


def test_third_bike_arriving_beside_two_abreast_drops_into_the_wheel():
    def lane(m: float) -> draft.Lane:
        return draft.Lane(m=m, home=m)

    others = [(100.0, 8.0, lane(1.2)), (100.0, 8.0, lane(2.1))]
    me = lane(3.0)            # il arrive sur leur droite, au bord
    got = draft.third_abreast(99.0, 8.0, me, 3.0, others)
    assert got is not None and got[0] < 0.0 and got[1] == 8.0
    assert draft.third_abreast(99.0, 8.0, me, 1.2 - draft.SIDE_CLEAR_M - 0.5, others) is None   # il double à gauche
    assert draft.third_abreast(99.0, 9.0, me, 3.0, others) is None                            # plus vite : il double
    assert draft.third_abreast(100.0, 8.0, me, 3.0, others) is None                           # déjà de front (départ)
