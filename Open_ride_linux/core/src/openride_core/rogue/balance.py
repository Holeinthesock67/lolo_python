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
    # Profils par archétype et par objectif (valeurs de départ du cahier R3 §4.2)
    room_profiles: dict = field(default_factory=lambda: {
        "diesel": {
            "endurance": {"g0": 2.0, "g1": 3.0, "fw": 0.68},
            "seuil": {"g0": 3.0, "g1": 4.0, "fw": 0.90},
        },
        "puncheur": {
            "vo2max": {"bump_s": 15.0, "valley_s": 30.0, "bump_grade": 9.0, "valley_grade": -2.0,
                       "fw_bump": 1.06, "fw_valley": 0.67,
                       "bump_s_30_30": 30.0, "fw_bump_30_30": 0.95, "fw_valley_30_30": 0.65},
        },
        "grimpeur": {
            "endurance": {"steps": (2.0, 3.0, 4.0), "step_s": 60.0, "fw": 0.70},
            "seuil": {"steps": (4.0, 7.0, 10.0), "step_s": 60.0, "fw": 0.88},
            "vo2max": {"steps": (5.0, 8.0, 10.0), "step_s": 60.0, "fw": 0.95},
        },
        "sprinteur": {
            "seuil": {"fw": 0.75, "burst_fw": 1.30, "burst_s": 10.0, "period_s": 45.0},
            "vo2max": {"fw": 0.80, "burst_fw": 1.50, "burst_s": 8.0, "period_s": 40.0},
        },
        "saboteur": {
            "endurance": {"lo": 1.0, "hi": 3.0, "fw": 0.68},
            "seuil": {"lo": 2.0, "hi": 5.0, "fw": 0.88},
        },
        "boss": {
            "endurance": {"p1_grade": 3.0, "p1_fw": 0.70, "p1_locks": 4,
                          "p2_grades": (4.0, 0.0, 5.0), "p2_fw": (0.80, 0.60, 0.85), "p2_block_s": 40.0,
                          "shock_period_s": 30.0, "p3_grade": 0.0, "p3_fw": 0.85},
            "seuil": {"p1_grade": 5.0, "p1_fw": 0.90, "p1_locks": 4,
                      "p2_grades": (8.0, 0.0, 10.0), "p2_fw": (1.00, 0.70, 1.05), "p2_block_s": 40.0,
                      "shock_period_s": 30.0, "p3_grade": 0.0, "p3_fw": 1.20},
        },
    })


DEFAULT_BALANCE = RogueBalance()
