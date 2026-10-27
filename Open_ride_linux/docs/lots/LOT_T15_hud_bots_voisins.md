# Lot T15 – Engine : HUD des bots et encart des deux voisins

## 1. Objectif

Afficher, pour chaque bot, son maillot, son profil, sa FTP en W et en W/kg, son écart en temps de passage et sa jauge de réserve W', et l'encart permanent des deux voisins immédiats (« ▲ Grimpeur +8,4 s », « ▼ Diesel −3,1 s »), d'après les champs du contrat 1.4. Décision du 27 octobre : **code d'abord, sans maquette**, validation à la recette T11.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md` §3.4 (HUD et écarts).
2. `docs/contracts/ipc_v1.md` révision 1.4 : champs des bots (`profile`, `cp_w`, `mass_kg`, `wbal_pct`, `jersey`, `gap_s`), `bot_ahead`, `bot_behind`, `jerseys`.
3. Cahiers `LOT_O7_affichage_bots.md` et `LOT_T16_ecarts_temps_passage.md`.
4. Code : `engine/scripts/hud_view_model.gd`, `hud_view.gd`, le modèle des bots livré par O7.

## 3. Prérequis

O7 (bots à l'écran et liste des bots, pas encore livré : ce lot l'étend, il ne peut commencer qu'après), T9 (même coin du HUD), T16 et T7 (champs remplis par le core). Les champs `profile`, `cp_w`, `mass_kg` et `wbal_pct` n'arrivent qu'avec T12 : sans eux, la ligne du bot montre seulement son nom, son maillot et son écart.

## 4. Travail demandé

- **Modèle sans affichage** `engine/scripts/bot_hud_model.gd`, testé par `engine/tests/unit/test_bot_hud_model.gd` :
  - encart des voisins : `bot_ahead` et `bot_behind` avec le nom et `gap_s` signé (« +8,4 s », « −3,1 s ») ; une ligne disparaît quand le champ vaut `null` ;
  - liste des bots : maillot (vert, à pois ou rien), profil traduit (« Grimpeur », « Rouleur », « Sprinteur », « Diesel »), FTP en W et en W/kg (`cp_w`, `mass_kg`), jauge `wbal_pct`, écart ;
  - maillots de la séance : porteur (« toi » quand `jerseys` vaut `"me"`).
- **Affichage** dans `hud_view.gd` : encart des voisins toujours visible quand il y a des bots ; liste compacte des bots (5 au plus, une ligne chacun) sous l'encart, sans nouveau bouton ni nouvelle action (plan de boutons commun inchangé).

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/bot_hud_model.gd`, son test.
- **Modifiés :** `hud_view.gd`, `hud_view_model.gd`, le modèle des bots d'O7.
- **Interdits :** le core, le contrat.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests Godot sans écran verts, dont le nouveau modèle (voisins présents ou absents, bots sans champs de profil, maillots).
2. Séance avec 4 bots : encart des voisins juste, mis à jour à chaque trame (contrôle visuel à la recette).

## 8. Hors périmètre

- Silhouettes et rendu des bots (O7) ; calcul des écarts (T16, dans le core).

## 9. Livraison (27 octobre 2026, code ; validation à la recette T11)

- **Modèle** `engine/scripts/bot_hud_model.gd` : `view(bots_view, race)` rend les voisins (`neighbors`), une ligne par bot (`rows` : nom, suivi du profil traduit quand il diffère du nom, FTP « 248 W · 4,1 W/kg », réserve `wbal` de 0 à 1 ou −1 sans champ, maillot) et les porteurs des maillots (« Vert : toi · Pois : Grimpeur ») ; `rows_that_fit` et `height` pour la place disponible. Écarts au format des blocs segment (« +8,4 s », « −3,1 s », une décimale), au lieu des secondes entières d'O7.
- **Modèle des bots d'O7** (`bots_view_model.gd`) : les champs `profile`, `cp_w`, `mass_kg`, `wbal_pct` et `jersey` passent dans `view()` ; `set_race()` et `race()` gardent `bot_ahead`, `bot_behind` et `jerseys` de la trame ; couleur jaune pour `kind = "profile"` (T12). Les lignes de l'encart (`hud_lines`, `gap_text`) passent dans `bot_hud_model.gd`.
- **HUD** (`hud_view.gd`) : triangle vers le haut (devant) ou vers le bas (derrière) tracé par le code, pastille du maillot (vert, ou blanc à point rouge pour les pois), jauge W′ sous chaque ligne. **Colonne de droite** empilée par `_layout_right_column()` : bloc segment, bloc bonus (qui remonte quand le bloc segment est caché), puis l'encart des bots jusqu'au-dessus du profil d'altitude, ou du bandeau ERG en ERG. Les lignes de bots qui ne tiennent pas sont cachées (priorité : voisins, maillots, bots) ; en 720p avec les deux blocs affichés, seuls les voisins restent.
- **Tests :** `test_bot_hud_model.gd` (nouveau), `test_bots_view_model.gd` (lignes du HUD), scène « bots » de `visual_check.py` (voisins et maillots).
- Aucun nouveau bouton, aucune modification du core ni du contrat.

