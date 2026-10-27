# Lot T14 – Points et maillots de la séance

## 1. Objectif

Attribuer pendant la séance le maillot vert (sprints) et le maillot à pois (montées) à qui a le plus de points, bots compris (plan de la série T §3.4, décision T-Q5), avec le barème validé par le propriétaire le 27 octobre. Module pur du core ; le branchement (arrivées du cycliste et des bots, champ de `state`, lignes `jersey` du journal) vient avec le contrat T1 et les bots à profil (T12).

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.4 (« Maillots »), §6 (T-Q5) et « Décisions du 27 octobre ».
2. `docs/lots/LOT_T4_chronometrage_segments.md` (passages et heure de franchissement interpolée).
3. Code : `core/src/openride_core/segments.py` (catégories `4` à `HC`), `core/src/openride_core/progression.py` (lignes `jersey` lues par la série V : `kom` et `sprint`).

## 3. Prérequis

T2 et T4 (livrés). Les bots à profil (T12) ne sont pas nécessaires au module : il ne lit que des arrivées. Aucun contrat ; branchement avec T1 (IPC v1.4).

## 4. Travail demandé

Nouveau module `core/src/openride_core/jerseys.py` :

| Segment | Points par place |
| --- | --- |
| Montée HC | 20, 15, 10, 6, 4 |
| Montée 1re catégorie | 10, 8, 6, 4, 2 |
| Montée 2e catégorie | 5, 3, 2, 1 |
| Montée 3e catégorie | 2, 1 |
| Montée 4e catégorie | 1 |
| Sprint | 15, 10, 6, 4, 2 |

- `Standings(segments).finish(arrivées)` : les arrivées d'un pas (`rider_id`, segment, tour, heure de franchissement), cycliste et bots, rangées par heure ; la place est l'ordre d'arrivée sur la ligne de fin, chaque passage (segment, tour) est une course à part ; une seule arrivée par coureur et par passage.
- Un passage annulé par une pause n'arrive pas, donc ne marque pas et ne prend pas de place ; un passage avec bonus marque comme les autres.
- `leader("sprint" | "kom")` : porteur du maillot, `None` sans point ; égalité : celui qui a atteint ce total le premier.
- `points(rider)` et `state_dict()` : forme proposée pour T1 (porteurs et points de chacun).
- Identifiants de maillot `sprint` (vert) et `kom` (à pois), ceux que lit déjà la série V.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/jerseys.py`, `core/tests/test_jerseys.py`, ce cahier.
- **Interdits :** `session.py`, `bots.py`, le contrat IPC, l'engine.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `python -m pytest -q` passe en entier dans `core/`.
2. Barèmes égaux à la décision du 27 octobre.
3. Points à l'ordre d'arrivée, bots compris, sixième d'une HC sans point ; arrivées d'un même pas rangées par heure de franchissement.
4. Une seule arrivée par coureur et par passage ; segment inconnu refusé.
5. Boucle : chaque tour est une nouvelle course.
6. Égalité de points : le premier à atteindre le total garde le maillot.
7. Deux maillots tenus séparément ; `state_dict` donne porteurs et points.

## 8. Hors périmètre

- Arrivées des bots (T12 puis branchement), champ de `state` (T1), lignes `jersey` du journal en fin de séance (branchement, lues par V5), HUD des maillots (T15).

## 9. Livraison (27 octobre 2026)

- Module pur et 8 tests, sans changement de `session.py` ni du contrat ; branchement avec T1.
