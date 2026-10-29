"""Cycliste virtuel du Bluetooth simulé (lot X27) : chaque stratégie, et le défaut inchangé."""

import asyncio
import math

import pytest

from openride_core import sim_scenarios
from openride_core.physics import steady_speed
from openride_core.sim_rider import SPEED_PHYSICS, STRATEGIES, SimRider

DT = 0.25


def ride(rider: SimRider, seconds: float, grade=lambda t: 0.0, erg=None):
    out = []
    for i in range(int(seconds / DT)):
        t = i * DT
        out.append((t, rider.step(t, DT, grade(t), erg(t) if erg else None)))
    return out


def test_default_is_the_rider_before_this_lot():
    r = SimRider()
    for t, g in ((0.0, 0.0), (1.3, 5.0), (7.0, -2.0)):
        assert r.step(t, DT, g).power_w == pytest.approx(180.0 * (1 + 0.04 * g) + 4.0 * math.sin(t * 0.9))
    assert r.step(0.0, DT, 0.0).cadence_rpm == 88.0
    freewheel = SimRider(watts=0)
    assert (freewheel.step(1.0, DT, 0.0).power_w, freewheel.step(1.0, DT, 0.0).cadence_rpm) == (0.0, 88.0)


def test_slope_strategy_follows_the_grade_with_seeded_noise():
    a, b = SimRider("pente", ftp_w=250, pct_ftp=80, seed=7), SimRider("pente", ftp_w=250, pct_ftp=80, seed=7)
    flat, climb = a.step(0, DT, 0.0).power_w, a.step(1, DT, 5.0).power_w
    assert 196 <= flat <= 204 and 254 <= climb <= 266
    assert [b.step(0, DT, 0.0).power_w, b.step(1, DT, 5.0).power_w] == [flat, climb]   # même graine, même séance
    assert SimRider("pente", ftp_w=250, pct_ftp=80).step(0, DT, -20.0).power_w == pytest.approx(80, rel=0.03)


def test_cadence_strategy_presses_the_click_to_stay_in_range():
    r = SimRider("cadence", cadence_rpm=90, cadence_low=80, cadence_high=95)
    grade = [8.0]   # pente reçue : un appui « - » (braquet plus souple) la fait baisser de 1,5 point

    presses = []
    for t, out in ((i * DT, None) for i in range(int(40 / DT))):
        out = r.step(t, DT, grade[0])
        if out.press == "-":
            grade[0] -= 1.5
        elif out.press == "+":
            grade[0] += 1.5
        if out.press:
            presses.append((t, out.press))
    assert presses[0] == (0.0, "-")
    assert all(b - a >= 2.0 for (a, _), (b, _) in zip(presses, presses[1:]))   # un appui toutes les 2 s au plus
    final = r.step(41.0, DT, grade[0]).cadence_rpm
    assert 80 <= final <= 95
    assert r.step(50.0, DT, -4.0).press == "+"   # descente : cadence trop haute, braquet plus dur


def test_ramp_rises_20_w_per_minute_then_stops_at_failure():
    r = SimRider("rampe", ftp_w=250, ramp_start_w=100, ramp_w_per_min=20, ramp_fail_pct_ftp=133)
    assert r.step(60.0, DT, 0.0).power_w == pytest.approx(120.0)
    fail_t = next(t for t, out in ride(r, 1200) if out.cadence_rpm == 0.0)
    assert fail_t == pytest.approx((250 * 1.33 - 100) / 20 * 60, abs=1.0)
    assert r.failed and r.step(2000.0, DT, 0.0) == r.step(2001.0, DT, 0.0)
    erg = SimRider("rampe", ftp_w=250)   # en ERG : la cible du trainer décide de l'échec
    assert erg.step(10.0, DT, 0.0, erg_target_w=300).cadence_rpm > 0
    assert erg.step(11.0, DT, 0.0, erg_target_w=340).cadence_rpm == 0.0


def test_sprints_at_the_requested_times():
    r = SimRider("sprint", ftp_w=250, pct_ftp=70, sprint_at_s=[30.0], sprint_s=10.0)
    powers = {t: out.power_w for t, out in ride(r, 60)}
    assert powers[29.75] < 200 and powers[30.0] > 600 and powers[39.75] > 600 and powers[40.0] < 200


def test_fatigue_power_drops_when_the_reserve_is_empty_then_comes_back():
    r = SimRider("fatigue", ftp_w=250, fatigue_pct_ftp=120, w_prime_j=6000, recover_frac=0.8, resume_pct=30)
    out = ride(r, 600)
    hard = [t for t, o in out if o.power_w > 280]
    easy = [t for t, o in out if o.power_w < 220]
    assert hard[0] == 0.0 and easy, "la réserve vide doit faire baisser la puissance"
    first_drop = easy[0]
    assert first_drop == pytest.approx(6000 / 50, abs=2.0)   # 6 000 J à 50 W au-dessus de la CP
    assert any(t > first_drop for t in hard)                 # réserve rechargée : l'effort reprend


@pytest.mark.parametrize("grade", [0.0, 3.0, 6.0])
def test_speed_strategy_holds_the_target_speed(grade):
    p = SimRider("vitesse", speed_kmh=35).step(0.0, DT, grade).power_w   # sin(0) : sans le bruit
    assert steady_speed(p, grade, SPEED_PHYSICS) * 3.6 == pytest.approx(35.0, abs=0.05)


def test_unknown_strategy_and_bad_scenarios_are_refused():
    with pytest.raises(ValueError, match="inconnue"):
        SimRider("course")
    with pytest.raises(ValueError, match="speed_kmh"):
        SimRider("vitesse")
    for spec, msg in (({"rider": {"strategy": "course"}}, "rider.strategy"),
                      ({"rider": {"vitesse": 3}}, "vitesse"),
                      ({"rider": {"strategy": "sprint", "sprint_at_s": 30}}, "liste de temps"),
                      ({"rider": {"strategy": "pente", "ftp_w": "250"}}, "nombre attendu"),
                      ({"trainer": {"rider_power_w": 180}}, "rider_power_w")):
        with pytest.raises(sim_scenarios.SimScenarioError, match=msg):
            sim_scenarios.validate(spec)
    assert set(STRATEGIES) == {"constante", "pente", "cadence", "rampe", "sprint", "fatigue", "vitesse"}


def test_trainer_presses_the_simulated_click_for_the_cadence_strategy():
    async def scenario():
        spec = {"trainer": {"ibd_hz": 20}, "click": {}, "rider": {"strategy": "cadence", "cadence_rpm": 70}}
        world = sim_scenarios.build_world(spec)
        pressed = []

        async def press(button, duration_s=0.12):
            pressed.append(button)
        world.press = press
        task = asyncio.create_task(world.trainer._data_loop())
        await asyncio.sleep(0.3)
        task.cancel()
        assert pressed == ["-"]
    asyncio.run(scenario())
