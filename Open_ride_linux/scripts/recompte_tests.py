#!/usr/bin/env python3
"""Compte des tests du projet (lots X34 et X52).

Depuis le lot X52, `README.md` et `docs/SUIVI_AVANCEMENT.md` n'écrivent plus de nombre de tests : ces
nombres changeaient à chaque fusion et toutes les PR ouvertes entraient alors en conflit sur ces lignes.
Le compte se lit ici, et chaque run de la CI l'écrit dans son résumé :

    python3 scripts/recompte_tests.py                          # affiche les nombres
    python3 scripts/recompte_tests.py --resume fichier.md      # les ajoute aussi en tableau Markdown
    python3 scripts/recompte_tests.py --verifier               # code 1 si un document écrit encore un nombre

Nombres comptés comme les suites les lancent : tests collectés par `pytest -q` du core et du compilateur
(sans les tests `network`), fichiers `engine/tests/unit/test_*.gd` et `engine/tests/render/test_*.gd`.
Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

# Documents qui décrivent les suites de tests, et phrases qui y écrivaient un nombre (à ne plus écrire).
DOCUMENTS = ("README.md", "docs/SUIVI_AVANCEMENT.md")
HARD_COUNT_PATTERNS: dict[str, str] = {
    "core": r"(\d+) tests (?:automatiques côté core|pytest passent dans le core)",
    "compiler": r"et (\d+) (?:côté compilateur|dans le compilateur)",
    "engine_unit": r"(\d+) fichiers de tests unitaires",
    "engine_render": r"(\d+) tests de rendu",
}
LABELS = {"core": "tests core", "compiler": "tests compiler", "engine_unit": "fichiers de tests unitaires de l'engine",
          "engine_render": "tests de rendu de l'engine"}


def collected_test_count(package_dir: Path) -> int:
    """Nombre de tests que `pytest -q` lance dans `package_dir` (options du paquet, donc sans
    les tests `network` du compilateur)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=package_dir, capture_output=True, text=True, timeout=120,
    )
    m = re.search(r"^(\d+)(?:/\d+)? tests? collected", proc.stdout, flags=re.MULTILINE)
    if proc.returncode != 0 or m is None:
        raise RuntimeError(f"collecte impossible dans {package_dir} :\n{proc.stdout[-2000:]}")
    return int(m.group(1))


def engine_counts(project: Path = PROJECT) -> dict[str, int]:
    tests = project / "engine" / "tests"
    return {"engine_unit": len(list((tests / "unit").glob("test_*.gd"))),
            "engine_render": len(list((tests / "render").glob("test_*.gd")))}


def actual_counts(project: Path = PROJECT, with_compiler: bool = True) -> dict[str, int]:
    out = {"core": collected_test_count(project / "core"), **engine_counts(project)}
    if with_compiler:
        out["compiler"] = collected_test_count(project / "compiler")
    return out


def hard_counts(text: str, doc_name: str) -> list[str]:
    """Nombres de tests encore écrits dans la doc `doc_name` (ils doivent venir de ce script)."""
    errors: list[str] = []
    for key, pattern in HARD_COUNT_PATTERNS.items():
        for value in re.findall(pattern, text):
            errors.append(f"{doc_name} : « {value} {LABELS[key]} » écrit en dur ; le nombre vient de "
                          f"python3 scripts/recompte_tests.py et du résumé de la CI")
    return errors


def summary_markdown(actual: dict[str, int]) -> str:
    rows = "".join(f"| {LABELS[k]} | {v} |\n" for k, v in actual.items())
    return "### Nombre de tests\n\n| Suite | Nombre |\n|---|---|\n" + rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compte des tests du projet (lots X34 et X52).")
    ap.add_argument("--verifier", action="store_true",
                    help="seulement vérifier qu'aucun document n'écrit de nombre de tests (code 1 sinon)")
    ap.add_argument("--resume", type=Path, help="ajoute le tableau des nombres à ce fichier Markdown "
                    "(résumé du run de la CI : $GITHUB_STEP_SUMMARY)")
    args = ap.parse_args(argv)
    if args.verifier:
        errors = [e for name in DOCUMENTS for e in hard_counts((PROJECT / name).read_text(encoding="utf-8"), name)]
        for e in errors:
            print("  " + e)
        if not errors:
            print("Aucun nombre de tests écrit en dur.")
        return 1 if errors else 0
    try:
        import openride_compiler  # noqa: F401
        with_compiler = True
    except ImportError:
        with_compiler = False
        print("openride-compiler non installé : tests du compilateur non comptés")
    actual = actual_counts(PROJECT, with_compiler)
    print("Comptés : " + ", ".join(f"{LABELS[k]} {v}" for k, v in actual.items()))
    if args.resume:
        with args.resume.open("a", encoding="utf-8") as f:
            f.write(summary_markdown(actual))
    return 0


if __name__ == "__main__":
    sys.exit(main())
