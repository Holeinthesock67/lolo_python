# Lot R25 – Jauge « Réserve W' » retirée du HUD du Cyber-Rogue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Jauge « Réserve W' » retirée du HUD du Cyber-Rogue : sans effet sur le jeu, elle nuisait à la lisibilité | GDScript | R22, R23 | Petite | En revue, **version 2.0** |

## 1. Constat

Essai du 21 novembre : le propriétaire demande ce qu'est « Réserve W' ». C'est la 4e jauge du HUD en haut à gauche
(sous Ennemi, Bouclier, Adrénaline) : la réserve anaérobie W'bal (modèle de Skiba, lot R2), en % de W'. Elle se vide
au-dessus de la CP (la FTP par défaut) et se recharge en dessous. Aucune règle du jeu ne la lit (combat, Firewall,
cartes, surchauffe) : elle n'était qu'affichée. Décision du propriétaire : « Retirer si inutile », « ça nuit à la
lisibilité ».

## 2. Travail

- `rogue_hud_view.gd` : la jauge n'est plus créée ni dessinée ; restent Ennemi, Bouclier et Adrénaline (avec sa tendance).
- `rogue_hud_model.gd` : plus de `wbal_pct` ni `wbal_low`.
- `test_rogue_hud_model.gd` : le lissage se vérifie sur l'écart au Firewall ; absence de la jauge vérifiée.
- `GUIDE_UTILISATION.md` : jauges du HUD mises à jour.

Gardés : le calcul W'bal du core et les champs `w_bal_j` et `w_prime_j` de la trame (contrat IPC : un champ ne se
retire pas), le journal de la run. Le choix « W' » de l'écran de départ du mode reste en attente d'une décision du
propriétaire (il ne règle que ce calcul).

## 3. Tests

- `test_rogue_hud_model.gd`, `test_rogue_r23_retours.gd`, `test_rogue_guide_model.gd`, `test_rogue_host.gd`.
- Galerie du Cyber-Rogue dans le cloud en low, medium et high ; planche du HUD à faire valider.

## 4. Livraison

PR à venir, séparée de #933 (R24).
