# Lot JP3 : maisons japonaises (version 6.0, série JP)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Style `kawara` façon minka : murs bois sombre et enduit blanc à poteaux apparents, shoji et portes à claire-voie, tuiles kawara en rangs, toits en croupe à grand débord | GLSL, GDScript | JP1 | Moyenne | **Livré le 12 novembre** (PR #855), **version 6.0** |

Plan : `docs/6.0/PLAN_SERIE_JP.md`. Demande du user le 12/11 : « des habitations plus japonaises ».

## Livraison

- `engine/shaders/building.gdshader` : mur `WALL_JAPANESE` (9), ouvertures `WIN_SHOJI` (6), toit `ROOF_KAWARA` (7).
  Mur : planches de bois sombre jusqu'à 1,1 m, enduit blanc au-dessus, poteaux tous les ken (1,8 m) au
  rez-de-chaussée et tous les 3,6 m à l'étage, lisses à 1,15 m, à l'étage (bandeau d'auvent) et sous l'égout ;
  pas de soubassement. Rez-de-chaussée : par travée, 30 % de portes à claire-voie (koshi), sinon shoji
  (papier et quadrillage kumiko). Étage : fenêtres à barreaux. Toit : rangs de tuiles 0,26 × 0,3 m.
- `engine/scripts/building_styles.gd` : style `kawara` refait (pente 24°, croupe 75 %, débord 1,2 m,
  murs japonais 80 % / bois 20 %, `house_windows` = shoji, palette kawara gris chaud). La clé
  `house_windows` est lue par tous les styles (défaut : fenêtres de maison), pas d'exception.
- Code d'habillage inchangé (`mur%16 + 16×ouv%8 + 128×toit%8 + 1024×partie + 2048×égout`) : les nouvelles
  valeurs tiennent dans les plages existantes, aucun changement de contrat.
- Tests : `engine/tests/unit/test_building_mesh.gd` (décodage aux valeurs maximales, contrôle Japon).
- Vitrine : vue `maisons_japon` (hameau de 5 bâtiments `kawara`).

## Essais

Captures cloud low / medium / high : `/mnt/project-files/captures/jp3-maisons-2026-11-12/`, à valider par le user.
Coût attendu nul (même shader, quelques branches de plus) ; banc PC dans la recette JP7.
