"""Lot CO9 : séance de jeu calibrée au besoin (format, réglages, temps prédit) ; parcours fabriqués."""

from __future__ import annotations

import time

from openride_core import coach, coach_game
from openride_core.coach import Inputs
from openride_core.coach_game import Candidate
from openride_core.demo_world import write_world
from openride_core.ipc_lists import build_coach_message

from test_coach import FTP, TABLE, TODAY, base_history
from test_contract_ipc import assert_valid


def cand(cid, chunks, loop=True, max_grade=None, climb=None):
    grades = [g for _, g in chunks]
    stats = {"max_grade_pct": max(grades) if max_grade is None else max_grade, "main_climb": climb}
    return Candidate(cid, cid.capitalize(), loop, tuple(chunks), stats)


FLAT = cand("plat", [(100.0, 0.0)] * 100)                                     # boucle de 10 km à 0 %
# Boucle de 8 km : 2 km de montée à 6 % (≈ 6 min au seuil), puis 6 km de descente douce.
CLIMB = cand("cote", [(100.0, 6.0)] * 20 + [(100.0, -2.0)] * 60, max_grade=6.0,
             climb={"length_m": 2000.0, "avg_grade_pct": 6.0, "gain_m": 120.0, "category": "3"})
ALPS = cand("col", [(100.0, 7.0)] * 120, loop=False,
            climb={"length_m": 12000.0, "avg_grade_pct": 7.0, "gain_m": 840.0, "category": "1"})
ALL = [FLAT, CLIMB, ALPS]


def test_one_format_per_need():
    got = {n: coach_game.choose(n, 3600, None, ALL, FTP, TABLE) for n in ("recovery", "light", "intense", "anaerobic")}
    assert (got["recovery"]["route_id"], got["recovery"]["bots"]["count"]) == ("plat", 0)
    assert got["light"]["bots"] == {"count": 4, "level_pct": 65, "tactics": "none"}
    assert got["light"]["route_id"] == "plat"                     # montée de la côte trop longue (> 2 min)
    assert (got["intense"]["route_id"], got["intense"]["bots"]["level_pct"]) == ("cote", 95)   # col : > 10 min
    assert got["anaerobic"]["mode"] == "survivor" and got["anaerobic"]["survivor"] == {"opponents": 4, "spacing_km": 1}
    for need, g in got.items():
        assert g["ratio_pct"] >= TABLE["game"]["min_ratio_pct"], need
        assert g["laps"] >= 1 and abs(g["duration_s"] - 3600) <= 400


def test_predicted_time_comes_from_the_virtual_rider():
    fmt = next(f for f in TABLE["game"]["formats"] if f["need"] == "intense")
    sim = coach_game.simulate(fmt, CLIMB.chunks, FTP, 3600, True)
    climb_w = FTP * fmt["climb_pct"] / 100.0
    assert coach_game.rider_power(fmt, 6.0, FTP) == climb_w                    # Z4 en montée
    assert sim["zone_s"]["Z4"] > 0 and sim["zone_s"]["Z4"] > sim["zone_s"]["Z5"]
    assert abs(sum(sim["zone_s"].values()) - sim["duration_s"]) < 1e-6


def test_format_rejected_under_70_percent_of_the_workout():
    # Entraînement intense de référence : 50 min dans les zones ; la côte en donne 31 min (63 %).
    assert coach_game.choose("intense", 3600, 3000.0, ALL, FTP, TABLE) is None
    assert coach_game.choose("intense", 3600, 900.0, ALL, FTP, TABLE)["route_id"] == "cote"


def test_no_format_possible_gives_erg_only():
    assert coach_game.choose("intense", 3600, None, [FLAT, ALPS], FTP, TABLE) is None   # aucune montée de 4 à 10 min
    assert coach_game.choose("light", 3600, None, [], FTP, TABLE) is None
    short = cand("court", [(100.0, 0.0)] * 20, loop=False)                            # 2 km : trop court pour le survivant
    assert coach_game.choose("anaerobic", 3600, None, [short], FTP, TABLE) is None


def test_advice_carries_the_game_next_to_the_workout():
    plain = coach.advise(base_history(), FTP, TODAY, Inputs(chosen_need="intense"), TABLE, [], [CLIMB])
    assert plain["route"]["route_id"] == "cote"
    msg = build_coach_message(1, plain)
    assert_valid(msg)
    assert msg["route"] == plain["route"]
    rest = coach.advise(base_history(), FTP, TODAY, Inputs(chosen_need="ftp_test"), TABLE, [], ALL)
    assert rest["route"] is None                                                   # test de FTP : pas de jeu
    without = coach.advise(base_history(), FTP, TODAY, Inputs(chosen_need="intense"), TABLE, [])
    assert without["route"] is None


def test_catalog_routes_and_time_budget(tmp_path):
    write_world(tmp_path, "plat", 20000.0, created="2026-11-07T00:00:00+01:00", grade=lambda s: 0.0)
    write_world(tmp_path, "col", 10000.0, created="2026-11-07T00:00:00+01:00",
                grade=lambda s: 0.0 if s < 2000.0 else 7.0)
    t0 = time.perf_counter()
    found = coach_game.load_candidates(tmp_path, tmp_path / "gpx")
    choices = [coach_game.choose(n, 3600, None, found, FTP, TABLE) for n in ("recovery", "light", "anaerobic")]
    assert time.perf_counter() - t0 < 2.0                                        # cahier : sous 2 s (PC : à mesurer)
    assert {c.id for c in found} == {"plat", "col"}
    assert all(c is not None and c["route_id"] == "plat" for c in choices)
