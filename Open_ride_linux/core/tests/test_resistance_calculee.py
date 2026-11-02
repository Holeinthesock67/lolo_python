"""Résistance calculée par le core (lots RC2-RC3, étude du 31 octobre) : la pente SIM part en niveau de
résistance FTMS 0x04, avec la force de la route à la vitesse du volant et la masse du profil ; le frein
du trainer suit F = k × niveau × v (étalonnage 7rc1 du 1er novembre)."""

import asyncio
import logging
import math
import struct

import pytest

from openride_core import config, ftms
from openride_core.config import BikeConfig, TrainerConfig
from openride_core.ftms_driver import FtmsDriver
from openride_core.physics import G, RHO0


def _ibd(speed_kmh: float, cadence_rpm: float, power_w: int) -> bytearray:
    flags = 0x0004 | 0x0040
    return bytearray(struct.pack("<HHHh", flags, round(speed_kmh * 100), round(cadence_rpm * 2), power_w))


def _driver(**trainer) -> tuple[FtmsDriver, list]:
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(control="resistance", **trainer), BikeConfig(), clock=lambda: now[0])
    drv.supports_resistance = True
    drv.resistance_range = (0.0, 100.0, 1.0)
    return drv, now


def _flush(drv) -> list[bytes]:
    sent = []

    class _Cp:
        async def write(self, payload, **_kw):
            sent.append(bytes(payload))

    async def _call(cp, build):
        await cp.write(build())
    drv._call_retrying = _call
    drv._last_sent, drv._last_sent_at = ("resistance", -1.0), -10.0   # contrôle déjà pris
    asyncio.run(drv._flush_command(_Cp()))
    return sent


def test_road_force_is_the_sim_formula_with_the_profile_mass():
    drv, _ = _driver()
    drv.road_mass_kg = 80.0
    v = 30 / 3.6
    expected = 80.0 * G * (math.sin(math.atan(0.05)) + 0.004 * math.cos(math.atan(0.05))) + 0.5 * RHO0 * 0.32 * v * v
    assert drv.road_force_n(5.0, v) == pytest.approx(expected)
    assert drv.road_force_n(-8.0, v) < 0   # descente : la gravité entraîne, niveau 0 envoyé


def test_sim_grade_is_sent_as_a_resistance_level():
    """Frein de l'étalonnage 7rc1 : F = k × niveau × v (km/h), donc niveau = F / (k × v)."""
    drv, now = _driver(resistance_n_per_pct_kmh=0.036)
    drv.road_mass_kg = 80.0
    drv._on_ibd(None, _ibd(30.0, 85, 200))
    drv.set_sim_grade(3.0)
    level = round(drv.road_force_n(3.0, 30 / 3.6) / (0.036 * 30.0))
    assert _flush(drv) == [ftms.cmd_set_target_resistance(level)]
    assert drv._last_sent == ("resistance", level)


def test_level_falls_as_the_flywheel_speeds_up_on_the_same_slope():
    """Le frein monte avec la vitesse du volant : à force égale, 40 km/h demande moins de niveau que 25 km/h."""
    drv, _ = _driver(resistance_n_per_pct_kmh=0.036)
    drv._wind_mps, drv._cw = 0.0, 0.0   # force de pente seule, la même aux deux vitesses
    drv._on_ibd(None, _ibd(25.0, 85, 200))
    slow = drv._road_level(4.0)
    drv._on_ibd(None, _ibd(40.0, 110, 400))
    fast = drv._road_level(4.0)
    assert fast == pytest.approx(slow * 25.0 / 40.0, abs=1.0)


def test_level_uses_a_speed_floor_when_starting():
    drv, _ = _driver(resistance_n_per_pct_kmh=0.036)
    drv._on_ibd(None, _ibd(2.0, 20, 50))
    force = drv.road_force_n(3.0, 2.0 / 3.6)
    assert drv._road_level(3.0) == pytest.approx(round(force / (0.036 * 10.0)), abs=1.0)


def test_downhill_sends_the_lowest_level():
    drv, _ = _driver()
    drv._on_ibd(None, _ibd(40.0, 85, 50))
    drv.set_sim_grade(-6.0)
    assert _flush(drv) == [ftms.cmd_set_target_resistance(0.0)]


def test_default_control_is_the_computed_resistance():
    """Choix du propriétaire (1er novembre, après les essais 7rc2-7rc3) : résistance calculée sans inertie."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.supports_resistance = True
    drv._on_ibd(None, _ibd(30.0, 85, 200))
    drv.set_sim_grade(3.0)
    sent = _flush(drv)
    assert TrainerConfig().control == "resistance" and TrainerConfig().resistance_inertia_pct == 0.0
    assert sent and sent[0][0] == ftms.OP_SET_TARGET_RESISTANCE


def test_sim_control_still_sends_the_grade():
    """« Pilotage du trainer » sur SIM : la pente part en 0x11, comme avant."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(control="sim"), BikeConfig(), clock=lambda: now[0])
    drv.supports_resistance = True
    drv.set_sim_grade(3.0)
    sent = _flush(drv)
    assert sent and sent[0][0] == ftms.OP_SET_SIM_PARAMS


