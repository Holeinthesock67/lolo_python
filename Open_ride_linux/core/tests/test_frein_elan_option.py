"""Frein d'élan en option du menu (#618 repris, décision du user du 1er novembre 2026).

Le frein d'élan (pente majorée en SIM quand le volant garde l'élan d'une relance, voir
`ftms_driver.MOMENTUM_*`) est une option de « Réglages › Séance », coupée par défaut, avec une durée de
3 à 8 s et une pente de 3 à 6 %, réglées par profil (`config.PROFILE_KEYS`). La séance pose ces
réglages sur le pilote du trainer (`CoreSession._feed_momentum`), ce qui suit un changement de profil
ou de réglage sans relancer.
"""

import pytest

from openride_core import config, profiles, settings
from openride_core.config import BikeConfig, Config, ConfigError, TrainerConfig
from openride_core.ftms_driver import FtmsDriver

from test_drivers_session import make_session
from test_ftms_trace import _drive

KEYS = ("trainer.momentum_brake", "trainer.momentum_brake_s", "trainer.momentum_brake_pct")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OPENRIDE_HOME", tmp_path / "OpenRide")
    profiles.activate(None)
    yield tmp_path / "OpenRide"
    profiles.activate(None)


def test_brake_is_off_by_default():
    t = Config().trainer
    assert (t.momentum_brake, t.momentum_brake_pct, t.momentum_brake_s) == (False, 6.0, 8.0)
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: 100.0)
    now = [100.0]
    drv._clock = lambda: now[0]
    drv.set_sim_grade(0.5)
    _drive(drv, now, [(0.0, 600, 95), (1.0, 150, 90)])
    assert drv.momentum_brakes == 0 and drv._momentum_boost() == 0.0


def test_menu_offers_the_three_settings_in_the_ride_group():
    items = {it["key"]: it for it in settings.current(Config())}
    assert items["trainer.momentum_brake"] == {
        "key": "trainer.momentum_brake", "label": "Frein d'élan", "group": "ride", "value": "off",
        "applies": "next_session", "type": "choice", "choices": ["on", "off"]}
    dur, pct = items["trainer.momentum_brake_s"], items["trainer.momentum_brake_pct"]
    assert (dur["min"], dur["max"], dur["step"], dur["unit"], dur["value"]) == (3, 8, 1, "s", 8)
    assert (pct["min"], pct["max"], pct["step"], pct["unit"], pct["value"]) == (3, 6, 1, "%", 6)
    assert all(settings.get(k).scope == "profil" for k in KEYS)


@pytest.mark.parametrize("key, value", [
    ("trainer.momentum_brake_s", 2), ("trainer.momentum_brake_s", 9),
    ("trainer.momentum_brake_pct", 2), ("trainer.momentum_brake_pct", 7),
])
def test_out_of_range_values_are_refused(key, value):
    with pytest.raises(settings.SettingError):
        settings.check(Config(), key, value)
    section, name = key.split(".")
    with pytest.raises(ConfigError):
        config.from_dict({section: {name: float(value)}})


def test_step_stays_within_the_range():
    cfg = Config()
    assert settings.step(cfg, "trainer.momentum_brake_s", 8, +1) == 8
    assert settings.step(cfg, "trainer.momentum_brake_s", 3, -1) == 3
    assert settings.step(cfg, "trainer.momentum_brake_pct", 6, -1) == 5


def _player(profile_id: str) -> profiles.ProfileContext:
    ctx = profiles.ProfileContext.for_id(profile_id)
    ctx.root.mkdir(parents=True, exist_ok=True)
    (ctx.root / profiles.FILE_NAME).write_text(f'[profil]\nid = "{profile_id}"\nnom = "{profile_id}"\n',
                                               encoding="utf-8")
    return profiles.ProfileContext.for_id(profile_id)


def test_brake_settings_follow_the_profile(home):
    machine = home / "config.toml"
    machine.parent.mkdir(parents=True)
    machine.write_text("[render]\nquality = \"low\"\n", encoding="utf-8")
    before = machine.read_text(encoding="utf-8")
    a, b = _player("cycliste-a"), _player("cycliste-b")
    profiles.activate(a)
    cfg = config.load(machine)
    settings.apply(cfg, {"trainer.momentum_brake": "on", "trainer.momentum_brake_s": 5,
                         "trainer.momentum_brake_pct": 4}, machine)
    assert machine.read_text(encoding="utf-8") == before   # rien pour la machine
    t = config.load(machine).trainer
    assert (t.momentum_brake, t.momentum_brake_s, t.momentum_brake_pct) == (True, 5.0, 4.0)
    profiles.activate(b)
    t = config.load(machine).trainer
    assert (t.momentum_brake, t.momentum_brake_s, t.momentum_brake_pct) == (False, 8.0, 6.0)


def test_session_feeds_the_driver_once_per_change(tmp_path, monkeypatch):
    s = make_session(tmp_path, monkeypatch, base_port=5790)
    calls = []
    s.driver.set_momentum_brake = lambda *a: calls.append(a)
    s._feed_momentum()
    s._feed_momentum()
    assert calls == [(False, 6.0, 8.0)]
    settings.apply(s.cfg, {"trainer.momentum_brake": "on", "trainer.momentum_brake_s": 4}, tmp_path / "config.toml")
    s._feed_momentum()
    assert calls[-1] == (True, 6.0, 4.0) and len(calls) == 2



def test_session_without_brake_setter_is_fine(tmp_path, monkeypatch):
    s = make_session(tmp_path, monkeypatch, base_port=5794)
    s._feed_momentum()   # MockDriver : pas de frein d'élan, rien à poser
    assert s._momentum_fed is None



def test_turning_the_option_off_releases_a_running_brake():
    now = [100.0]
    on = TrainerConfig(momentum_brake=True, momentum_brake_pct=6.0, momentum_brake_s=8.0)
    drv = FtmsDriver(on, BikeConfig(), clock=lambda: now[0])
    drv.set_sim_grade(0.5)
    _drive(drv, now, [(0.0, 600, 95), (1.0, 150, 90)])
    assert drv.momentum_brakes == 1 and drv._momentum_boost() == 6.0
    drv._immediate = False
    drv.set_momentum_brake(False, 6.0, 8.0)
    assert drv._momentum_boost() == 0.0 and drv._immediate


def test_driver_uses_the_fed_values():
    now = [100.0]
    drv = FtmsDriver(TrainerConfig(), BikeConfig(), clock=lambda: now[0])
    drv.set_momentum_brake(True, 4.0, 3.0)
    drv.set_sim_grade(0.5)
    _drive(drv, now, [(0.0, 600, 95), (1.0, 150, 90)])
    assert drv._momentum_boost() == 4.0
    _drive(drv, now, [(2.0, 150, 90), (3.0, 150, 90), (4.1, 150, 90)])
    assert drv._momentum_at is None   # tenu 3 s au plus
