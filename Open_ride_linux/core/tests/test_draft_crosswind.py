"""Vent de travers et bordure (lot AS3).

Critères du cahier `docs/lots/LOT_AS3_bordure_vent_travers.md` §7 : vent nul ou de face identique à AS2
(2), zone décalée sous le vent et bornée à 1,5 m, abri du coureur placé en diagonale (3), abri du coureur
resté dans la roue (4), éventail d'un groupe de 5 bots borné par la voie (5) ; placement de la séance.
"""

import pytest
from openride_core import draft as d
from openride_core.bots import ConstantPowerBot
from openride_core.config import Config
from openride_core.wind import WindModel
from test_draft import FlatRoute, flat_params, make_session, run

DT = 0.02
V = 10.0
LEFT_45 = -V      # vent de travers venant de gauche, lacet de 45° à 10 m/s (cross < 0 : de gauche)


def lead_at(lane_m: float, s: float = 100.0, bot_id: str = "b1") -> d.Source:
    return d.Source(s, V, id=bot_id, lane_m=lane_m)


def behind(gap_m: float, s: float = 100.0) -> float:
    return s - d.BIKE_LENGTH_M - gap_m


# --- critère 2 : vent nul ou de face ------------------------------------------------------------

@pytest.mark.parametrize("head", [0.0, 5.0, -3.0])
@pytest.mark.parametrize("dx", [0.0, 0.4, 0.9])
def test_no_crosswind_same_as_as2(head, dx):
    lead = lead_at(d.RIDER_LANE_M + dx)
    got, _ = d.draft_for(behind(2.0), [lead], rider_v=V, head_mps=head, cross_mps=0.0, lane_m=d.RIDER_LANE_M)
    assert got == pytest.approx(d.draft_coefficient(2.0) * d.lateral_factor(dx))
    assert d.crosswind_shift_m(2.0, V, head, 0.0) == 0.0
    assert d.echelon_lane(d.RIDER_LANE_M, 2.0, V, head, 0.0) == d.RIDER_LANE_M


# --- critère 3 : zone décalée, coureur placé en diagonale ---------------------------------------

def test_shift_goes_downwind_and_is_bounded():
    assert d.crosswind_shift_m(1.0, V, 0.0, LEFT_45) == pytest.approx(1.0)     # gap · tan 45°, à droite
    assert d.crosswind_shift_m(2.0, V, 0.0, LEFT_45) == d.CROSSWIND_SHIFT_MAX_M  # ~2 m, borné à 1,5 m
    assert d.crosswind_shift_m(2.0, V, 0.0, -LEFT_45) == -d.CROSSWIND_SHIFT_MAX_M  # vent de droite : à gauche
    assert d.crosswind_shift_m(0.5, V, 0.0, V * 0.1) == pytest.approx(-0.05)


def test_rider_in_diagonal_keeps_most_of_the_draft():
    calm, _ = d.draft_for(behind(2.0), [lead_at(1.0)], rider_v=V, lane_m=1.0)
    placed, bot_id = d.draft_for(behind(2.0), [lead_at(1.0)], rider_v=V, cross_mps=LEFT_45,
                                 lane_m=1.0 + d.CROSSWIND_SHIFT_MAX_M)
    assert bot_id == "b1"
    assert placed >= 0.8 * calm - 1e-9
    assert d.crosswind_residual(V, 0.0, LEFT_45) == pytest.approx(0.8)
    assert d.crosswind_residual(V, 0.0, 0.0) == 1.0


# --- critère 4 : coureur resté dans la roue ------------------------------------------------------

@pytest.mark.parametrize("gap", [0.5, 1.0, 2.0])
def test_rider_left_in_the_wheel_loses_draft(gap):
    calm, _ = d.draft_for(behind(gap), [lead_at(1.2)], rider_v=V, lane_m=1.2)
    wheel, _ = d.draft_for(behind(gap), [lead_at(1.2)], rider_v=V, cross_mps=LEFT_45, lane_m=1.2)
    assert wheel <= 0.6 * calm
    if gap >= 1.0:
        assert wheel <= 0.4 * calm


