# Lot VD4 – Ruban relevé

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : ruban de piste relevé, lignes peintes, caméra, avatar et bots qui penchent | GDScript | VD2 | Moyenne | En PR (7 novembre) : ruban générique, profil de piste, shader bois, coureurs et caméra sur la pente ; captures low/medium/high à valider, banc GPU sur PC à demander au fil de fusion |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Afficher la piste relevée avec un seul constructeur de ruban, la route classique devenant le cas `bank_deg = 0`.

## 2. À lire

§7.2 du plan ; `engine/scripts/road_builder.gd`, `camera_follow.gd`, `bots_view.gd`, `avatar_view.gd`.

## 3. Travail demandé

- Coupe tournée autour de la ligne de mesure selon `bank_deg` ; côte d'azur non relevée ; zone de sécurité ; balustrade.
- Texture de piste en bois et lignes peintes du §3.1 placées en distance depuis le bord intérieur.
- Position 3D des coureurs d'après `lane_m` remonté sur la pente (§4.2) ; inclinaison de l'avatar et des bots selon le relèvement et la vitesse ; inclinaison de la caméra limitée (réglable).
- Captures `low`, `medium`, `high` d'une ligne droite et d'un virage, validées par le propriétaire.

## 4. Critères d'acceptation

1. Routes existantes identiques au pixel près sur les captures de référence (`compare_captures.py`).
2. Aucun trou ni recouvrement à la jointure du tour.
3. Coût mesuré au banc dans les trois préréglages.

## 5. Fichiers touchés

- `road_builder.gd`, `camera_follow.gd`, `bots_view.gd`, `avatar_view.gd`, tests unitaires de l'engine.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.

## 5. Livraison (7 novembre)

- `road_builder.gd` : une seule coupe, tournée par `bank_deg` autour de la ligne de mesure (bank 0 : sommets identiques, test `test_track_ribbon.gd`) ; sur une piste (couche `venue`), profil à 6 sommets : zone de sécurité et côte d'azur à plat, piste relevée, balustrade verticale de 1 m ; une coupe par mètre ; pas de talus.
- `shaders/track_wood.gdshader` : lattes de 5 cm, lignes de mesure, sprinteurs et stayers, arrivée, poursuites, 200 m.
- `route_data.gd` : `bank_at`, `bank_right`, couche `venue` ; avatar et bots inclinés du relèvement, caméra de la moitié (`CAMERA_BANK_SHARE`), vue de côté posée sur la pente.
- Placement (cœur, `velodrome.py`) : `lane_m` publié = hauteur sur la piste ; ligne des sprinteurs par défaut, corde sous 15 km/h en virage.
- Tour de captures : `engine/tests/tours/velodrome.json`.
- Reste : critère 3 (banc GPU sur PC, trois préréglages) ; décor de la salle en VD5.
