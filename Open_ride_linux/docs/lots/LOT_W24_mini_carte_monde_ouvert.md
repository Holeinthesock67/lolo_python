# Lot W24 – Engine : mini-carte du monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : mini-carte du monde ouvert (cap en haut, route devant et roulée, carrefour, but écrit) | GDScript | W10, W12 | Petite | En revue |

## 1. Objectif

Se diriger en monde ouvert : après l'essai du week-end du 22 novembre, le propriétaire a demandé les lots manquants du
monde ouvert (24 novembre) ; aucun lot ne donnait de carte pendant la balade. La mini-carte montre où l'on est, où va
la route, les carrefours proches et, en Destination ou en Boucle, où est le but.

## 2. À lire

1. `LOT_W10_engine_monde_vivant.md` (route par parties, carrefours, amorces), `LOT_W12_hud_carrefour.md` (panneau du carrefour).
2. Code : `engine/scripts/live_world.gd`, `route_data.gd`, `junction_view.gd`, `hud_view.gd`, `main.gd`.

## 3. Travail fait

- **Modèle sans affichage** `minimap_model.gd` : carte de 1 200 m de large qui suit le cycliste, cap en haut, cycliste un
  peu sous le centre (environ 650 m visibles devant). Route engagée devant (lue directement dans les colonnes de la route,
  un point sur trois en low), route déjà roulée, amorces des branches non suivies (`live_world.previews`), anneau au
  prochain carrefour (`state.open_world.next`, jusqu'à 1 500 m), direction du nord, barre d'échelle ronde (« 200 m »).
- **But** : en Destination la cible, en Boucle le point de départ, d'après le dernier `start_open_world` envoyé par
  l'engine, sinon `hello_ack.config.last_choices.open_world` (séance reprise après une relance). La position se calcule
  avec les colonnes `lat` et `lon` de la route : premier point comme ancre, point le plus loin pour corriger l'écart
  entre le nord géographique et le nord de la grille UTM (2 à 3° au bord d'une zone). Hors de la carte, le losange est
  épinglé au bord, sur la ligne cycliste → but. Distance à vol d'oiseau écrite sous la carte.
- **Mots écrits, jamais la couleur seule** : route devant en trait plein épais, route roulée en pointillés, branches en
  traits fins, cycliste en flèche, but en losange avec son nom (« Arrivée », « Départ »), « N » au bord, « CARTE » et
  l'échelle en haut, lignes « Carrefour dans 240 m » et « Arrivée : 3,2 km à vol d'oiseau » dessous.
- **Affichage** `minimap_view.gd` : panneau de la largeur de la colonne gauche du HUD, en bas à gauche, au-dessus du
  bandeau ERG quand il est là, jamais sur la colonne gauche (vent, abri) : la carte rétrécit jusqu'à 96 px de haut, puis
  se cache. Visible en séance de monde ouvert seulement (prête, en route ou en pause), cachée sous les menus.
- **Performance** : quelques centaines de segments 2D ; redessinée au plus 4 fois par seconde en low, 10 en medium,
  15 en high ; le but n'est recalculé qu'à chaque nouvelle route (révision du monde vivant).
- Pas de contrat modifié (ni IPC, ni format), pas de `class_name`.

## 4. Fichiers

- **Nouveaux :** `engine/scripts/minimap_model.gd`, `engine/scripts/minimap_view.gd`,
  `engine/tests/unit/test_minimap_model.gd`, `engine/tests/menu_scenarios/ow_minicarte.json`.
- **Modifiés :** `engine/scripts/main.gd` (branchement, widget « minimap » des captures, ligne de test
  `minimap shown`), `engine/tests/hud_galerie.py` (cas `monde_ouvert_carte` et `monde_ouvert_destination`),
  `engine/tests/hud_lisibilite.py` (panneau compté dans les chevauchements), `engine/tests/fake_core.py`
  (`last_choices` du `hello_ack`), `docs/GUIDE_UTILISATION.md` (§4 bis).

## 5. Critères d'acceptation

1. Test sans écran `test_minimap_model.gd` : cap en haut (nord, est, marche arrière), nord au bon bord, échelle,
   carrefour écrit jusqu'à 1 500 m, but dans la carte puis épinglé au bord, position géographique juste à 5 m près
   avec 2,5° d'écart de grille, place insuffisante → carte cachée.
2. Galerie du HUD (`hud_galerie.py --cas monde_ouvert_carte,monde_ouvert_destination`) : carte affichée, textes
   attendus, panneaux sans chevauchement, en 1 024 × 600, 1 280 × 720 et 1 920 × 1 080.
3. **Sur le PC** : `menu_bench.py --scenario ow_minicarte` en low, medium et high (cache du monde ouvert séparé) ;
   captures validées par le propriétaire.

## 6. Hors périmètre

Carte plein écran, zoom réglable, noms des routes et des lieux sur la carte, flèche de l'itinéraire jusqu'au but
(le navigateur du générateur choisit déjà les branches vers le but).

## Livraison

PR #1055 (branche `claude/project-thread-i86ilm`), en revue.
