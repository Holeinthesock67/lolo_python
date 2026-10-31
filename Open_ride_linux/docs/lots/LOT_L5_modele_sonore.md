# Lot L5 – Modèle sonore sans affichage : vent, roue libre, points d'intérêt

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Modèle sonore sans affichage : vent, roue libre, points d'intérêt | GDScript | K1 (livré) | Petite | **Livré le 24 octobre** (PR #68, issue #57) |

## 1. Objectif

Préparer l'audio du sprint 6 (SRS §8, « Audio ») : calculer, à partir des trames `state` et de la couche `poi`, **quels sons jouer et à quel volume**, dans un script GDScript pur testé sans écran. Le lot audio n'aura plus qu'à brancher des `AudioStreamPlayer` sur ces valeurs.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_I6_logique_erg_godot.md` (même démarche : modèle sans nœud testé face à des trames).
2. `docs/SRS_v1.1.md` §8 (« Audio : vent proportionnel à la vitesse, bruit de roue libre à 0 W, sources 3D sur les points d'intérêt ») ; `docs/contracts/ipc_v1.md` §3 (trame `state` : `v`, `power`, `paused`…) ; `docs/contracts/world_format_v1.md` §8 (`poi` : `kind`, `x`, `y`, `z`, `radius_m`).
3. Code : `engine/scripts/erg_view_model.gd`, `engine/scripts/route_data.gd` (`sample_point` pour la position du cycliste) ; `engine/tests/fake_core.py`.

## 3. Prérequis

Lot K1 livré. K4 n'est pas nécessaire : les points d'intérêt sont reçus en tableau de dictionnaires.

## 4. Travail demandé

Nouveau `engine/scripts/sound_model.gd` (`extends RefCounted`, sans `class_name`), sans nœud :

- `on_state(state: Dictionary, rider_pos: Vector3, now_s: float)` puis `evaluate(now_s: float) -> Dictionary` :
  - `wind` : `{volume_db, pitch}` ; silence (−80 dB) à l'arrêt, volume croissant avec la vitesse jusqu'à 60 km/h puis plafonné, `pitch` de 0,8 à 1,3 ;
  - `freewheel` : `{playing, volume_db}` ; joue quand la vitesse dépasse 5 km/h et que la puissance est nulle ou absente depuis au moins 0,5 s, s'arrête dès qu'elle repasse au-dessus de 10 W ;
  - en pause (`paused`), tout est silencieux ;
  - `pois` : liste des points d'intérêt audibles `{id, kind, volume_db, position}`, au plus 4, les plus proches d'abord.
- `set_pois(points: Array)` : liste du tronçon courant ; `kind` inconnu ignoré (format §8).
- **Hystérésis :** un point entre à `radius_m` et sort à `1,1 × radius_m`, pour éviter qu'un son clignote à la limite ; un événement `entered` / `left` par passage (champ `events` de `evaluate`, vidé à chaque appel).
- **Lissage :** les volumes varient d'au plus 12 dB par seconde (pas de coupure brutale entre deux trames).
- Les constantes (60 km/h, 5 km/h, 0,5 s, 10 W, 12 dB/s, 4 sources) sont en tête du script et listées dans le rapport.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/sound_model.gd`, `engine/tests/unit/test_sound_model.gd`.
- **Modifiés :** `engine/tests/README.md` (une ligne), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `banner.gd` (bips existants), scripts de rendu d'E1, `run_engine_tests.sh`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Vent : silence à 0 km/h ; volume strictement croissant de 5 à 60 km/h, identique à 60 et 80 km/h ; silence en pause.
3. Roue libre : à 30 km/h, puissance passée de 200 W à 0 W, rien avant 0,5 s, `playing` après ; arrêt dès 15 W.
4. Points d'intérêt : un cycliste qui s'approche puis s'éloigne d'une cloche (`radius_m` 300) reçoit un seul `entered` et un seul `left` ; une position qui oscille entre 299 et 320 m ne produit pas de nouvel événement ; avec 6 points audibles, 4 sont rendus, les plus proches.
5. Lissage : entre deux évaluations espacées de 0,1 s, aucun volume ne varie de plus de 1,2 dB.
6. Déterminisme : la même suite de trames donne la même suite de sorties.

## 8. Hors périmètre

- Fichiers sons, `AudioStreamPlayer3D`, bus audio et réglages de volume (sprint 6).
- Sons choisis par thème pour chaque `kind`.

## 9. Livraison (24 octobre 2026, PR #68)

- `engine/scripts/sound_model.gd` : modèle acoustique pur (vent, cliquetis de roue libre, bips d'événements et compte à rebours ERG, 4 POI sonores les plus proches).
- `engine/tests/unit/test_sound_model.gd` : 16 vérifications sans écran.
- Intégration continue GitHub Actions verte.
