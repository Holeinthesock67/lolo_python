#!/usr/bin/env python3
"""Recompte des tests annoncés dans README.md et docs/SUIVI_AVANCEMENT.md (lot X34).

Les nombres de tests écrits dans la documentation sont vérifiés par `core/tests/test_docs_coherence.py`
(lot J7). Ils changent à chaque fusion, et toutes les PR ouvertes entrent alors en conflit sur ces
lignes. Après une fusion de `main` dans une branche, avant de pousser :

    python3 scripts/recompte_tests.py              # réécrit les nombres faux
    python3 scripts/recompte_tests.py --verifier   # dit seulement ce qui diffère (code 1)

Nombres comptés comme les tests les comptent : tests collectés par `pytest -q` du core et du
compilateur (sans les tests `network`), fichiers `engine/tests/unit/test_*.gd` et
`engine/tests/render/test_*.gd`. Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

# document -> {compte : motif à un groupe}. Chaque motif doit figurer dans son document.
TEST_COUNT_PATTERNS: dict[str, dict[str, str]] = {
    "README.md": {
        "core": r"(\d+) tests automatiques côté core",
        "compiler": r"et (\d+) côté compilateur",
        "engine_unit": r"(\d+) fichiers de tests unitaires",
        "engine_render": r"(\d+) tests de rendu",
    },
    "docs/SUIVI_AVANCEMENT.md": {
        "core": r"(\d+) tests pytest passent dans le core",
        "compiler": r"et (\d+) dans le compilateur",
        "engine_unit": r"(\d+) fichiers de tests unitaires",
        "engine_render": r"(\d+) tests de rendu",
    },
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


def check_test_counts(text: str, doc_name: str, actual: dict[str, int]) -> list[str]:
    """Erreurs de la doc `doc_name` face aux nombres réels ; un compte absent d'`actual` n'est pas vérifié."""
    errors: list[str] = []
    for key, pattern in TEST_COUNT_PATTERNS[doc_name].items():
        if key not in actual:
            continue
        found = re.findall(pattern, text)
        if not found:
            errors.append(f"{doc_name} : phrase du nombre de {LABELS[key]} absente ({pattern})")
        for value in found:
            if int(value) != actual[key]:
                errors.append(f"{doc_name} : {value} {LABELS[key]} annoncés, écrire {actual[key]} "
                              f"(python3 scripts/recompte_tests.py)")
    return errors


def fix_test_counts(text: str, doc_name: str, actual: dict[str, int]) -> str:
    """Le texte avec chaque nombre annoncé remplacé par le nombre réel."""
    for key, pattern in TEST_COUNT_PATTERNS[doc_name].items():
        if key in actual:
            text = re.sub(pattern, lambda m, v=actual[key]: m.group(0).replace(m.group(1), str(v), 1), text)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recompte des tests annoncés dans la documentation (lot X34).")
    ap.add_argument("--verifier", action="store_true", help="ne rien écrire, code 1 si un nombre est faux")
    args = ap.parse_args(argv)
    try:
        import openride_compiler  # noqa: F401
        with_compiler = True
    except ImportError:
        with_compiler = False
        print("openride-compiler non installé : nombre de tests du compilateur laissé tel quel")
    actual = actual_counts(PROJECT, with_compiler)
    print("Comptés : " + ", ".join(f"{LABELS[k]} {v}" for k, v in actual.items()))
    bad = 0
    for doc_name in TEST_COUNT_PATTERNS:
        path = PROJECT / doc_name
        text = path.read_text(encoding="utf-8")
        errors = check_test_counts(text, doc_name, actual)
        for e in errors:
            print(("  " if args.verifier else "  corrigé : ") + e)
        bad += len(errors)
        if errors and not args.verifier:
            path.write_text(fix_test_counts(text, doc_name, actual), encoding="utf-8")
    if not bad:
        print("Nombres de tests à jour.")
    return 1 if bad and args.verifier else 0


if __name__ == "__main__":
    sys.exit(main())
