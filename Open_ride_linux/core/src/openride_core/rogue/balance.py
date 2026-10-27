"""Valeurs d'équilibrage du mode Cyber-Rogue, réunies dans un seul objet (lot R2).

Les lots R4 à R6 et R15 ajoutent leurs champs ici. Le lot R7 les lit dans `balance.toml` (embarqué) et accepte
une surcharge `~/OpenRide/rogue_balance.toml` : `load_balance()`. `DEFAULT_BALANCE` reste la table de référence ;
un test vérifie que le fichier embarqué lui est identique.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path


@dataclass(frozen=True)
class RogueBalance:
    # W'bal (R2)
    fluid_regen_mult: float = 1.2       # bonus de jeu : recharge ×1,2 en Fluide à cadence 80-95 rpm
    fluid_regen_rpm_min: float = 80.0   # bas de la plage de cadence qui donne le bonus de recharge de W'bal (rpm)
    fluid_regen_rpm_max: float = 95.0   # haut de cette plage (rpm)
    # Postures (R2) : entrée et sortie en rpm
    roc_enter_rpm: float = 70.0         # Roc sous 70 rpm
    roc_exit_rpm: float = 73.0          # on quitte Roc à 73 rpm et plus
    veloce_enter_rpm: float = 100.0     # Véloce au-dessus de 100 rpm
    veloce_exit_rpm: float = 97.0       # on quitte Véloce à 97 rpm et moins
    stop_enter_rpm: float = 20.0        # arrêt sous 20 rpm ou sous 10 W
    stop_exit_rpm: float = 30.0   # cadence à partir de laquelle on sort de l'arrêt (rpm)
    stop_power_w: float = 10.0   # puissance sous laquelle on est à l'arrêt (W)
    posture_hold_s: float = 1.5         # durée continue dans une plage avant de changer
    cadence_smooth_s: float = 2.0       # constante de lissage de la cadence

    # Salles (R3)
    min_bump_s: float = 15.0            # durée minimale d'une bosse (30 si R0 l'exige)
    max_drop_pts: float = 5.0           # chute de pente maximale en 10 s (les chutes plus fortes sont étalées)
    arch_lead_s: float = 0.8            # avance des arches de Perfect Shift sur la rupture (t50 de R0)
    break_min_pts: float = 3.0          # rupture de pente : variation d'au moins 3 points
    room_grade_min: float = -3.0        # pente bornée avant le décalage du braquet
    room_grade_max: float = 10.0   # pente maximale d'une salle avant le décalage du braquet (%)
    marker_gap_s: float = 1.0           # écart minimal entre cibles, zones de parade et balises
    parry_lead_s: float = 2.0           # zone de parade : 2 s avant la bosse ou l'onde de choc
    tunnel_period_s: float = 40.0   # Diesel : période des tunnels de cadence (s)
    tunnel_len_s: float = 20.0   # Diesel : durée d'un tunnel (s)
    tunnel_cadence_rpm: float = 90.0   # Diesel : cadence visée dans un tunnel (rpm)
    tunnel_tolerance_rpm: float = 3.0   # Diesel : tolérance autour de la cadence visée (rpm)
    rock_armor: float = 2.0   # Grimpeur : points d'armure d'un rocher
    pad_threshold_frac: float = 1.40   # Sprinteur : puissance minimale sur un pavé, en fraction de la FTP
    pad_min_gear: float = 10.0   # Sprinteur : vitesse minimale pour que le pavé compte
    purge_period_s: float = 60.0        # Saboteur : une balise de purge par minute
    purge_first_s: float = 50.0   # Saboteur : instant de la première balise de purge (s)
    hack_delay_s: float = 20.0          # le piratage a lieu 20 s avant la balise de purge
    transition_s: float = 30.0          # transition à 0 % avant chaque phase du boss
    transition_frac: float = 0.50   # boss : fraction de la FTP conseillée pendant la transition
    boss_phase_s: tuple = (180.0, 240.0, 90.0)   # combat de chaque phase pour une run de 45 min
    # Firewall (R4)
    start_gap_m: float = 150.0          # le mur part derrière le joueur à l'entrée de chaque salle
    max_gap_m: float = 400.0            # écart plafonné : pas d'avance infinie à capitaliser
    # Combat (R5)
    hp_factor_endurance: float = 1.038  # PV de l'ennemi = facteur × cible moyenne × durée nominale (endurance)
    hp_factor_threshold: float = 1.03   # idem pour le seuil
    hp_factor_vo2max: float = 1.02      # idem pour la VO2max
    boss_hp_factor: float = 1.118       # PV de chaque phase du boss = facteur × cible moyenne × durée de la phase
    gear_step: float = 0.04             # m_gear = 1 + 0,04 × (vitesse − 6)
    gear_ref: int = 6   # vitesse neutre : multiplicateur de dégâts et pente envoyée sont centrés dessus
    gear_min: int = 1   # première vitesse
    gear_max: int = 12   # dernière vitesse
    roc_armor_mult: float = 0.7         # pertes de bouclier en Roc
    veloce_armor_mult: float = 1.2   # Véloce : multiplicateur des pertes de bouclier
    veloce_crit_chance: float = 0.15    # par seconde
    crit_mult: float = 2.0   # multiplicateur de dégâts d'un coup critique
    shield_max: float = 100.0   # bouclier maximal
    contact_shield_per_s: float = 4.0   # bouclier perdu par seconde au contact du Firewall
    contact_gold_per_s: float = 1.0   # or perdu par seconde au contact du Firewall
    unparried_hit: float = 10.0   # bouclier perdu sur un coup non paré
    corridor_regen_per_s: float = 2.0   # lu par R6
    recovery_s: float = 60.0   # durée de la récupération forcée après une défaite (s)
    recovery_shield: float = 50.0   # bouclier remis après une défaite
    defeat_run_gold_loss: float = 0.25   # part de l'or de la run perdue en cas de défaite
    adrenaline_max: float = 100.0   # adrénaline maximale
    adrenaline_per_s: float = 0.5   # adrénaline gagnée par seconde quand la puissance atteint la cible
    adrenaline_roc_mult: float = 0.7   # Roc : multiplicateur de cette recharge
    adrenaline_veloce_mult: float = 1.5   # Véloce : multiplicateur de cette recharge
    perfect_shift_adrenaline: float = 10.0   # adrénaline gagnée par Perfect Shift réussi
    ps_window_s: float = 1.5            # fenêtre de Perfect Shift centrée sur l'arche (R0)
    overheat_frac: float = 0.75   # surchauffe (endurance) : seuil de puissance, en fraction de la FTP
    overheat_after_s: float = 5.0   # surchauffe : durée au-delà du seuil avant qu'elle commence (s)
    overheat_adrenaline_per_s: float = 2.0   # surchauffe : adrénaline perdue par seconde
    long_press_gears: int = 3   # vitesses sautées par un appui long sur + ou B
    strike_cost: float = 50.0   # adrénaline consommée par une attaque Z
    strike_hp_frac: float = 0.06   # part des PV maximaux retirée par une attaque Z
    strike_window_s: float = 1.0        # fenêtre d'une cible ou d'une balise (± moitié)
    rock_window_s: float = 1.5   # largeur de la fenêtre d'un rocher (s)
    tunnel_charge_s: float = 10.0   # Diesel : secondes dans la bande de cadence pour une charge
    tunnel_max_charges: int = 3   # Diesel : charges au plus
    tunnel_charge_hp_frac: float = 0.04   # Diesel : part des PV maximaux retirée par charge libérée
    roc_charge_s: float = 5.0   # Grimpeur : secondes continues en Roc pour un coup chargé
    roc_max_charges: int = 2   # Grimpeur : coups chargés au plus
    rock_hp_frac: float = 0.08   # Grimpeur : part des PV maximaux retirée par un rocher brisé
    pad_damage_mult: float = 3.0   # Sprinteur : multiplicateur de dégâts sur un pavé
    hook_grade_mult: float = 0.5        # Puncheur : bosse aspirée à moitié de sa pente
    hook_power_ratio: float = 1.10   # Puncheur : rapport minimal des puissances (2 s récentes / 3 s d'avant) pour s'accrocher
    hook_s: float = 15.0   # Puncheur : durée de la bosse aspirée (s)
    hack_max_s: float = 30.0   # Saboteur : durée maximale d'un piratage sans purge (s)
    win_gold: float = 20.0   # or d'une salle gagnée
    win_gold_per_ps: float = 2.0   # or de plus par Perfect Shift
    flee_gold: float = 8.0   # or d'une salle où l'ennemi s'enfuit
    # Run, cartes et reliques (R6)
    warmup_relic_s: float = 180.0       # tirage de la relique de départ à la 3e minute
    warmup_grade_max: float = 2.0       # échauffement : pente 0 à 2 %, cible 0,50 à 0,75 FTP
    warmup_frac_from: float = 0.50   # échauffement : cible au début, en fraction de la FTP
    warmup_frac_to: float = 0.75   # échauffement : cible à la fin
    cooldown_frac: float = 0.50   # retour au calme : fraction de la FTP conseillée
    reroll_cost: int = 15   # coût de la première relance de cartes (or)
    reroll_step: int = 5   # supplément par relance dans le même couloir
    cards_offered: int = 3   # cartes proposées dans un couloir
    sent_grade_min: float = -10.0       # pente envoyée au trainer : plage du trainer
    sent_grade_max: float = 16.0   # pente maximale envoyée au trainer (%)
    gear_grade_pts: float = 1.0         # formule centrée (Q2) : + (vitesse − 6) × 1 point
    roller_cap_grade: float = 6.0       # Rouleau compresseur
    roller_hold_s: float = 3.0   # Rouleau compresseur : durée de maintien à 6 % après la pente (s)
    springboard_grade: float = -1.0     # Tremplin cinétique
    springboard_min_gear: int = 9   # Tremplin cinétique : vitesse minimale
    springboard_adrenaline: float = 15.0   # Tremplin cinétique : adrénaline gagnée
    springboard_s: float = 5.0   # Tremplin cinétique : durée du bonus de dégâts (s)
    springboard_mult: float = 1.5   # Tremplin cinétique : multiplicateur de dégâts
    overdrive_grade_pts: float = 4.0   # Overdrive : points de pente ajoutés
    overdrive_mult: float = 2.0   # Overdrive : multiplicateur de dégâts
    overdrive_s: float = 8.0   # Overdrive : durée (s)
    overdrive_cooldown_s: float = 45.0   # Overdrive : recharge (s)
    overdrive_back_gear: int = 6   # Overdrive : vitesse de retour automatique
    heal_cadence_rpm: float = 95.0   # Soin : cadence minimale (rpm)
    heal_per_s: float = 1.0   # Soin : bouclier gagné par seconde
    cursed_gear: int = 10   # Maudit : vitesse concernée
    cursed_mult: float = 1.35   # Maudit : multiplicateur de dégâts
    shifter_window_mult: float = 2.0   # Shifter électronique : multiplicateur de la fenêtre de Perfect Shift
    shifter_window_max_s: float = 3.0   # Shifter électronique : fenêtre maximale (s)
    shifter_shield: float = 3.0   # Shifter électronique : bouclier gagné par réussite
    siphon_adrenaline: float = 50.0   # Siphon d'aspiration : adrénaline gagnée
    inversion_s: float = 8.0   # Inversion polaire : durée (s)
    inversion_floor: float = -3.0   # Inversion polaire : pente minimale (%)
    relic_shield_bonus: float = 20.0   # relique de bouclier : bouclier maximal en plus
    relic_gold_mult: float = 1.25   # relique d'or : multiplicateur de l'or gagné
    relic_ps_window_bonus_s: float = 0.3   # relique de réflexes : fenêtre de Perfect Shift en plus (s)
    # Châssis (R9) : valeurs neutres, modifiées seulement par `progress.apply_chassis`
    gold_mult: float = 1.0   # multiplicateur de l'or gagné (châssis Collecteur)
    adrenaline_start: float = 0.0   # adrénaline au début de chaque salle (châssis Survolté)
    # Scénariste (R15) : durée de la run -> (échauffement min, nombre de salles, salle moyenne min,
    # couloir min, boss min, poids des trois phases, retour au calme min)
    calendars: dict = field(default_factory=lambda: {   # durée de la run (min) -> échauffement min, salles, salle moyenne min, couloir min, boss min, poids des phases, retour au calme min
        30: (6.0, 2, 4.0, 2.0, 7.0, (2.0, 3.0, 1.0), 5.0),
        45: (8.0, 4, 3.5, 2.0, 10.0, (3.0, 4.0, 1.5), 5.0),
        60: (10.0, 6, 3.5, 2.0, 10.0, (3.0, 4.0, 1.5), 7.0),
        90: (10.0, 10, 4.0, 2.0, 12.0, (4.0, 5.0, 1.5), 8.0),
    })
    room_min_s: float = 180.0           # salles de 3 à 5 minutes
    room_max_s: float = 300.0   # durée maximale d'une salle (s)
    room_spread_s: float = 60.0   # écart de tirage de la durée d'une salle (s)
    reservoirs: dict = field(default_factory=lambda: {   # archétypes disponibles par objectif
        "endurance": ("diesel", "grimpeur", "saboteur"),
        "threshold": ("diesel", "grimpeur", "saboteur"),
        "vo2max": ("puncheur", "sprinteur", "grimpeur"),
    })
    sprinter_extra: str = "sprinteur"   # seuil : Sprinteur au plus une fois (il remplace une porte)
    late_margin_s: float = 120.0        # retard toléré avant de raccourcir les couloirs
    corridor_min_s: float = 60.0   # durée minimale d'un couloir raccourci (s)
    skip_gold_penalty: float = 10.0   # or perdu pour une salle retirée
    # Profils par archétype et par objectif (valeurs de départ du cahier R3 §4.2)
    room_profiles: dict = field(default_factory=lambda: {   # profils des salles par archétype et par objectif (voir le cahier R3)
        "diesel": {
            "endurance": {"g0": 2.0, "g1": 3.0, "fw": 0.68},
            "threshold": {"g0": 3.0, "g1": 4.0, "fw": 0.90},
        },
        "puncheur": {
            "vo2max": {"bump_s": 15.0, "valley_s": 30.0, "bump_grade": 9.0, "valley_grade": -2.0,
                       "fw_bump": 1.15, "fw_valley": 0.67,
                       "bump_s_30_30": 30.0, "fw_bump_30_30": 0.95, "fw_valley_30_30": 0.65},
        },
        "grimpeur": {
            "endurance": {"steps": (2.0, 3.0, 4.0), "step_s": 60.0, "fw": 0.70},
            "threshold": {"steps": (4.0, 7.0, 10.0), "step_s": 60.0, "fw": 0.88},
            "vo2max": {"steps": (5.0, 8.0, 10.0), "step_s": 60.0, "fw": 0.95},
        },
        "sprinteur": {
            "threshold": {"fw": 0.75, "burst_fw": 1.30, "burst_s": 10.0, "period_s": 45.0},
            "vo2max": {"fw": 0.80, "burst_fw": 1.50, "burst_s": 8.0, "period_s": 40.0},
        },
        "saboteur": {
            "endurance": {"lo": 1.0, "hi": 3.0, "fw": 0.68},
            "threshold": {"lo": 2.0, "hi": 5.0, "fw": 0.88},
        },
        "boss": {
            "endurance": {"p1_grade": 3.0, "p1_fw": 0.70, "p1_locks": 4,
                          "p2_grades": (4.0, 0.0, 5.0), "p2_fw": (0.80, 0.60, 0.85), "p2_block_s": 40.0,
                          "shock_period_s": 30.0, "p3_grade": 0.0, "p3_fw": 0.85},
            "threshold": {"p1_grade": 5.0, "p1_fw": 0.90, "p1_locks": 4,
                      "p2_grades": (8.0, 0.0, 10.0), "p2_fw": (1.00, 0.70, 1.05), "p2_block_s": 40.0,
                      "shock_period_s": 30.0, "p3_grade": 0.0, "p3_fw": 1.20},
        },
    })


DEFAULT_BALANCE = RogueBalance()


EMBEDDED_PATH = Path(__file__).with_name("balance.toml")
OVERRIDE_PATH = Path.home() / "OpenRide" / "rogue_balance.toml"

_NEGATIVE_OK = {f.name: (-30.0, 30.0) for f in fields(RogueBalance)
                if isinstance(f.default, (int, float)) and f.default < 0}   # pentes minimales


class BalanceError(ValueError):
    """Table d'équilibrage refusée : le message nomme la clé fautive."""


