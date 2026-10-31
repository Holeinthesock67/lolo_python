# Lot U9 – Engine : mer animée et plages

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : mer animée, écume et plages | GDScript + shader | U3, U6 | Moyenne | Oui, après U3 et U6, **version 3.0** (issue #339) |

## 1. Objectif

**Version 3.0.** Afficher la mer écrite par U3 : surface animée simple jusqu'à l'horizon, couleur selon le biome (turquoise sous les tropiques, gris-vert au nord), écume le long du rivage, plages de sable ou de galets, falaises.

## 2. À lire

1. `docs/3.0/PLAN_SERIE_U.md` §6, `docs/lots/LOT_U1_contrat_biomes.md` §4.2, `docs/lots/LOT_U3_cote_mer_plages.md`, `docs/lots/LOT_L2_maillage_eau.md`.
2. Code : `engine/scripts/water_mesh.gd`, `engine/scripts/osm_layers.gd`, `engine/scripts/osm_streamer.gd`, `engine/scripts/terrain_material.gd`.

## 3. Prérequis

U3 et U6 livrés.

## 4. Travail demandé

- Lecture de la sorte `sea` et de la couche `coast` dans `osm_layers.gd`.
- `engine/scripts/sea_mesh.gd` : maillage de la mer (polygones de U3, triangulés, trous des îles), prolongé par un grand plan jusqu'au brouillard lointain ; `engine/shaders/sea.gdshader` : vagues par somme de quelques ondes (normales seulement, pas de déplacement de plus de 0,3 m), fresnel, couleur d'après `water` du biome `coast` ou du biome dominant, écume dans une bande de 2 à 6 m le long du rivage `sand` et `shingle`, plus large au pied des falaises.
- Plages : couche de sol sable ou galets forcée dans la bande de plage (via U6).
- Son des vagues : réglage transmis au modèle d'ambiance (fait par U11 ; ici, seulement la distance au rivage exposée par `sea_mesh.gd`).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/sea_mesh.gd`, `engine/shaders/sea.gdshader`, `engine/tests/unit/test_sea_mesh.gd`, `engine/tests/render/test_sea_render.gd`.
- **Modifiés :** `engine/scripts/osm_layers.gd`, `engine/scripts/osm_streamer.gd`, tests existants de ces scripts, `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd` (U17), core, compilateur, contrats.

## 6. Modifications de contrat autorisées

Aucune (U1).

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Polygone de mer avec île : maillage sans triangle sur l'île.
3. Rendu : pixels de mer bleus ou verts (teinte moyenne attendue à 10 % près), écume visible au bord d'une plage de test, absente au large.
4. Parcours sans mer : aucun nœud créé, coût nul.
5. Coût par image mesuré au banc simulé et noté dans la PR.

## 8. Hors périmètre

Réflexions en temps réel, marées, bateaux.
