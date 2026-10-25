# Lot P12 – Éoliennes, drapeaux et eau qui scintille

## 1. Objectif

Trois objets qui montrent le vent et la lumière, à faible coût :
- **éoliennes** tirées d'OpenStreetMap, dont le rotor tourne selon la force du vent et s'oriente face à lui ;
- **drapeaux** aux mâts OSM et, à défaut, un ou deux par village, qui flottent dans le sens du vent ;
- **eau qui scintille** : reflets du soleil animés sur les rivières et les lacs d'E4.

Le compilateur produit les deux nouvelles sortes de points d'intérêt (`wind_turbine`, `flag`) ajoutées au format par P1.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_P1_contrat_vent_decor.md` §4.5, `docs/lots/LOT_I4_osm_poi_eau.md`, `docs/lots/LOT_L2_maillage_eau.md`, `docs/lots/LOT_P4_modele_vent_engine.md`.
2. Code : `compiler/src/openride_compiler/osm_layers.py` (classement des points d'intérêt), `compiler/src/openride_compiler/osm.py` (requête Overpass), `engine/scripts/water_mesh.gd` (matériau de l'eau), `engine/scripts/osm_layers.gd`.

## 3. Prérequis

P1 et P4 livrés. Version 1.0 publiée.

## 4. Travail demandé

- **Compilateur :** `power=generator` avec `generator:source=wind` donne `wind_turbine` (avec `height_m` d'après `height` ou 100 m par défaut) ; `man_made=flagpole` donne `flag` ; requête Overpass complétée ; tests sur des données OSM de démonstration fictives (pas de coordonnées réelles).
- **Engine, éoliennes :** nouveau `engine/scripts/wind_turbines.gd` : mât, nacelle et trois pales construits par code ; rotor à `5 + 12 × strength` tr/min (arrêt sous 10 km/h), nacelle orientée face au vent avec un lissage de 20 s ; visibles de loin (jusqu'à la portée de vue, LOD simple au-delà de 2 km) ; au plus 20 actives.
- **Engine, drapeaux :** nouveau `engine/scripts/flags.gd` : mât et tissu (petit maillage déformé par shader selon vent et rafale) ; points `flag`, et un drapeau près des points `village` qui n'en ont pas (déterministe).
- **Eau :** dans `water_mesh.gd`, option `shimmer` du matériau : reflets spéculaires animés (bruit qui défile avec le vent), actifs seulement si `living(preset).water_shimmer` ; sans l'option, rendu identique à aujourd'hui.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/wind_turbines.gd`, `engine/scripts/flags.gd`, `engine/shaders/flag.gdshader`, `engine/shaders/water_shimmer.gdshader`, `engine/tests/unit/test_wind_turbines.gd`, `engine/tests/unit/test_flags.gd`.
- **Modifiés :** `compiler/src/openride_compiler/osm_layers.py`, `compiler/src/openride_compiler/osm.py`, tests du compilateur concernés, `engine/scripts/water_mesh.gd` (matériau), `engine/scripts/osm_layers.gd` (sortes acceptées), `engine/tests/unit/test_water_mesh.gd`, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `osm_streamer.gd` (branchement par P17), le core, le contrat (fait par P1).

## 6. Modifications de contrat autorisées

Aucune (P1).

## 7. Critères d'acceptation

1. `(cd compiler && pytest -q)` et `engine/tests/run_engine_tests.sh` passent en entier.
2. Compilateur : une éolienne et un mât fictifs donnent `wind_turbine` (hauteur lue ou 100 m) et `flag`, valides pour `poi.schema.json` ; un générateur solaire n'est pas retenu.
3. Éolienne : vitesse du rotor croissante avec la force du vent, nulle sous 10 km/h ; après un changement de direction de 90°, nacelle face au vent en 60 s au plus, sans à-coup.
4. Drapeau : tissu orienté vers où souffle le vent (± 15°) ; un drapeau par village sans mât OSM, au même endroit à chaque chargement.
5. Eau sans `shimmer` : test de rendu et références visuelles inchangés.
6. Mise à jour par image sous 0,2 ms pour 20 éoliennes et 30 drapeaux.

**Sur le PC cible (le propriétaire) :** parcours compilé avec des éoliennes : rotors qui tournent avec le vent de P2 ; eau qui scintille sans clignotement ; perte de moins de 1 image/s.

## 8. Hors périmètre

- Ombre portée animée des pales, bruit des éoliennes, vagues.