def test_pilotage_is_a_menu_setting():
    from openride_core import settings
    item = next(it for it in settings.current(config.Config()) if it["key"] == "trainer.control")
    assert item["label"] == "Pilotage du trainer" and item["group"] == "ride"
    assert item["value"] == "resistance" and item["choices"] == ["sim", "resistance"]
    assert settings.get("trainer.control").scope == "machine"


def test_falls_back_to_sim_when_resistance_is_not_announced(caplog):
    drv, _ = _driver()
    drv.supports_resistance = False
    drv.set_sim_grade(3.0)
    with caplog.at_level(logging.WARNING, logger="ftms_driver"):
        sent = _flush(drv)
    assert sent and sent[0][0] == ftms.OP_SET_SIM_PARAMS
    assert any("pilotage SIM gardé" in r.getMessage() for r in caplog.records)


def test_brake_k_learns_the_real_brake_on_a_steady_flywheel():
    """Frein réel à k = 0,030 (le départ dit 0,036) : la correction le rejoint en une vingtaine de secondes."""
    drv, now = _driver(resistance_n_per_pct_kmh=0.036)
    drv._last_sent = ("resistance", 40.0)
    for i in range(120):   # 4 trames par seconde, 30 s, volant à 30 km/h
        now[0] = 100.0 + i * 0.25
        drv._on_ibd(None, _ibd(30.0, 85, round(0.030 * 40.0 * 30.0 * 30 / 3.6)))
    assert drv.k_road == pytest.approx(0.030, abs=0.001)


def test_brake_k_frozen_while_the_flywheel_accelerates():
    drv, now = _driver(resistance_n_per_pct_kmh=0.036)
    drv._last_sent = ("resistance", 40.0)
    for i in range(20):   # sprint : +2 km/h par trame de 0,25 s (> 0,4 m/s²)
        now[0] = 100.0 + i * 0.25
        drv._on_ibd(None, _ibd(20.0 + 2 * i, 100, 900))
    assert drv.k_road == 0.036


def test_brake_k_is_bounded():
    drv, now = _driver(resistance_n_per_pct_kmh=0.036)
    drv._last_sent = ("resistance", 10.0)
    for i in range(400):
        now[0] = 100.0 + i * 0.25
        drv._on_ibd(None, _ibd(30.0, 85, 2000))   # force mesurée absurde
    assert drv.k_road == pytest.approx(0.18)   # 5 × la valeur de départ


def test_config_choices_and_bounds():
    assert config.from_dict({"trainer": {"control": "resistance", "resistance_n_per_pct_kmh": 0.04}}).trainer.control == "resistance"
    assert config.Config().trainer.resistance_n_per_pct_kmh == 0.036   # étalonnage 7rc1
    for bad in ({"control": "erg"}, {"resistance_n_per_pct_kmh": 0.0}, {"resistance_n_per_pct_kmh": 2.0}):
        with pytest.raises(config.ConfigError):
            config.from_dict({"trainer": bad})


def test_bench_on_the_realistic_simulated_trainer_sends_levels_only():
    """Bout en bout sur le trainer simulé réaliste : aucune commande 0x11, des niveaux 0x04 qui suivent la pente."""
    from openride_core.sim_scenarios import build_world, load_scenario
    from openride_core.tools import trainer_steps as ts
    world = build_world(load_scenario("realiste"), "realiste", click=False, hr=False)
    cfg = config.Config()
    cfg.trainer.control = "resistance"
    steps = [ts.Step("sim", 0.0, 4), ts.Step("sim", 6.0, 4)]
    asyncio.run(ts.run_bench(steps, cfg, sim_world=world, lead_in_s=0))
    ops = [c.op for c in world.trainer.commands]
    last_res = max(i for i, op in enumerate(ops) if op == ftms.OP_SET_TARGET_RESISTANCE)
    assert ftms.OP_SET_SIM_PARAMS not in ops[:last_res]   # 0x11 seulement au relâchement final (0 % puis Reset)
    levels = [c.payload for c in world.trainer.commands if c.op == ftms.OP_SET_TARGET_RESISTANCE]
    first, last = (struct.unpack_from("<h", p, 1)[0] for p in (levels[0], levels[-1]))
    assert last > first   # 6 % : frein plus fort qu'à plat


def test_power_control_is_no_longer_offered():
    """Le mode « power » des essais 7rc2 est retiré (1er novembre, PWR2 noté 2,5)."""
    with pytest.raises(config.ConfigError):
        config.from_dict({"trainer": {"control": "power"}})


def _accelerate(drv, now, speeds, dt=0.25, power=600, rpm=105):
    for v in speeds:
        now[0] += dt
        drv._on_ibd(None, _ibd(v, rpm, power))


