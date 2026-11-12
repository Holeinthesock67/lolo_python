# Lot GP8 – Engine : HUD, avertissements et bilan

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : case d'objet et roulette, place et tours, bande de course, choix de voie, avertissements et bilan | GDScript | GP2, GP6 | Moyenne | En PR, captures à valider (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Afficher le HUD et le bilan du mode selon les maquettes validées.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §8.2 ; maquettes GP6 ; `engine/scripts/hud_view.gd`, `engine/scripts/summary_view.gd`.

## 3. Travail demandé

- Case d'objet, place, tours et écart, bande de course, trois traits de voie, avertissements avec flèche et contour d'écran.
- Bilan : place, objets lancés, reçus et esquivés, temps gagné et perdu par objet.

## 4. Critères d'acceptation

1. Captures en 1680×1050 et 1024×600, en `low`, `medium` et `high`, validées par le propriétaire.
2. Tests de modèle du HUD et du bilan (valeurs absentes, 12 coureurs).

## 5. Livraison (8 novembre 2026)

- Modèle sans nœud `engine/scripts/grandprix/gp_hud_model.gd` : case d'objet (objet, charges « ×2 », roulette pendant le tirage, invite « Z : Trois musettes »), effets en cours, place, tours et écart (« à 2,1 s de Rouleur », « à 2,1 s du premier » pour le deuxième, « 2,1 s d'avance » en tête), bande de course (ordre, retard sur le premier, objet tenu, pastille « touché »), voies (choisie en blanc, en gris en automatique, aide « Bidon glissant en vue : A ou ← → »), avertissements (« Musette guidée derrière ! » avec flèche, contour et chevrons ; « Orage vers le premier » sans contour) ; lignes du bilan `summary_lines()`.
- Vue `engine/scripts/grandprix/gp_view.gd` (charte CT9, comme l'habillage WTF) et pastilles des treize objets `engine/scripts/grandprix/gp_items.gd` (forme de la famille, dessin à l'encre) ; branchées dans `main.gd` (`_update_grandprix`), l'encart des bots est caché pendant la course comme au Dernier survivant ; lignes du bilan dans `summary_view_model.gd`.
- Disposition : le HUD de base (puissance, vitesse, profil) reste à sa place, comme dans les autres modes ; la case d'objet se pose sous le panneau central, la place dans la colonne de droite, la bande de course sous le vent. La maquette 6 déplaçait vitesse, pente et arrivée en bas à droite : écart soumis au propriétaire avec les captures.
- Bilan : lignes du bilan de séance (place, objets lancés, reçus et esquivés, temps par objet, bilan des objets), sans le classement complet de la maquette 7, que `summary.gp` ne porte pas.
- Tests : `engine/tests/unit/test_gp_hud.gd` (valeurs absentes ou mal formées, 12 coureurs, bots loin, roulette, avertissements, bilan, vue) ; `core/tests/test_grandprix_engine_parity.py` (noms, familles et charges identiques au core).
- Captures : cas `gp_hud`, `gp_attaque`, `gp_orage_roulette`, `gp_12_coureurs` et `gp_bilan` de `engine/tests/hud_galerie.py`, à lancer sur le PC en 1680×1050 et 1024×600, en `low`, `medium` et `high` :
  `engine/tests/hud_galerie.py --native --configs 1680x1050:low,1680x1050:medium,1680x1050:high,1024x600:low,1024x600:medium,1024x600:high --cas gp_hud,gp_attaque,gp_orage_roulette,gp_12_coureurs,gp_bilan`
