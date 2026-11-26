# Lot NI3 – Un seul réglage de difficulté des bots

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série NI (éléments inutiles) : la ligne « Intensité » des écrans Prêt seule règle la force des bots ; « Niveau des bots », « Objectif des bots » des Réglages et lignes « Bot 1 » à « Bot 4 » retirés | Python, GDScript | BOT-elo (#941), NI2 (#962), R1 (#982) | Moyenne | En revue (PR à valider : captures des menus) |

## 1. Objectif

Audit des éléments inutiles du 21 novembre 2026 (`plans/AUDIT_ELEMENTS_INUTILES_2026-11-21.md` des fichiers du projet,
lignes R11 et M1), note « Stratégie des bots » (S1, « une seule chaîne de difficulté ») : trois boutons se multipliaient
(« Niveau des bots » en %, « Objectif des bots », niveau de chaque bot à 90, 100 ou 110 % sur l'écran Prêt), plus la
cote Elo. Le joueur ne savait pas lequel réglait quoi (essai du 15 novembre : « bots trop forts même à 50 % »).

**Choix du propriétaire (22 novembre, carte « Intensité seule ») :** la ligne « Intensité » des écrans Prêt (lot R1 :
facile, moyen, dur, avec les watts des bots) est le seul réglage de la force des bots ; la cote Elo reste le seul
réglage automatique (`bots.elo`, oui par défaut).

## 2. La règle

| # | Règle |
| --- | --- |
| NI3-1 | **« Niveau des bots » retiré du menu.** `bots.level_pct` n'est plus dans `settings.SETTINGS` (ni Réglages, ni écrans Prêt du Dernier survivant, du Grand Prix et de la Course) ; `set_setting` le refuse (`setting_invalid`). `migration_reglages.RETIRED` met la ligne en commentaire dans `config.toml` et chaque `profil.toml` au lancement : le niveau revient à 100 %. La clé reste lue par `config.py` (bancs, bornes de la cote, séance conseillée). |
| NI3-2 | **« Objectif des bots » : une seule place.** `bots.objective` passe au groupe `screen` (`settings.SCREEN_KEYS`) : absent de Réglages › Séance, toujours dans la liste `settings` pour la ligne « Intensité » et pour `set_setting`. Récupération et seuil ne se choisissent plus au menu ; une valeur déjà écrite reste valable (la séance conseillée choisit encore l'objectif selon le besoin). |
| NI3-3 | **Lignes « Bot 1 » à « Bot 4 » retirées** (19 choix : 200, 250, 300 W, 90, 100, 110 % de la FTP, quatre profils à trois niveaux) de l'écran Prêt et de l'écran de pause de la session libre, de l'ERG et du mode WTF. Restent « Fantôme de la dernière séance » et « Peloton » (4, 8 ou 11 bots à profil, réglés par l'Intensité et la cote). Derniers choix : le peloton et le fantôme sont repris, un ancien bot choisi un par un est sauté. Les bots de la ligne de commande (`--bot 200`, `--bot-profile`) et l'argument `bots` de `start` ne changent pas. |
| NI3-4 | **Ce qui reste propre aux modes** (dispersion et hasard, jamais la force moyenne) : écart de niveau du Dernier survivant, chaos du Grand Prix, tactique des bots au vélodrome. |
| NI3-5 | **Contrat inchangé.** Aucune commande ni aucun champ nouveau : seules les listes du menu changent. |

## 3. Fichiers

- `core/src/openride_core/settings.py`, `core/src/openride_core/migration_reglages.py` ;
- `engine/scripts/menu_model.gd`, `engine/scripts/menu_flow.gd`, `engine/scripts/ui_icons.gd` ;
- tests : `core/tests/test_settings.py`, `test_bots_calibration.py`, `test_bot_effort.py`, `test_config_couches.py`,
  `test_migration_reglages.py` ; `engine/tests/unit/test_menu_flow.gd`, `test_menu_model.gd`, `test_free_erg_menu.gd`,
  `test_race_menu.gd`, `test_grandprix_menu.gd`, `test_survivor_menu.gd` ; scénarios du banc des menus `ni3_bots` (nouveau),
  `reglages`, `persistance`, `derniers_choix`, `sessions`, `mode_wtf`, `course`, `grand_prix`, `dernier_survivant` ;
- `docs/GUIDE_UTILISATION.md`, `CHANGELOG.md`, `docs/SUIVI_AVANCEMENT.md`.

## 4. Critères d'acceptation

1. Réglages › Séance : ni « Niveau des bots » ni « Objectif des bots » ; « Bots selon ta cote » (la cote Elo, ancien « Niveau automatique (Elo) », libellé coupé à l’écran) est là.
2. Écrans Prêt du Dernier survivant, du Grand Prix et de la Course : pas de ligne « Niveau des bots » ; la ligne « Intensité » est là, avec les watts.
3. Écran Prêt et pause de la session libre : pas de ligne « Bot 1 » ; « Peloton : 4 bots » fait paraître la ligne « Intensité ».
4. Un `profil.toml` qui porte `level_pct = 50` : la ligne est en commentaire après le lancement (copie `.bak`), l'objectif est gardé.

## 5. Recette PC (catégorie : menus seuls)

Pas de rendu, de physique ni de règle de course touchés (la force des bots ne change que par la remise de
`bots.level_pct` à 100 %) : banc des menus PC medium seul, captures low, medium et high à valider par le propriétaire.

```bash
cd ~/Games/lolo_python/Open_ride_linux
python3 engine/tests/menu_bench.py --scenario ni3_bots --scenario reglages --scenario persistance --scenario derniers_choix --scenario course --scenario dernier_survivant --scenario grand_prix --qualite medium --captures ecrans
python3 engine/tests/menu_bench.py --scenario ni3_bots --qualite low --captures ecrans
python3 engine/tests/menu_bench.py --scenario ni3_bots --qualite high --captures ecrans
```

Captures à valider : `ni3_reglages_seance`, `ni3_pret_libre`, `ni3_pret_course`, `ni3_pret_ds`, `ni3_pret_gp`.
Pas d'essai vélo : la force des bots se vérifie par le banc simulé `python -m openride_core.tools.elo_campagne` (la cote converge encore à 100 %).

## Livraison

22 novembre 2026, branche `claude/project-thread-mjv5r1`, partie de la branche de R1 (#982, pas encore dans `main`).
