"""Séances guidées sur le HomeTrainer : consignes et bips à l'écran, relevés notés tout seuls.

Écrit deux parcours synthétiques (même montée douce de 1 à 4 % que `demo`, terrain compris) et les
consignes que l'engine affiche pendant la séance (`engine/scripts/cue_model.gd`) :

- `recette-velo` : séance libre en SIM de 25 min (HUD, appuis du Click, appuis longs, pause par Y,
  curseur de difficulté, ceinture retirée puis remise, roue libre, sprint) ;
- `recette-erg` : séance ERG de 13 min avec l'entraînement `recette_erg.zwo`, écrit dans le dossier des
  entraînements (biais ± 2 %, bip à T − 3 s, pause par Y, bilan).

Les consignes tombent au temps de séance (horloge du core, arrêtée en pause). Celles qui demandent du
matériel sont annoncées une minute avant (« Dans 1 min, prépare … »), avec un bip. À chaque consigne,
le journal du lanceur reçoit une ligne `[essai]` avec le temps, la puissance, la cadence, la FC, le
braquet et la pente envoyée : rien n'est à chronométrer à la main.

    python -m openride_core.tools.seance_guidee              # écrit les parcours, les consignes, l'entraînement
    python -m openride_core.tools.seance_guidee --materiel   # matériel à préparer et durée, sans rien écrire
    python -m openride_core.tools.seance_guidee --retirer    # efface ce que l'outil a écrit

Puis, dans OpenRide : « Monde » → `recette-velo` → « Session libre » ; ou « Monde » → `recette-erg` →
« Session ERG » → « Recette ERG guidée ». Origine fictive (même point que `demo`) : aucune donnée personnelle.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .. import config
from ..demo_world import write_world
from .fake_world import add_terrain_layer

ESSAIS_DIR = config.OPENRIDE_HOME / "Essais"
CREATED = "2026-10-26T12:00:00+01:00"
ERG_WORKOUT = "recette_erg"

# Consigne : (temps de séance en s, texte, durée d'affichage en s, à préparer ou "").
SIM_CUES: list[tuple[float, str, float, str]] = [
    (0, "Échauffement 5 min, cadence libre. Lis le HUD : puissance, cadence, FC, braquet", 40, ""),
    (300, "10 appuis courts sur +, un toutes les 2 s (un bip par appui, résistance plus dure)", 25, ""),
    (330, "10 appuis courts sur − (si le boîtier gauche se tait : B du boîtier droit)", 25, ""),
    (360, "Un appui long sur +, puis un appui long sur − (braquet ± 10)", 25, ""),
    (420, "Boutons A puis Z du Click : sans effet en séance (avec la PR #287)", 20, ""),
    (480, "Y : pause. Difficulté de 50 à 40 % si le curseur est là (PR #248), puis Y pour reprendre", 40, ""),
    (660, "Retire la ceinture 30 s : la FC reste figée (normal, relais du trainer)", 30,
     "la ceinture cardio (à retirer)"),
    (690, "Remets la ceinture : la FC doit repartir", 25, ""),
    (720, "Montée : change de braquet à chaque bip pendant 5 min", 20, ""),
    (780, "Un braquet plus dur", 10, ""),
    (840, "Un braquet plus facile", 10, ""),
    (900, "Deux braquets plus durs", 10, ""),
    (960, "Deux braquets plus faciles", 10, ""),
    (1020, "Roue libre 15 s, puis repédale", 20, ""),
    (1080, "Sprint 10 s à fond !", 15, "un sprint de 10 s"),
    (1140, "Retour au calme 4 min", 20, ""),
    (1380, "Dernière minute. À 25 min : Y, puis « Terminer et enregistrer », et lis le bilan", 40,
     "la fin de séance (bilan à lire)"),
]

ERG_CUES: list[tuple[float, str, float, str]] = [
    (0, "ERG : la puissance est imposée, ne change pas de braquet. Bandeau : tous les blocs visibles", 40, ""),
    (60, "Appui court + : intensité + 2 % (affichée au bandeau)", 20, ""),
    (90, "Deux appuis courts − : intensité − 2 %", 20, ""),
    (165, "Écoute : bip 3 s avant le changement de bloc (à 3 min)", 20, ""),
    (240, "Effort : cible tenue par le trainer, cadence 85 à 95", 25, ""),
    (330, "Récupération. Y : pause 10 s (le trainer se relâche), puis Y pour reprendre", 30, "une pause de 10 s"),
    (400, "Deuxième effort : garde la même cadence", 20, ""),
    (600, "Retour au calme 3 min", 20, ""),
    (720, "Dernière minute. À la fin : bilan, cible et écart par bloc", 30, "la fin de séance (bilan à lire)"),
]

# 13 min : échauffement 3 min, 2 × (2 min à 100 %, 1 min 30 à 50 %), retour au calme 3 min.
ERG_ZWO = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <author>OpenRide</author>
    <name>Recette ERG guidée</name>
    <description>Séance d'essai de 13 min : échauffement 3 min, 2 × 2 min à 100 % FTP avec 1 min 30 à 50 %, retour au calme 3 min.</description>
    <sportType>bike</sportType>
    <workout>
        <Warmup Duration="180" PowerLow="0.50" PowerHigh="0.65"/>
        <IntervalsT Repeat="2" OnDuration="120" OffDuration="90" OnPower="1.00" OffPower="0.50"/>
        <Cooldown Duration="180" PowerLow="0.55" PowerHigh="0.45"/>
    </workout>
</workout_file>
"""

