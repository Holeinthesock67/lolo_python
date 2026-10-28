# Lot N19 – Présentation des menus, étape 3 : Réglages, Appareils et connexion, plans et test de FTP

## 1. Objectif

Demande du propriétaire du 27 octobre : les menus sont « trop basiques » et l'aide des boutons ne se voit pas. Le système commun (thème, pictogrammes, bandeau des boutons, carte de détail) est en place depuis les étapes 1 et 2 (`docs/PRESENTATION_MENUS.md`, PR #433). Cette étape l'applique aux écrans qui restent en lignes de texte :

- **Réglages** et ses cinq sous-écrans (Cycliste, Séance, Affichage, Son, Vent, PR #452) : libellé à gauche, valeur alignée à droite, édition en place, curseurs ;
- **Appareils et connexion** : pastilles détaillées, recherche et appairage ;
- **Plans** et **test de FTP** (lot O12) : cartes de détail.

Maquette validée le 27 octobre (écran « Réglages », édition en place du poids) : [maquettes des menus](https://claude.ai/artifact/TEJk2ZXfxJky2BCFEjyEs1).

## 2. À lire

1. `docs/PRESENTATION_MENUS.md` (système commun, tailles, couleurs, étapes), `docs/SPECIFICATION_GENERALE.md` §7.1 (plan des boutons), cahiers `LOT_O4_menu_reglages.md`, `LOT_O12_menu_entrainement.md`, `LOT_N13_menu_appareils.md`, `LOT_Q1_difficulte_en_jeu.md` (curseur de la difficulté).
2. Code : `engine/scripts/menu_view.gd`, `menu_flow.gd`, `menu_model.gd`, `settings_view_model.gd`, `devices_view.gd`, `devices_view_model.gd`, `pairing_view_model.gd`, `ui_theme.gd`, `ui_icons.gd`, `button_help.gd`, `button_bar.gd`, `detail_card.gd` ; tests `engine/tests/unit/test_menu_style.gd`, `test_menu_flow.gd`, `test_menu_view_mouse.gd`, `test_devices_view_model.gd`, `engine/tests/test_menu_ipc.gd`, `engine/tests/visual_check.py`, `engine/tests/menu_bench.py`.

## 3. Prérequis

Étapes 1 et 2 de la présentation des menus fusionnées ; PR #452 (volumes, images/s, sous-écrans de Réglages) fusionnée.

## 4. Travail demandé

### 4.1 Réglages

- **Liste** : une rangée par réglage (`ROW_H`), pictogramme, libellé à gauche, valeur à droite en `DIM` (en `TEXT` sur la rangée sélectionnée), unité en plus petit ; un réglage en % de 0 à 100 (difficulté, volumes) montre son curseur (barre de 180 de large, remplie en `FOCUS`) à gauche de la valeur. L'entrée « Appareils » reste en tête, séparée des sous-écrans par un filet. Le fil d'Ariane du titre dit « Accueil › Réglages › Son ».
- **Édition en place** : valider un réglage n'ouvre plus l'écran séparé `setting_edit` ; la rangée passe en mode édition (`◀ 75 kg ▶`, flèches en `FOCUS`), + et B règlent la valeur (appui long : pas × 5, comme aujourd'hui), A maintenu enregistre, Y annule et rend la valeur d'avant. Un choix (thème, qualité, mode d'affichage) défile dans la même rangée. Le bandeau des boutons suit (`button_help.gd` : « maintenir : Enregistrer », « Régler », « Annuler »). La difficulté de l'écran de pause (`PAUSE_DIFFICULTY`) garde son propre écran (étape 4).
- **Carte de détail** à droite, pour le réglage sous le focus : ce qu'il change, sa plage, sa valeur par défaut, et s'il s'applique tout de suite ou à la prochaine séance (champ `applies` du message `settings`). Pas de carte sur l'entrée « Appareils ».
- **Version** du jeu et du core en bas à droite, en `DISABLED`, 16 px.
- La logique d'édition reste dans `settings_view_model.gd` (sans nœud) ; seul l'affichage change de place. Les « Créer un entraînement » de N16 (clés `workout.…`) profitent de la même édition en place.

### 4.2 Appareils et connexion

- **Liste des appareils** connus (trainer, Click droit, Click gauche, ceinture cardio) : pastille de la couleur du niveau (`OK`, `WARN`, `DANGER`, cercle vide si absent), nom, état écrit seulement s'il n'est pas « prêt », batterie à droite si l'appareil la donne. Le Click gauche montre la raison connue de son silence (verrou de l'application Zwift, `docs/RECHERCHE_CLICK_GAUCHE.md`) dans sa carte de détail plutôt qu'une erreur.
- **Recherche et appairage** : l'écran de `pairing_view_model.gd` en cartes (appareil trouvé, force du signal en barres, « déjà appairé » en `DIM`), anneau de recherche fixe (pas d'animation continue : un compteur de secondes suffit), messages d'échec en `DANGER` sous le titre.

### 4.3 Plans et test de FTP

- **Plans** : liste des plans avec, en carte, la semaine en cours (sept pastilles de jour, séance faite en `OK`, séance du jour en `FOCUS`, repos en `DIM`), la séance du jour en blocs colorés par zone (même graphique que l'étape 2) et la progression du plan (semaine x sur y).
- **Test de FTP** : carte du protocole choisi (rampe ou 20 min) avec sa durée, le graphique de ses blocs, la FTP actuelle et la date du dernier test ; après le test, l'offre d'accepter la nouvelle FTP en grand chiffre `GOLD`, l'ancienne en `DIM`.

### 4.4 Tests et captures

- `test_menu_style.gd` : chaque nouvel écran prend ses couleurs dans `ui_theme.gd` (aucune couleur écrite en dur dans les vues touchées), tailles minimales tenues, valeur d'un réglage alignée à droite dans sa rangée, curseur présent pour un réglage en %.
- `test_menu_flow.gd` : édition en place (entrée, réglage, Y annule et rend l'ancienne valeur, A maintenu envoie `set_setting` une seule fois), pas d'écran `setting_edit` depuis Réglages.
- `visual_check.py` : scènes `reglages` (sous-écran Son, un curseur), `reglage_edition` (poids en cours de modification) et `appareils`, vérifiées par textes et pixels ; captures de référence refaites sur le PC avec `run_visual_tests.sh --golden … --update-golden`.
- `menu_bench.py` sur le PC : temps d'image des menus avant et après, sans hausse de plus de 1 ms.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/menu_view.gd`, `menu_flow.gd`, `settings_view_model.gd`, `devices_view.gd`, `devices_view_model.gd`, `pairing_view_model.gd`, `detail_card.gd`, `ui_icons.gd` (pictogrammes des réglages et des appareils), `button_help.gd` ; `engine/tests/unit/test_menu_style.gd`, `test_menu_flow.gd`, `test_devices_view_model.gd`, `engine/tests/visual_check.py`, `engine/tests/fake_core.py` (si une scène manque d'une donnée) ; `docs/PRESENTATION_MENUS.md`, `docs/GUIDE_UTILISATION.md` (édition d'un réglage), `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** le core et le contrat IPC, `hud_view.gd` et `world_menu_view.gd` (étape 4), `main.gd` (sauf une ligne si l'écran `setting_edit` disparaît de son aiguillage).

## 6. Modifications de contrat autorisées

Aucune : messages `settings`, `set_setting`, `devices`, plans et test de FTP inchangés ; plan des boutons inchangé (§7.1). Aucun nouveau réglage : les idées refusées par le propriétaire le 27 octobre (relief exagéré à l'écran, décor vivant oui ou non) et la pente maximale, déjà couverte par la difficulté, restent hors des menus.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` et `visual_check.py` passent en entier ; `pytest -q` du core inchangé.
2. Réglages au Click, sans clavier ni souris : changer le poids, annuler avec Y (valeur d'avant), enregistrer avec A maintenu ; passer d'un sous-écran à l'autre ; la difficulté et les volumes en curseur.
3. Appareils : les quatre appareils listés avec leur couleur ; un appareil perdu en `DANGER` ; appairage d'un trainer simulé (`--ble-sim`) de bout en bout.
4. Plans et FTP : semaine en cours et séance du jour dessinées ; offre de la nouvelle FTP en `GOLD`.
5. Aucune couleur écrite en dur dans les vues modifiées ; rien sous 16 px ; aucune animation continue.

**Sur le PC cible (le propriétaire) :** parcourir Réglages, Appareils, plans et test de FTP au Click, à 2 m de l'écran ; dire si les valeurs se lisent et si l'édition en place est claire.

## 8. Hors périmètre

- Records, bilan, pause, confirmation et couleurs du HUD et du globe : N20 (étape 4).
- Nouveaux réglages, garage et avatar (V8), choix du biome (U16).
