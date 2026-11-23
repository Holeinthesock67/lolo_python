"""Lots O3 et O4 : réglages du menu (settings.py), écriture dans config.toml et messages IPC."""

from __future__ import annotations

import json
import logging
import re
import tomllib
from pathlib import Path

import jsonschema
import pytest

from openride_core import config as config_mod
from openride_core import settings
from openride_core.__main__ import main as core_main
from openride_core.config import Config
from openride_core.input_providers import NullProvider
from openride_core.ipc_server import MAX_DATAGRAM_SIZE, MAX_LIST_DATAGRAM_SIZE, IpcServer
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


def test_current_lists_the_settings_with_bounds_from_config():
    items = settings.current(Config())
    assert [it["key"] for it in items] == list(settings.KEYS)
    ftp = items[0]
    assert ftp == {"key": "rider.ftp_w", "label": "FTP", "group": "rider", "value": 250,
                   "applies": "next_session", "type": "int", "min": 50, "max": 600, "step": 5, "unit": "W"}
    quality = next(it for it in items if it["key"] == "render.quality")
    assert quality["type"] == "choice" and quality["choices"] == ["low", "medium", "high"]
    assert quality["applies"] == "now"
    gear = next(it for it in items if it["key"] == "gearing.start_gear")
    assert (gear["min"], gear["max"]) == (1, 24)
    display = next(it for it in items if it["key"] == "render.display")
    assert display == {"key": "render.display", "label": "Mode d'affichage", "group": "graphics",
                       "value": "fullscreen", "applies": "now", "type": "choice", "choices": ["windowed", "borderless", "fullscreen"]}
    camera = next(it for it in items if it["key"] == "render.camera")
    assert camera["value"] == "follow_near" and camera["group"] == "graphics"   # lot V12
    assert camera["choices"] == ["subjective", "follow_near", "follow_far", "side"]


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
    assert settings.step(cfg, "render.display", "fullscreen", +1) == "windowed"
    assert settings.step(cfg, "render.display", "windowed", -1) == "fullscreen"
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
    ("render.display", "maximized", "windowed, borderless, fullscreen"),
    ("render.camera", "drone", "subjective, follow_near, follow_far, side"),
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
    assert len(json.dumps(sent[-1], separators=(",", ":")).encode()) <= MAX_LIST_DATAGRAM_SIZE
    s._on_command("set_setting", {"key": "rider.ftp_w", "value": 265}, 4)
    assert not errors
    validator.validate(sent[-1])
    assert sent[-1]["request_cmd_id"] == 4 and sent[-1]["items"][0]["value"] == 265
    assert s.cfg.rider.ftp_w == 265.0 and s.server.hello_config["ftp_w"] == 265.0
    assert tomllib.loads(path.read_text(encoding="utf-8"))["rider"]["ftp_w"] == 265
    assert s.server.hello_config["chart"] == "reduced"
    s._on_command("set_setting", {"key": "render.chart", "value": "full"}, 8)
    assert not errors and s.cfg.render.chart == "full" and s.server.hello_config["chart"] == "full"
    s._on_command("set_setting", {"key": "render.chart", "value": "énorme"}, 9)
    assert errors and errors[-1][0] == "setting_invalid"
    errors.clear()
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


def test_wind_settings_lot_p16():
    """Lot P16 : réglages du vent dans le menu, bornes et choix tirés de config.py."""
    cfg = Config()
    items = {i["key"]: i for i in settings.current(cfg)}
    assert items["wind.mode"]["value"] == "off"
    assert items["wind.mode"]["choices"] == ["off", "fixed", "gusty", "theme", "local"]
    cap = items["wind.max_grade_offset_pct"]
    assert (cap["value"], cap["min"], cap["max"], cap["step"]) == (4, 0, 8, 1)
    assert items["wind.speed_kmh"]["max"] == 60
    assert settings.step(cfg, "wind.mode", "theme", +1) == "local"
    assert settings.step(cfg, "wind.mode", "local", +1) == "off"
    assert settings.step(cfg, "wind.max_grade_offset_pct", 8, +1) == 8
    assert settings.step(cfg, "wind.speed_kmh", 20, +1) == 25


