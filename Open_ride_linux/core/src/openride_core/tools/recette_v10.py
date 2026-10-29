"""Recette guidée de la série V (lot V10) : progression, équipement et avatar sur le vrai matériel.

Prépare tout, guide à l'écran et lit les journaux après coup ; le propriétaire n'a qu'à pédaler.

    python -m openride_core.tools.recette_v10 materiel     # matériel, durées, ce qui sera vérifié
    python -m openride_core.tools.recette_v10 preparer     # sauvegardes, parcours, consignes, pièces conseillées
    python -m openride_core.tools.recette_v10 pc           # essais sans vélo (expérience, profil effacé), guidés
    python -m openride_core.tools.recette_v10 bilan        # après les deux blocs : verdict lu dans les journaux
    python -m openride_core.tools.recette_v10 restaurer    # profil d'essai retiré, parcours et consignes retirés

Sur le vélo, deux blocs de 10 min sur le même parcours plat (`recette-v10-depart`, puis
`recette-v10-equipe`), avec les consignes de l'engine (`cue_model.gd`) : texte à l'écran, bip, préavis
d'une minute avant chaque geste et 30 à 40 s pour le faire. Entre les deux blocs, sans pédaler : Garage au
Click (cadre et roues aéro). `bilan` compare ensuite les deux blocs : vitesse à puissance égale, pente
envoyée au trainer, équipement noté dans l'en-tête du journal, temps gagné recalculé.

Rien n'est écrit dans le dépôt ; parcours fictifs (même origine que `demo`), aucune donnée personnelle.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config
from ..demo_world import write_world
from ..journal import JOURNAL_DIR, read_journal
from .fake_world import add_terrain_layer
from .seance_guidee import CREATED, ESSAIS_DIR, cues_json

RECETTE = "recette-v10"                      # dossier de la recette sous ~/OpenRide/Essais
BACKUP = "sauvegarde"                        # copies de config.toml et profile.json faites par `preparer`
TRIAL_MARK = "profil_essai"                  # présent si `preparer --profil-essai` a remplacé le profil
ROUTE_LENGTH_M = 12_000.0
SPRINTS_M = (1500.0, 3000.0, 4500.0)         # trois sprints de 400 m : un temps gagné par passage
SPRINT_LENGTH_M = 400.0
BLOCK_S = 600

# Pièces aéro conseillées, de la plus forte à la plus faible (catalogue du lot V3).
AERO_FRAMES = ("frame_tt", "frame_aero")
AERO_WHEELS = ("wheels_disc", "wheels_deep")

# Consigne : (temps de séance en s, texte, durée d'affichage en s, à préparer ou "").
BLOCK1_CUES: list[tuple[float, str, float, str]] = [
    (0, ("Bloc 1 sur 2, équipement de départ. Roule 10 min à puissance régulière (endurance) : "
         "retiens ta puissance, tu la referas au bloc 2"), 40, ""),
    (60, "Caméra : A (ou flèche haut) passe à la vue suivante. Une vue toutes les 20 s, 4 vues", 40, ""),
    (150, "Vue de suivi proche (A jusqu'à la retrouver) : regarde le pédalage de l'avatar", 30, ""),
    (210, "Cadence 60 tr/min pendant 30 s : les jambes ralentissent", 35, ""),
    (270, "Cadence 100 tr/min pendant 30 s : les jambes accélèrent", 35, ""),
    (330, "Retour à ta puissance d'endurance, cadence habituelle", 25, ""),
    (420, "Sprint 10 s à fond : l'avatar se met en danseuse", 20, "un sprint de 10 s"),
    (450, "Reprends ta puissance d'endurance jusqu'à la fin", 25, ""),
    (540, "Dernière minute. À 10 min : Y, « Terminer et enregistrer », lis le bilan (expérience, pièces)", 45,
     "la fin du bloc (bilan à lire)"),
]

BLOCK2_CUES: list[tuple[float, str, float, str]] = [
    (0, "Bloc 2 sur 2, cadre et roues aéro. Même puissance qu'au bloc 1, même cadence", 40, ""),
    (60, "Compare : la vitesse doit être un peu plus haute qu'au bloc 1, la résistance la même", 40, ""),
    (240, "Toujours la même puissance. Au sprint (vers 3 km) : « temps gagné » sous le chrono du segment", 40, ""),
    (420, "Ressenti : la résistance du trainer est-elle la même qu'au bloc 1 ? Note-le pour le bilan", 40, ""),
    (540, "Dernière minute. À 10 min : Y, « Terminer et enregistrer » ; « temps gagné » au bilan", 45,
     "la fin du bloc (bilan à lire)"),
]

SESSIONS = (("recette-v10-depart", BLOCK1_CUES), ("recette-v10-equipe", BLOCK2_CUES))

MATERIEL = """Recette V10 (progression, équipement, avatar) : à préparer