# --- placement : la diagonale, bornée par la voie ----------------------------------------------

def test_auto_lane_targets_the_diagonal_within_the_lane():
    rider = d.Lane(d.RIDER_LANE_M, d.RIDER_LANE_M)
    others = [(d.BIKE_LENGTH_M + 1.0, V, d.Lane(1.0, 1.0))]
    target, passing = d.lane_target(0.0, V, rider, others, cross_mps=LEFT_45)
    assert not passing and target == pytest.approx(2.0)
    target, _ = d.lane_target(0.0, V, rider, [(d.BIKE_LENGTH_M + 1.0, V, d.Lane(2.1, 2.1))], cross_mps=LEFT_45)
    assert target == d.LANE_MAX_M                         # la diagonale sortirait de la voie : le bord
    target, _ = d.lane_target(0.0, V, rider, others, cross_mps=0.0)
    assert target == pytest.approx(1.0)                   # sans vent : la roue (AS2)


def _echelon(cross: float, n: int = 5, gap: float = 1.0, seconds: float = 20.0) -> list[float]:
    """Groupe de `n` bots en file à la même vitesse : abri de chacun une fois les places prises."""
    lanes = [d.Lane(d.BOT_LANE_M, d.BOT_LANE_M, rank=i) for i in range(n)]
    s = [100.0 - i * (d.BIKE_LENGTH_M + gap) for i in range(n)]
    runners = list(zip(s, [V] * n, lanes))
    for _ in range(int(seconds / DT)):
        d.update_lanes(runners, DT, wind_at=lambda _s: (0.0, cross))
    for lane in lanes:
        assert d.LANE_MIN_M - 1e-9 <= lane.m <= d.LANE_MAX_M + 1e-9 and not lane.passing
    sources = [d.Source(si, V, id=f"b{i}", lane_m=lane.m) for i, (si, lane) in enumerate(zip(s, lanes))]
    return [d.draft_for(si, sources, rider_v=V, cross_mps=cross, skip=src, lane_m=src.lane_m)[0]
            for si, src in zip(s, sources)]


# --- critère 5 : éventail et bordure --------------------------------------------------------

@pytest.mark.parametrize("cross", [LEFT_45, -LEFT_45, 1.3 * LEFT_45])
def test_group_of_five_echelon_is_bounded_by_the_lane(cross):
    drafts = _echelon(cross)
    sheltered = [a for a in drafts[1:] if a >= 0.15]
    assert len(sheltered) <= 2                           # au plus 2 à 3 coureurs dans l'éventail, meneur compris
    assert all(a < 0.15 for a in drafts[1 + len(sheltered):])   # les suivants, en file au bord, exposés
    assert drafts[0] == 0.0
    if cross > 0.0:                                      # vent de droite : l'éventail a toute la voie vers l'axe
        assert len(sheltered) == 2


def test_group_without_wind_stays_in_line():
    drafts = _echelon(0.0)
    assert all(a >= 0.15 for a in drafts[1:])            # sans vent, toute la file est abritée (AS1, AS2)


# --- séance : le cycliste se place en diagonale derrière un bot -----------------------------

def test_session_rider_moves_into_the_diagonal(tmp_path, monkeypatch):
    cfg = Config()
    leader = ConstantPowerBot(250.0, bot_id="b1", params=flat_params(cfg), s=d.BIKE_LENGTH_M + 0.8, v=9.0)
    s, _ = make_session(tmp_path, monkeypatch, 5990, 225.0, [leader])   # 225 W : reste dans la roue
    s.route = FlatRoute()                      # plein nord : un vent d'ouest vient de gauche
    s.wind = WindModel("fixed", 30.0, 270.0)
    s.physics.v = 9.0
    s._on_command("start", {}, 2)
    run(s, 5.0)
    assert s._lane.m > leader.lane.m + 0.25    # à droite du bot : sous le vent
    assert d.LANE_MIN_M <= s._lane.m <= d.LANE_MAX_M
    assert s._draft > 0.1 and s._draft_bot == "b1", (s._draft, leader.s - s.physics.s)
