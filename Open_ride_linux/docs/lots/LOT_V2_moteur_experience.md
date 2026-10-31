# Lot V2 – Moteur d'expérience : gains, niveaux, défis, recalcul depuis le journal

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Moteur d'expérience : gains, niveaux, défis, recalcul depuis le journal, commande `openride-core xp` | Python | — | Moyenne | **Livré le 27 octobre** (PR #273, issue #239) ; branchement par V11 |

## 1. Objectif

Calculer l'expérience (XP), le niveau et les défis réussis **uniquement à partir des journaux de séance** écrits par OpenRide (`~/OpenRide/Activities/.journal/*.jsonl`). Le module est pur et testé en pytest ; rien n'est branché sur la séance ni sur l'IPC (lots V11 et T1). Une commande `openride-core xp` montre le résultat sur l'historique réel, pour régler la courbe avant de la figer (risque 2 du plan).

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.1, §2.4, §3 et §5.
2. Code : `core/src/openride_core/journal.py` (format), `recorder.py` et `session.py` (écriture de l'en-tête), `workout.py` (`workout_path`, `load_workout`, `Workout.duration_s`), `tools/history.py` (style d'une commande de lecture de l'historique).

## 3. Prérequis

Aucun : partir de `main`.

## 4. Travail demandé

### 4.1 Origine de la séance dans le journal

L'en-tête du journal gagne un champ `source` : `live` (trainer FTMS réel), `simulated` (trainer `mock` ou `sim` sans rejeu) ou `replay` (`--replay`). Ajout compatible : les lecteurs existants ignorent ce champ. Un journal sans `source` (antérieur à ce lot) est traité comme `live` (décision V-Q3 : les séances passées comptent ; voir V-Q6 pour les séances simulées anciennes).

### 4.2 Fichier de données `progression.toml`

Livré dans le paquet (`core/src/openride_core/data/progression.toml`), remplaçable par `~/OpenRide/progression.toml` (copie modifiée par le propriétaire, lue en priorité ; un fichier invalide est refusé avec une erreur claire, jamais à moitié lu). Valeurs du plan §2.1 :

- `[xp]` : `per_km = 20`, `per_climb_m = 2`, `erg_per_min = 10`, `erg_completed_bonus = 0.20`, `per_segment = 50`, `per_segment_pr = 100`, `per_jersey = 200`, `rogue_per_min = 10`, `rogue_boss_default = 100` et table `[xp.rogue_boss]` (bonus par boss, la Chimère centrale à 300 : valeurs provisoires, à ajuster avec la série R).
- `[rules]` : `min_session_s = 300`, `climb_deadband_m = 1.0`, `erg_replaces_distance = true` (V-Q7).
- `[levels]` : `count = 50`, `xp_level_2 = 1000`, `xp_level_max = 100000`.
- `[[challenges]]` : défis (§4.5).

### 4.3 Faits d'une séance

`session_facts(path, workout_duration=None) -> SessionFacts` lit un journal et donne : `journal` (nom du fichier), `start_ts`, `route_id`, `workout_id`, `source`, `duration_s` (dernier `t` chronométré), `distance_m` (plus grande `distance`), `climb_m` (somme des montées d'altitude, avec une zone morte de `climb_deadband_m` pour ignorer le bruit), `erg_s` (relevés à 1 Hz avec une cible ERG `target_w` non nulle), `erg_completed` (vrai si la durée de l'entraînement est connue et `erg_s ≥ durée − 5 s` ; `None` si elle est inconnue) et `events` (liste vide pour l'instant : segments, maillots et runs viendront de V5).

### 4.4 Gains, éligibilité et niveaux

- `ineligible_reason(facts, table)` : `replay`, `simulated`, `too_short` (moins de 5 min chronométrées) ou `None`. Les traces importées (lot M7) n'écrivent pas de journal et ne sont donc jamais lues.
- `session_gains(facts, table) -> XpGains` : points par source (`distance`, `climb`, `erg`, `erg_bonus`, `segment`, `segment_pr`, `jersey`, `rogue`, `rogue_boss`) et total, entiers arrondis par source. Avec `erg_replaces_distance` vrai, une séance ERG (`erg_s` > 0) ne compte ni la distance ni le dénivelé (V-Q7) : 10 points par minute valent 20 points par km à 30 km/h.
- Seuils de niveau : progression arithmétique entre deux niveaux, le premier écart valant `xp_level_2` et la somme des 49 écarts `xp_level_max` ; seuils arrondis à la dizaine, strictement croissants. `level_for(xp) -> LevelInfo` (`level`, `xp`, `xp_level_start`, `xp_next_level` ou `None` au niveau 50).

### 4.5 Défis

Chaque défi : `id`, `name`, `stat`, `threshold`, `reward` (identifiant d'équipement offert, lu par V3, ou vide). Statistiques reconnues : `total_km`, `total_climb_m`, `sessions`, `best_session_km`, `best_session_climb_m`, `erg_completed`, et les compteurs d'événements `segments`, `segment_prs`, `jerseys_kom`, `jerseys_sprint`, `hc_climbs`, `rogue_bosses` (nuls tant que V5 n'est pas livré). Défis livrés : 1 000 km cumulés, 10 000 m de dénivelé cumulé, première séance de 50 km, 10 entraînements ERG terminés, premier col HC, premier maillot à pois, premier boss Cyber-Rogue vaincu. Un défi est daté par la première séance qui le remplit.

### 4.6 Recalcul complet

`recompute(journal_dir, table, workout_durations) -> Progress` : toutes les séances triées par heure de début, gains de chacune (séances refusées listées avec leur raison), XP totale, niveau, statistiques cumulées et défis réussis. Un journal illisible est signalé et sauté sans arrêter le calcul. Le résultat ne dépend que des journaux et du fichier de données : effacer le profil ne perd rien (risque 4 du plan).

### 4.7 Commande `openride-core xp`

`openride-core xp [--dir DOSSIER] [--json] [--config FICHIER]` : niveau, XP, prochain seuil, défis réussis, puis une ligne par séance (date, parcours, durée, km, D+, points, ou raison du refus). Les durées des entraînements viennent de `~/OpenRide/Workouts` (dossier de la configuration). `--json` donne des clés stables, documentées en tête du module. Depuis le lot X39, `--save FICHIER` écrit cette sortie comme instantané et `--compare FICHIER` donne l'écart avec elle (non-régression du recalcul avant/après une PR).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/progression.py`, `core/src/openride_core/data/progression.toml`, `core/src/openride_core/tools/xp.py`, `core/tests/test_progression.py`.
- **Modifiés :** `journal.py` (champ `source`, docstring), `recorder.py`, `session.py` (transmission de `source` seulement), `__main__.py` (sous-commande), `core/pyproject.toml` (données du paquet), `README.md` (commande citée), `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** `physics.py`, l'IPC, l'engine.

## 6. Modifications de contrat autorisées

Aucune pour l'IPC. Format du journal : champ facultatif `source` dans l'en-tête (ajout compatible, décrit dans la docstring de `journal.py`).

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Seuils : niveau 2 à 1 000 points, niveau 50 à 100 000 (à l'arrondi près), écarts strictement croissants, 50 niveaux.
3. Séance synthétique de 30 km et 300 m de D+ en SIM : 600 + 600 = 1 200 points ; même séance en 4 min 59 s : refusée `too_short`.
4. Séance ERG de 60 min terminée : 600 + 120 = 720 points, distance non comptée ; interrompue à 40 min : 400 points.
5. Journal de rejeu ou simulé : refusé avec la bonne raison ; journal sans `source` : compté.
6. Recalcul sur un dossier de 3 journaux (dont un tronqué) : même total que la somme des séances, défi « 50 km » daté par la bonne séance.
7. Un fichier de données personnel invalide est refusé avec un message qui nomme la clé fautive.

## 8. Hors périmètre

Profil et choix (V4), équipement (V3), pièces (V3b), segments, maillots et runs (V5), affichage (V9).

## 9. Livraison (26 octobre 2026, issue #239)

- Code et tests : `progression.py`, `data/progression.toml`, `tools/xp.py`, `core/tests/test_progression.py` (25 tests).
- Écart assumé : un journal recréé après une panne d'écriture (`_reprise-N`, `recorder.py`) recopie toute la séance ; deux journaux de même heure de départ (à 1 s près) comptent donc une seule fois, le plus long.
- Le fichier personnel `~/OpenRide/progression.toml` ne contient que les clés changées : elles remplacent celles du fichier livré (une liste `[[challenges]]` remplace toute la liste).

