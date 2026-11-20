# Lot GPL1 – Grand Prix des objets sur des boucles seulement

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Le Grand Prix des objets se court sur une boucle seulement : départ refusé en ligne, liste du mode réduite aux boucles étiquetées, réglage « Distance en ligne » retiré, bancs sur le Circuit des Prés | Python, GDScript, JSON | GP13, GP13b | Petite | En cours (20 novembre) |

Demande du propriétaire (fil GP13b, 20 novembre à 0 h 56, lancée le 20 novembre à 17 h 53) : le Grand Prix des objets ne se joue plus que sur des boucles. Principe du propriétaire : pas d'exception, tout reste cohérent. Branche partie de celle de GP13b (#932, parcours Corniche et Vignes, déjà en boucle), avec `main` fusionné.

## 1. Règle

Un **parcours de mode** (Grand Prix, Vélodrome, `core/src/openride_core/mode_routes.py`) est une **boucle** qui porte l'étiquette du mode. La règle est la même partout :

- core : `mode_routes.mode_of(fiche, type)` ne rend un mode que pour `type == "loop"` (dernier parcours du mode dans `last_choices`, séance conseillée sur les parcours libres) ;
- engine : `CatalogModel.mode_route_ids` ne garde que les boucles étiquetées ; la liste du Grand Prix ne montre donc que ses boucles, et une trace en ligne étiquetée `grandprix` reste un parcours libre, dans la liste générale ;
- la piste du vélodrome est déjà une boucle : rien ne change pour elle.

## 2. Réalisation

- **Départ** : `CoreSession._grandprix_course` refuse un parcours en ligne (`bad_args`, « Grand Prix des objets : il se court sur une boucle… ») comme le monde ouvert ; la course fait `laps` tours. `GP_RUNOUT_M` (ligne posée 30 m avant le bout) et `boxes.MIN_COURSE_M` (course en ligne de 1 km au moins) disparaissent. `END_GAP_M` (file des bots arrivés au bout d'un parcours en ligne) reste pour les autres modes.
- **Réglage** : `grandprix.distance_km` (« Grand Prix : distance en ligne ») est retiré de `config.py`, des bornes, des clés du joueur et des réglages du menu. La clé encore écrite dans un `config.toml` ou un `profil.toml` est ignorée sans alerte « faute de frappe » ni « réglage de la machine » : nouvelle table `config.RETIRED_KEYS`, note au journal en information.
- **Menu** : l'écran Prêt du Grand Prix a une liste fixe de réglages (`MenuFlow.GRANDPRIX_KEYS` : adversaires, tours, niveau et objectif des bots, chaos, écart des boîtes), comme le Dernier survivant ; « Lancer » donne « 3 tours, 9,0 km » et se grise sur un parcours en ligne (« le Grand Prix se court sur une boucle »), comme le refus du core.
- **Module pur** `grandprix/mode.py` inchangé : il sait toujours courir sur une abscisse sans tour (tests purs), mais la séance ne lui donne plus que des boucles.
- **Contrat IPC** : aucune révision. `summary.gp.distance_km` reste au schéma (facultatif, journaux d'avant) ; le core écrit toujours `laps`. Note ajoutée au §`gp` de `ipc_v1.md`.
- **Bancs** : `sim_bench` a un monde `circuit` (Circuit des Prés, écrit par `make_biome_world.py --circuit`) ; sur une boucle, les captures en distance (`at_m`, `every_m`) comptent la distance parcourue, tours compris. `grand_prix`, `grand_prix_onze`, `grand_prix_gp4_voiture` et `grand_prix_gp4_furtif` passent du Col du lacet (5 km en ligne) au Circuit des Prés en 2 tours ; captures 35 m avant chaque vraie rangée de boîtes (769 m en chaos fou ; avant, `every_m` de 1 000 m ne tombait juste qu'à la première) ; appuis sur Z des GP4 recalés sur les passages estimés à 200 W sur le circuit.
- **Banc des menus** `grand_prix` : entrée sur la boucle d'essai, liste du mode sans la course en ligne d'essai ni le Col du lacet, tours ramenés à 2 au Click, objets, lancement, bilan, puis la course en ligne d'essai dans la liste générale.
- **Documents** : guide d'utilisation (modes à parcours propres, Grand Prix), SRS (`[grandprix]`), plan de la série GP, cahier GP13 (§4), recette de la série GP, outils de test.

## 3. Tests

- Core : `test_grandprix_session.py` (refus en ligne, course de 3 tours, 11 adversaires en chaos fou sans contact sur une boucle, réglages du menu sans distance), `test_gp4_voiture_furtif.py` (voiture d'équipe et usagers de la route sur une boucle de 5 km), `test_mode_routes.py` (trace en ligne étiquetée : parcours libre), `test_jeu_de_base.py`, `test_biome_demo_world.py` (chaque parcours `grandprix` du jeu de base est une boucle), `test_config_validation.py` et `test_config_couches.py` (clé retirée ignorée sans alerte), `test_sim_bench_scenarios.py` (scénarios sur le circuit, captures avant chaque rangée).
- Engine : `test_grandprix_menu.gd` (liste du mode, écran Prêt sans distance, Lancer grisé en ligne), `test_mode_routes.gd` (trace en ligne étiquetée dans la liste générale).

## 4. Recette PC (fil de fusion)

Bancs low, medium et high (budgets GPU 8 / 13 / 16 ms), captures à faire valider par le propriétaire avant la fusion :

```bash
cd /home/utilisateur/Games/lolo_python/Open_ride_linux
for q in low medium high; do
  python3 engine/tests/menu_bench.py --scenario grand_prix --qualite $q --native --out ~/OpenRide/menu_bench/gpl1_$q
  for sc in grand_prix grand_prix_onze; do
    python3 engine/tests/sim_bench.py --scenario $sc --quality $q --native --probe --out ~/OpenRide/sim_bench/gpl1_${sc}_$q
  done
done
```

Captures à regarder : `gp9_pret_boucle` et `gp9_pret` (écran Prêt sans « Distance en ligne », « 3 tours, 0,8 km » puis « 2 tours, 0,5 km »), captures `d…` des bancs avant chaque rangée de boîtes au premier et au second tour.
