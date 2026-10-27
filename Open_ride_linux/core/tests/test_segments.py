"""Lot T2 : détection automatique des montées et des sprints (module pur `segments`)."""

from __future__ import annotations

import json
import random

import pytest

from openride_core import segments as sg
from openride_core.demo_world import build_route
from openride_core.route import Route
from openride_core.segments import Profile, SegmentError

DS = 10.0


def profile_from_grades(pieces: list[tuple[float, float]], noise_pct: float = 0.0,
                        seed: int = 1) -> Profile:
    """Profil au pas de 10 m fait de morceaux (longueur m, pente %)."""
    rng = random.Random(seed)
    grades: list[float] = []
    for length, g in pieces:
        grades += [g] * int(round(length / DS))
    grades.append(grades[-1])
    grades = [g + rng.uniform(-noise_pct, noise_pct) for g in grades]
    s = [i * DS for i in range(len(grades))]
    alt = [100.0]
    for g in grades[:-1]:
        alt.append(alt[-1] + DS * g / 100.0)
    return Profile(s, alt, grades)


def climbs_of(p: Profile) -> list[sg.Segment]:
    return [x for x in sg.detect_segments(p, auto_sprints=False)]


def test_single_climb_detected_with_stats():
    p = profile_from_grades([(2000, 0), (2000, 6), (2000, 0)])
    (c,) = climbs_of(p)
    assert c.type == "climb" and c.source == "auto"
    assert c.s_start == pytest.approx(2000, abs=DS)
    assert c.s_end == pytest.approx(4000, abs=DS)
    assert c.avg_grade_pct == pytest.approx(6.0, abs=0.1)
    assert c.gain_m == pytest.approx(120.0, abs=1.0)
    assert c.category == "4"            # 2 000 m × 6 % = 12 000 → 4e catégorie


def test_thresholds_length_grade_gain():
    # 400 m à 8 % : trop courte.
    assert climbs_of(profile_from_grades([(1000, 0), (400, 8), (1000, 0)])) == []
    # 2 km à 2,5 % : trop douce.
    assert climbs_of(profile_from_grades([(1000, 0), (2000, 2.5), (1000, 0)])) == []
    # 800 m à 3,5 % : gain 28 m < 30 m.
    assert climbs_of(profile_from_grades([(1000, 0), (800, 3.5), (1000, 0)])) == []
    # 900 m à 3,5 % : gain 31,5 m, retenue.
    assert len(climbs_of(profile_from_grades([(1000, 0), (900, 3.5), (1000, 0)]))) == 1


def test_neighbour_climbs_merged_below_200_m():
    merged = climbs_of(profile_from_grades([(1000, 0), (1000, 6), (150, 0), (1000, 6), (1000, 0)]))
    assert len(merged) == 1
    assert merged[0].length_m == pytest.approx(2150, abs=2 * DS)
    apart = climbs_of(profile_from_grades([(1000, 0), (1000, 6), (300, 0), (1000, 6), (1000, 0)]))
    assert len(apart) == 2


def test_merge_falls_back_when_average_drops():
    # Deux montées séparées par 190 m de descente raide : fusion refusée, deux montées.
    p = profile_from_grades([(1000, 0), (800, 5), (190, -12), (800, 5), (1000, 0)])
    out = climbs_of(p)
    assert len(out) == 2
    assert all(c.avg_grade_pct >= 3.0 for c in out)


@pytest.mark.parametrize("length, grade, cat", [
    (500, 6, "4"), (2000, 6, "4"), (3000, 6, "3"), (5000, 7, "2"),
    (9000, 7.5, "1"), (12000, 7.5, "HC"),
])
def test_categories(length, grade, cat):
    # 2 000 m × 6 = 12 000 → 4 ; 3 000 × 6 = 18 000 → 3 ; 35 000 → 2 ; 67 500 → 1 ; 90 000 → HC
    assert sg.climb_category(length, grade) == cat


def test_detected_category_matches_formula():
    p = profile_from_grades([(1000, 0), (11000, 8), (1000, 0)])
    (c,) = climbs_of(p)
    assert c.category == "HC"


def test_noisy_profile_no_false_climbs():
    # Plat bruité de ±1,4 % (sous le seuil d'un point qui monte) : aucune montée, au moins un sprint.
    p = profile_from_grades([(25_000, 0)], noise_pct=1.4, seed=7)
    assert climbs_of(p) == []
    assert any(x.type == "sprint" for x in sg.detect_segments(p))


