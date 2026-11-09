# Essai PC du lot U3 (mer, côte et plages au compilateur), troisième passage (r790c)

Branche : `claude/project-thread-xqvi3w` (PR #830, reprise de #790), tête à jour (étapes de la tâche `osm` mesurées). Sans vélo. Durée : environ 25 min.
À lancer **par le fil « Fusionner les PR et séquencer les mesures »** (file unique du PC).

Ce qui a changé depuis r790 (8-9 novembre) :
- pire image de 142 ms en medium et high : la pleine mer est maintenant écrite en blocs rectangulaires
  (au lieu d'une aire par carré de 1 km), et les bateaux ne parcourent plus la route quand elle est loin ;
  les tronçons 1 et 4, préparés en 20-23 s à r790, doivent tomber sous la seconde ;
- tracé de 11,27 km au lieu de 8 : la D940 tirée d'OSM est coupée à 8 km depuis Wissant (`couper_gpx.py`) ;
- vue de dessus en SVG, sans Pillow (`plan_world.py` n'a plus besoin d'aucun paquet).

r790b (9 novembre, 8h21-8h37) : 56 aires de mer, GPU OK, mais pire image 124 / 149 ms en medium / high et tâches `osm` 1 et 4
toujours à 20-26 s. Les blocs de mer n'étaient donc pas la cause. r790c mesure le détail de la tâche `osm` (lignes
`osm_eau`, `osm_bateaux`, `osm_veg_poi`, `osm_faune`, `osm_circulation` dans `*_sonde_taches.csv`) ; la trace est la même qu'à r790b.

## Fichiers (dossier `plans/u3/` des fichiers du projet)

- `couper_gpx.py` : coupe une trace GPX à 8 km (Python seul).
- `plan_world.py` : vue de dessus d'un `.world` en SVG (Python seul).
- `cote_opale_essai.gpx` : ancien tracé en lignes droites (9 km), **ne plus l'utiliser** ; on repart de la D940.

## Étapes

1. Worktree de la branche, compilateur à jour :
   `git fetch origin claude/project-thread-xqvi3w` puis worktree, puis `pip install -e Open_ride_linux/compiler`.
2. Tracé : reprendre la trace coupée de r790b (802 points, 8,01 km) si elle est encore là ; sinon refaire la trace « D940 depuis OSM » comme à r790 (11,27 km, Wissant → Sangatte ; le fichier de r790 sert s'il est encore là),
   en `trace_d940.gpx`, sens Wissant → Sangatte. Puis :
   `python3 couper_gpx.py trace_d940.gpx cote_opale_essai.gpx --km 8`
   Attendu : « coupée : 8.00 km ». Si la trace part de Sangatte, ajouter `--depuis-la-fin`.
3. Compiler (réseau nécessaire) :
   `openride-compiler build cote_opale_essai.gpx --out <dossier de mesure>/routes --force --layers route,terrain,buildings,vegetation,poi,water,coast,roads,segments`
   Noter la ligne `côte : N ligne(s), N plage(s), N aire(s) de mer` (r790 : 214 aires ; attendu nettement moins), la longueur (8.00 km) et la durée.
4. Contrôler : `openride-compiler verify <…>/cote-opale-essai.world` → « valide ».
5. Vue de dessus : `python3 plan_world.py <…>/cote-opale-essai.world plan_u3.svg`
   Attendu : la Manche au nord-ouest de la route, du rouge (falaise) au cap Blanc-Nez, du jaune (sable) devant Wissant, aucun bloc de mer sur la terre.
6. Banc et captures, 3 qualités (budgets GPU low 8 ms, medium 13 ms, high 16 ms), comme r790 :
   `python3 Open_ride_linux/engine/tests/sim_bench.py --native --probe --muet --quality Q --size 1680x1050 --world <…>/cote-opale-essai.world --every 30 --out <dossier de mesure>/Q` pour Q = low, medium, high.
7. Rendre aussi les fichiers du monde des tronçons 1 et 4 (données OSM publiques, rien de privé) :
   `water/`, `vegetation/`, `poi/`, `roads/`, `buildings/` et `coast/` : `chunk_001.json` et `chunk_004.json` de chacun, plus `manifest.json`.
8. Rendre : `plan_u3.svg`, les captures, `sim_bench.txt` de chaque qualité, les CSV de la sonde (surtout `*_sonde_taches.csv` : durée des tâches `osm`), la sortie des étapes 2 et 3.

## À regarder

- « à-coups : pire image » sous 100 ms dans les 3 qualités ; tâches `osm` sous la seconde.
- Tuiles proches et arbres chargés avant le départ (vers 20-25 s, comme les autres parcours), pas pendant la sortie.
- Captures : la mer visible depuis la route près de Wissant, sans trou ni bloc de travers ; scintillement possible au bord de l'eau (mer à 0 m, MNT à 0 m au large : correction dans U9 si besoin).

Les captures sont à valider par le propriétaire avant la fusion de la PR.
