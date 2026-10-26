# OpenRide 2.0 – Monde ouvert généré en direct (série W)

25 octobre 2026. Proposition du propriétaire : choisir dans le menu un point de départ sur un globe, comme dans un simulateur de vol, puis rouler sur les vraies routes autour de ce point ; le monde se construit au fur et à mesure à partir de cartes téléchargées sur internet, et ce qui a déjà été téléchargé reste sur le PC pour ne pas être retéléchargé quand on repasse au même endroit. Ce plan étudie la faisabilité, fixe l'architecture et découpe le travail en lots. **La série W commence après la 1.0** (séries N et O) ; elle est indépendante des modes de jeu R, T et V. Les cahiers des lots seront rédigés au démarrage de la série et ajoutés à `docs/lots/00_INDEX.md`.

## 1. En résumé

C'est faisable avec le matériel actuel, à trois conditions :

1. **Ne pas interroger Overpass en continu.** Pour un usage régulier, la règle du serveur public revient à environ 100 requêtes et 10 Mo par jour, tous utilisateurs de l'application confondus ([wiki OSM, Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API)). Les routes, bâtiments, forêts et cours d'eau viennent donc d'un **extrait régional téléchargé une fois** (Geofabrik) ou de **tuiles vectorielles** (OpenFreeMap, sans quota déclaré), puis d'une base locale.
2. **Générer le monde dans un processus à part.** La physique du core tourne à 50 Hz ; un calcul numpy de quelques centaines de millisecondes la ferait bégayer. Un générateur séparé réutilise le code du compilateur et prépare les morceaux en avance.
3. **Garder la pente connue d'avance.** Le core engage toujours au moins 3 km de route devant le cycliste. Aux carrefours, le choix se fait avant un point de verrouillage, et les premiers 500 m de chaque branche sont déjà calculés.

Le rendu ne coûte pas plus cher qu'un parcours compilé : l'engine charge déjà le monde par tronçons de 1 km et par tuiles (`engine/scripts/world_streamer.gd`, `engine/scripts/osm_streamer.gd`), avec les mêmes préréglages de qualité. La marge de temps de génération est d'environ 50 fois le besoin (§3.3).

## 2. Ce que voit le cycliste

1. **Menu « Monde ouvert » :** un globe qu'on fait tourner au clavier ou au Click, une recherche par nom (liste de lieux embarquée et, si l'on est en ligne, recherche Nominatim), puis une carte régionale pour poser le départ sur une route et choisir le cap. Les régions déjà en cache sont mises en évidence.
2. **Préchargement :** une barre indique ce qui se télécharge (relief, extrait régional) et sa taille. Si la zone est déjà sur le PC, le départ est immédiat, même hors ligne.
3. **Sur la route :** à l'approche d'un carrefour, le HUD montre les branches possibles (flèche, type de route, pente des 500 premiers mètres) et celle que le jeu prendra. Le cycliste peut changer de branche jusqu'au point de verrouillage ; sans appui, le navigateur choisit.
4. **Modes de navigation :** balade (le jeu garde le cap et préfère les petites routes), vers une destination (un col, une ville), ou boucle de X km qui revient au départ.
5. **Fin :** la balade peut être enregistrée comme parcours ordinaire de la bibliothèque, pour la refaire plus tard en mode classique, avec bots et segments.

## 3. Faisabilité

### 3.1 Sources de données

