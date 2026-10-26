"""Lots O3 et O4 : réglages du menu (settings.py), écriture dans config.toml et messages IPC."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import jsonschema
import pytest

from openride_core import config as config_mod
from openride_core import settings
from openride_core.__main__ import main as core_main
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.mock_driver import MockDriver
from openride_core.session import CoreSession

SCHEMAS = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "ipc"
START = """# ma configuration
[rider]
ftp_w = 250        # FTP mesurée
mass_kg = 70

[drivers]
trainer_address = "C1:1C:00:00:00:09"

[inconnue]
cle = 1
"""


def test_current_lists_the_six_settings_with_bounds_from_config():
    items = settings.current(Config())
    assert [it["key"] for it in items] == list(settings.KEYS)
    ftp = items[0]
    assert ftp == {"key": "rider.ftp_w", "label": "FTP", "value": 250, "applies": "next_session",
                   "type": "int", "min": 50, "max": 600, "step": 5, "unit": "W"}
    quality = next(it for it in items if it["key"] == "render.quality")
    assert quality["type"] == "choice" and quality["choices"] == ["low", "medium", "high"]
    assert quality["applies"] == "now"
    gear = next(it for it in items if it["key"] == "gearing.start_gear")
    assert (gear["min"], gear["max"]) == (1, 24)


def test_bounds_and_choices_come_from_config(monkeypatch):
    """Critère 5 : une borne changée dans config.py se retrouve dans les réglages."""
    monkeypatch.setitem(config_mod.BOUNDS, ("rider", "ftp_w"), (60, 700))
    ftp = settings.current(Config())[0]
    assert (ftp["min"], ftp["max"]) == (60, 700)


def test_step_is_bounded_and_choices_loop(tmp_path: Path):
    """Critère 4."""
    cfg = Config()
    assert settings.step(cfg, "rider.ftp_w", 600, +1) == 600
    assert settings.step(cfg, "rider.ftp_w", 250, -1) == 245
    assert settings.step(cfg, "trainer.difficulty_pct", 0, -1) == 0
    assert settings.step(cfg, "render.quality", "high", +1) == "low"
    themes = tmp_path / "Themes"
    for name in ("automne", "brouillard"):
        (themes / name).mkdir(parents=True)
        (themes / name / "theme.json").write_text("{}", encoding="utf-8")
    (themes / "sans_fichier").mkdir()
    assert settings.installed_themes(themes) == ["default", "automne", "brouillard"]
    assert settings.step(cfg, "render.theme", "default", +1, themes) == "automne"
    assert settings.step(cfg, "render.theme", "default", -1, themes) == "brouillard"


def test_cli_set_changes_only_that_line_and_keeps_the_rest(tmp_path: Path, capsys):
    """Critère 2 : commentaires, section inconnue et appareils gardés, copie .bak."""
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    assert core_main(["settings", "set", "rider.ftp_w", "265", "--config", str(path)]) == 0
    text = path.read_text(encoding="utf-8")
    assert "ftp_w = 265   # FTP mesurée" in text
    assert text.replace("ftp_w = 265   # FTP mesurée", "ftp_w = 250        # FTP mesurée") == START
    assert (tmp_path / "config.toml.bak").read_text(encoding="utf-8") == START
    assert tomllib.loads(text)["drivers"]["trainer_address"] == "C1:1C:00:00:00:09"
    assert core_main(["settings", "set", "render.quality", "high", "--config", str(path)]) == 0
    assert tomllib.loads(path.read_text(encoding="utf-8"))["render"]["quality"] == "high"
    capsys.readouterr()
    assert core_main(["settings", "--json", "--config", str(path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["value"] == 265 and next(it for it in out if it["key"] == "render.quality")["value"] == "high"


@pytest.mark.parametrize("key,value,needle", [
    ("rider.ftp_w", "20", "50 à 600"),
    ("render.quality", "ultra", "low, medium, high"),
    ("rider.inconnu", "1", "réglage inconnu"),
    ("rider.mass_kg", "beaucoup", "nombre attendu"),
])
def test_cli_refuses_bad_values_and_writes_nothing(tmp_path: Path, capsys, key, value, needle):
    """Critère 3."""
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    assert core_main(["settings", "set", key, value, "--config", str(path)]) != 0
    assert needle in capsys.readouterr().out
    assert path.read_text(encoding="utf-8") == START and not (tmp_path / "config.toml.bak").exists()


def _session(tmp_path: Path, path: Path) -> tuple[CoreSession, list[dict], list[tuple[str, str]]]:
    s = CoreSession(Config(), driver=MockDriver(), inputs=[NullProvider()], journal_dir=tmp_path / "j",
                    routes_root=tmp_path / "routes", config_path=path)
    sent: list[dict] = []
    errors: list[tuple[str, str]] = []
    s.server.send_raw = lambda m, max_size=None: sent.append(m)
    s.server.send_error = lambda code, msg: errors.append((code, msg))
    return s, sent, errors


def test_ipc_list_and_set_setting(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    s, sent, errors = _session(tmp_path, path)
    validator = jsonschema.Draft202012Validator(json.loads((SCHEMAS / "settings.schema.json").read_text("utf-8")))
    s._on_command("list_settings", {}, 3)
    assert sent[-1]["type"] == "settings" and sent[-1]["request_cmd_id"] == 3
    validator.validate(sent[-1])
    assert len(json.dumps(sent[-1], separators=(",", ":")).encode()) <= 1400
    s._on_command("set_setting", {"key": "rider.ftp_w", "value": 265}, 4)
    assert not errors
    validator.validate(sent[-1])
    assert sent[-1]["request_cmd_id"] == 4 and sent[-1]["items"][0]["value"] == 265
    assert s.cfg.rider.ftp_w == 265.0 and s.server.hello_config["ftp_w"] == 265.0
    assert tomllib.loads(path.read_text(encoding="utf-8"))["rider"]["ftp_w"] == 265
    s._on_command("set_setting", {"key": "rider.mass_kg", "value": 80}, 5)
    assert s.physics.p.mass_kg == pytest.approx(80 + s.cfg.bike.mass_kg)
    s._on_command("set_setting", {"key": "trainer.difficulty_pct", "value": 70}, 6)
    assert s.state.difficulty_pct == 70 and s.difficulty_pct == 70.0
    s._on_command("set_setting", {"key": "gearing.start_gear", "value": 8}, 7)
    assert s.gearing.k == 8


def test_ipc_set_setting_refused_during_a_session_or_out_of_bounds(tmp_path: Path):
    """Critère 4 d'O4 : refusé pendant une séance, rien n'est écrit."""
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    s, sent, errors = _session(tmp_path, path)
    for st in ("RUNNING", "PAUSED"):
        s.state.session_state = st
        s._on_command("set_setting", {"key": "rider.ftp_w", "value": 265}, 10)
        assert errors[-1][0] == "busy"
    s.state.session_state = "IDLE"
    s._on_command("set_setting", {"key": "rider.ftp_w", "value": 20}, 11)
    assert errors[-1][0] == "setting_invalid" and "50 à 600" in errors[-1][1]
    s._on_command("set_setting", {"key": "drivers.trainer", "value": "sim"}, 12)
    assert errors[-1][0] == "setting_invalid"
    assert path.read_text(encoding="utf-8") == START
    assert not [m for m in sent if m.get("type") == "settings"]
