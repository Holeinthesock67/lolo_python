"""Lot O3 : réglages du menu côté core (`settings.py`, `openride-core settings`)."""

from __future__ import annotations

import json

import pytest

from openride_core import config as config_mod
from openride_core import settings
from openride_core.__main__ import main
from openride_core.settings import SETTINGS, SettingError

START = """# Configuration de test : commentaires, section inconnue et appareils appairés
[rider]
ftp_w = 250   # FTP de septembre

[outils_perso]
editeur = "vim"

[drivers]
trainer = "ftms"
trainer_address = "AA:BB:CC:DD:EE:01"
click_address = "AA:BB:CC:DD:EE:02"
click_minus_address = "AA:BB:CC:DD:EE:03"
"""


@pytest.fixture
def cfg_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    return path


@pytest.fixture
def themes(tmp_path):
    d = tmp_path / "Themes"
    for name in ("vosges", "alpes", "sans_fichier", ".cache"):
        (d / name).mkdir(parents=True)
    for name in ("vosges", "alpes"):
        (d / name / "theme.json").write_text("{}")
    return d


def test_list_is_closed_and_ordered():
    assert [s.key for s in SETTINGS] == ["rider.ftp_w", "rider.mass_kg", "trainer.difficulty_pct",
                                         "gearing.start_gear", "render.quality", "render.theme",
                                         "wind.mode", "wind.speed_kmh", "wind.from_deg", "wind.max_grade_offset_pct"]
    steps = {s.key: s.step for s in SETTINGS if s.type != "choice"}
    assert steps == {"rider.ftp_w": 5, "rider.mass_kg": 1, "trainer.difficulty_pct": 10, "gearing.start_gear": 1,
                     "wind.speed_kmh": 5, "wind.from_deg": 45, "wind.max_grade_offset_pct": 0.5}
    assert settings.get("trainer.difficulty_pct").type == "slider"
    assert all(s.applies in settings.APPLIES for s in SETTINGS)
    assert {s.key for s in SETTINGS if s.applies == "now"} == {"render.quality", "render.theme"}


def test_current_shape(themes):
    cfg = config_mod.Config()
    items = settings.current(cfg, themes)
    ftp = items[0]
    assert ftp == {"key": "rider.ftp_w", "label": "FTP", "type": "number", "unit": "W", "value": 250,
                   "min": 50, "max": 600, "step": 5, "applies": "next_session"}
    gear = next(i for i in items if i["key"] == "gearing.start_gear")
    assert gear["max"] == cfg.gearing.n_gears and isinstance(gear["value"], int)
    theme = next(i for i in items if i["key"] == "render.theme")
    assert theme["choices"] == ["default", "alpes", "vosges"] and "min" not in theme
    json.dumps(items)   # prêt pour l'IPC


def test_bounds_and_choices_come_from_config_py(monkeypatch):
    """Critère 5 : une borne ou un choix changé dans config.py se retrouve dans les réglages."""
    monkeypatch.setitem(config_mod.BOUNDS, ("rider", "ftp_w"), (40, 700))
    monkeypatch.setitem(config_mod.CHOICES, ("render", "quality"), ("low", "medium", "high", "ultra"))
    items = {i["key"]: i for i in settings.current(config_mod.Config())}
    assert (items["rider.ftp_w"]["min"], items["rider.ftp_w"]["max"]) == (40, 700)
    assert items["render.quality"]["choices"] == ["low", "medium", "high", "ultra"]
    assert settings.step("rider.ftp_w", 700, +1) == 700


def test_step(themes):
    """Critère 4."""
    assert settings.step("rider.ftp_w", 600, +1) == 600
    assert settings.step("rider.ftp_w", 50, -1) == 50
    assert settings.step("rider.ftp_w", 250, +1) == 255
    assert settings.step("rider.mass_kg", 72.5, -1) == 71.5
    assert settings.step("trainer.difficulty_pct", 50, +1) == 60
    assert settings.step("trainer.difficulty_pct", 100, +1) == 100
    assert settings.step("render.quality", "high", +1) == "low"
    assert settings.step("render.quality", "low", -1) == "high"
    assert settings.step("render.theme", "default", +1, themes_dir=themes) == "alpes"
    assert settings.step("render.theme", "alpes", +1, themes_dir=themes) == "vosges"
    assert settings.step("render.theme", "vosges", +1, themes_dir=themes) == "default"
    assert settings.step("render.theme", "disparu", +1, themes_dir=themes) == "default"
    cfg = config_mod.Config()
    cfg.gearing.n_gears = 10
    assert settings.step("gearing.start_gear", 10, +1, cfg) == 10
    with pytest.raises(SettingError, match="réglage inconnu"):
        settings.step("bike.mass_kg", 9, +1)


