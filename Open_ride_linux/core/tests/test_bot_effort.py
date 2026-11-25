"""Effort des bots selon la durée de la course et l'objectif (lot BT1, décisions du propriétaire du
15 novembre 2026) : courbe de puissance, parts par objectif, durée recalculée, vélodrome par épreuve,
réglage commun `bots.objective`, banc `bots_race` de 5 min à 2 h."""

from __future__ import annotations

import pytest

from openride_core import bot_effort as be
from openride_core.config import CHOICES, PROFILE_KEYS, Config
from openride_core.settings import SETTINGS

from test_grandprix_session import env  # noqa: F401  (fixture du Grand Prix)


def test_curve_is_anchored_on_the_ftp_and_falls_with_time():
    assert be.curve_pct(3600.0) == pytest.approx(100.0)
    assert be.curve_pct(60.0) == 160.0 and be.curve_pct(10.0) == 160.0       # bornée aux extrémités
    assert be.curve_pct(10800.0) == 80.0 and be.curve_pct(20000.0) == 80.0
    assert be.curve_pct(300.0) == pytest.approx(120.0) and be.curve_pct(7200.0) == pytest.approx(88.0)
    ts = [60, 120, 300, 600, 900, 1200, 2400, 3600, 5400, 7200, 10800]
    vals = [be.curve_pct(t) for t in ts]
    assert vals == sorted(vals, reverse=True)
    assert 105.0 > be.curve_pct(1800.0) > 100.0


def test_objectives_validated_on_15_november():
    assert be.OBJECTIVES == {"recovery": 55.0, "endurance": 65.0, "tempo": 80.0, "threshold": 92.0, "max": 100.0}
    assert be.DEFAULT_OBJECTIVE == "tempo" == Config().bots.objective
    assert CHOICES[("bots", "objective")] == tuple(be.OBJECTIVES)
    assert ("bots", "objective") in PROFILE_KEYS                 # réglage du joueur, gardé d'une séance à l'autre
    assert any(s.key == "bots.objective" for s in SETTINGS)
    # Lot NI3 : sa seule place est la ligne « Intensité du jour » des écrans Prêt, plus « Réglages › Séance »
    assert next(s for s in SETTINGS if s.key == "bots.objective").menu_group == "screen"
    assert be.share_pct("inconnu") == 80.0


def test_target_follows_the_race_duration():
    # Temps d'un passage proportionnel à 1 / puissance (plat rapide) : 250 W -> 10 min pour 5 km.
    def time_of(p):
        return 600.0 * 250.0 / p

    pct, dur = be.target_pct(100.0, be.Effort("max"), 250.0, time_of, 5000.0)
    assert pct == pytest.approx(be.curve_pct(dur), rel=0.02) and 100.0 < pct < 115.0 and 500.0 < dur < 600.0
    pct_t, _ = be.target_pct(100.0, be.Effort("tempo"), 250.0, time_of, 5000.0)
    assert pct_t < pct * 0.85
    long_pct, long_dur = be.target_pct(100.0, be.Effort("max", course_m=60000.0), 250.0, time_of, 5000.0)
    assert long_dur > 6000.0 and long_pct < 92.0                 # 12 passages : plus de 1 h 40, sous la FTP
    lvl, _ = be.target_pct(110.0, be.Effort("max"), 250.0, time_of, 5000.0)
    assert lvl > pct                                             # le niveau reste un réglage fin
    fixed, fdur = be.target_pct(100.0, be.Effort("max", duration_s=3600.0), 250.0, time_of, 5000.0)
    assert fdur == 3600.0 and fixed == pytest.approx(100.0)


def test_track_objective_follows_the_event():
    assert be.track_effort("kilo", {}, 250.0) == be.Effort("max", 1000.0, None)
    assert be.track_effort("pursuit", {"distance_m": 3000}, 250.0) == be.Effort("max", 3000.0, None)
    assert be.track_effort("scratch", {"laps": 20}, 250.0) == be.Effort("tempo", 5000.0, None)
    assert be.track_effort("hour", {}, 250.0) == be.Effort("max", None, 3600.0)
    assert be.track_effort("free", {}, 250.0).objective == "tempo"
    assert be.track_effort("elimination", {}, 250.0).course_m == be.TRACK_DEFAULT_LAPS * 250.0
    # élimination : une élimination tous les `every_laps` tours, une par adversaire
    assert be.track_effort("elimination", {"opponents": 7, "every_laps": 4}, 250.0).course_m == 7 * 4 * 250.0
    from openride_core import track

    assert set(be.TRACK_EFFORT) == set(track.EVENTS)            # toutes les épreuves ont leur effort


@pytest.mark.parametrize("route,objective,minutes", [
    ("demo", "max", (8, 16)),        # 5 km : course courte, au-dessus de la FTP
    ("plat", "tempo", (25, 45)),      # 20 km
    ("col", "max", (35, 60)),         # 10 km dont 8 à 7 %
])
def test_bench_rouleur_finishes_with_the_rider_at_the_same_effort(route, objective, minutes):
    from openride_core.tools import bots_race as br

    out = br.race(route, 100.0, ["rouleur", "climber"], objective=objective)
    rouleur = next(r for r in out["bots"] if r["profile"] == "rouleur")
    assert abs(rouleur["gap_pct"]) <= br.GAP_LIMIT_PCT, out
    assert minutes[0] * 60 <= out["race_s_est"] <= minutes[1] * 60, out["race_s_est"]
    assert out["rider_finish_s"] == pytest.approx(out["race_s_est"], rel=0.05)
    share = be.share_pct(objective) / 100.0
    assert out["rider_power_w"] == pytest.approx(250.0 * share * be.curve_pct(out["race_s_est"]) / 100.0, rel=0.02)


def test_two_hour_race_stays_under_the_ftp(tmp_path):
    """Course de 2 h (plat de 20 km, 4 passages estimés) : l'effort à fond tombe sous 90 % de la FTP."""
    from openride_core.bots import RefRider, RouteProfile, effort_target
    from openride_core.physics import PhysicsParams
    from openride_core.tools.bots_race import prepare_route
    from openride_core.route import load_world

    rid = prepare_route("plat", tmp_path)
    route = load_world(tmp_path / f"{rid}.world").route
    pct, dur = effort_target(RouteProfile(route), RefRider(250.0, PhysicsParams()), 100.0,
                             be.Effort("max", course_m=4 * route.length_m))
    assert 6000.0 < dur < 9000.0 and 85.0 < pct < 92.0


def test_session_uses_the_mode_course(env):
    """Grand Prix : longueur de la course (tours × tour) ; vélodrome : épreuve ; ailleurs, l'objectif commun."""
    make = env[0]
    s, _, _ = make(5700, laps=3)
    s.cfg.bots.objective = "endurance"
    assert s._bot_effort(None) == be.Effort("endurance", None)
    assert s._bot_effort("grandprix") == be.Effort("endurance", 3 * s.route.length_m)
    s._track_choice = ("kilo", {})
    assert s._bot_effort("track").objective == "max"
    s._track_choice = None
    s._on_command("start", {"mode": "grandprix"}, 2)
    targets = {b.effort_target for b in s.bots}
    assert all(t is not None for t in targets) and all(t[0] < 100.0 for t in targets)   # Endurance : sous la FTP
