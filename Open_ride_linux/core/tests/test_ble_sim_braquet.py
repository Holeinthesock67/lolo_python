"""Trainer simulé à braquet réel et décrochages du frein (lot X46)."""

import asyncio
import struct

import pytest

from openride_core import physics
from openride_core.sim_rider import SimRider
from openride_core.sim_scenarios import SimScenarioError, build_world, load_scenario, validate
from openride_core.tools import decrochages
from openride_core.tools.trainer_steps import Gearing, scenario_gearing

DT = 0.25


def ride(spec, seconds, grade=0.0):
    """Déroule le scénario `spec` image par image (horloge simulée) ; renvoie les relevés du trainer."""
    async def go():
        world = build_world(spec, click=False, hr=False)
        tr = world.trainer
        tr.mode, tr.grade_pct = "sim", grade
        clock = {"t": 0.0}
        world.now = lambda: clock["t"]
        events = sorted(spec.get("events") or [], key=lambda e: e["t"])
        out, t = [], 0.0
        while t < seconds:
            t += DT
            clock["t"] = t
            while events and events[0]["t"] <= t:
                await world.apply(events.pop(0))
            _, speed, cadence, power = struct.unpack("<HHHh", tr.frame(t, DT))
            out.append((t, power, cadence / 2, speed / 100))
        return out
    return asyncio.run(go())


def test_gear_speed_and_cadence_are_reciprocal():
    v = physics.gear_speed_mps(85, 50, 14)
    assert v * 3.6 == pytest.approx(38.3, abs=0.1)
    assert physics.gear_cadence_rpm(v, 50, 14) == pytest.approx(85)
    assert Gearing(50, 14).speed_mps(85) == pytest.approx(v)


def test_gearing_must_be_complete():
    with pytest.raises(ValueError, match="braquet réel"):
        SimRider(chainring=50)
    with pytest.raises(SimScenarioError, match="braquet réel"):
        validate({"rider": {"sprocket": 14}})
    with pytest.raises(SimScenarioError, match="braquet réel"):
        validate({"rider": {"chainring": 50, "sprocket": 0}})
    assert SimRider(chainring=50, sprocket=14).gear_speed_mps(85) == pytest.approx(physics.gear_speed_mps(85, 50, 14))
    assert SimRider().gear_speed_mps(85) is None


def test_single_sprocket_holds_the_flywheel_at_the_gear_speed():
    trace = ride(load_scenario("pignon_unique"), 30.0)
    t, power, cadence, speed = trace[-1]
    assert speed == pytest.approx(38.3, abs=0.3)
    assert cadence == pytest.approx(85, abs=2)
    assert power > 200   # grand plateau : l'effort de la route pèse déjà sur le plat


def test_cadence_follows_the_flywheel_when_the_rider_is_beaten():
    spec = load_scenario("pignon_unique")
    trace = ride(spec, 40.0, grade=10.0)   # bien au-delà des 600 W du cycliste à ce braquet
    t, power, cadence, speed = trace[-1]
    assert power == pytest.approx(600, abs=5)
    assert cadence < 70 and speed < 32


def test_brake_loss_is_classified_as_a_trainer_dropout():
    spec = load_scenario("decrochage_trainer")
    trace = ride(spec, 200.0)
    samples = [decrochages.Sample(t, p, c) for t, p, c, _ in trace]
    drops = decrochages.detect_drops(samples)
    assert [round(d.t) for d in drops] == [33, 93, 160]
    assert all(decrochages.classify(d) == "trainer" for d in drops)
    during = [s for s in trace if 36 <= s[0] < 41]
    assert max(p for _, p, _, _ in during) < 20                          # puissance annoncée vers 0 W
    assert min(c for _, _, c, _ in during) > 90                          # cadence de la relance gardée
    assert during[-1][3] < trace[int(32 / DT)][3] * 0.7                  # vitesse du volant qui baisse
    assert trace[int(50 / DT)][1] > 200                                  # puissance revenue après 8 s


def test_trainer_steps_takes_the_gearing_of_the_scenario():
    assert scenario_gearing(load_scenario("pignon_unique")) == Gearing(50, 14)
    assert scenario_gearing(load_scenario("nominal")) is None
