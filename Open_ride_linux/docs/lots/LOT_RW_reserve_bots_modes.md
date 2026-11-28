# Lot RW – Réserve des bots dans les modes compétitifs

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Jauge de réserve W′ des bots sur les listes du Dernier survivant, du Grand Prix, de la Course et du vélodrome | GDScript | T15, PL1, CR1 | Petite | **Livré le 25 novembre** (PR #967) |

## 1. Objectif

Demande du propriétaire du 21 novembre 2026 : « Il faudrait l'ajouter aussi pour les divers modes compétitifs. C'est
en libre où elle sert le moins », puis « N'oublie pas le mode course ». La jauge de réserve W′ des bots n'existait que
dans l'encart des bots de la session libre (lot T15), caché en Dernier survivant, Grand Prix, Course et vélodrome.

## 2. La règle (une seule, pas de copie par mode)

- `engine/scripts/bot_reserve.gd` : règle et dessin uniques. Réserve = `wbal_pct` du bot dans la trame `state`, de 0
  à 1 ; sans champ (bot à puissance constante, fantôme, bot loin allégé par `bots.light_frame`, qui ne garde
  `wbal_pct` que pour les 5 bots les plus proches), pas de barre. La valeur n'est pas gardée d'une trame à l'autre.
- L'encart de la session libre (`bot_hud_model.gd`, `hud_view.gd`) passe par cette règle et ces couleurs.
- Même trait fin bleu clair (`UiTheme.WBAL`) sous le nom du bot dans : la liste des coureurs du Dernier survivant
  (`survivor_hud_model.list_rows`, champ `wbal`), la bande de course du Grand Prix et de la Course
  (`gp_hud_model.strip_rows`), la liste du vélodrome (`track_hud_model.list_block`, bots de la trame). Pas de barre
  pour le cycliste, un éliminé ou un sorti.
- Mots écrits : sous chaque liste où une barre est visible, la légende « Trait bleu : réserve des bots ».
- Le trait est posé sous le texte de la ligne (séparation négative) : les listes ne grandissent que de la légende
  (bande du Grand Prix à 12 coureurs : bas à 675 px sur 720).
- Aucune donnée nouvelle du core, pas de révision du contrat IPC.

## 3. Tests

- `engine/tests/unit/test_bot_reserve.gd` : règle, lignes des quatre modèles, barres et légende des trois vues
  (Grand Prix et Course), plateau de 12 coureurs dans l'écran.
- `engine/tests/hud_galerie.py` : cas `ds_reserve`, `piste_points_reserve` et `course_reserve` (barres et légende
  contrôlées), bots du Grand Prix avec réserve ; la trame d'un mode (piste, Dernier survivant) est retirée hors de
  son cas.

## Livraison

21 novembre 2026, branche `claude/project-thread-5c1745`, empilée sur la PR #939 (mode Course). Captures low,
medium et high (galerie du HUD, 1280 × 720) à faire valider par le propriétaire ; pas d'essai physique.
