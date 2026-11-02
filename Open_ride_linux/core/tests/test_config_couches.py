"""Série MJ, lot MJ4 : configuration à deux couches, `config.toml` (machine) ← `profil.toml` (joueur)."""

import logging
from dataclasses import fields

import pytest

from openride_core import config, config_edit, pairing, profiles, settings
from openride_core.config import Config, ConfigError


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OPENRIDE_HOME", tmp_path / "OpenRide")
    profiles.activate(None)
    yield tmp_path / "OpenRide"
    profiles.activate(None)


def player(profile_id: str, name: str) -> profiles.ProfileContext:
    ctx = profiles.ProfileContext.for_id(profile_id)
    ctx.root.mkdir(parents=True, exist_ok=True)
    (ctx.root / profiles.FILE_NAME).write_text(f'[profil]\nid = "{profile_id}"\nnom = "{name}"\n', encoding="utf-8")
    return profiles.ProfileContext.for_id(profile_id)


def test_profile_keys_are_real_config_keys():
    cfg = Config()
    for section, key in config.PROFILE_KEYS:
        assert key in {f.name for f in fields(getattr(cfg, section))}, (section, key)


def test_every_menu_setting_has_a_scope():
    scopes = {s.key: s.scope for s in settings.SETTINGS}
    assert scopes["rider.ftp_w"] == scopes["rider.hr_max_bpm"] == scopes["bike.mass_kg"] == "profil"
    assert scopes["bots.level_pct"] == scopes["wind.mode"] == scopes["render.camera"] == "profil"
    assert scopes["render.quality"] == scopes["render.display"] == scopes["audio.master_pct"] == "machine"
    assert set(scopes.values()) == {"profil", "machine"}


def test_ftp_set_on_a_profile_stays_in_that_profile(home):
    machine = home / "config.toml"
    machine.parent.mkdir(parents=True)
    machine.write_text("# ma machine\n[render]\nquality = \"medium\"\n", encoding="utf-8")
    before = machine.read_text(encoding="utf-8")
    a, b = player("cycliste-a", "Cycliste A"), player("cycliste-b", "Cycliste B")
    profiles.activate(a)
    cfg = config.load(machine)
    settings.apply(cfg, {"rider.ftp_w": 280}, machine)
    assert machine.read_text(encoding="utf-8") == before
    assert "ftp_w = 280" in (a.root / profiles.FILE_NAME).read_text(encoding="utf-8")
    assert 'nom = "Cycliste A"' in (a.root / profiles.FILE_NAME).read_text(encoding="utf-8")   # identité gardée
    assert config.load(machine).rider.ftp_w == 280.0
    profiles.activate(b)
    assert config.load(machine).rider.ftp_w == 250.0 and config.load(machine).render.quality == "medium"


def test_graphics_quality_goes_to_the_machine(home):
    machine = home / "config.toml"
    a = player("cycliste-a", "Cycliste A")
    profiles.activate(a)
    before = (a.root / profiles.FILE_NAME).read_text(encoding="utf-8")
    settings.apply(config.load(machine), {"render.quality": "high", "render.camera": "side"}, machine)
    assert 'quality = "high"' in machine.read_text(encoding="utf-8")
    assert "camera" not in machine.read_text(encoding="utf-8")
    text = (a.root / profiles.FILE_NAME).read_text(encoding="utf-8")
    assert text.startswith(before.rstrip("\n")) and 'camera = "side"' in text and "quality" not in text


def test_without_profile_everything_goes_to_config_toml(home):
    machine = home / "config.toml"
    settings.apply(config.load(machine), {"rider.ftp_w": 300, "render.quality": "high"}, machine)
    text = machine.read_text(encoding="utf-8")
    assert "ftp_w = 300" in text and 'quality = "high"' in text
    assert not (home / "Profils").exists()


def test_player_key_left_in_config_toml_is_read_and_profile_wins(home):
    machine = home / "config.toml"
    machine.parent.mkdir(parents=True)
    machine.write_text("[rider]\nftp_w = 210\nmass_kg = 70\n", encoding="utf-8")
    a = player("cycliste-a", "Cycliste A")
    with (a.root / profiles.FILE_NAME).open("a", encoding="utf-8") as fh:
        fh.write("[rider]\nftp_w = 260\n")
    profiles.activate(a)
    cfg = config.load(machine)
    assert cfg.rider.ftp_w == 260.0 and cfg.rider.mass_kg == 70.0
    assert config.load(machine, profile_path=None).rider.ftp_w == 210.0


def test_machine_key_in_profile_is_ignored_with_warning(home, caplog):
    a = player("cycliste-a", "Cycliste A")
    with (a.root / profiles.FILE_NAME).open("a", encoding="utf-8") as fh:
        fh.write('[render]\nquality = "high"\ncamera = "side"\n')
    profiles.activate(a)
    with caplog.at_level(logging.WARNING, logger="config"):
        cfg = config.load(home / "config.toml")
    assert cfg.render.quality == "low" and cfg.render.camera == "side"
    assert "quality ignoré" in caplog.text


def test_bad_value_in_profile_names_the_file(home):
    a = player("cycliste-a", "Cycliste A")
    with (a.root / profiles.FILE_NAME).open("a", encoding="utf-8") as fh:
        fh.write("[rider]\nftp_w = 9000\n")
    profiles.activate(a)
    with pytest.raises(ConfigError, match=r"profil\.toml.*ftp_w"):
        config.load(home / "config.toml")


def test_refused_value_writes_nothing(home):
    machine = home / "config.toml"
    a = player("cycliste-a", "Cycliste A")
    profiles.activate(a)
    before = (a.root / profiles.FILE_NAME).read_text(encoding="utf-8")
    with pytest.raises(config_edit.ConfigEditError):   # braquet de départ au-delà des braquets de la machine
        config_edit.update_layers([("gearing", "start_gear", 30), ("gearing", "n_gears", 20)], machine)
    assert (a.root / profiles.FILE_NAME).read_text(encoding="utf-8") == before and not machine.exists()


def test_pairing_puts_the_heart_rate_strap_in_the_profile(home):
    machine = home / "config.toml"
    a = player("cycliste-a", "Cycliste A")
    profiles.activate(a)
    pairing.save(pairing.PairedDevices(trainer_address="AA:00:00:00:00:01", hr_address="BB:00:00:00:00:02"), machine)
    assert "trainer_address" in machine.read_text(encoding="utf-8")
    assert "hr_address" not in machine.read_text(encoding="utf-8")
    assert 'hr_address = "BB:00:00:00:00:02"' in (a.root / profiles.FILE_NAME).read_text(encoding="utf-8")
    assert 'hr = "ble"' in (a.root / profiles.FILE_NAME).read_text(encoding="utf-8")   # lot O24 : ceinture activée
