"""Index des lots calculé à partir des cahiers (lot X54) : lecture, tri, nombres, migration des anciennes lignes."""

from pathlib import Path

import index_lots as il   # scripts/ est dans le chemin (conftest.py)


def _cahier(dir_: Path, name: str, cells: list[str] | None, corps: str = "## 1. Objectif\n\nTexte.\n") -> Path:
    bloc = "\n".join(il.lot_block(cells)) + "\n\n" if cells else ""
    path = dir_ / name
    path.write_text(f"# {name}\n\n{bloc}{corps}", encoding="utf-8")
    return path


def test_real_index_is_complete():
    lots, errors = il.read_lots()
    assert errors == []
    assert il.check() == []
    assert il.main(["--verifier"]) == 0
    files = sorted(p.name for p in il.LOTS_DIR.glob("LOT_*.md"))
    assert sorted(lot.filename for lot in lots) == files
    assert il.old_rows((il.LOTS_DIR / il.INDEX_NAME).read_text(encoding="utf-8")) == []


def test_sort_series_then_number():
    ids = ["X10", "A2", "AS1", "X9", "A", "V3b", "V3", "B1"]
    assert sorted(ids, key=il.sort_key) == ["A", "A2", "AS1", "B1", "V3", "V3b", "X9", "X10"]


def test_table_and_stats(tmp_path: Path, capsys):
    _cahier(tmp_path, "LOT_X10_b.md", ["Outil B", "Python", "X9", "Petite", "Prêt"])
    _cahier(tmp_path, "LOT_X9_a.md", ["Outil A \\| bis", "Python", "—", "Petite", "**Livré le 30 octobre** (PR #1)"])
    _cahier(tmp_path, "LOT_A_c.md", ["Route", "Python", "—", "Moyenne", "Livré le 23 octobre"])
    (tmp_path / il.INDEX_NAME).write_text("# Index\n", encoding="utf-8")
    lots, errors = il.read_lots(tmp_path)
    assert errors == [] and [lot.lot_id for lot in lots] == ["A", "X9", "X10"]
    table = il.table_markdown(lots)
    assert table.splitlines()[0] == "| Lot | Titre | Langage | Dépend de | Taille | Statut |"
    assert "| [X9](LOT_X9_a.md) | Outil A \\| bis | Python | — | Petite | **Livré le 30 octobre** (PR #1) |" in table
    assert il.stats(lots) == [("A", 1, 1), ("X", 2, 1)]
    assert "| **Total** | **3** | **2** |" in il.stats_markdown(lots)

    resume = tmp_path / "resume.md"
    assert il.main(["--resume", str(resume)], lots_dir=tmp_path) == 0
    assert resume.read_text(encoding="utf-8").startswith("### Lots par série\n")
    assert capsys.readouterr().out == ""                    # --resume seul n'affiche rien


def test_missing_or_bad_line_is_reported(tmp_path: Path):
    _cahier(tmp_path, "LOT_X1_sans.md", None)
    _cahier(tmp_path, "LOT_X2_court.md", ["Titre", "Python", "—", "Petite", "Prêt"])
    court = tmp_path / "LOT_X2_court.md"
    court.write_text(court.read_text(encoding="utf-8").replace("| Petite | Prêt |", "| Petite |"), encoding="utf-8")
    (tmp_path / il.INDEX_NAME).write_text("# Index\n", encoding="utf-8")
    errors = il.check(tmp_path)
    assert any("LOT_X1_sans.md" in e and "pas de ligne d'index" in e for e in errors)
    assert any("LOT_X2_court.md" in e and "5 cellules" in e for e in errors)
    assert il.main(["--verifier"], lots_dir=tmp_path) == 1


INTRO_BASE = "# Index\n\n## 1. Liste des lots\n\n"
INTRO_MAIN = "# Index\n\n## 1. Liste des lots\n\nLe tableau se calcule (lot X54).\n\n"
ROW_O24 = "| [O24](LOT_O24_neuf.md) | Appareils | GDScript | O4 | Petite | Prêt |\n"
ROW_X32_OLD = "| [X32](LOT_X32_ancien.md) | Garde-fou | Python | — | Petite | Prêt |\n"
ROW_X32_LIVRE = "| [X32](LOT_X32_ancien.md) | Garde-fou | Python | — | Petite | **Livré le 31 octobre** |\n"
ROW_X11_OLD = "| [X11](LOT_X11_vieux.md) | FIT | Python | — | Petite | Oui |\n"


