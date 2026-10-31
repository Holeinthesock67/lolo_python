"""Abri en deux dimensions et placement automatique dans la roue (lot AS2).

Critères du cahier `docs/lots/LOT_AS2_zone_laterale_placement.md` §7 : courbe `lateral_factor` (2),
placement coupé et bot décalé (3), placement dans la roue en moins de 3 s (4), dépassement sans
chevauchement ni sortie de route (5), jamais à gauche de l'axe hors dépassement (6) ; trame `state`
avec `lane_m`, réglage `ride.auto_draft`.
"""

import json
from pathlib import Path

import jsonschema
import pytest
from openride_core import draft as d
from openride_core import settings
from openride_core.bots import ConstantPowerBot
from openride_core.config import Config
from test_draft import FlatRoute, flat_params, make_session, run

IPC_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
DT = 0.02


# --- critère 2 : courbe latérale ---------------------------------------------------------------

def test_lateral_factor_bell_curve():
    assert d.lateral_factor(0.0) == 1.0 and d.lateral_factor(0.3) == 1.0
    assert d.lateral_factor(0.6) == pytest.approx(0.5, abs=0.03)
    assert d.lateral_factor(1.0) == 0.0 and d.lateral_factor(1.5) == 0.0
    assert d.lateral_factor(-0.6) == d.lateral_factor(0.6)          # symétrique
    xs = [i / 100 for i in range(0, 121)]
    values = [d.lateral_factor(x) for x in xs]
    assert all(a >= b for a, b in zip(values, values[1:]))          # décroissante
    assert max(abs(a - b) for a, b in zip(values, values[1:])) < 0.05   # sans saut


# --- critère 3 : placement coupé, bot décalé ------------------------------------------------------

def test_offset_bot_gives_almost_no_draft():
    lead = d.Source(100.0, 10.0, id="b1", lane_m=d.RIDER_LANE_M + 0.9)
    rider_s = 100.0 - d.BIKE_LENGTH_M - 2.0
    in_wheel, _ = d.draft_for(rider_s, [d.Source(100.0, 10.0, id="b1", lane_m=d.RIDER_LANE_M)],
                              lane_m=d.RIDER_LANE_M)
    offset, _ = d.draft_for(rider_s, [lead], lane_m=d.RIDER_LANE_M)
    assert in_wheel > 0.2
    assert offset < 0.15 * in_wheel


def test_auto_off_keeps_home_lane():
    rider = d.Lane(d.RIDER_LANE_M, d.RIDER_LANE_M, auto=False)
    bot = d.Lane(d.BOT_LANE_M, d.BOT_LANE_M)
    for _ in range(int(5.0 / DT)):
        d.update_lanes([(0.0, 10.0, rider), (d.BIKE_LENGTH_M + 2.0, 10.0, bot)], DT)
    assert rider.m == d.RIDER_LANE_M


# --- critère 4 : placement dans la roue ------------------------------------------------------------

def test_auto_draft_reaches_the_wheel_in_three_seconds():
    rider = d.Lane(d.RIDER_LANE_M, d.RIDER_LANE_M)
    bot = d.Lane(d.BOT_LANE_M, d.BOT_LANE_M)
    rates = []
    t = 0.0
    while abs(rider.m - bot.m) >= 0.1:
        d.update_lanes([(0.0, 10.0, rider), (d.BIKE_LENGTH_M + 2.0, 10.0, bot)], DT)
        rates.append(rider.rate)
        t += DT
        assert t < 3.0, f"encore à {abs(rider.m - bot.m):.2f} m de la ligne après 3 s"
    assert max(abs(r) for r in rates) <= d.LANE_RATE_MPS + 1e-9
    assert max(abs(a - b) for a, b in zip(rates, rates[1:])) <= d.LANE_ACCEL_MPS2 * DT + 1e-9   # sans à-coup
    alpha, who = d.draft_for(0.0, [d.Source(d.BIKE_LENGTH_M + 2.0, 10.0, id="b1", lane_m=bot.m)], lane_m=rider.m)
    assert alpha == pytest.approx(d.draft_coefficient(2.0), rel=0.02) and who == "b1"   # abri plein


