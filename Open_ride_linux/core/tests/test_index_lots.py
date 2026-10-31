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


def test_migrate_moves_rows_left_by_an_old_pr(tmp_path: Path):
    """Rebase d'une PR d'avant X54 : ses lignes restées dans 00_INDEX.md vont dans les cahiers."""
    neuf = _cahier(tmp_path, "LOT_O24_neuf.md", None)
    ancien = _cahier(tmp_path, "LOT_X32_ancien.md", ["Garde-fou", "Python", "—", "Petite", "Prêt"])
    (tmp_path / il.INDEX_NAME).write_text(
        "# Index\n\n## 1. Liste des lots\n\n"
        "| [O24](LOT_O24_neuf.md) | Appareils | GDScript | O4 | Petite | Prêt |\n"
        "| [X32](LOT_X32_ancien.md) | Garde-fou | Python | — | Petite | **Livré le 31 octobre** |\n"
        "| [Q9](LOT_Q9_absent.md) | Absent | Python | — | Petite | Prêt |\n"
        "\n## 2. Règles\n", encoding="utf-8")
    errors = il.migrate(tmp_path)
    assert len(errors) == 1 and "LOT_Q9_absent.md" in errors[0]
    index = (tmp_path / il.INDEX_NAME).read_text(encoding="utf-8")
    assert "LOT_O24" not in index and "LOT_X32" not in index and "LOT_Q9_absent.md" in index
    assert "## 2. Règles" in index

    text = neuf.read_text(encoding="utf-8")
    assert text.startswith("# LOT_O24_neuf.md\n\n" + il.MARKER + "\n")   # sous le titre
    assert il.parse_lot(neuf)[0].cells == ("Appareils", "GDScript", "O4", "Petite", "Prêt")
    lot = il.parse_lot(ancien)[0]
    assert lot.delivered and ancien.read_text(encoding="utf-8").count(il.MARKER) == 1   # remplacée, pas doublée


def test_duplicate_id_is_reported(tmp_path: Path):
    _cahier(tmp_path, "LOT_X1_a.md", ["A", "Python", "—", "Petite", "Prêt"])
    _cahier(tmp_path, "LOT_X1_b.md", ["B", "Python", "—", "Petite", "Prêt"])
    _, errors = il.read_lots(tmp_path)
    assert errors == ["docs/lots/LOT_X1_b.md : lot X1 déjà décrit par LOT_X1_a.md"]
