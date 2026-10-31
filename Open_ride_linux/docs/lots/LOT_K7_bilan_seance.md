# Lot K7 – Bilan de séance `openride-core summary`

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Bilan de séance `openride-core summary` (NP, IF, TSS, zones) | Python | — | Petite | **Livré le 23 octobre** (fait directement ; cahier rédigé le 24 octobre) |

Cahier rédigé après coup (vérification du 24 octobre, constat S1) : le lot a été fait directement le 23 octobre, sans cahier préalable. Il décrit ce qui a été livré, pour que l'index des lots reste complet.

## 1. Objectif

Donner, après une séance, un bilan chiffré lisible sans application externe : `openride-core summary [FICHIER] [--ftp W] [--json]`, à partir du journal `.jsonl` ou du fichier `.fit` de la séance.

## 2. À lire

1. `docs/SRS_v1.1.md` (journal de séance, FIT, entraînements ERG §6).
2. Code : `core/src/openride_core/journal.py`, `core/src/openride_core/replay.py` (lecture `.jsonl` et `.fit`), `core/src/openride_core/tools/workouts.py` (NP, IF, TSS estimés), `core/src/openride_core/__main__.py`.

## 3. Prérequis

Aucun.

## 4. Travail demandé

- Sans fichier : bilan du dernier journal ; FTP donnée par `--ftp` ou lue dans `config.toml`.
- Chiffres : durée hors pauses, distance, dénivelé positif lissé, puissance moyenne et normalisée, IF, TSS, temps par zone de Coggan, meilleures puissances de 5 s à 20 min, cadence et fréquence cardiaque (0 bpm = pas de mesure), puissance par bloc ERG.
- Un `.jsonl` et le `.fit` de la même séance donnent les mêmes chiffres.
- Sortie texte, ou `--json` aux clés stables.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tools/session_summary.py`, `core/tests/test_session_summary.py`.
- **Modifiés :** `core/src/openride_core/__main__.py` (sous-commande `summary`), `core/tests/test_docs_coherence.py`, `README.md`, `CLAUDE.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune (le format du journal v1 ne change pas).

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. NP vérifiée sur un signal carré calculé à la main ; 200 W constants pendant 1 h donnent IF et TSS attendus.
3. Mêmes chiffres en `.jsonl` et en `.fit` ; pauses exclues ; FTP nulle ou négative refusée.

## 8. Hors périmètre

- Écart à la cible ERG : la cible n'est pas dans le journal v1 (évolution du format à prévoir).

## 9. Livraison (23 octobre 2026, fait directement, commit `4fb8d0a`)

- `session_summary.py` livré et branché sur `openride-core summary`.
- Tests : `core/tests/test_session_summary.py`, 13 tests (200 W pendant 1 h, NP sur signal carré, parité `.jsonl`/`.fit`, pauses et enregistrements pendant une pause, dénivelé et séance courte, FC à 0 et roue libre, blocs ERG sans cible, clés `--json`, sortie texte et erreurs, FTP de la configuration, séance simulée de 10 min en moins de 1 s, NP sur série courte).
- Écart assumé : l'écart à la cible ERG est signalé indisponible (cible absente du journal v1).