def test_noisy_climb_still_one_climb():
    # Bruit de ±3 % (trace GPS mal lissée) : toujours une seule montée, pas de morcellement.
    p = profile_from_grades([(2000, 0), (3000, 6), (2000, 0)], noise_pct=3.0, seed=3)
    assert len(climbs_of(p)) == 1
    # Bruit de ±1 % (pente lissée de la route) : bornes justes à 10 % près.
    p = profile_from_grades([(2000, 0), (3000, 6), (2000, 0)], noise_pct=1.0, seed=3)
    (c,) = climbs_of(p)
    assert c.length_m == pytest.approx(3000, rel=0.1)


def test_sprints_spacing_length_and_flatness():
    p = profile_from_grades([(35_000, 0.5)])
    sprints = [x for x in sg.detect_segments(p) if x.type == "sprint"]
    assert sprints, "un long plat doit proposer des sprints"
    for a, b in zip(sprints, sprints[1:]):
        assert b.s_start - a.s_start >= sg.SPRINT_SPACING_M
    for x in sprints:
        assert sg.SPRINT_MIN_LENGTH_M <= x.length_m <= sg.SPRINT_MAX_LENGTH_M
        assert x.s_start >= sg.SPRINT_MIN_START_M
        assert x.category is None


def test_no_sprint_on_climbs_or_steep_descents():
    p = profile_from_grades([(1500, 0), (3000, 7), (3000, -5), (150, 0), (3000, 7)])
    for x in sg.detect_segments(p):
        if x.type == "sprint":
            assert x.length_m >= sg.SPRINT_MIN_LENGTH_M
    # Le seul replat assez long hors montée est le premier : sprint avant la montée,
    # à au moins 200 m de son pied.
    sprints = [x for x in sg.detect_segments(p) if x.type == "sprint"]
    climbs = [x for x in sg.detect_segments(p) if x.type == "climb"]
    assert len(sprints) == 0 or sprints[0].s_end <= climbs[0].s_start - sg.SPRINT_CLIMB_CLEARANCE_M + DS


def test_short_flat_no_sprint():
    p = profile_from_grades([(1150, 0), (3000, 7)])
    assert [x for x in sg.detect_segments(p) if x.type == "sprint"] == []


def test_ids_order_and_to_dict_json():
    p = profile_from_grades([(12_000, 0), (2000, 6), (12_000, 0), (3000, 5), (2000, 0)])
    segs = sg.detect_segments(p)
    assert [x.s_start for x in segs] == sorted(x.s_start for x in segs)
    ids = [x.id for x in segs]
    assert len(set(ids)) == len(ids)
    assert {"climb1", "climb2", "sprint1"} <= set(ids)
    d = json.loads(json.dumps([x.to_dict() for x in segs]))
    assert set(d[0]) == {"id", "name", "type", "s_start", "s_end", "length_m", "avg_grade_pct",
                         "gain_m", "category", "source"}


def test_manual_segments_add_and_replace():
    p = profile_from_grades([(2000, 0), (2000, 6), (6000, 0)])
    auto = sg.detect_segments(p)
    manual = sg.manual_segments(p, [
        {"type": "climb", "start_km": 2.2, "end_km": 3.8, "name": "Côte du village"},
        {"type": "sprint", "start_km": 8.0, "end_km": 8.3},
    ])
    assert [m.source for m in manual] == ["manual", "manual"]
    assert manual[0].name == "Côte du village" and manual[0].category is not None
    added = sg.merge_manual(auto, manual, "add")
    # La montée automatique chevauche la manuelle : elle est retirée.
    assert [x.id for x in added if x.type == "climb"] == ["mclimb1"]
    assert sg.merge_manual(auto, manual, "replace") == manual


def test_manual_segments_rejected():
    p = profile_from_grades([(5000, 0)])
    with pytest.raises(SegmentError):
        sg.manual_segments(p, [{"type": "climb", "start_km": 3, "end_km": 2}])
    with pytest.raises(SegmentError):
        sg.manual_segments(p, [{"type": "kom", "start_km": 1, "end_km": 2}])
    with pytest.raises(SegmentError):
        sg.manual_segments(p, [{"type": "sprint", "start_km": 4, "end_km": 9}])
    with pytest.raises(SegmentError):
        sg.merge_manual([], [], "tout")


def test_profile_validation():
    with pytest.raises(SegmentError):
        Profile([0.0], [0.0], [0.0])
    with pytest.raises(SegmentError):
        Profile([0.0, 0.0], [0.0, 1.0], [0.0, 0.0])


def test_from_route_on_demo_world():
    # La route de démonstration est une montée continue : une seule montée détectée.
    route = Route(build_route(5000.0))
    segs = sg.detect_segments(Profile.from_route(route))
    climbs = [x for x in segs if x.type == "climb"]
    assert len(climbs) == 1
    assert climbs[0].gain_m >= sg.CLIMB_MIN_GAIN_M
