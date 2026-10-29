"""Recompte des tests annoncés dans la documentation (lot X34) : correction, idempotence, comptes de l'engine."""

import re
from pathlib import Path

import recompte_tests as rt   # scripts/ est dans le chemin (conftest.py)

README = ("**Tests :** 12 tests automatiques côté core (dont x) et 34 côté compilateur ; côté Godot, sans écran, "
          "5 fichiers de tests unitaires lancés par découverte, 2 tests de rendu, les couches OSM")
SUIVI = ("**12 tests pytest passent dans le core et 34 dans le compilateur** (…). Côté Godot : 5 fichiers de tests "
         "unitaires lancés par découverte (…), 2 tests de rendu (`engine/tests/render/`)")


def test_fix_rewrites_every_wrong_number_and_is_idempotent():
    actual = {"core": 13, "compiler": 34, "engine_unit": 6, "engine_render": 2}
    for name, text in (("README.md", README), ("docs/SUIVI_AVANCEMENT.md", SUIVI)):
        assert len(rt.check_test_counts(text, name, actual)) == 2
        fixed = rt.fix_test_counts(text, name, actual)
        assert rt.check_test_counts(fixed, name, actual) == []
        assert rt.fix_test_counts(fixed, name, actual) == fixed
        assert "13 tests" in fixed and "6 fichiers de tests" in fixed and "34" in fixed


def test_counts_missing_from_actual_are_left_alone():
    fixed = rt.fix_test_counts(README, "README.md", {"core": 99})
    assert fixed.startswith("**Tests :** 99 tests") and "34 côté compilateur" in fixed
    assert rt.check_test_counts(README, "README.md", {"core": 12}) == []


def test_missing_sentence_is_reported():
    errs = rt.check_test_counts("rien ici", "README.md", {"core": 1})
    assert errs == ["README.md : phrase du nombre de tests core absente (" + rt.TEST_COUNT_PATTERNS["README.md"]["core"] + ")"]


def test_engine_counts_read_the_test_folders(tmp_path: Path):
    unit = tmp_path / "engine" / "tests" / "unit"
    render = tmp_path / "engine" / "tests" / "render"
    unit.mkdir(parents=True)
    render.mkdir(parents=True)
    for n in ("test_a.gd", "test_b.gd", "outil.gd"):
        (unit / n).write_text("", encoding="utf-8")
    (render / "test_c.gd").write_text("", encoding="utf-8")
    assert rt.engine_counts(tmp_path) == {"engine_unit": 2, "engine_render": 1}


def test_real_documents_have_every_sentence():
    for name, patterns in rt.TEST_COUNT_PATTERNS.items():
        text = (rt.PROJECT / name).read_text(encoding="utf-8")
        missing = [k for k, pattern in patterns.items() if re.search(pattern, text) is None]
        assert missing == [], f"{name} : phrases absentes {missing}"
