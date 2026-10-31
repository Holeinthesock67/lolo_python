# Lot H8 – Outils et bibliothèque d'entraînements

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Outils et bibliothèque d'entraînements `.zwo` | Python | F (livré) | Petite | **Livré le 23 octobre** (PR #18) |

## 1. Objectif

En attendant le menu (lot G), permettre de préparer des séances ERG depuis le terminal :
- lister les entraînements de `~/OpenRide/Workouts/` et vérifier un fichier `.zwo` ;
- fournir une petite bibliothèque de `.zwo` de référence, à copier dans ce dossier.

## 2. À lire

1. `docs/lots/00_INDEX.md`.
2. `docs/SRS_v1.1.md` §6 (ERG et `.zwo`) et §11 (arborescence).
3. `docs/lots/LOT_F_erg_zwo.md` (lot livré, dont celui-ci réutilise le code).
4. Code : `core/src/openride_core/workout.py` (`load_workout`, `list_workouts`, `ErgController`, `WorkoutError`) ; `config.py` (`WORKOUTS_DIR`, `rider.ftp_w`).

## 3. Prérequis

Lot F livré (23 octobre). Partir de `main` à jour.

## 4. Travail demandé

### 4.1 Outil : `core/src/openride_core/tools/workouts.py` (nouveau)

Lancement : `python -m openride_core.tools.workouts <commande>`. Pas de nouvelle entrée dans `pyproject.toml` ni dans `__main__.py`, pour ne pas toucher aux fichiers d'autres lots.

| Commande | Effet |
| --- | --- |
| `list [--dir D]` | Tableau : identifiant, nom, durée (h:mm:ss), nombre de blocs, état (« ok » ou l'erreur). Utilise `list_workouts`. |
| `check FICHIER.zwo [--ftp W]` | Valide le fichier ; affiche les blocs (type, durée, cible de début et de fin en watts pour la FTP donnée, ou celle de `config.toml`), la durée totale, les avertissements de lecture. Code de sortie 1 si le fichier est invalide. |
| `install [--dir D]` | Copie la bibliothèque du §4.2 dans `~/OpenRide/Workouts/` (ou `D`), sans écraser un fichier existant ; dit ce qui a été copié et ce qui a été laissé. |

Le temps moyen pondéré (puissance normalisée approchée) et l'IF/TSS estimés pour la FTP donnée sont affichés par `check` : calcul simple, documenté dans le module (puissance moyenne par paliers de 1 s, sans lissage de 30 s si c'est plus simple, mais le dire).

### 4.2 Bibliothèque : `core/workouts/` (nouveau dossier)

Cinq `.zwo` écrits pour ce projet (pas de copie de fichiers Zwift), lisibles par `load_workout` sans aucun avertissement :

| Fichier | Contenu |
| --- | --- |
| `endurance_60.zwo` | 60 min : échauffement 10 min, 45 min à 65 %, retour au calme 5 min |
| `sweet_spot_3x10.zwo` | échauffement 10 min, 3 × 10 min à 90 % avec 5 min de récupération, retour au calme 5 min |
| `seuil_2x20.zwo` | échauffement 10 min, 2 × 20 min à 97 % avec 5 min de récupération, retour au calme 5 min |
| `vo2_5x3.zwo` | échauffement 10 min, 5 × 3 min à 115 % avec 3 min à 50 % (`IntervalsT`), retour au calme 5 min |
| `rampe_test.zwo` | test de rampe : 5 min à 40 %, puis paliers de 1 min de +6 % de 40 % à 148 % (`SteadyState` successifs) |

Les fichiers doivent être installés avec le paquet ou retrouvés depuis le module : préférer un chemin relatif au module ou `importlib.resources`, sans modifier `pyproject.toml` si possible ; sinon, le justifier.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/tools/workouts.py`, `core/workouts/*.zwo`, `core/tests/test_workout_tools.py`.
- **Modifiés :** `README.md` (section ERG : commandes), `docs/SUIVI_AVANCEMENT.md` (une ligne).

## 6. Modifications de contrat autorisées

Aucune. `workout.py` n'est pas modifié ; si un besoin apparaît, le signaler.

## 7. Critères d'acceptation

1. `cd core && pytest -q` passe en entier.
2. Les cinq fichiers de la bibliothèque se chargent sans avertissement, avec les durées attendues ; `endurance_60.zwo` dure exactement 3 600 s, et le test vérifie la durée de chaque fichier, calculée à partir de son contenu décrit au §4.2.
3. `check` sur le fichier de référence du lot F (texte `REFERENCE_ZWO` de `core/tests/test_workout.py`, écrit dans un fichier temporaire), FTP 250 W, affiche 10 blocs et 2 580 s ; sur un fichier invalide, il sort avec le code 1.
4. `install` dans un dossier temporaire copie les cinq fichiers ; une seconde exécution n'écrase rien.
5. `list` sur un dossier contenant un fichier invalide l'affiche avec son erreur.

## 8. Hors périmètre

- Menu de choix d'un entraînement (lot G), bandeau ERG dans l'engine (lot F2).
- Autres formats que `.zwo`.


## 9. Livraison (23 octobre 2026, PR #18)

- `core/src/openride_core/tools/workouts.py` : sous-commandes `list`, `check` (avec estimation Pmoy, NP par paliers de 1 s, IF et TSS) et `install` (copie sans écrasement dans `~/OpenRide/Workouts/`).
- `core/workouts/*.zwo` : 5 entraînements de référence (`endurance_60`, `sweet_spot_3x10`, `seuil_2x20`, `vo2_5x3`, `rampe_test`) lus sans avertissement.
- `core/tests/test_workout_tools.py` : 4 tests unitaires couvrant les 5 critères d'acceptation.
