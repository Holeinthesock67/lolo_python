# Lot U2 – Compilateur : classification des biomes (WorldCover en cache, OSM, altitude, latitude) et option `--biome`

## 1. Objectif

**Version 3.0.** Écrire la couche `biome` du contrat U1 pour chaque parcours compilé : poids des biomes sur la grille 17 × 17 de chaque tuile, à partir de l'occupation du sol ESA WorldCover (10 m), des couches OSM, de l'altitude et d'une zone climatique approchée par la latitude ; ou un biome imposé à tout le parcours par `--biome`.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §6 et §9 (risques 2, 3 et 6), `docs/lots/LOT_U1_contrat_biomes.md` §4.1, `docs/lots/LOT_U0_decisions_biomes.md` (identifiants).
2. Code : `compiler/src/openride_compiler/terrain.py` (tuiles), `elevation.py` et `cache.py` (téléchargement et cache du MNT, à imiter), `osm.py` et `osm_layers.py` (client Overpass), `cli.py`, `writer.py`, `verify.py`.

## 3. Prérequis

U1 livré.

## 4. Travail demandé

- **Source WorldCover** (`landcover.py`, nouveau) : lecture par fenêtre des tuiles COG publiques d'ESA WorldCover 2021 (licence CC BY 4.0, attribution dans le manifeste), seulement l'emprise des tuiles du parcours, rangée dans `~/.cache/openride/landcover/` par carré de 0,1° ; même politique que le MNT : réseau à la compilation seulement, `--offline` refuse proprement si le cache manque, et repli sans WorldCover (OSM et altitude seules) avec un avertissement.
- **Classification** (`biomes.py`, nouveau, numpy, sans entrée-sortie) :
  - classes WorldCover → biomes candidats (arbres → forêt tempérée ou boréale selon la zone climatique, cultures → `farmland`, prairie → prairie ou steppe, sol nu → désert de sable ou de roche, neige et glace → `polar` ou `alpine`, zone humide → `wetland`, mangrove → `wetland`, eau → ignorée) ;
  - OSM corrige : `landuse=vineyard`, `farmland`, `orchard` → `farmland` ; `natural=sand`, `wetland`, `glacier`, `scrub`, `heath` ;
  - altitude : au-dessus d'un seuil qui dépend de la latitude (par exemple 1 800 m à 45°), part `alpine` croissante ;
  - zone climatique d'après la latitude seule (tropicale, aride, tempérée, boréale, polaire, en bandes) ; `mediterranean` pour les zones tempérées chaudes à végétation basse ;
  - lissage des poids (flou de 2 cases) et bruit de bord déterministe (graine tirée de `ix`, `iz`) pour éviter les frontières droites ; quatre biomes au plus par tuile (les plus forts, renormalisés à 255) ; bords partagés identiques entre tuiles voisines.
- **Option `--biome ID`** pour `build`, `build-all` et `add-layer biome` : un seul biome à 255 partout, `forced` renseigné dans le manifeste.
- **Rapport de compilation :** part de chaque biome sur le parcours (`shares`), affichée par `build` et écrite dans le manifeste.
- `verify` contrôle les tuiles de biome (présence, sommes, bords partagés).

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/landcover.py`, `compiler/src/openride_compiler/biomes.py`, `compiler/tests/test_landcover.py`, `compiler/tests/test_biomes.py`, petites grilles WorldCover de test générées par les tests.
- **Modifiés :** `compiler/src/openride_compiler/cli.py`, `writer.py`, `verify.py`, `pipeline.py` (appel de la couche), `README.md`, `CLAUDE.md` (modules du compilateur), `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** core, engine, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/`, réseau coupé ; les essais réels sont marqués `network`.
2. Grille de test « tout cultures » à 46° : biome `farmland` à plus de 90 % ; même grille avec `landuse=vineyard` sur un quart : `farmland` partout, mais `shares` cohérent.
3. Grille « arbres » à 46° : `temperate_forest` ; à 64° : `boreal_forest`.
4. Relief de test montant à 2 600 m à 45° : part `alpine` croissante avec l'altitude, nulle sous 1 500 m.
5. Tuiles voisines : poids identiques sur le bord commun ; somme 255 en chaque point ; au plus 4 biomes par tuile.
6. `--biome savanna` : tout le parcours à 255 en `savanna`, `forced` renseigné, aucun accès à WorldCover.
7. Cache absent et `--offline` : message clair, code de sortie non nul ; sans `--offline` et sans réseau : repli OSM et altitude, avertissement, parcours valide.
8. Même compilation deux fois : tuiles identiques au bit près.

## 8. Hors périmètre

Côte et mer (U3), variante régionale (U4), rendu (U5 et suivants), données de climat réelles (Köppen) : la latitude suffit pour la 3.0.