def test_inertia_is_added_while_the_flywheel_accelerates():
    """Sprint : +1 m/s² au volant ; 100 % ajoute m × a à la force de la route, donc un niveau plus haut."""
    drv, now = _driver(resistance_inertia_pct=100.0)
    drv.road_mass_kg = 84.0
    steady, now0 = _driver(resistance_inertia_pct=0.0)
    _accelerate(drv, now, [30.0 + 0.9 * i for i in range(24)])   # 3,6 km/h/s = 1 m/s² pendant 6 s
    _accelerate(steady, now0, [30.0 + 0.9 * i for i in range(24)])
    assert drv._accel_mps2 == pytest.approx(1.0, abs=0.1)
    assert drv.inertia_force_n() == pytest.approx(84.0 * 0.6, abs=8.0)   # part au-dessus du seuil de 0,4 m/s²
    assert steady.inertia_force_n() == 0.0
    assert drv._road_level(0.0) > steady._road_level(0.0) + 15


@pytest.mark.parametrize("pct", [50.0, 100.0])
def test_inertia_dose_is_a_share_of_m_a(pct):
    drv, now = _driver(resistance_inertia_pct=pct)
    drv.road_mass_kg = 80.0
    drv._accel_mps2 = 1.2
    drv._trainer_speed_kmh = 40.0
    assert drv.inertia_target_n() == pytest.approx(pct / 100.0 * 80.0 * (1.2 - 0.4))
    drv._trainer_speed_kmh = 25.0   # entre 20 et 30 km/h : montée progressive
    assert drv.inertia_target_n() == pytest.approx(0.5 * pct / 100.0 * 80.0 * (1.2 - 0.4))
    drv._trainer_speed_kmh = 18.0
    assert drv.inertia_target_n() == 0.0


def test_inertia_force_changes_gradually():
    """7rc3 : plus de saut de niveau d'une trame à l'autre, la force d'inertie varie d'au plus 60 N/s."""
    drv, now = _driver(resistance_inertia_pct=100.0)
    prev, jumps = 0.0, []
    for i in range(24):
        now[0] += 0.25
        drv._on_ibd(None, _ibd(30.0 + 2.0 * i, 110, 900))   # relance brutale : 2,2 m/s²
        jumps.append(drv.inertia_force_n() - prev)
        prev = drv.inertia_force_n()
    assert max(jumps) <= 60.0 * 0.25 + 1e-9 and prev > 50.0


def test_low_speed_wobble_adds_no_inertia():
    """Relevé 7rc3 (chargement du jeu, 12 à 22 km/h, ±2 m/s² d'une trame à l'autre) : aucune inertie."""
    drv, now = _driver(resistance_inertia_pct=100.0)
    for v in [19.9, 15.3, 18.0, 12.0, 21.0, 14.0, 19.0, 4.7, 16.0, 22.0, 13.0, 18.5] * 3:
        now[0] += 1.0
        drv._on_ibd(None, _ibd(v, 60, 120))
    assert drv.inertia_force_n() == 0.0


def test_brake_k_frozen_while_inertia_acts():
    drv, now = _driver(resistance_n_per_pct_kmh=0.036)
    drv._last_sent = ("resistance", 40.0)
    drv._inertia_n = 20.0   # décroît de 15 N par trame : encore active aux trois premières
    for i in range(3):
        now[0] = 100.0 + i * 0.25
        drv._on_ibd(None, _ibd(30.0, 85, 2000))
    assert drv.k_road == 0.036


def test_inertia_is_never_given_back_when_slowing_down():
    """Après le sprint, le volant ralentit : aucune force retirée (pas de trou), seulement la route."""
    drv, now = _driver(resistance_inertia_pct=100.0)
    _accelerate(drv, now, [45.0 - 0.9 * i for i in range(24)], power=150, rpm=80)
    assert drv._accel_mps2 < -0.5
    assert drv.inertia_force_n() == 0.0
    road = max(drv.road_force_n(0.0, drv._trainer_speed_kmh / 3.6), 0.0)
    assert drv._road_level(0.0) == pytest.approx(round(road / (0.036 * drv._trainer_speed_kmh)), abs=1.0)


def test_inertia_ignores_pedal_stroke_ripple():
    """7rc3 : vitesse du volant qui oscille de ±0,5 km/h à chaque trame en roulant stable : aucune inertie."""
    drv, now = _driver(resistance_inertia_pct=100.0)
    forces = []
    for i in range(80):
        now[0] += 0.25
        drv._on_ibd(None, _ibd(32.0 + (0.5 if i % 2 else -0.5), 90, 250))
        forces.append(drv.inertia_force_n())
    assert max(forces[8:]) == 0.0


def test_inertia_config_bounds():
    assert config.Config().trainer.resistance_inertia_pct == 0.0   # coupée par défaut (choix du 1er novembre)
    assert config.from_dict({"trainer": {"resistance_inertia_pct": 50.0}}).trainer.resistance_inertia_pct == 50.0
    for bad in (-1.0, 101.0):
        with pytest.raises(config.ConfigError):
            config.from_dict({"trainer": {"resistance_inertia_pct": bad}})
