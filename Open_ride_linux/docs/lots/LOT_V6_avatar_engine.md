# Lot V6 – Engine : avatar généré par le code, pédalage synchronisé, danseuse

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Engine : avatar généré par le code, pédalage synchronisé, danseuse (sans caméra : V12) | GDScript | T1 ; O7 utile | Grande | **Livré le 27 octobre** (issue #372) ; recette de rendu sur le PC |

## 1. Objectif

Afficher le cycliste à l'écran : une silhouette 3D générée par le code (aucun fichier 3D sous licence), réglable (morphologie, peau, cheveux, couleurs de tenue, numéro), qui pédale à la cadence réelle et se met en danseuse dans les fortes pentes ou à forte puissance. Les vues de caméra qui montrent l'avatar (suivi proche, suivi éloigné, latérale) sont toutes faites par le lot V12, qui suit ce lot (décision D5 du 27 octobre) ; V6 n'ajoute aucune caméra et se recette avec la vue de contrôle du banc visuel.

**Lot interne (rendu) :** recette visuelle et mesure sur la GTX 1060.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.3 ; `LOT_T1_contrat_1_4.md` §4.4 (réglages) ; `LOT_O7_affichage_bots.md` (silhouettes légères des bots) ; budget de rendu de la série P dans `docs/lots/00_INDEX.md`.
2. Code : `engine/scripts/main.gd` (caméra, boucle de rendu), `camera_follow.gd`, `route_data.gd` (position et cap à `s`), `tree_renderer.gd` (géométrie générée par le code), `quality_presets.gd`, `render_quality.gd`, `ipc_client.gd` (`hello_ack`, `state.cadence`, `state.power`, `state.grade`).

## 3. Prérequis

T1 validé ; O7 de préférence livré (la version allégée des bots en dérive) ; N6 livré.

## 4. Travail demandé

- **Modèle sans affichage** `engine/scripts/avatar_model.gd` (testé dans `engine/tests/unit/test_avatar_model.gd`) : réglages lus depuis `hello_ack.config.progression.avatar` avec défauts et bornes du contrat ; angle du pédalier intégré depuis la cadence (`state.cadence`, extrapolé entre deux trames, figé à 0 rpm et en pause) ; position `seated` ou `standing` avec hystérésis : danseuse au-dessus de `standing_grade_pct` (8 % par défaut) ou de `standing_power_pct` de la FTP (150 % par défaut), retour assis 1 % ou 10 % en dessous et après au moins 2 s ; ces deux seuils sont réglables dans `[avatar]` de `config.toml` (lus par le core, transmis dans `hello_ack`).
- **Géométrie** `engine/scripts/avatar_mesh.gd` : corps en volumes simples (tronc, bassin, cuisses, jambes, bras, tête, casque, cheveux) assemblés par le code, proportions selon `height` et `build` ; 3 niveaux de détail (≤ 6 000, ≤ 1 500 et ≤ 300 triangles), le plus léger servant aux bots ; vélo de base générique (cadre, roues, pédalier) dont V7 remplacera les pièces.
- **Animation :** jambes et pédalier par cinématique simple (deux segments, pied sur la pédale), sans squelette importé ; balancement léger du vélo en danseuse.
- **Avatar masqué en vue subjective :** le nœud de l'avatar expose `set_visible_for_view(view)` ; il est caché en vue subjective et visible dans les autres (vues du lot V12).
- **Budget :** avatar du cycliste au niveau de détail 0, mis à jour en moins de 0,3 ms par image ; au moins 55 images/s en qualité basse sur la GTX 1060 avec toute la série P activée (ligne `[perf-rendu]`).

## 5. Fichiers concernés

Nouveaux : `avatar_model.gd`, `avatar_mesh.gd`, `avatar_view.gd`, leurs tests. Modifiés : `main.gd` (nœud de l'avatar), `quality_presets.gd` (niveau de détail par préréglage), `engine/tests/fake_core.py` (cadence et avatar de démonstration), tests graphiques, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune au-delà de T1 (les seuils de danseuse `standing_grade_pct` et `standing_power_pct` y sont déjà prévus, §4.4 ; leur lecture dans `config.toml` est une ligne de `config.py` faite par ce lot).

## 7. Critères d'acceptation

1. Toutes les suites passent ; `test_avatar_model.gd` couvre l'intégration de la cadence, la pause, l'hystérésis assis / danseuse et les bornes des réglages.
2. `run_visual_tests.sh` avec le faux core et une caméra de contrôle placée derrière l'avatar par le banc visuel (sans changer la caméra du jeu) : avatar visible, jambes à des angles différents sur deux captures espacées, en danseuse sur une pente de 10 %.
3. Sans `progression` dans `hello_ack` : avatar par défaut, aucune erreur.

**Sur le PC cible (le propriétaire) :** lisibilité, fluidité du pédalage à 60 et 100 rpm, images par seconde en qualité basse.

## 8. Hors périmètre

Vues de caméra (V12), cadres, roues et tenues distincts (V7), Garage (V8), bots détaillés.

## 9. Livraison (27 octobre 2026, issue #372)

- **Core :** section `[avatar]` de `config.toml` (`standing_grade_pct` 8, bornes 3 à 15 ; `standing_power_pct` 150, bornes 100 à 300), transmise dans `hello_ack.config.progression.avatar` (elle remplace les valeurs écrites en dur de V11) ; exemple et tableau du SRS à jour.
- **Engine :** `avatar_model.gd` (réglages bornés, pédalier intégré, hystérésis de la danseuse), `avatar_mesh.gd` (volumes et cinématique à deux segments), `avatar_view.gd` (nœuds, couleurs des palettes, balancement du vélo en danseuse, `set_visible_for_view`). `main.gd` crée l'avatar, le pose sur la route à chaque image et le cache en vue subjective.
- **Triangles :** niveau 0 : 4 948 (≤ 6 000), niveau 1 et niveau 2 sous leurs limites (test unitaire). Budget : 0,05 ms par image mesuré sans écran (budget 0,3 ms, `avatar_frame` dans `perf_budgets.json`).
- **Caméra de contrôle du banc visuel :** message de test `avatar_camera` (`follow` ou `side`) ; elle ne change pas la caméra du jeu. Scènes `avatar_subjectif`, `avatar_assis`, `avatar_assis_2` et `avatar_danseuse` dans `visual_check.py` (jambes à des angles différents entre deux captures, danseuse à 10 % de pente).
- **Écart au cahier :** pas de niveau de détail par préréglage dans `quality_presets.gd` : le cycliste est toujours au niveau 0 (4 948 triangles, bien dans le budget) ; le niveau 2 des bots attend leur affichage détaillé.
- **Reste, sur le PC :** lisibilité, fluidité du pédalage à 60 et 100 tr/min, images par seconde en qualité basse (`run_visual_tests.sh --open`, scène `avatar_assis`).