| Besoin | Source recommandée | Conditions d'usage | Volume | Rôle |
| --- | --- | --- | --- | --- |
| Relief | Copernicus GLO-30 (déjà utilisé par le compilateur), tuiles de 1° × 1° sur AWS | Données libres, attribution Copernicus obligatoire | 42 à 44 Mo par tuile (mesuré sur deux tuiles de France) ; une tuile couvre environ 78 × 111 km à 45° de latitude | Principal |
| Routes, bâtiments, forêts, eau | Extrait régional Geofabrik (`.osm.pbf`), converti en base locale | ODbL : attribution « © contributeurs OpenStreetMap » ; mises à jour quotidiennes, téléchargement raisonnable demandé | Ordre de grandeur : 100 à 500 Mo pour une région française, 4 à 5 Go pour la France entière (à mesurer en W0) | Facultatif : une région entière, hors ligne ensuite |
| Les mêmes, n'importe où | Tuiles vectorielles OpenFreeMap (schéma OpenMapTiles, zoom 14) | Gratuit, sans clé ni quota déclaré ; financé par des dons ; attribution OSM et OpenMapTiles | Quelques dizaines à quelques centaines de Ko par tuile (à mesurer en W0) | Téléchargées au fur et à mesure, partout dans le monde, et préchargées autour des lieux de départ habituels (W-Q4) |
| Compléments ponctuels | Overpass (code existant de `compiler/src/openride_compiler/osm.py`) | Usage régulier : environ 100 requêtes et 10 Mo par jour au total, pause de 30 s après une erreur 429 | Petites requêtes | Exceptionnel, jamais pendant la séance |
| Recherche de lieux | Liste embarquée (cols et villes, GeoNames, CC BY) ; Nominatim en ligne | Nominatim : une requête par seconde au plus, à la demande du cycliste seulement | — | Menu |
| Globe | Texture Blue Marble de la NASA en basse définition, côtes et frontières Natural Earth | Domaine public | Quelques Mo dans le dépôt | Menu |

Deux remarques sur le relief :
- **Copernicus est un modèle de surface :** il inclut en partie la canopée et les bâtiments. Sur une trace GPX, le lissage du compilateur l'absorbe ; en monde ouvert, il faut en plus corriger les **ponts et tunnels** (balises OSM `bridge` et `tunnel` : altitude interpolée entre les deux extrémités), sinon la route plonge dans la vallée sous un viaduc.
- En France, le RGE ALTI de l'IGN (licence ouverte, déjà prévu comme emplacement réservé dans `elevation.py`) donnerait un sol nu plus précis ; à garder comme option.

Le routage se fait sur notre propre graphe, construit depuis la base locale : aucun service de calcul d'itinéraire en ligne.

### 3.2 Bande passante

| Situation | Volume par heure de route (environ 30 km) |
| --- | --- |
| Région déjà en cache | 0 |
| Région nouvelle, extrait régional | Téléchargement unique de l'extrait et d'une à quatre tuiles de relief avant le départ, soit quelques centaines de Mo une fois ; ensuite 0 |
| Partout, sans extrait (tuiles vectorielles) | Une à deux tuiles de relief (40 à 90 Mo) et de l'ordre de 50 à 80 tuiles vectorielles (quelques Mo à une quinzaine de Mo), à confirmer en W0 |

Une connexion domestique ordinaire suffit. Le relief se télécharge avant le départ pour la tuile courante, puis dès qu'on arrive à moins de 10 km du bord d'une tuile.

### 3.3 Vitesse de génération

À 30 km/h, on parcourt 1 km en 2 minutes ; en descente à 70 km/h, en 51 secondes. Pour chaque kilomètre parcouru, il faut produire :
- environ 3 nouvelles tuiles proches de 1 km (fenêtre de 1 500 m autour de la caméra, comme aujourd'hui) et environ une tuile lointaine de 5 km ;
- le profil de 1 km de route engagée, plus les amorces de 500 m des branches aux carrefours ;
- les couches bâtiments, végétation, eau et points d'intérêt des nouvelles tuiles.

Estimation à confirmer par la mesure W0 : une grille de 101 × 101 points interpolée dans le MNT, fondue avec les routes et suivie des couches lues dans une base locale indexée prend moins de 300 ms par tuile en numpy. Le besoin est donc de l'ordre de 1 seconde de calcul par kilomètre, pour au moins 50 secondes disponibles. Avec 3 km d'avance, une coupure réseau de plusieurs minutes passe inaperçue si la zone voisine est déjà en cache.

### 3.4 Carte graphique (GTX 1060, au moins 55 images/s)

Rien ne change côté rendu : mêmes tuiles, mêmes tronçons de 1 km, mêmes préréglages (`engine/scripts/quality_presets.gd`). Deux ajouts restent bornés :
- les amorces de branches aux carrefours, de 500 m chacune, n'ajoutent que quelques ArrayMesh de ruban ;
- les bâtiments et la végétation sont gardés dans une bande de 400 m autour de la route engagée et des amorces, comme pour un parcours compilé, même si la base locale en contient davantage.

Seul point nouveau : au-delà de quelques dizaines de kilomètres de l'origine, la précision des flottants 32 bits de Godot descend vers quelques millimètres. L'engine recentre son origine tous les 10 km (décalage interne, invisible dans les fichiers).

### 3.5 Processeur et core

Le générateur tourne dans son propre processus (`openride-worldgen`), lancé par le core comme Godot l'est par le lanceur. Il échange avec le core par une file locale (demandes de tuiles et d'arêtes, réponses « prêt ») et écrit ses fichiers de façon atomique, comme le compilateur. La boucle à 50 Hz du core ne fait que lire des profils déjà calculés. Critère mesuré en recette : gigue de la boucle physique inférieure à 5 ms pendant la génération.

