"""Lot NI2 : réglages retirés du menu remis par défaut dans les fichiers du joueur (migration_reglages.py)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from openride_core import config as config_mod
from openride_core import launcher, migration_reglages, settings

CONFIG = """# ma configuration
[render]
quality = "medium"     # préréglage
texture_level = "low"  # choisi au menu avant le lot NI2

[rider]
ftp_w = 250

[bots]
level_pct = 50         # choisi au menu avant le lot NI3
objective = "endurance"
"""


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "OpenRide"
    (home / "Profils" / "principal").mkdir(parents=True)
    (home / "config.toml").write_text(CONFIG, encoding="utf-8")
    (home / "Profils" / "principal" / "profil.toml").write_text('[profil]\nnom = "Essai"\n\n[render]\ntexture_level = "high"\n',
                                                             encoding="utf-8")
    (home / "Profils" / "second").mkdir()
    (home / "Profils" / "second" / "profil.toml").write_text('[profil]\nnom = "Autre"\n', encoding="utf-8")
    return home


def test_retired_keys_are_not_in_the_menu_and_still_known_to_config():
    for section, key, _ in migration_reglages.RETIRED:
        assert f"{section}.{key}" not in settings.KEYS
        assert hasattr(getattr(config_mod.Config(), section), key) or (section, key) in config_mod.RETIRED_KEYS


def test_retired_draft_gauge_lot_ni1(tmp_path: Path):
    """Lot NI1 : la jauge d'abri est retirée du jeu ; même règle que les réglages retirés du menu."""
    home = tmp_path / "OpenRide"
    home.mkdir()
    (home / "config.toml").write_text('[render]\nquality = "low"\ndraft_gauge = "on"\n', encoding="utf-8")
    done = migration_reglages.migrate(home, date(2026, 11, 22))
    assert len(done) == 1 and "render.draft_gauge" in done[0]
    text = (home / "config.toml").read_text(encoding="utf-8")
    assert '# draft_gauge = "on"   # jauge d\'abri retirée (lot NI1)' in text and 'quality = "low"' in text
    assert config_mod.load(home / "config.toml", None).render.quality == "low"


def test_migration_comments_the_retired_lines_once_and_keeps_the_rest(tmp_path: Path):
    home = _home(tmp_path)
    done = migration_reglages.migrate(home, date(2026, 11, 21))
    assert len(done) == 2 and "render.texture_level" in done[0] and "bots.level_pct" in done[0]
    text = (home / "config.toml").read_text(encoding="utf-8")
    assert '# texture_level = "low"  # choisi au menu avant le lot NI2   # réglage retiré du menu (lot NI2)' in text
    assert "le 21/11/2026" in text and 'quality = "medium"     # préréglage' in text and "# ma configuration" in text
    assert (home / "config.toml.bak").read_text(encoding="utf-8") == CONFIG
    cfg = config_mod.load(home / "config.toml", None)
    assert cfg.render.texture_level == "auto" and cfg.render.quality == "medium" and cfg.rider.ftp_w == 250
    # Lot NI3 : niveau des bots remis à 100 %, l'objectif (Intensité du jour) gardé
    assert '# level_pct = 50' in text and cfg.bots.level_pct == 100 and cfg.bots.objective == "endurance"
    profil = (home / "Profils" / "principal" / "profil.toml").read_text(encoding="utf-8")
    assert '# texture_level = "high"' in profil and 'nom = "Essai"' in profil
    assert not (home / "Profils" / "second" / "profil.toml.bak").exists()   # rien à changer : pas de copie
    # Deuxième lancement : rien à faire, fichiers inchangés
    assert migration_reglages.migrate(home) == []
    assert (home / "config.toml").read_text(encoding="utf-8") == text


def test_launcher_runs_the_migration(tmp_path: Path, capsys):
    home = _home(tmp_path)
    assert len(launcher.migrate_settings(home)) == 2
    assert "retiré du menu" in capsys.readouterr().out
    assert launcher.migrate_settings(tmp_path / "absent") == []


def test_lot_ni4_living_off_is_put_back_on(tmp_path: Path):
    """Lot NI4 (R10) : « Décor vivant : non » retiré du menu ; un `living = false` choisi avant est mis en
    commentaire, le décor vivant repart (son coût suit la Qualité graphique)."""
    home = tmp_path / "OpenRide"
    home.mkdir()
    (home / "config.toml").write_text('[render]\nquality = "low"\nliving = false\n', encoding="utf-8")
    done = migration_reglages.migrate(home, date(2026, 11, 21))
    assert len(done) == 1 and "render.living" in done[0]
    text = (home / "config.toml").read_text(encoding="utf-8")
    assert "# living = false   # réglage retiré du menu (lot NI4)" in text
    cfg = config_mod.load(home / "config.toml", None)
    assert cfg.render.living is True and cfg.render.quality == "low"
