# Lot U14 – Engine : variantes régionales des roches, terres et bâtiments

## 1. Objectif

**Version 3.0.** Appliquer la variante régionale de chaque tuile (U4) par-dessus le biome : couleur et texture des roches et des terres (grès rose, calcaire blanc, granite, schiste, basalte, latérite, craie), murs et toits des bâtiments OSM (tuiles rondes ocre, ardoise, tuiles plates, pierre sèche, toits plats blancs, bois), formes de toit qui vont avec (toits plats en zone aride, pentes fortes en montagne).

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §3, `docs/lots/LOT_U1_contrat_biomes.md` §4.3 et §4.5 (`variants`), `docs/lots/LOT_U4_variantes_regionales_compilateur.md`, `docs/lots/LOT_L1_maillage_batiments.md`.
2. Code : `engine/scripts/building_mesh.gd`, `engine/scripts/osm_streamer.gd`, `engine/shaders/terrain_biomes.gdshader` (U6), `engine/scripts/biome_model.gd` (U5).

## 3. Prérequis

U4 et U6 livrés.

## 4. Travail demandé

- Sol : la variante teinte la couche roche et la couche terre de chaque biome (`rock_color`, `soil_color`, textures facultatives de la variante, qui remplacent celles du biome).
- Bâtiments : couleurs `walls` et `roofs` tirées de la variante de la tuile au lieu du thème global ; forme du toit selon `roofs` (`toit_plat_blanc` → plat, `ardoise` → pente de 45°, `tuile_ronde` → pente de 25°), sauf si OSM donne `roof:shape`.
- Changement de variante entre deux tuiles : fondu des couleurs du sol sur 100 m ; bâtiments sans fondu (chaque bâtiment prend la variante de son centre).

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/building_mesh.gd`, `engine/scripts/osm_streamer.gd`, `engine/shaders/terrain_biomes.gdshader`, `engine/scripts/biome_model.gd`, leurs tests, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe.
2. Tuile `toit_plat_blanc` : bâtiments sans `roof:shape` à toit plat ; avec `roof:shape=gabled` : toit à deux pentes.
3. Tuile sans variante : couleurs du thème actuel (tests de L1 inchangés).
4. Rendu : roche de la variante `gres_rose` à teinte moyenne rose (à 10 % près de `rock_color`).

## 8. Hors périmètre

Bâtiments modélisés par région (églises, chalets), textures de façade.