### 3.6 Hors ligne

- Zone en cache : tout fonctionne sans réseau, y compris le menu (la carte régionale est dessinée depuis la base locale).
- Zone hors cache sans réseau : le navigateur n'engage que des routes dont le relief est disponible ; à la limite, il propose un demi-tour ou une autre branche. La séance ne s'arrête jamais pour attendre un téléchargement.
- Plus de relief du tout devant (cas extrême) : pause automatique avec un message, comme une perte du trainer.

## 4. Cache local sur le PC (demande du propriétaire)

Tout ce qui est téléchargé ou généré reste sur le PC, jamais dans le dépôt. Quand on repasse au même endroit, rien n'est retéléchargé ni recalculé.

**Emplacement :** `~/OpenRide/Cache/monde/`, modifiable par `[open_world] cache_dir` dans `config.toml`. Les tuiles de relief déjà téléchargées par le compilateur dans `~/.cache/openride/dem/` sont relues avant tout téléchargement : un relief n'est jamais téléchargé deux fois.

**Contenu, en deux étages :**

| Étage | Dossier | Contenu | Format compact |
| --- | --- | --- | --- |
| Données brutes | `brut/dem/` | Tuiles Copernicus telles que téléchargées | GeoTIFF compressé d'origine |
| | `brut/osm/<region>.sqlite` | Extrait régional converti : seules les balises utiles (routes, bâtiments et hauteurs, forêts, eau, points d'intérêt), index spatial | SQLite avec index R-tree ; le `.osm.pbf` d'origine est supprimé après conversion, sauf option contraire |
| | `brut/tuiles/14/<x>/<y>.mvt` | Tuiles vectorielles de secours | Fichier MVT d'origine |
| Monde généré | `genere/<zone UTM>/<ix>_<iz>/` | Pour chaque carré de 1 km : grille proche, couches bâtiments, végétation, eau, points d'intérêt, arêtes du graphe routier avec leur profil | Les fichiers du format `.world` (grilles `float32`, JSON compressé) |

**Réutilisation d'une séance à l'autre :** les carrés générés sont rangés dans une grille fixe de 1 km de la zone UTM, et non par rapport au départ de la séance. L'origine d'une séance est le coin de grille le plus proche du départ, si bien que les carrés s'alignent toujours et se réutilisent tels quels. Le terrain est fondu avec toutes les routes du carré, et non avec la seule route suivie : il ne dépend donc pas du chemin pris.

**Validité :** chaque carré porte les versions du générateur et des sources. Un carré dont la version est dépassée est régénéré depuis les données brutes, sans téléchargement. L'extrait régional peut être rafraîchi à la demande (menu ou `openride-compiler region-update`), jamais automatiquement pendant une séance.

**Taille et éviction :**
- plafond `[open_world] cache_max_gb`, 5 Go par défaut ; pour fixer les idées, une région de 300 Mo et ses carrés générés tiennent dans moins de 1 Go ;
- au-delà du plafond, on supprime d'abord les carrés générés les moins récemment utilisés (ils se recalculent sans réseau), puis les données brutes les moins récemment utilisées ;
- les tuiles préchargées autour des lieux de départ habituels (W-Q4) passent en dernier ;
- une région peut être **épinglée** dans le menu : elle n'est jamais supprimée ;
- `openride-compiler cache-info` donne la taille par région, `cache-clean` vide le cache.

**Vie privée :** le cache dit où l'on a roulé. Il reste dans le dossier personnel, n'est jamais envoyé ni versionné, et aucune coordonnée réelle du propriétaire n'apparaît dans les exemples ou les tests du dépôt (lieux d'exemple : cols célèbres).

