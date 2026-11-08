"""Lot TT4 : bonus Échappée (les suiveurs perdent ton abri et ne répondent pas à ton attaque, 20 s)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from openride_core import bot_tactics, classic, draft
from openride_core.physics import PhysicsParams, RiderPhysics
from openride_core.powerups import DEFAULT_TABLE, Context, PowerUps
from openride_core.segments import Segment

PLAN = PhysicsParams(mass_kg=84.0, cda_m2=0.32, crr=0.004)
OK = Context(has_bots=True)


def test_table_line_shared_with_the_grand_prix_stealth():
    s = DEFAULT_TABLE.specs["breakaway"]
    assert (s.effect, s.duration_s, s.sets) == ("breakaway", 20.0, ("tactiques",))
    from openride_core.grandprix.items import DEFAULT_ITEMS
    stealth = DEFAULT_ITEMS["stealth"]
    assert [e.effect for e in stealth.self_fx] == ["breakaway"]           # même effet, même table


@pytest.mark.parametrize("ctx, reason", [(Context(), "no_bots"), (Context(has_bots=True, near_finish=True), "near_finish")])
def test_refusals(ctx, reason):
    pu = PowerUps(set_name="tactiques")
    pu.reserve = "breakaway"
    assert not pu.activate(0.0, ctx) and pu.contract()["refused"]["reason"] == reason and pu.reserve == "breakaway"
    assert pu.activate(1.0, OK) and pu.unseen()


def test_near_finish_end_of_route_and_end_of_sprint():
    sprint = Segment(id="sp", name="Sprint", type="sprint", s_start=2000.0, s_end=2500.0, length_m=500.0,
                     avg_grade_pct=0.0, gain_m=0.0, category=None, source="manual")
    race = classic.ClassicRace("demo", (sprint,), 5000.0)
    near = race._near_finish
    assert near(2100.0) and near(2500.0) and not near(2050.0) and not near(2501.0)
    assert near(4600.0) and not near(4500.0)
    loop = classic.ClassicRace("demo", (sprint,), 5000.0, loop=True)
    assert not loop._near_finish(4900.0) and loop._near_finish(7400.0)     # boucle : pas d'arrivée, sprint du 2e tour


def _follow(breakaway: bool, seconds: float = 20.0, dt: float = 0.02) -> float:
    """Un bot collé derrière le cycliste (0,5 m de roue) à la puissance qui le garde là ; le cycliste roule
    250 W. Écart perdu par le suiveur après `seconds` s, avec ou sans Échappée."""
    me = RiderPhysics(PLAN, 0.0, 0.0)
    for _ in range(int(300 / dt)):
        me.step(250.0, 0.0, 0.0, dt)
    v = me.v
    gap = 0.5 + draft.BIKE_LENGTH_M
    alpha = draft.draft_coefficient(0.5)
    probe = RiderPhysics(PLAN, 0.0, v)
    # puissance du suiveur à l'équilibre dans la roue : celle du cycliste moins l'économie de l'abri
    lo, hi = 50.0, 250.0
    for _ in range(40):
        mid = (lo + hi) / 2
        probe.v = v
        probe.step(mid, 0.0, 0.0, 1.0, alpha_draft=alpha)
        lo, hi = (mid, hi) if probe.v < v else (lo, mid)
    p_follow = (lo + hi) / 2
    bot = SimpleNamespace(id="b1", kind="constant", s=-gap, v=v, params=PLAN, draft=alpha, wheel=None, push=0.0)
    phys = RiderPhysics(PLAN, -gap, v)
    me = RiderPhysics(PLAN, 0.0, v)
    t = 0.0
    while t < seconds - 1e-9:
        t += dt
        rider = draft.Source(me.s, me.v, shelters=not breakaway)
        draft.update_bots([bot], rider, dt)
        me.step(250.0, 0.0, 0.0, dt)
        phys.step(p_follow, 0.0, 0.0, dt, alpha_draft=bot.draft)
        bot.s, bot.v = phys.s, phys.v
    return (me.s - bot.s) - gap


def test_follower_loses_about_14_m_in_20_s():
    assert _follow(False) == pytest.approx(0.0, abs=0.3)
    lost = _follow(True)
    assert lost == pytest.approx(14.0, abs=4.0)


def test_rider_still_gets_shelter_from_bots_ahead():
    ahead = SimpleNamespace(id="b2", kind="constant", s=3.0, v=11.0)
    assert draft.best_draft(0.0, [ahead])[0] > 0.0      # rien ne change pour l'abri que reçoit le cycliste


def test_bots_blind_to_the_attack():
    """Un bot qui répondrait au départ du cycliste ne le voit pas pendant l'Échappée (règle de réponse de Y10)."""
    def race(unseen: frozenset) -> int:
        tac = bot_tactics.Tactics("b1", bot_tactics.Character(follow_flat=1.0, follow_climb=1.0), seed=1,
                                  mode="essai")
        bot = SimpleNamespace(id="b1", kind="constant", s=0.0, v=10.0, t=0.0, tactics=tac, wbal_pct=100.0,
                              cp_w=250.0, peak_w=0.0, segments=(), lane=None)
        field = bot_tactics.Field()
        rider_s = 2.0
        for i in range(int(120 / 0.1)):
            v_me = 10.0 + (3.0 if i * 0.1 > 60 else 0.0)   # attaque du cycliste à 60 s
            rider_s += 0.1 * v_me
            bot.s += 0.1 * 10.0
            bot.t += 0.1
            bot_tactics.update_field(field, [bot], (rider_s, v_me), 0.1, unseen=unseen)
        return tac.responses
    assert race(frozenset()) >= 1
    assert race(frozenset({bot_tactics.RIDER_ID})) == 0
