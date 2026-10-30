"""Recette guidée de la série V (lot V10) : progression, équipement et avatar, en une commande.

    python -m openride_core.tools.recette_v10              # tout : prépare, roule les 2 blocs, bilan, restaure
    python -m openride_core.tools.recette_v10 materiel     # ce qu'il faut avoir sous la main, durées

Déroulé de la commande seule (environ 30 min, le propriétaire n'a qu'à pédaler) :
  1. sans vélo : sauvegarde de `config.toml` et `profile.json`, deux parcours plats identiques avec leurs
     consignes, expérience recalculée, profil effacé puis remis ;
  2. bloc 1 : vélo de départ posé dans le profil, OpenRide lancé directement en séance (`--autostart`) sur
     `recette-v10-depart` ; l'outil suit le journal et ferme OpenRide à 10 min de séance (séance enregistrée) ;
  3. pause de 2 min : cadre et roues aéro posés dans le profil (sans achat), compte à rebours et bips ;
  4. bloc 2 : même chose sur `recette-v10-equipe` ;
  5. bilan lu dans les journaux (équipement de l'en-tête, vitesse à puissance égale, pente envoyée à
     braquet égal, temps gagné recalculé, expérience), puis restauration du profil et retrait des parcours,
     même après Ctrl+C.
Dans le jeu, les consignes (`cue_model.gd`) annoncent chaque geste une minute avant et restent 20 à 45 s.
Le Garage au Click n'est pas recetté ici : le banc des menus (`menu_bench`) le couvre.
Les étapes se lancent aussi une à une : `pc`, `bilan`, `restaurer`.

Rien n'est écrit dans le dépôt ; parcours fictifs (même origine que `demo`), aucune donnée personnelle.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config
from ..demo_world import write_world
from ..journal import read_journal
from .fake_world import add_terrain_layer
from .seance_guidee import CREATED, ESSAIS_DIR, cues_json

RECETTE = "recette-v10"                      # dossier de la recette sous ~/OpenRide/Essais
BACKUP = "sauvegarde"                        # copies de config.toml et profile.json d'avant la recette
TRIAL_MARK = "profil_essai"                  # présent tant que l'outil a changé le vélo du profil
ROUTE_LENGTH_M = 12_000.0
SPRINTS_M = (1500.0, 3000.0, 4500.0)         # trois sprints de 400 m : un temps gagné par passage
SPRINT_LENGTH_M = 400.0
BLOCK_S = 600
PAUSE_S = 120                                # entre les blocs, sans pédaler
GET_READY_S = 60                             # avant le bloc 1 : monter sur le vélo
BLOCK_MAX_S = 30 * 60                        # garde-fou : OpenRide fermé quoi qu'il arrive
LAUNCH_WAIT_S = 180                          # pas de journal après ce délai : lancement raté

# Cadre et roues du bloc 2, les plus aéro du catalogue (lot V3), posés sans achat.
AERO_FRAMES = ("frame_tt", "frame_aero")
AERO_WHEELS = ("wheels_disc", "wheels_deep")
AERO_LOADOUT = {"frame": AERO_FRAMES[0], "wheels": AERO_WHEELS[0]}

# Consigne : (temps de séance en s, texte, durée d'affichage en s, à préparer ou "").
BLOCK1_CUES: list[tuple[float, str, float, str]] = [
    (0, ("Bloc 1 sur 2, vélo de départ. Roule 10 min à puissance régulière (endurance) : "
         "retiens ta puissance, tu la referas au bloc 2"), 40, ""),
    (60, "Caméra : A (ou flèche haut) passe à la vue suivante. Une vue toutes les 20 s, 4 vues", 40, ""),
    (150, "Vue de suivi proche (A jusqu'à la retrouver) : regarde le pédalage de l'avatar", 30, ""),
    (210, "Cadence 60 tr/min pendant 30 s : les jambes ralentissent", 35, ""),
    (270, "Cadence 100 tr/min pendant 30 s : les jambes accélèrent", 35, ""),
    (330, "Retour à ta puissance d'endurance, cadence habituelle", 25, ""),
    (420, "Sprint 10 s à fond : l'avatar se met en danseuse", 20, "un sprint de 10 s"),
    (450, "Reprends ta puissance d'endurance jusqu'à la fin", 25, ""),
    (540, "Dernière minute. À 10 min, la séance s'arrête et s'enregistre toute seule", 45, ""),
]

BLOCK2_CUES: list[tuple[float, str, float, str]] = [
    (0, "Bloc 2 sur 2, cadre et roues aéro déjà posés. Même puissance qu'au bloc 1, même cadence", 40, ""),
    (60, "Compare : la vitesse doit être un peu plus haute qu'au bloc 1, la résistance la même", 40, ""),
    (240, "Toujours la même puissance. Au sprint (vers 3 km) : « temps gagné » sous le chrono du segment", 40, ""),
    (420, "Ressenti : la résistance du trainer est-elle la même qu'au bloc 1 ?", 40, ""),
    (540, "Dernière minute. À 10 min, la séance s'arrête ; le verdict s'affiche au terminal", 45, ""),
]

SESSIONS = (("recette-v10-depart", BLOCK1_CUES), ("recette-v10-equipe", BLOCK2_CUES))

MATERIEL = """Recette V10 (progression, équipement, avatar) : environ 30 min, une seule commande

  python -m openride_core.tools.recette_v10

