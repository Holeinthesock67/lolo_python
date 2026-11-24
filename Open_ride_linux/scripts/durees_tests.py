#!/usr/bin/env python3
"""Durées des fichiers de test mesurées dans des rapports JUnit, pour répartir la CI (audit du 22 novembre, P1).

    python3 scripts/durees_tests.py junit/core.xml junit/compiler.xml   # réécrit scripts/durees_tests.json

Les rapports viennent de `pytest --junitxml` (pièces jointes « junit-python-* » des runs de la CI, ou un
passage local). Les parties de `OPENRIDE_TESTS_PARTIE` (`isolation_tests.repartir_fichiers`) s'en servent
pour faire des parts de durée voisine ; un fichier absent compte pour la durée médiane, si bien qu'un
fichier périmé ne fait jamais perdre de test, seulement un peu d'équilibre. Bibliothèque standard seulement.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

DUREES = Path(__file__).with_name("durees_tests.json")
SUITES = {"core": "core/tests", "compiler": "compiler/tests"}


def fichier_du_cas(classname: str, suite: str) -> str | None:
    """« tests.test_x.TestY » ou « test_x » → « core/tests/test_x.py »."""
    parts = [p for p in classname.split(".") if p]
    if parts and parts[0] == "tests":
        parts = parts[1:]
    module = next((p for p in parts if p.startswith("test_")), None)
    return f"{SUITES[suite]}/{module}.py" if module else None


def lire_rapport(chemin: Path) -> dict[str, float]:
    """Durée par fichier de test d'un rapport ; la suite (core ou compilateur) se lit dans le nom du rapport."""
    suite = next((s for s in SUITES if s in chemin.stem), None)
    if suite is None:
        raise SystemExit(f"{chemin} : nom sans « core » ni « compiler »")
    durees: dict[str, float] = defaultdict(float)
    for cas in ET.parse(chemin).iter("testcase"):
        nom = fichier_du_cas(cas.get("classname", ""), suite)
        if nom:
            durees[nom] += float(cas.get("time") or 0.0)
    return dict(durees)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rapports", nargs="+", type=Path, help="rapports JUnit (core*.xml, compiler*.xml)")
    ap.add_argument("--sortie", type=Path, default=DUREES)
    args = ap.parse_args(argv)
    durees: dict[str, float] = defaultdict(float)
    for chemin in args.rapports:
        for nom, s in lire_rapport(chemin).items():
            durees[nom] += s
    if not durees:
        print("aucun cas de test lu")
        return 1
    doc = {"note": "Durées en secondes par fichier de test, réécrites par scripts/durees_tests.py ; "
                   "servent seulement à équilibrer les parties de la CI (OPENRIDE_TESTS_PARTIE).",
           "fichiers": {k: round(v, 1) for k, v in sorted(durees.items())}}
    args.sortie.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(durees)} fichiers, {sum(durees.values()) / 60:.1f} min au total → {args.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
