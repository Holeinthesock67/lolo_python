# Lot PP1 – Courbe de puissance du profil sur 6 mois et 6 semaines

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Courbe de puissance du profil (13 durées, 6 mois et 6 semaines, libre ou ERG) | Python | R16, MJ1 | Moyenne | PR ouverte le 21 novembre (série PP, 6.0) |

## 1. Objectif

Premier lot de la série PP (`docs/6.0/PLAN_SERIE_PP.md`, cadrage validé le 21 novembre) : calculer, pour le profil de joueur en cours, la meilleure puissance moyenne de 13 durées sur les 6 derniers mois et les 6 dernières semaines, en disant pour chaque point si l'effort était libre ou imposé par l'ERG. Ni écran ni contrat IPC : l'écran « Ma puissance » est le lot PP3 (révision 1.29), la FTP estimée le lot PP2.

## 2. À lire

`docs/6.0/PLAN_SERIE_PP.md` §2, §3.1, §3.2, §3.4 et §10 ; code : `tools/estimate_cp.py` (R16), `tools/history.py` (lecture des séances), `tools/session_summary.py` (`load_session`), `journal.py` (sortes de lignes), `profiles.py` (`current()`, `counted_sources`, `mmp_cache`).

## 3. Travail demandé

- Durées : 5 s, 15 s, 30 s, 1, 2, 3, 5, 8, 12, 20, 30, 45 et 60 min. Fenêtres : 183 jours (« 6 derniers mois ») et 42 jours (« 6 dernières semaines »).
- Une fenêtre de calcul ne traverse jamais une pause, une coupure du trainer (`device` `trainer` `down` puis `up`) ni un trou de plus de 2 s : la séance est découpée en morceaux continus. Corrige le défaut de R16, qui recollait les relevés hors pause (un « meilleur 20 min » pouvait cacher une pause).
- Pics de capteur : relevé de plus de 2 000 W, ou pic isolé (plus de 1 000 W et plus de 3 fois ses deux voisins), remplacé par le relevé précédent. Relevé sans puissance : coupure.
- Séances comptées : sources du profil (`live` ; le profil d'essai garde `simulated`), jamais un rejeu ; FIT lu seulement quand son journal manque (compté `live`, effort « inconnu »).
- Chaque point : watts, date, séance (fichier, parcours, entraînement), effort « libre » ou « ERG » (relevé avec `target_w` ou `mode` ERG), et le meilleur effort libre de la durée à part (`free`) : la FTP estimée de PP2 ne lira que lui (décision Q1).
- Cache par séance, version 2, à l'emplacement du cache de R16 (`Profils/<id>/.cache/mmp.json`), qui est remplacé : `estimate_cp` lit désormais ses meilleures puissances dans ce cache commun. Écriture atomique ; entrées des fichiers disparus retirées. Les lignes `ftp_test` de la séance y sont gardées pour PP2.
- Outil `python -m openride_core.tools.power_curve` (texte et `--json`, `--dir`, `--sources`).

## 4. Critères d'acceptation

1. `(cd core && pytest -q)` passe ; `core/tests/test_power_curve.py` couvre : 13 durées et deux fenêtres, pause, coupure du trainer, trou, pics, vrai sprint gardé, ERG et courbe libre, séance mixte, sources et rejeux, FIT de secours, cache version 2 (cache de R16 ignoré, aucun recalcul au deuxième appel), profil en cours et profil d'essai, outil.
2. Séances fabriquées seulement (modèle à 250 W), aucune donnée réelle dans le dépôt.
3. Calcul d'une séance d'une heure : une vingtaine de millisecondes mesurées (borne du test : 0,5 s, pour la CI) ; jamais dans la boucle à 50 Hz (rien n'appelle l'outil depuis la séance dans ce lot).

## 5. Hors périmètre

Écran et contrat (PP3), FTP estimée et proposition au menu (PP2), records au bilan (PP4). Le code de la proposition de W' de Cyber-Rogue reste en place tant que R25 (#956, jauge W' retirée) n'est pas fusionné ; il lit déjà le nouveau cache.

## 6. Livraison

- **Créés :** `core/src/openride_core/tools/power_curve.py`, `core/tests/test_power_curve.py`, `docs/6.0/PLAN_SERIE_PP.md`, ce cahier.
- **Modifiés :** `core/src/openride_core/tools/estimate_cp.py` (cache commun, `mmp` délégué à `power_curve.best_means`), `README.md`, `CLAUDE.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne chacun).
- Recette PC : catégorie logique (fumée + medium), après l'essai du 22 novembre.
