"""Valeurs d'équilibrage du mode Cyber-Rogue, réunies dans un seul objet (lot R2).

Les lots R4 à R6 et R15 ajoutent leurs champs ici ; R7 les charge depuis un fichier de données.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RogueBalance:
    # W'bal (R2)
    fluid_regen_mult: float = 1.2       # bonus de jeu : recharge ×1,2 en Fluide à cadence 80-95 rpm
    fluid_regen_rpm_min: float = 80.0
    fluid_regen_rpm_max: float = 95.0
    # Postures (R2) : entrée et sortie en rpm
    roc_enter_rpm: float = 70.0         # Roc sous 70 rpm
    roc_exit_rpm: float = 73.0          # on quitte Roc à 73 rpm et plus
    veloce_enter_rpm: float = 100.0     # Véloce au-dessus de 100 rpm
    veloce_exit_rpm: float = 97.0       # on quitte Véloce à 97 rpm et moins
    stop_enter_rpm: float = 20.0        # arrêt sous 20 rpm ou sous 10 W
    stop_exit_rpm: float = 30.0
    stop_power_w: float = 10.0
    posture_hold_s: float = 1.5         # durée continue dans une plage avant de changer
    cadence_smooth_s: float = 2.0       # constante de lissage de la cadence

    # Salles (R3)
    min_bump_s: float = 15.0            # durée minimale d'une bosse (30 si R0 l'exige)
    max_drop_pts: float = 5.0           # chute de pente maximale en 10 s (les chutes plus fortes sont étalées)
    arch_lead_s: float = 0.8            # avance des arches de Perfect Shift sur la rupture (t50 de R0)
    break_min_pts: float = 3.0          # rupture de pente : variation d'au moins 3 points
    room_grade_min: float = -3.0        # pente bornée avant le décalage du braquet
    room_grade_max: float = 10.0
    marker_gap_s: float = 1.0           # écart minimal entre cibles, zones de parade et balises
    parry_lead_s: float = 2.0           # zone de parade : 2 s avant la bosse ou l'onde de choc
    tunnel_period_s: float = 40.0
    tunnel_len_s: float = 20.0
    tunnel_cadence_rpm: float = 90.0
    tunnel_tolerance_rpm: float = 3.0
    rock_armor: float = 2.0
    pad_threshold_frac: float = 1.40
    pad_min_gear: float = 10.0
    purge_period_s: float = 60.0        # Saboteur : une balise de purge par minute
    purge_first_s: float = 50.0
    hack_delay_s: float = 20.0          # le piratage a lieu 20 s avant la balise de purge
    transition_s: float = 30.0          # transition à 0 % avant chaque phase du boss
    transition_frac: float = 0.50
    boss_phase_s: tuple = (180.0, 240.0, 90.0)   # combat de chaque phase pour une run de 45 min
    # Firewall (R4)
    start_gap_m: float = 150.0          # le mur part derrière le joueur à l'entrée de chaque salle
    max_gap_m: float = 400.0            # écart plafonné : pas d'avance infinie à capitaliser
    # Combat (R5)
    hp_factor: float = 0.9              # PV de l'ennemi = 0,9 × cible moyenne × durée nominale
    gear_step: float = 0.04             # m_gear = 1 + 0,04 × (vitesse − 6)
    gear_ref: int = 6
    gear_min: int = 1
    gear_max: int = 12
    roc_armor_mult: float = 0.7         # pertes de bouclier en Roc
    veloce_armor_mult: float = 1.2
    veloce_crit_chance: float = 0.15    # par seconde
    crit_mult: float = 2.0
    shield_max: float = 100.0
    contact_shield_per_s: float = 4.0
    contact_gold_per_s: float = 1.0
    unparried_hit: float = 10.0
    corridor_regen_per_s: float = 2.0   # lu par R6
    recovery_s: float = 60.0
    recovery_shield: float = 50.0
    defeat_run_gold_loss: float = 0.25
    adrenaline_max: float = 100.0
    adrenaline_per_s: float = 0.5
    adrenaline_roc_mult: float = 0.7
    adrenaline_veloce_mult: float = 1.5
    perfect_shift_adrenaline: float = 10.0
    ps_window_s: float = 1.5            # fenêtre de Perfect Shift centrée sur l'arche (R0)
    overheat_frac: float = 0.75
    overheat_after_s: float = 5.0
    overheat_adrenaline_per_s: float = 2.0
    long_press_gears: int = 3
    strike_cost: float = 50.0
    strike_hp_frac: float = 0.06
    strike_window_s: float = 1.0        # fenêtre d'une cible ou d'une balise (± moitié)
    rock_window_s: float = 1.5
    tunnel_charge_s: float = 10.0
    tunnel_max_charges: int = 3
    tunnel_charge_hp_frac: float = 0.04
    roc_charge_s: float = 5.0
    roc_max_charges: int = 2
    rock_hp_frac: float = 0.08
    pad_damage_mult: float = 3.0
    hook_grade_mult: float = 0.5        # Puncheur : bosse aspirée à moitié de sa pente
    hook_power_ratio: float = 1.10
    hook_s: float = 15.0
    hack_max_s: float = 30.0
    win_gold: float = 20.0
    win_gold_per_ps: float = 2.0
    flee_gold: float = 8.0
    # Run, cartes et reliques (R6)
    warmup_relic_s: float = 180.0       # tirage de la relique de départ à la 3e minute
    warmup_grade_max: float = 2.0       # échauffement : pente 0 à 2 %, cible 0,50 à 0,75 FTP
    warmup_frac_from: float = 0.50
    warmup_frac_to: float = 0.75
    cooldown_frac: float = 0.50
    reroll_cost: int = 15
    reroll_step: int = 5
    cards_offered: int = 3
    sent_grade_min: float = -10.0       # pente envoyée au trainer : plage du trainer
    sent_grade_max: float = 16.0
    gear_grade_pts: float = 1.0         # formule centrée (Q2) : + (vitesse − 6) × 1 point
    roller_cap_grade: float = 6.0       # Rouleau compresseur
    roller_hold_s: float = 3.0
    springboard_grade: float = -1.0     # Tremplin cinétique
    springboard_min_gear: int = 9
    springboard_adrenaline: float = 15.0
    springboard_s: float = 5.0
    springboard_mult: float = 1.5
    overdrive_grade_pts: float = 4.0
    overdrive_mult: float = 2.0
    overdrive_s: float = 8.0
    overdrive_cooldown_s: float = 45.0
    overdrive_back_gear: int = 6
    heal_cadence_rpm: float = 95.0
    heal_per_s: float = 1.0
    cursed_gear: int = 10
    cursed_mult: float = 1.35
    shifter_window_mult: float = 2.0
    shifter_window_max_s: float = 3.0
    shifter_shield: float = 3.0
    siphon_adrenaline: float = 50.0
    inversion_s: float = 8.0
    inversion_floor: float = -3.0
    relic_shield_bonus: float = 20.0
    relic_gold_mult: float = 1.25
    relic_ps_window_bonus_s: float = 0.3
    # Scénariste (R15) : durée de la run -> (échauffement min, nombre de salles, salle moyenne min,
    # couloir min, boss min, poids des trois phases, retour au calme min)
    calendars: dict = field(default_factory=lambda: {
        30: (6.0, 2, 4.0, 2.0, 7.0, (2.0, 3.0, 1.0), 5.0),
        45: (8.0, 4, 3.5, 2.0, 10.0, (3.0, 4.0, 1.5), 5.0),
        60: (10.0, 6, 3.5, 2.0, 10.0, (3.0, 4.0, 1.5), 7.0),
        90: (10.0, 10, 4.0, 2.0, 12.0, (4.0, 5.0, 1.5), 8.0),
    })
    room_min_s: float = 180.0           # salles de 3 à 5 minutes
    room_max_s: float = 300.0
    room_spread_s: float = 60.0
    reservoirs: dict = field(default_factory=lambda: {
        "endurance": ("diesel", "grimpeur", "saboteur"),
        "threshold": ("diesel", "grimpeur", "saboteur"),
        "vo2max": ("puncheur", "sprinteur", "grimpeur"),
    })
    sprinter_extra: str = "sprinteur"   # seuil : Sprinteur au plus une fois (il remplace une porte)
    late_margin_s: float = 120.0        # retard toléré avant de raccourcir les couloirs
    corridor_min_s: float = 60.0
    skip_gold_penalty: float = 10.0
    # Profils par archétype et par objectif (valeurs de départ du cahier R3 §4.2)
    room_profiles: dict = field(default_factory=lambda: {
        "diesel": {
            "endurance": {"g0": 2.0, "g1": 3.0, "fw": 0.68},
            "threshold": {"g0": 3.0, "g1": 4.0, "fw": 0.90},
        },
        "puncheur": {
            "vo2max": {"bump_s": 15.0, "valley_s": 30.0, "bump_grade": 9.0, "valley_grade": -2.0,
                       "fw_bump": 1.06, "fw_valley": 0.67,
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
