# Lot O5 – Traces FIT, TCX et archives Garmin déposées dans le dossier des traces

## 1. Objectif

Le lot M7 permet `openride-compiler build sortie.fit`, mais le catalogue (`catalog.list_routes`, lot I2/J6) ne regarde que les fichiers `.gpx` de `~/OpenRide/GPX/`. Un FIT ou un TCX déposé dans ce dossier n'apparaît donc ni dans `build-all`, ni dans la compilation au lancement (N11), ni dans la liste du menu. Garmin Connect livre aussi parfois une archive (`.zip`) ou un FIT compressé (`.fit.gz`), que rien ne lit. Ce lot rend tous ces fichiers utilisables par simple dépôt dans le dossier.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_M7_compilateur_fit_tcx.md` (et sa « Livraison »), `docs/lots/LOT_I2_catalogue_parcours.md`, `docs/lots/LOT_J6_parite_catalogue.md`, `docs/lots/LOT_N11_compilation_au_lancement.md`.
2. Code : `core/src/openride_core/catalog.py`, `compiler/src/openride_compiler/cli.py` (`fallback_catalog`, `cmd_build_all`, `cmd_build`), `compiler/src/openride_compiler/track_formats.py` (`sniff_format`, `read_track`), `core/tests/test_catalog*.py`, `compiler/tests/test_catalog_parity.py`.

## 3. Prérequis

N11 fusionné (il appelle `build-all` au lancement ; ce lot ne touche pas `launcher.py`).

## 4. Travail demandé

- **Catalogue (core et repli du compilateur, mêmes règles, parité vérifiée par `test_catalog_parity.py`) :** les traces sont les fichiers `.gpx`, `.fit`, `.tcx`, `.fit.gz`, `.tcx.gz` et `.zip` du dossier (extension insensible à la casse). L'identifiant reste le nom normalisé sans extension(s) ; deux fichiers de même identifiant (`col.gpx` et `col.fit`) : le premier dans l'ordre `gpx`, `fit`, `tcx` gagne, l'autre est signalé en conflit, jamais compilé deux fois.
- Le SHA-256 enregistré dans le manifeste est celui **du fichier déposé** (archive comprise), pour que `outdated` fonctionne comme pour un GPX. Champ `source.gpx` du manifeste : nom du fichier déposé (champ inchangé, pas de modification du format `.world`).
- **Lecture des archives (`track_formats.py`) :** `.gz` décompressé en mémoire puis format reconnu par le contenu ; `.zip` : la première entrée `.fit`, `.tcx` ou `.gpx` (ordre alphabétique) est lue, les autres sont ignorées et listées dans le message ; archive vide, corrompue ou de plus de 50 Mo décompressés : erreur claire, sans plantage de `build-all`.
- `build` accepte aussi ces formats en ligne de commande.
- Documentation : `README.md` (déposer une sortie Garmin), aide de `build` et `list`.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/catalog.py`, `compiler/src/openride_compiler/cli.py`, `compiler/src/openride_compiler/track_formats.py`, tests du catalogue et des formats, `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Nouveaux :** fichiers de test **générés** par les tests (FIT et TCX fabriqués comme dans M7, compressés à la volée) : aucun fichier d'activité réel dans le dépôt.
- **Interdits :** `launcher.py`, l'engine, le format `.world`, tout fichier FIT/GPX/TCX réel (règle de confidentialité du dépôt).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et `compiler/`, parité du catalogue comprise.
2. Dossier temporaire avec `a.gpx`, `b.fit`, `c.tcx.gz`, `d.zip` (contenant un FIT) : `list` montre quatre traces `to_compile`, `build-all` produit quatre `.world`, un second `build-all` ne recompile rien.
3. Modifier `b.fit` : statut `outdated`, recompilé seul.
4. `col.gpx` et `col.fit` ensemble : un seul parcours, conflit signalé.
5. Archive corrompue, `.zip` sans trace, `.gz` trop gros : message clair, les autres traces sont compilées, code de sortie non nul seulement si une trace a échoué.
6. Aucun fichier d'activité réel ajouté (recherche dans la PR).

**Sur le PC cible (le propriétaire) :** déposer l'export Garmin d'une vraie sortie tel quel dans `~/OpenRide/GPX/`, cliquer sur l'icône, rouler le parcours.

## 8. Hors périmètre

- Téléchargement depuis Garmin Connect (service en ligne, hors périmètre du SRS).
- Lecture des fichiers `.fit` de séances OpenRide comme parcours (ils n'ont pas de GPS).

## 9. Livraison

Livré le 26 octobre 2026 (issue #122), thread « Développer les lots O restants ».

- Règles communes (`openride_core/catalog.py` et `openride_compiler/track_formats.py`, parité testée) : `TRACK_SUFFIXES` = `.gpx`, `.fit`, `.fit.gz`, `.tcx`, `.tcx.gz`, `.zip` dans l'ordre de priorité ; `track_stem` (nom sans extension) ; `scan_tracks` (une trace par identifiant, conflits `(écartée, retenue)`). L'ordre de priorité place chaque `.gz` juste après son format, puis `.zip` en dernier. Deux traces de même extension et de même identifiant (`Col.gpx` et `col.gpx`) sont aussi un conflit ; avant ce lot, elles donnaient deux entrées de même identifiant.
- Conflits : avertissement `catalog` au journal du core ; `list` et `build-all` les écrivent sur la sortie d'erreur (`conflit : col.fit ignoré, même parcours que col.gpx`). `RouteEntry` ne change pas.
- `read_track(path, notes)` : `.gz` (ou contenu gzip) décompressé en mémoire, `.zip` : première entrée `.fit`/`.tcx`/`.gpx` par ordre alphabétique, les autres citées dans `notes` ; vide, corrompue ou plus de 50 Mo décompressés : `CompileError`. `build` nomme le parcours sans les extensions (`Ma Sortie.tcx.gz` → `ma-sortie`).
- Manifeste : `source.gpx` = nom du fichier déposé, `source.gpx_sha256` = SHA-256 du fichier déposé (archive comprise) ; format `.world` inchangé.
- Tests : `compiler/tests/test_garmin_exports.py` (critères 2 à 6, traces fabriquées et compressées à la volée), situation `garmin` et règles de traces dans `test_catalog_parity.py`, `core/tests/test_catalog.py`. `launcher.py` n'a pas changé : la compilation au lancement passe par le catalogue.
