"""Montées et sprints du monde ouvert détectés en roulant, records d'une balade à l'autre (lot W20)."""

import math

import pytest

from openride_core.open_world_segments import (FINAL_MARGIN_M, LiveSegments, OwIndex, RouteWindow,
                                                route_window)

LAT0, LON0 = 44.0, 5.0                  # point fictif (aucune coordonnée réelle)
M_PER_DEG = 111_195.0


def window(length_m: float, climb=(2000.0, 3500.0, 6.0), shift: float = 0.0, offset_m: float = 0.0,
           start: float = 0.0, every_m: float | None = None) -> RouteWindow:
    """Route droite vers l'est : plat, une montée à `climb[2]` % entre climb[0] et climb[1], puis plat
    (répétée tous les `every_m`). `offset_m` décale la route vers le nord (autre route) ; `shift` décale
    les distances de séance sans changer la route (même route, abordée dans une autre balade)."""
    s = [start + 10.0 * i for i in range(int((length_m - start) / 10.0) + 1)]

    def g(v: float) -> float:
        u = v % every_m if every_m else v
        return climb[2] if climb[0] <= u < climb[1] else 0.0

    grade = [g(v) for v in s]
    alt, a = [], 100.0
    for i, v in enumerate(s):
        if i:
            a += grade[i - 1] / 100.0 * 10.0
        alt.append(a)
    lat = [LAT0 + offset_m / M_PER_DEG] * len(s)
    lon = [LON0 + v / (M_PER_DEG * math.cos(math.radians(LAT0))) for v in s]
    return RouteWindow([shift + v for v in s], alt, grade, lat, lon)


def test_climb_is_kept_only_once_it_is_final():
    live = LiveSegments()
    added, _ = live.update(window(3500.0 + FINAL_MARGIN_M - 100.0), 0.0)
    assert not [x for x in added if x.type == "climb"]          # la montée touche encore le bout connu
    added, _ = live.update(window(6000.0), 0.0)
    climbs = [x for x in added if x.type == "climb"]
    assert len(climbs) == 1
    c = climbs[0]
    assert c.s_start == pytest.approx(2000.0, abs=20) and c.s_end == pytest.approx(3500.0, abs=20)
    assert c.id.startswith("owc") and len(c.id) <= 24 and c.name.startswith("Montée n°1")
    added, removed = live.update(window(7000.0), 100.0)
    assert not [x for x in added if x.type == "climb"] and not removed   # jamais redessinée


def test_climb_behind_the_rider_is_not_timed():
    live = LiveSegments()
    added, _ = live.update(window(6000.0), 2500.0)
    assert not [x for x in added if x.type == "climb"]


def test_same_climb_next_ride_keeps_its_id(tmp_path):
    path = tmp_path / "segments_monde_ouvert.json"
    first = LiveSegments()
    (c1,) = [x for x in first.update(window(6000.0), 0.0)[0] if x.type == "climb"]
    first.index.save(path)
    # autre balade : même route abordée depuis plus loin (distances de séance différentes)
    again = LiveSegments(index=OwIndex.load(path))
    (c2,) = [x for x in again.update(window(6000.0, shift=12_000.0), 12_000.0)[0] if x.type == "climb"]
    assert c2.id == c1.id and c2.name == c1.name
    assert c2.s_start == pytest.approx(c1.s_start + 12_000.0, abs=20)
    # une montée ailleurs (500 m plus au nord) a son propre identifiant
    other = LiveSegments(index=OwIndex.load(path))
    (c3,) = [x for x in other.update(window(6000.0, offset_m=500.0), 0.0)[0] if x.type == "climb"]
    assert c3.id != c1.id and c3.name.startswith("Montée n°2")


def test_route_rewritten_under_a_segment_removes_it():
    live = LiveSegments()
    (c,) = [x for x in live.update(window(6000.0), 0.0)[0] if x.type == "climb"]
    _, removed = live.update(window(6000.0, offset_m=200.0), 500.0)   # choix de branche : autre route
    assert c.id in removed and all(x.id != c.id for x in live.accepted)


def test_segment_already_ridden_is_never_removed():
    live = LiveSegments()
    (c,) = [x for x in live.update(window(6000.0), 0.0)[0] if x.type == "climb"]
    _, removed = live.update(window(9000.0, offset_m=200.0, start=4000.0), 4000.0)
    assert removed == [] and c in live.accepted


def test_sprints_are_ten_kilometres_apart():
    live = LiveSegments()
    # replats suivis d'une montée tous les 4 km : un sprint au bout de chaque replat, mais un tous les 10 km
    for end in range(6000, 41_000, 1000):
        live.update(window(float(end), climb=(3000.0, 3800.0, 6.0), every_m=4000.0), max(end - 6000.0, 0.0))
    sprints = sorted(x.s_start for x in live.accepted if x.type == "sprint")
    assert len(sprints) >= 3 and all(b - a >= 10_000.0 for a, b in zip(sprints, sprints[1:]))


def test_unreadable_index_starts_afresh(tmp_path):
    path = tmp_path / "segments_monde_ouvert.json"
    path.write_text("{pas du json")
    assert OwIndex.load(path).items == {}


def test_route_window_from_a_live_route_like_object():
    class Inner:
        s = [10.0 * i for i in range(1000)]
        alt_m = [0.0] * 1000
        grade_pct = [0.0] * 1000
        lat = [LAT0] * 1000
        lon = [LON0] * 1000

    class Live:
        base_m = 500.0

        def _current(self):
            return Inner()

    win = route_window(Live(), 3000.0)
    assert win.s[0] == pytest.approx(3000.0) and win.s[-1] == pytest.approx(500.0 + 9990.0)