def test_gravel_setting_lot_u16(tmp_path: Path):
    """Lot U16 (partie gravel) : `gravel.mode` dans Séance, coupé par défaut, avec sa légende ; écrit dans
    config.toml, porté par `hello_ack.config.gravel` ; refusé pendant une séance."""
    items = {i["key"]: i for i in settings.current(Config())}
    g = items["gravel.mode"]
    assert (g["group"], g["value"], g["applies"]) == ("ride", "off", "next_session")
    assert g["choices"] == ["off", "auto", "compacted", "gravel", "dirt"]
    assert "Chemins réels" in g["help"] and "pente ajoutée maximale" in g["help"]
    assert "help" not in items["wind.speed_kmh"]
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    s, _, errors = _session(tmp_path, path)
    assert s.server.hello_config["gravel"] == "off"
    s._on_command("set_setting", {"key": "gravel.mode", "value": "gravel"}, 2)
    assert not errors and s.cfg.gravel.mode == "gravel" and s.server.hello_config["gravel"] == "gravel"
    assert tomllib.loads(path.read_text(encoding="utf-8"))["gravel"]["mode"] == "gravel"
    s.state.session_state = "RUNNING"
    s._on_command("set_setting", {"key": "gravel.mode", "value": "dirt"}, 3)
    assert errors[-1][0] == "busy" and s.cfg.gravel.mode == "gravel"


def test_biome_setting_lot_u16(tmp_path: Path):
    """Lot U16 : `render.biome` dans Graphisme, `auto` puis les biomes de l'engine (biome_ids.gd), appliqué
    tout de suite ; écrit dans config.toml, porté par `hello_ack.config.biome`, permis pendant une séance."""
    gd = (Path(__file__).resolve().parents[2] / "engine" / "scripts" / "biome_ids.gd").read_text(encoding="utf-8")
    engine_biomes = re.findall(r'"([a-z_]+)"', gd.split("const BIOMES", 1)[1].split("= [", 1)[1].split("]", 1)[0])
    assert list(config_mod.BIOMES) == engine_biomes and len(engine_biomes) == len(set(engine_biomes)) >= 19
    b = {i["key"]: i for i in settings.current(Config())}["render.biome"]
    assert (b["group"], b["value"], b["applies"], b["choices"]) == ("graphics", "auto", "now", ["auto", *engine_biomes])
    assert "Automatique" in b["help"]
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    s, _, errors = _session(tmp_path, path)
    assert s.server.hello_config["biome"] == "auto"
    s._on_command("set_setting", {"key": "render.biome", "value": "savanna"}, 2)
    assert not errors and s.cfg.render.biome == "savanna" and s.server.hello_config["biome"] == "savanna"
    assert tomllib.loads(path.read_text(encoding="utf-8"))["render"]["biome"] == "savanna"
    s.state.session_state = "RUNNING"
    s._on_command("set_setting", {"key": "render.biome", "value": "jungle"}, 3)
    assert not errors and s.cfg.render.biome == "jungle"
    s._on_command("set_setting", {"key": "render.biome", "value": "lune"}, 4)
    assert errors[-1][0] == "setting_invalid"


def test_settings_with_installed_themes_is_sent(tmp_path: Path):
    """Les thèmes installés allongent la liste des choix : `settings` passe 4 096 octets et part quand
    même, en un seul datagramme (60 000 octets au plus comme `plans`, contrat §2, depuis le 30 octobre)."""
    for i in range(12):
        (tmp_path / f"asphalte_et_herbe_{i:02d}").mkdir()
        (tmp_path / f"asphalte_et_herbe_{i:02d}" / "theme.json").write_text("{}", encoding="utf-8")
    msg = {"type": "settings", "v": 1, "request_cmd_id": 2_147_483_647,
           "items": settings.current(Config(), tmp_path)}
    sent: list[bytes] = []

    class Sock:
        def sendto(self, payload, addr):
            sent.append(payload)

    srv = IpcServer()
    srv._tx_sock = Sock()
    srv.send_raw(msg)
    assert len(sent) == 1 and MAX_DATAGRAM_SIZE < len(sent[0]) <= MAX_LIST_DATAGRAM_SIZE
    assert json.loads(sent[0]) == msg


def test_audio_volumes_in_menu(tmp_path: Path):
    """Volumes par catégorie (docs/AUDIO.md) : 0 à 100 % par pas de 10, appliqués tout de suite, écrits
    dans une section `[audio]` créée au besoin."""
    cfg = Config()
    items = {i["key"]: i for i in settings.current(cfg)}
    keys = ["audio.master_pct", "audio.ride_pct", "audio.ambience_pct", "audio.events_pct",
            "audio.rogue_sfx_pct", "audio.rogue_music_pct"]
    defaults = {"audio.rogue_sfx_pct": 70, "audio.rogue_music_pct": 40}   # Cyber-Rogue plus bas (lot R18)
    for key in keys:
        it = items[key]
        assert (it["value"], it["min"], it["max"], it["step"], it["unit"], it["applies"]) == (
            defaults.get(key, 100), 0, 100, 10, "%", "now")
        assert len(it["label"]) <= 32 and it["group"] == "sound"
    assert settings.step(cfg, "audio.master_pct", 100, +1) == 100
    assert settings.step(cfg, "audio.master_pct", 0, -1) == 0
    path = tmp_path / "config.toml"
    path.write_text("[rider]\nftp_w = 250\n", encoding="utf-8")
    settings.apply(cfg, {"audio.ambience_pct": 40}, path)
    assert cfg.audio.ambience_pct == 40
    assert config_mod.load(path).audio.ambience_pct == 40
    with pytest.raises(settings.SettingError):
        settings.check(cfg, "audio.master_pct", 101)


