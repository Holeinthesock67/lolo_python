# Pack de biomes CC0 : recette

**Lot U15, série U (3.0).** Ce document dit comment fabriquer un pack de textures libres pour les sols des biomes du premier jalon (U-Q5).

Le thème par défaut reste en couleurs unies. Le pack, lui, reste hors du dépôt : on l'installe avec `theme-install`.

## 1. Sources et licence

- [ambientCG](https://ambientcg.com/) et [Poly Haven](https://polyhaven.com/) publient toutes leurs textures sous licence **CC0 1.0** : usage libre, même commercial, sans attribution obligatoire ([licence ambientCG](https://docs.ambientcg.com/license/)).
- Pour chaque texture, prendre la version **2K JPG**, avec la couleur (albedo) et la normale au format OpenGL. Le préréglage `high` affiche du 2 048 px au plus ; `low` et `medium` affichent du 1 024 px (`QualityPresets.ground_texture_px`).
- La provenance va dans le pack, dans `PROVENANCE.md` : nom de l'asset, adresse de la page, licence, date du téléchargement.

## 2. Textures conseillées, sol par sol

Le **rôle** dit où la couche s'affiche : `flat` sur le plat, `steep` dans les pentes, `high` en altitude. Les couches sont celles du thème par défaut (`engine/themes/default/theme.json`, `biomes.<id>.ground.layers`).

| Biome | Couche (rôle) | Texture conseillée | Page |
| --- | --- | --- | --- |
| `temperate_grassland` | herbe (flat) | Grass 001 (ambientCG) | <https://ambientcg.com/view?id=Grass001> |
| `temperate_grassland` | roche (steep) | Rock 026 (ambientCG) | <https://ambientcg.com/view?id=Rock026> |
| `temperate_grassland` | neige (high) | Snow 006 (ambientCG) | <https://ambientcg.com/view?id=Snow006> |
| `temperate_forest` | litière et mousse (flat) | Forest Leaves 04 (Poly Haven) | <https://polyhaven.com/a/forest_leaves_04> |
| `temperate_forest` | roche (steep) | Rock 023 (ambientCG) | <https://ambientcg.com/view?id=Rock023> |
| `temperate_forest` | neige (high) | Snow 006 (ambientCG) | <https://ambientcg.com/view?id=Snow006> |
| `farmland` | champs et chaumes (flat) | Grass Ground (Poly Haven) | <https://polyhaven.com/a/grass_ground> |
| `farmland` | talus (steep) | Ground 079 S (ambientCG) | <https://ambientcg.com/view?id=Ground079S> |
| `alpine` | herbe du parcours de démonstration (flat) | Grass 001 (ambientCG), comme la prairie | <https://ambientcg.com/view?id=Grass001> |
| `alpine` | roche du parcours de démonstration (steep) | Rock 026 (ambientCG), comme la prairie | <https://ambientcg.com/view?id=Rock026> |
| `alpine` | neige du parcours de démonstration (high) | Snow 006 (ambientCG), comme la prairie | <https://ambientcg.com/view?id=Snow006> |
| `mediterranean` | terre ocre et garrigue (flat) | Dry Ground 01 (Poly Haven) | <https://polyhaven.com/a/dry_ground_01> |
| `mediterranean` | calcaire (steep) | Rock 017 (ambientCG), pierre gris clair | <https://ambientcg.com/view?id=Rock017> |
| `coast` | sable et oyats (flat) | Coast Sand 02 (Poly Haven) | <https://polyhaven.com/a/coast_sand_02> |
| `coast` | falaise (steep) | Rock 060 (ambientCG) | <https://ambientcg.com/view?id=Rock060> |

Ce sont des propositions. Si une texture paraît trop sombre ou trop saturée sur la GTX 1060, la remplacer par une voisine de la même page de catégorie. La `color` de la couche reste la teinte de repli et sert au lointain.

Choix de départ pour les biomes lointains (désert, savane, jungle, polaire, volcanique), à confirmer à la recette U18 :
- [Sand 03](https://polyhaven.com/a/sand_03) pour le sable ;
- [Cracked Red Ground](https://polyhaven.com/a/cracked_red_ground) pour la savane ;
- [Leaves Forest Ground](https://polyhaven.com/a/leaves_forest_ground) pour la jungle.

## 3. Fabriquer le pack

1. Copier le thème par défaut :
   ```
   mkdir -p ~/OpenRide/Packs/biomes-cc0
   cp engine/themes/default/theme.json ~/OpenRide/Packs/biomes-cc0/
   ```
2. Ranger les images dans `textures/<biome>/`, par exemple :
   - `textures/temperate_grassland/herbe_albedo.jpg` ;
   - `textures/temperate_grassland/herbe_normal.jpg`.
3. Dans `theme.json`, changer `name` (par exemple « Biomes CC0 »). Pour chaque couche du tableau, remplir :
   - `texture` (albedo) et `normal`, en chemins relatifs au dossier du pack ;
   - `scale_m` : taille réelle couverte par l'image, donnée sur la page de l'asset (2 m pour Gravel 033, par exemple).
4. Écrire `PROVENANCE.md` (§1).
5. Contrôler le pack, puis en faire une archive :
   ```
   openride-compiler theme-check ~/OpenRide/Packs/biomes-cc0
   cd ~/OpenRide/Packs && zip -r biomes-cc0.zip biomes-cc0
   ```
   `theme-check` vérifie le schéma 2.0, les images et la taille.
6. Les niveaux de résolution par préréglage (`texture_levels`) viendront avec le lot P20. D'ici là, le pack donne une seule taille et l'engine la réduit si le préréglage le demande.

## 4. Installer et retirer

- Archive locale :
  ```
  openride-compiler theme-install ~/OpenRide/Packs/biomes-cc0.zip
  ```
- Archive publiée sur un serveur à soi :
  ```
  openride-compiler theme-install https://exemple.org/biomes-cc0.zip
  ```
  Seul HTTPS est accepté. L'archive est contrôlée en entier par `theme-check` avant toute copie. Sans réseau, le refus est clair. L'installation ne se fait jamais pendant une séance.
- Le pack va dans `~/OpenRide/Themes/biomes-cc0/`. Il s'utilise avec `[render] theme = "biomes-cc0"`, ou au menu Réglages.
- `openride-compiler theme-list` donne la taille et la dernière utilisation de chaque pack. Le lanceur date le thème choisi au début de chaque séance (`~/OpenRide/Themes/.utilisation.json`).
- La bibliothèque est plafonnée à `[render] theme_library_gb`, 5 Go par défaut (de 1 à 50). Au-delà, `theme-install` retire les packs utilisés le moins récemment et le dit. Il ne retire jamais le thème choisi, le thème intégré, ni le pack qu'il vient d'installer.
