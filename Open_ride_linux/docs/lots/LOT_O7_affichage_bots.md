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
