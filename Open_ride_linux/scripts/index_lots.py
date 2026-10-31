#!/usr/bin/env python3
"""Index des lots calculé à partir des cahiers (lot X54).

Jusqu'au 31 octobre, `docs/lots/00_INDEX.md` contenait le tableau de tous les lots. Chaque PR y ajoutait
ou y modifiait sa ligne, presque toujours en fin de série : deux PR ouvertes en même temps entraient en
conflit à chaque fusion (#629, #635, #643, #644). Depuis le lot X54, la ligne d'un lot est écrite dans son
propre cahier, juste sous le titre, et le tableau complet se calcule ici :

    python3 scripts/index_lots.py                         # tableau Markdown de tous les lots
    python3 scripts/index_lots.py --sortie index.md       # le même tableau dans un fichier
    python3 scripts/index_lots.py --stats                 # nombre de lots et de lots livrés par série
    python3 scripts/index_lots.py --resume fichier.md     # ajoute ces nombres en Markdown (résumé de la CI)
    python3 scripts/index_lots.py --verifier              # code 1 si un cahier n'a pas de ligne valide
    python3 scripts/index_lots.py --migrer                # fusion de main dans une PR d'avant X54 (voir migrate)

Ligne d'un lot, dans `docs/lots/LOT_<id>_<sujet>.md`, sous le titre `# …` :

    <!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
    | Titre | Langage | Dépend de | Taille | Statut |
    | --- | --- | --- | --- | --- |
    | Titre court | Python | O4 | Petite | **Livré le 31 octobre** (PR #000) |

L'identifiant du lot est celui du nom de fichier. Un lot est compté « livré » quand son statut commence
par « Livré » (en gras ou non). Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
LOTS_DIR = PROJECT / "docs" / "lots"
INDEX_NAME = "00_INDEX.md"

MARKER = "<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->"
COLUMNS = ("Titre", "Langage", "Dépend de", "Taille", "Statut")
HEADER = "| " + " | ".join(COLUMNS) + " |"
SEPARATOR = "| " + " | ".join("---" for _ in COLUMNS) + " |"

LOT_FILE_RE = re.compile(r"^LOT_([A-Z]+\d*[a-z]?)_.+\.md$")
# Ligne de l'ancien tableau de 00_INDEX.md : « | [X54](LOT_X54_sujet.md) | titre | … | statut | ».
OLD_ROW_RE = re.compile(r"^\|\s*\[([^\]]+)\]\((LOT_[^)#]+\.md)\)\s*(\|.*\|)\s*$")


@dataclass(frozen=True)
class Lot:
    lot_id: str
    filename: str
    cells: tuple[str, ...]     # Titre, Langage, Dépend de, Taille, Statut, tels qu'écrits

    @property
    def status(self) -> str:
        return self.cells[-1]

    @property
    def delivered(self) -> bool:
        return self.status.lstrip("*").startswith("Livré")

    @property
    def series(self) -> str:
        return re.match(r"[A-Z]+", self.lot_id).group(0)


def split_row(row: str) -> list[str]:
    """Cellules d'une ligne de tableau Markdown (les « \\| » restent dans leur cellule)."""
    return [c.strip() for c in re.split(r"(?<!\\)\|", row.strip())[1:-1]]


def sort_key(lot_id: str) -> tuple[str, int, str]:
    """A, A2, AS1, …, X9, X10 : lettres, puis numéro, puis suffixe (V3b)."""
    m = re.fullmatch(r"([A-Z]+)(\d*)([a-z]?)", lot_id)
    return (m.group(1), int(m.group(2)) if m.group(2) else -1, m.group(3))


def lot_id_of(filename: str) -> str | None:
    m = LOT_FILE_RE.match(filename)
    return m.group(1) if m else None


def parse_lot(path: Path) -> tuple[Lot | None, str | None]:
    """Ligne d'index du cahier `path`, ou message d'erreur."""
    lot_id = lot_id_of(path.name)
    if lot_id is None:
        return None, f"docs/lots/{path.name} : nom attendu LOT_<id>_<sujet>.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        i = lines.index(MARKER)
    except ValueError:
        return None, f"docs/lots/{path.name} : pas de ligne d'index sous le titre (voir scripts/index_lots.py)"
    block = lines[i + 1:i + 4]
    if len(block) < 3 or block[0] != HEADER or block[1] != SEPARATOR:
        return None, f"docs/lots/{path.name} : ligne d'index mal formée (en-tête attendu : {HEADER})"
    cells = split_row(block[2])
    if len(cells) != len(COLUMNS) or not all(cells):
        return None, f"docs/lots/{path.name} : la ligne d'index doit avoir {len(COLUMNS)} cellules non vides"
    return Lot(lot_id, path.name, tuple(cells)), None


