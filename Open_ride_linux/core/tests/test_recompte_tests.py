"""Compte des tests du projet (lots X34 et X52) : comptes de l'engine, nombres écrits en dur, résumé de la CI."""

from pathlib import Path

import recompte_tests as rt   # scripts/ est dans le chemin (conftest.py)

README = ("**Tests :** 12 tests automatiques côté core (dont x) et 34 côté compilateur ; côté Godot, sans écran, "
          "5 fichiers de tests unitaires lancés par découverte, 2 tests de rendu, les couches OSM")
SUIVI = ("**12 tests pytest passent dans le core et 34 dans le compilateur** (…). Côté Godot : 5 fichiers de tests "
         "unitaires lancés par découverte (…), 2 tests de rendu (`engine/tests/render/`)")


def test_hard_counts_are_reported_in_both_wordings():
    for name, text in (("README.md", README), ("docs/SUIVI_AVANCEMENT.md", SUIVI)):
        errs = rt.hard_counts(text, name)
        assert len(errs) == 4, errs
        assert all(e.startswith(name + " : « ") and "recompte_tests.py" in e for e in errs)
    assert rt.hard_counts("des tests automatiques côté core et côté compilateur, des tests de rendu", "README.md") == []


def test_real_documents_write_no_count():
    for name in rt.DOCUMENTS:
        assert rt.hard_counts((rt.PROJECT / name).read_text(encoding="utf-8"), name) == []
    assert rt.main(["--verifier"]) == 0


def test_summary_table(tmp_path: Path):
    md = rt.summary_markdown({"core": 13, "engine_unit": 6})
    assert md.startswith("### Nombre de tests\n")
    assert "| tests core | 13 |\n" in md and "| fichiers de tests unitaires de l'engine | 6 |\n" in md


def test_engine_counts_read_the_test_folders(tmp_path: Path):
    unit = tmp_path / "engine" / "tests" / "unit"
    render = tmp_path / "engine" / "tests" / "render"
    unit.mkdir(parents=True)
    render.mkdir(parents=True)
    for n in ("test_a.gd", "test_b.gd", "outil.gd"):
        (unit / n).write_text("", encoding="utf-8")
    (render / "test_c.gd").write_text("", encoding="utf-8")
    assert rt.engine_counts(tmp_path) == {"engine_unit": 2, "engine_render": 1}
