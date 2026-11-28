# Lot DL2 – Boucles de démonstration d'au moins 15 km

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Les boucles du jeu de base font au moins 15 km (Circuit des Prés, Boucle de la Corniche, Route des Vignes 15 km, Récif des tortues et Volcan en flammes 16 km, Route du Grand Nord 20 km) ; boucles d'avant gardées pour les bancs (variante de recette) | Python, GDScript | DL1, O38, SM1, DB2, DB3, GP13b | Petite | En PR |

Demande du propriétaire du 27 novembre 2026 (3 h 45) : « Toutes les boucles à au moins 15 km et on peut laisser 5 km pour bancs de test ».

## 1. Règle

- Une boucle du jeu de base fait au moins `LOOP_MIN_M` (15 km) : `loop_repeat` fois sa longueur de `LOOPS` (la plus petite qui passe 15 km), `loop_length_m`.
- Boucle d'un seul biome (circuit, Corniche, Vignes, Récif) : la boucle est agrandie à l'identique (mêmes lobes, lacets `repeat` fois plus nombreux et de même amplitude : autant de virages par kilomètre, aucun plus serré), et le décor de la boucle d'avant revient à chaque tronçon (`_Section` : abscisses décalées, noms de lieux suivants de `PLACE_NAMES`). Même densité de décor, comme les blocs répétés du lot DL1.
- Volcan (`whole`) : une seule montée vers un seul cratère à mi-boucle ; son relief est construit sur la boucle agrandie (`road_relief`), la montée et le cône grandissent avec elle (`volcano_scale` : 370 m de montée sur 16 km).
- Grand Nord (boucle à plusieurs blocs) : chaque bloc de 2 km deux fois à la suite, comme une route ouverte du lot DL1 ; relief construit sur la boucle agrandie.
- Reliefs : la pente d'ensemble du circuit et de la Corniche s'étale comme la boucle (`trend`), sans quoi la Corniche passait sous la mer ; le fond du récif est étiré (`stretch`), le lagon reste au départ.
- Variante de recette (`--recette`) : boucles d'avant, octet pour octet (3, 2,5, 5, 8, 8 et 10 km) ; tous les bancs y restent, aucune référence à refaire. La fiche (`{km}`) donne la longueur du jeu ou de la recette ; une démonstration installée avec l'ancienne fiche est réécrite par les contenus de départ (`biome_demo_outdated`).
- Cyclistes du décor (core `road_cyclists.py` et engine `road_cyclists_model.gd`, même règle) : un groupe en gêne un autre par chacun de ses membres, pas seulement par sa tête. Sur le circuit de 15 km, un groupe de quatre entrait dans la queue d'un groupe de deux dont la tête s'était déjà écartée (`test_decor_cyclists_never_touch`). Relevé de parité inchangé.

## 2. Réalisation

| Parcours | Recette (bancs) | Jeu (DL2) | D+ du jeu | Pente du jeu |
| --- | --- | --- | --- | --- |
| Circuit des Prés | 3 km | 15 km (5 tronçons) | 195 m | −6,4 à +6,3 % |
| Boucle de la Corniche | 2,5 km | 15 km (6 tronçons) | 100 m | ± 3,2 % |
| Route des Vignes | 5 km | 15 km (3 tronçons) | 180 m | −6,0 à +6,2 % |
| Récif des tortues | 8 km | 16 km (2 tronçons, 2 épaves) | 30 m | ± 0,7 % |
| Volcan en flammes | 8 km | 16 km (un cratère) | 372 m | ± 8,3 % |
| Route du Grand Nord | 10 km | 20 km (10 blocs) | 145 m | ± 3,6 % |

- Grand Prix : 3 tours par défaut (réglage 1 à 5) font maintenant 45 km sur le Circuit des Prés.
- Boucle « Avenue de la Lagune » (#1089, pas encore sur main) : elle suivra la même règle d'elle-même dès qu'elle sera dans `LOOPS` et au jeu de base (décor par tronçon), à vérifier à la fusion de la seconde PR.

## 3. Recette PC
Catégorie : rendu
- Cloud : suites core et compilateur ; variante de recette comparée octet pour octet à celle d'avant (identique).
- PC : `captures_demo.py lancer --vitesse 80 --parcours demo-circuit,demo-corniche,demo-vignes,demo-recif,demo-volcan,demo-biomes-nord --qualites low,medium,high` (planche à valider par le propriétaire) ; mesure GPU low, high, medium sur une boucle agrandie (`sim_bench --world <routes>/demo-volcan.world --scenario nominal`, 10 min), cache séparé.
- Bancs existants : inchangés (variante de recette courte).
- Versions : aucune (WORLDGEN_VERSION, SCHEMA_VERSION et révision IPC inchangés).

## 4. Livraison

PR à venir sur `claude/project-thread-x0616t` (empilée sur #945).
