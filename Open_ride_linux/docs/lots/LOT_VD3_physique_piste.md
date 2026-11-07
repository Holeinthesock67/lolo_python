# Lot VD3 – Physique en piste

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : surface bois, air de la salle, hauteur sur la piste, distance au tour et placement | Python | VD1, AS2 | Moyenne | En PR (7 novembre) : bois, air de la salle, vent coupé, distance selon la hauteur ; placement sur la piste (corde, montée pour doubler, descente sous 15 km/h) au lot suivant |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Faire rouler le cycliste et les bots sur la piste avec la même physique que la route, plus la surface, l'air et la règle de distance du §4.2.

## 2. À lire

§2 et §4 du plan ; `core/src/openride_core/surface_physics.py`, `physics.py`, `draft.py`, `session.py` ; cahier AS2.

## 3. Travail demandé

- Surface `wood` dans `surface_physics.py` (facteur réglable dans la configuration, bornes testées).
- Section `[velodrome]` de la configuration (`temperature_c`, `braquet_fixe`), vent coupé.
- Distance : avance de `s` de v × R / (R + écart × cos θ) dans les virages, R et θ lus dans la couche `venue` et `bank_deg`.
- Placement : corde par défaut, montée pour doubler (AS2), descente automatique sous 15 km/h dans un virage.

## 4. Critères d'acceptation

1. Pente envoyée strictement nulle sur toute la piste, quel que soit le réglage de difficulté.
2. Rouler 1 m plus haut sur un tour de 250 m coûte entre 4 et 6 m (test).
3. Bois : temps au tour d'un cycliste de 84 kg à 250 W plus court qu'en `paved`, écart conforme au facteur choisi à ± 10 %.
4. Une route classique reste identique (tests de non-régression de la physique).

## 5. Fichiers touchés

- `surface_physics.py`, `session.py`, `settings.py`, `config.py` (section `[velodrome]`), leurs tests.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
