# Lot JP5 : végétation du Japon (version 6.0, série JP)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Espèces `sugi`, `hinoki`, `momiji`, `bamboo` au contrat du thème et dans l'engine ; biome `japan` du thème par défaut ; torii et lanternes des montées | GDScript, JSON | JP1 | Moyenne | En PR le 12 novembre, **version 6.0** |

Plan : `docs/6.0/PLAN_SERIE_JP.md`.

## Livraison

- Contrat du thème (ajout compatible, journal 1.8 de `docs/contracts/world_format_v1.md`) : quatre espèces de plus
  dans `vegetation.species[].kind` (schéma de référence et copie du compilateur).
- `engine/scripts/tree_species.gd` : maillages bas poly (moins de 300 triangles) et houppiers lointains (LOD 1 et
  forêts en imposteurs) :
  - `sugi`, cèdre du Japon : 26 m, fût roux, houppier étroit et pointu en trois étages ;
  - `hinoki`, cyprès hinoki : 18 m, cône plus large et plus clair en quatre étages ;
  - `momiji`, érable du Japon : 7 m, caduc (feuillage d'automne et charpente d'hiver de P18), houppier en ombrelle ;
  - `bamboo`, bosquet de bambous : 11 m, sept chaumes arqués et panaches de feuilles.
- `engine/scripts/biome_ids.gd` : énumération `SPECIES`.
- Thème par défaut (`engine/themes/default/theme.json` et sa copie du compilateur) : biome `japan` en sugi 4,
  hinoki 3, momiji 2, bambou 2, hêtre 1.
- Vitrine `engine/tests/vitrine_rendu.gd` : rangée et vue `arbres_japon`.

- Bord de route (`roadside_model.gd`, `roadside_props.gd`, `living_decor.gd`) : une montée qui commence dans le
  biome `japan` reçoit un torii vermillon au-dessus de la route, 20 m après son pied (comme le grand torii de
  Hakone-Yumoto sur la route 1), et une paire de lanternes de pierre (tōrō) 12 m après son sommet. Le biome
  est lu sur la couche biome du parcours (tuiles sous verrou, dans la tâche de fond du décor). Vue `torii` de la
  vitrine.

## Reporté

Garde-fous japonais et maisons minka : avec JP3.

## Critères

1. `engine/tests/unit/test_vegetation_biomes.gd` vert (budget de triangles, matières, hauteurs, saisons).
2. `engine/tests/unit/test_roadside_model.gd` vert (torii et lanternes seulement dans le biome `japan`).
3. Captures `arbres_japon` et `torii` low / medium / high validées par le propriétaire.