def read_lots(lots_dir: Path = LOTS_DIR) -> tuple[list[Lot], list[str]]:
    lots: list[Lot] = []
    errors: list[str] = []
    for path in sorted(lots_dir.glob("LOT_*.md")):
        lot, err = parse_lot(path)
        if err:
            errors.append(err)
        else:
            lots.append(lot)
    seen: dict[str, str] = {}
    for lot in lots:
        if lot.lot_id in seen:
            errors.append(f"docs/lots/{lot.filename} : lot {lot.lot_id} déjà décrit par {seen[lot.lot_id]}")
        seen[lot.lot_id] = lot.filename
    lots.sort(key=lambda lot: sort_key(lot.lot_id))
    return lots, errors


def old_rows(index_text: str) -> list[str]:
    """Lignes de l'ancien tableau restées dans 00_INDEX.md (il ne doit plus y en avoir)."""
    return [line for line in index_text.splitlines() if OLD_ROW_RE.match(line.strip())]


def check(lots_dir: Path = LOTS_DIR) -> list[str]:
    _, errors = read_lots(lots_dir)
    index = lots_dir / INDEX_NAME
    if index.is_file():
        for row in old_rows(index.read_text(encoding="utf-8")):
            errors.append(f"docs/lots/{INDEX_NAME} : ligne de lot à déplacer dans son cahier "
                          f"(python3 scripts/index_lots.py --migrer) : {row[:80]}")
    return errors


def table_markdown(lots: list[Lot]) -> str:
    out = ["| Lot | " + " | ".join(COLUMNS) + " |", "| --- " * (len(COLUMNS) + 1) + "|"]
    out += [f"| [{lot.lot_id}]({lot.filename}) | " + " | ".join(lot.cells) + " |" for lot in lots]
    return "\n".join(out) + "\n"


def stats(lots: list[Lot]) -> list[tuple[str, int, int]]:
    """(série, lots, lots livrés), séries dans l'ordre alphabétique."""
    by_series: dict[str, list[Lot]] = {}
    for lot in lots:
        by_series.setdefault(lot.series, []).append(lot)
    return [(s, len(ls), sum(lot.delivered for lot in ls)) for s, ls in sorted(by_series.items())]


def stats_markdown(lots: list[Lot]) -> str:
    rows = stats(lots)
    out = ["### Lots par série", "", "| Série | Lots | Livrés |", "| --- | --- | --- |"]
    out += [f"| {s} | {n} | {d} |" for s, n, d in rows]
    out.append(f"| **Total** | **{sum(r[1] for r in rows)}** | **{sum(r[2] for r in rows)}** |")
    return "\n".join(out) + "\n"


def lot_block(cells: list[str]) -> list[str]:
    return [MARKER, HEADER, SEPARATOR, "| " + " | ".join(cells) + " |"]


def write_lot_line(path: Path, cells: list[str]) -> None:
    """Écrit (ou remplace) la ligne d'index du cahier, juste sous son titre."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if MARKER in lines:
        i = lines.index(MARKER)
        lines[i:i + 4] = lot_block(cells)
    else:
        title = next((n for n, line in enumerate(lines) if line.startswith("# ")), -1)
        lines[title + 1:title + 1] = [""] + lot_block(cells)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _without_rows(text: str) -> str:
    return "".join(line for line in text.splitlines(keepends=True) if not OLD_ROW_RE.match(line.strip()))


def _merge_text(ours: str, base: str, theirs: str) -> tuple[str, bool]:
    """Fusion à trois du texte de 00_INDEX.md (`git merge-file`) ; vrai si elle laisse un conflit."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, text in (("branche", ours), ("base", base), ("main", theirs)):
            path = Path(tmp) / name
            path.write_text(text, encoding="utf-8")
            paths.append(str(path))
        proc = subprocess.run(["git", "merge-file", "-p", "-L", "branche", "-L", "base", "-L", "main", *paths],
                              capture_output=True, text=True)
    if proc.returncode < 0 or proc.returncode > 127:
        raise RuntimeError(f"git merge-file a échoué : {proc.stderr}")
    return proc.stdout, proc.returncode != 0