## 5. Architecture

### 5.1 Trois acteurs

| Acteur | Rôle |
| --- | --- |
| `openride-worldgen` (nouveau processus Python, code du compilateur) | Télécharge, convertit, génère les carrés et les profils d'arêtes, gère le cache |
| Core | Choisit le départ, tient la route engagée (au moins 3 km), le graphe local et le navigateur ; envoie la pente au trainer ; publie le prochain carrefour |
| Engine | Affiche le globe et la carte du menu, lit les carrés et la route qui s'allonge, dessine les amorces de branches et le HUD du carrefour |

### 5.2 Format du monde vivant (ajout compatible au format `.world`)

Une séance de monde ouvert écrit un dossier `.world` « vivant » dans `~/OpenRide/Cache/monde/seances/<id>.world/`, que l'engine lit comme un parcours ordinaire, avec trois ajouts :
- `manifest.json` : `live: true`, origine sur la grille UTM (`origin_kind: "utm_grid"`), révision du monde ;
- route par parties ajoutées au fur et à mesure (`route/part_<k>.json`, même colonnes que `route.json`, `s` toujours croissant) ;
- couches rangées par carré de terrain (`<couche>/tile_<ix>_<iz>.json`) au lieu du tronçon de route `k`, et fichier `junctions.json` des carrefours à venir.

Les carrés du cache sont liés dans ce dossier, pas copiés.

### 5.3 Contrat IPC (ajout compatible, révision suivant celles des séries P, R, T et V)

