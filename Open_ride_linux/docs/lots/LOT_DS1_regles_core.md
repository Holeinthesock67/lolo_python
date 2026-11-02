# Lot DS1 – Règles du mode « Dernier survivant » dans le core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : règles du mode « Dernier survivant » dans le core (arches, passages, éliminations, égalités, bilan) | Python | T12, T13, AS1 | Moyenne | Prêt (version 3.0 proposée) |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/3.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Écrire en module pur (aucune entrée-sortie dans la boucle) la course à l'élimination : position des arches, instant de passage de chaque coureur, élimination du dernier, égalités, place finale, trame `survivor`, lignes de journal et bilan.

## 2. À lire

`docs/3.0/PLAN_SERIE_DS.md` §2 et §6 ; `core/src/openride_core/classic.py` (forme d'un mode branché sur la séance) ; `core/src/openride_core/bots.py` (`ProfileBot`, `calibrate_bots`) ; `core/src/openride_core/segments.py` (lignes de sprint et sommets pour le calage).

## 3. Travail demandé

- Nouveau module du core (`survivor.py`) : `SurvivorRace(opponents, spacing_m, segments, seed)` avec `start(t, s, bots)`, `step(t, dt, s, bots)`, `frame()`, `due_results(t)` (messages `elimination` répétés 3 fois à 1 s), `summary()` et `take_journal()`.
- Arches : une par adversaire, à `s0 + k × écart`, calées sur une ligne de sprint ou un sommet à moins de 300 m (jamais avant 1 km) ; circuits : la distance continue au tour suivant.
- Passage interpolé entre deux pas ; élimination dès que l'avant-dernier coureur en course passe ; égalité sous 1 ms : bot avant joueur, puis niveau le plus bas, puis identifiant le plus grand.
- Composition du plateau : profils dans l'ordre grimpeur, rouleur, sprinteur, diesel, niveaux étalés (serré ± 3 %, normal ± 8 %, large ± 15 %) autour de `bots.level_pct`.
- Pas d'élimination pendant une pause.

## 4. Critères d'acceptation

1. Tests positifs et négatifs pour chaque règle du §2 du plan : nombre et position des arches, calage, circuit, élimination immédiate d'un coureur loin derrière, égalité, pause.
2. Course simulée de 4 et de 11 bots : exactement une élimination par arche, places de 1 à N + 1 sans doublon, trame `survivor` sous 400 octets.
3. Même graine, même course.
