"""Lot TT3 : bonus Aspiration + (abri × 1,5 plafonné à 0,55, portée 25 m, 40 s, avec des bots)."""

from __future__ import annotations

import pytest

from openride_core import draft
from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.powerups import DEFAULT_TABLE, Context, PowerUps

PLAN = PhysicsParams(mass_kg=84.0, cda_m2=0.32, crr=0.004)
WITH_BOTS = Context(has_bots=True)


class Src:
    def __init__(self, s: float, ident: str = "b1", lane: float | None = None) -> None:
        self.s, self.id, self.kind, self.v = s, ident, "constant", 11.0
        if lane is not None:
            self.lane = draft.Lane(lane, lane)


def boosted() -> PowerUps:
    pu = PowerUps(set_name="tactiques")
    pu.reserve = "draft_plus"
    assert pu.activate(0.0, WITH_BOTS)
    return pu


def test_table_line():
    s = DEFAULT_TABLE.specs["draft_plus"]
    assert (s.effect, s.factor, s.duration_s, s.cap, s.reach_m) == ("draft", 1.5, 40.0, 0.55, 25.0)
    assert s.sets == ("tactiques",)


def test_drawn_and_allowed_only_with_bots():
    pu = PowerUps(seed=2, set_name="tactiques")
    assert "draft_plus" not in {pu.award("segment", Context()) for _ in range(500)}
    assert "draft_plus" in {pu.award("segment", WITH_BOTS) for _ in range(500)}
    pu.reserve = "draft_plus"
    assert not pu.activate(1.0, Context()) and pu.contract()["refused"]["reason"] == "no_bots"
    assert pu.reserve == "draft_plus"


def test_multiplier_cap_and_reach():
    boost = boosted().draft_boost()
    assert boost is not None
    rider = 0.0
    for d in (3.0, 5.0, 8.0, 12.0):
        base, _ = draft.best_draft(rider, [Src(d)])
        more, _ = draft.best_draft(rider, [Src(d)], boost=boost)
        assert more == pytest.approx(min(base * 1.5, 0.55))
    # Au-delà de 15 m d'écart (16,7 m d'axe à axe), plus rien sans bonus ; un peu d'abri jusqu'à 25 m avec.
    far = 20.0 + draft.BIKE_LENGTH_M
    assert draft.best_draft(rider, [Src(far)])[0] == 0.0
    assert draft.best_draft(rider, [Src(far)], boost=boost)[0] > 0.0
    assert draft.best_draft(rider, [Src(26.0 + draft.BIKE_LENGTH_M)], boost=boost)[0] == 0.0


def test_cap_never_exceeded_in_a_group():
    boost = boosted().draft_boost()
    group = [Src(2.2, "a", 1.2), Src(2.4, "b", 0.6), Src(2.6, "c", 1.8), Src(4.5, "d", 1.2), Src(4.6, "e", 0.6)]
    alpha, _ = draft.best_draft(0.0, group, lane_m=1.2, boost=boost)
    assert alpha == pytest.approx(0.55)
    for b in group:   # les bots n'ont jamais le bonus : leur abri ne change pas
        assert draft.draft_for(b.s, group, skip=b, lane_m=b.lane.m)[0] <= draft.ALPHA_GROUP_CAP


def test_no_boost_without_the_bonus_or_when_held_off():
    pu = PowerUps(set_name="tactiques")
    assert pu.draft_boost() is None
    pu.reserve = "aero"
    pu.activate(0.0)
    assert pu.draft_boost() is None


def _gain(alpha0: float, horizon_s: float = 60.0, dt: float = 0.02) -> float:
    """Temps gagné par un cycliste qui passe de l'abri `alpha0` à l'abri renforcé pendant 40 s (250 W, plat)."""
    alpha1 = min(alpha0 * 1.5, 0.55)
    warm = RiderPhysics(PLAN, 0.0, 10.0)
    for _ in range(int(400 / dt)):
        warm.step(250.0, 0.0, 0.0, dt, alpha_draft=alpha0)
    v = warm.v
    a, b = RiderPhysics(PLAN, 0.0, v), RiderPhysics(PLAN, 0.0, v)
    t = 0.0
    while t < horizon_s - 1e-9:
        t += dt
        a.step(250.0, 0.0, 0.0, dt, alpha_draft=alpha1 if t <= 40.0 else alpha0)
        b.step(250.0, 0.0, 0.0, dt, alpha_draft=alpha0)
    return (a.s - b.s) / v


def test_gain_on_the_flat():
    """Roue dans la roue à 1,9 m de la roue (α = 0,27) : 2,2 s, dans la cible de 1,5 à 2,5 s. Collé (0,5 m,
    α = 0,38, plafonné à 0,55) : 3,3 s, au-dessus de la cible : valeur du plan gardée, ajustement au lot TT8."""
    assert 1.5 <= _gain(draft.draft_coefficient(1.9)) <= 2.5
    assert _gain(draft.draft_coefficient(0.5)) == pytest.approx(3.3, abs=0.1)


def test_sim_feel_follows_the_draft():
    from openride_core.wind import grade_offset_pct
    a0 = draft.draft_coefficient(1.9)
    plain = grade_offset_pct(11.3, 0.0, a0, 200.0, PLAN, 10.0)
    more = grade_offset_pct(11.3, 0.0, min(a0 * 1.5, 0.55), 200.0, PLAN, 10.0)
    assert more < plain < 0.0 and more - plain == pytest.approx(-0.5, abs=0.25)
