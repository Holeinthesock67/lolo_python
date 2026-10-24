# Lot M7 – Compilateur : parcours depuis un fichier FIT ou TCX

## 1. Objectif

Le compilateur ne lit que le GPX. Les sorties de Laurent sont enregistrées par une montre Garmin : Garmin Connect exporte l'activité d'origine en FIT (ou TCX), et les parcours (« courses ») se téléchargent aussi en FIT. Ce lot permet `openride-compiler build sortie.fit` et `build sortie.tcx`, avec le même traitement que pour un GPX.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_B1_compilateur_route.md` (livraison), `docs/contracts/world_format_v1.md` (la sortie ne change pas).
2. Formats :
   - FIT : messages `record` (champs `position_lat`, `position_long` en semi-cercles, `enhanced_altitude` ou `altitude`), aussi présents dans un fichier de parcours (`course`) ;
   - TCX : `Trackpoint` avec `Position/LatitudeDegrees`, `LongitudeDegrees`, `AltitudeMeters` (activité) ou `Course/Track` (parcours).
3. Code : `compiler/src/openride_compiler/gpx.py` (`GpxPoint`, lecture et erreurs), `compiler/src/openride_compiler/cli.py` (`build`), `compiler/src/openride_compiler/errors.py`, `core/src/openride_core/replay.py` (lecture d'un FIT avec `fit-tool`, exemple à suivre).

## 3. Prérequis

Aucun.

## 4. Travail demandé

- Nouveau module `compiler/src/openride_compiler/track_formats.py` :
  - `read_track(path) -> list[GpxPoint]` qui choisit le lecteur d'après l'extension (`.gpx`, `.fit`, `.tcx`, insensible à la casse) et, pour une extension inconnue, d'après les premiers octets (en-tête FIT `.FIT`, XML `TrainingCenterDatabase` ou `gpx`) ;
  - FIT : semi-cercles convertis en degrés (`× 180 / 2³¹`), `enhanced_altitude` préférée à `altitude`, points sans position ignorés (début d'activité sans GPS, tunnel) ; un FIT sans aucune position (séance sur home trainer) donne une `CompileError` claire : « aucune position GPS dans ce FIT » ;
  - TCX : bibliothèque standard (`xml.etree`), espaces de noms ignorés comme dans `gpx.py`, plusieurs `Lap` mis bout à bout ;
  - points consécutifs identiques fusionnés, comme pour le GPX.
- `build` accepte ces formats (l'argument s'appelle toujours `gpx` pour ne rien casser ; l'aide dit « GPX, FIT ou TCX ») ; le nom par défaut du parcours vient du nom du fichier, comme aujourd'hui.
- Dépendance : `fit-tool` (déjà utilisée par le core, même contrainte de version que `constraints.txt`) ajoutée à `compiler/pyproject.toml`.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/track_formats.py`, `compiler/tests/test_track_formats.py`.
- **Modifiés :** `compiler/src/openride_compiler/cli.py` (lecture par `read_track` dans `build`), `compiler/pyproject.toml` (section `dependencies`), `constraints.txt` (seulement si `fit-tool` n'y est pas), `README.md` (exemple), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `gpx.py` et `pipeline.py` (lecture seule), le core, le format `.world`. `list` et `build-all` continuent de ne voir que les `.gpx` (la liste des parcours vient d'une logique partagée avec le core, lot J6).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `compiler/` et dans `core/`.
2. Une même trace (le GPX de démonstration des tests) écrite en FIT (par `fit-tool`, dans le test) et en TCX (écrit à la main) donne un `.world` dont `route.json` est identique à celui du GPX, à 1 cm et 0,01 % près.
3. FIT dont les 30 premiers points n'ont pas de position : ignorés, compilation réussie.
4. FIT sans position : `CompileError` avec le message du §4 et code de sortie 2 de `build` (comme les autres erreurs de compilation).
5. Fichier `.fit` qui est en fait un GPX, et fichier sans extension : reconnus par leur contenu.
6. TCX de parcours (`Course`) et TCX d'activité à deux tours : lus.

**Sur le PC cible (Laurent) :** compiler une vraie sortie exportée de Garmin Connect (FIT d'origine) et la rouler.

## 8. Hors périmètre

- `list` et `build-all` sur les FIT et TCX (demande un changement du catalogue partagé : lot à part).
- Lecture de la puissance, de la fréquence cardiaque ou du temps de l'activité (fantôme : SRS §14).
- Fichiers FIT compressés (`.fit.gz`) : à signaler si Garmin Connect les produit.

## 9. Livraison (24 octobre 2026)

- `track_formats.py` : `read_track(path)` lit GPX, FIT et TCX. Le contenu prime sur l'extension (en-tête « .FIT », `TrainingCenterDatabase`, `<gpx`) ; l'extension ne sert que si le contenu n'est pas reconnu, ce qui couvre à la fois le `.fit` qui est un GPX et le fichier sans extension (critère 5). `cmd_build` appelle `read_track` ; `gpx.py` et `pipeline.py` inchangés.
- FIT : `fit-tool` rend déjà `position_lat`/`position_long` en degrés ; une valeur hors de ± 180 (encore en semi-cercles) serait convertie par × 180 / 2³¹. `enhanced_altitude` préférée à `altitude`. Points sans position ignorés ; aucun → « aucune position GPS dans ce FIT ».
- TCX : `xml.etree`, espaces de noms ignorés, `Trackpoint` pris dans l'ordre du document (tours d'une activité bout à bout, `Track` d'un `Course`). Points consécutifs identiques fusionnés (FIT et TCX).
- `compiler/pyproject.toml` : `fit-tool>=0.9` (même contrainte que le core ; `constraints.txt` fixe déjà 0.9.16).
- Écart avec le critère 4 : le code de sortie est **1** et non 2. Dans `errors.py`, toute `CompileError` (trace invalide ou trop courte) sort en 1 (`EXIT_INPUT`) et 2 est réservé aux erreurs internes ; le FIT sans position suit donc « les autres erreurs de compilation », comme le demande le critère.
- Critère 2 : `test_fit_gives_same_route_as_gpx` et `test_tcx_gives_same_route_as_gpx` comparent tout `route.json` à 1 cm ou 0,01 % près. La trace de test a ses altitudes arrondies à 0,2 m (résolution de l'altitude FIT) ; les caps sont comparés modulo 360° (plein nord : 0 et 359,99).
- `compiler/tests/test_track_formats.py` : 17 tests ; compilateur 171 tests (au lieu de 154).
