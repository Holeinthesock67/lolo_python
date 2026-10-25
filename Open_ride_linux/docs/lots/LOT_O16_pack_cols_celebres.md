# Lot O16 – Pack de départ : cols célèbres (Alpes, Pyrénées, Vosges, Teide, Japon…)

## 1. Objectif

Le propriétaire veut trouver dans la bibliothèque (O15), dès l'installation, quelques cols célèbres : l'Alpe d'Huez, la montée du Teide, le Mont Ventoux, etc. Ce lot fournit ce **pack de départ**.

**Confidentialité et licences (règle du dépôt) :** le pack ne contient que des montées célèbres et publiques (aucun lieu lié au domicile du propriétaire, aucune boucle personnelle) et aucune trace réelle enregistrée par quelqu'un. Les traces personnelles du propriétaire restent seulement sur son PC (`~/OpenRide/GPX/`). La géométrie vient d'OpenStreetMap (licence ODbL, attribution obligatoire) et l'altitude du MNT Copernicus déjà utilisé par le compilateur : on ne recopie aucun GPX tiers.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_O15_bibliotheque_parcours.md` (fiches `.toml`, `pack.toml`, `route-pack-install`), `docs/lots/LOT_I3_osm_batiments_forets.md` (accès Overpass et cache), `docs/lots/LOT_B2_compilateur_terrain.md`.
2. Code : `compiler/src/openride_compiler/osm.py` (`OverpassClient`, cache `~/.cache/openride/osm/`), `compiler/src/openride_compiler/route_pack.py` (O15), `compiler/src/openride_compiler/cli.py`.

## 3. Prérequis

O15 fusionné.

## 4. Travail demandé

- **Régions :** les recettes portent un pays ; pour le Japon, les noms sont donnés en lettres latines (et en japonais dans `description` si souhaité, l'affichage devant alors gérer les caractères japonais, à vérifier par O12).
- **Recettes plutôt que traces :** le dépôt contient, pour chaque col, une petite **recette** `compiler/route_packs/cols_celebres/<id>.toml` : nom, description, région (pays et massif), points de passage publics et célèbres (départ, éventuels points intermédiaires, sommet) donnés par des coordonnées arrondies à 4 décimales, versant choisi, longueur et dénivelé de référence (pour le contrôle), étiquettes (`col`, `classique`, `hc`…), crédits « © contributeurs OpenStreetMap, ODbL ».
- **Construction de la trace** (`openride-compiler route-pack-build cols_celebres`) : récupère par Overpass les routes ouvertes aux vélos autour des points (`highway` hors `motorway`, `trunk` avec `bicycle=no`, chemins non revêtus exclus sauf mention), calcule le plus court chemin entre points successifs sur ce graphe, ré-échantillonne et écrit un GPX dans un dossier de travail, puis un pack installable (O15) avec les fiches. Réseau seulement à la première construction ; ensuite le cache suffit.
- **Contrôle :** la longueur et le dénivelé obtenus doivent être à ± 5 % de la référence de la recette ; sinon la trace est refusée avec un message (point de passage à corriger).
- **Contenu proposé** (le propriétaire peut retirer ou ajouter des cols avant la livraison) : Alpe d'Huez (depuis Le Bourg-d'Oisans), Mont Ventoux (depuis Bédoin), Col du Galibier (depuis Valloire), Col du Tourmalet (depuis Luz-Saint-Sauveur), Teide (depuis Vilaflor, Tenerife), Passo dello Stelvio (depuis Prato allo Stelvio), Monte Zoncolan (depuis Ovaro), Alto de l'Angliru (depuis La Vega), Grand Colombier (depuis Culoz), Col de la Madeleine (depuis La Chambre) ; dans les Vosges (demande du propriétaire) : Grand Ballon (depuis Willer-sur-Thur), La Planche des Belles Filles (depuis Plancher-les-Mines), Ballon d'Alsace (depuis Saint-Maurice-sur-Moselle) ; au Japon (demande du propriétaire) : Fuji Subaru Line jusqu'à la 5e station du mont Fuji (depuis Fujiyoshida), Norikura Echo Line, la route goudronnée la plus haute du Japon (depuis Norikura Kōgen), Irohazaka et ses 48 virages (route montante, depuis Nikkō). Aucun lieu proche du domicile du propriétaire, et aucun col n'est choisi d'après ses sorties.
- **Installation :** au premier démarrage (N14) ou par le menu, proposition d'installer le pack (construction en arrière-plan, notification à la fin) ; jamais d'installation silencieuse qui télécharge.
- Documentation : `README.md` (pack de départ, crédits OSM), `docs/GUIDE_UTILISATION.md` si présent.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/route_packs/cols_celebres/pack.toml` et une recette `.toml` par col, `compiler/src/openride_compiler/route_recipe.py`, `compiler/tests/test_route_recipe.py` (graphe routier synthétique, sans réseau).
- **Modifiés :** `compiler/src/openride_compiler/cli.py`, `compiler/pyproject.toml` (inclure les recettes dans le paquet), `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** tout GPX, FIT ou TCX dans le dépôt ; toute coordonnée liée au domicile ou aux sorties du propriétaire ; l'engine, le contrat IPC.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe dans `compiler/` sans réseau (graphe et réponses Overpass simulés).
2. Graphe synthétique avec deux chemins possibles : le plus court qui respecte les exclusions est choisi ; un point de passage hors de toute route est refusé avec un message clair.
3. Contrôle à ± 5 % : une recette dont la référence est fausse est refusée.
4. Le pack produit s'installe avec `route-pack-install` (O15) et ses fiches portent les crédits OSM.
5. Aucun fichier de trace ni coordonnée hors des recettes listées (recherche dans la PR).

**Sur le PC cible (le propriétaire) :** construire le pack (réseau), vérifier dans la bibliothèque longueur, dénivelé et pente de l'Alpe d'Huez, du Grand Ballon et de la Norikura Echo Line face aux valeurs connues, rouler l'un d'eux.

## 8. Hors périmètre

- Parcours de plaine ou classiques sur pavés (pack ultérieur possible avec le même outil).
- Itinéraires calculés librement entre deux villes (pas de calculateur d'itinéraire général).
