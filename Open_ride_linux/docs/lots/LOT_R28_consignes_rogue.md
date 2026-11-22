# Lot R28 – Consignes du Cyber-Rogue : plage exacte, puissance écrite une fois, adrénaline à 1 par seconde

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Consignes du Cyber-Rogue : la plage affichée est la plage jugée, la puissance n'est écrite qu'une fois, l'adrénaline monte de 1 par seconde quelle que soit la cadence (contrat révision 1.33, provisoire) | Python, GDScript | R26 | Petite | En revue, **version 2.0** |

## 1. Constat

Essai du propriétaire du 22 novembre (analyse : `rogue-r28/ANALYSE_ESSAI_ROGUE_2026-11-22.md` des fichiers du projet) :

1. L'écran affiche « 170–195 W », mais l'adrénaline charge dès 153 W : le jeu accepte 10 % sous la consigne (lot R26).
2. La puissance est écrite trois fois (pavé en haut à gauche, sous la consigne, dans l'écart en direct).
3. Une frappe Z demande 100 s à la consigne (0,5 par seconde), et 143 s en posture ROC (× 0,7, malus caché).

## 2. Choix du propriétaire

- Carte du 22 novembre : « +1/s, sans malus ROC (A+C) ».
- « Afficher exactement la plage jugée » ; « chaque information n'apparaîtrait plus qu'à un seul endroit ».

## 3. Règle

- `target_pct` (contrat IPC) donne la plage **jugée** : bas = consigne − tolérance (10 %, au moins 5 W), arrondi vers
  l'intérieur ; haut = plafond de surchauffe + tolérance. À la puissance écrite, on est dans la plage.
  Fonction unique : `combat.judged_band_pct`.
- Adrénaline : `adrenaline_per_s = 1.0`, multiplicateurs ROC et Véloce à 1,0 : une frappe toutes les 50 s.
- Écran : la puissance n'est écrite qu'en haut à gauche. Sous la plage : « ✔ dans la plage », « il manque 14 W »
  ou « 12 W de trop » ; conseil « Monte dans la plage pour remplir l'adrénaline (12/50) » ou « Dans la plage :
  l'adrénaline monte ». Toujours des mots, jamais la couleur seule.

## 4. Contrat

Précision compatible du champ `target_pct` (révision 1.33 **provisoire**, à renuméroter à la fusion au-dessus de
`CONTRACT_REV` de main) : mêmes clés, mêmes types.

## 5. Tests

- `core/tests/test_rogue_r28_consignes.py` : plage jugée, cohérence avec `in_target`, 1 par seconde.
- `test_rogue_r23_retours.py`, `test_rogue_r26_debut_run.py`, `test_contract_ipc.py` mis à jour.
- Engine : `test_rogue_guide_model.gd` (62), `test_rogue_r23_retours.gd` (85), `test_rogue_hud_model.gd` (32).
- Galerie du Cyber-Rogue en low, medium et high ; planche à valider par le propriétaire ; essai vélo de 10 minutes.
