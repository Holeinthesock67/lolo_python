# Lot Y18 – Bots dessinés comme l'avatar du joueur

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Bots dessinés comme l'avatar du joueur (même cycliste, maillot selon le bot, maillots de la séance, danseuse, pente) avec niveaux de détail selon la distance et le préréglage | GDScript | O7, Y14, Y16, T14 | Moyenne | En PR (31 octobre), captures à valider, mesure GTX 1060 low/medium/high à faire |

**Statut : en PR (31 octobre)**, captures low, medium et high à valider par le propriétaire, mesure GPU sur la GTX 1060 à faire avant fusion.

## 1. Objectif

Demande du propriétaire du 31 octobre : « Il faudra améliorer le graphisme des bots. S'inspirer de la modélisation / avatar du joueur. »

Avant ce lot, les bots (lot O7) étaient les coureurs du décor (`people_mesh.gd`, lot Y14) : corps droit à 580 triangles, bras tendus, vélo d'une seule couleur, animés par `crowd.gdshader`, et un fantôme dessiné par `bot_ghost.gdshader`. L'avatar du joueur (lot Y16) est bien plus fin : maillot à motif, cuissard, membres effilés, casque à aérations, vélo de route complet, roues et pédalier qui tournent, buste penché.

## 2. Règles (pas d'exception)

- **Un seul cycliste dans le jeu** : un bot est une instance de `avatar_view.gd`, le code de l'avatar du joueur ; aucune géométrie propre aux bots. Les coureurs du décor (P28) restent ceux de `people_mesh.gd` (des dizaines d'instances en un appel de dessin).
- **Apparence tirée du bot, stable** (`scripts/bot_look.gd`, sans nœud) : maillot dans la teinte du nom du bot dans l'encart du HUD (bot à puissance constante orange, bot à profil jaune, fantôme bleu), couleur secondaire, motif, taille, silhouette, peau, cheveux, cadre, roues, casque, chaussettes et lunettes selon l'indice d'affichage ; dossard = indice + 1 ; jamais de cadre de contre-la-montre.
- **Maillots de la séance (T14)** : le porteur du maillot vert des sprints est en vert uni, celui du maillot à pois en blanc à pois rouges ; l'apparence suit quand le maillot change de porteur.
- **Mouvement** : pédalier et roues calés sur la distance parcourue `s` (comme avant, un tour de pédalier par `DEVELOPMENT_M`) ; danseuse au-delà de 8 % (seuil par défaut de l'avatar du joueur) ; vélo incliné avec la pente affichée (relief exagéré compris).
- **Fantôme** : le même cycliste, translucide (`ghost_alpha` 0,55, pré-passe de profondeur : une silhouette d'un seul tenant), sans ombre ni dossard. `bot_ghost.gdshader` est supprimé.
- **Niveau de détail selon la distance à la caméra et le préréglage** (`QualityPresets.BOT_LOD_M`) : niveau 0 (celui du joueur, ≤ 6 000 triangles) de près, niveau 1 (≤ 1 500) à moyenne distance, niveau 2 (≤ 300) au-delà ; hystérésis de 2 m. Un avatar par niveau déjà vu, gardé caché : changer de niveau ne reconstruit rien ; les maillages identiques sont partagés (`AvatarView._parts_cache`).

| Préréglage | Niveau 0 | Niveau 1 | Niveau 2 |
| --- | --- | --- | --- |
| low | jamais | < 15 m | au-delà |
| medium | < 10 m | < 35 m | au-delà |
| high | < 20 m | < 60 m | au-delà |

- **Ombres** : niveaux 0 et 1 (`BOT_SHADOW_MAX_LOD`), et seulement par les pièces de la silhouette (`AvatarView.SHADOW_PARTS` : tronc, cuisses, jambes, bras, tête, casque, chaussures, vélo, roues) ; mains, lunettes, cheveux, chaussettes, manches, cou, cuissard et pédalier n'en portent plus, pour le joueur aussi (invisibles dans l'ombre, un appel de dessin de moins par cascade).

## 3. Fichiers

| Fichier | Rôle |
| --- | --- |
| `engine/scripts/bot_look.gd` | Nouveau : rôle du bot, réglages d'avatar et équipement par indice et maillot |
| `engine/scripts/bots_view.gd` | Réécrit : un `AvatarView` par niveau de détail et par bot, pose, pente, danseuse, maillots ; `set_quality`, `avatar_of`, `test_info` donne les bots par niveau |
| `engine/scripts/avatar_view.gd` | `ghost_alpha`, `shadow_max_lod`, `set_wheel_angle`, `SHADOW_PARTS`, maillages partagés |
| `engine/scripts/quality_presets.gd` | `BOT_LOD_M`, `BOT_SHADOW_MAX_LOD`, `bot_lod()` |
| `engine/scripts/main.gd` | Préréglage transmis aux bots au lancement et au changement de qualité |
| `engine/shaders/bot_ghost.gdshader` | Supprimé ; `crowd.gdshaderinc` perd sa variante fantôme |
| `engine/tests/unit/test_bots_view_model.gd` | Bots = avatar, maillot, niveaux par préréglage, avatar gardé au retour, maillot à pois, danseuse, pente, fantôme ; apparence et `bot_lod` |
| `engine/tests/vitrine_bots.gd` | Nouveau : vitrine avant/après en low, medium et high |

## 4. Mesures dans le nuage (vitrine, gl_compatibility, 1280 × 720)

Triangles de l'image et appels de dessin, avant (main a1b028f) → après. Les triangles baissent ou restent du même ordre (le vélo du décor était lourd) ; les appels de dessin montent (un avatar est fait d'une vingtaine de pièces) : c'est le coût à vérifier sur la GTX 1060.

| Vue | low | medium | high |
| --- | --- | --- | --- |
| Suivi, 5 bots de 4 à 22 m | 19,1 k → 10,8 k tri ; 93 → 230 appels | 19,1 k → 17,4 k ; 101 → 316 | 19,1 k → 29,7 k ; 129 → 364 |
| De côté, 5 bots | 10,8 k → 6,1 k ; 27 → 161 | 10,8 k → 22,4 k ; 29 → 177 | 10,8 k → 22,4 k ; 28 → 176 |
| Loin, 4 bots de 30 à 120 m | 16,4 k → 6,7 k ; 81 → 115 | 16,4 k → 8,0 k ; 93 → 161 | 16,4 k → 9,2 k ; 91 → 203 |

Captures : `/mnt/project-files/captures/y18-bots/` (planches `planche_low.jpg`, `planche_medium.jpg`, `planche_high.jpg`, avant à gauche, après à droite).

## 5. Recette

1. Tests unitaires : `UNIT=test_bots_view_model engine/tests/run_engine_tests.sh` et `test_draft_gauge`.
2. Vitrine : `vitrine_bots.gd --quality low,medium,high`, captures validées par le propriétaire.
3. Sur la GTX 1060 (fil de fusion, file des mesures PC) : banc avec 4 bots et le fantôme groupés devant le cycliste (`sim_bench.py`, scénario avec bots), main contre la branche, en **low, medium et high** : budgets GPU low 6 ms, medium 12 ms, high 14 ms, p99 et images/s inchangés à ± 1 ; captures de chaque préréglage. Si les appels de dessin coûtent trop : abaisser les distances de `BOT_LOD_M` (une ligne), puis, au besoin, un lot suivant qui fusionne les pièces fixes du niveau 2.
4. Sur le vélo (10 min) : rouler derrière et à côté des bots en plaine et dans une montée > 8 % (danseuse), regarder le changement de niveau de détail en s'approchant.
