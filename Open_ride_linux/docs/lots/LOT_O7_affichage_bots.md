# Lot O7 – Bots à l'écran : silhouettes, écarts et choix au menu (facultatif pour la 1.0)

## 1. Objectif

Le lot N9 calcule dans le core des bots à puissance constante et un fantôme d'une séance passée, publiés dans le champ `bots` de la trame `state`. Rien ne les montre encore. Ce lot les affiche (silhouette sur la route, écart en secondes dans le HUD, position sur le profil d'altitude) et permet de les choisir au menu avant une séance. La SRS classe les bots en « optionnel » : la 1.0 peut sortir sans ce lot.

**Lot interne :** il modifie la scène principale et le menu ; sa recette est visuelle.

## 2. À lire

1. `docs/contracts/ipc_v1.md` §3 (liste `bots`), `docs/lots/LOT_N9_bots_core.md` (et sa « Livraison »), `docs/lots/LOT_N6_affichage_menus.md`, `docs/lots/LOT_E3_ciel_arbres_hud.md` (HUD final, profil).
2. Code : `core/src/openride_core/bots.py` (N9), `engine/scripts/main.gd`, `engine/scripts/camera_follow.gd`, `engine/scripts/route_data.gd` (position et cap à `s`), `engine/scripts/hud_view_model.gd`, `engine/scripts/hud_view.gd`, `engine/scripts/menu_model.gd`.

## 3. Prérequis

N9 et N6 fusionnés. Si le choix au menu est retenu : une commande IPC de plus, à grouper avec la révision de contrat de N13 et O4.

## 4. Travail demandé

- **Modèle sans affichage** `engine/scripts/bots_view_model.gd` (testé dans `engine/tests/unit/test_bots_view_model.gd`) : à partir de `s` et `v` du cycliste et des bots, écart en mètres et en secondes (signe : devant ou derrière), bots visibles (moins de 300 m), ordre d'affichage, extrapolation entre deux trames comme pour le cycliste, bots en boucle gérés.
- **Rendu :** silhouette simple et légère par bot (forme stylisée, couleur par `kind`, pas d'avatar détaillé : hors périmètre SRS), posée sur la route à `s` avec le cap de `route_data.gd`, décalée latéralement pour ne pas masquer la caméra ; nom au-dessus à moins de 50 m.
- **HUD :** encart « Bot 200 W  +12 s » (au plus 5 lignes), points colorés sur le profil d'altitude d'E3.
- **Menu (au choix du propriétaire) :** sur l'écran « Prêt », ajouter un bot (200, 250, 300 W ou % de la FTP) ou le fantôme de la dernière séance sur ce parcours ; transmis au core par les arguments de `start` (proposition à valider dans le contrat).
- Coût : 5 bots n'enlèvent pas plus de 1 image/s en qualité basse sur le PC cible.

## 5. Fichiers concernés

Nouveaux `bots_view_model.gd`, `bots_view.gd` et leur test ; modifiés `main.gd`, `hud_view.gd`, `hud_view_model.gd`, `menu_model.gd` (si choix au menu), `docs/contracts/ipc_v1.md` et schémas (si choix au menu), `core/src/openride_core/ipc_server.py` (idem), tests graphiques, `README.md`, `docs/SUIVI_AVANCEMENT.md`.

## 6. Critères d'acceptation

1. Toutes les suites passent ; le modèle de vue est testé sans écran (écarts, visibilité, boucle, extrapolation).
2. `engine/tests/run_visual_tests.sh` avec le faux core émettant deux bots : silhouettes visibles sur la route et encart du HUD présent.
3. Sans bot : rendu et trames identiques à aujourd'hui.

**Sur le PC cible (le propriétaire) :** une séance avec un bot à la FTP et le fantôme de la séance précédente ; vérifier lisibilité et images par seconde.

## 7. Hors périmètre

- Modèle CP / W' des bots (sprint 7 de la SRS, en dernier), multijoueur.

## 9. Livraison

**27 octobre 2026** (thread « Développer les lots O restants »), lot interne sans issue ; les essais Godot sur le PC sont reportés à la demande du propriétaire.

- **Contrat (révision 1.3, décision du 27 octobre) :** `start` accepte `bots`, liste qui remplace les bots de la séance : au plus 4 `{"kind": "constant", "power_w"}` ou `{"kind": "constant", "ftp_pct"}` (en % de la FTP du core) et un `{"kind": "ghost"}` (dernière séance enregistrée sur le parcours choisi). Sans `bots`, la séance garde les bots de la ligne de commande (`--bot`, `--ghost`) ; une liste vide les retire. Liste refusée, ou aucune séance passée pour le fantôme : `error` `bot_invalid`, rien ne démarre. Les trames `state` ne changent pas (sans bot, identiques à avant).
- **Core :** `bots.bots_from_menu`, `bots.last_ride`, `CoreSession._choose_start_bots` ; `core/tests/test_menu_o7.py` (listes refusées, bots créés à la position du cycliste, fantôme de la séance enregistrée, retour aux bots de la ligne de commande).
- **Modèle sans affichage** `bots_view_model.gd` : écart signé en mètres (plus court sens sur une boucle) et en secondes (`gap_s` du core s'il y est, sinon mètres sur la vitesse moyenne des deux), extrapolation d'une seconde au plus entre deux trames, visibles à moins de 300 m, nom à moins de 50 m, du plus loin devant au plus loin derrière, au plus 5 bots. Testé par `engine/tests/unit/test_bots_view_model.gd`.
- **Rendu** `bots_view.gd` : silhouette légère (deux roues, cadre, buste penché), formes et matériaux partagés, couleur par `kind` (orange pour un bot à puissance constante, bleu pâle translucide pour le fantôme), posée à `s` avec le cap de la route et décalée de 1,5 m à droite ; aucun nœud sans bot. `main.gd` met l'encart et les silhouettes à jour à chaque image quand il y a des bots.
- **HUD :** `hud_view.gd` : encart sous le panneau de droite (même largeur, 5 lignes au plus, couleur par `kind`) et points sur le profil d'altitude aux écarts des bots. Le coin sous le panneau de droite est partagé avec les blocs « segment » et « bonus » de la série T : T15 déplacera l'encart si besoin.
- **Menu :** l'écran Prêt gagne « Bot : aucun / 200 W / 250 W / 300 W / 90, 100, 110 % de la FTP » et « Fantôme de la dernière séance : non / oui » (A long change la valeur) ; `start` envoie `bots` seulement si l'un des deux est choisi (avec `ftp_test` ou `plan_day` si besoin) ; un refus du core s'affiche sur la ligne d'état de l'écran Prêt ; une nouvelle séance remet les choix à zéro. Les réglages de bots des menus et de la pause restent au lot N18.
- **Tests graphiques :** scène « bots » du faux core (un bot à 20 m devant, un fantôme à 60 m derrière : encart, silhouettes dans le champ, absence de chevauchement) et scène « sans_bot » ; l'écran Prêt a deux éléments de plus.
- **À faire sur le PC :** une séance avec un bot à la FTP et le fantôme de la séance précédente ; lisibilité et images par seconde avec 5 bots en qualité basse (budget : 1 image/s au plus).
