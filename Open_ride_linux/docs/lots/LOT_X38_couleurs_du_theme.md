# Lot X38 – Couleurs du thème : aucune couleur en dur dans le HUD et le globe

## 1. Objectif

L'étape 4 de la présentation des menus (N20) ramène les couleurs du HUD et du globe au thème. Sans contrôle, une couleur écrite en dur (`Color(…)`, `Color.html("#…")`) revient à la première retouche (proposition du fil des menus, 28 octobre).

## 2. À lire

`engine/scripts/menu_style.gd` (couleurs du thème), `hud_view.gd`, `world_menu_view.gd` (globe), `engine/tests/unit/test_menu_style.gd`, cahier N20.

## 3. Travail demandé

- **Test GDScript** `engine/tests/unit/test_theme_colors.gd` : lit les sources des scripts d'interface listés (`hud_view.gd`, `world_menu_view.gd`, `menu_view.gd`, `erg_panel.gd`, `summary_view.gd`… liste dans le test) et échoue sur toute couleur littérale (`Color(`, `Color.html(`, `Color8(`, constantes `Color.RED`…) hors de `menu_style.gd` ; exceptions explicites et commentées (transparent `Color(0, 0, 0, 0)`, couleurs de données comme les zones de puissance si elles viennent d'une table du thème).
- Le message d'échec donne le fichier, la ligne et la couleur du thème la plus proche.

## 4. Fichiers

- **Nouveaux :** `engine/tests/unit/test_theme_colors.gd`.
- **Modifiés :** scripts qui ont encore des couleurs en dur après N20 (remplacées par celles du thème), `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Le test passe sur `main` après N20 ; un `Color(1, 0, 0)` ajouté dans `hud_view.gd` le fait échouer avec la ligne.

## 6. Hors périmètre

Le choix des couleurs (N20).