def test_fps_counter_setting(tmp_path: Path):
    """Compteur d'images/s du HUD : choix off / on / detail (temps CPU et GPU en plus, pour les essais),
    appliqué tout de suite, coupé par défaut."""
    cfg = Config()
    it = {i["key"]: i for i in settings.current(cfg)}["render.fps"]
    assert (it["value"], it["choices"], it["applies"]) == ("off", ["off", "on", "detail"], "now")
    path = tmp_path / "config.toml"
    path.write_text("[render]\nquality = \"low\"\n", encoding="utf-8")
    settings.apply(cfg, {"render.fps": "on"}, path)
    assert config_mod.load(path).render.fps == "on"
    settings.apply(config_mod.load(path), {"render.fps": "detail"}, path)
    assert config_mod.load(path).render.fps == "detail"
    with pytest.raises(settings.SettingError):
        settings.check(cfg, "render.fps", "oui")


def test_draft_gauge_retired(tmp_path: Path, caplog):
    """Jauge d'abri des bots retirée (lot NI1, 21/11) : plus au menu, et un config.toml d'avant qui la porte se lit
    sans avertissement de faute de frappe."""
    assert "render.draft_gauge" not in {i["key"] for i in settings.current(Config())}
    path = tmp_path / "config.toml"
    path.write_text("[render]\nquality = \"low\"\ndraft_gauge = \"on\"\n", encoding="utf-8")
    with caplog.at_level(logging.INFO, logger=config_mod.log.name):
        cfg = config_mod.load(path)
    assert not hasattr(cfg.render, "draft_gauge")
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING and "draft_gauge" in r.getMessage()]
    assert any("draft_gauge" in r.getMessage() and "NI1" in r.getMessage() for r in caplog.records)


def test_settings_groups_and_new_entries():
    """Sous-écrans de « Réglages » : chaque réglage a un groupe connu, groupes contigus dans l'ordre de
    `GROUPS` ; poids du vélo, direction et rafales du vent ajoutés (bornes de config.py)."""
    cfg = Config()
    items = settings.current(cfg)
    groups = [it["group"] for it in items]
    assert set(groups) == set(settings.GROUPS)
    assert sorted(groups, key=settings.GROUPS.index) == groups
    by_key = {it["key"]: it for it in items}
    bike = by_key["bike.mass_kg"]
    assert (bike["group"], bike["value"], bike["min"], bike["max"], bike["unit"]) == ("rider", 9, 3, 30, "kg")
    direction = by_key["wind.from_deg"]
    assert (direction["value"], direction["min"], direction["max"], direction["step"], direction["unit"]) == (270, 0, 360, 45, "°")
    gust = by_key["wind.gust_pct"]
    assert (gust["value"], gust["min"], gust["max"], gust["step"]) == (0, 0, 100, 10)
    assert settings.step(cfg, "wind.from_deg", 360, +1) == 360


