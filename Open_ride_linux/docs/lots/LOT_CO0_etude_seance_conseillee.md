# Lot CO0 – Étude de la séance conseillée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CO : étude de la séance conseillée (besoins aérobie léger, aérobie intense, anaérobie ; signaux, règles, écran) | Markdown | – | Petite | En PR (version 5.0) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Répondre à la demande du propriétaire du 7 novembre : dire comment identifier le besoin d'entraînement du joueur (aérobie léger, aérobie intense, anaérobie) à partir de ses séances et de ses courses, et proposer des règles lisibles et un écran du menu.

## 2. Livrables

- `docs/5.0/PLAN_SERIE_CO.md` : besoins et zones (§1), signaux S1 à S7 et cibles (§2), règles R0 à R7 (§3), courses et championnat (§4), suggestion Garmin (§4 bis), séances de jeu calibrées (§4 ter), questions Q1 à Q10 (§5), écran (§6), lots CO0 à CO9 (§7).
- Maquette de principe dans `/mnt/project-files/menus/co-seance-conseillee/` (hors dépôt).
- Cahiers CO0 à CO9 dans `docs/lots/`.

## 3. Critères d'acceptation

1. `python3 scripts/index_lots.py --verifier` et `pytest -q core/tests/test_docs_coherence.py` passent.
2. Le propriétaire répond aux questions (défauts de Q1 à Q10 acceptés le 7 novembre) et valide la maquette de principe avant CO4 et CO5.
