# Lot X12 – Analyse automatique d'une séance réelle

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Analyse automatique d'une séance réelle (`openride-core session-report`) | Python | — | Moyenne | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x12`), essai sur le journal de la prochaine séance vélo ; issue #210 |

## 1. Objectif

Le bilan de l'essai 69 a été fait à la main (médianes par section de pente, pente envoyée, braquet, cadence). Chaque essai sur le vélo, dont la séance T11/J7, demande ce travail. Ce lot produit le rapport automatiquement, **en local** : le journal et le FIT du propriétaire ne quittent jamais le PC.

## 2. À lire

`core/src/openride_core/journal.py` (sortes de lignes), `session_summary.py` (`openride-core summary`), `tools/log_report.py`, `route.py` (pente du parcours à la distance), `/mnt/project-files/essais/BILAN_ESSAI_69_2026-10-25.md` (modèle du bilan manuel).

## 3. Travail demandé

- **`openride-core session-report [JOURNAL.jsonl|FIT] [--log run_trainer.log] [--engine-log …] [--out DOSSIER]`** (dernière séance par défaut) :
  - découpage du parcours en sections de pente homogène (changement de plus de 1,5 point, longueur minimale 200 m) ; par section : longueur, pente du parcours, pente envoyée médiane, braquet le plus utilisé, puissance, cadence et vitesse médianes, FC ;
  - **retard pente → effort** : à chaque marche de pente de plus de 3 points, temps pour que la puissance (à cadence tenue) atteigne 63 % de son nouveau palier ;
  - ERG : écart à la cible par bloc (médiane, p90), temps hors de ± 5 % ;
  - coupures et silences (`log_report`), appuis du Click par boîtier, images/s (ligne `[perf-rendu]` du journal de l'engine si fourni) ;
  - lignes `segment` et `powerup` (série T) : temps de chaque montée et sprint, bonus pris.
- Sortie : `rapport.html` (tableaux et courbes SVG, sans dépendance), `sections.csv`, `resume.json`, dans `~/OpenRide/rapports/<séance>/`.

## 4. Fichiers

- **Nouveaux :** `core/src/openride_core/tools/session_report.py`, `core/tests/test_session_report.py` (journaux fabriqués : montée à 7 %, ERG à paliers, coupure).
- **Modifiés :** `__main__.py` (sous-commande), `README.md`, `CLAUDE.md`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Sur un journal fabriqué avec une marche de pente connue et une réponse du 1er ordre de 10 s, le retard mesuré est de 10 ± 1 s.
2. Le rapport se lit sans réseau ; aucun chemin personnel n'est écrit dans le dépôt.

## 6. Hors périmètre

Le conseil d'entraînement.

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x12`).

- `core/src/openride_core/tools/session_report.py` et sous-commande `openride-core session-report` ; définitions en tête du module.
- Sections : coupure dès que la pente s'écarte de plus de 1,5 point de la moyenne de la section, puis une section de moins de 200 m rejoint sa voisine de pente la plus proche (une bosse de 45 m reste dans son plat). Pente tirée de l'altitude sur 50 m pour un FIT.
- Retard pente → effort : palier d'avant = médiane des 10 s avant la marche, nouveau palier = médiane de 30 à 60 s après, puissance lissée sur 3 s centrées ; marche notée sans retard si la cadence tombe à 0 ou si les paliers diffèrent de moins de 20 W.
- `--log` passe par `log_report` (coupures du trainer et du Click, appuis par boîtier, pauses) ; `--engine-log` lit les lignes `[perf-rendu]`.
- `core/tests/test_session_report.py` (7 tests) : réponse du 1er ordre de 10 s → retard mesuré 10 s ; sections plat et montée ; ERG à paliers ; coupure, segment et bonus ; rapport sans ressource en ligne.
- Essai : journal du banc simulé (`sim_bench --scenario nominal`) avec `core.log` et `engine.log` ; calcul d'un journal de 3 h en 0,2 s.
- Reste sur le PC : lancer l'outil sur le journal de la prochaine séance vélo et comparer au bilan manuel de l'essai 69.
