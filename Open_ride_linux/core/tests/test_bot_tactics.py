"""Tactique des bots à profil (lot Y10) : critères du cahier `docs/lots/LOT_Y10_comportement_bots_core.md` §7.

1. Pas d'un bot sous 0,1 ms (5 bots, 50 Hz).
2. Abri : un bot à 1,5 m derrière un autre va plus vite que seul ; aucun abri derrière un fantôme.
3. Trois rouleurs sur 10 km de plat : au moins 8 changements de tête ; pas de relais en montée ni sous 30 %.
4. Montée de 5 km : le grimpeur attaque une fois au plus, au-dessus de 50 % de réserve ; le diesel jamais ;
   une attaque du cycliste est suivie par au moins un bot sur 20 tirages.
5. Déterminisme : même graine, mêmes positions après 1 h ; autre graine, autre course.
6. Calibrage du lot T13 tenu à ± 2 % (moyenne des bots sur plusieurs graines, forme du jour comprise).

Petite course sans séance (`race`) : placement (AS2), abri et roue (AS1), tactique, pas des bots, dans l'ordre
de la séance.
"""

from __future__ import annotations

from dataclasses import replace
import time

import pytest

from openride_core import bot_tactics as bt
from openride_core import draft
from openride_core.bots import PROFILES, ConstantPowerBot, ProfileBot
from openride_core.physics import PhysicsParams, RiderPhysics

from test_profile_bots import FakeRoute, seg



class Rider:
    """Cycliste simulé : puissance donnée par `power(t)`, même physique que les bots."""

    def __init__(self, power, s: float = 0.0, mass_kg: float = 79.0) -> None:
        self.power = power
        self.physics = RiderPhysics(PhysicsParams(mass_kg=mass_kg), s=s)
        self.lane = draft.Lane(draft.RIDER_LANE_M, draft.RIDER_LANE_M)
        self.draft = 0.0

    @property
    def s(self) -> float:
        return self.physics.s

    @property
    def v(self) -> float:
        return self.physics.v


def race(bots, route, seconds: float, dt: float = 0.1, rider: Rider | None = None, seed: int = 1,
         mode: str = "classic", segments=(), on_step=None):
    for b in bots:
        b.segments = tuple(segments)
    bt.start_race(bots, seed, mode)
    draft.start_grid(bots, rider.s if rider else 0.0)
    field = bt.Field()
    t = 0.0
    while t < seconds:
        runners = [(b.s, b.v, b.lane) for b in bots]
        if rider is not None:
            runners.append((rider.s, rider.v, rider.lane))
        draft.update_lanes(runners, dt, route.length_m, route.is_loop)
        src = draft.Source(rider.s, rider.v, lane_m=rider.lane.m) if rider is not None else None
        draft.update_bots(bots, src, dt, route.length_m, route.is_loop)
        if rider is not None:
            target, _ = draft.best_draft(rider.s, bots, route.length_m, route.is_loop, rider.v, 0.0, 0.0,
                                         lane_m=rider.lane.m)
            rider.draft = draft.smooth(rider.draft, target, dt)
            here = route.sample(rider.s)
            rider.physics.step(rider.power(t), here.grade_pct, here.alt_m, dt, alpha_draft=rider.draft)
        bt.update_field(field, bots, (rider.s, rider.v) if rider else None, dt,
                                 lambda s: route.sample(s).grade_pct, route.length_m, route.is_loop)
        for b in bots:
            b.step(dt, route)
        t += dt
        if on_step is not None:
            on_step(t, field)
    return field


ROUTE_FLAT = FakeRoute(12000.0)
CLIMB_ROUTE = FakeRoute(6000.0, lambda s: 6.0 if s >= 500.0 else 0.0)
CLIMB = (seg("climb", 500.0, 5500.0),)


def head_changes(bots, route, seconds, **kw):
    heads = []

    def on(t, field):
        lead = max(bots, key=lambda b: b.s)
        if lead.s < route.length_m and (not heads or heads[-1] != lead.id):
            heads.append(lead.id)

    race(bots, route, seconds, on_step=on, **kw)
    return len(heads) - 1


# --- module pur ------------------------------------------------------------------------------------------

def test_draws_depend_only_on_the_seed_and_keys():
    assert bt.draw(7, "b1", "forme") == bt.draw(7, "b1", "forme")
    assert bt.draw(7, "b1", "forme") != bt.draw(8, "b1", "forme")
    assert all(0.0 <= bt.draw(s, "x") < 1.0 for s in range(200))


def test_durability_and_relay_duration():
    assert bt.durability_factor(3599.0, 3.0) == 1.0
    assert bt.durability_factor(3600.0 + 3600.0, 3.0) == pytest.approx(0.97)
    assert bt.durability_factor(30 * 3600.0, 3.0) == bt.DURABILITY_FLOOR
    assert bt.relay_duration_s(30.0) == 30.0 and bt.relay_duration_s(100.0) == 60.0
    assert bt.relay_duration_s(65.0) == pytest.approx(45.0)