- Commande `start_open_world` : latitude, longitude, cap, mode de navigation (balade, destination, boucle), cible ou longueur de boucle, graine.
- Commande `choose_branch` : identifiant du carrefour et numéro de branche.
- Champ facultatif `open_world` de `state` : révision du monde (l'engine relit les nouvelles parties quand elle change), distance au prochain carrefour, branches (angle, type de route, pente moyenne des 500 premiers mètres), branche choisie, verrouillé ou non, état des données (en cache, téléchargement, hors ligne). Doit tenir dans les 1 400 octets de la trame.
- Message `world_status` : progression du préchargement pour l'écran d'attente.

### 5.4 Carrefours et pente connue d'avance

- **Horizon :** la route engagée fait au moins 3 km devant le cycliste (plus de 2 minutes à 70 km/h).
- **Choix :** les branches sont proposées dès 300 m du carrefour ; le choix reste possible jusqu'à 30 m avant, puis il est verrouillé.
- **Profils prêts :** le profil des 500 premiers mètres de chaque branche est calculé à l'avance ; changer de branche remplace la fin de la route engagée sans attente. La pente envoyée au trainer suit la limite de variation existante (`grade_rate_pct_per_s`).
- **Impasses :** le navigateur les évite ; si le cycliste en prend une, demi-tour automatique à son extrémité.
- **Routes admises :** routes, chemins revêtus et pistes cyclables ; ni autoroutes ni voies rapides ; chemins de terre et pistes forestières réservés à l'option « gravel » de la 3.0 (W-Q2).

## 6. Ce qui se réutilise

| Besoin | Existant | Où |
| --- | --- | --- |
| Relief et son cache | Copernicus GLO-30, téléchargement atomique, reprises | `compiler/src/openride_compiler/elevation.py`, `compiler/src/openride_compiler/cache.py` |
| Repère local | UTM translaté, aller-retour latitude et longitude | `compiler/src/openride_compiler/frame.py` |
| Profil de route | Rééchantillonnage à 10 m, lissage, pente bornée, cap | `compiler/src/openride_compiler/pipeline.py` |
| Terrain | Tuiles proches et lointaines, fondu avec la route | `compiler/src/openride_compiler/terrain.py` |
| Couches OSM | Bâtiments, végétation, eau, points d'intérêt | `compiler/src/openride_compiler/osm_layers.py` |
| Chargement par morceaux | Ruban par tronçon, tuiles, couches OSM en tâches de fond | `engine/scripts/world_streamer.gd`, `engine/scripts/osm_streamer.gd` |
| Arbres hors forêts OSM | Probabilité par région (décision E4) | `engine/scripts/vegetation_placer.gd` |
| Lecture de la route | Interpolation, pente, échantillons | `core/src/openride_core/route.py`, `engine/scripts/route_data.gd` |
| Menus et lanceur | Modèle de menu, lanceur unique | `engine/scripts/menu_model.gd`, `core/src/openride_core/launcher.py` |
| Bibliothèque de parcours | Catalogue, compilation à la demande | `core/src/openride_core/catalog.py` |

Les séries de la 2.0 s'y branchent sans travail particulier : vent, décor vivant et saisons (P) s'appliquent tels quels ; les montées détectées automatiquement (T) le sont sur la route engagée, donc seulement dans l'horizon de 3 km ; les bots (T) suivent la route engagée. Les biomes de la 3.0 (U) trouvent ici leur meilleur terrain, puisque le paysage change vraiment de région.

## 7. Risques

| # | Risque | Parade |
| --- | --- | --- |
| 1 | Serveurs publics saturés ou quotas (Overpass surtout) | Extrait régional et tuiles vectorielles, Overpass hors séance seulement ; en-tête `User-Agent` existant |
| 2 | OpenFreeMap disparaît ou change ses conditions | Source de secours seulement ; l'extrait régional suffit ; logiciel libre, auto-hébergeable |
| 3 | Pentes fausses sous les ponts, dans les tunnels, en forêt (modèle de surface) | Interpolation des ponts et tunnels, lissage, borne de pente ; RGE ALTI en option en France |
| 4 | Génération trop lente sur le PC | Mesure W0 avant tout ; processus séparé ; horizon de 3 km ; profils des branches à l'avance |
| 5 | Bégaiement de la physique à 50 Hz | Aucun calcul lourd dans le core ; gigue mesurée en recette |
| 6 | Disque qui se remplit | Plafond, éviction, épinglage, `cache-info` et `cache-clean` |
| 7 | Choix de branche au Click peu fiable (boîtier gauche bridé) | Navigateur par défaut, choix facultatif, clavier de secours (question W-Q1) |
| 8 | Flottants 32 bits loin de l'origine | Recentrage de l'engine tous les 10 km |
| 9 | Passage d'une zone UTM à l'autre | Garder la zone du départ pour toute la séance ; déformation faible sur 100 km |
| 10 | Attributions oubliées | Écran de chargement et crédits : OpenStreetMap, OpenMapTiles, Copernicus, NASA, Natural Earth, GeoNames |
| 11 | Vie privée (le cache trace les sorties) | Cache local hors dépôt, aucune coordonnée réelle dans les exemples |

## 8. Décisions du propriétaire

| # | Question | Décision (25 octobre 2026) |
| --- | --- | --- |
| W-Q1 | Bouton de choix au carrefour | Flèches gauche et droite du boîtier gauche quand il répond, sinon A court qui fait défiler les branches ; flèches du clavier en secours ; sans appui, le navigateur choisit |
| W-Q2 | Chemins de terre | Pas en 2.0 ; une option « gravel » dans les menus est prévue pour la 3.0 |
| W-Q3 | Plafond du cache | 5 Go par défaut, modifiable |
| W-Q4 | Sources de cartes | Les tuiles mondiales s'ajoutent au fur et à mesure : téléchargées pendant la balade, et préchargées à l'avance autour des lieux de départ de l'historique du joueur (les plus fréquents et les plus récents d'abord), toujours dans la limite du cache de 5 Go. L'extrait régional reste possible pour une région qu'on veut avoir en entier hors ligne |
| W-Q5 | Monde ouvert en ERG | Autorisé : en ERG, la pente ne joue pas sur la résistance |

