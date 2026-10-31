# Lot AS2 – Zone d'abri en deux dimensions et placement automatique dans la roue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série AS : zone d'abri en deux dimensions (écart latéral `lane_m`) et placement automatique dans la roue, activé par défaut | Python + GDScript | AS1, P32 | Grande | Prêt (version 2.0) |

Série AS, version 2.0 (décision du propriétaire du 29 octobre 2026). Décision du même jour : placement automatique **activé par défaut**.

## 1. Objectif

Aujourd'hui, l'abri ne dépend que de la distance derrière le bot : à 1,5 m sur le côté, on reçoit le même abri que dans la roue. Ce lot ajoute la position sur la route (écart à l'axe) au calcul, pour le cycliste et pour les bots. Le cycliste n'a pas de direction au Click : un placement automatique le range dans la roue du coureur devant lui et l'en sort pour doubler, comme dans Zwift.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_P3_aspiration_bots.md`, `docs/lots/LOT_AS1_abri_entre_bots.md`, PR #562 (lot P32, circulation à droite, constantes de `road_builder.gd`).
2. `docs/contracts/ipc_v1.md` (`state`, `bots`).
3. Code : `core/src/openride_core/draft.py`, `session.py`, `bots.py` ; `engine/scripts/bots_view.gd`, `avatar_view.gd`, `road_builder.gd` (constantes de voie de P32), `camera_follow.gd`.

## 3. Prérequis

AS1 livré. Contrat de la 2.0 ouvert (révision à numéroter par le propriétaire).

## 4. Travail demandé

- **Écart latéral.** Chaque coureur (cycliste et bots) a un `lane_m` : écart à l'axe de la route, positif à droite, borné à la voie de droite (constantes de P32 : cycliste à 1,2 m, bord de voie). Il évolue au plus à 0,8 m/s, lissé, sans à-coup.
- **Abri latéral.** L'abri de P3 est multiplié par `lateral_factor(dx)`, `dx` étant l'écart latéral entre les deux coureurs : 1 jusqu'à 0,3 m, 0,5 vers 0,6 m, 0 au-delà de 1,0 m (courbe en cloche, constantes en tête de `draft.py`, recalées sur les mesures de Blocken et coll. ; citer les sources dans la docstring).
- **Placement automatique** (`[ride] auto_draft = true`, réglage « Placement dans la roue », groupe Séance, activé par défaut) : à moins de 15 m derrière un coureur plus lent ou à la même vitesse, la cible de `lane_m` du cycliste devient celle du coureur devant. Pour doubler (plus de 0,5 m/s plus vite et écart de moins de 3 m), la cible passe à 1,0 m à gauche du coureur doublé, puis revient sur la voie de droite. Coupé : le cycliste garde 1,2 m.
- **Bots.** Les bots se placent de la même façon (règle de suivi d'AS1 comprise). `bots_view.gd` utilise le `lane_m` reçu au lieu de `LATERAL_M`.
- **Contrat.** Champs `lane_m` du cycliste dans `state` et de chaque élément de `bots`, au centimètre. L'engine place l'avatar et les bots avec. La caméra suit l'avatar latéralement avec un lissage de 0,5 s.
- **Jauge d'abri** (PR #566) : inchangée, elle suit toujours `draft_bot`.

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/draft.py`, `session.py`, `bots.py`, `config.py`, `settings.py`, tests correspondants ; `engine/scripts/bots_view.gd`, `avatar_view.gd`, `camera_follow.gd`, `main.gd`, `settings_view_model.gd`, `engine/tests/visual_check.py` ; `docs/contracts/ipc_v1.md`, `docs/contracts/ipc/state.schema.json`, `docs/SRS_v1.1.md` (§5), `docs/GUIDE_UTILISATION.md`.

## 6. Modifications de contrat autorisées

Champ `lane_m` facultatif dans `state` et dans les éléments de `bots` ; réglage `ride.auto_draft` dans `settings`. Révision de la 2.0.

## 7. Critères d'acceptation

1. `pytest` passe en entier ; tests de l'engine sans écran ; `visual_check.py` en low, medium et high.
2. `lateral_factor` : 1 à 0,3 m, environ 0,5 à 0,6 m, 0 à 1,0 m ; décroissant.
3. Placement coupé, bot à 2 m devant décalé de 0,9 m : abri inférieur à 15 % de l'abri dans la roue.
4. Placement activé : en moins de 3 s, le cycliste est à moins de 0,1 m de la ligne du bot et reçoit l'abri plein.
5. Dépassement : écart latéral d'au moins 0,9 m pendant la phase où les deux coureurs se chevauchent ; jamais hors de la route.
6. `lane_m` jamais à gauche de l'axe hors dépassement (circulation à droite).
7. Captures en low, medium et high : avatar dans la roue d'un bot, puis en dépassement.

**Sur le vélo (le propriétaire) :** 10 min derrière deux bots : l'avatar se range seul dans la roue, l'abri se sent, le dépassement est lisible.

## 8. Hors périmètre

Bordure par vent de travers (AS3), groupes larges (AS4).

## 9. Livraison (31 octobre 2026)

- **Core.** `draft.py` : `Lane` (écart à l'axe, vitesse latérale, place `home`), `lateral_factor`, `lane_target`, `step_lane`, `update_lanes`, `start_grid` ; constantes de voie en tête du module, recopiées de `road_builder.gd` (cycliste 1,2 m, bots 2,1 m). Les bots portent `lane` et publient `lane_m` ; le fantôme reste à 2,1 m. Réglage `[ride] auto_draft` (`on` ou `off`, choix comme les autres oui/non des menus).
- **Côte à côte.** Deux coureurs dont les roues se chevauchent, ou se toucheront dans la seconde (`SIDE_LOOK_S`), devant comme derrière, gardent 0,9 m d'écart latéral, chacun du côté où il est déjà ; à écart égal, celui de derrière passe à gauche ; coincé entre deux, le milieu.
- **Grille de départ.** Les bots du menu sont recréés à la place du cycliste : ils se rangent par deux, à 2,1 m et 0,3 m, un rang tous les 2,7 m derrière lui (avant la ligne de départ s'il le faut, l'engine les montant dans l'axe de la route), pour que personne ne parte empilé ni devant le cycliste : un rang devant faussait le calibrage des bots du lot T13 (sprinteur 2,3 % en avance sur 1,5 km).
- **Engine.** `bots_view.gd` pose chaque bot à son `lane_m` ; l'avatar suit `lane_m` du cycliste (au plus 1 m/s entre deux trames), la caméra le suit avec 0,5 s de lissage (`camera_follow.gd`) ; le décor vivant évite cycliste et bots à leur vraie place (poussière, compteur de contacts, véhicules qui doublent).
- **Banc.** `draft_bench` (lot X50) gagne la partie 3 (mise en roue, dépassement) et le groupe libre placement coupé, sur trois départs.

### Mesures du 31 octobre (cloud, `python -m openride_core.tools.draft_bench`)

| Mesure | Valeur |
| --- | --- |
| Mise en roue, bot 2 m devant et 0,9 m à droite | ligne du bot en 1,7 s, abri 0,278 (0,262 dans la roue d'un bot seul, file du banc à vitesse imposée) |
| Même bot, placement coupé | le cycliste reste à 1,2 m, abri 0,011 (4 % de l'abri dans la roue) |
| Dépassement à + 1 m/s | 0,91 m sur le côté au plus près, au plus à 0,2 m de l'axe, retour à 1,2 m |

Groupe libre, bots à 230, 240 et 250 W et cycliste à 240 W, 10 min, moyenne de trois départs :

| Coureur | À l'abri, placement activé | À l'abri, placement coupé |
| --- | --- | --- |
| Bot 230 W | 29 % | 41 % |
| Bot 240 W | 25 % | 30 % |
| Bot 250 W | 11 % | 11 % |
| Cycliste 240 W | 28 % | 5 % |

Placement coupé, le cycliste, à 0,9 m des bots, ne reçoit presque plus d'abri : c'est le prix du réalisme latéral, et ce que le placement automatique rattrape. Placement activé, il retrouve à peu près la part du lot X50 (27 % en une dimension) : un cycliste à puissance constante ne peut pas rester dans une roue plus rapide que lui ni freiner derrière une plus lente, alors que sur le vélo (53 % à l'essai du bloc 7af) on dose sa puissance. La course d'un groupe libre est chaotique : un seul départ donne de 23 à 46 % pour le cycliste, d'où la moyenne de trois départs. Contacts (roues qui se chevauchent à moins de 0,6 m sur le côté) : 3,4 s sur 30 min, sous la borne de 1 % du temps du banc.
