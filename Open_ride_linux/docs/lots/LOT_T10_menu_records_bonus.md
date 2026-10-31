# Lot T10 – Menu : records par parcours et option bonus

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 2.0 série T : menu, écran « Records » par parcours et option « Bonus » | GDScript | T5, N6 (livrés) ; T7 | Moyenne | Non : interne (menu) ; **codé le 27 octobre** (issue #400) ; tests Godot à passer sur le PC, validation à la recette T11 |

## 1. Objectif

Dans le menu de l'engine : un écran « Records » par parcours (pour chaque segment, les 10 meilleurs temps avec leur date, tables « sans bonus » et « avec bonus ») et l'option « Bonus » (oui ou non) dans les réglages. Décision du 27 octobre : **code d'abord, sans maquette**, validation à la recette T11.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.2 et §6 (T-Q1, records séparés).
2. Cahier `LOT_T5_records_classement.md` : forme versionnée de `~/OpenRide/records.json`.
3. Code : `engine/scripts/menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `settings_view_model.gd`, `catalog_model.gd` ; `core/src/openride_core/settings.py`.

## 3. Prérequis

T5 et N6 (livrés) ; T7 pour la clé `powerups.mode` de `set_setting` et pour des records réels.

## 4. Travail demandé

- **Lecture des records :** l'engine lit lui-même `~/OpenRide/records.json` en lecture seule, comme il lit déjà les `.world` et `config.toml` ; version inconnue ou fichier illisible : écran « Aucun record lisible », sans erreur. Le core reste le seul à écrire ce fichier. *Choix proposé :* ce chemin évite une commande `list_records` dans le contrat ; si le propriétaire préfère passer par le core, la commande prendra la prochaine révision libre.
- **Modèle sans affichage** `engine/scripts/records_view_model.gd`, testé par `engine/tests/unit/test_records_view_model.gd` : liste des segments du parcours choisi (noms lus dans `segments.json`), puis table du segment, basculement « sans bonus » / « avec bonus » ; temps au dixième, date, puissance moyenne et W/kg.
- **Menu :** entrée « Records » sur l'écran « Prêt » du parcours choisi ; navigation selon le plan de boutons commun (spécification générale §7.1, sans exception) : ± déplacent, A court passe à l'élément suivant (bascule de table), A long valide, Y revient.
- **Option « Bonus » :** ligne des réglages (O3) liée à la clé `powerups.mode` (`on` ou `off`) de `set_setting` (T7), refusée pendant une séance (`busy`) comme les autres réglages.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/records_view_model.gd`, son test.
- **Modifiés :** `menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `settings_view_model.gd`.
- **Interdits :** le core (sauf, si besoin, le libellé de la clé dans `settings.py`, fait par T7), le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests Godot sans écran verts, dont le modèle des records (deux tables, fichier absent, version inconnue, segment sans record).
2. Après une séance sur le parcours de démonstration : l'écran « Records » montre le temps de la montée et du sprint.
3. Option « Bonus » à « non » : la séance suivante n'a ni arche ni bonus.

## 8. Hors périmètre

- Effacement ou export des records ; menu Cyber-Rogue (R13) et Garage (V8).

## 9. Livraison (27 octobre 2026, code ; validation sur le PC)

- Nouveau modèle `engine/scripts/records_view_model.gd` :
  - lecture seule de `~/OpenRide/records.json`, relu à chaque ouverture de l'écran ; fichier absent : aucun temps ; illisible ou version autre que 1 : « Aucun record lisible » ;
  - liste des segments du parcours (noms de la couche `segments`), meilleur temps sans bonus et meilleur temps avec bonus ; segment sans temps désactivé ;
  - table d'un segment : les temps au dixième (« 1. 4:08,1 · 27/10/2026 18:05 »), puissance moyenne et W/kg ; première ligne « A : voir les temps avec bonus » (ou « sans bonus »).
- Menu :
  - `menu_model.gd` : entrée « Records du parcours » en fin d'écran Prêt ;
  - `menu_flow.gd` : écrans « Records » et table ; A long ouvre, A court bascule entre les deux tables, Y revient ; aucune commande ajoutée au contrat ;
  - `main.gd` donne la couche `segments` au modèle au chargement du parcours.
- Option « Bonus » : la ligne des réglages vient du core (clé `powerups.mode`, T7) ; `settings_view_model.gd` affiche `on` / `off` en « oui » / « non » (table `CHOICE_TEXTS`). `menu_view.gd` reste inchangé.
- Tests : `engine/tests/unit/test_records_view_model.gd` (deux tables, fichier absent, version inconnue, fichier illisible, segment sans record, navigation depuis l'écran Prêt, oui / non), à lancer sur le PC (Godot n'est pas disponible dans l'environnement cloud).
