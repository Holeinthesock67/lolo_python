"""Valeurs d'équilibrage du mode Cyber-Rogue, réunies dans un seul objet (lot R2).

Les lots R4 à R6 et R15 ajoutent leurs champs ici ; R7 les charge depuis un fichier de données.
"""

from __future__ import annotations

from dataclasses import dataclass


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


DEFAULT_BALANCE = RogueBalance()
