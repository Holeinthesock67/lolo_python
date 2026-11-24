"""Paquet installable hors du dépôt (lot J4) : données rangées dans le paquet et essai par la roue.

- `data/workouts/` et `data/plans/` du paquet sont le seul exemplaire des entraînements et des plans de
  référence (les copies `core/workouts/` et `core/plans/` sont retirées depuis l'audit du 22/11, C12) ;
- test `slow` : la roue construite sans réseau, installée dans un environnement neuf, donne un
  `workouts install` et un `plan install` qui copient toute la bibliothèque depuis un dossier hors
  du dépôt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import essai_roue  # scripts/ (chemin posé par conftest.py)
from openride_core import plans, workout
from openride_core.tools import workouts as workouts_tool

CORE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = CORE_DIR / "src" / "openride_core" / "data"


def test_un_seul_exemplaire_des_donnees_livrees() -> None:
    for old in ("workouts", "plans"):
        assert not (CORE_DIR / old).exists(), (
            f"core/{old}/ est revenu : les données livrées sont dans core/src/openride_core/data/{old}/ seulement")


def test_le_code_lit_les_donnees_du_paquet() -> None:
    assert workout.BUILTIN_WORKOUTS_DIR == DATA_DIR / "workouts"
    assert plans.BUILTIN_WORKOUTS_DIR is workout.BUILTIN_WORKOUTS_DIR
    assert workouts_tool.BUILTIN_WORKOUTS_DIR is workout.BUILTIN_WORKOUTS_DIR
    assert plans.BUILTIN_PLANS_DIR == DATA_DIR / "plans"


@pytest.mark.slow
def test_roue_installee_hors_du_depot(tmp_path: Path) -> None:
    pytest.importorskip("setuptools", reason="construction sans réseau : `pip install \"setuptools>=68\"` dans le venv")
    bin_dir = essai_roue.construire_et_installer(CORE_DIR, tmp_path / "roue")
    dehors = tmp_path / "dehors"
    dehors.mkdir()

    res = essai_roue.lancer(bin_dir, ["python", "-c", "import openride_core; print(openride_core.__file__)"],
                            cwd=dehors)
    assert res.returncode == 0, res.stderr
    assert Path(res.stdout.strip()).is_relative_to(tmp_path / "roue" / "venv"), res.stdout

    cible = dehors / "Workouts"
    res = essai_roue.lancer(bin_dir, ["python", "-m", "openride_core.tools.workouts", "install",
                                      "--dir", str(cible)], cwd=dehors)
    assert res.returncode == 0, res.stdout + res.stderr
    attendus = sorted(p.name for p in (DATA_DIR / "workouts").iterdir() if p.suffix in workout.WORKOUT_SUFFIXES)
    assert sorted(p.name for p in cible.iterdir()) == attendus

    res = essai_roue.lancer(bin_dir, ["python", "-c",
                                      "from pathlib import Path; from openride_core import plans; "
                                      "print(plans.install_builtin(Path('Plans'), Path('W'))[0])"], cwd=dehors)
    assert res.returncode == 0, res.stderr
    assert sorted(p.name for p in (dehors / "Plans").iterdir()) == sorted(p.name for p in (DATA_DIR / "plans").iterdir())