À avoir avant de lancer :
- vélo sur le HomeTrainer, Bluetooth du PC allumé, aucune autre application reliée au trainer ;
- les deux boîtiers du Click réveillés (le clavier fait aussi l'affaire : A ou flèche haut) ;
- écran visible depuis le vélo, son du PC audible (bip à chaque consigne, préavis d'une minute) ;
- bidon et serviette.

L'outil fait tout le reste : sauvegarde, parcours, essais sans vélo (3 min), lancement et arrêt d'OpenRide
pour chaque bloc, vélo aéro posé pendant la pause, bilan, restauration.
Tes gestes : pédaler à puissance régulière ; 60 puis 100 tr/min, 30 s chacun ; un sprint de 10 s ;
au bloc 1, quatre appuis sur A pour voir les vues de caméra. Chaque geste est annoncé une minute avant.
Au bloc 2, même puissance qu'au bloc 1.

Hors vélo, dans la file des mesures du PC : banc par vue de caméra en low, medium et high (au moins 55 images/s
en low), engine/tests/sim_bench.py --native --quality low --camera follow_near (puis follow_far, side).
"""


# --- préparation -------------------------------------------------------------------------------

def sprint_segments() -> list[dict]:
    return [{"id": f"sprint{i}", "name": f"Sprint {i}", "type": "sprint", "s_start": s, "s_end": s + SPRINT_LENGTH_M,
             "length_m": SPRINT_LENGTH_M, "avg_grade_pct": 0.0, "gain_m": 0.0, "category": None, "source": "auto"}
            for i, s in enumerate(SPRINTS_M, 1)]


def write_route(routes_dir: Path, name: str, terrain: bool = True) -> Path:
    """Parcours plat de 12 km, trois sprints de 400 m dans les 5 premiers km (passés en 10 min)."""
    world = routes_dir / f"{name}.world"
    if world.exists():
        shutil.rmtree(world)
    write_world(routes_dir, name, ROUTE_LENGTH_M, created=CREATED, grade=lambda s: 0.0)
    segments = sprint_segments()
    (world / "segments.json").write_text(
        json.dumps({"version": "1.0", "segments": segments}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = json.loads((world / "manifest.json").read_text(encoding="utf-8"))
    manifest["layers"]["segments"]["count"] = len(segments)
    (world / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if terrain:
        add_terrain_layer(world)
    return world


def write_all(routes_dir: Path, essais_dir: Path, terrain: bool = True) -> list[Path]:
    written: list[Path] = []
    for name, cues in SESSIONS:
        written.append(write_route(routes_dir, name, terrain))
        path = essais_dir / f"{name}.consignes.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cues_json(cues), ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(path)
    return written


def remove_all(routes_dir: Path, essais_dir: Path) -> list[Path]:
    """Retire les deux parcours et leurs consignes (les journaux des séances restent)."""
    removed: list[Path] = []
    for name, _ in SESSIONS:
        world, cues = routes_dir / f"{name}.world", essais_dir / f"{name}.consignes.json"
        if world.is_dir():
            shutil.rmtree(world)
            removed.append(world)
        if cues.is_file():
            cues.unlink()
            removed.append(cues)
    return removed


def backup(files: list[Path], backup_dir: Path) -> list[Path]:
    """Copie chaque fichier existant dans `backup_dir` (une seule fois : une copie déjà faite est gardée)."""
    saved: list[Path] = []
    backup_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        dest = backup_dir / f.name
        if f.is_file() and not dest.exists():
            shutil.copy2(f, dest)
            saved.append(dest)
    return saved


def base_loadout() -> dict[str, str]:
    from ..profile import DEFAULT_EQUIPPED

    return {"frame": DEFAULT_EQUIPPED["frame"], "wheels": DEFAULT_EQUIPPED["wheels"]}


def set_bike(profile_path: Path, loadout: dict[str, str], recette_dir: Path) -> None:
    """Pose cadre et roues dans le profil, sans achat (profil d'origine sauvegardé, remis par `restore`)."""
    from ..profile import load_profile, save_profile

    profile = load_profile(profile_path)
    profile.equipped.update(loadout)
    save_profile(profile, profile_path)
    recette_dir.mkdir(parents=True, exist_ok=True)
    (recette_dir / TRIAL_MARK).write_text("vélo du profil changé par recette_v10\n", encoding="utf-8")


def restore(profile_path: Path, routes_dir: Path, essais_dir: Path) -> list[str]:
    """Profil d'avant la recette remis (retiré s'il n'y en avait pas), parcours et consignes retirés."""
    recette_dir = essais_dir / RECETTE
    saved, mark = recette_dir / BACKUP / profile_path.name, recette_dir / TRIAL_MARK
    done: list[str] = []
    if mark.is_file():
        if saved.is_file():
            shutil.copy2(saved, profile_path)
            done.append(f"Profil remis : {profile_path}")
        else:   # pas de profil avant la recette : on revient à « pas de profil »
            profile_path.unlink(missing_ok=True)
            done.append(f"Profil d'essai retiré : {profile_path}")
        mark.unlink()
    done += [f"Retiré : {path}" for path in remove_all(routes_dir, essais_dir)]
    return done


# --- essais sans vélo ------------------------------------------------------------------------

def check_xp(svc: Any) -> tuple[bool, list[str]]:
    """Expérience recalculée : séances comptées et refusées, avec la raison."""
    progress = svc.progress
    refused: dict[str, int] = {}
    for r in progress.sessions:
        if r.reason:
            refused[r.reason] = refused.get(r.reason, 0) + 1
    lines = [f"Niveau {progress.level.level}, {progress.total_xp} points, {len(progress.counted)} séance(s) comptée(s)."]
    names = {"replay": "rejeu", "simulated": "simulée", "too_short": "moins de 5 min"}
    if refused:
        lines.append("Refusées : " + ", ".join(f"{n} {names.get(k, k)}" for k, n in sorted(refused.items())) + ".")
    if progress.errors:
        lines.append(f"{len(progress.errors)} journal(aux) illisible(s) : " + ", ".join(n for n, _ in progress.errors[:3]))
    return not progress.errors, lines


def check_profile_reset(make_service: Any, profile_path: Path, backup_dir: Path) -> tuple[bool, list[str]]:
    """Profil effacé : niveau et pièces gagnées identiques, choix revenus aux défauts ; le profil est remis."""
    from ..coins import earned_coins
    from ..profile import DEFAULT_EQUIPPED

    before = make_service()
    level, earned = before.progress.level.level, earned_coins(before.progress, before.ct)
    moved = backup_dir / "profile.json.pendant_essai"
    had = profile_path.is_file()
    if had:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(profile_path), moved)
    try:
        after = make_service()
        same_level = after.progress.level.level == level
        same_coins = earned_coins(after.progress, after.ct) == earned
        defaults = dict(after.profile.equipped) == dict(DEFAULT_EQUIPPED)
    finally:
        if had:
            shutil.move(str(moved), profile_path)
    ok = same_level and same_coins and defaults
    return ok, [(f"Sans profil : niveau {after.progress.level.level} (avant {level}), pièces gagnées "
                 f"{earned_coins(after.progress, after.ct)} (avant {earned}), choix par défaut : "
                 f"{'oui' if defaults else 'non'}. Profil remis en place.")]


# --- bilan après les deux blocs --------------------------------------------------------------

@dataclass
class Block:
    journal: Path
    route_id: str
    loadout: dict | None
    minutes: float
    avg_power_w: float
    avg_speed_kmh: float
    grade_sent: dict            # braquet -> (pente envoyée au trainer moyenne en %, nombre de relevés)
    records: list[dict]


def read_block(path: Path) -> Block | None:
    header: dict = {}
    records: list[dict] = []
    for line in read_journal(path):
        if line.get("kind") == "header":
            header = line
        elif line.get("kind") == "record":
            records.append(line)
    if not records:
        return None
    moving = [r for r in records if (r.get("speed") or 0.0) > 1.0 and (r.get("power") or 0.0) > 0.0]
    if not moving:
        return None
    sent: dict = {}
    for r in moving:
        if r.get("grade_sent") is not None:
            total, n = sent.get(r.get("gear"), (0.0, 0))
            sent[r.get("gear")] = (total + float(r["grade_sent"]), n + 1)
    return Block(path, str(header.get("route_id")), header.get("loadout"), len(records) / 60.0,
                 sum(float(r["power"]) for r in moving) / len(moving),
                 3.6 * sum(float(r["speed"]) for r in moving) / len(moving),
                 {g: (total / n, n) for g, (total, n) in sent.items()}, records)


def last_blocks(journal_dir: Path) -> dict[str, Block]:
    """Dernière séance de chaque parcours de la recette."""
    out: dict[str, Block] = {}
    for path in sorted(journal_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
        name = None
        try:
            for line in read_journal(path):
                if isinstance(line, dict) and line.get("kind") == "header":
                    name = line.get("route_id")
                break
        except (OSError, UnicodeDecodeError):
            continue
        if name in dict(SESSIONS):
            block = read_block(path)
            if block is not None:
                out[name] = block
    return out


def verdict(blocks: dict[str, Block], plain: Any, equipped: Any) -> tuple[bool, list[str]]:
    """Comparaison des deux blocs ; `plain` et `equipped` : `PhysicsParams` sans et avec l'équipement du bloc 2."""
    from ..equipment import equipment_time_gain

    a, b = blocks.get("recette-v10-depart"), blocks.get("recette-v10-equipe")
    if a is None or b is None:
        missing = [n for n, _ in SESSIONS if n not in blocks]
        return False, [f"Bloc manquant dans les journaux : {', '.join(missing)}."]
    lines, ok = [], True
    for label, blk in (("Bloc 1", a), ("Bloc 2", b)):
        lo = blk.loadout or {}
        lines.append(f"{label} : {blk.minutes:.1f} min, {blk.avg_power_w:.0f} W, {blk.avg_speed_kmh:.1f} km/h, "
                     f"cadre {lo.get('frame')}, roues {lo.get('wheels')}.")
    same_kit = (a.loadout or {}).get("frame") == (b.loadout or {}).get("frame") \
        and (a.loadout or {}).get("wheels") == (b.loadout or {}).get("wheels")
    if same_kit:
        ok = False
        lines.append("ÉCHEC : même cadre et mêmes roues dans les deux blocs (Garage non pris en compte ?).")
    if abs(b.avg_power_w - a.avg_power_w) > 0.10 * a.avg_power_w:
        lines.append("Attention : puissances moyennes à plus de 10 % l'une de l'autre, comparaison de vitesse peu sûre.")
    # Vitesse à puissance égale : la vitesse du plat varie comme la racine cubique de la puissance.
    ratio = (b.avg_speed_kmh / a.avg_speed_kmh) / (b.avg_power_w / a.avg_power_w) ** (1.0 / 3.0)
    faster = ratio > 1.0
    ok &= faster or same_kit
    lines.append(f"{'OK' if faster else 'ÉCHEC'} : vitesse à puissance égale {100.0 * (ratio - 1.0):+.1f} % au bloc 2.")
    # Pente envoyée comparée à braquet égal : le braquet la change, l'équipement ne doit pas la changer.
    gears = [g for g in a.grade_sent if g in b.grade_sent and min(a.grade_sent[g][1], b.grade_sent[g][1]) >= 30]
    if gears:
        g = max(gears, key=lambda k: a.grade_sent[k][1] + b.grade_sent[k][1])
        ga, gb = a.grade_sent[g][0], b.grade_sent[g][0]
        same_feel = abs(ga - gb) < 0.2
        ok &= same_feel
        lines.append(f"{'OK' if same_feel else 'ÉCHEC'} : pente envoyée au trainer au braquet {g} : {ga:.2f} % puis "
                     f"{gb:.2f} % (même résistance attendue).")
    else:
        lines.append("Pente envoyée non comparée : aucun braquet tenu 30 s dans les deux blocs.")
    gain = equipment_time_gain(b.records, equipped, plain)
    if gain is not None:
        lines.append(f"{'OK' if gain < 0 else 'ÉCHEC'} : temps gagné par l'équipement sur le bloc 2 recalculé : "
                     f"{gain:+.0f} s (le bilan à l'écran doit dire la même chose).")
        ok &= gain < 0
    return ok, lines


# --- blocs sur le vélo -------------------------------------------------------------------------

def launch_command(route_id: str, config_path: Path | None) -> list[str]:
    """OpenRide par son lanceur (core, engine, libération du trainer), séance démarrée sur `route_id`."""
    cfg_args = ["--config", str(config_path)] if config_path is not None else []
    return [sys.executable, "-m", "openride_core.launcher", "--no-compile", "--trainer", "ftms", "--input", "click",
            *cfg_args, "--autostart", "--route", route_id]


def last_record(path: Path) -> dict | None:
    """Dernier relevé d'un journal en cours d'écriture (lecture de la fin du fichier seulement)."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(fh.tell() - 4096, 0))
            tail = fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(tail):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("kind") == "record":
            return obj
    return None


def new_journal(journal_dir: Path, since: float, route_id: str) -> Path | None:
    """Journal du bloc : modifié après le lancement, en-tête sur `route_id`."""
    for path in sorted(journal_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.stat().st_mtime < since:
            break
        try:
            with path.open(encoding="utf-8") as fh:
                head = json.loads(fh.readline() or "{}")
        except (OSError, json.JSONDecodeError):
            continue
        if head.get("route_id") == route_id:
            return path
    return None


@dataclass
class BlockRun:
    journal: Path | None
    session_s: float        # temps de séance atteint (s)
    reason: str             # "fin" (10 min), "ferme" (OpenRide fermé avant), "garde_fou", "pas_de_journal"


def stop(proc: Any, sleep: Callable[[float], None] = time.sleep, wait_s: float = 30.0) -> None:
    """Ferme OpenRide comme Ctrl+C : le lanceur arrête le core (séance enregistrée) puis l'engine."""
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    for _ in range(int(wait_s)):
        if proc.poll() is not None:
            return
        sleep(1.0)
    proc.kill()


def ride_block(route_id: str, guide: Any, journal_dir: Path, config_path: Path | None, *,
               spawn: Callable[[list[str]], Any] | None = None, wall: Callable[[], float] = time.time,
               sleep: Callable[[float], None] = time.sleep, block_s: float = BLOCK_S) -> BlockRun:
    """Lance OpenRide sur le parcours, suit le temps de séance dans le journal, ferme OpenRide à `block_s`."""
    spawn = spawn or (lambda cmd: subprocess.Popen(cmd, start_new_session=True))
    started = wall()
    proc = spawn(launch_command(route_id, config_path))
    journal, session_s, reason = None, 0.0, "garde_fou"
    try:
        while wall() - started < BLOCK_MAX_S:
            if journal is None:
                journal = new_journal(journal_dir, started - 1.0, route_id)
                if journal is None and wall() - started > LAUNCH_WAIT_S:
                    reason = "pas_de_journal"
                    break
            rec = last_record(journal) if journal is not None else None
            if rec is not None:
                session_s = float(rec.get("t") or 0.0)
                power, cadence = rec.get("power"), rec.get("cadence")
                guide.tick({"séance": f"{int(session_s) // 60}:{int(session_s) % 60:02d} sur {int(block_s) // 60}:00",
                            "puissance": f"{power:.0f} W" if power is not None else "-",
                            "cadence": f"{cadence:.0f} tr/min" if cadence is not None else "-"})
            else:
                guide.tick({"séance": "lancement d'OpenRide…"})
            if session_s >= block_s:
                reason = "fin"
                break
            if proc.poll() is not None:
                reason = "ferme"
                break
            sleep(1.0)
    finally:
        stop(proc, sleep)
    return BlockRun(journal, session_s, reason)


def countdown(guide: Any, text: str, seconds: float, detail: str = "", *,
              clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
    guide.step(text, seconds, detail)
    end = clock() + seconds
    while clock() < end:
        guide.tick()
        sleep(0.5)
    guide.tick()


# --- commandes ---------------------------------------------------------------------------------

def _service(profile_path: Path, journal_dir: Path, cfg: Any) -> Any:
    from ..garage import ProgressionService

    return ProgressionService(cfg, journal_dir, None, profile_path)


def pc_steps(profile_path: Path, journal_dir: Path, cfg: Any, backup_dir: Path) -> list[tuple[str, Callable]]:
    return [("Expérience recalculée depuis le journal", lambda: check_xp(_service(profile_path, journal_dir, cfg))),
            ("Profil effacé puis remis", lambda: check_profile_reset(
                lambda: _service(profile_path, journal_dir, cfg), profile_path, backup_dir))]


def bilan_steps(profile_path: Path, journal_dir: Path, cfg: Any) -> list[tuple[str, Callable]]:
    from ..equipment import apply_equipment
    from ..physics import PhysicsParams

    plain = PhysicsParams.from_config(cfg)
    blocks = last_blocks(journal_dir)
    kit = (blocks["recette-v10-equipe"].loadout or {}) if "recette-v10-equipe" in blocks else {}
    svc = _service(profile_path, journal_dir, cfg)
    equipped = apply_equipment(plain, {k: v for k, v in kit.items() if k in ("frame", "wheels") and v},
                               svc.catalogue)
    return [("Comparaison des deux blocs", lambda: verdict(blocks, plain, equipped)),
            ("Expérience après les deux blocs", lambda: check_xp(svc))]


def run_checks(guide: Any, steps: list[tuple[str, Callable]]) -> bool:
    all_ok = True
    for i, (title, run) in enumerate(steps, 1):
        guide.step(title, index=i, total=len(steps), beep=False)
        ok, lines = run()
        for line in lines:
            guide.measure(title, line, ok=ok)
        all_ok &= ok
    return all_ok


@dataclass
class Ride:
    """Horloges et lancement d'OpenRide, remplaçables dans les tests."""
    spawn: Callable[[list[str]], Any] | None = None
    wall: Callable[[], float] = time.time
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


def run_all(args: Any, cfg: Any, profile_path: Path, config_path: Path, guide: Any, ride: Ride) -> bool:
    """La recette entière ; profil et parcours restaurés quoi qu'il arrive."""
    recette_dir = args.essais_dir / RECETTE
    backup_dir = recette_dir / BACKUP
    for path in backup([config_path, profile_path], backup_dir):
        guide.log("sauvegarde", chemin=str(path))
    try:
        write_all(args.routes_dir, args.essais_dir, terrain=not args.sans_terrain)
        ok = run_checks(guide, pc_steps(profile_path, args.journal_dir, cfg, backup_dir))
        launch_cfg = config_path if args.config is not None else None
        for i, ((route_id, _), loadout) in enumerate(zip(SESSIONS, (base_loadout(), AERO_LOADOUT)), 1):
            set_bike(profile_path, loadout, recette_dir)
            if i == 1:
                countdown(guide, "Monte sur le vélo : le bloc 1 démarre seul", GET_READY_S,
                          "OpenRide s'ouvre directement en séance ; pédale dès que le parcours s'affiche",
                          clock=ride.clock, sleep=ride.sleep)
            else:
                countdown(guide, "Pause sans pédaler : cadre et roues aéro posés", PAUSE_S,
                          "bois un coup ; le bloc 2 démarre seul à la fin du compte à rebours",
                          clock=ride.clock, sleep=ride.sleep)
            guide.step(f"Bloc {i} sur 2 : {route_id}", BLOCK_S, "suis les consignes à l'écran du jeu")
            run = ride_block(route_id, guide, args.journal_dir, launch_cfg,
                             spawn=ride.spawn, wall=ride.wall, sleep=ride.sleep)
            done = run.reason == "fin"
            guide.measure(f"Bloc {i}", f"{run.session_s / 60:.1f} min de séance ({run.reason})", ok=done)
            if not done:
                guide.alert(f"Bloc {i} interrompu ({run.reason}) : recette arrêtée, profil restauré.")
                return False
        return run_checks(guide, bilan_steps(profile_path, args.journal_dir, cfg)) and ok
    finally:
        for line in restore(profile_path, args.routes_dir, args.essais_dir):
            guide.log("restauration", texte=line)


def main(argv: list[str] | None = None, ride: Ride | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("commande", nargs="?", default="tout", choices=("tout", "materiel", "pc", "bilan", "restaurer"))
    p.add_argument("--routes-dir", type=Path, default=config.ROUTES_DIR)
    p.add_argument("--essais-dir", type=Path, default=ESSAIS_DIR)
    p.add_argument("--journal-dir", type=Path, default=None)
    p.add_argument("--profile", type=Path, default=None, help="profil de progression (défaut ~/OpenRide/profile.json)")
    p.add_argument("--config", type=Path, default=None, help="config.toml (défaut ~/OpenRide/config.toml)")
    p.add_argument("--sans-terrain", action="store_true", help="route seule (plus rapide)")
    args = p.parse_args(argv)
    if args.commande == "materiel":
        print(MATERIEL, end="")
        return 0

    from .. import profiles
    from .guide import Guide

    ctx = profiles.current()   # profil de joueur en cours (série MJ, lot MJ1)
    profile_path = args.profile or ctx.profile_path
    args.journal_dir = args.journal_dir or ctx.journal_dir
    config_path = args.config or config.DEFAULT_CONFIG_PATH
    recette_dir = args.essais_dir / RECETTE
    if args.commande == "restaurer":
        for line in restore(profile_path, args.routes_dir, args.essais_dir) or ["Rien à restaurer."]:
            print(line)
        return 0
    cfg = config.load(config_path if config_path.is_file() else None)
    if not cfg.progression.enabled:
        print("[progression] enabled = false dans config.toml : la recette V10 demande la progression active.")
        return 1

    recette_dir.mkdir(parents=True, exist_ok=True)
    guide = Guide("Recette V10", recette_dir / "guide.jsonl")
    ok = False
    try:
        if args.commande == "tout":
            ok = run_all(args, cfg, profile_path, config_path, guide, ride or Ride())
        elif args.commande == "pc":
            ok = run_checks(guide, pc_steps(profile_path, args.journal_dir, cfg, recette_dir / BACKUP))
        else:
            ok = run_checks(guide, bilan_steps(profile_path, args.journal_dir, cfg))
        guide.finish(ok, "Recette V10 : tout est bon" if ok else "Recette V10 : écart à regarder (lignes NON)")
    except KeyboardInterrupt:
        guide.finish(False, "Recette V10 arrêtée (Ctrl+C) : profil et parcours restaurés")
    finally:
        guide.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