def test_faster_leader_is_not_followed():
    rider = d.Lane(d.RIDER_LANE_M, d.RIDER_LANE_M)
    target, passing = d.lane_target(0.0, 9.0, rider, [(5.0, 10.0, d.Lane(d.BOT_LANE_M, d.BOT_LANE_M))])
    assert target == d.RIDER_LANE_M and not passing


# --- critères 5 et 6 : dépassement ------------------------------------------------------------------

def overtake(rider_v: float, bot_v: float, rider_lane: float, bot_lane: float, seconds: float = 40.0):
    rider, bot = d.Lane(rider_lane, d.RIDER_LANE_M), d.Lane(bot_lane, d.BOT_LANE_M)
    rs, bs = 0.0, d.BIKE_LENGTH_M + 6.0
    overlap_dx, lanes = [], []
    for _ in range(int(seconds / DT)):
        d.update_lanes([(rs, rider_v, rider), (bs, bot_v, bot)], DT)
        rs, bs = rs + rider_v * DT, bs + bot_v * DT
        if abs(bs - rs) < d.BIKE_LENGTH_M:
            overlap_dx.append(abs(rider.m - bot.m))
        lanes.append((rider.m, rider.passing, bot.m, bot.passing))
    return rider, bot, overlap_dx, lanes


@pytest.mark.parametrize("rider_lane,bot_lane", [(d.BOT_LANE_M, d.BOT_LANE_M), (d.RIDER_LANE_M, d.RIDER_LANE_M)])
def test_overtake_keeps_side_clearance_and_stays_on_the_road(rider_lane, bot_lane):
    rider, bot, overlap_dx, lanes = overtake(11.0, 10.0, rider_lane, bot_lane)
    assert overlap_dx, "le dépassement n'a pas eu lieu"
    assert min(overlap_dx) >= d.SIDE_CLEAR_M - 1e-6
    half_road = 3.0
    for r_m, r_pass, b_m, b_pass in lanes:
        assert -half_road < r_m < half_road and -half_road < b_m < half_road   # jamais hors de la route
        if not r_pass:
            assert r_m >= 0.0                                                # critère 6
        if not b_pass:
            assert b_m >= 0.0
    assert rider.m == pytest.approx(d.RIDER_LANE_M, abs=0.01)                 # revenu à droite


def test_slow_creep_into_the_wheel_also_overtakes_cleanly():
    rider, bot, overlap_dx, _ = overtake(10.1, 10.0, d.BOT_LANE_M, d.BOT_LANE_M, seconds=120.0)
    assert overlap_dx and min(overlap_dx) >= d.SIDE_CLEAR_M - 0.02   # à 0,1 m/s : décalé avant de toucher la roue


def test_bot_passes_a_fixed_rider():
    rider = d.Lane(d.RIDER_LANE_M, d.RIDER_LANE_M, auto=False)
    bot = d.Lane(d.RIDER_LANE_M, d.BOT_LANE_M)   # le bot a pris la roue du cycliste
    rs, bs = 10.0, 10.0 - d.BIKE_LENGTH_M - 6.0
    dx = []
    for _ in range(int(20.0 / DT)):
        d.update_lanes([(rs, 9.0, rider), (bs, 10.0, bot)], DT)
        rs, bs = rs + 9.0 * DT, bs + 10.0 * DT
        if abs(bs - rs) < d.BIKE_LENGTH_M:
            dx.append(abs(rider.m - bot.m))
    assert rider.m == d.RIDER_LANE_M and dx and min(dx) >= d.SIDE_CLEAR_M - 1e-6


def test_order_of_runners_does_not_matter():
    def pack():
        return [(0.0, 10.5, d.Lane(1.2, 1.2)), (4.0, 10.0, d.Lane(2.1, 2.1)), (8.0, 9.8, d.Lane(2.1, 2.1))]

    a, b = pack(), pack()
    for _ in range(200):
        d.update_lanes(a, DT)
        d.update_lanes(list(reversed(b)), DT)
    assert [r[2].m for r in a] == [r[2].m for r in b]


