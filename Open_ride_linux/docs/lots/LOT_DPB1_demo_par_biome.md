# Lot DPB1 – Une démonstration dédiée à chaque biome

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Une démonstration de 42 km en ligne pour chaque biome qui n'avait qu'un tronçon d'une démonstration partagée ; profil de 40 km propre ; jeu de base seul (bancs inchangés) ; DPB1a : 12 biomes, puis les 5 autres après le correctif des cyclistes du décor | Python, JSON | DL1, DB1, DB3, VR4 | Moyenne | En PR |

Demande du propriétaire du 27 novembre 2026 (3 h 50) : « Oui » à une démonstration dédiée à chaque biome, puis « et au moins 40 km si ligne droite » (boucles d'au moins 15 km, variantes courtes réservées aux bancs). Cadrage : `/mnt/project-files/plans/CADRAGE_DEMO_PAR_BIOME_2026-11-27.md` (bibliothèque du projet).

## 1. État avant le lot

23 biomes dans le compilateur (`biomes.BIOMES`). Ont déjà une démonstration à eux dans la liste des parcours : `japan` (Route des Érables), `reef` (Récif des tortues), `volcanic` (Volcan en flammes). N'ont qu'une boucle du Grand Prix, hors de la liste libre : `temperate_grassland`, `mediterranean`, `farmland`. Les 17 autres ne sont qu'un tronçon d'une démonstration partagée.

## 2. Règle

- Une démonstration d'un seul biome est une route ouverte de 42 km (21 blocs de 2 km du décor du biome, `BLOCKS`, répétés par `line_repeat` du lot DL1).
- Profil (`LINE_PROFILES`) : tronçons (km, %) fondus sur `PROFILE_RAMP_M` (400 m), les ondulations du biome (`GRADE` moins `GRADE_MEAN`) par-dessus. Sans lui, la pente moyenne tenue sur 42 km donnerait 3 000 m de montée à l'alpin et mènerait la jungle sous la mer. Biome sans pente moyenne (côte) : pas de profil.
- Jeu de base seul (`GAME_ONLY`) : absentes de la variante de recette (`--recette`), donc des bancs. `--biome <biome> --recette` donne encore 6 km pour un essai.
- Fiche : description en `{km}` et étiquette `biome` (filtre possible du menu ; d'aucun mode, `mode_routes`).
- Lieux : noms ajoutés à la fin des listes de `PLACE_NAMES` (7 par clé) ; les premiers noms ne changent pas.

## 3. DPB1a (12 biomes)

| Parcours | Biome | D+ | Altitudes | Pentes |
| --- | --- | --- | --- | --- |
| Route des Alpages (`demo-alpages`) | `alpine` | 1564 m | 6 → 1311 m | −6,5 à 8,5 % |
| Route du Littoral (`demo-littoral`) | `coast` | 47 m | 6 → 21 m | −0,3 à 0,3 % |
| Route de la Jungle (`demo-jungle`) | `jungle` | 556 m | 6 → 243 m | −4,8 à 4,2 % |
| Route de la Savane (`demo-savane`) | `savanna` | 456 m | 6 → 316 m | −3,1 à 2,9 % |
| Route des Landes (`demo-landes`) | `atlantic_heath` | 434 m | 6 → 246 m | −3,8 à 3,2 % |
| Route des Canyons (`demo-canyons`) | `rock_desert` | 747 m | 6 → 518 m | −5,6 à 5,4 % |
| Route des Dunes (`demo-dunes`) | `sand_desert` | 181 m | 6 → 43 m | −1,2 à 1,2 % |
| Route du Delta (`demo-delta`) | `wetland` | 26 m | 6 → 8 m | −0,2 à 0,2 % |
| Route de la Taïga (`demo-taiga`) | `boreal_forest` | 651 m | 6 → 406 m | −4,2 à 4,3 % |
| Route du Bush (`demo-bush`) | `eucalypt_woodland` | 514 m | 6 → 296 m | −3,7 à 3,8 % |
| Route des Grands Cèdres (`demo-grands-cedres`) | `temperate_rainforest` | 1091 m | 6 → 776 m | −5,3 à 5,7 % |
| Route des Nuages (`demo-nuages`) | `cloud_forest` | 1470 m | 6 → 1286 m | −4,8 à 6,7 % |

Route des Canyons : variante régionale `canyon` (grès rose) sur toutes ses tuiles (`BIOME_VARIANTS`), le désert de roche n'ayant de décor que dans ce paysage. Route des Alpages et Route des Nuages finissent au col (sommet du parcours). Désert de sable et delta sans profil (pas de pente moyenne).

Poids : environ 6 Mo et 3 à 5 s de génération par parcours, aux contenus de départ (rien dans le paquet). Recette du jeu : `captures_demo.py` et le scénario `parcours_demo` (délai des contenus de départ porté à 240 s : 12 parcours de plus, environ 50 s) suivent la liste.

## 4. Après le correctif des cyclistes du décor

`temperate_forest` (Route des Chênes), `polar` (Route de la Banquise), `high_plateau`, `steppe` et `tundra` : écrites et essayées, mais `test_decor_cyclists_never_touch` y trouve des contacts (voir §5) ; elles reviennent après le lot « Corriger le dépassement des cyclistes du décor ». Plus tard, en option : prairie, méditerranéen et terres agricoles en parcours libre.

## 5. Constat : cyclistes du décor sur la ligne du cycliste (lot à part)

Route des Chênes (collines, D+ 951 m) et Route de la Banquise (D+ 444 m) écrites (de même hauts plateaux, steppe et toundra, essai du 27/11 : 7, 5 et 70 contacts), mais `test_decor_cyclists_never_touch` y trouve à 40 et 50 km/h des contacts : dans une côte, un groupe `overtake` rabattu (`held`) en double un autre en prenant la ligne du cycliste (`pass_lat` 1,2 m, `RIDER_LATERAL_M`), et le dépassement, commencé quand l'écart de vitesse était grand, dure assez pour que le cycliste arrive derrière et le rattrape à 1,6 m. La règle du cycliste de `road_cyclists._move` (plus de `PASS_START_M`) n'est lue qu'au début du dépassement, et sans la vitesse du cycliste. Essais : la lire à chaque pas et exiger que le cycliste ne rattrape pas le groupe avant la fin du dépassement règle les deux routes, mais un groupe qui renonce en cours de dépassement touche alors un autre groupe sur la Route du Sud ; changer le profil déplace seulement le contact. Le correctif touche la règle commune du core et de l'engine (`road_cyclists_model.gd`, relevé de parité) : lot à part, avant les 5 autres démonstrations. La garde finale `road_space` de la séance écarte déjà le chevauchement à l'écran.

## Livraison

- DPB1a : branche `claude/project-thread-m03uak`, empilée sur #945 (DL1).