def migrate(lots_dir: Path, base_text: str, main_text: str) -> list[str]:
    """Fusion de main dans une PR ouverte avant X54 : range ses lignes de lot dans leur cahier.

    `00_INDEX.md` doit être la version de la branche (conflit résolu par `git checkout --ours`).
    `base_text` est l'index du dernier `main` d'avant X54 que la branche contient, `main_text` celui
    de `main` aujourd'hui. Seules les lignes que la branche a ajoutées ou modifiées par rapport à
    `base_text` vont dans leur cahier : les autres sont d'anciennes copies de `main`, et les cahiers
    de `main` sont plus récents. Le reste du texte (introduction, séries, graphe) est fusionné à
    trois : les changements de `main` et ceux de la branche sont gardés. Tout ou rien : en cas
    d'erreur, aucun fichier n'est modifié.
    """
    index = lots_dir / INDEX_NAME
    current = index.read_text(encoding="utf-8")
    if re.search(r"^(<{7}|={7}|>{7})( |$)", current, flags=re.MULTILINE):
        return [f"{INDEX_NAME} : conflit non résolu ; prendre d'abord la version de la branche "
                f"(git checkout --ours -- docs/lots/{INDEX_NAME}), puis relancer --migrer"]
    base_rows = {line.strip() for line in old_rows(base_text)}
    moves: list[tuple[Path, list[str]]] = []
    errors: list[str] = []
    for line in old_rows(current):
        if line.strip() in base_rows:
            continue                                   # ligne que la branche n'a pas touchée
        lot_id, filename, rest = OLD_ROW_RE.match(line.strip()).groups()
        cells = split_row(rest)
        path = lots_dir / filename
        if not path.is_file() or lot_id_of(filename) != lot_id or len(cells) != len(COLUMNS):
            errors.append(f"{INDEX_NAME} : ligne non déplacée (cahier absent ou ligne mal formée) : {line[:80]}")
        else:
            moves.append((path, cells))
    merged, conflict = _merge_text(_without_rows(current), _without_rows(base_text), main_text)
    if conflict:
        errors.append(f"{INDEX_NAME} : le texte hors tableau a changé des deux côtés ; fusion à faire à la main")
    if errors:
        return errors
    for path, cells in moves:
        write_lot_line(path, cells)
    index.write_text(merged, encoding="utf-8")
    return []


def _git(*args: str) -> str:
    proc = subprocess.run(["git", "-C", str(PROJECT), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} : {proc.stderr.strip()}")
    return proc.stdout


def git_texts(main_ref: str, base_ref: str | None) -> tuple[str, str]:
    """(index de la base, index de `main_ref`). Base par défaut : dernier `main` d'avant X54 que HEAD contient."""
    if base_ref is None:
        x54 = _git("log", "--first-parent", "--diff-filter=A", "--format=%H", main_ref, "--",
                   "scripts/index_lots.py").split()
        if not x54:
            raise RuntimeError(f"fusion du lot X54 introuvable dans {main_ref} (git fetch origin main ?)")
        base_ref = _git("merge-base", "HEAD", f"{x54[-1]}^1").strip()
    show = lambda ref: _git("show", f"{ref}:./docs/lots/{INDEX_NAME}")   # noqa: E731
    return show(base_ref), show(main_ref)


def main(argv: list[str] | None = None, lots_dir: Path = LOTS_DIR) -> int:
    parser = argparse.ArgumentParser(description="Index des lots calculé à partir des cahiers (lot X54).")
    parser.add_argument("--sortie", type=Path, help="écrire le tableau dans ce fichier au lieu de l'afficher")
    parser.add_argument("--stats", action="store_true", help="nombre de lots et de lots livrés par série")
    parser.add_argument("--resume", type=Path, help="ajouter les nombres par série à ce fichier Markdown")
    parser.add_argument("--verifier", action="store_true", help="code 1 si un cahier n'a pas de ligne valide")
    parser.add_argument("--migrer", action="store_true",
                        help="ranger dans leur cahier les lignes que la branche a changées dans 00_INDEX.md")
    parser.add_argument("--main", default="origin/main", help="référence de main pour --migrer (origin/main)")
    parser.add_argument("--base", help="index de départ de la branche pour --migrer (défaut : calculé)")
    args = parser.parse_args(argv)

    if args.migrer:
        try:
            base_text, main_text = git_texts(args.main, args.base)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 1
        migrate_errors = migrate(lots_dir, base_text, main_text)
        for err in migrate_errors:
            print(err, file=sys.stderr)
        if migrate_errors:
            return 1
    errors = check(lots_dir)
    if args.verifier or args.migrer:
        for err in errors:
            print(err, file=sys.stderr)
        if not errors:
            print("Index des lots : chaque cahier a sa ligne, 00_INDEX.md n'en contient plus.")
        return 1 if errors else 0

    lots, _ = read_lots(lots_dir)
    if args.resume:
        with args.resume.open("a", encoding="utf-8") as f:
            f.write(stats_markdown(lots))
    if args.stats:
        sys.stdout.write(stats_markdown(lots))
    elif args.sortie:
        args.sortie.write_text(table_markdown(lots), encoding="utf-8")
    elif not args.resume:
        sys.stdout.write(table_markdown(lots))
    for err in errors:
        print(err, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
