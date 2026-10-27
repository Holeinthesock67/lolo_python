"""Lot O3 : écriture commune et typée de `config.toml` (`config_writer.py`)."""

from __future__ import annotations

import tomllib

import pytest

from openride_core import config as config_mod
from openride_core import config_writer
from openride_core.config_writer import ConfigWriteError, toml_literal, update_config

START = """# Ma configuration
[rider]
ftp_w = 250   # mesurée en septembre
mass_kg = 75

[section_perso]
note = "gardée"

[drivers]
trainer_address = "AA:BB:CC:DD:EE:01"
click_address = "AA:BB:CC:DD:EE:02"
"""


@pytest.mark.parametrize("value, literal", [
    (True, "true"), (False, "false"), (265, "265"), (265.0, "265"), (72.5, "72.5"),
    ("forêt", '"forêt"'), ('a"b', '"a\\"b"'),
])
def test_toml_literal(value, literal):
    assert toml_literal(value) == literal


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, [1]])
def test_toml_literal_refuses(bad):
    with pytest.raises(ConfigWriteError):
        toml_literal(bad)


def test_only_the_changed_lines_move(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    changed = update_config({("rider", "ftp_w"): 265.0, ("render", "quality"): "medium"}, path)
    assert changed == ["[rider] ftp_w = 265", '[render] quality = "medium"']
    text = path.read_text(encoding="utf-8")
    assert text == START.replace("ftp_w = 250", "ftp_w = 265") + '\n[render]\nquality = "medium"\n'
    assert (tmp_path / "config.toml.bak").read_text(encoding="utf-8") == START
    cfg = config_mod.load(path)
    assert cfg.rider.ftp_w == 265.0 and cfg.render.quality == "medium"
    assert tomllib.loads(text)["section_perso"] == {"note": "gardée"}


def test_nothing_written_on_invalid_value(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    with pytest.raises(ConfigWriteError, match=r"\[rider\] ftp_w : 20 hors de 50 à 600"):
        update_config({("rider", "mass_kg"): 80, ("rider", "ftp_w"): 20}, path)
    assert path.read_text(encoding="utf-8") == START
    assert not (tmp_path / "config.toml.bak").exists()


def test_unchanged_value_writes_nothing(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    assert update_config({("rider", "mass_kg"): 75}, path) == []
    assert not (tmp_path / "config.toml.bak").exists()


def test_missing_file_is_created(tmp_path):
    path = tmp_path / "sous" / "config.toml"
    assert update_config({("gearing", "start_gear"): 8}, path) == ["[gearing] start_gear = 8"]
    assert config_mod.load(path).gearing.start_gear == 8


def test_default_path_is_the_local_config(tmp_path, monkeypatch):
    target = tmp_path / "config.toml"
    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG_PATH", target)
    update_config({("rider", "ftp_w"): 270})
    assert config_mod.load(target).rider.ftp_w == 270


def test_pairing_uses_the_common_writer(tmp_path, monkeypatch):
    from openride_core import pairing

    calls = []
    real = config_writer.update_config
    monkeypatch.setattr(config_writer, "update_config", lambda ch, p=None: calls.append(ch) or real(ch, p))
    path = tmp_path / "config.toml"
    pairing.save(pairing.PairedDevices(trainer_address="AA:BB:CC:DD:EE:09"), path)
    assert calls == [{("drivers", "trainer_address"): "AA:BB:CC:DD:EE:09"}]
