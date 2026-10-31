# Lot T9 – Engine : HUD des segments et des bonus

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 2.0 série T : engine, HUD segment (approche, chrono, écart au record, résultat) et HUD bonus, coin supérieur droit | GDScript | T1, P16 (livrés) ; T7 | Moyenne | Non : interne (HUD) ; **codé le 27 octobre** (issue #399) ; tests Godot à passer sur le PC, validation à la recette T11 |

## 1. Objectif

Afficher, dans le coin supérieur droit laissé libre par P16, le bloc segment (approche, chrono, écart au record, résultat à l'arrivée) et le bloc bonus (bonus en réserve, bonus actif et compte à rebours), d'après les champs `segment`, `powerup` et le message `segment_result` du contrat 1.4. Décision du 27 octobre : **code d'abord, sans maquette**, validation ensemble à la recette T11.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.2, §3.3 et risque 5.
2. `docs/contracts/ipc_v1.md` révision 1.4 : champs `segment`, `powerup`, message `segment_result`.
3. Code : `engine/scripts/hud_view_model.gd`, `hud_view.gd` (coin supérieur droit réservé à la série T), `ipc_client.gd`, `erg_view.gd`.

## 3. Prérequis

T1 et P16 (livrés) ; T7 pour les vraies trames (en attendant, `engine/tests/fake_core.py` les produit).

## 4. Travail demandé

- **Modèle sans affichage** `engine/scripts/segment_hud_model.gd`, testé par `engine/tests/unit/test_segment_hud_model.gd` :
  - approche : nom, type, catégorie et distance (« Montée 2 · cat. 3 dans 1,2 km ») quand `d_to_start_m` est sous 2 km ;
  - dans le segment : chrono `elapsed_s` et écart au record `gap_to_pr_s` (« −3,2 s » en vert, « +1,8 s » en rouge, rien sans record) ;
  - résultat : à la réception de `segment_result` (doublons ignorés par `segment_id`), temps, « Record ! » et ancien record, place `rank`/`rank_total`, points de maillot ; affiché 8 s ;
  - bonus : icône et nom du bonus en réserve (« Z : Aéro »), bonus actif avec barre de temps `remaining_s` ; bloc masqué en ERG (champ absent).
- **Affichage** dans `hud_view.gd` : deux blocs empilés dans le coin supérieur droit, sous le panneau de droite, sans chevaucher l'indicateur de vent ni les blocs ERG ; tailles et couleurs du thème du HUD existant.
- Noms des segments lus dans la couche `segments.json` (le champ `segment` ne donne que l'`id`).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/segment_hud_model.gd`, son test.
- **Modifiés :** `hud_view.gd`, `hud_view_model.gd`, `ipc_client.gd` (message `segment_result`), `engine/tests/fake_core.py` (trames de démonstration si T7 n'est pas encore là).
- **Interdits :** le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests Godot sans écran verts, dont le nouveau modèle (approche, chrono, écart positif et négatif, résultat, doublons, ERG sans bloc bonus).
2. Avec `fake_core.py` ou le core de T7 : blocs visibles et lisibles à 1080p et 720p, sans chevauchement (contrôle visuel à la recette).
3. Une trame sans `segment` ni `powerup` donne le HUD d'aujourd'hui.

## 8. Hors périmètre

- HUD des bots et encart des voisins (T15) ; rendu 3D (T8).

## 9. Livraison (27 octobre 2026, code ; validation sur le PC)

- Nouveau modèle `engine/scripts/segment_hud_model.gd` :
  - approche sous 2 km (« Montée 2 · cat. 3 dans 1,2 km ») ;
  - chrono (« 1:23 ») et écart au record (« −3,2 s » en vert, « +1,8 s » en rouge, rien sans record) ;
  - résultat affiché 8 s (« 4:08,1 », « Record ! Ancien : 4:11,5 · 2 / 5 · +3 pts », « (bonus) » pour un passage avec bonus) ;
  - bonus en réserve (« Z : Aéro ») et bonus actif avec secondes restantes et barre de temps.
- `hud_view.gd` : blocs « segment » (300 × 100 px) et « bonus » (300 × 72 px) empilés sous le panneau de droite (`update_segment`) ; le bloc segment s'arrête à 448 px, au-dessus du bandeau ERG en 720p, et le bloc bonus n'apparaît jamais en ERG (champ `powerup` absent).
- `ipc_client.gd` : message `segment_result` (signal `segment_result_received`) ; révision annoncée « 1.4 ». `main.gd` donne au modèle les noms de la couche `segments` au chargement du parcours.
- `engine/tests/fake_core.py --serie-t SECONDES` : séance de démonstration sur le parcours `demo` (champs `segment`, `powerup`, `jerseys`, trois `segment_result` à la fin de chaque segment), conforme aux schémas de la révision 1.4.
- Choix faits :
  - doublons de `segment_result` reconnus par segment et temps : un nouveau passage sur une boucle (autre temps) s'affiche ;
  - durée du bonus actif prise au premier `remaining_s` reçu (le contrat ne la donne pas) ;
  - `hud_view_model.gd` reste inchangé : tout le texte de la série T est dans le nouveau modèle.
- Tests : `engine/tests/unit/test_segment_hud_model.gd`, à lancer sur le PC (Godot n'est pas disponible dans l'environnement cloud).
