"""Migration du joueur d'avant les profils vers `Profils/principal/` (série MJ, lot MJ5)."""

from __future__ import annotations

import json
import tarfile
from datetime import date, datetime
from pathlib import Path

import pytest

from openride_core import config as config_mod
from openride_core import launcher, profiles
from openride_core import migration_profils as mig
from test_progression import write_journal

LIVE_TS = 1_760_000_000.0
SIM_TS = 1_760_100_000.0
REPLAY_TS = 1_760_200_000.0
CONFIG = """# Configuration de test
[rider]
ftp_w = 250   # FTP d'essai
mass_kg = 70

[render]
quality = "medium"
camera = "side"
"""


def _fit_name(start_ts: float) -> str:
    return datetime.fromtimestamp(start_ts + 1).strftime("%Y-%m-%d_%H-%M") + "_demo.fit"


def make_home(root: Path) -> Path:
    """Dossier factice d'avant les profils : séances réelle, simulée, rejouée, FIT sans journal."""
    home = root / "OpenRide"
    jdir = home / "Activities" / ".journal"
    jdir.mkdir(parents=True)
    (home / "config.toml").write_text(CONFIG, encoding="utf-8")
    (home / "plan_state.toml").write_text('plan = "essai"\n', encoding="utf-8")
    write_journal(jdir / "2025-10-09_10-53-20.jsonl", minutes=30, start_ts=LIVE_TS)
    write_journal(jdir / "2025-10-10_14-40-00.jsonl", minutes=30, source="simulated", start_ts=SIM_TS)
    write_journal(jdir / "2025-10-11_18-26-40.jsonl", minutes=30, source="replay", start_ts=REPLAY_TS)
    for ts in (LIVE_TS, SIM_TS, REPLAY_TS):
        (home / "Activities" / _fit_name(ts)).write_bytes(b"FIT")
    (home / "Activities" / "2024-01-01_08-00_vieux.fit").write_bytes(b"FIT")   # sans journal
    old = {"version": 1, "routes": {
        "demo": {"s1": {"no_bonus": [{"time_s": 61.0, "date": "2025-10-09 10:53"}]}},
        "fantome": {"s1": {"no_bonus": [{"time_s": 99.0, "date": "2025-10-10 14:40"}]}},
    }}
    (home / "records.json").write_text(json.dumps(old), encoding="utf-8")
    return home


def run(home: Path, stop_after: str | None = None) -> str:
    caches = (home.parent / "cache" / "history.json", home.parent / "cache" / "mmp.json")
    return mig.Migration(home, date(2025, 10, 30), caches).run(stop_after)


def tree(home: Path) -> dict[str, bytes]:
    """Fichiers de `home` et leur contenu (la sauvegarde : son seul nom, l'archive change d'heure)."""
    out = {}
    for p in sorted(home.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(home))
            data = p.read_bytes().replace(str(home).encode(), b"<HOME>")   # instantanés : dossier absolu
            out[rel] = b"" if rel.startswith(mig.BACKUP_DIR) or rel.endswith(".bak") else data
    return out


def test_sessions_are_sorted_and_progression_is_kept(tmp_path):
    home = make_home(tmp_path)
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "history.json").write_text("{}", encoding="utf-8")
    assert run(home) == profiles.MIGRATION_DONE
    main, trial = home / "Profils" / "principal", home / "Profils" / "_essai"
    assert sorted(p.name for p in (main / "Activities" / ".journal").iterdir()) == ["2025-10-09_10-53-20.jsonl"]
    assert sorted(p.name for p in (trial / "Activities" / ".journal").iterdir()) == [
        "2025-10-10_14-40-00.jsonl", "2025-10-11_18-26-40.jsonl"]
    assert sorted(p.name for p in (main / "Activities").glob("*.fit")) == sorted(
        [_fit_name(LIVE_TS), "2024-01-01_08-00_vieux.fit"])
    assert sorted(p.name for p in (trial / "Activities").glob("*.fit")) == sorted(
        [_fit_name(SIM_TS), _fit_name(REPLAY_TS)])
    assert not (home / "Activities").exists()
    assert (main / "plan_state.toml").read_text(encoding="utf-8") == 'plan = "essai"\n'
    assert not (tmp_path / "cache" / "history.json").exists()
    # profil.toml : clés joueur ; config.toml : clés machine, commentaire à la place des autres
    desc = profiles.read_description(main, "principal")
    assert (desc["nom"], desc["type"], desc["seances_comptees"]) == ("Cycliste 1", "joueur", ["live"])
    text = (home / "config.toml").read_text(encoding="utf-8")
    assert "ftp_w = 250" not in text and "# ftp_w : passé dans Profils/principal/profil.toml" in text
    assert 'quality = "medium"' in text
    cfg = config_mod.load(home / "config.toml", main / "profil.toml")
    assert (cfg.rider.ftp_w, cfg.rider.mass_kg, cfg.render.camera, cfg.render.quality) == (250, 70, "side", "medium")
    # records : parcours introuvable gardé, parcours sans séance réelle retiré, ancien fichier parti
    book = json.loads((main / "records.json").read_text(encoding="utf-8"))
    assert list(book["routes"]) == ["demo"]
    assert not (home / "records.json").exists()
    # sauvegarde complète d'avant
    with tarfile.open(home / "Sauvegardes" / "avant_profils_20251030.tar.gz") as tar:
        names = tar.getnames()
    assert {"config.toml", "records.json", "plan_state.toml",
            "Activities/.journal/2025-10-10_14-40-00.jsonl"} <= set(names)
    assert profiles.default_id(home / "Profils") == "principal"


