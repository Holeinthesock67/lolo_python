# Lot EN1 – Essai d'endurance avant livraison : séance de 2 h et saison de ligue enchaînées

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Essai d'endurance : séance de 2 h puis saison de la ligue d'hiver (8 semaines simulées, horloge du core décalée) dans le même core et le même engine, mémoire, GPU, à-coups et fichiers jugés par des seuils chiffrés | Python (outil de test) | X13, X16, CH3 (#989) | Petite | **Livré le 24 novembre** (PR #1014) ; suite EN1b (PR #1067, 25 novembre) |

Demande : audit de cohérence du 22 novembre (`statut/AUDIT_COHERENCE_QUALITE_2026-11-22.md`, lot majeur validé par
le propriétaire). L'essai d'une heure du lot X16 n'a jamais été fait sur le PC ; avant la livraison (J9), un essai
plus long, qui enchaîne aussi une saison de la ligue, observe ce que des semaines d'usage font à la mémoire, aux
à-coups et aux fichiers.

## 1. Livré

- `engine/tests/essai_endurance.py` : l'essai, une commande ; procédure, déroulé et critères dans
  `docs/ESSAI_ENDURANCE.md`.
- `engine/tests/horloge_decalee.py` : lance le core avec une horloge murale décalée, relue chaque seconde dans un
  fichier du banc ; la boucle à 50 Hz (horloge monotone) n'est pas touchée.
- Aucun code du jeu modifié : seulement des commandes du menu envoyées au core et le cycliste virtuel piloté par le
  fichier de contrôle du Bluetooth simulé (`control_file`).

## 2. Vérification

- Cloud, core seul, sur la branche de CH3 (#989) avec ce lot : `essai_endurance.py --court --sans-engine` (séance de
  2 min, manches de 60 s, voir « Livraison »).
- PC : `essai_endurance.py --native --court` (essai à blanc, ~25 min) puis l'essai complet de nuit.

## 3. Limites connues

- CH3a ne branche que la Course : 3 manches sur 8 jouables ; les autres sont simulées pour les rivaux jusqu'à CH3b,
  que l'essai suit de lui-même (`league.PLAYABLE_MODES`).
- Anneau synthétique sans décor OSM : décor léger ; le scénario `endurance` de `sim_bench.py` (village) reste
  l'essai du décor lourd.

## Recette PC
Catégorie : logique
- Cloud : essai à blanc en core seul (`--court --sans-engine`).
- PC : essai à blanc `--native --court` (~25 min), puis essai complet de nuit (~3 h 30 avec CH3a, ~6 h avec la
  ligue complète), jamais pendant un essai vélo ni un autre banc ; ne touche pas `~/OpenRide/Cache/monde`.
- Versions : aucune (WORLDGEN_VERSION, SCHEMA_VERSION et révision IPC inchangés)

## Livraison
- 22 novembre, cloud, core seul, branche de CH3 (#989, fusionnée depuis) avec ce lot, `essai_endurance.py --court
  --sans-engine` (séance de 6 min, manches de 90 s, anneau de 1,5 km) : 25 vérifications sur 25 sans échec. Saison
  créée (11 rivaux), manches 1, 5 et 8 (Course) courues et enregistrées « joueur », les 5 autres (modes pas encore
  branchés, CH3b) simulées pour les rivaux, saison close le lundi 18 janvier 2027 simulé ; 4 FIT. Mémoire du core au
  plus 63 Mo ; journaux de séance 1,4 Mo/h, FIT 96 Ko/h, `ligue.json` 4,6 Ko, `elo.json` 0,7 Ko, profil + 0,4 Mo en
  15 min. Pente de la mémoire du core non jugée (moins de 20 min mesurées) : l'essai de nuit sur le PC la juge.