def _bounds(name: str) -> tuple[float, float]:
    """Bornes d'une constante : larges par défaut, plus serrées pour les fractions et multiplicateurs."""
    if name in _NEGATIVE_OK:
        return _NEGATIVE_OK[name]
    if name.endswith("hp_frac"):
        return 0.0, 1.0
    if name.endswith("_frac") or name.startswith("hp_factor_") or name == "boss_hp_factor":
        return 0.0, 5.0
    if name.endswith("_mult"):
        return 0.0, 10.0
    if name in ("gear_ref", "gear_min", "gear_max"):
        return 1.0, 24.0
    return 0.0, 10000.0


def _like(path: str, val, ref):
    """Vérifie la forme (nombre, texte, liste) d'une valeur par rapport à la référence ; rend la valeur en tuples."""
    if isinstance(ref, bool) or isinstance(val, bool):
        raise BalanceError(f"{path} : booléen non attendu")
    if isinstance(ref, (int, float)):
        if not isinstance(val, (int, float)):
            raise BalanceError(f"{path} : un nombre est attendu, reçu {val!r}")
        if isinstance(ref, int):
            if float(val) != int(val):
                raise BalanceError(f"{path} : un entier est attendu, reçu {val!r}")
            return int(val)
        return float(val)
    if isinstance(ref, str):
        if not isinstance(val, str):
            raise BalanceError(f"{path} : un texte est attendu, reçu {val!r}")
        return val
    if isinstance(ref, tuple):
        if not isinstance(val, (list, tuple)) or len(val) != len(ref):
            raise BalanceError(f"{path} : une liste de {len(ref)} éléments est attendue, reçu {val!r}")
        return tuple(_like(f"{path}[{i}]", v, r) for i, (v, r) in enumerate(zip(val, ref)))
    raise BalanceError(f"{path} : type non géré")


