# Lot T4 – Chronométrage des segments

## 1. Objectif

Chronométrer chaque passage sur un sprint ou une montée (plan de la série T §3.2), dans un module pur du core : heure d'entrée et de sortie interpolées entre deux pas de 50 Hz, annulation en cas de pause, un passage par tour sur une boucle, statistiques du passage et relecture depuis le journal des séances. Les records (T5), les points des maillots (T14), l'obtention d'un bonus en fin de segment (T6) et le HUD (T9) s'appuient dessus.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.2 et §3.3 (bonus notés dans le passage).
2. `docs/lots/LOT_T2_detection_segments.md` (forme d'un segment).
3. Code : `core/src/openride_core/physics.py` (`RiderPhysics.s` cumulée), `core/src/openride_core/session.py` (`_step`, `_set_state` et événements `pause` du journal), `core/src/openride_core/journal.py`.

## 3. Prérequis

- T2 pour les segments réels ; le module lit les segments par attributs (`id`, `name`, `type`, `s_start`, `s_end`) et se teste sans T2.
- Aucun contrat : le branchement dans `session.py` et l'envoi de `segment` et `segment_result` à l'engine viennent avec T1 (IPC v1.4).

## 4. Travail demandé

Nouveau module `core/src/openride_core/segment_timing.py` :

- `SegmentTimer(segments, length_m, loop, rider_mass_kg)` ; `step(t, s, power_w, bonus)` à chaque pas de `RUNNING`, avec le temps chronométré et la distance cumulée (sur une boucle, le tour k commence à k × L).
- Entrée et sortie interpolées linéairement entre deux pas ; plusieurs segments chevauchants chronométrés en même temps ; segment entier franchi pendant un seul pas traité ; un segment qui commence en s = 0 compte au premier pas.
- `pause(raison)` : les passages en cours sont annulés (toutes les raisons, `trainer_lost` compris) et notés dans `cancelled` ; la reprise ne crée pas de faux franchissement.
- `SegmentPass` : segment, tour, entrée, sortie, temps, puissance moyenne **mesurée** (intégrée sur le temps), W/kg, vitesse moyenne, bonus actifs pendant le passage (`with_bonus` pour séparer les records, décision T-Q1) ; `to_dict()` pour le futur message `segment_result`.
- `live(t, s)` : segment en cours (distance jusqu'à l'arrivée, chrono) ou prochain départ (distance), y compris au tour suivant d'une boucle.
- `passes_from_journal(path, segments, …)` : rejoue un journal `.jsonl` (relevés à 1 Hz, événements `pause`) pour recalculer les passages d'une séance passée (base des records de T5).
- Aller-retour : `s` ne fait que croître, un segment ne se chronomètre donc que dans le sens où il a été défini.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/segment_timing.py`, `core/tests/test_segment_timing.py`, ce cahier.
- **Interdits :** `session.py`, `journal.py` (format inchangé), le contrat IPC, l'engine.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `python -m pytest -q` passe en entier dans `core/`.
2. 1 000 m à 10 m/s : 100 s à 0,02 s près, puissance, W/kg et vitesse moyennes justes.
3. Cycliste simulé par `physics.py` à 50 Hz : temps égal à 0,02 s près à celui d'une simulation à 1 kHz.
4. Pause au milieu d'un segment : passage annulé ; reprise dans le segment : aucun passage.
5. Boucle : un passage par tour ; segment au départ d'une boucle compté à chaque tour.
6. Segments chevauchants et bonus actif : les deux passages notent le bonus.
7. Journal avec une pause dans le sprint : la montée est retrouvée (100 s), le sprint est annulé.

## 8. Hors périmètre

- Records et classement local (T5), points (T14), écart au record en direct (T5 puis T9).
- Bonus utilisés écrits au journal : le format du journal ne change pas ici ; T6 et son branchement les ajouteront, `passes_from_journal` rend donc `bonuses` vide.

## 9. Livraison (26 octobre 2026)

- Module pur et 11 tests, sans changement de `session.py` ni du contrat ; branchement avec T1. Ligne de suivi : ce cahier (le suivi général garde la ligne de T2 pour la série).
