# Lot DPS1 : dépassement des cyclistes du décor, règle commune et garde finale

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Dépassement des cyclistes du décor, règle commune et garde finale | Python, GDScript | AS11, DPB1 | Moyenne | Livré |

## 1. Constat (cahier DPB1, §5, et demande du propriétaire du 27 novembre)

Sur les démonstrations de 42 km à collines du lot DPB1, `test_decor_cyclists_never_touch` trouve des contacts sur
main : Route des Chênes 89, Route de la Banquise 27, hauts plateaux 7, steppe 5, toundra 70. Le propriétaire :
« il ne devrait plus y avoir de problème de dépassement, le fond ne semble pas réglé ». Rejoué avec d'autres tirages
que celui du jeu et d'autres vitesses, main n'est pas propre non plus : 371 contacts au tirage 1, 176 au tirage 2.

Le modèle des cyclistes du décor (`road_cyclists.py`, jumeau `road_cyclists_model.gd`) est un empilement de règles
locales (P32, AS7 à AS11), chacune écrite pour un cas ; un nouveau parcours en révèle un autre. Deux causes communes,
et aucun filet :

1. Un groupe qui en double un autre choisit sa ligne sans compter le cycliste comme un usager : il ne le regarde
   qu'au début du dépassement, à moins de 30 m, sans sa vitesse. Le cycliste le rattrape sur sa ligne.
2. Un groupe `overtake` qui vient de doubler le cycliste se rabat devant lui derrière un groupe lent qu'il rattrape
   aussitôt : il freine net, à moitié rabattu, devant le cycliste.
3. Rien ne garantit, au bout du pas, que personne ne chevauche personne : la garde `road_space` (AS11) le fait pour la
   séance, pas le modèle lui-même (bancs, engine pour les groupes lointains).

## 2. Règle

1. **Le cycliste est un usager comme un bot** (`_rider_lane_group`) : quand un groupe en double un autre, sa ligne est
   une de celles qu'on ne prend ni ne traverse, s'il sera à hauteur pendant le dépassement : à moins de PASS_START_M
   maintenant, ou rattrapé avant la fin du dépassement (fenêtre en temps, au plus PASS_HORIZON_S).
2. **Pas de rabattement dans un trou qui se ferme** (`_lane_closing`) : un `overtake` reste sur sa ligne de dépassement
   tant qu'un groupe plus lent est sur sa place de retour et qu'il le rattraperait en moins de MERGE_LOOK_S.
3. **Garde finale du registre** (`_guard`, en fin de chaque pas, même principe que `road_space.resolve`) : le cycliste
   et les bots sont posés d'abord et ne bougent pas, puis les groupes du plus avancé au plus en retrait dans leur sens.
   Un membre qui touche un usager posé devant lui (gabarit GUARD_LEN_M × GUARD_WIDTH_M, MIN_CENTRE_M en travers du
   cycliste) fait reculer son groupe derrière lui, à sa vitesse au plus. Touché par derrière (le cycliste qui le
   rattrape) ou par un usager d'en face, il s'écarte à la place libre la plus proche ; sinon, devant le cycliste
   seulement, son groupe est avancé à sa vitesse. Jamais avancé devant un autre cycliste du décor : il passe derrière.
   Corrections comptées (`guard_total`, `guard_kinds` par sorte) : la règle de chaque groupe doit les rendre rares.

Mêmes changements dans le core et l'engine ; relevé de parité régénéré. Pas d'IPC, ni WORLDGEN, ni SCHEMA.

## 3. Vérification

- Contrôle de `test_decor_cyclists_never_touch` rejoué sur les 33 routes (jeu de base, recette, Chênes, Banquise et
  les 10 biomes d'essai de DPB1), 5 tirages, 8 vitesses de 20 à 55 km/h : 0 contact (main : 82 au seul tirage du
  jeu sur les essais, 371 et 176 aux tirages 1 et 2).
- `core/tests/test_road_cyclists_dps1.py` : six routes de DPB1 (pentes de route.json dans
  `core/tests/data/decor_profils_dps1.json`) à 25, 40 et 50 km/h ; trois autres tirages à 30 et 55 km/h (marqués
  `slow`) ; règles 1 à 3.
- `engine/tests/unit/test_road_cyclists_dps1.gd` : jumeau des règles 1 à 3, mêmes valeurs ; tests de l'engine des
  cyclistes du décor (modèle, parité, core, limite, AS8) verts.

## Livraison

- Branche `claude/project-thread-pul5ey`, depuis main ; indépendante de #1144 (DL2) et de #1132 (EC8), aucune ligne
  commune (même résultat avec #1144 appliquée en plus).