# Parcours : (identifiant, longueur en m, consignes, durée prévue en min).
SESSIONS = [("recette-velo", 20_000.0, SIM_CUES, 25), ("recette-erg", 12_000.0, ERG_CUES, 13)]

MATERIEL = """Séances guidées sur le HomeTrainer : à préparer

Avant les deux séances (5 min) :
- vélo sur le HomeTrainer, Bluetooth du PC allumé, aucune autre application reliée au trainer ;
- les deux boîtiers du Click réveillés (un appui sur chacun), pile de secours CR2032 à portée ;
- ceinture cardio humidifiée et portée ; bidon et serviette ;
- écran visible depuis le vélo, son du PC audible (bips des consignes et de l'ERG) ;
- FTP et poids à jour dans les réglages (l'ERG calcule ses cibles sur la FTP).

recette-velo, séance libre en SIM : 25 min.
  Préavis d'une minute avant de retirer la ceinture (11 min), avant le sprint (18 min) et avant la fin (23 min).
recette-erg, séance ERG : 13 min.
  Préavis d'une minute avant la pause (5 min 30) et avant la fin (12 min).

Rien à chronométrer : chaque consigne écrit une ligne « [essai] » (temps, puissance, cadence, FC,
braquet, pente envoyée) dans le journal du lanceur, ~/OpenRide/Logs/openride_<date>.log.
Après la séance : python -m openride_core.tools.log_report ; openride-core summary
"""


def cues_json(cues: list[tuple[float, str, float, str]]) -> dict:
    out = []
    for at_s, text, duration_s, prepare in cues:
        cue: dict = {"at_s": at_s, "text": text, "duration_s": duration_s}
        if prepare:
            cue["prepare"] = prepare
            cue["warn_s"] = 60
        out.append(cue)
    return {"cues": out}


def write_all(routes_dir: Path, essais_dir: Path, workouts_dir: Path, terrain: bool = True) -> list[Path]:
    written: list[Path] = []
    for name, length_m, cues, _ in SESSIONS:
        world = routes_dir / f"{name}.world"
        if world.exists():
            shutil.rmtree(world)
        write_world(routes_dir, name, length_m, created=CREATED)
        if terrain:
            add_terrain_layer(world)
        written.append(world)
        path = essais_dir / f"{name}.consignes.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cues_json(cues), ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(path)
    zwo = workouts_dir / f"{ERG_WORKOUT}.zwo"
    zwo.parent.mkdir(parents=True, exist_ok=True)
    zwo.write_text(ERG_ZWO, encoding="utf-8")
    written.append(zwo)
    return written


def remove_all(routes_dir: Path, essais_dir: Path, workouts_dir: Path) -> list[Path]:
    removed: list[Path] = []
    for name, *_ in SESSIONS:
        for path in (routes_dir / f"{name}.world", essais_dir / f"{name}.consignes.json"):
            if path.is_dir():
                shutil.rmtree(path)
                removed.append(path)
            elif path.is_file():
                path.unlink()
                removed.append(path)
    zwo = workouts_dir / f"{ERG_WORKOUT}.zwo"
    if zwo.is_file():
        zwo.unlink()
        removed.append(zwo)
    return removed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--materiel", action="store_true", help="matériel à préparer et durées, sans rien écrire")
    p.add_argument("--retirer", action="store_true", help="efface les parcours, consignes et entraînement écrits")
    p.add_argument("--routes-dir", type=Path, default=config.ROUTES_DIR)
    p.add_argument("--essais-dir", type=Path, default=ESSAIS_DIR)
    p.add_argument("--workouts-dir", type=Path, default=config.WORKOUTS_DIR)
    p.add_argument("--sans-terrain", action="store_true", help="route seule (plus rapide)")
    args = p.parse_args(argv)
    if args.materiel:
        print(MATERIEL, end="")
        return 0
    if args.retirer:
        removed = remove_all(args.routes_dir, args.essais_dir, args.workouts_dir)
        print("\n".join(f"Effacé : {path}" for path in removed) or "Rien à effacer.")
        return 0
    for path in write_all(args.routes_dir, args.essais_dir, args.workouts_dir, terrain=not args.sans_terrain):
        print(f"Écrit : {path}")
    print()
    print(MATERIEL, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
