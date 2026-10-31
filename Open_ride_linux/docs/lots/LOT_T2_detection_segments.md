# Lot T2 – Détection automatique des montées et des sprints

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 2.0 série T : détection automatique des montées et des sprints (module pur) | Python | — | Petite | **Livré le 27 octobre** (PR #247, module pur ; branché sur le `.world` par T3) |

## 1. Objectif

Premier lot de la série T (`docs/2.0/PLAN_SERIE_T.md`) : trouver sur le profil d'un parcours les **montées** à chronométrer et proposer des **zones de sprint**, dans un module pur du core, sans contrat ni engine. Les lots suivants s'en servent : T3 (couche `segments` du `.world` et segments déclarés à la main), T4 (chronométrage), T12 (stratégie des bots) et T14 (points des maillots).

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.1 (règles des segments) et §4 (risque 1 : profil bruité).
2. `docs/contracts/world_format_v1.md` §4 (couche route : `s`, `alt_m`, `grade_pct` lissée).
3. Code : `core/src/openride_core/route.py` (`Route.s`, `Route.alt_m`, `Route.grade_pct`), `core/src/openride_core/demo_world.py`.

## 3. Prérequis

Aucun : le module ne lit que la couche route, déjà livrée (lot A). Il ne dépend ni de la 1.0 ni du contrat T1.

## 4. Travail demandé

Nouveau module `core/src/openride_core/segments.py` :

- `Profile(s, alt_m, grade_pct)` et `Profile.from_route(route)` : le profil d'une couche route, avec la pente lissée qu'utilise déjà la route (aucun second lissage).
- **Montées** (`detect_climbs`) : un point « monte » à partir de 1,5 % ; les plages de points qui montent séparées par moins de 200 m sont fusionnées ; une montée est retenue si elle fait au moins 500 m, 3 % de moyenne et 30 m de gain. Si la fusion fait passer la moyenne sous les seuils (descente entre deux rampes), les morceaux sont évalués séparément.
- **Catégorie** (`climb_category`) : produit longueur (m) × pente moyenne (%) ; HC dès 80 000, 1re dès 64 000, 2e dès 32 000, 3e dès 16 000, 4e sinon (toute montée retenue est au moins de 4e catégorie, les seuils d'entrée faisant déjà le tri). Ces seuils reprennent ceux de Strava.
- **Sprints proposés** (`detect_sprints`) : tronçon de 200 à 500 m dont toute la pente lissée est entre −1 et +2 %, placé au bout du replat, à au moins 200 m d'une montée, jamais dans le premier kilomètre, au plus un tous les 10 km (écart entre deux débuts).
- `detect_segments(profile, auto_sprints=True)` : liste de `Segment` triée par début, identifiants `climb1`, `climb2`, `sprint1`…, noms « Montée 1 », « Sprint 1 ».
- **Segments manuels** : `manual_segments(profile, entrées)` lit des entrées `{type, start_km, end_km, name?}` (format du petit fichier de T3), identifiants `mclimb1`, `msprint1`… ; `merge_manual(auto, manual, "add" | "replace")` les ajoute (en retirant les automatiques du même type qui les chevauchent) ou les met à la place.
- `Segment.to_dict()` donne les champs prévus pour `segments.json` (plan §3.5) : `id`, `name`, `type`, `s_start`, `s_end`, `length_m`, `avg_grade_pct`, `gain_m`, `category`, `source`.
- Tous les seuils sont des constantes en tête du module.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/segments.py`, `core/tests/test_segments.py`, ce cahier.
- **Modifiés :** `docs/lots/00_INDEX.md` (série T), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `route.py`, `session.py`, le contrat IPC, le format `.world`, le compilateur et l'engine (T1 et T3).

## 6. Modifications de contrat autorisées

Aucune. La forme de `segments.json` sera fixée par T1 ; ce lot ne fait que la préparer.

## 7. Critères d'acceptation

1. `python -m pytest -q` passe en entier dans `core/`.
2. Une rampe de 2 km à 6 % entre deux plats est trouvée à un pas de route près, avec 120 m de gain et la 4e catégorie.
3. Seuils : 400 m à 8 %, 2 km à 2,5 % et 800 m à 3,5 % (28 m de gain) sont refusés ; 900 m à 3,5 % est retenu.
4. Deux rampes séparées par 150 m de plat donnent une montée ; par 300 m, deux montées ; par 190 m de descente à 12 %, deux montées.
5. Profil bruité : un plat de 25 km avec ±1,4 % de bruit ne donne aucune montée ; une rampe avec ±3 % de bruit reste une seule montée ; avec ±1 %, ses bornes sont justes à 10 % près.
6. Sprints : sur 35 km de plat, longueur entre 200 et 500 m, début après le premier kilomètre, au moins 10 km entre deux débuts ; aucun sprint sur un replat de moins de 200 m hors des abords d'une montée.
7. Segments manuels : ajout, remplacement, refus clairs (bornes inversées, type inconnu, hors parcours, mode inconnu).
8. Le parcours de démonstration (`demo`, montée continue) donne une montée.

## 8. Hors périmètre

- Écriture de la couche `segments` dans le `.world`, lecture du fichier de segments manuels à côté du GPX, segments du parcours de démonstration (T3).
- Montée qui passe la ligne d'une boucle : elle est vue comme deux morceaux (début et fin du profil) ; T3 pourra les recoller si besoin.
- Sens des allers-retours : traité au chronométrage (T4).

## 9. Livraison (27 octobre 2026, PR #247)

- Nouveau module pur `core/src/openride_core/segments.py` : montées sur la pente lissée (500 m, 3 %, 30 m de gain, fusion sous 200 m de replat, catégories 4 à HC), sprints proposés de 200 à 500 m au plus tous les 10 km, segments manuels ajoutés ou à la place.
- Tests : `core/tests/test_segments.py` (critères 2 à 8).
- Branché sur le `.world` par T3 (PR #394) ; le chronométrage (T4) et l'affichage viennent avec le branchement de la série T.
