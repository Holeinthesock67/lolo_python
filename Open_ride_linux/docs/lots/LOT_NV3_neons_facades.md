# Lot NV3 – Ville néon : néons des façades

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Tubes de néon dessinés par le shader des bâtiments dans le paysage `ville_neon` (un par étage, sous l'égout, aux angles), fenêtres et luminaires allumés dès le coucher du soleil du paysage | GDScript | NV2, Y8, P35 | Moyenne | **En revue** (26 novembre) |

Troisième lot du parcours « Avenue de la Lagune » (cadrage hors dépôt : `/mnt/project-files/plans/CADRAGE_AVENUE_LAGUNE_2026-11-26.md`). Les immeubles pastel à toit plat viennent du parcours lui-même (lot NV6, balises de couleur et de niveaux des bâtiments) ; les enseignes et le mobilier du lot NV4.

## 1. Objectif

En ville néon, chaque bâtiment de plus d'un étage porte des tubes rose et cyan du thème, visibles au coucher du soleil et de nuit, **sans aucune lampe ni objet de plus** : tout est dans `building.gdshader`.

## 2. Contraintes

- Image par défaut inchangée au pixel près : global `neon_glow` nul hors du paysage (vérifié sur `vitrine_nuit.gd`, vues de jour identiques).
- Coût : une branche du shader des façades, seulement en ville néon ; pas de lampe, pas d'appel de dessin de plus. À confirmer par le banc PC.
- Loin, un tube plus fin qu'un pixel est fondu vers sa lueur moyenne (même règle que le reste du shader, `sd_visible`), pour ne pas scintiller.
- Aucune révision du contrat IPC ni du format des parcours.

## 3. Réalisation

- `project.godot` : globaux `neon_glow` (0), `neon_color_a`, `neon_color_b`.
- `neon_fx.gd` : `apply_globals(level, palette)`, ambiance × `density` du thème, couleurs `pink` et `cyan`, posés seulement quand ils changent.
- `building.gdshader` : tubes en haut de chaque étage, sous l'égout et aux deux angles de chaque mur, couleur tirée de la graine du bâtiment et alternée par étage, halo court sur le mur ; rien sur les toits, le socle, ni les bâtiments d'un seul niveau.
- `main.gd` : en ville néon, `NightLights` allume fenêtres, vitrines et luminaires dans la mesure de l'ambiance, même si le joueur roule de jour.
- `tests/vitrine_nuit.gd --neon 1` : pose aussi les globaux.

## 4. Critères d'acceptation

1. Tests graphiques de référence (`tests/golden`) et `test_neon_landscape.gd` verts.
2. Captures au cloud (`vitrine_nuit.gd --neon 1`, `medium`) validées par le propriétaire.
3. PC : banc `low`, `medium`, `high` dans les budgets 8 / 13 / 16 ms sur une rue dense (parcours du lot NV6 ou `make_sim_world.py`), par le fil de fusion après le 28 novembre.

## 5. Livraison

Prêt le 26 novembre, empilé sur NV2. La PR s'ouvre après la fusion des lots précédents.