def _check_range(path: str, val, lo: float, hi: float) -> None:
    if isinstance(val, (int, float)) and not lo <= val <= hi:
        raise BalanceError(f"{path} : {val} hors bornes ({lo} à {hi})")


def _merge_table(path: str, base: dict, over: dict, *, numeric_range=(0.0, 10000.0)) -> dict:
    """Fusion récursive : toute clé doit exister dans la table de base."""
    out = dict(base)
    for k, v in over.items():
        kp = f"{path}.{k}"
        if k not in base:
            raise BalanceError(f"{kp} : clé inconnue")
        if isinstance(base[k], dict):
            if not isinstance(v, dict):
                raise BalanceError(f"{kp} : une table est attendue")
            out[k] = _merge_table(kp, base[k], v, numeric_range=numeric_range)
        else:
            out[k] = _like(kp, v, base[k])
            _check_range_deep(kp, out[k], *numeric_range)
    return out


def _check_range_deep(path: str, val, lo: float, hi: float) -> None:
    if isinstance(val, tuple):
        for i, x in enumerate(val):
            _check_range_deep(f"{path}[{i}]", x, lo, hi)
    else:
        _check_range(path, val, lo, hi)


def apply_overrides(base: RogueBalance, data: dict) -> RogueBalance:
    """Rend `base` modifié par `data` (contenu d'un fichier TOML). Lève `BalanceError` sinon."""
    names = {f.name for f in fields(RogueBalance)}
    changes: dict = {}
    for k, v in data.items():
        if k not in names:
            raise BalanceError(f"{k} : clé inconnue")
        ref = getattr(base, k)
        if k == "calendars":
            if not isinstance(v, dict):
                raise BalanceError("calendars : une table est attendue")
            cal = dict(ref)
            for dk, row in v.items():
                try:
                    d = int(dk)
                except ValueError:
                    raise BalanceError(f"calendars.{dk} : la clé doit être une durée en minutes") from None
                if d not in ref:
                    raise BalanceError(f"calendars.{dk} : clé inconnue (durées connues : {sorted(ref)})")
                val = _like(f"calendars.{dk}", row, ref[d])
                _check_range_deep(f"calendars.{dk}", val, 0.0, 10000.0)
                cal[d] = val
            changes[k] = cal
        elif k == "reservoirs":
            if not isinstance(v, dict):
                raise BalanceError("reservoirs : une table est attendue")
            res = dict(ref)
            known = {a for t in ref.values() for a in t} | set(base.room_profiles)
            for ok, row in v.items():
                if ok not in ref:
                    raise BalanceError(f"reservoirs.{ok} : objectif inconnu")
                if not isinstance(row, list) or not row or any(a not in known for a in row):
                    raise BalanceError(f"reservoirs.{ok} : liste d'archétypes connus attendue, reçu {row!r}")
                res[ok] = tuple(row)
            changes[k] = res
        elif isinstance(ref, dict):
            if not isinstance(v, dict):
                raise BalanceError(f"{k} : une table est attendue")
            changes[k] = _merge_table(k, ref, v, numeric_range=(-30.0, 10000.0))
        else:
            val = _like(k, v, ref)
            _check_range_deep(k, val, *_bounds(k))
            changes[k] = val
    return replace(base, **changes)


def _read(path: Path) -> dict:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise BalanceError(f"{path} : TOML invalide ({exc})") from None


def load_balance(override: Path | None = None, *, required: bool = False) -> RogueBalance:
    """Table embarquée, puis surcharge `~/OpenRide/rogue_balance.toml` si elle existe (ou `override`).
    Un fichier demandé (`required`) qui manque est une erreur ; la surcharge par défaut, elle, est facultative."""
    bal = apply_overrides(RogueBalance(), _read(EMBEDDED_PATH))
    path = OVERRIDE_PATH if override is None else override
    if required and not path.is_file():
        raise BalanceError(f"{path} : fichier introuvable")
    if path.is_file():
        try:
            bal = apply_overrides(bal, _read(path))
        except BalanceError as exc:
            raise BalanceError(f"{path} : {exc}") from None
    return bal


def balance_hash(bal: RogueBalance) -> str:
    """Empreinte courte (8 caractères) de la table, notée dans le journal de chaque run."""
    raw = json.dumps({f.name: getattr(bal, f.name) for f in fields(bal)}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:8]
