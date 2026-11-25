"""Rappel de la manche de la ligue d'hiver (série CH, lot CH7) : texte écrit le samedi et le dimanche seulement,
manche faite, saison en pause ou close : rien ; fichier jamais touché ; minuteur samedi 18 h et dimanche midi."""

import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

from openride_core import league, league_reminder as rem

MON = date(2026, 11, 23)
ME = league.ME
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _places(season):
    keys = [ME] + [r.key for r in season.rivals]
    return {k: n for n, k in enumerate(keys, 1)}


def test_text_on_saturday_and_sunday_only():
    s = league.new_season(MON, seed=3)
    sat, sun = MON + timedelta(days=5), MON + timedelta(days=6)
    assert rem.due_text(s, sat) == "Manche 1 sur 8 (Course en tours) à courir avant demain soir. Elle compte au bilan."
    assert "avant ce soir, dernier jour" in rem.due_text(s, sun)
    for d in range(5):   # lundi à vendredi, et le lundi d'un minuteur rattrapé : rien
        assert rem.due_text(s, MON + timedelta(days=d)) is None
    assert rem.due_text(s, MON + timedelta(days=7)) is None
    week2 = rem.due_text(s, sat + timedelta(weeks=1))
    assert week2.startswith("Manche 2 sur 8 (Dernier survivant)")


def test_nothing_when_done_paused_closed_or_missing():
    sat = MON + timedelta(days=5)
    assert rem.due_text(None, sat) is None
    s = league.new_season(MON, seed=3)
    s.record(0, _places(s), MON + timedelta(days=2))
    assert rem.due_text(s, sat) is None   # manche faite
    p = league.new_season(MON, seed=3)
    p.pause(MON + timedelta(days=1))
    assert rem.due_text(p, sat) is None
    c = league.new_season(MON, seed=3)
    c.closed = "fin"
    assert rem.due_text(c, sat) is None


def test_main_reads_the_profile_file_without_touching_it(tmp_path, monkeypatch, capsys):
    path = tmp_path / league.FILE_NAME
    monkeypatch.setattr(rem, "league_path", lambda profile_id=None: path)
    sent = []
    monkeypatch.setattr(rem, "notify", lambda text: sent.append(text) or True)
    assert rem.main(["--jour", "2026-11-28"]) == 0 and sent == []   # pas de saison
    league.save(path, league.new_season(MON, seed=3))
    before = path.read_bytes()
    assert rem.main(["--jour", "2026-11-28", "--essai"]) == 0 and sent == []
    assert "Manche 1 sur 8" in capsys.readouterr().out
    assert rem.main(["--jour", "2026-11-28"]) == 0 and len(sent) == 1
    assert path.read_bytes() == before
    path.write_text("{abîmé", encoding="utf-8")   # fichier en cours d'écriture : pas de rappel, rien de déplacé
    assert rem.main(["--jour", "2026-11-28"]) == 0 and len(sent) == 1
    assert path.is_file() and not path.with_name(path.name + ".abime").exists()
    assert rem.main(["--jour", "pas une date"]) == 2


def test_league_path_follows_the_profile(tmp_path, monkeypatch):
    from openride_core import profiles

    monkeypatch.setattr(profiles, "profiles_dir", lambda: tmp_path / "Profils")
    assert rem.league_path("principal") == tmp_path / "Profils" / "principal" / league.FILE_NAME


def test_notify_without_tool_is_quiet(monkeypatch):
    monkeypatch.setattr(rem.shutil, "which", lambda name: None)
    assert rem.notify("x") is False


def test_timer_units_and_install_script():
    timer = (SCRIPTS / "systemd" / "openride-rappel-ligue.timer").read_text(encoding="utf-8")
    assert "OnCalendar=Sat *-*-* 18:00:00" in timer and "OnCalendar=Sun *-*-* 12:00:00" in timer
    assert "Persistent=true" in timer
    service = (SCRIPTS / "systemd" / "openride-rappel-ligue.service.in").read_text(encoding="utf-8")
    assert "ExecStart=@PYTHON@ -m openride_core.league_reminder" in service
    script = SCRIPTS / "install-rappel-ligue.sh"
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0
    out = subprocess.run(["bash", str(script), "--help"], capture_output=True, text=True)
    assert out.returncode == 0 and "--uninstall" in out.stdout
