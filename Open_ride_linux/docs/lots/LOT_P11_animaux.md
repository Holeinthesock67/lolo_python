# Lot P11 – Animaux : oiseaux en vol, bétail dans les prés, chevreuil en lisière

## 1. Objectif

Peupler le paysage de quelques animaux simples et peu coûteux :
- des bandes d'oiseaux qui tournent au-dessus des forêts et s'écartent quand on approche ;
- des vaches ou des moutons qui paissent près des points `livestock` déjà produits par le compilateur ;
- de temps en temps, un chevreuil en lisière de forêt qui relève la tête puis s'enfuit.

Les formes sont basses en polygones, animées par le shader (battement d'ailes, tête qui monte et descend), en nombre borné par `living(preset)`.

## 2. À lire

1. `docs/lots/00_INDEX.md` (budget de la série P), `docs/lots/LOT_P4_modele_vent_engine.md` (`living`), `docs/lots/LOT_K3_placement_vegetation.md` (placement déterministe), `docs/lots/LOT_K4_lecture_couches_osm_godot.md`.
2. Code : `engine/scripts/vegetation_placer.gd`, `engine/scripts/osm_layers.gd`, `engine/scripts/osm_streamer.gd`, `engine/scripts/tree_renderer.gd` (`MultiMesh`, LOD).

## 3. Prérequis

P4 livré. Version 1.0 publiée.

## 4. Travail demandé

- Nouveau modèle pur `engine/scripts/fauna_placer.gd` :
  - `place_chunk(chunk_index, vegetation_areas, pois, route, density) -> Array` : troupeaux de 3 à 12 bêtes autour des points `livestock` (hors route, eau, bâtiments, pente au-dessus de 25 %), bandes d'oiseaux (5 à 15) au-dessus des forêts, sites de chevreuil en lisière (au plus un tous les 3 km) ; déterministe par tronçon ;
  - densités `fauna` du thème 1.2.
- Nouveau modèle `engine/scripts/fauna_behaviour.gd` : trajectoire des oiseaux (cercles lents et ondulés, écart quand le cycliste passe à moins de 40 m), bétail quasi immobile (rotation lente, pas de déplacement sur la route), chevreuil : immobile, puis fuite vers la forêt quand le cycliste est à moins de 60 m, puis disparition.
- Nouveau nœud `engine/scripts/fauna_renderer.gd` : un `MultiMesh` par espèce, maillages construits par code (aucun fichier externe), animation par shader à partir d'un temps global ; nombre borné par `living(preset).birds` et `.animals`, les plus proches en priorité.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/fauna_placer.gd`, `engine/scripts/fauna_behaviour.gd`, `engine/scripts/fauna_renderer.gd`, `engine/shaders/fauna.gdshader`, `engine/tests/unit/test_fauna_placer.gd`, `engine/tests/unit/test_fauna_behaviour.gd`.
- **Modifiés :** `engine/tests/README.md`, `docs/SUIVI_AVANCEMENT.md` (une ligne).
- **Interdits :** `main.gd`, `osm_streamer.gd` (branchement par P17), le compilateur, le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Placement déterministe (même tronçon, même résultat) ; aucune bête sur la route (à moins de 4 m de l'axe), l'eau ou un bâtiment ; aucun oiseau sous 15 m au-dessus du sol.
3. Pas de point `livestock` : aucun bétail ; densité `fauna.deer = 0` : aucun chevreuil.
4. Chevreuil : passe de « immobile » à « fuite » quand le cycliste est à 59 m, s'éloigne de la route, disparaît en moins de 6 s.
5. Jamais plus d'instances que le budget ; avec 200 candidats, ce sont les plus proches de la caméra qui restent.
6. Mise à jour de tous les animaux sous 0,3 ms par image (mesure du test, 200 animaux).

**Sur le PC cible (le propriétaire) :** séance en `low` sur un parcours avec prés et forêts : animaux visibles, ni volants ni enterrés ; perte de moins de 1 image/s.

## 8. Hors périmètre

- Sons des animaux autres que la sonnaille existante et les oiseaux de P9, animaux qui traversent la route, collisions.
