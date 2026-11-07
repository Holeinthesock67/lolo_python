# Lot CO1 – Module du conseil dans le core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : module pur `coach.py` (signaux S1 à S4 et S7, règles R0 à R7, table `coach.toml`), commande `openride-core coach` | Python | CO0, O28, O10, R16, MJ1 (livrés sauf CO0) | Moyenne | En PR (version 5.0) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Calculer dans le core, sans affichage, le conseil du jour et sa raison, testable en CI sur des historiques synthétiques.

## 2. À lire

`docs/5.0/PLAN_SERIE_CO.md` §1 à §3 ; code : `tools/session_summary.py` (`ZONES`, `BEST_WINDOWS`, `compute_summary`), `tools/history.py` (`compute_history`, cache), `tools/estimate_cp.py`, `plans.py` (`load_state`, `today`), `ftp_test.py`, `profiles.py` (`current()`).

## 3. Travail demandé

- `core/src/openride_core/coach.py`, module pur : `Signals` (S1 répartition 28 j par besoin, S2 CTL/ATL/forme, S3 jours depuis la dernière séance dure, S4 profil de puissance en multiples de la FTP, S7 âge de la FTP), `recommend(signals, table, today) -> Advice` (`need`, `rule`, `reason`, `details`).
- Lecture de l'historique dans une fonction à part (`collect_signals(profile, today)`), seule à toucher le disque, qui passe par les caches de `history` et d'`estimate_cp`.
- Table `core/src/openride_core/data/coach.toml` : bornes des besoins, cibles par objectif, seuils des règles.
- Sous-commande `openride-core coach [--date AAAA-MM-JJ] [--objectif …] [--json] [--profil ID]` ; clés `--json` stables, documentées dans la docstring.
- Les séances rejouées (`source = replay`) sont exclues ; les séances simulées ne comptent que sur le profil d'essai.

## 4. Tests

`core/tests/test_coach.py` : générateur d'historiques synthétiques (journaux `.jsonl` écrits dans `tmp_path`, puissance seconde par seconde) ; un cas par règle R0 à R7 (avec la raison attendue), bornes des zones (55, 75, 120 %), forme calculée sur 42 et 7 jours, séance rejouée exclue, profil sans séance. Jamais de vrai FIT.

## 5. Critères d'acceptation

1. `pytest -q` passe dans `core/`.
2. `openride-core coach --json` sur un dossier synthétique donne le besoin, la règle et la raison attendus.
3. Aucune formule de zone, de NP ou de TSS dupliquée : tout vient de `session_summary`.

## 6. Réalisation (7 novembre, en PR)

- `coach.py` : `SessionFacts`, `session_facts`, `build_signals`, `Inputs`, `recommend`, `advise` (purs) ; `collect_facts` (seule lecture du disque, cache `.cache/coach.json` du profil) et `plan_today` ; sous-commande `openride-core coach`.
- La règle RG (suggestion de la montre) est dans `recommend` dès CO1, avec `--montre TYPE[:MIN[:W]]` pour l'essayer ; CO8 garde la saisie au menu, l'écriture dans le profil et le contrat. De même, `Inputs.raced_yesterday` et `Inputs.next_race` (R1, R2) sont prêts pour CO6 ; `--prochaine-course` permet d'essayer R2.
- Choix : la forme compte les séances du jour même ; un objectif s'efface au profit de « reprise » sous une CTL de 20 ; sans séance dans la cible, R6 conseille l'endurance ; R7 départage par le profil de puissance, puis par le besoin le moins récemment travaillé.
- Tests : `core/tests/test_coach.py` (19 cas, journaux fabriqués dans `tmp_path`).
