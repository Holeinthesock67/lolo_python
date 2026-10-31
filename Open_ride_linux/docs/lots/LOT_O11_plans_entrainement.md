# Lot O11 – Plans d'entraînement sur plusieurs semaines, côté core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Plans d'entraînement sur plusieurs semaines, séance du jour et suivi, import d'un dossier | Python | O9 ; O10 pour les jours de test | Moyenne | **Livré le 26 octobre** (issue #155) |

## 1. Objectif

Suivre un plan : « semaine 3, mardi : sweet spot 3 × 10 ». Ce lot ajoute des plans d'entraînement faits d'entraînements existants (`.zwo`, `.erg`, `.mrc`, tests de FTP), rangés par semaine et par jour, avec le suivi de ce qui a été fait d'après l'historique des séances. Comme GoldenCheetah, OpenRide gère une **bibliothèque d'entraînements** dans un dossier ; un plan n'est qu'une liste ordonnée de ces entraînements. On peut aussi importer un dossier d'entraînements numérotés (forme habituelle des plans téléchargés) comme un plan.

L'écran du menu (choisir un plan, voir la séance du jour, la lancer) est le lot O12.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_H8_outils_entrainements.md`, `docs/lots/LOT_L7_historique_seances.md`, `docs/lots/LOT_O9_formats_erg_mrc.md`, `docs/lots/LOT_O10_test_ftp.md`.
2. Code : `core/src/openride_core/workout.py` (`list_workouts`, `workout_path`), `core/src/openride_core/tools/workouts.py` (`estimate_metrics` : durée, IF, TSS), `core/src/openride_core/tools/history.py`, `core/src/openride_core/config.py` (dossiers).

## 3. Prérequis

O9 fusionné (formats lus). O10 pour les jours « test de FTP » (sinon ces jours sont refusés avec un message clair et le lot le note).

## 4. Travail demandé

- **Format de plan** (`~/OpenRide/Plans/<id>.toml`, documenté dans un nouveau `docs/contracts/plan_format_v1.md`) :
  ```toml
  [plan]
  name = "Construire sa FTP en 6 semaines"
  description = "..."
  days_per_week = 3
  [[week]]
  focus = "Endurance"
  days = [
    { day = "mardi",   workout = "endurance_45" },
    { day = "jeudi",   workout = "sweet_spot_3x10" },
    { day = "samedi",  workout = "ftp_test:ramp" },
  ]
  ```
  `workout` est un identifiant de la bibliothèque (`~/OpenRide/Workouts/`) ou `ftp_test:ramp` / `ftp_test:20min` ; `day` est un jour de la semaine ou `jour1` à `jour7` (plan sans calendrier).
- Nouveau module `core/src/openride_core/plans.py` :
  - `load_plan`, `list_plans` (plans invalides listés avec leur erreur, comme les entraînements) ;
  - `start_plan(id, start_date)` et `stop_plan()` : plan actif et date de début gardés dans `~/OpenRide/plan_state.toml` (hors du dépôt) ;
  - `today(state, history)` : séance du jour, séances en retard, semaine en cours, pourcentage fait ; une séance est **faite** si une séance de l'historique du même jour (ou rattrapée dans les 3 jours) porte le même entraînement et a duré au moins 80 % de sa durée prévue ;
  - `plan_summary(plan, ftp_w)` : durée et TSS par semaine (`estimate_metrics`).
