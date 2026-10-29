"""Trainer simulé réaliste (lot X6) : frein à retard pur, serrage et relâchement, volant, calibration."""

import asyncio
import math
import struct

import pytest

from openride_core import ble_sim
from openride_core.ble_sim import REALISTE, SimTrainer, SimWorld, TrainerResponse, load_calibration
from openride_core.sim_scenarios import SimScenarioError, build_world, load_scenario

DT = 0.25          # Indoor Bike Data à 4 Hz
V_RIDE = 9.0       # m/s tenus par le cycliste


def model(**kw):
    params = {k: v for k, v in REALISTE.items() if k != "notify_jitter_s"}
    params.update(kw)
    return TrainerResponse(**params)


def run_step(m, before, after, hold_before=30.0, hold_after=40.0, cap=5000.0):
    """Consigne `before` pendant `hold_before` s, puis `after` ; renvoie [(t depuis la marche, puissance)],
    en commençant par (0, puissance juste avant la marche)."""
    p = m.power_w
    for _ in range(int(hold_before / DT)):
        p = m.step(DT, before, V_RIDE, cap)
    out = [(0.0, p)]
    for i in range(int(hold_after / DT)):
        out.append(((i + 1) * DT, m.step(DT, after, V_RIDE, cap)))
    return out


def t_frac(trace, frac):
    """Temps où la puissance a fait `frac` du changement (milieu de l'intervalle de 0,25 s qui le franchit)."""
    start, end = trace[0][1], trace[-1][1]
    level = start + frac * (end - start)
    sign = 1 if end > start else -1
    return next(t for t, p in trace if sign * (p - level) >= 0) - DT / 2


def erg(w):
    return ("erg", w, 0.0, None, None, 0.0)


def sim(grade):
    return ("sim", None, grade, None, None, 0.0)


@pytest.mark.parametrize("before, after, tau", [(erg(150.0), erg(250.0), "up"), (erg(250.0), erg(150.0), "down")])
def test_erg_step_t63_matches_delay_plus_tau(before, after, tau):
    m = model()
    trace = run_step(m, before, after)
    want = m.delay_s + (m.tau_up_s if tau == "up" else m.tau_down_s)
    assert t_frac(trace, 0.63) == pytest.approx(want, rel=0.10)
    # Retard pur : rien ne bouge avant brake_delay_s.
    assert all(abs(p - trace[0][1]) < 3.0 for t, p in trace if t < m.delay_s - DT)
    assert trace[-1][1] == pytest.approx(after[1], abs=2.0)


def test_release_is_slower_than_clamp_and_90_percent_near_12_s():
    m = model()
    up = run_step(m, sim(0.0), sim(7.0))
    down = run_step(m, sim(7.0), sim(0.0), hold_before=0.0)
    assert t_frac(down, 0.63) > 2 * t_frac(up, 0.63)
    assert t_frac(down, 0.90) == pytest.approx(12.0, abs=1.5)   # relâchement mesuré à l'essai du 25 octobre


def test_sim_power_follows_the_road_force_at_held_speed():
    m = model()
    trace = run_step(m, sim(0.0), sim(7.0), hold_after=60.0)
    p = ble_sim.SPEED_PHYSICS
    expected = (p.mass_kg * 9.80665 * (0.0697 + p.crr * 0.9976) + 0.5 * 1.225 * p.cda_m2 * V_RIDE ** 2) * V_RIDE
    assert trace[-1][1] == pytest.approx(expected, rel=0.02)
    assert m.v == pytest.approx(V_RIDE, abs=0.05)


def test_rider_power_capped_so_the_flywheel_slows_down():
    m = model()
    run_step(m, sim(0.0), sim(7.0), hold_after=60.0, cap=300.0)
    assert m.power_w == pytest.approx(300.0, abs=2.0) and m.v < 0.6 * V_RIDE


def test_heavier_flywheel_smooths_a_speed_change():
    light, heavy = model(flywheel_kg_m2=0.2), model(flywheel_kg_m2=2.0)
    for m in (light, heavy):
        run_step(m, sim(0.0), sim(10.0), hold_after=3.0, cap=250.0)
    assert heavy.v > light.v   # même effort plafonné : le volant lourd ralentit moins vite


def test_calibration_from_trainer_steps_csv(tmp_path):
    head = "index,mode,value,from_value,write_ms,ack_ms,baseline_w,final_w,delta_w,t10_s,t63_s,t90_s,settle_s,overshoot_pct,cadence_rpm,note\n"
    rows = ["1,sim,0,,,,,,,,,,,,85,palier de départ",
            "2,sim,7,0,10,40,150,400,250,1.0,3.0,5.0,6,2,85,",       # τ = 2/0,895 = 2,23 ; retard 0,77
            "3,sim,0,7,10,40,400,150,-250,1.5,7.0,13.0,14,0,85,"]    # τ = 6,15 ; retard 0,85
    path = tmp_path / "steps.csv"
    path.write_text(head + "\n".join(rows) + "\n")
    cal = load_calibration(path)
    assert cal["brake_tau_up_s"] == pytest.approx(2.0 / 0.895, abs=0.01)
    assert cal["brake_tau_down_s"] == pytest.approx(5.5 / 0.895, abs=0.01)
    assert cal["brake_delay_s"] == pytest.approx((3.0 - 2.0 / 0.895 + 7.0 - 5.5 / 0.895) / 2, abs=0.01)
    spec = load_scenario("realiste")
    spec["trainer"]["calibration"] = str(path)
    world = build_world(spec, click=False, hr=False)
    assert world.trainer.model.tau_down_s == cal["brake_tau_down_s"]
    spec["trainer"]["calibration"] = str(tmp_path / "absent.csv")
    with pytest.raises(SimScenarioError, match="calibration"):
        build_world(spec)


def test_scenario_keys_validated():
    spec = load_scenario("realiste")
    assert build_world(spec, click=False, hr=False).trainer.model is not None
    assert build_world(load_scenario("nominal"), click=False, hr=False).trainer.model is None
    spec["trainer"]["response"] = "molle"
    with pytest.raises(SimScenarioError, match="response"):
        build_world(spec)
    spec["trainer"].update({"response": "realiste", "brake_tau_down_s": -1})
    with pytest.raises(SimScenarioError, match="brake_tau_down_s"):
        build_world(spec)


def test_sim_frame_crr_cw_and_wind_are_read():
    async def go():
        world = SimWorld()
        tr = SimTrainer(world, response="realiste")
        tr.control = tr.indications = True
        frame = bytes([0x11]) + struct.pack("<hhBB", 2500, 500, 40, 51)   # vent 2,5 m/s, 5 %, Crr 0,004, Cw 0,51
        tr._execute(frame[0], frame)
        return tr
    tr = asyncio.run(go())
    assert (tr.wind_mps, tr.grade_pct, tr.crr, tr.cw) == (2.5, 5.0, 0.004, 0.51)


def test_instant_response_is_unchanged():
    async def go():
        world = SimWorld()
        tr = SimTrainer(world)
        tr.mode, tr.target_w = "erg", 250.0
        tr.power_w = 150.0
        return tr, tr._step_power(10.0, 1.5, tr.rider.step(10.0, 1.5, 0.0, 250.0))
    tr, speed = asyncio.run(go())
    assert tr.model is None and tr.notify_jitter_s == 0.0
    goal = 250.0 + 2.0 * math.sin(15.0)
    assert tr.power_w == pytest.approx(150.0 + (goal - 150.0) * (1 - math.exp(-1.0)))
