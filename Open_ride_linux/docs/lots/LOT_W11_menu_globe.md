# Lot W11 – Engine : menu globe, recherche de lieu, carte régionale, écran de préchargement

## 1. Objectif

Choisir le départ d'un monde ouvert « comme dans un simulateur de vol » (plan §2.1) : un globe qu'on fait tourner au clavier ou au Click, une recherche de lieu, une carte régionale pour poser le départ sur une route et choisir le cap, les régions en cache mises en évidence, puis un écran de préchargement.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §2, §3.1 (globe, recherche) et §4 (épinglage), `LOT_W1_contrat_monde_vivant.md` §4.3 (commandes et messages du menu).
2. Code : `engine/scripts/menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `ipc_client.gd`, `catalog_model.gd` ; core : `ipc_lists.py` (messages en parties).

## 3. Prérequis

W1 et W3 livrés (recherche et carte depuis la base) ; W2 pour les régions et l'épinglage.

## 4. Travail demandé

- **Données embarquées (dans le dépôt, sous 3 Mo au total) :** texture du globe Blue Marble de la NASA réduite à 2 048 × 1 024 en JPEG (au plus 1 Mo) ; côtes et frontières Natural Earth au 1:110 m converties en polylignes JSON (au plus 500 Ko) ; liste de lieux `places.json` (villes de plus de 50 000 habitants de GeoNames et cols célèbres du pack O16, au plus 1 Mo). Sources et licences dans `engine/assets/globe/LICENCES.md` ; script de préparation dans `scripts/` (non exécuté à l'installation).
- **Core :** réponses à `world_search` (liste embarquée, puis bases locales `search_places`, puis Nominatim si `network` vrai, au plus une requête par seconde, `User-Agent` du projet, à la demande seulement), `world_map` (routes de la base dans le rayon demandé, simplifiées à 20 m, au plus 60 000 octets par partie), `world_regions` et `world_pin` (W2).
- **Modèle sans affichage** `world_menu_model.gd` : états globe → carte → cap → préchargement ; rotation du globe (± au Click, flèches au clavier), sélection d'un résultat de recherche, point de départ accroché à la route la plus proche sur la carte, cap par pas de 15°, mode de navigation (balade, destination, boucle et longueur).
- **Affichage :** globe en `SphereMesh` texturée avec côtes ; régions en cache en surbrillance et épinglées marquées ; carte régionale 2D des routes reçues ; écran de préchargement alimenté par `world_status` (barre, octets, carrés prêts) avec attributions (OpenStreetMap, OpenMapTiles, Copernicus, NASA, Natural Earth, GeoNames).
- Entrée « Monde ouvert » ajoutée au menu principal ; hors ligne, la recherche n'utilise que la liste embarquée et les bases locales.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/world_menu_model.gd`, `engine/scripts/world_menu_view.gd`, `engine/assets/globe/*`, `scripts/prepare_globe_assets.py`, `engine/tests/unit/test_world_menu_model.gd`, `core/tests/test_world_menu_ipc.py`.
- **Modifiés :** `engine/scripts/menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `ipc_client.gd`, `core/src/openride_core/ipc_server.py`, `ipc_lists.py`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests Godot sans écran et `pytest` du core passent.
2. Modèle : suite de touches globe → recherche « Ventoux » → carte → cap 90° → `start_open_world` avec les bons arguments.
3. `world_map` sur une base de test : réponse en parties, chacune sous 60 000 octets, routes simplifiées à 20 m près.
4. Hors ligne : aucune requête Nominatim ; avec réseau, au plus une par seconde (horloge simulée).
5. Fichiers embarqués sous 3 Mo au total (test de taille).

**Sur le PC (le propriétaire) :** contrôle visuel du globe, de la carte et du préchargement.

## 8. Hors périmètre

HUD de séance (W12).
