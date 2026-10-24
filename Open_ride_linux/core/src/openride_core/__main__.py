"""Point d'entrée `openride-core`.

Sous-commandes disponibles à ce stade :
    openride-core recover [JOURNAL]   transforme le dernier journal (ou celui donné) en FIT
    openride-core run [--trainer mock|ftms] [--input click|keyboard|none] [--gear N]
                      [--autostart [--route ID] [--workout ID]]
                                      boucle de séance (BLE, physique, IPC, journal) ; avec
                                      --autostart, parcours <routes>/<ID>.world (défaut demo) et
                                      entraînement ERG ~/OpenRide/Workouts/<ID>.zwo (absent : SIM)
    openride-core release-trainer     dépannage : annule la consigne du trainer, lui rend sa
                                      liberté et le déconnecte (après un arrêt brutal)
    openride-core summary [FICHIER] [--ftp W] [--json]
                                      bilan d'une séance (.jsonl ou .fit ; défaut : dernier journal)
    openride-core history [--dir DOSSIER] [--weeks N] [--ftp W] [--json]
                                      historique des séances et cumul par semaine ISO
"""

from __future__ import annotations

import argparse
import logging
import sys
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


def cmd_run(args: argparse.Namespace) -> int:
    import asyncio

    from . import config as config_mod
    from .session import AutostartError, CoreSession

    try:
        cfg = config_mod.load(args.config)
    except config_mod.ConfigError as exc:
        print(f"openride-core : configuration invalide : {exc}", file=sys.stderr)
        return 1
    if args.trainer:
        cfg.drivers.trainer = args.trainer
    if args.input:
        cfg.drivers.input = args.input
    if args.gear is not None:
        if not 1 <= args.gear <= cfg.gearing.n_gears:
            print(f"openride-core : --gear {args.gear} hors de 1 à {cfg.gearing.n_gears}", file=sys.stderr)
            return 2
        cfg.gearing.start_gear = args.gear
    if args.replay:
        cfg.drivers.trainer = "mock"
        cfg.drivers.mock_replay = str(args.replay)
    try:
        asyncio.run(CoreSession(cfg).run(autostart=args.autostart, route_id=args.route or "demo",
                                         workout_id=args.workout))
    except AutostartError as exc:
        logging.getLogger("openride_core").error("Séance non lancée : %s", exc)
        print(f"openride-core : {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_release_trainer(args: argparse.Namespace) -> int:
    import asyncio

    from . import config as config_mod
    from .ftms_driver import release_trainer

    try:
        cfg = config_mod.load(args.config)
    except config_mod.ConfigError as exc:
        print(f"openride-core : configuration invalide : {exc}", file=sys.stderr)
        return 1
    ok = asyncio.run(release_trainer(cfg.trainer, cfg.bike, cfg.drivers.trainer_address or None))
    print("Trainer libéré." if ok else "Trainer non libéré (voir les messages ci-dessus).")
    return 0 if ok else 1


def cmd_summary(args: argparse.Namespace) -> int:
    from .tools.session_summary import run

    return run(args.file, args.ftp, args.json, args.config)


def cmd_history(args: argparse.Namespace) -> int:
    from .tools.history import run

    return run(args.directory, args.weeks, args.ftp, args.json, args.config)


def build_parser() -> argparse.ArgumentParser:
    """Analyseur de la ligne de commande ; aussi lu par `test_docs_coherence.py` (commandes citées)."""
    p = argparse.ArgumentParser(prog="openride-core")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("recover", help="convertir un journal de séance en FIT")
    r.add_argument("journal", nargs="?", type=Path)
    run = sub.add_parser("run", help="lancer la boucle de séance")
    run.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    run.add_argument("--trainer", choices=["mock", "ftms"])
    run.add_argument("--input", choices=["click", "keyboard", "none"])
    run.add_argument("--gear", type=int, help="braquet de départ, 1 (léger) à 24 (dur) ; défaut 12")
    run.add_argument("--replay", type=Path,
                     help="rejoue une séance enregistrée (.jsonl ou .fit) avec le simulateur (force --trainer mock)")
    run.add_argument("--autostart", action="store_true",
                     help="charge le parcours (--route, défaut demo) et démarre aussitôt")
    run.add_argument("--route", metavar="ID",
                     help="avec --autostart : parcours <routes>/<ID>.world (défaut : demo)")
    run.add_argument("--workout", metavar="ID",
                     help="avec --autostart : entraînement ERG ~/OpenRide/Workouts/<ID>.zwo (absent : SIM)")
    rel = sub.add_parser("release-trainer",
                         help="libérer le trainer resté réservé (consigne annulée, contrôle rendu)")
    rel.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    summ = sub.add_parser("summary", help="bilan d'une séance : NP, IF, TSS, zones, meilleures puissances")
    summ.add_argument("file", nargs="?", type=Path, help="journal .jsonl ou .fit (défaut : dernier journal)")
    summ.add_argument("--ftp", type=float, help="FTP en watts (défaut : config.toml)")
    summ.add_argument("--json", action="store_true", help="sortie JSON")
    summ.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    hist = sub.add_parser("history", help="historique des séances et cumul par semaine ISO")
    hist.add_argument("--dir", type=Path, dest="directory",
                      help="dossier des séances (défaut : ~/OpenRide/Activities)")
    hist.add_argument("--weeks", type=int, default=8, help="nombre de semaines ISO (défaut : 8)")
    hist.add_argument("--ftp", type=float, help="FTP en watts (défaut : config.toml)")
    hist.add_argument("--json", action="store_true", help="sortie JSON")
    hist.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run" and not args.autostart:
        given = [opt for opt, val in (("--route", args.route), ("--workout", args.workout)) if val]
        if given:
            print(f"openride-core run : erreur : {' et '.join(given)} demande --autostart (sans lui,"
                  " l'engine choisit le parcours et l'entraînement)", file=sys.stderr)
            raise SystemExit(2)   # code d'argparse pour une ligne de commande refusée
    logging.basicConfig(level=logging.INFO, force=True,
                        format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    return {"recover": cmd_recover, "run": cmd_run,
            "release-trainer": cmd_release_trainer, "summary": cmd_summary,
            "history": cmd_history}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