# --- séance : trame, bots, réglage -------------------------------------------------------------------

def test_session_places_the_rider_in_the_wheel_and_sends_lane_m(tmp_path, monkeypatch):
    validator = jsonschema.Draft202012Validator(
        json.loads((IPC_DIR / "state.schema.json").read_text(encoding="utf-8")))
    cfg = Config()
    lead = ConstantPowerBot(250.0, bot_id="b1", params=flat_params(cfg), s=d.BIKE_LENGTH_M + 1.0, v=9.0)
    s, _ = make_session(tmp_path, monkeypatch, 6080, 250.0, [lead])
    s.route = FlatRoute()
    s.physics.v = 9.0
    s._on_command("start", {}, 2)
    run(s, 3.0)
    s.state.bots = [b.to_dict() for b in s.bots]   # posé par la boucle d'envoi, absente ici
    frame = s.state.to_dict()
    assert abs(frame["lane_m"] - frame["bots"][0]["lane_m"]) < 0.1
    assert frame["draft"] > 0.2 and frame["draft_bot"] == "b1"
    assert not list(validator.iter_errors(frame))


def test_session_auto_draft_off_keeps_the_rider_at_home(tmp_path, monkeypatch):
    cfg = Config()
    lead = ConstantPowerBot(250.0, bot_id="b1", params=flat_params(cfg), s=d.BIKE_LENGTH_M + 1.0, v=9.0)
    s, _ = make_session(tmp_path, monkeypatch, 6084, 250.0, [lead])
    s.cfg.ride.auto_draft = "off"
    s.route = FlatRoute()
    s.physics.v = 9.0
    s._on_command("start", {}, 2)
    run(s, 3.0)
    s.state.bots = [b.to_dict() for b in s.bots]
    frame = s.state.to_dict()
    assert frame["lane_m"] == d.RIDER_LANE_M and frame["bots"][0]["lane_m"] == d.BOT_LANE_M
    assert frame["draft"] < 0.03                       # bot 0,9 m à droite : presque pas d'abri


def test_no_bot_no_lane_field(tmp_path, monkeypatch):
    s, _ = make_session(tmp_path, monkeypatch, 6088, 250.0, [])
    s._on_command("start", {}, 2)
    run(s, 1.0)
    assert "lane_m" not in s.state.to_dict()


def test_auto_draft_setting():
    cfg = Config()
    item = next(it for it in settings.current(cfg) if it["key"] == "ride.auto_draft")
    assert item["value"] == "on" and item["choices"] == ["on", "off"] and item["group"] == "ride"
    assert settings.get("ride.auto_draft").scope == "profil"
    with pytest.raises(settings.SettingError):
        settings.check(cfg, "ride.auto_draft", "peut-être")


def test_grouped_start_grid():
    """Bots recréés au départ à la place du cycliste : grille par deux, 0,9 m de chaque côté, aucun contact."""
    bots = [ConstantPowerBot(250.0, bot_id=f"bot{i}", s=100.0) for i in range(1, 5)]
    d.start_grid(bots, 100.0)
    rider = (100.0, 0.0, d.Lane(d.RIDER_LANE_M, d.RIDER_LANE_M))
    runners = [rider] + [(b.s, 0.0, b.lane) for b in bots]
    assert [(round(b.s - 100.0, 2), b.lane.m) for b in bots] == [
        (0.0, d.BOT_LANE_M), (0.0, d.LANE_MIN_M), (-d.START_ROW_M, d.BOT_LANE_M), (-d.START_ROW_M, d.LANE_MIN_M)]
    for i, (s1, _, a) in enumerate(runners):
        for s2, _, b in runners[i + 1:]:
            assert abs(s1 - s2) >= d.BIKE_LENGTH_M or abs(a.m - b.m) >= d.SIDE_CLEAR_M - 1e-9
    for _ in range(int(2.0 / DT)):   # à l'arrêt, personne ne bouge vers un autre
        d.update_lanes(runners, DT)
    assert runners[0][2].m == pytest.approx(d.RIDER_LANE_M)
