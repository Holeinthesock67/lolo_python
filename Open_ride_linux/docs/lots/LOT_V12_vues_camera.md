# Lot V12 – Engine : quatre vues de caméra au Click et au clavier

## 1. Objectif

Remplacer la caméra unique de la 1.0 (subjective, SRS §8) par quatre vues, choisies au Click et au clavier selon le plan de boutons commun (spécification générale §7.1 et §7.2, exigences 2.0-CAM-1 à 2.0-CAM-5). Décision du propriétaire du 27 octobre (décision D5 de l'audit de cohérence) : un lot dédié, après l'avatar (V6).

| Vue | Placement | Usage |
| --- | --- | --- |
| Subjective | Yeux du cycliste, 1,4 m, avatar masqué (celle de la 1.0) | Immersion, lisibilité des pentes |
| Suivi proche | 4 m derrière, 1,8 m de haut, regard 10 m devant | Voir son avatar et l'aspiration |
| Suivi éloigné | 12 m derrière, 6 m de haut | Bots, carrefours, peloton |
| Latérale | De côté, façon retransmission, à 8 m de la route | Spectacle, montées |

## 2. À lire

1. `docs/SPECIFICATION_GENERALE.md` §7.1 (A court : vue suivante ; A long : vue par défaut ; flèches haut et bas : vue suivante et précédente) et §7.2 ; `docs/2.0/PLAN_SERIE_V.md` (V-Q11) ; `docs/lots/LOT_V6_avatar_engine.md` ; `docs/lots/LOT_Q2_pentes_a_l_ecran.md` ; `docs/lots/LOT_S1_rendu_invisible.md` ; `docs/lots/LOT_R11_hud_diegetique.md` (champ de vision et tremblement du Cyber-Rogue).
2. Code : `engine/scripts/main.gd`, `camera_follow.gd`, `route_data.gd`, `ipc_client.gd` (événements `input`), `quality_presets.gd`, le module de tri de S1.

## 3. Prérequis

V6 livré (avatar visible) ; événements de tous les boutons dans le contrat (révision 1.3, PR #287) ; S1 livré ou en cours (tri selon la caméra active).

## 4. Travail demandé

- **Modèle sans affichage** `engine/scripts/camera_views.gd` (test `engine/tests/unit/test_camera_views.gd`) : liste ordonnée des quatre vues, vue courante, vue suivante et précédente en boucle, retour à la vue par défaut, transition douce de moins de 0,5 s (position et orientation interpolées), placement de chaque vue à partir de la position, du cap et de la pente de la route.
- **Entrées :** `A_SHORT` et `UP_SHORT` → vue suivante, `DOWN_SHORT` → vue précédente, `A_LONG` → vue par défaut, quand aucun choix n'est affiché (sinon A agit sur le choix : carrefour, couloir, carte) ; le clavier double ces boutons touche pour touche (décision D6, même tableau). Aucune touche propre aux vues.
- **Vue par défaut :** subjective tant que l'avatar n'existe pas, suivi proche ensuite (2.0-CAM-3) ; la dernière vue choisie est écrite dans `[render] camera` (`subjective`, `follow_near`, `follow_far`, `side`) et reprise au lancement.
- **Avatar :** masqué en vue subjective, visible dans les trois autres (`set_visible_for_view` de V6).
- **Pentes (Q2) :** tangage et relief exagéré appliqués à toutes les vues (2.0-CAM-4).
- **Cyber-Rogue :** champ de vision et tremblement de R11 gardés dans chaque vue.
- **Budget (2.0-CAM-5) :** aucune vue sous 55 images/s en `low` sur la GTX 1060 ; mêmes distances de vue et de brouillard qu'en vue subjective ; le tri de S1 reçoit la caméra active.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/camera_views.gd`, `engine/tests/unit/test_camera_views.gd`.
- **Modifiés :** `main.gd`, `camera_follow.gd`, `engine/tests/fake_core.py`, tests graphiques, `core/src/openride_core/config.py` (clé `[render] camera`, validée), `docs/SRS_v1.1.md` (§8 et §11), `docs/SPECIFICATION_GENERALE.md` (§6.3, §7.2), index, suivi.

## 6. Modifications de contrat autorisées

Aucune : les événements des boutons sont dans la révision 1.3 ; la clé `[render] camera` est de la configuration locale.

## 7. Critères d'acceptation

1. Toutes les suites passent ; `test_camera_views.gd` couvre le passage en boucle, le retour à la vue par défaut, la durée de transition et la mémorisation.
2. Banc visuel : une capture par vue sur le parcours de démonstration ; l'avatar n'apparaît pas en vue subjective.
3. Banc simulé : images par seconde et p99 de chaque vue en `low`, au moins 55 images/s.
4. Sur le PC cible (le propriétaire) : changement de vue au Click (A court, A long) et au clavier, transitions sans à-coup.

## 8. Hors périmètre

Caméra libre, ralenti, rejeu.

## 9. Livraison (28 octobre 2026)

- **Modèle :** `camera_views.gd` (quatre vues, passage en boucle, vue par défaut, placement le long de la pente de la route, transition de 0,4 s en position et en orientation, mémorisation 2 s après le dernier changement) ; test `test_camera_views.gd`.
- **Branchement :** `main.gd` place la caméra d'après la vue courante à chaque image (l'avatar est masqué en subjective) ; A court et flèche haut : vue suivante, flèche bas : précédente, A long : vue par défaut, seulement quand ni menu ni carrefour du monde ouvert n'est affiché. Au clavier, Tab (A court) et Entrée (A long) font de même. **Flèches haut et bas du clavier :** elles font encore le braquet jusqu'à O17, qui réécrit tout le tableau du clavier (§7.1).
- **Sans avatar** (core sans `progression`) : vue subjective seule, les changements de vue ne font rien.
- **Réglage :** `[render] camera` (`subjective`, `follow_near`, `follow_far`, `side`), validé par `config.py`, passé à l'engine par `--camera=` et écrit au bout de 2 s par `set_setting render.camera` ; le réglage « Vue de caméra » du menu Réglages la change aussi. Conséquence sur le contrat : la liste `settings` passe de 12 à 13 éléments, la borne `maxItems` du schéma passe de 12 à 16 (ajout compatible).
- **Tests :** visuels (scènes `camera_*` : quatre vues distinctes, avatar caché en subjective, transition, retour par défaut, vue précédente, mémorisation) ; les scènes des lots précédents lancent l'engine avec `--camera=subjective`.
- **Reste :** le banc simulé par vue (≥ 55 images/s en `low`) et l'essai au Click sur le PC.
