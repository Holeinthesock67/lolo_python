# Lot AS9 – Cyclistes du décor sans contact à vitesse élevée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Cyclistes du décor sans contact à 50–75 km/h : groupe à cheval sur les 60 m de la liste `riders`, places du core recalées sur le cycliste affiché, groupe ralenti qui ne traverse plus la ligne du cycliste | GDScript, Python | AS7, AS8 | Petite | **Livré le 16 novembre** (PR #893) |

Série AS, suite des lots AS7 (cyclistes du décor calculés par le core) et AS8 (groupes de l'engine rattrapés par un groupe
du core). Lot séparé du volcan (#879), où le défaut a été vu.

## 1. Constat

Banc PC r879b du 14 novembre sur le volcan (#879, roulé à 50–65 km/h), compteur de contacts du décor
(`living_decor._count_contacts`, lot P32) : 41 et 46 contacts sur 2 des 3 passages de `captures_demo`,
« overtake / core à −61 m (écarts à l'axe 1,9 et 2,0 m) » ; dans le cloud, « core / cycliste à −1 m (1,2 et 1,2) ».
Le core seul roulé 900 s sur le volcan à plusieurs allures ne donnait aucun contact : le défaut vient de l'échange
core ↔ engine et touche toute démo roulée vite.

## 2. Reproduction

`engine/tests/rejeu_cyclistes_core.py` (nouvel outil) : le vrai core roule le cycliste à vitesse tenue (route droite de
40 km, pas de 50 Hz, liste `riders` à 10 Hz), puis `rejeu_cyclistes_core.gd` rejoue ces listes dans `road_cyclists_model.gd`
comme `living_decor.gd` (images à 60 Hz avec 2 % d'à-coups de 30 à 80 ms, trames à 30 Hz reçues 5 ms plus tard,
cycliste affiché extrapolé comme `camera_follow.gd`) et compte les contacts avec le critère du banc. Sur `main`, les deux
signatures du banc reviennent : « overtake / core à −61,3 m (1,33 et 1,92) » à 55 km/h, « core / cycliste à −0,6 m
(1,43 et 1,20) » à 65 km/h.

## 3. Causes et correctifs (une règle pour tous, pas d'exception)

1. **Groupe à cheval sur la limite des 60 m.** Le core donne les cyclistes à moins de 60 m un par un : d'un groupe dont la
   tête est à −59 m, la liste ne donne que la tête. L'engine mettait la tête au core et laissait les autres membres dans sa
   propre copie du groupe, qui ne roule pas au même endroit (départ à une autre image, autre vitesse du cycliste) : la tête
   du core se posait sur le 2e de l'engine (« overtake / core à −61 m »). Correctif (`sync_core`) : un groupe donné en
   partie appartient tout entier au core ; ses membres hors liste, ceux de la copie de l'engine comme ceux que le core
   donnait avant, gardent leur place dans le groupe par rapport à un membre reçu (`_anchor`), et la tête du groupe est le
   premier de la file, reçu ou non (une tête sortie de la liste par l'avant ne se pose plus sur le suivant).
2. **Places du core prises en absolu.** Le cycliste affiché (`cam_s`, extrapolé par `camera_follow.gd`) n'est pas au même
   endroit que le cycliste de la trame ; à 15–18 m/s, quelques dizaines de millisecondes font 0,5 à 1 m, et la place reçue
   était en plus extrapolée une fois de plus à l'image de sa reprise. Correctif : comme les véhicules (`traffic_model.sync_core`),
   `sync_core(list, seq, rider_s, core_s)` garde l'écart du core au cycliste (`rider_s − core_s`, pas de recalage au-delà de
   `CORE_SHIFT_MAX_M`, 50 m) et le groupe n'est pas extrapolé à l'image de sa reprise (`fresh`). `living_decor.gd` passe
   `state.s`.
3. **Groupe `overtake` ralenti devant le cycliste** (dans le core comme dans l'engine, même règle, parité gardée). Rabattu
   devant le cycliste puis ralenti par un groupe lent, il repassait « à gauche » dès que sa queue revenait à moins de 20 m
   et traversait la ligne du cycliste qui le doublait (contact du core seul à 65 km/h). Correctifs :
   - il ne sort pour doubler que derrière le cycliste, à plus de `SIDE_LOOK_M` de sa roue ;
   - sorti tout près derrière lui, il ne s'approche pas à moins de `SIDE_LOOK_M` de sa roue tant qu'il n'est pas hors de
     sa ligne ;
   - `_side_blocked` regarde à `SIDE_LOOK_M` plus le chemin que l'autre et lui se rapprochent en `SIDE_CROSS_S`
     (`MIN_CENTRE_M / SIDE_SPEED_MPS`, temps d'un écart d'une place à la voisine), avec la vitesse du dernier pas
     (`step_mps`) : à 65 km/h, un groupe ralenti à 25 km/h voit le cycliste arriver de 10 m au lieu de 2,5 m.

Pas de changement de contrat IPC (la liste reste « au plus 6 cyclistes à moins de 60 m ») ; le relevé de parité
`engine/tests/data/road_cyclists_parity.json` est réécrit (une case change) et l'engine le suit.

## 4. Tests

- `engine/tests/unit/test_road_cyclists_limit.gd` (nouveau) : groupe de 3 à cheval sur les 60 m (tous au core, à leur
  place dans la file, aucun contact en 2 s), tête sortie de la liste par l'avant gardée à sa place, recalage sur le
  cycliste affiché, pas de double extrapolation, pas de recalage au-delà de 50 m. Sur `main` : 7 vérifications sur 9 en échec.
- `core/tests/test_road_cyclists.py` (`test_no_contact_at_high_speed`) (nouveau) : 55, 65 et 75 km/h, 4 graines, 600 s,
  aucun contact du core seul avec le cycliste ni entre groupes ; échoue sur `main` à 65 km/h.
- `test_road_cyclists_core.gd` mis à jour (l'image de la reprise n'extrapole plus) ; `test_road_cyclists_model.gd`,
  `test_road_cyclists_parity.gd`, `test_road_cyclists_yield.gd` et `core/tests/test_road_cyclists.py` verts.
- Rejeu core → engine (`rejeu_cyclistes_core.py`, 30 à 75 km/h, 4 graines, budgets 4, 8 et 16, 900 s) : voir § 5.

## 5. Mesures du rejeu (cloud, 14 novembre)

`rejeu_cyclistes_core.py`, 30, 45, 55, 65 et 75 km/h, graines 0 à 3, budgets 4, 8 et 16, 900 s (60 passes) ; contacts
comptés en images × paires, comme le banc :

| | Core seul | Passes de l'engine avec contact | Contacts de l'engine |
| --- | --- | --- | --- |
| `main` | 3 (65 km/h, « core / cycliste ») | 21 sur 60 | 681 |
| AS9 | 0 | 7 sur 60 | 367 |

Disparus : « overtake / core » à −61 m (55 km/h), « core / cycliste » (65 km/h), « ahead / core » et « oncoming / core »
vers 60 m (45 à 75 km/h). Restent, hors des signatures du banc, pour un lot suivant :
- 65 km/h, graine 1 (104 par passe, tous budgets) : liste pleine (un groupe de 6 et un 7e cycliste à moins de 60 m) ;
  le groupe `ahead` que la liste ne donne plus repasse au décor de l'engine, qui (règle AS8 « roule à la vitesse du
  poursuivant s'il ne peut pas s'écarter ») le garde probablement à la vitesse du groupe du core au lieu de le laisser
  reculer : 18 m d'écart avec le core, contact « core / ahead » à −58 m ;
- budget 16 seulement (préréglage high, 8 à 17 par passe) : « core / core » vers 13 à 40 m, liste pleine ; l'écart
  latéral d'un cycliste repris de l'engine rejoint celui du core en 0,15 s en croisant un autre cycliste du core ;
  « ahead / core » à −21 m avec liste pleine.

## 6. Recette PC

Banc `sim_bench.py` sur le volcan (#879) et une démo rapide en low, medium et high, `--speed-kmh 55` : 0 contact attendu,
budgets GPU 8, 13 et 16 ms, pire image notée ; captures validées par le propriétaire avant fusion.

## Livraison

Fusionné dans `main` : PR #893 (16 novembre). Statut relevé par la mise à jour de la documentation du 19 novembre 2026.
