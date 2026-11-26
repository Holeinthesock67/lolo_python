# Lot PG1 : préparation des graphismes au premier lancement

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série AC (à-coups) : préparation des graphismes au premier lancement, catalogue des matériaux rejoué une doublure par image | GDScript, Python | AC6, BF1 | Moyenne | **En revue** (PR #1097) |

Décision du 26/11 (le user a choisi « les deux lots ») : une préparation unique au premier lancement, au lieu de
corriger les à-coups source par source. Le banc est traité à part (BF1, #1094). Analyse :
`statut/ACOUPS_CAUSE_GENERALE_2026-11-26.md` (dossier du projet). Empilé sur AC6 (#1066, `shader_warm.gd`).

## 1. Constat

- À cache vide, chaque couple nouveau shader + format de maillage compile ses pipelines. Sur la GTX 1060, cela
  prend 100 à 250 ms par pipeline, jusqu'à 0,7 s pour un seul. À chaud, les 71 pipelines du départ DB1 sortent du
  cache en 0,18 s.
- Essais au cloud (Godot 4.7.2, lavapipe, une boîte et un shader nouveau, lumière avec ombres) :

| Cas | Pipelines compilés |
| --- | --- |
| objet ajouté, visible | 6 |
| objet ajouté, caché | 1 |
| objet ajouté puis détaché du monde (`instance_set_scenario(RID())`) | 1 |

  La création d'un objet coûte donc déjà un pipeline par shader nouveau, qu'il soit caché ou détaché. Le premier
  dessin coûte le reste. Tant que les objets de tout le décor naissent dans la même image (décor vivant : 26
  shaders nouveaux à t = 31,9 s, pile c57b9746), retenir ou cacher ces objets ensuite ne suffit pas. Il faut que
  leurs shaders soient déjà passés **avant** leur création.

## 2. Principe

1. **Catalogue des matériaux** (`user://graphismes/catalogue.res` et compagnons). `shader_warm.gd` voit déjà
   chaque couple (shader, format de sommets, ombres) des tuiles, de l'OSM et du décor. Pour chaque couple, il
   garde une **recette de doublure** : le matériau (le shader par son chemin `res://` quand il en a un, sinon son
   code) et un maillage d'un triangle **au même format de sommets**, écrits avec `ResourceSaver`. Le catalogue
   grandit au fil des séances, et il est remis à jour à chaque séance. Il est le même pour toutes les cartes
   graphiques, donc un catalogue de départ peut être livré avec le jeu : un outil le produit au cloud en chargeant
   les parcours de démonstration, le monde ouvert simulé et les modes.
2. **Préparation au premier lancement.** Elle se lance quand la clé `version du jeu + version de Godot + nom de la
   carte graphique et du pilote` change (fichier `user://graphismes/prepare.json`), ou quand le cache de Godot est
   vide. Sur l'écran de chargement, avant le menu, chaque doublure du catalogue est **créée** dans une image,
   puis **dessinée** minuscule devant la caméra deux images plus tard, une à la fois. L'écran reste animé, avec une
   barre et le texte « Préparation des graphismes : première fois seulement (N sur M) ».
3. **Ensuite, tout est à chaud.** Les lancements suivants ne refont rien : la clé n'a pas changé, et le départ
   compile 0 pipeline. `shader_warm.gd` reste le filet de sécurité pour un couple absent du catalogue (il l'y
   ajoute pour la fois suivante).
4. **Export (J9).** `shader_baker/enabled = true` dans `export_presets.cfg` livrerait les shaders déjà traduits
   par Godot. Le banc PG1-0 du 26/11 (BF1, r1094) montre que cette part est petite : avec le cache du pilote plein
   et celui de Godot vide, le départ DB1 passe à 43 ms ; avec le cache de Godot plein et celui du pilote vide, il
   reste à 8,1 s. Le gain vient donc de la préparation, qui fait créer les pipelines du pilote un par image. Le
   shader baker reste un plus facultatif pour J9.

## 3. Étapes

| # | Étape | Où |
| --- | --- | --- |
| PG1-0 | **Fait le 26/11** (le pilote porte le coût, voir 2.4). Diagnostic : bancs DB1 medium `--shaders froid-pilote` et `--shaders froid-godot` (BF1-6), après un banc chaud de la même tête. Ils disent quelle part revient à Godot (traduction, que le shader baker supprime à l'export) et quelle part revient au pilote (que seule la préparation supprime). | PC |
| PG1-1 | Recettes de doublures dans `shader_warm.gd` (`recipe_of`), catalogue écrit en fin de chargement et en fin de séance, lu au lancement. Tests unitaires : recette au même format de sommets, matériau rechargé, shader par chemin. | cloud |
| PG1-2 | Écran « Préparation des graphismes » : clé de préparation, une création puis un dessin par image, barre et texte écrits. Pas de changement IPC : l'engine attend la fin avant d'envoyer `hello`. Si l'IPC doit changer (annonce au core), révision après 1.41. | cloud |
| PG1-3 | Outil `engine/tests/catalogue_graphismes.py` : catalogue de départ produit en chargeant les parcours de démonstration, le monde ouvert simulé et les modes. Le catalogue est livré dans `engine/data/graphismes/`. | cloud |
| PG1-4 | `shader_baker/enabled` dans `export_presets.cfg` (avec J9). | cloud |
| PG1-5 | Recette PC : `--shaders froid` DB1 low, medium et high, plus le monde ouvert ea1_lac medium. Critère BF1 : départ sous 1 s à froid, et sous 150 ms à chaud. | PC |

## 4. Hors lot

La ligue, le profil et la remise à zéro ne sont pas touchés. Le catalogue vit dans `user://` (dossier de
l'engine), pas dans le profil du joueur.

## 5. Critères d'acceptation

- Tests unitaires verts en CI.
- Recette PC à froid : la préparation dure moins de 90 s, l'écran reste animé (aucune image de plus de 1 s), puis
  le départ DB1 passe sous 150 ms dès la séance qui suit.

## 6. Livraison

- `engine/scripts/graphics_catalog.gd` : clés stables (shader par chemin ou par son code, matériau standard par ses
  options et ses emplacements de texture, format de sommets vu par le serveur de rendu, ombres), recette d'un
  triangle par surface au même format de sommets, matériaux aux textures de 4 × 4 pixels, écriture en `.scn`
  (quatre par image au plus), relecture du dossier livré puis de celui du joueur.
- `engine/scripts/shader_warm.gd` : chaque objet dessiné qui entre dans l'arbre (`node_added`, lu à l'image suivante)
  laisse sa recette au catalogue, en séance aussi ; `prime` met en file les doublures du catalogue ; `primed_left`,
  `primed_shown`.
- `engine/scripts/graphics_prep.gd` : clé `version du jeu | Godot | carte | API | pilote` dans
  `user://graphismes/prepare.json`, cache `user://shader_cache` vide ; barre et texte « Préparation des graphismes :
  première fois seulement (N sur M) » ; clé écrite seulement si tout est passé (séance partie avant : refaite au
  lancement suivant).
- `engine/scripts/engine_args.gd` : `--graphics-prep=on|off` (coupée avec `--test-mode` sauf demande, comme le
  garde-fou de charge), `--graphics-catalog-dir=CHEMIN`.
- `engine/tests/catalogue_graphismes.py` et `tour_visuel.py --engine-arg` : catalogue de départ.
- Tests : `test_graphics_catalog.gd`, `test_graphics_prep.gd`.
- Pas de changement IPC.

### Banc PC r1097 du 26/11 (pile 02bd9377 + #953 + #985 + #1066) et correctifs

- Constat : en low, medium et high, une seule image de 20,5 à 22,2 s (124 pipelines) à l'entrée de la première
  doublure, puis le parcours chargé à 56 s (« non chargé en 30 s »). Après la préparation, plus aucune image lente au
  départ ni pendant la séance (pire image 76 ms en medium) : le principe tient, la cadence non.
- Cause : les 49 doublures étaient chargées d'un coup ; leurs matériaux et maillages faisaient compiler tous leurs
  pipelines dans l'image suivante (reproduit en cloud : 67 pipelines dans une image juste après le chargement).
  Correctif : `GraphicsCatalog.list_paths` et `load_one`, `graphics_prep.gd` charge un fichier par image, le suivant
  quand la doublure d'avant est passée (la barre avance, au plus quelques pipelines par image).
- « Vertex amount (3) must be a multiple … (2) » : une doublure de lignes réduite à 3 sommets. Correctif :
  `tiny_mesh` garde 1, 2 ou 3 sommets selon la primitive ; la recette livrée fautive refaite (mêmes clés).
- Banc : le parcours attend la préparation au premier lancement ; `sim_bench.py` attend sa fin (ligne « Préparation
  des graphismes finie », 300 s au plus, notée à titre indicatif) avant ses 30 s de chargement.
- Hors PG1 : l'échec d'`ow-chaud` (images de 1 à 3,5 s au départ, cache par PR vide au premier passage « chaud »)
  vient du banc des menus, sans préparation (`--test-mode`) ; même défaut que celui corrigé par BF1 pour
  `sim_bench.py`.
