#!/usr/bin/env python3
"""Filet « à l'identique » des modes de jeu (lot IM0) : référence des empreintes et relevés complets.

    python3 scripts/modes_identique.py                       # rejoue tout, dit ce qui a changé (rien n'est écrit)
    python3 scripts/modes_identique.py --maj                 # réécrit core/tests/data/modes_identique.json
    python3 scripts/modes_identique.py --releve DOSSIER      # écrit aussi le relevé complet de chaque séance
    python3 scripts/modes_identique.py --scenario wtf        # une séance seulement (répétable)

Les séances tournent dans un dossier temporaire, avec un HOME temporaire (`isolation_tests`) : rien n'est lu
ni écrit dans le vrai dossier personnel. À lancer depuis `Open_ride_linux/`, environnement du core actif.
Pour comparer deux versions : `--releve A` sur l'une, `--releve B` sur l'autre, puis `diff A/x.json B/x.json`
(une ligne par relevé : `python3 -m json.tool` les rend lisibles).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from isolation_tests import isoler_environnement  # noqa: E402

TESTS = ICI.parent / "core" / "tests"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maj", action="store_true", help="réécrit la référence des empreintes")
    ap.add_argument("--releve", type=Path, help="dossier où écrire le relevé complet de chaque séance")
    ap.add_argument("--scenario", action="append", help="séance à jouer (défaut : toutes)")
    args = ap.parse_args(argv)

    isoler_environnement()   # avant tout import d'openride_core (chemins calculés à l'import)
    sys.path.insert(0, str(TESTS))
    import identique
    from identique_scenarios import SCENARIOS

    if sys.version_info[:2] < identique.PYTHON_MIN:
        ap.error("empreintes calculées en Python %d.%d et plus (3.14 sur le PC et en CI)" % identique.PYTHON_MIN)
    names = args.scenario or sorted(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        ap.error(f"séance inconnue : {', '.join(unknown)} (connues : {', '.join(sorted(SCENARIOS))})")
    if args.maj and args.scenario:
        ap.error("--maj rejoue toutes les séances (sans --scenario)")
    ref = identique.load_reference().get("scenarios", {})
    out: dict[str, dict] = {}
    changed = 0
    for i, name in enumerate(names):
        with tempfile.TemporaryDirectory(prefix="openride-im0-") as tmp:
            root = Path(tmp) / "banc"
            rel = identique.play(name, root, port=7600 + 40 * i)
            out[name] = identique.fingerprint(rel, root)
            if args.releve:
                args.releve.mkdir(parents=True, exist_ok=True)
                (args.releve / f"{name}.json").write_bytes(identique.canonical(rel, root))
        diff = [k for k in identique.RELEVES if ref.get(name, {}).get(k) != out[name][k]]
        changed += bool(diff)
        print(f"{name:24} {'à l’identique' if not diff else 'CHANGÉ : ' + ', '.join(diff)}")
    if args.maj:
        doc = {"note": "Empreintes du filet « à l'identique » des modes (lot IM0), recalculées par "
                       "scripts/modes_identique.py --maj ; à ne changer que pour un changement de comportement voulu.",
               "scenarios": out}
        identique.REFERENCE.parent.mkdir(parents=True, exist_ok=True)
        identique.REFERENCE.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
        print(f"Référence écrite : {identique.REFERENCE}")
        return 0
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
