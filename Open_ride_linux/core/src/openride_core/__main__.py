"""Point d'entrée `openride-core`.

Sous-commandes disponibles à ce stade :
    openride-core recover [JOURNAL]   transforme le dernier journal (ou celui donné) en FIT
    openride-core run [--trainer mock|ftms|sim] [--input click|keyboard|none|sim]
                      [--hr none|ble|sim] [--sim-scenario NOM|FICHIER] [--gear N]
                      [--autostart [--route ID] [--workout ID | --ftp-test ramp]]
                      [--resume JOURNAL]
                                      boucle de séance (BLE, physique, IPC, journal) ; avec
                                      --autostart, parcours <routes>/<ID>.world (défaut demo) et
                                      entraînement ERG ~/OpenRide/Workouts/<ID>.zwo (absent : SIM) ;
                                      « sim » : HomeTrainer, Click ou ceinture simulés (Bluetooth simulé) ;
                                      --resume : reprend en pause la séance d'un journal non terminé
                                      (relance par le lanceur après un plantage du core, lot N8) ;
                                      --ftp-test : séance de test de FTP (lot O10)
    openride-core release-trainer     dépannage : annule la consigne du trainer, lui rend sa
                                      liberté et le déconnecte (après un arrêt brutal)
    openride-core summary [FICHIER] [--ftp W] [--json]
                                      bilan d'une séance (.jsonl ou .fit ; défaut : dernier journal)
    openride-core session-report [FICHIER] [--log F] [--engine-log F] [--out DOSSIER] [--json]
                                      analyse d'une séance réelle : sections de pente, retard
                                      pente → effort, ERG, coupures, segments (lot X12)
    openride-core fit-check FICHIER.fit [--journal JOURNAL.jsonl] [--json]
                                      contrôle local d'un FIT de séance réelle avec le SDK Garmin
                                      (messages, pauses, trous, FC figée, totaux ; lot X11)
    openride-core history [--dir DOSSIER] [--weeks N] [--ftp W] [--json]
                                      historique des séances et cumul par semaine ISO
    openride-core xp [--dir DOSSIER] [--json] [--config FICHIER] [--save F | --compare F]
                                      progression (niveau, expérience, défis) recalculée depuis
                                      le journal des séances (série V, lot V2) ; écart avant/après
                                      une PR face à un instantané (lot X39)
    openride-core devices [--timeout S] [--json] [--all] [--config FICHIER]
                          [--sim-scenario NOM|FICHIER] [--save [--yes]]
                                      inventaire des appareils Bluetooth (trainer, Click,
                                      ceinture) et bloc [drivers] proposé pour config.toml
    openride-core settings [--json] [--config FICHIER]
    openride-core settings set CLÉ VALEUR [--config FICHIER]
                                      réglages du menu (FTP, poids, difficulté, braquet de
                                      départ, qualité, thème) : lecture, ou écriture dans config.toml
    openride-core plan list|show ID|start ID [--date AAAA-MM-JJ]|stop|today|install
    openride-core plan import DOSSIER --name NOM --days mardi,jeudi,samedi
                                      plans d'entraînement sur plusieurs semaines (lot O11)
    openride-core ftp-test [FICHIER] [--accept [--force]] [--history] [--json] [--config FICHIER]
                                      résultat du dernier test de FTP (ou du journal donné),
                                      enregistrement de la nouvelle FTP, historique des tests (lot O10)
    openride-core profil list [--json] | create NOM | rename ID NOM | delete ID
                                      profils de joueurs : liste, création, renommage, corbeille
                                      (série MJ, lot MJ7)
    openride-core profil essai [--vider] [--json] [--config FICHIER]
                                      profil d'essai (séances simulées comptées) : dossier,
                                      progression ; --vider efface ses séances (série MJ, lot MJ2)

Toutes les sous-commandes prennent `--profil ID` (profil de joueur, série MJ).
"""

from __future__ import annotations

