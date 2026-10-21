"""Point d'entrée `openride-core`.

Sous-commandes disponibles à ce stade :
    openride-core recover [JOURNAL]   transforme le dernier journal (ou celui donné) en FIT
La boucle de séance (BLE, physique, IPC) arrive au sprint 1.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import __version__
from .fit_export import journal_to_fit
from .journal import latest_journal


def cmd_recover(args: argparse.Namespace) -> int:
    path = args.journal or latest_journal()
    if path is None:
        print("Aucun journal trouvé.")
        return 1
    fit_path, s = journal_to_fit(Path(path))
    print(f"{fit_path}  ({s.distance_m / 1000:.2f} km, {s.timer_s / 60:.1f} min)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="openride-core")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("recover", help="convertir un journal de séance en FIT")
    r.add_argument("journal", nargs="?", type=Path)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    return {"recover": cmd_recover}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
