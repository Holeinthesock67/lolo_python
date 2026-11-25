"""Rappel de la manche de la ligue d'hiver (série CH, lot CH7) : notification bureau le samedi à 18 h et le
dimanche à midi quand la manche de la semaine n'est pas courue (choix du propriétaire du 24 novembre 2026).

Lancé par un minuteur systemd de l'utilisateur (`scripts/install-rappel-ligue.sh`), même quand OpenRide est fermé :

    python -m openride_core.league_reminder              # profil par défaut, notification si la manche attend
    python -m openride_core.league_reminder --essai      # affiche le texte sans notifier (rien n'est écrit)

Lecture seule : `ligue.json` du profil n'est jamais réécrit (la saison avance quand le core l'ouvre). Pas de
rappel en dehors du samedi et du dimanche : un minuteur rattrapé le lundi (PC éteint le dimanche) ne parle pas de
la semaine nouvelle. Le cycliste coupe le rappel en retirant le minuteur (`install-rappel-ligue.sh --uninstall`).
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from . import league, profiles

log = logging.getLogger("openride.rappel_ligue")

TITLE = "OpenRide : ligue d'hiver"
SATURDAY, SUNDAY = 5, 6   # `date.weekday()`


def due_text(season: league.Season | None, today: date) -> str | None:
    """Texte du rappel (mots écrits), None sans rappel : pas de saison, saison close ou en pause, manche faite,
    jour qui n'est ni samedi ni dimanche."""
    if season is None or today.weekday() not in (SATURDAY, SUNDAY):
        return None
    index = season.current_round(today)
    if index is None:
        return None
    rnd = league.ROUNDS[index]
    when = "avant demain soir" if today.weekday() == SATURDAY else "avant ce soir, dernier jour"
    return f"Manche {index + 1} sur {league.WEEKS} ({rnd.short}) à courir {when}. Elle compte au bilan."


def read_season(path: Path) -> league.Season | None:
    """Saison du fichier, sans jamais le toucher (`league.load` met de côté un fichier illisible : ici, un fichier
    en cours d'écriture par le core, ou abîmé, donne seulement « pas de rappel »)."""
    try:
        return league.Season.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def league_path(profile_id: str | None = None) -> Path:
    """`ligue.json` du profil `profile_id` (défaut : celui que le core prendrait au lancement)."""
    ctx = profiles.resolve(profile_id)
    records = ctx.records_path if ctx is not None else profiles.ProfileContext.legacy().records_path
    return records.with_name(league.FILE_NAME)


def notify(text: str) -> bool:
    """Notification bureau (`notify-send`) ; faux si l'outil manque ou échoue (rien d'autre n'est tenté)."""
    tool = shutil.which("notify-send")
    if tool is None:
        log.warning("Rappel de la ligue : notify-send introuvable (paquet libnotify-bin).")
        return False
    try:
        subprocess.run([tool, "--app-name=OpenRide", "--icon=openride", TITLE, text], check=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Rappel de la ligue : notification refusée : %s", exc)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openride-rappel-ligue", description=__doc__.splitlines()[0])
    parser.add_argument("--profil", default=None, help="profil de joueur (défaut : celui du lancement)")
    parser.add_argument("--jour", default=None, help="jour AAAA-MM-JJ à la place d'aujourd'hui (essais)")
    parser.add_argument("--essai", action="store_true", help="affiche le texte sans notifier")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        today = date.fromisoformat(args.jour) if args.jour else datetime.now().date()
        path = league_path(args.profil)
    except (ValueError, profiles.ProfileContextError) as exc:
        log.error("Rappel de la ligue : %s", exc)
        return 2
    text = due_text(read_season(path), today)
    if text is None:
        log.info("Rappel de la ligue : rien à rappeler (%s, %s).", today.isoformat(), path)
        return 0
    print(text)
    if not args.essai:
        notify(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
