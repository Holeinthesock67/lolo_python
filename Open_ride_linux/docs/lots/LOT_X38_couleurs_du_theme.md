# Lot X38 – Couleurs du thème : aucune couleur en dur dans le HUD et le globe

## 1. Objectif

L'étape 4 de la présentation des menus (N20) ramène les couleurs du HUD et du globe au thème. Sans contrôle, une couleur écrite en dur (`Color(…)`, `Color.html("#…")`) revient à la première retouche (proposition du fil des menus, 28 octobre).

## 2. À lire

`engine/scripts/ui_theme.gd` (couleurs du thème), `hud_view.gd`, `world_menu_view.gd` (globe), `engine/tests/unit/test_menu_style.gd`, cahier N20.

## 3. Travail demandé

- **Test GDScript** `engine/tests/unit/test_theme_colors.gd` : lit les sources des scripts d'interface listés (`hud_view.gd`, `world_menu_view.gd`, `menu_view.gd`, `erg_panel.gd`, `summary_view.gd`… liste dans le test) et échoue sur toute couleur littérale (`Color(`, `Color.html(`, `Color8(`, constantes `Color.RED`…) hors de `ui_theme.gd` ; exceptions explicites et commentées (transparent `Color(0, 0, 0, 0)`, couleurs de données comme les zones de puissance si elles viennent d'une table du thème).
- Le message d'échec donne le fichier, la ligne et la couleur du thème la plus proche.

## 4. Fichiers

- **Nouveaux :** `engine/tests/unit/test_theme_colors.gd`.
- **Modifiés :** scripts qui ont encore des couleurs en dur après N20 (remplacées par celles du thème), `docs/OUTILS_DE_TEST.md`, ce cahier, `00_INDEX.md`, `SUIVI_AVANCEMENT.md`.

## 5. Critères d'acceptation

1. Le test passe sur `main` après N20 ; un `Color(1, 0, 0)` ajouté dans `hud_view.gd` le fait échouer avec la ligne.

## 6. Hors périmètre

Le choix des couleurs (N20).

## 7. Livraison

Livré le 28 octobre (branche `claude/project-thread-818r6t-x38`, empilée sur l'étape 4 des menus).

- **`engine/tests/unit/test_theme_colors.gd`** (5 vérifications) :
  - scripts lus : tout script de `engine/scripts/` qui charge `ui_theme.gd` (la liste suit les nouvelles vues sans retouche), plus `banner.gd`, `bots_view_model.gd` et `ui_icons.gd` ; 14 aujourd'hui ;
  - refusés : `Color(` suivi d'un nombre, `Color8(`, `Color.html(`, `Color.from_hsv(`…, constantes nommées (`Color.WHITE`…) ; permis : `Color(UiTheme.X, alpha)` et `Color.TRANSPARENT` ; les commentaires sont ignorés ;
  - message : `hud_view.gd:343 « var _rouge := Color(1, 0, 0) » (thème le plus proche : UiTheme.KOM_DOT)` ;
  - le détecteur est vérifié sur une source fabriquée, et le critère 1 a été essayé en ajoutant `Color(1, 0, 0)` dans `hud_view.gd`.
- **Couleurs restantes ramenées au thème** : `UiTheme.INK` (blanc des curseurs, repères et flèches teintées par `modulate`) et `UiTheme.INK_EDGE` (leur liseré noir) dans `hud_view.gd`, `erg_view.gd`, `junction_view.gd` et `workout_chart_view.gd` ; `BOT_CONSTANT`, `BOT_GHOST`, `BOT_PROFILE` et `BOT_OTHER` pour `bots_view_model.gd` ; `GRADE_TEXT_DESCENT` à `GRADE_TEXT_WALL` pour le texte des classes de pente (teintes éclaircies du lot X22, `hud_view.GRADE_TEXT_COLORS`), trouvées par le test lui-même à la fusion de l'étape 4c. Les onze entrent dans `UiTheme.DATA`. Aucune teinte ne change.
- Le contrôle plus faible de `test_menu_style.gd` (`Color(` suivi d'un chiffre, liste fixe de onze vues) est retiré ; ce fichier garde la table des couleurs de données.
