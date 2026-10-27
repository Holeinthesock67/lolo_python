# Lot T10 – Menu : records par parcours et option bonus

## 1. Objectif

Dans le menu de l'engine : un écran « Records » par parcours (pour chaque segment, les 10 meilleurs temps avec leur date, tables « sans bonus » et « avec bonus ») et l'option « Bonus » (oui ou non) dans les réglages. Décision du 27 octobre : **code d'abord, sans maquette**, validation à la recette T11.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.2 et §6 (T-Q1, records séparés).
2. Cahier `LOT_T5_records_classement.md` : forme versionnée de `~/OpenRide/records.json`.
3. Code : `engine/scripts/menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `settings_view_model.gd`, `catalog_model.gd` ; `core/src/openride_core/settings.py`.

## 3. Prérequis

T5 et N6 (livrés) ; T7 pour la clé `[powerups] enabled` de `set_setting` et pour des records réels.

## 4. Travail demandé

- **Lecture des records :** l'engine lit lui-même `~/OpenRide/records.json` en lecture seule, comme il lit déjà les `.world` et `config.toml` ; version inconnue ou fichier illisible : écran « Aucun record lisible », sans erreur. Le core reste le seul à écrire ce fichier. *Choix proposé :* ce chemin évite une commande `list_records` dans le contrat ; si le propriétaire préfère passer par le core, la commande prendra la prochaine révision libre.
- **Modèle sans affichage** `engine/scripts/records_view_model.gd`, testé par `engine/tests/unit/test_records_view_model.gd` : liste des segments du parcours choisi (noms lus dans `segments.json`), puis table du segment, basculement « sans bonus » / « avec bonus » ; temps au dixième, date, puissance moyenne et W/kg.
- **Menu :** entrée « Records » sur l'écran « Prêt » du parcours choisi ; navigation selon le plan de boutons commun (spécification générale §7.1, sans exception) : ± déplacent, A court passe à l'élément suivant (bascule de table), A long valide, Y revient.
- **Option « Bonus » :** ligne des réglages (O3) liée à la clé `powerups.enabled` de `set_setting` (T7), refusée pendant une séance (`busy`) comme les autres réglages.

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
