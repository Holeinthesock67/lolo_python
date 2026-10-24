"""Outils en ligne de commande pour les entraînements ERG (`.zwo`, Lot H8, SRS §6).

Commandes :
- ``python -m openride_core.tools.workouts list [--dir D]``
- ``python -m openride_core.tools.workouts check FICHIER.zwo [--ftp W]``
- ``python -m openride_core.tools.workouts install [--dir D]``

Estimation de charge dans ``check`` :
La puissance normalisée approchée (NP), le facteur d'intensité (IF) et le score de charge
d'entraînement (TSS) sont calculés par échantillonnage à 1 s sur les blocs de l'entraînement
(sans fenêtre glissante de 30 s) :
- ``NP = (moyenne(P(t)^4))^(1/4)`` (0 W pendant les blocs ``freeride``) ;
- ``IF = NP / FTP`` ;
- ``TSS = (durée_s * NP * IF) / (FTP * 3600) * 100``.
"""

from __future__ import annotations

import argparse
import logging
import math
import shutil
import sys
from pathlib import Path

from .. import config as config_mod
from ..config import WORKOUTS_DIR
from ..workout import Workout, WorkoutError, list_workouts, load_workout

BUILTIN_WORKOUTS_DIR = Path(__file__).resolve().parents[3] / "workouts"


def format_hms(seconds: float) -> str:
    total = int(round(max(seconds, 0.0)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def estimate_metrics(workout: Workout, ftp_w: float) -> dict[str, float]:
    """Calcule la puissance moyenne, NP approchée (paliers de 1 s sans lissage 30 s), IF et TSS."""
    samples_w: list[float] = []
    for blk in workout.blocks:
        dur = max(int(round(blk.duration_s)), 1)
        for sec in range(dur):
            frac = blk.frac_at(sec + 0.5)
            w = ftp_w * frac if frac is not None else 0.0
            samples_w.append(w)

    if not samples_w or ftp_w <= 0:
        return {"avg_w": 0.0, "np_w": 0.0, "if": 0.0, "tss": 0.0}

    avg_w = sum(samples_w) / len(samples_w)
    mean_p4 = sum(w**4 for w in samples_w) / len(samples_w)
    np_w = mean_p4**0.25
    intensity_factor = np_w / ftp_w
    tss = (workout.duration_s * np_w * intensity_factor) / (ftp_w * 3600.0) * 100.0
    return {
        "avg_w": round(avg_w, 1),
        "np_w": round(np_w, 1),
        "if": round(intensity_factor, 2),
        "tss": round(tss, 1),
    }


class _WarningCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def cmd_list(args: argparse.Namespace) -> int:
    directory = Path(args.dir).expanduser()
    items = list_workouts(directory)
    if not items:
        print(f"Aucun entraînement dans {directory}")
        return 0

    print(f"{'ID':<20} {'Nom':<28} {'Durée':>8} {'Blocs':>6}  État")
    print("-" * 76)
    for info in items:
        status = "ok" if info.selectable else f"erreur : {info.error}"
        dur_str = format_hms(info.duration_s) if info.selectable else "-"
        n_blocks = str(len(info.profile)) if info.selectable else "-"
        print(f"{info.id:<20} {info.name:<28} {dur_str:>8} {n_blocks:>6}  {status}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.file).expanduser()
    if args.ftp is not None:
        ftp_w = float(args.ftp)
    else:
        try:
            ftp_w = float(config_mod.load().rider.ftp_w)
        except config_mod.ConfigError as exc:
            print(f"configuration invalide : {exc} (utiliser --ftp)", file=sys.stderr)
            return 1
    if not (math.isfinite(ftp_w) and ftp_w > 0):
        print(f"FTP invalide : {ftp_w:g} (attendu : un nombre de watts positif)", file=sys.stderr)
        return 1

    w_logger = logging.getLogger("workout")
    collector = _WarningCollector()
    w_logger.addHandler(collector)
    try:
        workout = load_workout(path)
    except WorkoutError as exc:
        print(f"Erreur ({path.name}) : {exc}", file=sys.stderr)
        return 1
    finally:
        w_logger.removeHandler(collector)

    metrics = estimate_metrics(workout, ftp_w)
    print(
        f"{workout.name} ({workout.id}) — {len(workout.blocks)} blocs, "
        f"{workout.duration_s:.0f} s ({format_hms(workout.duration_s)}), FTP {ftp_w:.0f} W"
    )
    for idx, blk in enumerate(workout.blocks, start=1):
        if blk.start_frac is None or blk.end_frac is None:
            target_str = "roue libre (SIM)"
        elif blk.start_frac == blk.end_frac:
            w = round(ftp_w * blk.start_frac)
            target_str = f"{w} W ({blk.start_frac * 100:.0f} %)"
        else:
            w0 = round(ftp_w * blk.start_frac)
            w1 = round(ftp_w * blk.end_frac)
            target_str = f"{w0} -> {w1} W ({blk.start_frac * 100:.0f} -> {blk.end_frac * 100:.0f} %)"
        print(f"  {idx:>2}. {blk.type:<12} {blk.duration_s:>6.0f} s   {target_str}")

    print(
        f"Estimations : Pmoy {metrics['avg_w']:.0f} W, NP {metrics['np_w']:.0f} W, "
        f"IF {metrics['if']:.2f}, TSS {metrics['tss']:.0f}"
    )
    if collector.messages:
        print(f"Avertissements ({len(collector.messages)}) :")
        for msg in collector.messages:
            print(f"  - {msg}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    target_dir = Path(args.dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)

    sources = sorted(BUILTIN_WORKOUTS_DIR.glob("*.zwo"))
    copied: list[str] = []
    skipped: list[str] = []

    for src in sources:
        dst = target_dir / src.name
        if dst.exists():
            skipped.append(src.name)
        else:
            shutil.copy2(src, dst)
            copied.append(src.name)

    print(
        f"Installation dans {target_dir} : "
        f"{len(copied)} copié(s) ({', '.join(copied) or 'aucun'}), "
        f"{len(skipped)} conservé(s) sans écrasement ({', '.join(skipped) or 'aucun'})."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m openride_core.tools.workouts",
        description="Outils de gestion et vérification des entraînements ERG (.zwo).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="liste les entraînements d'un dossier")
    p_list.add_argument(
        "--dir",
        type=Path,
        default=WORKOUTS_DIR,
        help=f"Dossier des entraînements (défaut : {WORKOUTS_DIR})",
    )

    p_check = sub.add_parser("check", help="valide et détaille un fichier .zwo")
    p_check.add_argument("file", type=Path, help="Fichier .zwo à vérifier")
    p_check.add_argument("--ftp", type=float, default=None, help="FTP en watts (défaut : config.toml)")

    p_install = sub.add_parser("install", help="copie la bibliothèque d'entraînements de référence")
    p_install.add_argument(
        "--dir",
        type=Path,
        default=WORKOUTS_DIR,
        help=f"Dossier cible (défaut : {WORKOUTS_DIR})",
    )

    args = parser.parse_args(argv)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "check":
        return cmd_check(args)
    if args.command == "install":
        return cmd_install(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
