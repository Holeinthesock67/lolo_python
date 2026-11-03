# Lot AS7 – Abri derrière les groupes de cyclistes du décor

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série AS : groupes de cyclistes du décor calculés par le core et sources d'abri | Python + GDScript | AS2, AS6 (AS4 conseillé) | Grande | Prêt (version 2.0) |

Série AS, version 2.0. Demande du propriétaire du 29 octobre 2026 (« abri derrière véhicules ou groupes à intégrer »).

## 1. Objectif

Les cyclistes du décor (P28) ne sont aujourd'hui que de l'affichage : ils sont tirés par l'engine (`road_cyclists_model.gd`) et ne donnent aucun abri. Ce lot les rend physiques, comme les véhicules d'AS6 :

- le core devient l'autorité des groupes proches du cycliste et les envoie à l'engine ;
- les groupes « devant et plus lents » abritent quand on les rattrape ;
- les groupes « qui doublent » abritent si l'on prend leur roue ;
- les groupes en face n'ont aucun effet.

## 2. À lire

`docs/lots/LOT_P28_cyclistes_route.md`, `LOT_AS2_zone_laterale_placement.md`, `LOT_AS4_groupes_pelotons.md`, `LOT_AS6_abri_vehicules.md` ; code `engine/scripts/road_cyclists_model.gd`, `road_cyclists_renderer.gd`, `core/src/openride_core/draft.py`.

## 3. Prérequis

