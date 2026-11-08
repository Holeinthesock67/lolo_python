# Lot VD1 – Contrat

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : contrat, colonne `bank_deg` et couche `venue` du format `.world`, surface `wood`, objet `track` de l'IPC | Contrat | VD0 | Petite | Livré le 8 novembre (PR #746, partie format ; objet `track` de l'IPC avec VD6, PR #769) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Ajouter au format `.world` et à l'IPC, par ajouts compatibles, ce que le vélodrome demande, sans rien changer aux parcours existants.

## 2. À lire

§7.1 du plan ; `docs/contracts/world_format_v1.md` §4 et §12 ; `docs/contracts/ipc_v1.md` ; schémas `docs/contracts/world/route.schema.json` et `docs/contracts/ipc/state.schema.json` ; plan de la série GP §8.1 (commandes génériques `list_mode_options` et `set_mode_option`).

## 3. Travail demandé

- Format `.world`, mineur libre suivant : colonne facultative `bank_deg` de `route.json` (absente = 0), valeur `wood` de la surface, couche facultative `venue.json` et son schéma ; ligne au journal des changements.
- IPC, première révision libre : objet facultatif `track` de `state` (épreuve, tour, tours restants, cloche, points, classement, éliminé) ; options d'épreuve par les commandes génériques de la série GP (les créer ici si GP2 n'est pas encore livré, sous le même nom).
- Lecture de `bank_deg` dans `route.py` et `route_data.gd` (interpolée comme l'altitude) ; vecteurs de test de la route complétés.
- Pire trame `track` ajoutée à l'outil X25.

## 4. Critères d'acceptation

1. Un `.world` sans `bank_deg` ni `venue` se lit exactement comme avant (tests existants inchangés).
2. Schémas valides, exemples et contre-exemples testés (`test_docs_coherence.py`, `test_ipc_contract`).
3. Pire trame `state` avec `track` et 12 coureurs sous 4 096 octets.
4. Validation du propriétaire avant fusion (contrat).

## 5. Fichiers touchés

- `docs/contracts/` (format et IPC), `core/src/openride_core/route.py`, `engine/scripts/route_data.gd`, outil X25.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.

## Livraison

PR #746 (fusionnée le 8 novembre, main bd7b29d5) : partie format. Objet `track` de l'IPC avec les épreuves (VD6, PR #769). Statut corrigé par le bilan du 8 novembre au soir.