import argparse
import json
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
    from . import config as config_mod

    try:
        cfg = config_mod.load(args.config)
    except config_mod.ConfigError as exc:
        print(f"openride-core : configuration invalide : {exc}", file=sys.stderr)
        return 1
    if args.trainer:
        cfg.drivers.trainer = args.trainer
    if args.input:
        cfg.drivers.input = args.input
    if args.hr:
        cfg.drivers.hr = args.hr
    if args.sim_scenario:
        cfg.drivers.sim_scenario = args.sim_scenario
    if args.gear is not None:
        if not 1 <= args.gear <= cfg.gearing.n_gears:
            print(f"openride-core : --gear {args.gear} hors de 1 à {cfg.gearing.n_gears}", file=sys.stderr)
            return 2
        cfg.gearing.start_gear = args.gear
    if args.replay:
        cfg.drivers.trainer = "mock"
        cfg.drivers.mock_replay = str(args.replay)
    if args.trace_ftms:
        cfg.trainer.trace_ftms = True
    if args.latence:
        cfg.log.latence = True
    from . import latency_log
    latency_log.enable(cfg.log.latence)

    bots_list = []
    if args.bot or args.bot_profile:
        if len(args.bot or []) + len(args.bot_profile or []) > 4:
            print("openride-core run : erreur : au plus 4 bots à puissance constante ou à profil "
                  "(--bot, --bot-profile)", file=sys.stderr)
            return 2
        from .bots import ConstantPowerBot, BotError, ProfileBot, profile_bot_names
        from .physics import PhysicsParams
        phys_params = PhysicsParams.from_config(cfg)
        try:
            for w in args.bot or []:
                bots_list.append(ConstantPowerBot(w, bot_id=f"bot{len(bots_list) + 1}", params=phys_params))
            profiles = args.bot_profile or []
            for prof, name in zip(profiles, profile_bot_names(profiles)):
                bots_list.append(ProfileBot(prof, bot_id=f"bot{len(bots_list) + 1}", name=name,
                                            params=phys_params, bike_mass_kg=cfg.bike.mass_kg))
        except BotError as exc:
            print(f"openride-core run : erreur : {exc}", file=sys.stderr)
            return 2
    if args.ghost:
        from .bots import GhostBot, BotError
        try:
            bots_list.append(GhostBot(args.ghost))
        except BotError as exc:
            print(f"openride-core run : erreur : {exc}", file=sys.stderr)
            return 1

    if args.first_run:
        logging.getLogger("openride_core").info(
            "Premier démarrage : configurez vos appareils avec openride-core devices --save.")
    from . import profiles

    ctx = profiles.current()
    lock = profiles.ProfileLock(ctx) if ctx.id is not None else None
    if lock is not None:
        try:
            lock.acquire()   # une seule séance par profil (rendu à l'arrêt ou au plantage du core)
        except profiles.ProfileContextError as exc:
            print(f"openride-core : {exc}", file=sys.stderr)
            return 1
        profiles.ensure_description(ctx)   # profil.toml écrit à la première séance (lot MJ2)
        logging.getLogger("openride_core").info("Profil de joueur : %s (%s)%s.", ctx.id, ctx.root,
                                                " — PROFIL D'ESSAI" if ctx.is_trial else "")
    try:
        return _run_session(cfg, bots_list, args, lock)
    finally:
        if lock is not None:
            lock.release()


def _run_session(cfg, bots_list: list, args: argparse.Namespace, lock=None) -> int:
    import asyncio

    from .session import AutostartError, CoreSession
    from .sim_scenarios import SimScenarioError

    try:
        session = CoreSession(cfg, bots=bots_list, config_path=args.config)
    except SimScenarioError as exc:
        print(f"openride-core : scénario de simulation refusé : {exc}", file=sys.stderr)
        return 1
    # Le verrou suit le profil choisi au menu (lot MJ7) ; rendu à la fin, quel que soit le profil.
    session.profile_lock = lock
    if lock is not None:
        session._note_profile()
    try:
        asyncio.run(session.run(autostart=args.autostart, route_id=args.route or "demo",
                                workout_id=args.workout, resume=args.resume))
    except AutostartError as exc:
        logging.getLogger("openride_core").error("Séance non lancée : %s", exc)
        print(f"openride-core : {exc}", file=sys.stderr)
        return 1
    finally:
        if session.profile_lock is not None and session.profile_lock is not lock:
            session.profile_lock.release()
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


def cmd_session_report(args: argparse.Namespace) -> int:
    from .tools.session_report import run

    return run(args.file, args.log, args.engine_log, args.out, args.json)
def cmd_fit_check(args: argparse.Namespace) -> int:
    from .tools.fit_check import run

    return run(args.file, args.journal, args.json)