@pytest.mark.parametrize("step", mig.STEPS[:-1])
def test_cut_after_each_step_resumes_to_the_same_result(tmp_path, step):
    ref = make_home(tmp_path / "ref")
    run(ref)
    home = make_home(tmp_path / "cut")
    assert run(home, stop_after=step) == step
    assert run(home) == profiles.MIGRATION_DONE
    assert tree(home) == tree(ref)


def test_cut_in_the_middle_of_the_moves_resumes(tmp_path):
    ref = make_home(tmp_path / "ref")
    run(ref)
    home = make_home(tmp_path / "cut")
    run(home, stop_after="plan")
    moves = json.loads((home / "Profils" / ".migration_plan.json").read_text(encoding="utf-8"))
    for m in moves[: len(moves) // 2]:   # coupure de courant au milieu des renommages
        (home / m["to"]).parent.mkdir(parents=True, exist_ok=True)
        (home / m["from"]).replace(home / m["to"])
    assert run(home) == profiles.MIGRATION_DONE
    assert tree(home) == tree(ref)


def test_second_run_changes_nothing(tmp_path):
    home = make_home(tmp_path)
    run(home)
    before = tree(home)
    assert run(home) == profiles.MIGRATION_DONE
    assert not mig.needed(home)
    assert tree(home) == before


def test_progression_mismatch_puts_everything_back(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    original = tree(home)

    def mismatch(self):
        raise mig._Mismatch("XP : 120 → 0")

    monkeypatch.setattr(mig.Migration, "check", mismatch)
    assert run(home) == mig.CANCELLED
    after = {k: v for k, v in tree(home).items()
             if not k.startswith(("Profils", mig.BACKUP_DIR)) and not k.endswith(".bak")}
    assert after == original
    assert not (home / "Profils" / "principal").exists()
    assert "XP : 120 → 0" in (home / "Profils" / ".migration_ecart.txt").read_text(encoding="utf-8")
    assert not mig.needed(home) and profiles.default_id(home / "Profils") is None
    assert run(home) == mig.CANCELLED   # pas retentée seule


def test_existing_main_profile_is_refused_untouched(tmp_path):
    home = make_home(tmp_path)
    (home / "Profils" / "principal").mkdir(parents=True)
    (home / "Profils" / "principal" / "profil.toml").write_text("[profil]\n", encoding="utf-8")
    original = tree(home)
    with pytest.raises(mig.MigrationError, match="existe déjà"):
        run(home)
    assert tree(home) == original


def test_fresh_install_migrates_to_an_empty_main_profile(tmp_path):
    home = tmp_path / "OpenRide"
    home.mkdir()
    assert run(home) == profiles.MIGRATION_DONE
    assert profiles.read_description(home / "Profils" / "principal", "principal")["nom"] == "Cycliste 1"


def test_launcher_migrates_and_core_then_uses_the_main_profile(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    monkeypatch.setattr(config_mod, "OPENRIDE_HOME", home)
    monkeypatch.setattr(mig.Migration, "__init__", _init_with(mig.Migration.__init__, tmp_path))
    assert launcher.migrate_profiles() is None
    ctx = profiles.resolve(None, {})
    assert ctx is not None and ctx.id == "principal" and ctx.root == home / "Profils" / "principal"
    assert profiles.resolve(None, {profiles.ENV_VAR: "_essai"}).id == "_essai"   # demande explicite d'abord


def _init_with(init, tmp_path):
    def wrapped(self, home=None, today=None, legacy_caches=None):
        init(self, home, today, (tmp_path / "cache" / "h.json", tmp_path / "cache" / "m.json"))
    return wrapped


def test_launcher_reports_a_cancelled_migration(tmp_path, monkeypatch):
    home = make_home(tmp_path)
    monkeypatch.setattr(mig.Migration, "check", lambda self: (_ for _ in ()).throw(mig._Mismatch("écart")))
    monkeypatch.setattr(mig.Migration, "__init__", _init_with(mig.Migration.__init__, tmp_path))
    assert "annulée" in launcher.migrate_profiles(home)
    assert launcher.migrate_profiles(home) is None   # annulée une fois : plus de message ni d'essai
