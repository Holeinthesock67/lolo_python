# Essai PC du lot U3 (mer, côte et plages au compilateur)

Branche : `claude/project-thread-f69c9e` (PR du lot U3). Sans vélo. Durée : environ 25 min.
À lancer **par le fil « Fusionner les PR et séquencer les mesures »** (file unique du PC).

Pourquoi sur le PC : Overpass (OpenStreetMap) est bloqué depuis le cloud ; le cloud n'a testé que des côtes synthétiques.

## Fichiers

- `cote_opale_essai.gpx` : 8 km sur la route côtière entre Wissant et Sangatte (Côte d'Opale, lieu public) : plage de sable de Wissant, falaises du cap Blanc-Nez, plage de Sangatte.
- `plan_world.py` : vue de dessus d'un `.world` (mer par tronçon, rivage coloré, plages, route).

## Étapes

1. Mettre la branche et le compilateur à jour :
   `cd ~/Games/lolo_python && git fetch origin claude/project-thread-f69c9e && git checkout claude/project-thread-f69c9e && pip install -e Open_ride_linux/compiler`
2. Compiler (réseau nécessaire la première fois) :
   `openride-compiler build cote_opale_essai.gpx --out ~/.local/share/openride/routes --force --layers route,terrain,buildings,vegetation,poi,water,coast,roads,segments`
   Noter la ligne `côte : N ligne(s), N plage(s), N aire(s) de mer` et la durée totale.
3. Contrôler : `openride-compiler verify ~/.local/share/openride/routes/cote-opale-essai.world` → « valide ».
4. Vue de dessus : `python3 plan_world.py ~/.local/share/openride/routes/cote-opale-essai.world plan_u3.png`.
   Attendu : la mer au nord-ouest de la route (la Manche), du rouge (falaise) autour du cap Blanc-Nez, du jaune (sable) devant Wissant et Sangatte, aucun carré de mer sur la terre.
5. Banc et captures, 3 qualités (budgets GPU low 8 ms, medium 13 ms, high 16 ms) :
   `python3 Open_ride_linux/engine/tests/sim_bench.py --native --probe --muet --quality Q --size 1680x1050 --world ~/.local/share/openride/routes/cote-opale-essai.world --every 30 --out ~/OpenRide/mesures/2026-11-08-u3/Q` pour Q = low, medium, high.
6. Rendre : `plan_u3.png`, les captures, `sim_bench.txt` de chaque qualité, la sortie de l'étape 2.

## Points à regarder sur les captures

- La mer (aplat d'eau des plans d'eau, l'animation est pour U9) couvre bien le large, sans trou ni carré de travers.
- **Scintillement au bord de l'eau** : la mer est à 0 m (contrat) et le terrain sous la mer n'est pas modifié (cahier) ; si le MNT vaut aussi 0 m au large, la surface et le sol peuvent se battre. Si c'est le cas, la correction va dans U9 (engine) ou dans une décision sur le niveau de la mer (le cahier U3 parlait d'un niveau négatif possible, le contrat dit 0 m).
- Coût GPU : la mer ajoute des aires d'eau ; comparer au même parcours compilé sans `water,coast` si le budget est dépassé.

Les captures sont à valider par le propriétaire avant la fusion de la PR.