- **Import d'un dossier** : `openride-core plan import DOSSIER --name NOM --days mardi,jeudi,samedi` copie les entraînements dans la bibliothèque (préfixés par l'identifiant du plan pour éviter les conflits) et écrit le `.toml`, dans l'ordre naturel des noms (`w1d1`, `w1d2`, …, `semaine 10` après `semaine 9`).
- Le journal de séance note l'identifiant de l'entraînement (déjà le cas avec `--workout` : à vérifier) et, s'il y a un plan actif, la semaine et le jour (champ facultatif ; format v1 toujours lisible).
- Commandes : `openride-core plan list|show ID|start ID [--date AAAA-MM-JJ]|stop|today|import`.
- Deux plans de référence écrits pour le projet dans `core/plans/` (par exemple « Reprise 4 semaines » et « FTP 6 semaines »), faits des `.zwo` de `core/workouts/` (à compléter si besoin), installés par `plan install`.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/plans.py`, `core/tests/test_plans.py`, `docs/contracts/plan_format_v1.md`, `core/plans/*.toml`, éventuels `.zwo` de référence.
- **Modifiés :** `core/src/openride_core/__main__.py`, `core/src/openride_core/config.py` (dossier `PLANS_DIR`), `journal.py` (champ facultatif), `tools/history.py` (colonne « plan » facultative), `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** l'engine, le contrat IPC (O12), `workout.py` (lecture seule).

## 6. Modifications de contrat autorisées

Aucune (nouveau format de fichier `plan_format_v1.md`, propre à ce lot).

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Plan de 2 semaines, date de début fixée, historique simulé : `today` donne la bonne séance un mardi, signale une séance en retard, compte une séance rattrapée le lendemain, ne compte pas une séance arrêtée à 50 %.
3. Plan qui cite un entraînement absent ou invalide : plan listé avec l'erreur, `start` refusé.
4. `plan import` sur un dossier de 12 `.zwo` nommés `w1d1` à `w4d3` : plan de 4 semaines à 3 jours, ordre juste, entraînements copiés sans écraser ceux de l'utilisateur.
5. `plan show` : durée et TSS par semaine cohérents avec `workouts list`.
6. Les deux plans de référence passent `plan show` et `workouts check`.

**Sur le PC cible (le propriétaire) :** démarrer un plan, rouler la séance du jour, vérifier qu'elle est comptée le lendemain.

## 8. Hors périmètre

- Plans adaptatifs (séances recalculées selon la forme) et calendrier synchronisé avec un service en ligne.
- Écran du menu (lot O12).

## 9. Livraison

Livré le 26 octobre 2026 (issue #155), thread « Développer les lots O restants ».

- `core/src/openride_core/plans.py` : `load_plan`, `list_plans`, `schedule`, `today`, `plan_summary`, `start_plan`, `stop_plan`, `load_state`, `plan_tag`, `active_tag`, `history_sessions`, `import_folder`, `install_builtin` ; `config.PLANS_DIR`.
- Format : `docs/contracts/plan_format_v1.md`. Semaine 1 = semaine du lundi au dimanche qui contient la date de début (séances antérieures au début omises) ; `jourN` compté depuis la date de début. Jours au calendrier et `jourN` ne se mélangent pas.
- Suivi : une séance de l'historique ne valide qu'une seule séance prévue ; « en retard » distingue `catch_up` (encore rattrapable, 3 jours) des séances manquées.
- Journal : champ facultatif `plan` = `{id, week, day}` dans l'en-tête quand l'entraînement choisi est celui du jour ou une séance rattrapable du plan actif (`session.py`, une ligne, via `active_tag` qui ne lève jamais). `recorder.py` et `journal.py` le transmettent. `history` : clés `workout` et `plan` (de l'en-tête du journal, et pour un `.fit`, du journal de la même séance) et mention du plan dans le texte ; entrées en cache sans ces clés recalculées.
- Tests de FTP (`ftp_test:ramp`, `ftp_test:20min`) : acceptés dès que le module `ftp_test` du lot O10 existe (`planned_duration_s`, `workout_for`), refusés avant avec « test de FTP pas encore disponible (lot O10) ». Les plans de référence utilisent donc `rampe_test.zwo` pour leurs tests.
- `plan import` : identifiant du plan normalisé depuis `--name`, entraînements copiés sous `<id>_<nom>` ; un fichier de même nom au contenu différent fait refuser l'import avant toute copie.
- Plans de référence : `core/plans/reprise_4_semaines.toml`, `core/plans/ftp_6_semaines.toml` (entraînements de `core/workouts/`, aucun ajouté).
- Tests : `core/tests/test_plans.py` (critères 2 à 6, journal, historique, ligne de commande) ; `test_history.py` attend les deux nouvelles clés.
