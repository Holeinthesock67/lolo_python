# Lot O9 – Entraînements au format GoldenCheetah : `.erg` et `.mrc`

## 1. Objectif

Le propriétaire veut utiliser ses entraînements et ses plans « de la même manière que GoldenCheetah ». GoldenCheetah lit, en plus des `.zwo` de Zwift, les fichiers texte `.erg` (cibles en watts) et `.mrc` (cibles en % de la FTP), très répandus (TrainerRoad, ErgDB, exports de GoldenCheetah lui-même). OpenRide ne lit que les `.zwo`. Ce lot ajoute la lecture des `.erg` et des `.mrc`, avec le même comportement que les `.zwo` dans la séance, la liste et les outils.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_F_erg_zwo.md`, `docs/lots/LOT_H8_outils_entrainements.md`, `docs/SRS_v1.1.md` §6.
2. Code : `core/src/openride_core/workout.py` (`Block`, `Workout`, `parse_workout`, `load_workout`, `list_workouts`, `workout_path`, `ErgController`), `core/src/openride_core/tools/workouts.py`, `core/tests/test_workout*.py`.

## 3. Prérequis

Aucun. Indépendant de l'engine et du contrat.

## 4. Travail demandé

- **Format** (celui de GoldenCheetah, insensible à la casse et aux fins de ligne Windows) :
  ```text
  [COURSE HEADER]
  VERSION = 2
  UNITS = ENGLISH
  DESCRIPTION = Sweet spot 3 x 10
  FILE NAME = sweet_spot.erg
  FTP = 250                 (facultatif, .erg seulement)
  MINUTES WATTS             (.erg)   ou   MINUTES PERCENT   (.mrc)
  [END COURSE HEADER]
  [COURSE DATA]
  0.00    100
  10.00   100
  10.00   200
  ...
  [END COURSE DATA]
  [COURSE TEXT]             (facultatif : temps en secondes, texte, durée)
  ```
  Les points sont reliés en ligne droite : deux points de même temps font une marche, deux valeurs différentes font une rampe. Séparateurs : espaces ou tabulations. Autres clés d'en-tête : ignorées avec un message au niveau DEBUG.
- **Conversion en blocs** (`parse_erg(text, workout_id, source)` dans `workout.py` ou un nouveau `workout_formats.py`) : chaque segment devient un bloc `steady` (valeurs égales) ou `ramp`. Les `.mrc` donnent directement des fractions de FTP.
- **Cibles en watts des `.erg`** : ajouter au `Block` un mode absolu (cibles en watts, `start_w` / `end_w`) que `ErgController` applique **sans** multiplier par la FTP ; le biais du Click (± 2 %) s'applique comme pour les autres blocs. Option `--erg-relative` de `workouts install` (et paramètre de `parse_erg`) pour convertir un `.erg` en % à partir de sa clé `FTP` d'en-tête, pour qui préfère que l'entraînement suive sa FTP.
- **`COURSE TEXT`** : messages gardés dans le `Workout` (temps et texte), pour un affichage futur ; aucun changement du contrat.
- **Découverte** : `list_workouts`, `workout_path` et `tools/workouts.py` (`list`, `check`, `install`) acceptent `.zwo`, `.erg` et `.mrc` ; même identifiant sans extension ; conflit `x.zwo` / `x.erg` signalé, le `.zwo` gagne.
- Contrôles : temps décroissants, valeurs négatives, plus de 6 h, fichier vide ou sans `[COURSE DATA]` : erreur claire qui cite la ligne, le fichier figure dans la liste avec son erreur (comme un `.zwo` invalide).
- Ajouter à `core/workouts/` un `.erg` et un `.mrc` de référence écrits pour le projet (pas de fichier tiers).

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/workout.py`, `core/src/openride_core/tools/workouts.py`, tests des entraînements, `README.md` (formats acceptés), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Nouveaux :** au choix `core/src/openride_core/workout_formats.py`, `core/tests/test_workout_erg.py`, `core/workouts/*.erg`, `core/workouts/*.mrc`.
- **Interdits :** l'engine, le contrat IPC, `session.py` (sauf si l'appel du lecteur y est écrit en dur : le signaler).

## 6. Modifications de contrat autorisées

Aucune : l'objet `erg` du contrat porte déjà la cible en watts.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/`.
2. Un `.mrc` et un `.zwo` décrivant le même entraînement donnent la même cible à chaque seconde (à 1 W près, FTP 250 W).
3. Un `.erg` à 200 W donne 200 W quelle que soit la FTP ; converti avec `--erg-relative` (en-tête `FTP = 250`), il donne 80 % de la FTP.
4. Marches et rampes : cible juste au début, au milieu et à la fin de chaque segment.
5. Fichiers mal formés : un test par erreur, message avec le numéro de ligne, la séance refuse de démarrer avec `workout_invalid`.
6. Une séance simulée complète (`--trainer sim`) sur le `.erg` de référence produit un journal et un FIT valides.

**Sur le PC cible (le propriétaire) :** déposer un `.erg` exporté de GoldenCheetah dans `~/OpenRide/Workouts/` et le rouler.

## 8. Hors périmètre

- Formats `.crs`, `.pgmf` (parcours vidéo de GoldenCheetah) et entraînements TrainerRoad au format JSON.
