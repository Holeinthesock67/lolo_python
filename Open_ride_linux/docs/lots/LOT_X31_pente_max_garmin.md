# Lot X31 – Pente maximale face à Garmin Connect

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : Pente maximale et D+ face à Garmin Connect, en local | Python | — | Petite | **Livré le 28 octobre** (branche `claude/project-thread-818r6t-x31`) ; issue #229 |

## 1. Objectif

Ligne 22 de la recette 1.0 : la pente maximale d'un parcours compilé doit être à ± 1 point de celle de Garmin Connect sur une vraie trace de col.

## 2. À lire

`compiler/src/openride_compiler/route_stats.py`, `verify.py`, `cli.py`.

## 3. Travail demandé

- **`openride-compiler compare-garmin PARCOURS.world --pente-max P --dplus D [--longueur KM]`** : valeurs saisies par le propriétaire depuis Garmin Connect ; calcule la pente maximale du parcours sur la même fenêtre glissante que Garmin (100 m par défaut, `--fenetre`), le D+ et la longueur ; verdict OK si la pente est à ± 1 point, le D+ à ± 5 %, la longueur à ± 1 %. En local : rien n'est écrit dans le dépôt.

## 4. Fichiers

- **Nouveaux :** `compiler/tests/test_compare_garmin.py` (parcours fabriqué de pente connue).
- **Modifiés :** `route_stats.py`, `cli.py`, `README.md` (commandes), `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Sur une rampe fabriquée à 8 % de 500 m, pente maximale 8,0 ± 0,1 % ; un écart de 2 points donne ÉCHEC.

## 6. Hors périmètre

Changer le lissage du relief.

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x31`).

- **`route_stats.compare_garmin(route, pente, dplus, longueur, fenetre)`** : pente maximale par la fonction de la fiche (`max_grade`, fenêtre glissante de 100 m par défaut), D+ par `gain_loss` (hystérésis de 1 m, comme la fiche), longueur `length_m`. Tolérances : ± 1 point, ± 5 %, ± 1 %. Le module reste copié à l'identique dans le core (`test_catalog_parity`).
- **`openride-compiler compare-garmin PARCOURS.world --pente-max P --dplus D [--longueur KM] [--fenetre M] [--json]`** : contrôle le `.world` (`verify`), une ligne OK ou ÉCHEC par mesure, code 0 si tout est conforme, 1 sinon. Rien n'est écrit.
- **Tests** `compiler/tests/test_compare_garmin.py` (5 tests) : rampe fabriquée à 8 % sur 500 m (8,0 % ; 2 points d'écart donnent ÉCHEC), tolérances du D+ et de la longueur, effet de la fenêtre, commande sur un parcours compilé à 5 %.
- **Docs** : `README.md`, `docs/OUTILS_DE_TEST.md`, protocole F2, `SUIVI_AVANCEMENT.md`.
- **Reste sur le PC** : une vraie sortie avec un col (protocole F2).
