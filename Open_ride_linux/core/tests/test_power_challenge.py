"""Lot PP7 : défi « bats ton record » (durée, cible en watts, parcours proposé), sans aucune donnée réelle."""

from __future__ import annotations

from types import SimpleNamespace

from openride_core.tools import power_challenge as ch

M6 = [{"seconds": s, "watts": w} for s, w in [(5, 880), (60, 430), (300, 310), (1200, 262)]] + [
    {"seconds": 3600, "watts": None}]


def route(rid, length_m, grade, status="ready", tags=None, route_type="open"):
    return SimpleNamespace(id=rid, name=rid.title(), status=status, route_type=route_type,
                           stats={"main_climb": {"length_m": length_m, "avg_grade_pct": grade}},
                           library={"tags": tags} if tags else None)


def test_duration_and_target():
    assert ch.pick_duration({"weak": 60, "aging": {"s": 5}}) == (60, "weak")
    assert ch.pick_duration({"weak": None, "aging": {"s": 5}}) == (5, "aging")
    assert ch.pick_duration(None) == (300, "default")
    c = ch.challenge({"weak": 300}, M6, [])
    assert c["s"] == 300 and c["record_w"] == 310 and c["target_w"] == 311 and c["route_id"] is None


def test_route_whose_climb_lasts_long_enough():
    routes = [route("court", 800, 6.0), route("juste", 2500, 6.0), route("long", 9000, 6.0),
              route("velo", 3000, 6.0, tags=["velodrome"], route_type="loop"), route("brouillon", 2500, 6.0, status="to_compile")]
    c = ch.challenge({"weak": 300}, M6, routes)
    assert c["route_id"] == "juste" and c["route_name"] == "Juste" and c["climb_s"] >= 300
    assert ch.climb_time_s(routes[0].stats, 311) < 300                 # trop courte
    assert ch.climb_time_s(routes[2].stats, 311) > 300 * ch.MAX_FACTOR   # bien trop longue


def test_sprint_and_missing_record():
    assert ch.challenge({"weak": 5}, M6, [route("juste", 2500, 6.0)])["route_id"] is None   # n'importe quel sprint
    assert ch.challenge({"weak": 3600}, M6, []) is None                                     # pas de record : pas de défi
