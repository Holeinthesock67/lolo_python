# Lot DL1 – Démonstrations en ligne d'au moins 40 km

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Les parcours en ligne du jeu de base font au moins 40 km (Col du lacet 40 km, Tour des nouveaux paysages et Route des Érables 42,5 km, Route du Sud 48,5 km) ; variante de recette courte gardée pour les bancs | Python, JSON | NT1, DB1, DB3, DJ1, O37 | Petite | En PR |

Demande du propriétaire du 20 novembre 2026 (18 h 28) : « Reprends les circuits en ligne pour qu'ils fassent au minimum 40 km », puis « fais au plus simple ». Choix (carte, 18 h 32) : rallonger en ligne ; 18 h 33 : « rallonger le Col du lacet aussi » ; 18 h 34 : « faire une version finale de 40 km et garder la version de 5 km pour les bancs le temps de finir le jeu ».

## 1. Règle

- Une route ouverte du jeu de base fait au moins `LINE_MIN_M` (40 km). Les démonstrations des biomes répètent chaque bloc de 2 km à la suite (`demo_biomes.line_repeat`, `tour_blocks`) : un biome sur 6 ou 8 km au lieu de 2, même ordre climatique, même décor par bloc, fondus de 300 m inchangés. Le décor d'un bloc étant placé en mètres dans ses 2 km, allonger les blocs aurait clairsemé le décor : la répétition garde la densité.
- Le Col du lacet (`demo`, core) passe à 40 km (`DEMO_LENGTH_M`) : même route, lacet à 45 % de la longueur, même pente qui ondule (environ 950 m de montée, de 1 120 à 2 071 m).
- Variante de recette (`--recette`, la même que pour les noms techniques) : longueurs d'avant (Col du lacet 5 km, Tour 14 km, Érables 6 km, Sud 12 km), fiche qui le dit. Les bancs (`sim_bench`, `menu_bench`, `run_engine_tests.sh`, `visual_check`, `hud_galerie`, `gigue_charge`, `coupures`, `recette_u18`, `reglage_image`) restent dessus ; seuls les outils de la recette du jeu (`captures_demo.py`, scénario `parcours_demo` avec `demo_jeu`) prennent la version finale. Le bilan final (avant J9) dira si la variante courte reste.
- Les boucles (Grand Nord, Volcan, Récif, Circuit des Prés), le vélodrome et le pack Cols ne changent pas ; les parcours de recette seuls (tour des six paysages, côte, alpin, gravel) non plus.

## 2. Réalisation

| Parcours | Avant | Jeu (DL1) | D+ | Altitudes | Pente max |
| --- | --- | --- | --- | --- | --- |
| Col du lacet | 5,0 km | 40,0 km | 951 m | 1 120 → 2 071 m | 4,5 % |
| Tour des nouveaux paysages | 14,2 km | 42,5 km (21 blocs) | 840 m | 6 → 808 m | 6,5 % |
| Route des Érables | 6,1 km | 42,5 km (21 blocs) | 1 407 m | 6 → 1 413 m | 5,0 % |
| Route du Sud | 12,1 km | 48,5 km (24 blocs) | 398 m | 6 → 387 m | 5,0 % |

- Lieux : chaque clé a assez de noms pour ses blocs (3 par paysage, 4 par biome de la Route du Sud, 10 pour le Japon) ; un lieu de sommet (`SUMMIT_KEYS` : col, plateau, belvédère japonais) ne porte son premier nom qu'au dernier bloc du parcours (« Col des Cèdres », « Col des Lamas »).
- Copies embarquées : `engine/demo/demo.world` reste la variante de recette (5 km, tests de l'engine) ; `engine/demo/jeu/demo.world` (40 km, 5 Mo) est copiée par `ensure_demo_world` dans le dossier des parcours du joueur (la séance n'attend pas l'écriture de 14 s). Générateur 0.5.0 : un Col du lacet de 5 km d'un joueur est remplacé ; celui de recette d'un banc est gardé.
- Suite de tests du core : `OPENRIDE_DEMO_RECETTE=1` (posé par `core/tests/conftest.py`) fait poser le Col du lacet de recette par `ensure_demo_world` ; ses séances d'essai gardent ainsi le parcours de 5 km sur lequel elles ont été écrites.
- Fiches : la longueur de la description d'une route ouverte vient de ses blocs (`{km}`), jeu ou recette ; une démonstration de recette n'est pas « périmée » pour les contenus de départ.
- Coût : génération des sept démonstrations du jeu de base en 13 s dans le conteneur (contre environ 5 s), 6,8 à 7,6 Mo par route ouverte (contre 2 à 3 Mo).
- `captures_demo.py` : captures à l'entrée et au milieu du premier bloc de chaque biome seulement (les blocs répétés ont le même décor), sommet en fin de parcours : environ 5 h par qualité à 50 km/h, 3 h à 80 km/h.

## 3. Recette PC

Catégorie rendu (règle PR #938) : captures du jeu (`captures_demo.py lancer --vitesse 80 --parcours demo,demo-biomes-paysages,demo-japon,demo-biomes-sud`) en low, medium et high, et banc des menus `parcours_demo` (descriptions « 40 km », « 42.5 km », « 48.5 km ») ; captures à valider par le propriétaire.

## 4. Livraison

PR à venir sur `claude/project-thread-y6f4qt`.