def test_apply_writes_only_the_setting(cfg_file, themes):
    changed = settings.apply({"rider.ftp_w": 265, "render.theme": "vosges"}, cfg_file, themes)
    assert changed == ["[rider] ftp_w = 265", '[render] theme = "vosges"']
    cfg = config_mod.load(cfg_file)
    assert cfg.rider.ftp_w == 265 and cfg.render.theme == "vosges"
    assert cfg.drivers.click_minus_address == "AA:BB:CC:DD:EE:03"


@pytest.mark.parametrize("changes, message", [
    ({"render.theme": "lune"}, "non installé"),
    ({"rider.ftp_w": "265"}, "nombre attendu"),
    ({"rider.ftp_w": True}, "nombre attendu"),
    ({"drivers.trainer": "mock"}, "réglage inconnu"),
    ({"rider.mass_kg": 500}, r"\[rider\] mass_kg : 500 hors de 20 à 200"),
])
def test_apply_refuses(cfg_file, themes, changes, message):
    with pytest.raises(SettingError, match=message):
        settings.apply(changes, cfg_file, themes)
    assert cfg_file.read_text(encoding="utf-8") == START


def test_parse_value():
    assert settings.parse_value("rider.ftp_w", "265") == 265.0
    assert settings.parse_value("rider.mass_kg", "72,5") == 72.5
    assert settings.parse_value("gearing.start_gear", "8") == 8
    assert settings.parse_value("render.quality", "high") == "high"
    for key, bad in (("gearing.start_gear", "8.5"), ("rider.ftp_w", "beaucoup")):
        with pytest.raises(SettingError, match=key):
            settings.parse_value(key, bad)


# --- ligne de commande -------------------------------------------------------------------------

def test_cli_set_changes_one_line_and_keeps_backup(cfg_file, capsys):
    """Critère 2 : seule la ligne de la FTP change, avec copie .bak."""
    assert main(["settings", "set", "rider.ftp_w", "265", "--config", str(cfg_file)]) == 0
    assert cfg_file.read_text(encoding="utf-8") == START.replace("ftp_w = 250", "ftp_w = 265")
    assert (cfg_file.parent / "config.toml.bak").read_text(encoding="utf-8") == START
    assert "[rider] ftp_w = 265" in capsys.readouterr().out


@pytest.mark.parametrize("key, value, expected", [
    ("rider.ftp_w", "20", "ftp_w : 20 hors de 50 à 600"),
    ("render.quality", "ultra", "quality : 'ultra' n'est pas parmi low, medium, high"),
    ("bike.cda_m2", "0.3", "réglage inconnu 'bike.cda_m2'"),
])
def test_cli_refuses(cfg_file, capsys, key, value, expected):
    """Critère 3 : rien n'est écrit, message qui cite la clé et les bornes, code non nul."""
    assert main(["settings", "set", key, value, "--config", str(cfg_file)]) == 1
    assert expected in capsys.readouterr().err
    assert cfg_file.read_text(encoding="utf-8") == START
    assert not (cfg_file.parent / "config.toml.bak").exists()


def test_cli_set_needs_key_and_value(cfg_file, capsys):
    assert main(["settings", "set", "rider.ftp_w", "--config", str(cfg_file)]) == 1
    assert "usage" in capsys.readouterr().err


def test_cli_json_is_stable(cfg_file, capsys):
    """Critère 6."""
    assert main(["settings", "--json", "--config", str(cfg_file)]) == 0
    first = capsys.readouterr().out
    assert main(["settings", "--json", "--config", str(cfg_file)]) == 0
    assert capsys.readouterr().out == first
    data = json.loads(first)
    assert data["config"] == str(cfg_file)
    assert [i["key"] for i in data["settings"]] == [s.key for s in SETTINGS]
    assert all(set(i) >= {"key", "label", "type", "unit", "value", "applies"} for i in data["settings"])


def test_cli_text(cfg_file, capsys):
    assert main(["settings", "--config", str(cfg_file)]) == 0
    out = capsys.readouterr().out
    assert "FTP" in out and "250 W" in out and "à la prochaine séance" in out and "immédiatement" in out


def test_wind_settings_lot_p16():
    cfg = config_mod.Config()
    items = {i["key"]: i for i in settings.current(cfg)}
    assert items["wind.mode"]["value"] == "off"
    assert items["wind.mode"]["choices"] == ["off", "fixed", "gusty", "theme"]
    cap = items["wind.max_grade_offset_pct"]
    assert (cap["value"], cap["min"], cap["max"], cap["step"]) == (4, 0, 8, 0.5)
    assert items["wind.from_deg"]["unit"] == "°" and items["wind.speed_kmh"]["max"] == 60
    assert settings.step("wind.mode", "theme", 1) == "off"
    assert settings.step("wind.max_grade_offset_pct", 8, 1) == 8
    assert settings.step("wind.from_deg", 270, 1) == 315
