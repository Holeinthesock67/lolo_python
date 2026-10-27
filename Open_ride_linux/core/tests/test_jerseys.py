"""Lot T14 : points et maillots de la séance (module pur `jerseys`)."""

from __future__ import annotations

import pytest

from openride_core.jerseys import CLIMB_POINTS, SPRINT_POINTS, Finish, Standings, scale
from openride_core.segments import Segment


def seg(id_, type_, category=None):
    return Segment(id_, id_, type_, 0.0, 500.0, 500.0, 5.0 if type_ == "climb" else 0.0,
                   25.0, category, "auto")


SEGS = [seg("sprint-1", "sprint"), seg("climb-hc", "climb", "HC"), seg("climb-1", "climb", "1"),
        seg("climb-2", "climb", "2"), seg("climb-3", "climb", "3"), seg("climb-4", "climb", "4")]


def test_scales_match_the_owner_decision():
    assert SPRINT_POINTS == (15, 10, 6, 4, 2)
    assert CLIMB_POINTS == {"HC": (20, 15, 10, 6, 4), "1": (10, 8, 6, 4, 2), "2": (5, 3, 2, 1),
                            "3": (2, 1), "4": (1,)}
    assert scale(SEGS[0]) == SPRINT_POINTS and scale(SEGS[5]) == (1,)


def test_points_by_order_of_arrival_bots_included():
    st = Standings(SEGS)
    riders = ["grimpeur", "you", "diesel", "sprinteur", "rouleur", "bot6"]
    awards = st.finish([Finish(r, "climb-hc", 0, 100.0 + i) for i, r in enumerate(riders)])
    assert [(a.rider_id, a.place, a.points) for a in awards] == [
        ("grimpeur", 1, 20), ("you", 2, 15), ("diesel", 3, 10), ("sprinteur", 4, 6),
        ("rouleur", 5, 4), ("bot6", 6, 0)]
    assert all(a.jersey == "kom" for a in awards)
    assert st.leader("kom") == "grimpeur" and st.leader("sprint") is None


def test_same_step_arrivals_sorted_by_crossing_time():
    st = Standings(SEGS)
    awards = st.finish([Finish("you", "sprint-1", 0, 50.31), Finish("sprinteur", "sprint-1", 0, 50.29)])
    assert [(a.rider_id, a.points) for a in awards] == [("sprinteur", 15), ("you", 10)]


def test_small_categories_and_duplicates():
    st = Standings(SEGS)
    a = st.finish([Finish("you", "climb-4", 0, 10.0), Finish("diesel", "climb-4", 0, 11.0)])
    assert [x.points for x in a] == [1, 0]
    a = st.finish([Finish("you", "climb-3", 0, 20.0), Finish("you", "climb-3", 0, 20.5),
                   Finish("diesel", "climb-3", 0, 21.0)])
    assert [(x.rider_id, x.points) for x in a] == [("you", 2), ("diesel", 1)]
    assert st.points("you") == {"sprint": 0, "kom": 3}
    with pytest.raises(KeyError):
        st.finish([Finish("you", "inconnu", 0, 1.0)])


def test_each_lap_is_a_new_contest():
    st = Standings(SEGS)
    st.finish([Finish("you", "sprint-1", 0, 10.0), Finish("sprinteur", "sprint-1", 0, 11.0)])
    st.finish([Finish("sprinteur", "sprint-1", 1, 70.0), Finish("you", "sprint-1", 1, 71.0)])
    assert st.points("you")["sprint"] == 25 and st.points("sprinteur")["sprint"] == 25


def test_tie_goes_to_who_reached_the_total_first():
    st = Standings(SEGS)
    st.finish([Finish("you", "sprint-1", 0, 10.0), Finish("sprinteur", "sprint-1", 0, 11.0)])
    st.finish([Finish("sprinteur", "sprint-1", 1, 70.0), Finish("you", "sprint-1", 1, 71.0)])
    # 25 points chacun ; le sprinteur a atteint 25 à 70 s, toi à 71 s.
    assert st.leader("sprint") == "sprinteur"


def test_two_jerseys_and_state_dict():
    st = Standings(SEGS)
    st.finish([Finish("grimpeur", "climb-1", 0, 300.0), Finish("you", "climb-1", 0, 302.0)])
    st.finish([Finish("you", "sprint-1", 0, 400.0), Finish("grimpeur", "sprint-1", 0, 401.0)])
    assert st.state_dict() == {
        "jerseys": {"sprint": "you", "kom": "grimpeur"},
        "points": {"grimpeur": {"sprint": 10, "kom": 10}, "you": {"sprint": 15, "kom": 8}}}


def test_cancelled_pass_scores_nothing_and_does_not_take_a_place():
    # Un passage annulé par une pause n'arrive jamais : le suivant prend la place.
    st = Standings(SEGS)
    a = st.finish([Finish("diesel", "climb-2", 0, 200.0)])
    assert a[0].place == 1 and a[0].points == 5
