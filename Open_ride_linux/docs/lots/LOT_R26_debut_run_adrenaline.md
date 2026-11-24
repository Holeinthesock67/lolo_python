# Lot R26 – Début de run et adrénaline du Cyber-Rogue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Début de run et adrénaline du Cyber-Rogue : échauffement qui charge l'adrénaline, consignes jugées sur 8 s à 10 % près avec marge de sortie, plage et écart en direct, sons d'entrée et de sortie (contrat révision 1.28) | Python, GDScript | R23 | Moyenne | **Livré le 22 novembre** (PR #960), **version 2.0** |

## 1. Constat

Essai du propriétaire du 21 novembre (« savoir quoi faire à tout moment » noté 3/5) :

1. « On commence sans adrénaline, il y a tout de suite une porte à frapper. »
2. « Mesure de puissance pour l'adrénaline pas assez lissée. »
3. « Très difficile de rester dans la plage. »

## 2. Causes

- Une frappe coûte 50 d'adrénaline (`strike_cost`), gagnée à 0,5 par seconde à la consigne : 100 s. La run part de 0 et
  l'échauffement ne chargeait rien ; la première cible (Grimpeur à 35 % de la première marche, verrous du boss) peut
  tomber avant.
- Consignes jugées sur `power_3s` (moyenne de 3 s) à 5 W près (`target_grace_w`, lot R23). L'écart type du trainer en
  salle est de 60 à 90 W brut (essai du 15 novembre) : sur 3 s, la moyenne bouge encore de 20 W et plus, et on sort de
  la plage sans rien changer.
- Les coupures du Click gauche du 21 novembre (verrou Zwift toutes les 52 s) ne touchent pas la puissance, qui vient
  du trainer ; la cardio figée non plus (elle ne juge rien).

## 3. Travail (choix du propriétaire)

Une seule règle partout : **à la consigne, l'adrénaline monte**, échauffement compris.

- `rogue/run.py` : puissance jugée = moyenne des `judged_power_s` (8 s) dernières secondes de la run, calculée par le
  mode ; l'échauffement charge l'adrénaline à sa consigne (bas de la plage), avec les mêmes multiplicateurs de posture
  ; `rogue.adrenaline` et `adrenaline_trend` renseignés à l'échauffement ; champs `power_judged_w` et `in_target`,
  événements `target_in` et `target_out` (rien au premier pas d'une phase ou d'une salle).
- `rogue/combat.py` : `target_grace` (10 % de la consigne, au moins 5 W) et `in_target` (entrée à la consigne moins la
  tolérance, sortie à la consigne moins 1,5 fois la tolérance), règle unique de l'échauffement, des salles et du boss ;
  la surchauffe garde la même tolérance.
- `balance.toml` : `target_grace_frac = 0.10`, `target_exit_mult = 1.5`, `judged_power_s = 8.0`.
- `session.py` : `power_3s` reste pour le HUD classique ; le mode juge sur sa propre moyenne.
- Engine : HUD du mode à la puissance jugée ; « Garde ≥ 200 W · tu es à 186 W (−14 W) », « ✔ » dans la plage ;
  jauge d'adrénaline et sa tendance affichées à l'échauffement ; consigne de l'échauffement « Tiens la consigne : ton
  adrénaline se charge pour la première salle » ; sons `rogue_target_in` (quinte qui monte) et `rogue_target_out`
  (quinte qui descend).
- Contrat IPC révision 1.28 (ajouts compatibles).

## 4. Tests

- `core/tests/test_rogue_r26_debut_run.py` : réglages, tolérance, marge de sortie, moyenne de 8 s (bruit ±80 W),
  adrénaline chargée à l'échauffement (≥ 50 à la première salle), événements une fois par passage.
- Tests du mode adaptés (`step_in_room` impose la puissance jugée du pas ; `judged=None` : moyenne glissante).
- Engine : `test_rogue_guide_model.gd` (écart en direct, échauffement), `test_rogue_r23_retours.gd`,
  `test_rogue_sound_synth.gd`, `test_rogue_host.gd` (31 sons).
- Galerie du Cyber-Rogue dans le cloud en low, medium et high ; planche à valider ; passe PC ; essai sur le vélo.

## 5. Livraison

PR à venir, séparée de #933 et #956.