AS2 et AS6 livrés (même mécanisme d'autorité du core et de liste dans `state`). AS4 conseillé pour l'abri au milieu d'un groupe.

## 4. Travail demandé

- **Groupes dans le core.** Nouveau module pur `road_cyclists.py`, portage de `road_cyclists_model.gd` : mêmes cases, mêmes cas (`oncoming`, `ahead`, `overtake`), mêmes tailles, même graine. Chaque cycliste a une vitesse, une position `s` et un `lane_m` (file ou deux de front, comme P28). Les groupes proches ne dépendent plus du préréglage de qualité.
- **Abri.** Les cyclistes du décor dans le sens du parcours sont des sources d'abri ordinaires (courbe de P3, facteur latéral d'AS2, calcul de groupe d'AS4). Ils ne reçoivent pas d'abri eux-mêmes et ne réagissent pas au cycliste, sauf un groupe `overtake` dont on prend la roue : il garde sa vitesse.
- **Contrat.** Liste `riders` dans `state` : au plus 6 cyclistes à moins de 60 m, `{id, s, v, lane_m, look}` (`look` : tenue et vélo tirés par P28). Elle est envoyée à 10 Hz et extrapolée par l'engine. La trame reste sous 4 096 octets avec 5 bots, 4 véhicules et 6 cyclistes. Au-delà de 60 m, l'engine garde ses groupes décoratifs.
- **Jauge.** `draft_bot` peut désigner un cycliste du décor (`rider:<id>`), et la jauge se pose au-dessus de lui.

## 5. Fichiers concernés

- **Nouveaux :** `core/src/openride_core/road_cyclists.py`, `core/tests/test_road_cyclists.py`.
- **Modifiés :** `draft.py`, `session.py` et tests ; `engine/scripts/road_cyclists_model.gd` (groupes lointains), `road_cyclists_renderer.gd`, `main.gd`, `draft_gauge.gd`, `engine/tests/fake_core.py`, `visual_check.py` ; `docs/contracts/ipc_v1.md` et schéma `state` ; `docs/SRS_v1.1.md` (§5).

## 6. Modifications de contrat autorisées

Liste facultative `riders` dans `state` ; `draft_bot` peut valoir `rider:<id>`. Révision de la 2.0.

## 7. Critères d'acceptation

1. `pytest` et tests de l'engine sans écran passent ; `visual_check.py` et banc sim en low, medium **et** high, avec les mêmes cyclistes proches dans les trois.
2. `road_cyclists.py` et l'ancien modèle : mêmes groupes sur 20 km avec la même graine.
3. Groupe `ahead` de 3 cyclistes à 24 km/h rattrapé à 25 km/h : abri du cycliste derrière le dernier entre 0,30 et 0,45 ; au milieu du groupe (AS4) jusqu'à 0,55.
4. Groupe en face : aucun abri.
5. Trame `state` pleine (5 bots, 4 véhicules, 6 cyclistes) : sous 4 096 octets.
6. Captures en low, medium et high : jauge au-dessus du cycliste du décor qui abrite.

**Sur le vélo (le propriétaire) :** rattraper un groupe du décor et rester dans sa roue.

## 8. Hors périmètre

Cyclistes du décor qui réagissent (relais, attaques) : ce sont des bots (AS1), pas du décor.

## 9. Conception et étapes (31 octobre)

Le lot dépend d'AS2 (écart latéral, `lane_m`) et d'AS6 (circulation du core, même révision du contrat `state`). Il est livré en deux étapes pour avancer sans les attendre.

**Étape 1 (indépendante d'AS2 et d'AS6).**

- `core/src/openride_core/road_cyclists.py` : portage ligne à ligne de `road_cyclists_model.gd` (hachage de `vegetation_placer.gd`, cases, cas, tailles, vitesses à puissance constante, voies du lot P32, bots vus comme des groupes). Entrées : la route du core, les montées `(début, sommet)`, les villages `(x, z)`, la graine (0 comme l'engine) ; la circulation d'AS6 arrive par `vehicles` (clés ou attributs `s`, `dir`).
- Budget du core : `CORE_BUDGET = 16` (celui du préréglage high), pour que les groupes proches ne dépendent plus du préréglage.
- Sorties : `riders()` (tous les cyclistes, `id` « `<groupe>-<rang>` »), `sources()` (ceux qui roulent dans le sens du parcours, `id` « `rider:<id>` », `kind` constant, `lane_m` lu par `draft.py` d'AS2), `state_list(s)` (au plus 6 à moins de 60 m, du plus proche au plus loin, `{id, s, v, lane_m, look}` au centimètre, `v` négative en face).
- Groupe `overtake` dont on prend la roue : une fois rabattu, il garde sa vitesse (sa puissance au rabattement, sur la pente du moment) au lieu de suivre celle du cycliste (`hold_after_pass`, coupé pour la parité).
- Parité (critère 2) : `engine/tests/make_road_cyclists_parity.py` écrit le relevé `engine/tests/data/road_cyclists_parity.json` (séance de `test_road_cyclists_model.gd`, 30 km, budget 16, graine 7) ; `engine/tests/unit/test_road_cyclists_parity.gd` le rejoue avec le modèle de l'engine (mêmes groupes, mêmes comptes, mêmes places à 5 cm) ; `core/tests/test_road_cyclists.py` vérifie que le relevé est à jour, reprend les garanties du test de l'engine et les critères 3 (en une dimension) et 4.

**Étape 2 (après la fusion d'AS2 et d'AS6).**

- `session.py` : le modèle tourne à chaque pas de la boucle (montées tirées des `segments` ou de la détection du core, villages des POI), ses `sources()` s'ajoutent aux bots dans `draft_for` et dans le placement automatique d'AS2 ; `draft_bot` peut valoir `rider:<id>`.
- Contrat : liste facultative `riders` dans `state` à 10 Hz, dans la révision de la 2.0 d'AS6 ; trame pleine (5 bots, 4 véhicules, 6 cyclistes) sous 4 096 octets (`ipc_budget.py`).
- Engine : `road_cyclists_model.gd` ne tire plus que les groupes au-delà de 60 m (ceux qui entrent dans la zone sont repris par la liste du core) ; `road_cyclists_renderer.gd` place les cyclistes reçus, extrapolés entre deux trames ; `draft_gauge.gd` se pose au-dessus de `rider:<id>` ; `fake_core.py` et `visual_check.py` (scène « abri derrière un groupe du décor »).
- Critère 3 complet (écart latéral d'AS2, cœur de groupe d'AS4), mesures et captures en low, medium et high, validées par le propriétaire avant la fusion.
