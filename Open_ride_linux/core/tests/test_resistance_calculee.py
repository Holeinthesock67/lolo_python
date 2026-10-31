"""Résistance calculée par le core (lots RC2-RC3, étude du 31 octobre) : la pente SIM part en niveau de
résistance FTMS 0x04, avec la force de la route à la vitesse du volant et la masse du profil."""

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
    drv, now = _driver(resistance_n_per_pct=2.0)
    drv.road_mass_kg = 80.0
    drv._on_ibd(None, _ibd(30.0, 85, 200))
    drv.set_sim_grade(3.0)
    level = round(drv.road_force_n(3.0, 30 / 3.6) / 2.0)
    assert _flush(drv) == [ftms.cmd_set_target_resistance(level)]
    assert drv._last_sent == ("resistance", level)


def test_downhill_sends_the_lowest_level():
    drv, _ = _driver()
    drv._on_ibd(None, _ibd(40.0, 85, 50))
    drv.set_sim_grade(-6.0)
    assert _flush(drv) == [ftms.cmd_set_target_resistance(0.0)]


def test_default_control_stays_sim():
    """Le SIM reste le pilotage par défaut jusqu'aux essais réels (31 octobre)."""
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.supports_resistance = True
    drv.set_sim_grade(3.0)
    sent = _flush(drv)
    assert TrainerConfig().control == "sim" and sent and sent[0][0] == ftms.OP_SET_SIM_PARAMS


def test_falls_back_to_sim_when_resistance_is_not_announced(caplog):
    drv, _ = _driver()
    drv.supports_resistance = False
    drv.set_sim_grade(3.0)
    with caplog.at_level(logging.WARNING, logger="ftms_driver"):
        sent = _flush(drv)
    assert sent and sent[0][0] == ftms.OP_SET_SIM_PARAMS
    assert any("pilotage SIM gardé" in r.getMessage() for r in caplog.records)


def test_force_per_pct_learns_the_real_brake_on_a_steady_flywheel():
    """Frein réel à 1 N par % (le départ dit 2) : la correction rejoint 1 en une vingtaine de secondes."""
    drv, now = _driver(resistance_n_per_pct=2.0)
    drv._last_sent = ("resistance", 40.0)
    for i in range(120):   # 4 trames par seconde, 30 s, volant à 30 km/h
        now[0] = 100.0 + i * 0.25
        drv._on_ibd(None, _ibd(30.0, 85, round(1.0 * 40.0 * 30 / 3.6)))
    assert drv.n_per_pct == pytest.approx(1.0, abs=0.05)


def test_force_per_pct_frozen_while_the_flywheel_accelerates():
    drv, now = _driver(resistance_n_per_pct=2.0)
    drv._last_sent = ("resistance", 40.0)
    for i in range(20):   # sprint : +2 km/h par trame de 0,25 s (> 0,4 m/s²)
        now[0] = 100.0 + i * 0.25
        drv._on_ibd(None, _ibd(20.0 + 2 * i, 100, 900))
    assert drv.n_per_pct == 2.0


def test_force_per_pct_is_bounded():
    drv, now = _driver(resistance_n_per_pct=2.0)
    drv._last_sent = ("resistance", 10.0)
    for i in range(400):
        now[0] = 100.0 + i * 0.25
        drv._on_ibd(None, _ibd(30.0, 85, 2000))   # force mesurée absurde
    assert drv.n_per_pct == pytest.approx(10.0)   # 5 × la valeur de départ


def test_config_choices_and_bounds():
    assert config.from_dict({"trainer": {"control": "resistance", "resistance_n_per_pct": 1.5}}).trainer.control == "resistance"
    for bad in ({"control": "erg"}, {"resistance_n_per_pct": 0.0}):
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
