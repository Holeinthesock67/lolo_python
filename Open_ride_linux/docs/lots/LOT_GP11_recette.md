# Lot GP11 – Recette sur le vélo et banc

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : recette sur le vélo en étapes de 10 min et banc `low`, `medium`, `high` | Recette | GP3, GP5, GP7, GP8, GP9 | Petite | Préparé le 12 novembre (recette et outil de bilan, version 4.0) ; essais sur le PC et le vélo à faire (GP9 fusionné), étape 5 complète après GP4 |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Vérifier sur le PC cible et le home trainer que le mode est jouable, lisible et sans à-coup sous les pieds.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` ; `docs/PLAN_DE_TESTS.md`.

## 3. Travail demandé

- Étapes de 10 min au plus : course de 2 bots sur circuit ; course de 4 bots en ligne ; chaque objet lancé et reçu au moins une fois ; esquive au Click et au clavier.
- Banc sans vélo, séquencé par le fil de fusion : départ du mode en `low`, `medium` et `high`.

## 4. Critères d'acceptation

1. Aucun à-coup de résistance ressenti à la réception d'un objet ; pente envoyée du journal lisse.
2. Budgets GPU tenus dans les trois préréglages ; captures validées par le propriétaire.

## 5. Livraison (12 novembre 2026, préparation)

- Recette : [`docs/RECETTE_SERIE_GP.md`](../RECETTE_SERIE_GP.md). §1 banc sans vélo `grand_prix` en `low`, `medium` et `high` (budgets GPU 8, 13 et 16 ms, captures), puis quatre étapes de 10 min au plus : course en ligne à 4 bots ; circuit à 2 bots ; pièges et attaques avec esquive au Click puis au clavier ; objets pour soi, de défense et contre la tête, devant (bots à 70 %) puis derrière (bots à 130 %). Chaque étape restreint les objets par l'écran « Objets » du menu (GP9) pour que chacun soit lancé et reçu.
- Outil de bilan : `python -m openride_core.tools.gp_recette [--dernieres N] [JOURNAL…] [--json]` (`core/src/openride_core/tools/gp_recette.py`). Il lit les lignes `gp_start`, `gp`, `gp_summary` et `record` des journaux du profil en cours et contrôle : couverture (chaque objet joué utilisé par le cycliste ; chaque objet qui peut toucher, d'après sa table : effet sur la cible, éclaboussure ou vol, subi au moins une fois ; un vol compte pour l'objet qui l'a permis) ; formats (au moins un circuit et une course en ligne) ; critère 1, pente envoyée lisse autour de chaque coup subi (de 1 s avant à 6 s après : pas plus de variation d'une seconde à l'autre que le 99e centile du reste de la course plus 0,3 point, plancher 0,5 ; supplément de vent et d'abri sous 0,5 point par seconde). Code 0, 1 ou 2 (aucune course lisible).
- Tests : `core/tests/test_gp_recette.py`, dont une vraie séance de 3 tours à 4 bots (fixture de `test_grandprix_session.py`) relue par le bilan.
- Circuit : l'étape 3 se joue sur « Circuit des Prés » (lot O38, boucle de 3 km livrée avec le jeu), 2 tours.
- Reste : banc PC (§1, par le fil de fusion), étapes 2 à 5 sur le vélo, étape 5 complète après GP4, captures validées par le propriétaire.
