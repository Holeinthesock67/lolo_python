# Lot X26 – Fuzz des fichiers d'entrée

## 1. Objectif

Les fichiers `.zwo`, `.erg`, `.mrc`, GPX, FIT et TCX viennent d'ailleurs (GoldenCheetah, Garmin, internet). Le lot J2 ne couvre que l'IPC. Un fichier abîmé ne doit jamais faire planter le core ou le compilateur : toujours une erreur lisible.

## 2. À lire

`core/src/openride_core/workout.py` (lecteurs `.zwo`, `.erg`, `.mrc`), `compiler/src/openride_compiler/gpx.py`, `track_formats.py` (FIT, TCX), leurs exceptions documentées (`WorkoutError`, `CompilerError`…).

## 3. Travail demandé

- **Tests `hypothesis`** (extra `dev` du core et du compilateur, version bornée dans `constraints.txt`) :
  - fichiers valides générés puis abîmés (octets tronqués, balises supprimées, nombres hors bornes, encodages, attributs vides, XML entités) ;
  - propriété : la lecture rend un résultat valide ou lève **l'exception documentée** du module, jamais une autre (`KeyError`, `IndexError`, `ZeroDivisionError`, `RecursionError`…), et en moins de 2 s ;
  - XML : aucune entité externe ni expansion (bombe de milliards de rires) acceptée.
- Marque `fuzz` ; en CI, 200 exemples par lecteur ; `--hypothesis-profile=long` (5 000) sur le PC.
- Chaque plantage trouvé : corrigé dans le lecteur, avec un test de non-régression nommé d'après l'exemple.

## 4. Fichiers

- **Nouveaux :** `core/tests/test_fuzz_workouts.py`, `compiler/tests/test_fuzz_tracks.py`, `core/tests/conftest.py` et `compiler/tests/conftest.py` (profils hypothesis).
- **Modifiés :** lecteurs concernés si un défaut est trouvé, `core/pyproject.toml`, `compiler/pyproject.toml`, `constraints.txt`, `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Les suites passent avec 200 exemples par lecteur.
2. Les défauts trouvés sont listés dans la section Livraison avec leur correction.

## 6. Hors périmètre

Fuzz de l'IPC (J2).
