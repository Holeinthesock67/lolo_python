# Lot Q4 – Rampe de pente plus rapide, surtout à la descente

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Rampe de pente plus rapide, vitesses distinctes à la montée et à la descente | Python | Q1 (`session.py`) | Petite | Livré le 27 octobre (PR #194) |

## 1. Objectif

Essai du 25 octobre, marches 0 / 7 % : le core met 4 à 5 s pour passer d'une pente à l'autre (`grade_rate_pct_per_s` = 2 %/s), en partie compensés par l'anticipation de 0,8 s (`latency_tau_s`). Le trainer ajoute ensuite son propre retard, surtout quand la pente baisse. Ce lot rend la rampe du core plus rapide, avec une vitesse distincte pour la montée et la descente de la pente envoyée, pour que le core ne s'ajoute plus au retard du trainer.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/SRS_v1.1.md` §5 (pente envoyée).
2. Code : `core/src/openride_core/session.py` (calcul de `target`, `max_delta`, `_grade_sent`, envoi immédiat au changement de braquet), `config.py` (`TrainerConfig`, bornes `_BOUNDS`), `gearing.py`, `mock_driver.py`, `sim_scenarios.py`, `tools/run_mock_session.py`.

## 3. Prérequis

Aucun. `session.py` est aussi modifié par Q1 : faire Q1 et Q4 l'un après l'autre. Utile mais pas obligatoire : Q3 d'abord, pour mesurer avant et après sur le trainer.

## 4. Travail demandé

- Deux réglages dans `[trainer]` :
  - `grade_rate_up_pct_per_s`, défaut 4,0 : vitesse maximale quand la pente envoyée augmente ;
  - `grade_rate_down_pct_per_s`, défaut 8,0 : vitesse maximale quand elle diminue ;
  - bornes 0,1 à 100, comme l'actuel.
- `grade_rate_pct_per_s` reste accepté : s'il est présent dans `config.toml` et que les nouveaux réglages manquent, il sert pour les deux sens, avec un avertissement au journal (« réglage remplacé par … »).
- `session.py` choisit la vitesse selon le signe de `target − _grade_sent`. Le changement de braquet reste immédiat (inchangé).
- Le reste du calcul ne change pas : anticipation, bornes de pente, envoi.
- Une ligne du journal au démarrage donne les deux vitesses.
- `README.md` (réglages du trainer) à jour.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/session.py` (sélection de la vitesse seulement), `config.py` ; `README.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `core/tests/test_grade_ramp.py`.
- **Interdits :** `ftms_driver.py`, `gearing.py`, `physics.py`, l'engine, le contrat IPC.

## 6. Modifications de contrat autorisées

Aucune (le format de `config.toml` gagne deux clés, l'ancienne reste lue).

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Séance simulée (`--trainer mock`), braquet fixe, marche de pente 0 → 7 % : `grade_sent` monte à 4 %/s ± 5 % (durée de la rampe = écart de pente effective / 4, ± 0,1 s) ; marche 7 → 0 % : descend à 8 %/s ± 5 %.
3. Ancienne configuration avec `grade_rate_pct_per_s = 2` seule : comportement identique à aujourd'hui, avertissement présent.
4. Valeurs hors bornes refusées par la validation de la configuration, avec le message habituel.
5. Changement de braquet : envoi immédiat inchangé (test existant toujours vert).

**Sur le PC cible (le propriétaire) :** rouler les marches 0 / 7 % d'`essai-69` (si possible avec la trace de Q3) et dire si le relâchement est plus rapide ; essayer aussi 2 / 4 %/s pour comparer.

## 8. Hors périmètre

- Le retard propre au trainer (volant, régulation interne) : on ne peut que le mesurer (Q3).
- Changement de `latency_tau_s` ou de la formule des braquets.

## Livraison

PR #194, fusionnée le 27 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Oui ; issue #171 ».
