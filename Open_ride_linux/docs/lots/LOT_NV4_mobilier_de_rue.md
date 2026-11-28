# Lot NV4 – Ville néon : mobilier de rue, palmiers, enseignes et voitures garées

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Rue de la ville néon remplie : palmiers à 16 palmes en rangée, lampadaires à globe, enseignes sur mât à noms inventés, guirlandes d'ampoules, voitures garées (part du lot NV5) | GDScript | NV3, NV6, P25 | Moyenne | **En revue** (26 novembre) |

Cinquième lot du parcours « Avenue de la Lagune ». Remarque du propriétaire du 26 novembre sur les captures du lot NV6 : « mis à part les bâtiments le monde est un peu vide ».

## 1. Objectif

En ville néon, la bande du trottoir (3,5 à 9,5 m de l'axe, devant les façades) est meublée partout, sans donnée de plus dans le parcours : tout parcours ou tuile en `ville_neon` en profite.

## 2. Contraintes

- Rien hors de la ville néon (`biome_model.neon_at`) : image par défaut inchangée.
- Aucune lampe, aucune ombre portée : parties lumineuses dans `neon_street.gdshader` (global `neon_glow` du lot NV3).
- Un MultiMesh par sorte et par tronçon de 100 m, 9 tronçons autour de la caméra, un tronçon construit par image au plus.
- Placement déterministe, sans hasard ; rien dans un bâtiment ni dans l'eau (zones d'exclusion du décor vivant).
- Création originale : noms d'enseignes inventés (`SIGN_NAMES`), voitures du jeu (`vehicle_mesh.gd`).
- Préréglage `low` : pas de guirlande, une voiture sur deux. **Banc PC obligatoire** (budgets 8 / 13 / 16 ms).

## 3. Réalisation

- `engine/scripts/neon_street.gd` (nouveau) : `items_of_chunk(k)` (règle de placement), `side_kind` (côté ville, ou côté mer reconnu par le terrain : promenade à double rangée de palmiers, sans voiture ni enseigne), maillages construits par code (`build_palm`, `build_lamp`, `build_garland`, `build_sign`), enseignes en drapeau avec leur nom en `Label3D` sur les deux faces.
- `engine/shaders/neon_street.gdshader` (nouveau).
- `living_world.gd` : nœud `NeonStreet`, configuré avec la route, le modèle de biome, le terrain affiché et les zones d'exclusion.

Par tronçon de 100 m de ville : 10 palmiers, 8 lampadaires, 4 enseignes, 2 guirlandes, 15 voitures environ.

## 4. Critères d'acceptation

- [x] `test_neon_street.gd` (20 vérifications) : rien hors de la ville, placement stable, bande du trottoir, côté mer, zone exclue, `low` allégé, tronçons libérés derrière.
- [x] Captures au cloud sur « Avenue de la Lagune » (`medium`).
- [ ] Banc PC `low`, `medium`, `high` dans les budgets (fil de fusion).
- [ ] Captures validées par le propriétaire.

## 5. Limites connues

- Les passants sont ceux du décor vivant (budget inchangé) : densité à revoir au lot NV5.
- Les enseignes sont sur mât au bord du trottoir, pas encore accrochées aux façades ni aux toits.
- Les voitures garées n'ont pas d'ombre ; quelques-unes gardent leurs feux allumés.
