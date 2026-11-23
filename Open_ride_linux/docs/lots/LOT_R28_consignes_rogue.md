# Lot R28 – Consignes du Cyber-Rogue : vraie consigne, plage exacte, puissance écrite une fois, adrénaline à 1 par seconde

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Consignes du Cyber-Rogue : la consigne écrite est celle qui gagne et qui charge l'adrénaline, la puissance n'est écrite qu'une fois, l'adrénaline monte de 1 par seconde quelle que soit la cadence (contrat révision 1.33, provisoire) | Python, GDScript | R26 | Petite | En revue, **version 2.0** |

## 1. Constat

Essai du propriétaire du 22 novembre (analyse : `rogue-r28/ANALYSE_ESSAI_ROGUE_2026-11-22.md` des fichiers du projet) :

1. L'écran affiche « 170–195 W », mais l'adrénaline charge dès 153 W : le jeu accepte 10 % sous la consigne (lot R26).
2. La puissance est écrite trois fois (pavé en haut à gauche, sous la consigne, dans l'écart en direct).
3. Banc de cohérence (§2.5 du document de cohérence du level design) : le boss du seuil et de la VO2max ne se bat
   qu'à 11,8 % au-dessus de la consigne écrite (`boss_hp_factor` = 1,118) ; 0 à 35 % de boss battus.
4. Une frappe Z demande 100 s à la consigne (0,5 par seconde), et 143 s en posture ROC (× 0,7, malus caché).

## 2. Choix du propriétaire

- Carte du 22 novembre : « +1/s, sans malus ROC (A+C) ».
- « Affiche une vraie consigne » (22 novembre, 18 h 09) : la résistance du boss ne baisse pas, la consigne écrite monte.
- « Afficher exactement la plage jugée » ; « chaque information n'apparaîtrait plus qu'à un seul endroit ».

## 3. Règle

- Consigne écrite d'une salle ou du boss = la puissance qui vide la barre à temps : cible du profil × facteur de PV
  (`combat.win_target` ; 1,118 au boss, 1,02 à 1,038 en salle). Elle sert à tout : l'écran, l'adrénaline, la surchauffe.
- `target_pct` (contrat IPC) donne la plage jugée : bas = cette consigne, arrondie au-dessus ; haut = plafond de
  surchauffe + tolérance, arrondi au-dessous. On entre dans la plage à la consigne écrite ; la tolérance du lot R26
  (10 %, au moins 5 W) ne sert plus qu'à la sortie (`target_exit_mult` = 1), et l'écran le dit : « ✔ marge :
  remonte de 8 W ». Bornes en watts au pas de 5 W, arrondies vers l'intérieur de la plage.
- Adrénaline : `adrenaline_per_s = 1.0`, multiplicateurs ROC et Véloce à 1,0 : une frappe toutes les 50 s.
- Écran : la puissance n'est écrite qu'en haut à gauche. Sous la plage : « ✔ dans la plage », « il manque 14 W »
  ou « 12 W de trop » ; conseil « Monte dans la plage pour remplir l'adrénaline (12/50) » ou « Dans la plage :
  l'adrénaline monte ». Toujours des mots, jamais la couleur seule.

## 3 bis. Voile et halo (retour du 23 novembre)

« Il y a encore un peu trop brouillard/halo en médium et high » : l'éclair d'une attaque réussie couvrait tout l'écran
d'un crème à 45 % (voile gris sur la capture « Z : FRAPPE ! », dans les trois qualités) ; il passe à 15 %
(`HIT_FLASH_ALPHA`). Le glow du medium et du high passe à 4 niveaux, intensité 0,8, sans bloom (le bloom éclairait
tout l'écran). La brume reste celle du lot R27.

## 4. Contrat

Précision compatible des champs `target_pct` et `in_target` (révision 1.33 **provisoire**, à renuméroter à la fusion au-dessus de
`CONTRACT_REV` de main) : mêmes clés, mêmes types.

## 5. Tests

- `core/tests/test_rogue_r28_consignes.py` : consigne qui gagne, plage jugée, cohérence avec `in_target`, 1 par seconde.
- Le cycliste simulé (`rogue_sim`, `rogue_bout_en_bout`) suit la consigne écrite.
- `test_rogue_r23_retours.py`, `test_rogue_r26_debut_run.py`, `test_contract_ipc.py` mis à jour.
- Engine : `test_rogue_guide_model.gd` (62), `test_rogue_r23_retours.gd` (85), `test_rogue_hud_model.gd` (32).
- Galerie du Cyber-Rogue en low, medium et high ; planche à valider par le propriétaire ; essai vélo de 10 minutes.
