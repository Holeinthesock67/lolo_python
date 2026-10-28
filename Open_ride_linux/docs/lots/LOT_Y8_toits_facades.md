# Lot Y8 – Habillage des bâtiments : toits à pans et façades

## 1. Objectif

Retour du propriétaire du 25 octobre : bâtiments sans texture et tous à toit plat. Priorités validées le 27 octobre (`docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §0, question 10) : toits à pans et façades texturées, puis étalonnage, puis marquages de route. Depuis, l'étalonnage est passé à l'étape 1 du cahier Y13 (PR #446) et les marquages de route à Y11 : Y8 garde **les toits et les façades**.

Ce lot :

- donne aux maisons un **toit à deux pans** (ou à quatre pans pour une empreinte presque carrée), choisi par l'engine d'après la forme de l'empreinte et l'étiquette OSM du bâtiment, sans changer le format `.world` ;
- dessine des **façades** par shader (fenêtres par étage, porte, soubassement, encadrements) plutôt que par géométrie, avec les couleurs du thème ;
- garde les bâtiments industriels, commerciaux et les grands immeubles en toit plat.

## 2. À lire

1. `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §6 (point 2) ; `docs/contracts/world_format_v1.md` §6 (bâtiments : `roof`, `hint`, `height_m`) ; `docs/lots/LOT_L1_maillage_batiments.md`, `LOT_E4_osm_eau_sons.md`, `LOT_P20_packs_textures_performance.md`, Y3.
2. Code : `engine/scripts/building_mesh.gd` (`gabled` lu mais dessiné à plat aujourd'hui, `gabled_as_flat`), `osm_streamer.gd` (matériaux des bâtiments), `theme_loader.gd`, `theme_render_params.gd` (couleurs `buildings.walls` et `buildings.roofs`), `quality_presets.gd`.

## 3. Prérequis

Y3 (blocs des villages au loin : ils restent à toit plat) et P20 (packs de textures par préréglage, pour l'option du §4.3) livrés.

## 4. Travail demandé

### 4.1 Toits (`building_mesh.gd`, sans nœud)

- **Choix du toit** pour un bâtiment sans trou, de 4 à 12 sommets : si `hint.building` vaut `house`, `detached`, `semidetached_house`, `farm`, `barn`, `church`, `chapel`, `garage` ou `yes`, si `height_m` ne dépasse pas 15 m et si l'empreinte tient dans son rectangle orienté minimal à 85 % au moins : toit à deux pans quand le rectangle fait plus de 1,3 fois sa largeur en longueur, sinon à quatre pans. Tout le reste (industriel, commercial, immeuble, empreinte complexe ou avec cour) garde le toit plat. Un `roof` « gabled » écrit par le compilateur (réservé par le format) est toujours respecté.
- **Géométrie** : faîtage le long du grand axe du rectangle orienté, pente de 35° (45° pour `church` et `chapel`), débord de 0,3 m ; pignons fermés par deux triangles de mur ; quatre pans : croupes à la même pente. Au plus 24 triangles de toit par maison. La hauteur du bâtiment reste celle du mur ; le toit s'y ajoute (au plus 6 m).
- Le compteur `gabled_as_flat` disparaît (plus aucun toit `gabled` dessiné à plat).

### 4.2 Façades (nouveau `engine/shaders/building_facade.gdshader`)

- Coordonnées de texture des murs écrites par `building_mesh.gd` : abscisse en mètres le long du mur, ordonnée en mètres depuis le sol.
- Shader : étages de 3 m, fenêtres de 1,2 × 1,4 m tous les 2,5 à 3,5 m (pas tiré du hachage de l'identifiant), volets ou encadrements selon le thème, porte au rez-de-chaussée sur le mur le plus proche de la route, soubassement plus sombre, légère salissure en bas ; aucun motif sur un mur de moins de 2 m. Vitres sombres avec un reflet du ciel bon marché (pas de SSR). Fenêtres coupées au-delà de 400 m (mur uni, même couleur moyenne) pour éviter le scintillement.
- Les couleurs restent celles du thème (`buildings.walls`, `buildings.roofs`) ; les tuiles du toit sont dessinées par le shader (rangées, teinte du thème).

### 4.3 Option textures

- Si un pack de textures (P20) fournit un atlas de façades et de tuiles pour le préréglage, le shader l'utilise à la place des motifs dessinés ; sans pack, les motifs du §4.2 suffisent. Une seule texture par village au plus.

### 4.4 Mesures

- Banc simulé avec la sonde X13, monde OSM avec villages, en `medium` puis `low` : coût du toit (triangles de plus) et du shader (temps GPU) ; enveloppe proposée : +0,5 ms de GPU en `medium`, +0,2 ms en `low`.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/building_mesh.gd`, `osm_streamer.gd` (matériau des bâtiments), `quality_presets.gd` (distance des fenêtres) ; `engine/tests/unit/test_building_mesh.gd`, `engine/tests/perf_budgets.json` (`building_mesh_500`) ; `docs/contracts/world_format_v1.md` (§6 : l'engine déduit le toit ; `gabled` toujours réservé) ; ce cahier, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Nouveaux :** `engine/shaders/building_facade.gdshader`, `engine/tests/render/test_building_facade_render.gd`.
- **Interdits :** le compilateur (le format ne change pas), le core, les blocs HLOD de Y3 (toit plat), les marquages de route (Y11).

## 6. Modifications de contrat autorisées

Aucune : le format `.world` ne change pas (le texte du §6 précise seulement que l'engine choisit le toit) ; le thème garde ses clés.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier ; `building_mesh_500` reste dans son budget.
2. Toits : une maison rectangulaire de 12 × 8 m a un toit à deux pans de faîtage parallèle à 12 m ; une maison de 9 × 9 m un toit à quatre pans ; un bâtiment `industrial` et une maison à cour restent plats ; aucun trou ni recouvrement entre toit et murs (sommets partagés à 1 mm près).
3. Façades : coordonnées de texture en mètres ; aucun motif sur un mur de 1,5 m ; capture de rendu d'une rue de test conforme (fenêtres alignées par étage, porte côté route).
4. Banc : enveloppe du §4.4 tenue, ou réduction (fenêtres plus tôt coupées, toits à deux pans seulement) notée dans ce cahier.

**Sur le PC cible (le propriétaire) :** traverser un village en `medium` : toits à pans, façades avec fenêtres, aucun scintillement au loin ; **avis du propriétaire** sur l'aspect.

## 8. Hors périmètre

- Toits lus dans OSM (`roof:shape`, orientation) : nécessiterait un changement du format (`roof_dir_deg`), à proposer à part ; bâtiments remarquables modélisés à la main.
- Étalonnage de l'image (Y13) ; marquages de route (Y11) ; variantes régionales des murs et des toits (U14, version 3.0) ; éclairage des fenêtres la nuit (P19, version 2.0).