def test_profiles_carry_their_character():
    climber, diesel, sprinter = (PROFILES[p].character for p in ("climber", "diesel", "sprinter"))
    assert climber.attack_chance > PROFILES["rouleur"].character.attack_chance > 0.0
    assert climber.attack_window[1] < PROFILES["rouleur"].character.attack_window[0]   # plus tôt
    assert diesel.attack_chance == diesel.sprint_attack_chance == 0.0
    assert not sprinter.relays
    assert sprinter.durability_pct_per_h > climber.durability_pct_per_h > diesel.durability_pct_per_h


def test_form_of_the_day_from_the_seed():
    forms = set()
    for seed in range(30):
        b = ProfileBot("rouleur", bot_id="b1")
        bt.start_race([b], seed, "classic")
        assert 0.97 <= b.tactics.form <= 1.03
        assert b.cp_w == pytest.approx(b.base_cp_w * b.tactics.form)
        forms.add(round(b.tactics.form, 4))
    assert len(forms) > 20
    b = ProfileBot("rouleur", bot_id="b1")
    bt.start_race([b], 3, "essai")
    assert b.tactics.form == 1.0 and b.cp_w == b.base_cp_w


def test_mode_none_changes_nothing():
    a, b = ProfileBot("climber", bot_id="a"), ProfileBot("climber", bot_id="b")
    for x in (a, b):
        x.segments = CLIMB
    bt.start_race([a], 1, "none")
    for _ in range(20000):
        a.step(0.05, CLIMB_ROUTE)
        b.step(0.05, CLIMB_ROUTE)
    assert a.s == b.s and a.wbal.w_bal_j == b.wbal.w_bal_j
    with pytest.raises(ValueError):
        bt.start_race([a], 1, "vélodrome")


def test_long_ride_fatigue_lowers_the_cp_after_an_hour():
    b = ProfileBot("sprinter", bot_id="s")
    bt.start_race([b], 1, "essai")
    b.t = 2 * 3600.0
    b.step(0.02, ROUTE_FLAT)
    assert b.cp_w == pytest.approx(b.base_cp_w * (1.0 - 0.045), rel=1e-3)


def test_tactics_only_change_the_requested_power():
    """Même physique et même réserve : le pas d'un bot en attaque est celui d'un bot à puissance constante qui
    demande la même puissance, et la réserve suit `wbal_step` (pas de recharge hors modèle)."""
    from openride_core.rogue.wbal import wbal_step

    b = ProfileBot("climber", bot_id="b0")
    b.segments = CLIMB
    bt.start_race([b], 4, "classic")
    twin = ConstantPowerBot(100.0, params=b.params)
    twin.physics.s, twin.physics.v = b.s, b.v
    for _ in range(20000):
        w0 = b.wbal
        b.step(0.05, CLIMB_ROUTE)
        twin.power_w = b.power_w
        twin.step(0.05, CLIMB_ROUTE)
        assert b.s == twin.s
        expect = wbal_step(w0, b.power_w, 0.0, 0.05, cp_w=b.cp_w, w_prime_j=b.w_prime_j)
        assert b.wbal.w_bal_j == pytest.approx(expect.w_bal_j)
    assert b.tactics.attacks == 1


# --- critères du cahier --------------------------------------------------------------------------------

def test_step_cost_under_a_tenth_of_a_millisecond():
    bots = [ProfileBot(p, bot_id=f"b{i}") for i, p in enumerate(["climber", "rouleur", "sprinter", "diesel",
                                                                     "rouleur"])]
    rider = Rider(lambda t: 250.0)
    race(bots, CLIMB_ROUTE, 60.0, dt=0.02, rider=rider, segments=CLIMB)   # en route, groupe formé
    field = bt.Field()
    n = 2000
    t0 = time.perf_counter()
    for _ in range(n):
        bt.update_field(field, bots, (rider.s, rider.v), 0.02, lambda s: CLIMB_ROUTE.sample(s).grade_pct,
                        CLIMB_ROUTE.length_m)
        for b in bots:
            b.step(0.02, CLIMB_ROUTE)
    per_bot_ms = 1000.0 * (time.perf_counter() - t0) / (n * len(bots))
    assert per_bot_ms < 0.1, per_bot_ms


def test_draft_between_bots_and_none_behind_a_ghost():
    lead, back = ConstantPowerBot(200.0, bot_id="a", s=1.7 + 1.5), ConstantPowerBot(200.0, bot_id="b")
    alone = ConstantPowerBot(200.0, bot_id="c")
    for _ in range(600):   # 30 s, le bot de derrière gardé à 1,5 m de la roue
        draft.update_bots([lead, back], None, 0.05)
        for x in (lead, back, alone):
            x.step(0.05, ROUTE_FLAT)
        back.physics.s = lead.s - 1.7 - 1.5
    assert back.draft > 0.2 and back.v > alone.v + 0.3
    assert back.draft == pytest.approx(draft.draft_for(back.s, [lead])[0], abs=0.02)   # courbe de draft.py

    class Ghost:
        kind, id, s, v, lane = "ghost", "ghost", 3.2, 10.0, None
    solo = ConstantPowerBot(200.0, bot_id="d")
    for _ in range(200):
        draft.update_bots([Ghost(), solo], None, 0.05)
    assert solo.draft == 0.0


