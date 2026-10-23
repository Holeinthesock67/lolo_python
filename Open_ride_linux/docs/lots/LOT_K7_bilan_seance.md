# Lot K7 – Bilan d'une séance : `openride-core summary`

## 1. Objectif

Après une séance, le propriétaire ouvre le FIT dans Garmin Connect ou GoldenCheetah pour voir ses chiffres. Une commande locale, hors ligne, donnerait tout de suite le bilan (et préparera l'écran de fin de séance du lot G) : durée, distance, dénivelé, puissance moyenne et normalisée, IF, TSS, temps par zone, meilleures puissances, et, en ERG, l'écart entre cible et puissance par bloc.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §6 (ERG), §9 (journal et FIT), §11 (FTP).
3. Code : `core/src/openride_core/journal.py` (lignes JSONL, champs `mode`, `block`), `fit_export.py` (`summarize`), `replay.py` (lecture d'un `.jsonl` ou d'un `.fit`), `tools/workouts.py` (calcul NP/IF/TSS d'un `.zwo`, à réutiliser), `tools/log_report.py` (style d'un outil avec `--json`).

## 3. Prérequis

Aucun. Partir de `main` à jour.

## 4. Travail demandé

- Nouveau `core/src/openride_core/tools/session_summary.py`, appelé par `openride-core summary [FICHIER] [--ftp W] [--json]` (sous-commande ajoutée à `__main__.py`) ; sans fichier : dernier journal (`journal.latest_journal`).
- Entrées : `.jsonl` (journal) ou `.fit` (par `replay.py`), même résultat pour la même séance.
- Calculs (définitions écrites en tête du module) :
  - durée de roulage (hors pauses), distance, dénivelé positif (altitude lissée sur 10 s, seuil 1 m) ;
  - puissance moyenne, puissance normalisée (moyenne glissante de 30 s, puissance 4, moyenne, racine 4), IF = NP / FTP, TSS = durée_h × IF² × 100 ;
  - temps par zone de Coggan (Z1 < 55 %, Z2 à 75 %, Z3 à 90 %, Z4 à 105 %, Z5 à 120 %, Z6 à 150 %, Z7 au-delà) ;
  - meilleures puissances sur 5 s, 1 min, 5 min, 20 min (absentes si la séance est plus courte) ;
  - cadence et fréquence cardiaque moyennes et maximales (FC à 0 ou absente ignorée) ;
  - en ERG : par bloc (`block`), puissance moyenne et écart à la cible quand le journal la contient ; sinon le signaler.
- FTP : `--ftp`, sinon `config.toml` (`ConfigError` lisible).

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tools/session_summary.py`, `core/tests/test_session_summary.py`, éventuellement `core/tests/data/sessions/*.jsonl` (petits fichiers synthétiques).
- **Modifiés :** `core/src/openride_core/__main__.py` (sous-commande), `README.md` et `CLAUDE.md` (commande), `docs/SUIVI_AVANCEMENT.md` (une ligne). J1 modifie aussi `__main__.py` : fusionner à la main si les deux sont en cours.

## 6. Modifications de contrat autorisées

Aucune. Si la cible ERG manque dans le journal, ne pas l'ajouter ici : le signaler (ajout possible au format du journal par un lot ultérieur).

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier.
2. Séance synthétique à puissance constante 200 W pendant 1 h avec FTP 250 : NP = 200 W à ± 1 W, IF 0,80, TSS 64 à ± 0,5, 100 % en Z3.
3. Séance 30 s à 400 W puis 30 s à 0 W, répétée 20 fois : NP supérieure à la moyenne et égale à la valeur calculée à la main dans le test (méthode écrite).
4. Même séance écrite en `.jsonl` et en `.fit` (par `fit_export.write_fit`) : mêmes chiffres à l'arrondi près.
5. Pauses : le temps de pause n'entre ni dans la durée ni dans NP.
6. `--json` : sortie valide, clés stables documentées dans le module.
7. Séance réelle anonymisée de `core/tests/data/` si elle existe, sinon séance de `MockDriver` de 10 minutes : la commande se termine en moins de 1 s.

## 8. Hors périmètre

- Écran de fin de séance dans l'engine (G).
- Historique, courbes de forme, service en ligne (hors périmètre du projet).