def cmd_history(args: argparse.Namespace) -> int:
    from .tools.history import run

    return run(args.directory, args.weeks, args.ftp, args.json, args.config)


def cmd_xp(args: argparse.Namespace) -> int:
    from .tools.xp import run

    return run(args.directory, args.json, args.config, save=args.save, compare=args.compare)


def cmd_devices(args: argparse.Namespace) -> int:
    from .tools.devices import run

    return run(args.timeout, args.json, args.config, args.sim_scenario, args.all,
               save=args.save, assume_yes=args.yes)


def cmd_settings(args: argparse.Namespace) -> int:
    from .settings import run

    if args.action and (args.action[0] != "set" or len(args.action) != 3):
        print("openride-core settings : usage : settings set CLÉ VALEUR", file=sys.stderr)
        return 2
    return run(args.json, args.config, args.action[1:] if args.action else None)


def cmd_ftp_test(args: argparse.Namespace) -> int:
    from .ftp_test import run

    return run(args.file, args.accept, args.force, args.history, args.json, args.config, args.directory)


def cmd_plan(args: argparse.Namespace) -> int:
    from .plans import run

    return run(args)


PROFIL_ARGS = {"essai": 0, "list": 0, "create": 1, "rename": 2, "delete": 1}


def cmd_profil(args: argparse.Namespace) -> int:
    """`openride-core profil essai [--vider]` : profil d'essai, sa progression, sa remise à zéro ;
    `profil list|create|rename|delete` : profils de joueurs, pour les outils (lot MJ7)."""
    from . import profiles
    from .tools.xp import run as xp_run

    if len(args.valeurs) != PROFIL_ARGS[args.action]:
        print("openride-core profil : usage : profil essai [--vider] | list [--json] | create NOM | "
              "rename ID NOM | delete ID", file=sys.stderr)
        return 2
    if args.action != "essai":
        return _profil_players(args)
    ctx = profiles.ProfileContext.for_id(profiles.TRIAL_ID)
    profiles.activate(ctx)
    profiles.ensure_description(ctx)
    if args.vider:
        with profiles.ProfileLock(ctx):   # pas pendant une séance d'essai
            removed = profiles.clear(ctx)
        print(f"Profil d'essai vidé ({ctx.root}) : {', '.join(removed) or 'rien à effacer'}.")
        return 0
    if not args.json:
        print(f"Profil d'essai : {ctx.root}")
        print(f"Séances comptées : {', '.join(ctx.counted_sources)}")
    return xp_run(None, args.json, args.config)


