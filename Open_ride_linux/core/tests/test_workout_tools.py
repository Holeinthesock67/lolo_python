"""Tests des outils et de la bibliothèque d'entraînements ERG (Lot H8, SRS §6)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from openride_core.tools.workouts import BUILTIN_WORKOUTS_DIR, main as workouts_main
from openride_core.workout import load_workout

from test_workout import REFERENCE_ZWO

EXPECTED_DURATIONS_S: dict[str, float] = {
    # §4.2 : 10 min échauffement + 45 min à 65 % + 5 min retour au calme = 60 min (3 600 s)
    "endurance_60": 10 * 60 + 45 * 60 + 5 * 60,
    # §4.2 : 10 min échauffement + 3 × (10 min à 90 % + 5 min récup) + 5 min retour au calme = 3 600 s
    "sweet_spot_3x10": 10 * 60 + 3 * (10 * 60 + 5 * 60) + 5 * 60,
    # §4.2 : 10 min échauffement + 2 × (20 min à 97 % + 5 min récup) + 5 min retour au calme = 3 900 s
    "seuil_2x20": 10 * 60 + 2 * (20 * 60 + 5 * 60) + 5 * 60,
    # §4.2 : 10 min échauffement + 5 × (3 min à 115 % + 3 min à 50 %) + 5 min retour au calme = 2 700 s
    "vo2_5x3": 10 * 60 + 5 * (3 * 60 + 3 * 60) + 5 * 60,
    # §4.2 : 5 min à 40 %, puis 19 paliers de 1 min de 40 % à 148 % par pas de +6 % = 1 440 s
    "rampe_test": 5 * 60 + 19 * 60,
}


def test_builtin_library_loads_without_warning_and_matches_durations(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Critère 2 : les 5 fichiers se chargent sans avertissement et avec les durées attendues."""
    files = sorted(BUILTIN_WORKOUTS_DIR.glob("*.zwo"))
    assert [f.stem for f in files] == sorted(EXPECTED_DURATIONS_S.keys())

    with caplog.at_level(logging.WARNING, logger="workout"):
        for path in files:
            w = load_workout(path)
            assert w.duration_s == pytest.approx(EXPECTED_DURATIONS_S[path.stem])

    assert caplog.records == []
    assert EXPECTED_DURATIONS_S["endurance_60"] == 3600.0


def test_check_reference_zwo_and_invalid_zwo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Critère 3 : check sur REFERENCE_ZWO (FTP 250 W) affiche 10 blocs et 2 580 s ; code 1 sur invalide."""
    ref_path = tmp_path / "reference.zwo"
    ref_path.write_text(REFERENCE_ZWO, encoding="utf-8")

    rc = workouts_main(["check", str(ref_path), "--ftp", "250"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "10 blocs" in out
    assert "2580 s" in out
    assert "FTP 250 W" in out
    assert "NP " in out and "IF " in out and "TSS " in out

    bad_path = tmp_path / "invalide.zwo"
    bad_path.write_text("<workout_file><workout></workout></workout_file>", encoding="utf-8")
    rc_bad = workouts_main(["check", str(bad_path)])
    assert rc_bad == 1
    err = capsys.readouterr().err
    assert "invalide.zwo" in err


@pytest.mark.parametrize("ftp", ["0", "-100", "nan", "inf"])
def test_check_rejects_invalid_ftp(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    ftp: str,
) -> None:
    """Une FTP nulle, négative ou non finie est refusée, comme par `summary` (vérification du 24 octobre, R2)."""
    ref_path = tmp_path / "reference.zwo"
    ref_path.write_text(REFERENCE_ZWO, encoding="utf-8")
    assert workouts_main(["check", str(ref_path), "--ftp", ftp]) == 1
    captured = capsys.readouterr()
    assert "FTP invalide" in captured.err
    assert captured.out == ""


def test_install_copies_five_files_and_does_not_overwrite(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Critère 4 : install copie les 5 fichiers ; une seconde exécution n'écrase rien."""
    rc1 = workouts_main(["install", "--dir", str(tmp_path)])
    assert rc1 == 0
    out1 = capsys.readouterr().out
    assert "5 copié(s)" in out1

    installed = sorted(tmp_path.glob("*.zwo"))
    assert len(installed) == 5

    # Modifie un fichier existant pour vérifier qu'il n'est pas écrasé au second appel
    sentinel = "<!-- modification utilisateur -->\n"
    custom_file = tmp_path / "endurance_60.zwo"
    original_content = custom_file.read_text(encoding="utf-8")
    custom_file.write_text(sentinel + original_content, encoding="utf-8")

    rc2 = workouts_main(["install", "--dir", str(tmp_path)])
    assert rc2 == 0
    out2 = capsys.readouterr().out
    assert "0 copié(s)" in out2
    assert "5 conservé(s)" in out2
    assert custom_file.read_text(encoding="utf-8").startswith(sentinel)


def test_list_displays_valid_and_invalid_workouts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Critère 5 : list sur un dossier contenant un fichier invalide l'affiche avec son erreur."""
    workouts_main(["install", "--dir", str(tmp_path)])
    capsys.readouterr()

    broken = tmp_path / "casse.zwo"
    broken.write_text("<workout_file><workout><SteadyState Duration='-10' Power='0.5'/></workout></workout_file>", encoding="utf-8")

    rc = workouts_main(["list", "--dir", str(tmp_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "endurance_60" in out
    assert "ok" in out
    assert "casse" in out
    assert "erreur :" in out
