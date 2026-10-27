# Lot O15 – Bibliothèque de parcours : fiches, tri, filtres et packs de parcours

## 1. Objectif

Aujourd'hui, la liste des parcours ne donne que le nom, le statut, la longueur et le type. Pour choisir comme dans une bibliothèque (« un col de 10 km », « une boucle plate d'une heure »), il faut une **fiche par parcours** (distance, dénivelé positif, pente maximale, montée principale, région, étiquettes, difficulté), le **tri et les filtres**, et de quoi **installer des packs de parcours** préparés (un dossier ou un `.zip` de traces avec leurs fiches), comme les packs de thèmes de N10. L'écran de la bibliothèque dans le menu est le lot O12.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_I2_catalogue_parcours.md`, `docs/lots/LOT_J6_parite_catalogue.md`, `docs/lots/LOT_N10_packs_themes.md` (même forme d'installation), `docs/lots/LOT_O5_traces_garmin_dossier.md`, `docs/contracts/world_format_v1.md` (manifeste, couche route).
2. Code : `core/src/openride_core/catalog.py`, `core/src/openride_core/route.py` (altitudes, pentes), `compiler/src/openride_compiler/cli.py` (`build`, `list`, `build-all`, `fallback_catalog`), `engine/scripts/hud_view_model.gd` (détection de la prochaine montée, à reprendre côté Python si utile).

## 3. Prérequis

O5 fusionné (il est seul à modifier `catalog.py` avant ce lot).

## 4. Travail demandé

- **Fiche calculée** (`core/src/openride_core/route_stats.py`, utilisée par le catalogue et par le repli du compilateur, parité vérifiée) : distance, dénivelé positif et négatif (altitudes lissées, seuil de 1 m pour ne pas compter le bruit), altitude min et max, pente max sur 100 m, montée principale (longueur, dénivelé, pente moyenne, catégorie 4 à HC selon un barème documenté), durée estimée à 200 W et à la FTP de la configuration, difficulté 1 à 5. Calculée à la compilation et rangée dans le manifeste (`stats`, champ facultatif) ; recalculée à la lecture pour un `.world` ancien qui n'en a pas.
- **Fiche saisie** (facultative) : fichier `<trace>.toml` à côté du GPX (ou dans un pack) : `name`, `description`, `region` (texte libre, jamais de coordonnées), `tags` (liste : `col`, `plat`, `boucle`, `classique`…), `credits`. Copiée dans le manifeste (`library`, champ facultatif) à la compilation.
- **Tri et filtres** : `catalog.query(routes, sort=..., filters=...)` (distance, dénivelé, pente max, durée estimée, difficulté, étiquette, région, statut) ; `openride-compiler list --sort deniv --tag col --min-km 10 --max-km 40 [--json]`.
- **Packs** : `openride-compiler route-pack-install SOURCE [--name NOM] [--force]` : dossier ou `.zip` contenant des traces (GPX, FIT, TCX) et leurs fiches `.toml`, plus un `pack.toml` (nom, description, licence, crédits) ; contrôles comme N10 (chemins sûrs, taille maximale, fiches valides), copie dans `~/OpenRide/GPX/<pack>/` puis compilation par `build-all` (sous-dossiers à prendre en compte par le catalogue) ; `route-pack-list`.
- **Pack d'exemple** fabriqué par les tests (traces synthétiques) ; le contenu d'un vrai pack de départ (cols célèbres, parcours régionaux) et sa source (traces de l'utilisateur, traces sous licence libre) sont une décision du propriétaire, hors de ce lot.
- Documentation : `docs/contracts/world_format_v1.md` (champs facultatifs `stats` et `library`, compatibles), `README.md`.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/route_stats.py`, `compiler/src/openride_compiler/route_pack.py`, tests associés.
- **Modifiés :** `core/src/openride_core/catalog.py`, `compiler/src/openride_compiler/cli.py`, `docs/contracts/world_format_v1.md`, `docs/contracts/world/*.schema.json` (champs facultatifs), `README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** l'engine, le contrat IPC (les nouveaux champs passeront au menu par O12), `launcher.py`. Aucune trace réelle dans le dépôt.

## 6. Modifications de contrat autorisées

Format `.world` : champs **facultatifs** `stats` et `library` dans le manifeste ; un `.world` sans eux reste valide et lisible par l'engine actuel.

## 7. Critères d'acceptation

1. `pytest -q` passe en entier dans `core/` et `compiler/`, parité du catalogue comprise.
2. Trace synthétique connue (montée de 10 km à 7 % puis plat) : dénivelé, pente max, montée principale et catégorie justes (tolérances écrites dans le test).
3. `.world` compilé avant ce lot : fiche recalculée à la lecture, aucun avertissement de schéma.
4. `list --tag col --sort deniv` : ordre et filtre justes, `--json` stable.
5. Pack `.zip` d'exemple avec 3 traces et fiches : installé, compilé, listé avec ses étiquettes ; pack avec chemin `../` ou fiche invalide refusé sans rien écrire.
6. Aucune coordonnée ni trace réelle dans les fichiers ajoutés (recherche dans la PR).

**Sur le PC cible (le propriétaire) :** installer un pack de ses propres traces et vérifier les fiches.

## 8. Hors périmètre

- Téléchargement de parcours depuis un service en ligne ; écran du menu (O12).

## 9. Livraison

Livré le 26 octobre 2026 (issue #157), thread « Développer les lots O restants ».

- `core/src/openride_core/route_stats.py`, copié tel quel dans `compiler/src/openride_compiler/route_stats.py` (égalité des deux fichiers testée) : `compute_stats` (barème en tête du module et dans `docs/contracts/world_format_v1.md` §2), `duration_at` (durée à la FTP, interpolée dans `durations_s`, 100 à 400 W par pas de 25 W), `load_library` (fiche `<trace>.toml`, coordonnées refusées dans `region`), `query` (tri `nom`, `distance`, `deniv`, `pente`, `duree`, `difficulte`, croissant ou `reverse` ; filtres étiquette, région, statut, distance, dénivelé, pente, durée, difficulté). `catalog.query` est ce même `query`.
- Catalogue (core et repli du compilateur, parité testée par la situation `library`) : `RouteEntry` et `CatalogEntry` gagnent `stats` et `library` (défaut `None`) ; les traces sont aussi lues dans les sous-dossiers directs de `~/OpenRide/GPX/` (packs) ; la fiche saisie est lue à côté de la trace, sinon dans le manifeste ; une fiche invalide est ignorée avec un avertissement.
- Compilateur : `build` range `stats` et `library` dans le manifeste (schéma `manifest.schema.json` complété, champs facultatifs) ; `list` gagne `--sort`, `--reverse`, `--tag`, `--region`, `--status`, `--min-km`, `--max-km`, `--max-difficulty`, `--ftp`, `--json` (clés triées, sortie stable) et les colonnes D+, pente, difficulté et durée ; `route-pack-install` et `route-pack-list` (`compiler/src/openride_compiler/route_pack.py` : tout est contrôlé avant d'écrire, remplacement par `--force` sans perte de l'ancien pack en cas d'échec).
- Tests : `core/tests/test_route_stats.py` (critère 2 : 10 km à 7 % puis plat), `compiler/tests/test_route_library.py` (critères 4 et 5 : pack `.zip` de 3 traces synthétiques, refus `../`, fiche invalide, lien, fichier inconnu, taille), situation `library` de `compiler/tests/test_catalog_parity.py` (critère 3 : `.world` sans `stats`).
- Hors de ce lot : l'écran de la bibliothèque (O12) et le contenu d'un vrai pack (O16).
