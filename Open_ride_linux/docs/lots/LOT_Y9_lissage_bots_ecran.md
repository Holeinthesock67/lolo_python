# Lot Y9 – Bots à l'écran : lissage, déplacements latéraux et niveaux de détail

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Lissage des bots à l'écran (mémoire de trames, Hermite, déplacements latéraux, LOD) | GDScript | O7 | Moyenne | Oui ; issue #365 |

## 1. Objectif

Série Y (fin de projet, `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §7). Le core calcule les bots à 50 Hz et envoie l'état à 30 Hz ; l'engine (`bots_view_model.gd`, lot O7) les affiche en extrapolant la dernière trame (`s + v × âge`, borné à 1 s), toujours à 1,5 m à droite de la route. D'où de petits sauts à chaque trame quand la vitesse change, et des bots qui se superposent quand ils se doublent. Décision du propriétaire du 27 octobre (§0, question 11) : **un retard d'affichage d'environ 0,1 s est accepté**.

Ce lot, entièrement dans l'engine et sans changement de contrat :

- affiche les bots avec 0,1 s de retard, **interpolés** entre deux trames connues par une courbe d'Hermite qui respecte leurs vitesses ;
- leur donne des **déplacements latéraux** crédibles (se ranger, doubler par la gauche, se mettre dans la roue) avec une accélération latérale bornée ;
- règle leur **niveau de détail** selon la distance, pour tenir le budget avec cinq bots.

## 2. À lire

1. `docs/RECHERCHE_GODOT_PERFORMANCE_GRAPHISMES.md` §7 ; « Snapshot interpolation » de Glenn Fiedler ; Reynolds, « Steering Behaviors » (liens au §9 de la recherche).
2. `docs/lots/LOT_O7_affichage_bots.md`, `LOT_T15_hud_bots_voisins.md`, `LOT_V6_avatar_engine.md` (modèle du cycliste construit par code), `docs/contracts/ipc_v1.md` (liste `bots` : `id`, `name`, `s`, `v`, `kind`, `gap_s`).
3. Code : `engine/scripts/bots_view_model.gd`, `bots_view.gd`, `camera_follow.gd` (extrapolation bornée de la caméra), `people_mesh.gd` (`build_bike`, `build_person`), `route_data.gd`.

## 3. Prérequis

O7 livré. V6 et T15 utiles (modèle des bots et encart du HUD) : si leurs PR sont fusionnées avant, ce lot s'applique à leur modèle ; sinon aux silhouettes d'O7.

## 4. Travail demandé

### 4.1 Interpolation (`bots_view_model.gd`, sans nœud)

- Mémoire des 8 dernières trames de chaque bot (`s`, `v`, heure de réception) ; affichage à `now − INTERP_DELAY_S` (0,1 s) entre les deux trames qui encadrent cet instant, par interpolation d'Hermite cubique sur `s` avec les vitesses comme tangentes ; vitesse affichée = dérivée de la courbe.
- Trame manquante : si l'instant affiché dépasse la dernière trame, extrapolation comme aujourd'hui, bornée à `MAX_EXTRAPOLATION_S` ; au retour des trames, rattrapage en 150 ms sans saut (comme la caméra).
- Boucle : `s` ramené dans [0, longueur[ après l'interpolation, sans saut au passage de la ligne.
- Les écarts du HUD (mètres et secondes) restent calculés sur la dernière trame reçue (ils ne doivent pas prendre 0,1 s de retard).

### 4.2 Déplacements latéraux (`bots_view_model.gd`)

- Chaque bot a une position latérale cible : voie de droite (`LATERAL_M`, 1,5 m) par défaut ; voie de dépassement (0,4 m) quand il rattrape un bot ou le cycliste à moins de 4 m avec 0,5 m/s d'écart de vitesse ou plus, jusqu'à 3 m après l'avoir passé ; dans la roue (même position latérale que celui de devant) quand il le suit à moins de 2 m sans le doubler.
- Position latérale lissée : accélération latérale bornée à 1,5 m/s², vitesse latérale à 1 m/s ; cap légèrement tourné dans le sens du déplacement.
- Purement visuel : aucun effet sur l'aspiration (calculée par le core, P3) ni sur les écarts.

### 4.3 Niveaux de détail (`bots_view.gd`)

- De 0 à 60 m : modèle complet (cadre, roues qui tournent à la vitesse, pédalage à une cadence déduite de la vitesse par un braquet fixe de 50 × 17, cycliste) ; de 60 à 300 m : silhouette simple sans pédalage ; au-delà de `VISIBLE_M` : rien (inchangé). Nœuds créés à la première apparition d'un bot et gardés ensuite (au plus 5) ; aucun nœud créé par image.

## 5. Fichiers concernés

- **Modifiés :** `engine/scripts/bots_view_model.gd`, `bots_view.gd` ; `engine/tests/unit/test_bots_view_model.gd`, `engine/tests/perf_budgets.json` (ligne `bots_view_frame`) ; `engine/tests/visual_check.py` (scène `bots`) ; ce cahier, `docs/lots/00_INDEX.md`, `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** le core, le contrat IPC, l'aspiration, `people_mesh.gd` (utilisé sans le modifier), le HUD des bots (T15).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `engine/tests/run_engine_tests.sh` passe en entier.
2. Interpolation : trames à 30 Hz d'un bot qui accélère de 8 à 12 m/s : position affichée continue, sans saut de plus de 2 cm d'une image à 60 Hz à la suivante ; retard de 0,1 s ± 0,01 s ; deux trames perdues de suite : aucun saut.
3. Latéral : un bot qui en double un autre passe à 0,4 m puis revient à 1,5 m, accélération latérale jamais au-dessus de 1,5 m/s² ; deux bots jamais à moins de 0,8 m l'un de l'autre à la même abscisse.
4. Écarts du HUD inchangés par rapport à O7 pour les mêmes trames.
5. Mise à jour de 5 bots sous 0,1 ms par image (`bots_view_frame`) ; aucun nœud créé après l'apparition des bots.

**Sur le PC cible (le propriétaire) :** séance de 15 min contre 4 bots (`--bots`) en `medium` : bots fluides, dépassements par la gauche, aucun bot qui traverse un autre ; avis sur le retard de 0,1 s (doit passer inaperçu).

## 8. Hors périmètre

- Comportement des bots (attaques, relais, fatigue) : Y10, dans le core.
- Collisions, chutes, bots qui occupent toute la route ; bots du Cyber-Rogue (ennemis de R12).
