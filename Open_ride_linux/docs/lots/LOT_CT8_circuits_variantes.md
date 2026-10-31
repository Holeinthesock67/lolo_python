# Lot CT8 – Circuits générés et variantes asymétriques

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : circuits générés et variantes asymétriques | Python | CT0, CT1 ; W (étape 2) | Grande | Prêt (version 5.0) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Décision du 29 octobre : les bifurcations se font d'abord sur des circuits générés pour le mode, puis sur certains carrefours du monde ouvert. La voie A, courte et raide, sans abri, éclate le groupe ; la voie B, plus longue et plus douce, le garde soudé. Les deux voies montent le même dénivelé, et leurs longueurs sont calculées par la physique du core.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Plan `docs/2.0/PLAN_SERIE_W.md` (carrefours, `choose_branch`) ; cahier `LOT_R6_run_deck_boss.md` et code `rogue/rooms.py` (parcours généré sans GPS) ; code `demo_world.py`, `route.py`, `open_world.py`, `bots.py` (`calibrate`).

## 3. Prérequis

CT0 et CT1 livrés ; pour l'étape 2, la série W livrée.

## 4. Travail demandé

- **Étape 1, circuits générés** : générateur pur `tactical/circuit.py` qui produit une route (boucle de 5 à 20 km) avec relief, virages et 1 à 4 variantes ; `lat`, `lon` et `alt` à `null` comme en Cyber-Rogue ; graine reproductible.
- **Variante** : même point de départ et d'arrivée, même dénivelé. Voie A : 300 à 400 m à 10 à 12 %, Crr × 2, pas d'abri. Voie B : longueur calculée pour que A soit plus rapide de 5 à 10 s à la CP d'un rouleur (voir le tableau de l'étude, B de 600 à 700 m pour 41 m), abri × 1,25 sous le plafond de 0,55 (AS4).
- **Choix** : comme au monde ouvert (A court branche suivante, A long valider, flèches en complément) ; branche par défaut B sans appui ; verrouillage 30 m avant.
- **Bots** : choix selon le profil et la situation (grimpeur et attaquant sur A, groupe sur B).
- **Étape 2, monde ouvert** : marquer des carrefours dont les deux branches se rejoignent comme « asymétriques » et appliquer les mêmes règles.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tactical/circuit.py`, `core/tests/test_tactical_circuit.py`.
- **Modifiés :** `session.py`, `bot_tactics.py`, ce cahier, `00_INDEX.md` ; étape 2 : `open_world.py`.
- **Interdits :** le compilateur des parcours réels.

## 6. Modifications de contrat autorisées

Aucune : les champs viennent du lot CT1.

## 7. Critères d'acceptation

1. `pytest -q` passe ; génération d'un circuit en moins de 200 ms.
2. Même dénivelé sur A et B à 0,5 m près.
3. À la CP de chaque profil, A plus rapide que B de 5 à 10 s ; écart grimpeur–sprinteur à l'arrivée plus grand après A qu'après B.
4. Abri jamais au-dessus de 0,55.

## 8. Hors périmètre

Circuits dessinés à la main ; parcours `.world` réels avec variantes.
