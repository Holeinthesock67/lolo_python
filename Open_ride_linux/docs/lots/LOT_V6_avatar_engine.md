# Lot V6 – Engine : avatar généré par le code, pédalage synchronisé, danseuse et caméra de suivi

## 1. Objectif

Afficher le cycliste à l'écran : une silhouette 3D générée par le code (aucun fichier 3D sous licence), réglable (morphologie, peau, cheveux, couleurs de tenue, numéro), qui pédale à la cadence réelle et se met en danseuse dans les fortes pentes ou à forte puissance. Aujourd'hui la caméra est subjective (à 1,4 m, hauteur des yeux, `main.gd`) : l'avatar ne se voit pas. Ce lot ajoute donc une **caméra de suivi** derrière le cycliste (V-Q11).

**Lot interne (rendu) :** recette visuelle et mesure sur la GTX 1060.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.3 ; `LOT_V1_contrat_progression.md` §4.4 (réglages) ; `LOT_O7_affichage_bots.md` (silhouettes légères des bots) ; budget de rendu de la série P dans `docs/lots/00_INDEX.md`.
2. Code : `engine/scripts/main.gd` (caméra, boucle de rendu), `camera_follow.gd`, `route_data.gd` (position et cap à `s`), `tree_renderer.gd` (géométrie générée par le code), `quality_presets.gd`, `render_quality.gd`, `ipc_client.gd` (`hello_ack`, `state.cadence`, `state.power`, `state.grade`).

## 3. Prérequis

V1 validé ; O7 de préférence livré (la version allégée des bots en dérive) ; N6 livré.

## 4. Travail demandé

- **Modèle sans affichage** `engine/scripts/avatar_model.gd` (testé dans `engine/tests/unit/test_avatar_model.gd`) : réglages lus depuis `hello_ack.config.progression.avatar` avec défauts et bornes du contrat ; angle du pédalier intégré depuis la cadence (`state.cadence`, extrapolé entre deux trames, figé à 0 rpm et en pause) ; position `seated` ou `standing` avec hystérésis : danseuse au-dessus de `standing_grade_pct` (8 % par défaut) ou de `standing_power_pct` de la FTP (150 % par défaut), retour assis 1 % ou 10 % en dessous et après au moins 2 s ; ces deux seuils sont réglables dans `[avatar]` de `config.toml` (lus par le core, transmis dans `hello_ack`).
- **Géométrie** `engine/scripts/avatar_mesh.gd` : corps en volumes simples (tronc, bassin, cuisses, jambes, bras, tête, casque, cheveux) assemblés par le code, proportions selon `height` et `build` ; 3 niveaux de détail (≤ 6 000, ≤ 1 500 et ≤ 300 triangles), le plus léger servant aux bots ; vélo de base générique (cadre, roues, pédalier) dont V7 remplacera les pièces.
- **Animation :** jambes et pédalier par cinématique simple (deux segments, pied sur la pédale), sans squelette importé ; balancement léger du vélo en danseuse.
- **Caméra de suivi :** derrière et au-dessus du cycliste (4 m derrière, 1,8 m de haut, regard 10 m devant), lissée dans les virages ; bascule subjective / suivi par une touche du clavier et dans le menu (V8) ; la caméra par défaut suit la réponse à V-Q11. Le léger tangage du lot Q2 s'applique aux deux caméras.
- **Budget :** avatar du cycliste au niveau de détail 0, mis à jour en moins de 0,3 ms par image ; au moins 55 images/s en qualité basse sur la GTX 1060 avec toute la série P activée (ligne `[perf-rendu]`).

## 5. Fichiers concernés

Nouveaux : `avatar_model.gd`, `avatar_mesh.gd`, `avatar_view.gd`, leurs tests. Modifiés : `main.gd` (caméra, nœud de l'avatar), `quality_presets.gd` (niveau de détail par préréglage), `engine/tests/fake_core.py` (cadence et avatar de démonstration), tests graphiques, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune au-delà de V1 (les seuils de danseuse `standing_grade_pct` et `standing_power_pct` y sont déjà prévus, §4.4 ; leur lecture dans `config.toml` est une ligne de `config.py` faite par ce lot).

## 7. Critères d'acceptation

1. Toutes les suites passent ; `test_avatar_model.gd` couvre l'intégration de la cadence, la pause, l'hystérésis assis / danseuse et les bornes des réglages.
2. `run_visual_tests.sh` avec le faux core : avatar visible en caméra de suivi, jambes à des angles différents sur deux captures espacées, en danseuse sur une pente de 10 %.
3. Sans `progression` dans `hello_ack` : avatar par défaut, aucune erreur.

**Sur le PC cible (le propriétaire) :** lisibilité, fluidité du pédalage à 60 et 100 rpm, images par seconde en qualité basse.

## 8. Hors périmètre

Cadres, roues et tenues distincts (V7), Garage (V8), bots détaillés.
