"""Configuration invalide réparable depuis le lanceur (lot O34) : valeur remise par défaut ou fichier
illisible remis à neuf, toujours avec une copie `.bak`, et seulement sur accord du joueur."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from openride_core import config as config_mod
from openride_core import config_repair, launcher

from test_launch_no_terminal import capture_run, home  # noqa: F401  (fixture `home`)

TEMPLATE_TEXT = "# modèle\n[render]\nquality = \"low\"\n"


def load_error(path: Path, profile: Path | None = None) -> config_mod.ConfigError:
    with pytest.raises(config_mod.ConfigError) as info:
        config_mod.load(path, profile)
    return info.value


def test_errors_name_the_faulty_value(tmp_path):
    cfg = tmp_path / "config.toml"
    for text, where in (("[rider]\nftp_w = 5\n", ("rider", "ftp_w")),
                        ("[rider]\nftp_w = \"vite\"\n", ("rider", "ftp_w")),
                        ("[render]\nquality = \"ultra\"\n", ("render", "quality")),
                        ("[ipc]\nport_state = 5005\nport_commands = 5005\n", ("ipc", "port_commands"))):
        cfg.write_text(text, encoding="utf-8")
        exc = load_error(cfg)
        assert (exc.section, exc.key, exc.path) == (*where, None)
    cfg.write_text("[rider\nftp_w = 250\n", encoding="utf-8")
    assert load_error(cfg).path == cfg


def test_reset_key_comments_the_line_and_keeps_a_copy(tmp_path):
    cfg = tmp_path / "config.toml"
    original = "# mes réglages\n[rider]\nftp_w = 5   # trop bas\nmass_kg = 70\n[bike]\nftp_w = 1\n"
    cfg.write_text(original, encoding="utf-8")
    assert config_repair.reset_key(cfg, "rider", "ftp_w", today=date(2026, 10, 31))
    text = cfg.read_text(encoding="utf-8")
    assert "# ftp_w = 5   # trop bas   # valeur invalide, remise par défaut le 31/10/2026" in text
    assert "mass_kg = 70" in text and "[bike]\nftp_w = 1" in text   # autre section intacte
    assert (tmp_path / "config.toml.bak").read_text(encoding="utf-8") == original
    assert config_mod.load(cfg, None).rider.ftp_w == config_mod.Config().rider.ftp_w
    assert not config_repair.reset_key(cfg, "rider", "absente")


def test_proposal_targets_the_file_that_holds_the_value(tmp_path):
    cfg, prof = tmp_path / "config.toml", tmp_path / "profil.toml"
    cfg.write_text("[render]\nquality = \"low\"\n", encoding="utf-8")
    prof.write_text("[profil]\nid = \"a\"\n\n[rider]\nftp_w = 9999\n", encoding="utf-8")
    fix = config_repair.proposal(load_error(cfg, prof), cfg, prof, None)
    assert fix is not None and "[rider] ftp_w" in fix.question and "profil.toml" in fix.question
    fix.apply()
    assert config_mod.load(cfg, prof).rider.ftp_w == config_mod.Config().rider.ftp_w
    assert "id = \"a\"" in prof.read_text(encoding="utf-8") and not (tmp_path / "config.toml.bak").exists()


def test_unreadable_files_start_again(tmp_path):
    template = tmp_path / "modele.toml"
    template.write_text(TEMPLATE_TEXT, encoding="utf-8")
    cfg, prof = tmp_path / "config.toml", tmp_path / "profil.toml"
    cfg.write_text("[rider\n", encoding="utf-8")
    config_repair.proposal(load_error(cfg, None), cfg, None, template).apply()
    assert cfg.read_text(encoding="utf-8") == TEMPLATE_TEXT and (tmp_path / "config.toml.bak").read_text() == "[rider\n"
    prof.write_text("[profil]\nid = \"a\"\nnom = \"A\"\n[rider]\nftp_w = = 2\n", encoding="utf-8")
    config_repair.proposal(load_error(cfg, prof), cfg, prof, template).apply()
    assert prof.read_text(encoding="utf-8") == "[profil]\nid = \"a\"\nnom = \"A\"\n"   # identité gardée


def test_cross_key_error_without_line_gives_no_proposal(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[gearing]\nratio_max = 0.5\n", encoding="utf-8")   # ratio_min (défaut) ≥ ratio_max
    exc = load_error(cfg, None)
    assert (exc.section, exc.key) == ("gearing", "ratio_min")
    assert config_repair.proposal(exc, cfg, None, None) is None   # rien à remettre : message seul


def test_launcher_repairs_after_yes_and_starts(home: Path, monkeypatch):
    runs = capture_run(monkeypatch)
    home.mkdir(parents=True)
    cfg = home / "config.toml"
    cfg.write_text("[rider]\nftp_w = 5\n[render]\nquality = \"ultra\"\n", encoding="utf-8")
    questions: list[str] = []
    assert launcher.main([], message=lambda t, e: None, ask=lambda q: questions.append(q) or True) == 0
    assert len(questions) == 2 and "[rider] ftp_w" in questions[0] and "[render] quality" in questions[1]
    assert len(runs) == 1 and (home / "config.toml.bak").is_file()


def test_launcher_refusal_keeps_the_file(home: Path, monkeypatch):
    capture_run(monkeypatch)
    home.mkdir(parents=True)
    cfg = home / "config.toml"
    cfg.write_text("[rider]\nftp_w = 5\n", encoding="utf-8")
    messages: list[tuple[str, bool]] = []
    assert launcher.main([], message=lambda t, e: messages.append((t, e)), ask=lambda q: False) == 1
    assert cfg.read_text(encoding="utf-8") == "[rider]\nftp_w = 5\n" and not (home / "config.toml.bak").exists()
    assert "configuration invalide" in messages[-1][0]