Sans vélo, sur le PC (environ 5 min, tout est automatique) :
  python -m openride_core.tools.recette_v10 preparer
  python -m openride_core.tools.recette_v10 pc

Sur le vélo : 2 blocs de 10 min, 2 min de pause entre les deux (environ 25 min en tout) :
- vélo sur le HomeTrainer, Bluetooth du PC allumé, aucune autre application reliée au trainer ;
- les deux boîtiers du Click réveillés (le clavier fait aussi l'affaire : A, flèches, Y) ;
- écran visible depuis le vélo, son du PC audible (bip à chaque consigne, préavis d'une minute) ;
- bidon et serviette.

Bloc 1 : « Monde » → recette-v10-depart → « Session libre ». Vues de caméra, avatar à 60 et 100 tr/min,
  sprint de 10 s (danseuse), bilan de fin.
Entre les blocs, sans pédaler : « Garage » au Click, choisir le cadre et les roues indiqués par `preparer`.
Bloc 2 : « Monde » → recette-v10-equipe → « Session libre », même puissance qu'au bloc 1.

Après : python -m openride_core.tools.recette_v10 bilan       (verdict lu dans les journaux)
Enfin : python -m openride_core.tools.recette_v10 restaurer   (profil d'essai, parcours et consignes retirés)
Hors vélo, à mettre dans la file des mesures du PC : banc par vue de caméra, au moins 55 images/s en low :
  engine/tests/sim_bench.py --godot <godot> --native --quality low --camera follow_near   (puis follow_far, side)
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


@dataclass
class Advice:
    frame: str | None          # pièce conseillée pour le bloc 2, None si aucune n'est à portée
    wheels: str | None
    lines: list[str]


def advise(svc: Any) -> Advice:
    """Cadre et roues aéro pour le bloc 2 : possédés d'abord, puis achetables avec le solde actuel."""
    from .. import coins as coins_mod

    progress, profile, cat = svc.progress, svc.profile, svc.catalogue
    owned = coins_mod.owned_items(progress, profile, cat)
    coins = svc.balance()
    lines = [f"Niveau {progress.level.level}, {progress.total_xp} points, {coins} pièces."]
    picks: dict[str, str | None] = {}
    for slot, ids in (("frame", AERO_FRAMES), ("wheels", AERO_WHEELS)):
        pick = next((i for i in ids if i in owned), None)
        how = "déjà possédé"
        if pick is None:
            pick = next((i for i in ids if coins_mod.item_state(cat.items[i], progress, profile, cat) == "buyable"
                         and cat.items[i].price <= coins), None)
            how = "à acheter au Garage"
            if pick is not None:
                coins -= cat.items[pick].price
        picks[slot] = pick
        label = "Cadre" if slot == "frame" else "Roues"
        if pick is None:
            need = ", ".join(f"{cat.items[i].name} : niveau {cat.items[i].level}, {cat.items[i].price} pièces"
                             for i in ids)
            lines.append(f"{label} : aucune pièce aéro à portée ({need}).")
        else:
            lines.append(f"{label} : {cat.items[pick].name} ({how}, {cat.items[pick].price} pièces).")
    if picks["frame"] is None and picks["wheels"] is None:
        lines.append("Bloc 2 impossible sans pièce aéro : relancer avec --profil-essai (le profil est sauvegardé, "
                     "`restaurer` le remet).")
    return Advice(picks["frame"], picks["wheels"], lines)


def trial_profile(svc: Any, profile_path: Path, recette_dir: Path) -> list[str]:
    """Profil d'essai : cadre et roues les plus aéro choisis sans achat (rendu par `restaurer`)."""
    from ..profile import save_profile

    svc.profile.equipped.update({"frame": AERO_FRAMES[0], "wheels": AERO_WHEELS[0]})
    save_profile(svc.profile, profile_path)
    recette_dir.mkdir(parents=True, exist_ok=True)
    (recette_dir / TRIAL_MARK).write_text("profil d'essai écrit par `preparer --profil-essai`\n", encoding="utf-8")
    cat = svc.catalogue
    return [(f"Profil d'essai : {cat.items[AERO_FRAMES[0]].name} et {cat.items[AERO_WHEELS[0]].name} déjà choisis. "
             "Au Garage, vérifier seulement qu'ils sont marqués « équipé » (pas d'achat).")]


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


# --- commandes ---------------------------------------------------------------------------------

def _service(profile_path: Path, journal_dir: Path, cfg: Any) -> Any:
    from ..garage import ProgressionService

    return ProgressionService(cfg, journal_dir, None, profile_path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("commande", choices=("materiel", "preparer", "pc", "bilan", "restaurer"))
    p.add_argument("--profil-essai", action="store_true",
                   help="preparer : choisir cadre et roues aéro sans achat (profil sauvegardé puis rendu)")
    p.add_argument("--routes-dir", type=Path, default=config.ROUTES_DIR)
    p.add_argument("--essais-dir", type=Path, default=ESSAIS_DIR)
    p.add_argument("--journal-dir", type=Path, default=JOURNAL_DIR)
    p.add_argument("--profile", type=Path, default=None, help="profil de progression (défaut ~/OpenRide/profile.json)")
    p.add_argument("--config", type=Path, default=None, help="config.toml (défaut ~/OpenRide/config.toml)")
    p.add_argument("--sans-terrain", action="store_true", help="route seule (plus rapide)")
    args = p.parse_args(argv)
    if args.commande == "materiel":
        print(MATERIEL, end="")
        return 0

    from ..profile import PROFILE_PATH
    from .guide import Guide

    profile_path = args.profile or PROFILE_PATH
    config_path = args.config or config.DEFAULT_CONFIG_PATH
    recette_dir = args.essais_dir / RECETTE
    backup_dir = recette_dir / BACKUP
    cfg = config.load(config_path if config_path.is_file() else None)
    if args.commande == "restaurer":
        saved, mark = backup_dir / profile_path.name, recette_dir / TRIAL_MARK
        if not mark.is_file():
            print("Profil gardé : pas de profil d'essai (les achats faits au Garage restent).")
        elif saved.is_file():
            shutil.copy2(saved, profile_path)
            print(f"Profil remis : {profile_path}")
        else:   # pas de profil avant la recette : on revient à « pas de profil »
            profile_path.unlink(missing_ok=True)
            print(f"Profil d'essai retiré : {profile_path}")
        mark.unlink(missing_ok=True)
        for path in remove_all(args.routes_dir, args.essais_dir):
            print(f"Retiré : {path}")
        return 0
    if not cfg.progression.enabled:
        print("[progression] enabled = false dans config.toml : la recette V10 demande la progression active.")
        return 1

    if args.commande == "preparer":
        for path in backup([config_path, profile_path], backup_dir):
            print(f"Sauvegardé : {path}")
        for path in write_all(args.routes_dir, args.essais_dir, terrain=not args.sans_terrain):
            print(f"Écrit : {path}")
        svc = _service(profile_path, args.journal_dir, cfg)
        advice = advise(svc)
        lines = advice.lines + (trial_profile(svc, profile_path, recette_dir) if args.profil_essai else [])
        print()
        print("\n".join(lines))
        print()
        print(MATERIEL, end="")
        return 0

    recette_dir.mkdir(parents=True, exist_ok=True)
    guide = Guide("Recette V10", recette_dir / "guide.jsonl")
    if args.commande == "pc":
        steps = [("Expérience recalculée depuis le journal", lambda: check_xp(_service(profile_path, args.journal_dir, cfg))),
                 ("Profil effacé puis remis", lambda: check_profile_reset(
                     lambda: _service(profile_path, args.journal_dir, cfg), profile_path, backup_dir))]
    else:
        from ..physics import PhysicsParams

        plain = PhysicsParams.from_config(cfg)
        blocks = last_blocks(args.journal_dir)
        kit = (blocks.get("recette-v10-equipe").loadout or {}) if "recette-v10-equipe" in blocks else {}
        svc = _service(profile_path, args.journal_dir, cfg)
        from ..equipment import apply_equipment

        equipped = apply_equipment(plain, {k: v for k, v in kit.items() if k in ("frame", "wheels") and v},
                                   svc.catalogue)
        steps = [("Comparaison des deux blocs", lambda: verdict(blocks, plain, equipped)),
                 ("Expérience après les deux blocs", lambda: check_xp(svc))]
    all_ok = True
    for i, (title, run) in enumerate(steps, 1):
        guide.step(title, index=i, total=len(steps))
        ok, lines = run()
        for line in lines:
            guide.measure(title, line, ok=ok)
        all_ok &= ok
    guide.finish(all_ok, "Recette V10 : tout est bon" if all_ok else "Recette V10 : écart à regarder (lignes ÉCHEC)")
    guide.close()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
