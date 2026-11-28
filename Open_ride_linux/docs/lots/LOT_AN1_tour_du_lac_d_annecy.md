# Lot AN1 – « Tour du lac d'Annecy », pack « Tours célèbres » livré avec le jeu

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| « Tour du lac d'Annecy » (boucle de 38 km depuis Sevrier, lac, villages et ponts dessinés) dans un pack « Tours célèbres » livré à côté des Cols : couches choisies par pack (`layers` du `pack.toml`), paquet et écran Contenus à plusieurs packs | Python + Bash | PK1, EA1, EA4 | Moyenne | **En PR le 20 novembre** |

## 1. Objectif

Question du propriétaire du 20 novembre (18 h 44) : « Annecy a été généré lors des tests, est-il intégrable aux démos ? ». Les balades `ow-*.world` des bancs `ea1_lac` et `ea2_lac_loin` ne sont pas réutilisables : morceaux de route du monde ouvert liés à une balade, au schéma du cache et à `WORLDGEN_VERSION`, qui bougent encore, et cache réel partagé avec le jeu. Le tour du lac est donc **reconstruit** par la chaîne du pack Cols (PK1) : recette publique (centres des villages), OpenStreetMap et MNT, compilé une fois sur le PC, livré dans `paquet/`, installé sans réseau au premier lancement. Étude : `plans/ETUDE_ANNECY_DEMO_2026-11-20.md` du dossier du projet.

Le parcours compilé ne dépend pas du générateur du monde ouvert : #936 (sol) et #907 (mer) ne touchent que `worldgen/`. Il reprend le niveau du lac (EA1) et les ponts dessinés (EA4) des parcours compilés.

## 2. Spécification

| # | Règle |
| --- | --- |
| AN1-1 | **Recette** `route_packs/tours_celebres/tour_du_lac_d_annecy.toml` : boucle dans le sens des aiguilles d'une montre (lac à droite), départ et arrivée à Sevrier, par Annecy, Veyrier-du-Lac, Menthon-Saint-Bernard, Talloires, le Bout-du-Lac et Duingt ; premier point = dernier point, le compilateur en fait une boucle (`type loop`). Référence 38,1 km et 265 m de dénivelé (mesurés le 25 novembre sur les réponses Overpass du banc du 24 novembre, MNT Copernicus ; point haut 556 m au-dessus de Talloires). Le point du Bout-du-Lac est sur la D 1508 (route d'Annecy) : au centre du hameau, il tombait sur une voie privée isolée, sans chemin vers Talloires ni Duingt (refus du banc du 24 novembre). |
| AN1-2 | **Couches par pack** : clé facultative `layers` du `pack.toml` (noms de `constants.WORLD_LAYERS`, `route` obligatoire), contrôlée à l'installation du pack. `build` sans `--layers` prend les couches du pack de la trace, sinon celles par défaut ; `build-all` aussi, donc la construction par le réseau (Contenus sans paquet) dessine le lac comme le paquet. « Tours célèbres » : route, terrain, biome, segments, eau, maisons, végétation, routes, ponts. Les Cols gardent les couches par défaut. |
| AN1-3 | **Paquet à plusieurs packs** : `scripts/build_pack_base.sh` construit tous les packs de `route_packs/` (variable `PACKS` pour en choisir), chacun dans `paquet/packs/<pack>/` ; `ONLY` saute un pack sans aucun des parcours demandés. `pack_bundle.load_all()` lit tous les packs du paquet. |
| AN1-4 | **Contenus** : une ligne par pack de base (`routes:<pack>`, table `contents.BASE_PACKS` pour les mots du menu), installée depuis le paquet ou construite par le réseau ; les contenus de départ installent tous les packs du paquet (« 21 cols célèbres, 1 tour célèbre »). |
| AN1-5 | **Crédits** : ceux du pack Cols (OpenStreetMap ODbL, Copernicus, WorldCover), sur la ligne du pack et au §10 du guide. Aucune trace réelle recopiée. |

## 3. Contrat

Aucun changement d'IPC : le message `contents` porte une ligne de plus (même forme). Format `.world` inchangé.

## 4. Fichiers

- Compilateur : `constants.py` (`WORLD_LAYERS`, `DEFAULT_WORLD_LAYERS`), `route_pack.py` (`layers`, `pack_layers`), `cli.py` (`build`, `build-all`), `route_packs/tours_celebres/`.
- Core : `pack_bundle.py` (`load_all`, identifiant du pack), `contents.py` (packs de base).
- Script : `scripts/build_pack_base.sh`.
- Tests : `compiler/tests/test_route_recipe.py` (couches du pack à `build` et `build-all`, contrôle de `layers`, recette du lac), `core/tests/test_pack_bundle.py` (deux packs au premier lancement, ligne « Tours célèbres »).

## 5. Recette PC (file PC, catégorie rendu, ≈ 30 min)

Depuis `~/Games/lolo_python/Open_ride_linux`, branche du lot, `HOME` réel non touché (le script travaille dans un dossier temporaire et n'écrit que dans `paquet/`).

1. **Construction** : `PACKS=tours_celebres scripts/build_pack_base.sh 2>&1 | tee <sortie>/construction.log`. Si la recette est refusée (« longueur X m au lieu de 38100 » ou « dénivelé Y m au lieu de 265 »), noter X et Y dans le compte rendu : la référence est corrigée dans la PR, puis on relance. Attendu : code 0, poids du pack (estimé 15 à 30 Mo).
2. **Contrôle** : `core/.venv/bin/python -m openride_core.pack_bundle verify paquet/packs/tours_celebres` puis `info`.
3. **Sol sur la route** : `python3 scripts/controle_sol_route.py --out <sortie>/sol paquet/packs/tours_celebres/routes/tour-du-lac-d-annecy.world` (si présent sur main, #936).
4. **Banc perf** low / medium / high (budgets GPU 8 / 13 / 16 ms, pire image < 100 ms), départ (Sevrier), Annecy (≈ 6 km) et Talloires (≈ 20 km) : `python3 engine/tests/sim_bench.py --world paquet/packs/tours_celebres/routes/tour-du-lac-d-annecy.world --quality <q> --probe --at-m <0, 6000, 20000>`.
5. **Captures** medium : lac vu de la route à Sevrier, Annecy (maisons), Talloires, un pont ; écran « Réglages › Contenus » avec les deux packs.

**Part du propriétaire** : valider la planche et le poids.
