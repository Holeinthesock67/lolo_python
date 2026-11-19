# Lot AS10 – Contacts sur la route : une règle commune à tous les parcours et au monde ouvert

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Contacts des cyclistes du décor, des véhicules et du cycliste corrigés une seule fois pour tous les parcours, le demi-tour et le monde ouvert : liste `riders` de 10, groupe rendu par le core qui garde sa vitesse, chacun vu à sa vraie place en travers, pas de roue prise chez celui qu'on rattrape vite, placement à rebours | GDScript, Python | AS9 | Moyenne | **Livré le 16 novembre** (PR #894) ; les contacts restants relèvent du lot AS11 (PR #925, en revue) |

Série AS, suite du lot AS9 (#893). Demande du propriétaire du 15 novembre : résoudre les contacts de façon globale,
pas parcours par parcours, « de manière générale et égal en open world », véhicules compris.

## 1. Constat (bancs PC de la nuit du 14 au 15 novembre)

| Banc | Contacts | Signature |
| --- | --- | --- |
| rAS9 (#893) volcan, 55 km/h | 84 / 81 / 84 | « core / cycliste à 0 m (écarts 2,5 et 1,9) » |
| rAS9 (#893) demo_long, 55 km/h | 13 / 19 / 22 | « core / core à −21 m (2,0 et 2,5) » |
| #866 DB1 | 18 à 31 | « core / core » |
| r892 et r892main `montees_retour --crowd all` | 24 à 28 (44 sur main) | « tractor / cycliste à 1 m (−2,2 et −0,8) », après le demi-tour |
| #877, #882 | 1 à 5 | cyclistes, voiture d'en face |

Rien de propre à un parcours : les mêmes règles (core `road_cyclists.py`, `traffic.py`, `draft.py` ; engine
`road_cyclists_model.gd`) font rouler tout le monde sur tous les parcours et en monde ouvert.

## 2. Causes communes et correctifs

1. **Liste `riders` pleine.** Le core fait rouler jusqu'à 16 cyclistes (budget fixe) et jusqu'à 10 sont ensemble à moins de
   60 m (relevé du rejeu : 7 à 10 dans 1 % des images, au cœur des groupes de 3 à 6) ; la liste n'en donnait que 6 : les
   autres restaient dans la copie de l'engine, qui ne roule pas au même endroit (« core / core », « ahead / core »).
   Correctif : au plus `STATE_MAX` = 10 (révision 1.18 du contrat IPC), dans la trame qui suit celle de `vehicles`
   (toujours 10 Hz, jamais dans la même trame : la trame la plus chargée reste sous 4 096 octets, `ipc_budget`).
2. **Groupe rendu par le core.** Au-delà des 60 m, un groupe sorti de la liste repasse au décor de l'engine
   (`_to_decor`) ; doublé par un groupe du core sur sa ligne, la règle AS8 (`_yield_to_core`) le faisait rouler à la
   vitesse du groupe du core, à côté de lui, pendant que le core (qui le fait encore rouler) rabattait celui-ci
   (« core / ahead » vers −60 m à 65 km/h). Correctif : un groupe rendu par le core (`core_known`) garde sa vitesse ;
   AS8 ne vaut plus que pour les groupes que le core ne connaît pas.
3. **Le cycliste vu à 1,2 m.** Les cyclistes du décor (core et engine) évitaient le cycliste à `RIDER_LATERAL_M`,
   alors que son placement (lot AS2) le met de 0,3 à 2,6 m (roue prise, dépassement) ; tenu à 0,3 m, 74 à 431 contacts
   de 25 à 55 km/h. Correctif : `update(…, rider_lane)` dans le core (`lane_m` du cycliste, repère de la route) et
   `update(…, lane)` dans l'engine (`lane_m` de la trame) ; le dépassement, le rabattement et `_side_blocked` partent de
   sa vraie place.
4. **Roue prise chez celui qu'on double** (`draft.lane_target`, cycliste et bots). Rattrapé vite, un coureur plus lent
   attirait le cycliste dans sa roue (15 m avant), puis le dépassement le renvoyait à 1 m à gauche au dernier moment :
   frôlé à 0,55 m de 36 à 52 km/h (signature du volcan, 2,5 et 1,9). Correctif : pas de roue prise chez celui qu'on
   rattrape à plus de `FOLLOW_CLOSE_MPS` (1,5 m/s) ; dans un paquet (bots à des vitesses voisines), rien ne change
   (course des bots `bots_race` : mêmes écarts, aucun contact à 11 bots). Vaut aussi pour les véhicules (même placement).
5. **À rebours, pas de placement.** Après un demi-tour (lot N17), le placement était coupé (« personne dans le même
   sens ») ; depuis la circulation et les cyclistes du décor à rebours, le cycliste passait au travers d'un tracteur lent
   de son sens. Le lot N23 (#892, fusionné dans main le 15 novembre) fait rouler circulation et cyclistes du décor sur le
   parcours retourné et y place le cycliste : AS10 reprend ce repère (le `_reverse_runners` d'AS10 est retiré à la mise à
   jour avec main) et y donne aux cyclistes du décor la vraie place du cycliste (`rider_lane`, à droite de son sens).
6. **Banc rAS10 du volcan (après les correctifs 1 à 5) : 87 / 81 / 82 contacts, « core / cycliste à 0 m (2,5 et 1,9) ».**
   Rejoué en séance du core (vrai `_step`, vitesse du cycliste lue dans `seance.jsonl` du banc, boucle de 8 km au profil
   du volcan) puis dans l'engine (`rejeu_cyclistes_core.gd`), deux causes, toutes deux générales :
   - **Retour dans la roue de celui qu'on rattrape encore** (`draft.lane_target`). Dans la roue d'un cycliste du décor à
     peine plus lent, le cycliste ralentit dans la montée ; il sort le doubler, puis l'écart de vitesse passe sous
     `PASS_SPEED_MPS` (0,5 m/s) : il reprend sa roue alors qu'il le rattrape encore à 0,45 m/s, et l'écart latéral
     (`SIDE_CLEAR_M`, dès qu'on toucherait sa roue dans `SIDE_LOOK_S`) arrivait trop tard : il finissait à 0,6 m de lui.
     Correctif : déjà hors de la ligne de l'autre, on regarde en plus le temps de s'en écarter de nouveau
     (`SIDE_CLEAR_M / LANE_RATE_MPS`) ; dans sa roue, rien ne change (abri, Grand Prix GP12 inchangés). Un premier essai
     (dépassement fini tant qu'on va plus vite) coupait l'abri dans la roue d'un bot (0,165 au lieu de 0,2) : abandonné.
   - **Vitesse annoncée, pas vitesse réelle** (`road_cyclists.py` et `road_cyclists_model.gd`). Un groupe retenu derrière
     un groupe lent roulait 4 m/s moins vite que sa vitesse voulue (`speed_mps`) ; le groupe qui le rattrapait se réglait
     sur cette vitesse voulue et venait se poser à côté de lui (« overtake / overtake »), et la liste `riders` l'annonçait
     aussi (`v`) : placement du cycliste, abri, extrapolation de l'engine et reprise au décor (`_to_decor`) le croyaient
     plus loin. Correctif : `riders()` donne la vitesse où il roule (`_step_mps`) ; celui qui rattrape un groupe devant lui
     se règle sur sa vitesse réelle (derrière lui, la vitesse voulue : pas de ralentissement en cascade).

7. **Banc rAS10b (tête d49063be) : volcan et demo_long à 0 en low, medium et high ; « montees_retour --crowd all »
   30 / 27 / 14 contacts, « tractor / cycliste à ±1 m ».** Cause générale, au demi-tour (`traffic.set_direction`,
   lot N23) : le véhicule croisé avant le demi-tour roule ensuite devant le cycliste, dans son sens ; il était marqué
   « a fini de doubler » (`passed`, `committed`), et `_move_overtaker` garde la voie de gauche à un véhicule engagé
   tant qu'il est à moins de `PASS_ZONE_M[1]` (30 m) devant : le tracteur à 25 km/h passait à gauche juste quand le
   cycliste, plus rapide, le doublait (journal : 25 m devant, en train de passer à gauche ; puis 2,1 m à gauche de
   l'axe à côté du cycliste à 0,9 m). Correctif : devant dans le même sens, c'est un véhicule lent devant, comme celui
   que pose `place_for_test` (`slow` : sa voie de droite, il ne double pas, doublé par le cycliste il redevient un
   dépassant). Celui qui doublait le cycliste vient en face : il rejoint sa voie d'un coup au lieu de traverser
   devant lui. L'engine ne fait que prolonger les véhicules du core à moins de 60 m ; au-delà, son modèle garde
   « a fini de doubler » (plus de 30 m devant : voie de droite, sa vitesse), et la règle du croisé y est la même.

Pas d'exception par parcours : le monde ouvert passe par les mêmes fonctions (`_update_draft`, `living_decor.gd`).

## 3. Tests

- Core : `test_road_cyclists.py::test_groups_avoid_the_rider_where_he_is`, `::test_riders_frame_never_carries_vehicles`,
  `test_state_list_is_short_and_near` (10) ; `test_draft_lane.py::test_closing_fast_on_a_slower_rider_never_brushes_him` ;
  `test_traffic.py::test_reverse_rider_passes_slow_tractor_on_the_left` ; banc rAS10 :
  `test_draft_lane.py::test_no_return_into_the_wheel_of_a_rider_still_caught` (0,67 m avant le correctif, 0,81 après) et
  `test_road_cyclists.py::test_group_caught_behind_a_held_group_never_touches_it` (contacts dans 64 cas sur 72 avant) ;
  banc rAS10b : `test_decor_rebours.py::test_vehicles_met_before_u_turn_never_touch_the_rider_after_it` (tracteur,
  voiture, camion : 99 pas sur la voie de gauche devant le cycliste avant le correctif, 0 après) ; budgets de trame (`test_ipc_budget.py`,
  `test_peloton.py`, `test_traffic.py`) et contrat 1.18 (`test_contract_ipc.py`). Les nouveaux échouent sans le correctif.
- Engine : `test_road_cyclists_limit.gd` § 4 (groupe rendu par le core : 3,0 m en 0,5 s au lieu de 9,5) et § 5 (dépassement
  à côté du cycliste là où il est).
- Rejeu `rejeu_cyclistes_core.py` (30 à 75 km/h, 4 graines, budgets 4, 8 et 16, 900 s, 60 passes) : voir § 4.

## 4. Mesures (cloud, 15 novembre)

| | Passes avec contact | Contacts (images × paires) |
| --- | --- | --- |
| AS9 (#893) | 7 / 60 | 367 |
| AS10 | 0 / 60 | 0 |

Banc rAS10 du volcan rejoué (séance du core avec la vitesse du banc, puis engine aux budgets 4, 8 et 16) : avant le
point 6, 8 contacts « cycliste / overtake » et 1 010 « overtake / overtake » dans le core, 2 307 dans l'engine (dont
« core / cycliste » à 2,5 et 2,3) ; après, 0 partout. `rejeu_cyclistes_core.gd` lit maintenant aussi la place du
cycliste en travers et sa vitesse à chaque liste, et une boucle.

Séance du core à vitesse tenue (vrai `_step`, placement automatique, cases chargées à 75 %, 30 à 65 km/h, 900 s) :
aucun contact avec la vraie place du cycliste. Placement seul (36 à 52 km/h derrière un coureur lent) : écart mini 0,55 m
→ 1,3 m. Tracteur lent à rebours : chevauchement de 0,9 m → 0,4 m d'écart.

## 5. Recette PC

Même banc pour tous, low, medium et high (budgets GPU 8, 13 et 16 ms), 0 contact attendu : `sim_bench.py --speed-kmh 55`
sur le volcan et `demo_long`, `montees_retour --crowd all` (demi-tour), le parcours DB1, et un passage en monde ouvert ;
captures validées par le propriétaire avant fusion.

## Livraison

Fusionné dans `main` : PR #894 (16 novembre). Statut relevé par la mise à jour de la documentation du 19 novembre 2026.
