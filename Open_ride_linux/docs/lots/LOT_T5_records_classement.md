# Lot T5 – Records personnels et classement local

## 1. Objectif

Tenir les records personnels de chaque segment (plan de la série T §3.2, décisions T-Q1 et du 27 octobre) dans un module pur du core : fichier `~/OpenRide/records.json` par parcours et par segment, 10 meilleurs temps avec leur date, tables « avec bonus » et « sans bonus » séparées, recalcul depuis les journaux, écart au record en direct et classement local du passage (toi, tes records, les bots). Le journal gagne la ligne `powerup` décidée le 27 octobre, pour que les records « avec bonus » se recalculent. Le branchement dans la séance (passage terminé, champ `segment` et message `segment_result`) vient avec le contrat T1.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.2, §6 (T-Q1) et « Décisions du 27 octobre ».
2. `docs/lots/LOT_T4_chronometrage_segments.md` (`SegmentPass`, `passes_from_journal`).
3. Code : `core/src/openride_core/segment_timing.py`, `core/src/openride_core/journal.py`, `core/src/openride_core/progression.py` (lignes `segment` et `jersey` lues par la série V, lot V5).

## 3. Prérequis

T4 (livré, PR #251) et N9 (livré). Aucun contrat ; branchement avec T1 (IPC v1.4).

## 4. Travail demandé

Nouveau module `core/src/openride_core/records.py` :

- `RecordBook.load(path)` et `save(path)` : fichier JSON versionné (`version` = 1) ; absent, carnet vide ; illisible, version ou forme inconnue, ou temps invalide : `RecordsError` claire. Écriture d'un coup (fichier temporaire puis remplacement).
- Forme : `routes` → identifiant du parcours → identifiant du segment → tables `no_bonus` et `bonus`, chacune triée et limitée aux 10 meilleurs (`time_s`, `date` « AAAA-MM-JJ HH:MM », `avg_power_w` mesurée, `avg_wkg`).
- `add(route, segment, passage, date)` : range le passage dans sa table (avec bonus si au moins un bonus était actif) et rend la place, « record battu » et l'écart à l'ancien record. Un même passage (même date, même temps) n'est noté qu'une fois.
- `live_gap(route, segment, avec_bonus, chrono, fraction)` : écart au record pendant le passage, au prorata de la distance parcourue (négatif = en avance).
- `ranking(route, segment, passage, bots)` : classement local, à appeler avant `add` ; le fantôme n'est pas un coureur de plus, ton meilleur temps le représente (décision du 27 octobre).
- `rebuild(route, journaux, segments, longueur, boucle, masse)` et `merge` : records recalculés depuis les journaux du parcours (en-tête `route_id`, date du premier relevé).

Journal (`journal.py`, `segment_timing.py`) :

- `JournalWriter.powerup(kind, t_start, duration_s, ts)` écrit `{"kind": "powerup", "ts", "powerup", "t", "duration_s"}` ; les champs existants ne changent pas et les lecteurs actuels ignorent cette ligne.
- `passes_from_journal` lit ces lignes : un relevé pris pendant un bonus le note dans le passage.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/records.py`, `core/tests/test_records.py`, ce cahier.
- **Modifiés :** `core/src/openride_core/journal.py` (méthode `powerup`), `core/src/openride_core/segment_timing.py` (relecture des bonus).
- **Interdits :** `session.py`, `resume.py`, `recorder.py`, le contrat IPC, l'engine.

## 6. Modifications de contrat autorisées

Aucune pour l'IPC. Format du journal : ajout de la ligne `powerup` (décision du 27 octobre).

## 7. Critères d'acceptation

1. `python -m pytest -q` passe en entier dans `core/`.
2. Tables avec et sans bonus séparées ; place, record battu et écart justes.
3. 10 meilleurs temps gardés avec leur date ; un 12e temps plus lent n'entre pas ; pas de doublon.
4. Aller-retour du fichier ; fichiers illisibles, de version inconnue, mal formés ou à temps négatif refusés.
5. Écart en direct : record de 300 s, 147 s à mi-segment donne −3 s.
6. Classement : toi, tes records de la même table et les bots, triés ; pas de ligne de fantôme.
7. Recalcul depuis quatre journaux : passage annulé par une pause écarté, autre parcours ignoré, passage avec bonus aéro rangé dans la table « avec bonus ».

## 8. Hors périmètre

- Écriture des passages, des lignes `powerup` et des lignes `segment` (lues par la série V, lot V5) pendant la séance ; champ `segment` et message `segment_result` (T1 puis branchement).
- Reprise après incident : `resume.py` et `recorder.py` ne recopient que les lignes `record`, `event` et `device` ; recopier les lignes `powerup` vient avec le branchement.
- Menu des records (T10), HUD (T9), points et maillots (T14).

## 9. Livraison (27 octobre 2026)

- Module pur et 11 tests, ligne `powerup` du journal et sa relecture ; sans changement de `session.py` ni du contrat IPC ; branchement avec T1.
