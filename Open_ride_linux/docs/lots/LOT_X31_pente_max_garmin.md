# Lot X31 – Pente maximale face à Garmin Connect

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
