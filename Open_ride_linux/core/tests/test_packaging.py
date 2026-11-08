"""Paquet installable hors du dépôt (lot J4) : copies embarquées et essai par la roue.

- `data/workouts/` et `data/plans/` sont des copies, identiques octet pour octet, de `core/workouts/`
  et `core/plans/` (les références : bibliothèque d'entraînements et plans de départ) ;
- test `slow` : la roue construite sans réseau, installée dans un environnement neuf, donne un
  `workouts install` et un `plan install` qui copient toute la bibliothèque depuis un dossier hors
  du dépôt.
"""

from __future__ import annotations

import filecmp
from pathlib import Path

import pytest

import essai_roue  # scripts/ (chemin posé par conftest.py)
from openride_core import plans, workout
from openride_core.tools import workouts as workouts_tool

CORE_DIR = Path(__file__).resolve().parents[1]
ROOT = CORE_DIR.parent
DATA_DIR = CORE_DIR / "src" / "openride_core" / "data"

# copie embarquée -> référence
COPIES = {
    DATA_DIR / "workouts": CORE_DIR / "workouts",
    DATA_DIR / "plans": CORE_DIR / "plans",
}


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


@pytest.mark.parametrize("copie", sorted(COPIES), ids=lambda p: p.name)
def test_copie_embarquee_identique_a_sa_reference(copie: Path) -> None:
    reference = COPIES[copie]
    cmp = filecmp.dircmp(reference, copie, ignore=["__pycache__"])
    ecarts = cmp.left_only + cmp.right_only + filecmp.cmpfiles(reference, copie, cmp.common_files,
                                                                 shallow=False)[1] + cmp.common_dirs
    assert not ecarts, (
        f"{_rel(copie)}/ diffère de sa référence {_rel(reference)}/ ({', '.join(sorted(ecarts))}). "
        f"Recopier depuis Open_ride_linux/ : rm -f {_rel(copie)}/* && cp {_rel(reference)}/* {_rel(copie)}/"
    )


def test_le_code_lit_les_copies_embarquees() -> None:
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
    attendus = sorted(p.name for p in (CORE_DIR / "workouts").iterdir() if p.suffix in workout.WORKOUT_SUFFIXES)
    assert sorted(p.name for p in cible.iterdir()) == attendus

    res = essai_roue.lancer(bin_dir, ["python", "-c",
                                      "from pathlib import Path; from openride_core import plans; "
                                      "print(plans.install_builtin(Path('Plans'), Path('W'))[0])"], cwd=dehors)
    assert res.returncode == 0, res.stderr
    assert sorted(p.name for p in (dehors / "Plans").iterdir()) == sorted(p.name for p in (CORE_DIR / "plans").iterdir())