def _old_branch(tmp_path: Path) -> tuple[str, str]:
    """Cahiers de main (X11 livré depuis), index de base d'avant X54 et index de main."""
    _cahier(tmp_path, "LOT_O24_neuf.md", None)
    _cahier(tmp_path, "LOT_X32_ancien.md", ["Garde-fou", "Python", "—", "Petite", "Prêt"])
    _cahier(tmp_path, "LOT_X11_vieux.md", ["FIT", "Python", "—", "Petite", "**Livré le 28 octobre**"])
    base = INTRO_BASE + ROW_X11_OLD + ROW_X32_OLD + "\n## 2. Règles\n"
    main = INTRO_MAIN + "\n## 2. Règles\n"
    return base, main


def test_migrate_moves_only_rows_changed_by_the_branch(tmp_path: Path):
    """Fusion de main dans une PR d'avant X54 : seules ses lignes vont dans les cahiers (retour du fil AS2)."""
    base, main = _old_branch(tmp_path)
    branch = INTRO_BASE + ROW_X11_OLD + ROW_O24 + ROW_X32_LIVRE + "\n## 2. Règles\n\nRègle de la branche.\n"
    (tmp_path / il.INDEX_NAME).write_text(branch, encoding="utf-8")
    assert il.migrate(tmp_path, base, main) == []

    index = (tmp_path / il.INDEX_NAME).read_text(encoding="utf-8")
    assert il.old_rows(index) == []
    assert "Le tableau se calcule (lot X54)." in index          # introduction de main gardée
    assert "Règle de la branche." in index                       # texte de la branche gardé
    neuf = tmp_path / "LOT_O24_neuf.md"
    assert neuf.read_text(encoding="utf-8").startswith("# LOT_O24_neuf.md\n\n" + il.MARKER + "\n")
    assert il.parse_lot(neuf)[0].cells == ("Appareils", "GDScript", "O4", "Petite", "Prêt")
    ancien = tmp_path / "LOT_X32_ancien.md"
    assert il.parse_lot(ancien)[0].delivered and ancien.read_text(encoding="utf-8").count(il.MARKER) == 1
    # X11 : ancienne copie de main dans la branche, le cahier de main (livré) n'est pas écrasé
    assert il.parse_lot(tmp_path / "LOT_X11_vieux.md")[0].status == "**Livré le 28 octobre**"


def test_migrate_is_all_or_nothing(tmp_path: Path):
    base, main = _old_branch(tmp_path)
    absent = "| [Q9](LOT_Q9_absent.md) | Absent | Python | — | Petite | Prêt |\n"
    branch = INTRO_BASE + ROW_O24 + absent + "\n## 2. Règles\n"
    (tmp_path / il.INDEX_NAME).write_text(branch, encoding="utf-8")
    errors = il.migrate(tmp_path, base, main)
    assert len(errors) == 1 and "LOT_Q9_absent.md" in errors[0]
    assert (tmp_path / il.INDEX_NAME).read_text(encoding="utf-8") == branch
    assert il.MARKER not in (tmp_path / "LOT_O24_neuf.md").read_text(encoding="utf-8")

    (tmp_path / il.INDEX_NAME).write_text("<<<<<<< HEAD\n" + ROW_O24 + "=======\n>>>>>>> origin/main\n",
                                          encoding="utf-8")
    assert "git checkout --ours" in il.migrate(tmp_path, base, main)[0]


def test_duplicate_id_is_reported(tmp_path: Path):
    _cahier(tmp_path, "LOT_X1_a.md", ["A", "Python", "—", "Petite", "Prêt"])
    _cahier(tmp_path, "LOT_X1_b.md", ["B", "Python", "—", "Petite", "Prêt"])
    _, errors = il.read_lots(tmp_path)
    assert errors == ["docs/lots/LOT_X1_b.md : lot X1 déjà décrit par LOT_X1_a.md"]
