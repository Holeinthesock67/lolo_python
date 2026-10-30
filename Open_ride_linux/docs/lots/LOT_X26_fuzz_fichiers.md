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

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x26`).

- **`core/tests/test_fuzz_workouts.py`** : `.zwo` (blocs de toutes les sortes), `.erg` (en watts, avec ou sans conversion en % de la FTP de l'en-tête) et `.mrc`, puis `load_workout` sur des fichiers dans quatre encodages (UTF-8, avec BOM, Latin-1, UTF-16), tronqués ou non.
- **`compiler/tests/test_fuzz_tracks.py`** : `parse_gpx`, `parse_tcx`, `parse_fit` (FIT construit par `fit_tool`), puis `read_track` sur des fichiers nus, `.gz` et `.zip`.
- **Retouches** : une à trois par exemple. Pour le texte : troncature, morceau supprimé ou dupliqué jusqu'à 50 fois, nombre remplacé (vide, négatif, `1e309`, `nan`, `inf`, hors bornes, lettres, virgule décimale), balise retirée, caractères ou balises insérés. Pour les octets : troncature, octet retourné, morceau supprimé, dupliqué ou inséré.
- **Propriété** : résultat valide (blocs de durée finie et positive, cibles finies et positives, messages de durée finie ; points dans les bornes, altitude finie ou absente) ou exception documentée (`WorkoutError`, `CompileError`), en moins de 2 s. Bombe XML de type « milliards de rires » refusée en moins de 2 s ; entité externe jamais lue.
- **Profils** (`conftest.py` des deux suites) : `default` à 200 exemples, `long` à 5 000, sans base d'exemples et avec le dossier de travail d'hypothesis en dossier temporaire (garde-fou d'isolation). Marque `fuzz` ; `hypothesis` est dans l'extra `dev` du core et du compilateur, fixé à 6.170.13 dans `constraints.txt`. Sans lui, les tests sont sautés (`importorskip`).
- **Défauts trouvés et corrigés** (chacun avec son test de non-régression) :
  1. `.erg` / `.mrc`, section `[COURSE TEXT]` : `60 Allez 1e309` donnait un message de durée infinie (`nan`, négative ou nulle de même). La durée doit maintenant être un nombre fini et positif, sinon `WorkoutError` « durée du message invalide » ; un dernier mot non numérique reste du texte (`test_erg_text_duration_1e309`).
  2. `.zip` privé de son premier octet : `zipfile` levait `ValueError` (« negative seek value »). L'erreur est désormais rattrapée en « archive .zip corrompue » (`test_zip_without_first_byte`).
  3. GPX et TCX avec `encoding="UTF--1"` : `ElementTree` levait `LookupError`. `gpx.xml_root` est maintenant commun aux deux lecteurs et rend `CompileError` « illisible » (`test_unknown_xml_encoding_utf__1`). Le `.zwo` n'est pas touché, car il est décodé avant l'analyse XML (`test_zwo_unknown_encoding_utf__1`).
- **Mesuré au cloud** : profil `long` (5 000 exemples par lecteur) vert dans les deux suites après les corrections.