## 9. Lots de la série W

| Lot | Contenu | Dépend de | Type |
| --- | --- | --- | --- |
| W0 | Mesures : script qui télécharge un extrait régional et une tuile de relief, génère 10 km de monde et mesure tailles, temps par carré et par kilomètre, et débit (exécuté sur le PC) | — | Délégable, puis propriétaire (PC) |
| W1 | Contrat : format du monde vivant (`live`, origine sur grille UTM, route par parties, couches par carré, `junctions.json`) et contrat IPC (`start_open_world`, `choose_branch`, champ `open_world`, `world_status`) | W0 | Interne (décision) |
| W2 | Cache local : arborescence, versions, plafond, éviction, épinglage, `cache-info`, `cache-clean`, réutilisation du relief du compilateur | W1 | Délégable |
| W3 | Extrait régional : téléchargement Geofabrik, conversion en SQLite indexée (balises utiles), mise à jour à la demande | W2 | Délégable |
| W4 | Graphe routier : arêtes, carrefours, type de route, revêtement, ponts et tunnels, filtre des routes admises | W3 | Délégable |
| W5 | Profil d'arête : rééchantillonnage, altitude, ponts et tunnels interpolés, lissage et borne (code de `pipeline.py`) | W4 | Délégable |
| W6 | Navigateur : balade (cap, petites routes, pas d'impasse), destination, boucle de X km, sur le graphe local | W4 | Délégable |
| W7 | Générateur de carrés : terrain fondu avec toutes les routes du carré, couches OSM par carré, file de priorités, écriture atomique | W2, W3, W5 | Délégable |
| W8 | Processus `openride-worldgen` : file de demandes, horizon de 3 km, amorces de branches, téléchargement anticipé du relief, comportement hors ligne | W6, W7 | Délégable |
| W9 | Core : route qui s'allonge, branche choisie et verrouillage, intégration à la séance, journal, pause si plus de relief | W1, W8 | Interne |
| W10 | Engine : lecture du monde vivant (parties de route, couches par carré), amorces de branches, recentrage tous les 10 km | W1 | Interne (rendu) |
| W11 | Engine : menu globe, recherche de lieu, carte régionale depuis la base locale, régions en cache et épinglées, écran de préchargement | W1, W3 | Interne |
| W12 | Engine : HUD du carrefour (branches, pente, choix, verrouillage) et attributions | W1 | Interne (rendu) |
| W13 | Tuiles vectorielles OpenFreeMap (même base locale, mêmes couches) : téléchargement au fil de la balade et préchargement autour des lieux de départ de l'historique, par ordre de fréquence et de récence, dans la limite du cache (W-Q4) | W2, W7 | Délégable |
| W14 | Enregistrer la balade comme parcours de la bibliothèque (GPX puis `.world`) | W9 | Délégable |
| W15 | Monde synthétique pour les essais sans réseau : relief analytique, faux graphe, séance simulée de bout en bout | W1 | Délégable |
| W16 | Recette sur le PC et le vélo : une heure de monde ouvert, au moins 55 images/s, aucune pause d'attente, gigue de la physique sous 5 ms, retour au même endroit sans téléchargement | W9 à W12 | Propriétaire |

Ordre conseillé : W0 d'abord, pour confirmer les volumes et les temps ; puis W1 ; ensuite W2 à W8, W13 et W15 en parallèle pendant que W10 à W12 avancent ; enfin W9, W14 et la recette W16. Une première balade jouable (extrait régional, navigateur en mode balade, sans menu globe) est possible après W0 à W10. Dix lots sont délégables à une autre IA : W2 à W8 et W13 à W15 (W0 aussi, pour l'écriture du script).