def test_three_rouleurs_take_turns_on_10_km_of_flat():
    bots = [ProfileBot("rouleur", bot_id=f"r{i}") for i in range(3)]
    low_reserve_relays = []

    def check(t, field):
        for b in bots:
            if b.tactics.role == "relay" and b.wbal_pct < bt.RELAY_MIN_RESERVE_PCT:
                low_reserve_relays.append(b.id)

    route = FakeRoute(10000.0)
    changes = head_changes(bots, route, 1100.0, seed=3)
    race([ProfileBot("rouleur", bot_id=f"r{i}") for i in range(3)], route, 200.0, on_step=check)
    assert changes >= 8, changes
    assert not low_reserve_relays


def test_no_relay_in_a_climb_nor_by_a_sprinter_or_an_empty_bot():
    bots = [ProfileBot("rouleur", bot_id=f"r{i}") for i in range(3)]
    relays_on_climb = []

    def check(t, field):
        for b in bots:
            if b.tactics.role in ("relay", "drop", "take") and b.s > 520.0:
                relays_on_climb.append((t, b.id, b.tactics.role))

    race(bots, FakeRoute(3000.0, lambda s: 6.0 if s >= 500.0 else 0.0), 400.0, seed=2, on_step=check)
    assert not relays_on_climb

    sprinter, rouleur = ProfileBot("sprinter", bot_id="s"), ProfileBot("rouleur", bot_id="r")
    bt.start_race([sprinter, rouleur], 1, "classic")
    assert not bt._eligible(sprinter)
    rouleur.wbal = replace(rouleur.wbal, w_bal_j=0.2 * rouleur.w_prime_j)
    assert not bt._eligible(rouleur)
    rouleur.wbal = replace(rouleur.wbal, w_bal_j=rouleur.w_prime_j)
    assert bt._eligible(rouleur)


def test_climber_attacks_once_at_most_and_the_diesel_never():
    attacks = {"climber": 0, "diesel": 0}
    for seed in range(1, 11):
        bots = [ProfileBot(p, bot_id=f"b{i}") for i, p in enumerate(["climber", "diesel"])]
        started = []

        def check(t, field):
            for b in bots:
                if b.tactics.attacks > sum(1 for x in started if x[0] == b.id):
                    started.append((b.id, b.wbal_pct))

        race(bots, CLIMB_ROUTE, 1300.0, seed=seed, segments=CLIMB, on_step=check)
        climber, diesel = bots
        assert climber.tactics.attacks <= 1 and diesel.tactics.attacks == 0
        # la réserve relevée au pas de l'attaque (après un pas à 1,15–1,30 × CP) dépassait 50 % au départ
        assert all(w > bt.ATTACK_MIN_RESERVE_PCT - 1.0 for _, w in started)
        attacks["climber"] += climber.tactics.attacks
    assert attacks["climber"] >= 5


def test_a_rider_attack_is_followed_on_20_draws():
    followed = 0
    for seed in range(1, 21):
        bots = [ProfileBot(p, bot_id=f"b{i}") for i, p in enumerate(["climber", "diesel", "rouleur"])]
        rider = Rider(lambda t: 360.0 if 400.0 <= t < 440.0 else 235.0)
        seen = set()

        def check(t, field):
            for b in bots:
                if b.tactics.respond_to == bt.RIDER_ID:
                    assert b.wbal_pct > bt.RESPONSE_STOP_RESERVE_PCT
                    seen.add(b.id)

        race(bots, CLIMB_ROUTE, 700.0, rider=rider, seed=seed, segments=CLIMB, on_step=check)
        followed += bool(seen)
    assert followed >= 1


def test_same_seed_same_race_other_seed_other_race():
    def positions(seed):
        bots = [ProfileBot(p, bot_id=f"b{i}") for i, p in enumerate(["climber", "rouleur", "diesel"])]
        route = FakeRoute(60000.0, lambda s: 5.0 if 10000.0 <= s < 14000.0 else 0.0)
        race(bots, route, 3600.0, dt=0.1, seed=seed, segments=(seg("climb", 10000.0, 14000.0),))
        return [round(b.s) for b in bots]

    a = positions(11)
    assert positions(11) == a
    assert positions(12) != a


def test_calibration_holds_within_two_percent_on_average(monkeypatch):
    from openride_core.tools import bots_race as br

    monkeypatch.setitem(br.SYNTHETIC, "col", (2000.0, lambda s: 0.0 if s < 700.0 else 6.0))
    monkeypatch.setattr(br, "TACTICS_MODE", "classic")   # avec la forme du jour
    gaps = []
    for seed in range(1, 4):
        out = br.race("col", 85.0, ["climber", "rouleur", "diesel"], seed=seed)
        gaps += [r["gap_pct"] for r in out["bots"]]
    assert abs(sum(gaps) / len(gaps)) <= 2.0, gaps