def _profil_players(args: argparse.Namespace) -> int:
    from . import profiles
    from .garage import profile_summary

    try:
        if args.action == "list":
            active = profiles.default_id()
            items = [profile_summary(c) for c in profiles.list_contexts()]
            if args.json:
                print(json.dumps({"default": active, "items": items}, ensure_ascii=False, indent=2))
                return 0
            for it in items:
                mark = "*" if it["id"] == active else " "
                print(f"{mark} {it['id']:<20} {it['name']:<16} {it['type']:<7} niveau {it['level']:>2}  "
                      f"dernière séance {it['last_ride'] or '—'}")
            if not items:
                print(f"Aucun profil dans {profiles.profiles_dir()}")
            return 0
        if args.action == "create":
            ctx = profiles.create(args.valeurs[0])
            print(f"Profil créé : {ctx.name} ({ctx.root})")
        elif args.action == "rename":
            ctx = profiles.rename(args.valeurs[0], args.valeurs[1])
            print(f"Profil renommé : {ctx.id} s'appelle maintenant {ctx.name}")
        else:
            dest = profiles.delete(args.valeurs[0], None)   # une séance en cours tient le verrou du profil
            print(f"Profil mis à la corbeille : {dest}")
    except profiles.ProfileContextError as exc:
        print(f"openride-core profil {args.action} : {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_open_world_save(args: argparse.Namespace) -> int:
    from . import config as config_mod
    from .config import GPX_DIR
    from .open_world_save import MIN_SAVE_M, save_from_folder
    from .route import WorldError

    cfg = config_mod.load(args.config)
    try:
        path, s_end = save_from_folder(args.ride_id, cfg.open_world, args.gpx_dir or GPX_DIR,
                                       args.journal_dir,
                                       args.km * 1000.0 if args.km else None)
    except WorldError as exc:
        print(f"openride-core open-world-save : {exc}", file=sys.stderr)
        return 1
    if path is None:
        print(f"Balade de {s_end:.0f} m : au plus {MIN_SAVE_M:.0f} m, rien n'est enregistré.")
        return 0
    print(f"Balade enregistrée : {path} ({s_end / 1000.0:.1f} km). Elle sera compilée au prochain lancement.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Analyseur de la ligne de commande ; aussi lu par `test_docs_coherence.py` (commandes citées)."""
    p = argparse.ArgumentParser(prog="openride-core")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("recover", help="convertir un journal de séance en FIT")
    r.add_argument("journal", nargs="?", type=Path)
    run = sub.add_parser("run", help="lancer la boucle de séance")
    run.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    run.add_argument("--trainer", choices=["mock", "ftms", "sim"],
                     help="sim : HomeTrainer simulé derrière le vrai pilote FTMS (sans matériel)")
    run.add_argument("--input", choices=["click", "keyboard", "none", "sim"],
                     help="sim : paire de Zwift Click simulée (le clavier y appuie)")
    run.add_argument("--hr", choices=["none", "ble", "sim"],
                     help="ceinture cardio : ble (réelle), sim (simulée) ; défaut none")
    run.add_argument("--sim-scenario", metavar="NOM|FICHIER",
                     help="scénario du Bluetooth simulé : demo (défaut), nominal, reveil_tardif, "
                          "erreur_0x80, connexions_retardees, coupures, controle_refuse, ou JSON")
    run.add_argument("--gear", type=int, help="braquet de départ, 1 (léger) à 24 (dur) ; défaut 12")
    run.add_argument("--replay", type=Path,
                     help="rejoue une séance enregistrée (.jsonl ou .fit) avec le simulateur (force --trainer mock)")
    run.add_argument("--bot", action="append", type=float, metavar="W",
                     help="ajoute un bot à puissance constante en watts (répétable, au plus 4 avec --bot-profile)")
    run.add_argument("--bot-profile", action="append", choices=["climber", "rouleur", "sprinter", "diesel"],
                     metavar="PROFIL",
                     help="ajoute un bot à profil : climber (Grimpeur), rouleur, sprinter (Sprinteur) ou "
                          "diesel (répétable, au plus 4 bots en tout avec --bot ; lot T12)")
    run.add_argument("--ghost", type=Path, metavar="FICHIER",
                     help="ajoute un fantôme rejouant une séance enregistrée (.jsonl ou .fit)")
    run.add_argument("--first-run", action="store_true",
                     help="premier démarrage (passé par le lanceur ; le menu ouvrira « Appareils », lot N13)")
    run.add_argument("--resume", type=Path, metavar="JOURNAL",
                     help="reprend en pause la séance d'un journal non terminé (après un plantage du core)")
    run.add_argument("--autostart", action="store_true",
                     help="charge le parcours (--route, défaut demo) et démarre aussitôt")
    run.add_argument("--route", metavar="ID",
                     help="avec --autostart : parcours <routes>/<ID>.world (défaut : demo)")
    run.add_argument("--workout", metavar="ID",
                     help="avec --autostart : entraînement ERG ~/OpenRide/Workouts/<ID>.zwo (absent : SIM)")
    run.add_argument("--ftp-test", choices=["ramp"],
                     help="avec --autostart : séance de test de FTP (rampe par paliers)")
    run.add_argument("--latence", action="store_true",
                     help="journal de latence des appuis du Click, lignes [latence] (lot X7 ; [log] latence)")
    run.add_argument("--trace-ftms", action="store_true",
                     help="trace horodatée de chaque échange Control Point FTMS (lot Q3)")
    rel = sub.add_parser("release-trainer",
                         help="libérer le trainer resté réservé (consigne annulée, contrôle rendu)")
    rel.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    summ = sub.add_parser("summary", help="bilan d'une séance : NP, IF, TSS, zones, meilleures puissances")
    summ.add_argument("file", nargs="?", type=Path, help="journal .jsonl ou .fit (défaut : dernier journal)")
    summ.add_argument("--ftp", type=float, help="FTP en watts (défaut : config.toml)")
    summ.add_argument("--json", action="store_true", help="sortie JSON")
    summ.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    srep = sub.add_parser("session-report", help="analyse d'une séance : sections de pente, retard pente → effort, "
                                                 "ERG, coupures, segments (rapport HTML local)")
    srep.add_argument("file", nargs="?", type=Path, help="journal .jsonl ou .fit (défaut : dernier journal)")
    srep.add_argument("--log", type=Path, help="journal du core (run_trainer.log)")
    srep.add_argument("--engine-log", type=Path, help="journal de l'engine (lignes [perf-rendu])")
    srep.add_argument("--out", type=Path, help="dossier du rapport (défaut : ~/OpenRide/rapports/<séance>)")
    srep.add_argument("--json", action="store_true", help="sortie JSON")
    fitc = sub.add_parser("fit-check", help="contrôle local d'un FIT de séance réelle (SDK Garmin, lot X11)")
    fitc.add_argument("file", type=Path, help="fichier .fit")
    fitc.add_argument("--journal", type=Path, help="journal .jsonl de la séance : distance et durée à ± 1 %%")
    fitc.add_argument("--json", action="store_true", help="sortie JSON")
    hist = sub.add_parser("history", help="historique des séances et cumul par semaine ISO")
    hist.add_argument("--dir", type=Path, dest="directory",
                      help="dossier des séances (défaut : ~/OpenRide/Activities)")
    hist.add_argument("--weeks", type=int, default=8, help="nombre de semaines ISO (défaut : 8)")
    hist.add_argument("--ftp", type=float, help="FTP en watts (défaut : config.toml)")
    hist.add_argument("--json", action="store_true", help="sortie JSON")
    hist.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    xp = sub.add_parser("xp", help="progression (niveau, expérience, défis) recalculée depuis le journal")
    xp.add_argument("--dir", type=Path, dest="directory",
                    help="dossier des journaux (défaut : ~/OpenRide/Activities/.journal)")
    xp.add_argument("--json", action="store_true", help="sortie JSON")
    xp.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    snap = xp.add_mutually_exclusive_group()
    snap.add_argument("--save", type=Path, metavar="FICHIER", help="écrit l'instantané (sortie --json) avant une PR")
    snap.add_argument("--compare", type=Path, metavar="FICHIER",
                      help="écart d'expérience, de pièces et de défis face à un instantané (code 1 si écart)")
    dev = sub.add_parser("devices", help="inventaire des appareils Bluetooth et bloc [drivers] proposé")
    dev.add_argument("--timeout", type=float, default=8.0, help="durée de la recherche en s (défaut : 8)")
    dev.add_argument("--json", action="store_true", help="sortie JSON")
    dev.add_argument("--all", action="store_true", help="montre aussi les appareils sans rôle")
    dev.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    dev.add_argument("--sim-scenario", metavar="NOM|FICHIER",
                     help="recherche dans le Bluetooth simulé (mêmes noms que run --sim-scenario)")
    dev.add_argument("--save", action="store_true",
                     help="enregistre le matériel trouvé dans config.toml (appui « + » demandé, lot N12)")
    dev.add_argument("--yes", action="store_true", help="avec --save : sans demander de confirmation")
    st = sub.add_parser("settings", help="réglages du menu : lecture ou écriture dans config.toml")
    st.add_argument("action", nargs="*", metavar="set CLÉ VALEUR")
    st.add_argument("--json", action="store_true", help="sortie JSON")
    st.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    pl = sub.add_parser("plan", help="plans d'entraînement : list, show, start, stop, today, import, install")
    pl.add_argument("action", choices=["list", "show", "start", "stop", "today", "import", "install"])
    pl.add_argument("plan_id", nargs="?", metavar="ID|DOSSIER",
                    help="identifiant du plan (show, start) ou dossier d'entraînements (import)")
    pl.add_argument("--date", help="start : date de début AAAA-MM-JJ (défaut : aujourd'hui)")
    pl.add_argument("--name", help="import : nom du plan")
    pl.add_argument("--days", help="import : jours, par exemple mardi,jeudi,samedi ou jour1,jour3")
    pl.add_argument("--json", action="store_true", help="sortie JSON (list, show, today)")
    pl.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    pl.add_argument("--plans-dir", type=Path, help="dossier des plans (défaut : ~/OpenRide/Plans)")
    pl.add_argument("--workouts-dir", type=Path, help="bibliothèque (défaut : ~/OpenRide/Workouts)")
    pl.add_argument("--activities-dir", type=Path, help="séances (défaut : ~/OpenRide/Activities)")
    pl.add_argument("--state", type=Path, help="plan actif (défaut : ~/OpenRide/plan_state.toml)")
    ftp = sub.add_parser("ftp-test", help="résultat d'un test de FTP, enregistrement de la FTP, historique")
    ftp.add_argument("file", nargs="?", type=Path, help="journal .jsonl (défaut : dernier test trouvé)")
    ftp.add_argument("--accept", action="store_true", help="écrit la FTP proposée dans config.toml")
    ftp.add_argument("--force", action="store_true", help="avec --accept : accepte un résultat douteux")
    ftp.add_argument("--history", action="store_true", help="liste les tests trouvés dans les journaux")
    ftp.add_argument("--json", action="store_true", help="sortie JSON")
    ftp.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    ftp.add_argument("--dir", type=Path, dest="directory",
                     help="dossier des journaux (défaut : ~/OpenRide/Activities/.journal)")
    ows = sub.add_parser("open-world-save", help="enregistre une balade du monde ouvert comme parcours (GPX)")
    ows.add_argument("ride_id", metavar="ID", help="identifiant de la séance (ow-AAAAMMJJ-HHMMSS)")
    ows.add_argument("--km", type=float, help="distance parcourue en km (défaut : celle du journal, sinon toute la route)")
    ows.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    ows.add_argument("--gpx-dir", type=Path, help="dossier des traces (défaut : ~/OpenRide/GPX)")
    ows.add_argument("--journal-dir", type=Path, help="journaux (défaut : ~/OpenRide/Activities/.journal)")
    prf = sub.add_parser("profil", help="profils de joueurs : liste, création, renommage, corbeille ; "
                                        "profil d'essai (série MJ)")
    prf.add_argument("action", choices=["essai", "list", "create", "rename", "delete"])
    prf.add_argument("valeurs", nargs="*", metavar="ARG",
                     help="create NOM ; rename ID NOM ; delete ID")
    prf.add_argument("--vider", action="store_true",
                     help="efface séances, records, plan et équipement du profil d'essai (garde profil.toml)")
    prf.add_argument("--json", action="store_true", help="sortie JSON (progression)")
    prf.add_argument("--config", type=Path, help="config.toml (défaut : ~/OpenRide/config.toml)")
    for cmd in sub.choices.values():   # profil de joueur, sur toutes les sous-commandes (série MJ, lot MJ1)
        cmd.add_argument("--profil", metavar="ID",
                         help="profil de joueur ~/OpenRide/Profils/<ID>/ (défaut : $OPENRIDE_PROFIL, "
                              "sinon les dossiers de ~/OpenRide/ d'avant les profils)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run" and args.ftp_test:
        if args.workout:
            print("openride-core run : erreur : --workout et --ftp-test s'excluent", file=sys.stderr)
            raise SystemExit(2)
        args.workout = f"ftp_test:{args.ftp_test}"   # un test de FTP se roule comme un entraînement
    if args.command == "run" and not args.autostart:
        given = [opt for opt, val in (("--route", args.route), ("--workout", args.workout and not args.ftp_test),
                                      ("--ftp-test", args.ftp_test)) if val]
        if given:
            print(f"openride-core run : erreur : {' et '.join(given)} demande --autostart (sans lui,"
                  " l'engine choisit le parcours et l'entraînement)", file=sys.stderr)
            raise SystemExit(2)   # code d'argparse pour une ligne de commande refusée
    logging.basicConfig(level=logging.INFO, force=True,
                        format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    from . import profiles

    try:
        profiles.activate(profiles.resolve(args.profil))
    except profiles.ProfileContextError as exc:
        print(f"openride-core {args.command} : erreur : {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    return {"recover": cmd_recover, "run": cmd_run,
            "release-trainer": cmd_release_trainer, "summary": cmd_summary, "session-report": cmd_session_report, "xp": cmd_xp,
            "fit-check": cmd_fit_check,
            "history": cmd_history, "devices": cmd_devices,
            "plan": cmd_plan, "settings": cmd_settings, "ftp-test": cmd_ftp_test,
            "open-world-save": cmd_open_world_save, "profil": cmd_profil}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