def test_bool_and_scaled_settings_in_the_menu(tmp_path: Path):
    """Lot O26 : décor vivant (booléen en on / off), relief (2,5 affiché 250 %), ressenti du vent."""
    cfg = Config()
    items = {it["key"]: it for it in settings.current(cfg)}
    living = items["render.living"]
    assert living == {"key": "render.living", "label": "Décor vivant", "group": "graphics", "value": "on",
                      "applies": "relaunch", "type": "choice", "choices": ["on", "off"]}
    relief = items["render.visual_grade_scale"]
    assert (relief["value"], relief["min"], relief["max"], relief["step"], relief["unit"]) == (250, 100, 300, 25, "%")
    assert relief["applies"] == "relaunch"
    assert items["wind.feel"]["choices"] == ["grade", "ftms"] and items["wind.feel"]["group"] == "advanced"
    assert settings.step(cfg, "render.visual_grade_scale", 250, +1) == 275
    with pytest.raises(settings.SettingError):
        settings.check(cfg, "render.visual_grade_scale", 310)
    with pytest.raises(settings.SettingError):
        settings.check(cfg, "render.living", True)
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    settings.apply(cfg, {"render.living": "off", "render.visual_grade_scale": 150, "wind.feel": "ftms"}, path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["render"]["living"] is False and data["render"]["visual_grade_scale"] == 1.5
    assert data["wind"]["feel"] == "ftms"
    assert cfg.render.living is False and cfg.render.visual_grade_scale == 1.5
    again = config_mod.load(path, None)
    assert (again.render.living, again.render.visual_grade_scale) == (False, 1.5)
    assert {it["key"]: it["value"] for it in settings.current(again)}["render.living"] == "off"


def test_advanced_settings_and_settings_in_parts(tmp_path: Path):
    """Lot O27 : sous-écran « Avancé » (monde ouvert hors ligne, plafonds de disque, progression) ;
    `settings` part en parties comme `routes`, plus de plafond de 32 réglages."""
    from openride_core.ipc_lists import chunk_list_message

    cfg = Config()
    by_key = {it["key"]: it for it in settings.current(cfg)}
    assert [k for k, it in by_key.items() if it["group"] == "advanced"] == [
        "trainer.control", "wind.max_grade_offset_pct", "wind.feel",   # choix d'essai et plafond, lot NI2
        "open_world.network", "open_world.cache_max_gb", "render.theme_library_gb", "progression.enabled"]
    assert by_key["open_world.network"]["choices"] == ["on", "off"] and by_key["open_world.network"]["value"] == "on"
    cache = by_key["open_world.cache_max_gb"]
    assert (cache["value"], cache["min"], cache["max"], cache["unit"]) == (5, 1, 500, "Go")   # 0,5 Go arrondi au-dessus
    assert by_key["progression.enabled"]["applies"] == "relaunch"
    path = tmp_path / "config.toml"
    settings.apply(cfg, {"open_world.network": "off", "open_world.cache_max_gb": 20, "progression.enabled": "off"}, path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["open_world"] == {"network": False, "cache_max_gb": 20} and data["progression"]["enabled"] is False
    assert cfg.open_world.cache_max_gb == 20.0
    validator = jsonschema.Draft202012Validator(json.loads((SCHEMAS / "settings.schema.json").read_text("utf-8")))
    items = settings.current(cfg)
    parts = chunk_list_message("settings", 5, items, False, 2_000)
    assert len(parts) > 1 and [m["part"] for m in parts] == list(range(1, len(parts) + 1))
    for m in parts:
        validator.validate(m)
    assert [it for m in parts for it in m["items"]] == items


def test_seasons_random_and_month_lot_u13b(tmp_path: Path):
    """Lot U13b : `render.seasons` gagne `random` (au hasard, hiver deux fois moins souvent) et `render.month`
    (date du PC ou mois choisi) suit dans Graphisme, appliqué tout de suite et écrit dans config.toml."""
    items = {i["key"]: i for i in settings.current(Config())}
    se, mo = items["render.seasons"], items["render.month"]
    assert "random" in se["choices"] and "hasard" in se["help"]
    assert (mo["group"], mo["value"], mo["applies"]) == ("graphics", "pc", "now")
    assert mo["choices"] == ["pc", "january", "february", "march", "april", "may", "june", "july", "august",
                             "september", "october", "november", "december"]
    keys = [i["key"] for i in settings.current(Config())]
    assert keys.index("render.month") == keys.index("render.seasons") + 1
    # Les choix de l'engine (settings_view_model.gd) ont tous un libellé français
    gd = (Path(__file__).resolve().parents[2] / "engine" / "scripts" / "settings_view_model.gd").read_text(encoding="utf-8")
    for key in ("render.seasons", "render.month"):
        block = gd.split(f'"{key}": {{', 1)[1].split("}", 1)[0]
        assert set(re.findall(r'"([a-z]+)":', block)) == set(items[key]["choices"]), key
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    s, _, errors = _session(tmp_path, path)
    s._on_command("set_setting", {"key": "render.seasons", "value": "random"}, 2)
    s._on_command("set_setting", {"key": "render.month", "value": "february"}, 3)
    assert not errors and s.cfg.render.seasons == "random" and s.cfg.render.month == "february"
    written = tomllib.loads(path.read_text(encoding="utf-8"))["render"]
    assert (written["seasons"], written["month"]) == ("random", "february")
    s._on_command("set_setting", {"key": "render.month", "value": "13"}, 4)
    assert errors[-1][0] == "setting_invalid"


def test_lot_ni2_one_place_per_setting_and_rule_for_useless_lines():
    """Lot NI2 (audit des éléments inutiles du 21 novembre) : réglages des écrans de mode et du conseil dans le
    groupe `screen` (absent de « Réglages », toujours écrits par `set_setting`) ; lignes dépendantes avec `when`
    sur des clés et des valeurs qui existent ; choix d'essai et plafond en Avancé ; textures retirées du menu."""
    cfg = Config()
    items = settings.current(cfg)
    by_key = {it["key"]: it for it in items}
    screen = [k for k, it in by_key.items() if it["group"] == settings.SCREEN_GROUP]
    assert screen and all(k.split(".")[0] in settings.SCREEN_SECTIONS for k in screen)
    assert {"survivor.opponents", "grandprix.chaos", "coach.objectif"} <= set(screen)
    assert not [k for k, it in by_key.items() if k.split(".")[0] in settings.SCREEN_SECTIONS and k not in screen]
    assert "render.texture_level" not in by_key
    assert by_key["wind.max_grade_offset_pct"]["label"] == "Pente ajoutée max"
    assert {by_key[k]["group"] for k in ("trainer.control", "wind.feel", "wind.max_grade_offset_pct")} == {"advanced"}
    whens = {k: it["when"] for k, it in by_key.items() if "when" in it}
    assert set(whens) == {"depart.cadence_rpm", "ride.vehicle_draft", "render.month", "wind.speed_kmh",
                          "wind.from_deg", "wind.gust_pct", "wind.feel"}
    for key, conds in whens.items():   # une dépendance porte sur un réglage du menu et sur ses vrais choix
        for c in conds:
            assert c["key"] != key and set(c["in"]) <= set(by_key[c["key"]]["choices"]), (key, c)
    assert whens["wind.gust_pct"] == [{"key": "wind.mode", "in": ["gusty"]}]
    # Un réglage du groupe `screen` reste réglable (écran Prêt du mode)
    settings.check(cfg, "survivor.opponents", 6)
    validator = jsonschema.Draft202012Validator(json.loads((SCHEMAS / "settings.schema.json").read_text("utf-8")))
    validator.validate({"type": "settings", "v": 1, "request_cmd_id": 0, "items": items})
    # L'engine connaît le groupe `screen` (settings_view_model.gd)
    gd = (Path(__file__).resolve().parents[2] / "engine" / "scripts" / "settings_view_model.gd").read_text(encoding="utf-8")
    assert f'const SCREEN_GROUP := "{settings.SCREEN_GROUP}"' in gd


def test_graphic_style_lot_cs1(tmp_path: Path):
    """Lot CS1 : « Style graphique » (`render.style`) dans Graphisme, juste après la qualité, `realistic` par
    défaut (image inchangée), appliqué tout de suite et écrit dans config.toml ; libellés français en mots."""
    assert Config().render.style == "realistic"
    items = {i["key"]: i for i in settings.current(Config())}
    st = items["render.style"]
    assert (st["label"], st["group"], st["type"], st["value"], st["applies"]) == (
        "Style graphique", "graphics", "choice", "realistic", "now")
    assert st["choices"] == ["realistic", "toon"]
    assert "Réaliste" in st["help"] and "Dessin animé" in st["help"] and "Cyber-Rogue" in st["help"]
    keys = [i["key"] for i in settings.current(Config())]
    assert keys.index("render.style") == keys.index("render.quality") + 1
    gd = (Path(__file__).resolve().parents[2] / "engine" / "scripts" / "settings_view_model.gd").read_text(encoding="utf-8")
    block = gd.split('"render.style": {', 1)[1].split("}", 1)[0]
    assert dict(re.findall(r'"([a-z]+)": "([^"]+)"', block)) == {"realistic": "réaliste", "toon": "dessin animé"}
    style_gd = (Path(__file__).resolve().parents[2] / "engine" / "scripts" / "graphic_style.gd").read_text(encoding="utf-8")
    assert 'const STYLES: Array[String] = [REALISTIC, TOON]' in style_gd
    assert 'const REALISTIC := "realistic"' in style_gd and 'const TOON := "toon"' in style_gd
    path = tmp_path / "config.toml"
    path.write_text(START, encoding="utf-8")
    s, _, errors = _session(tmp_path, path)
    s._on_command("set_setting", {"key": "render.style", "value": "toon"}, 2)
    assert not errors and s.cfg.render.style == "toon"
    assert tomllib.loads(path.read_text(encoding="utf-8"))["render"]["style"] == "toon"
    s._on_command("set_setting", {"key": "render.style", "value": "manga"}, 3)
    assert errors[-1][0] == "setting_invalid" and s.cfg.render.style == "toon"

