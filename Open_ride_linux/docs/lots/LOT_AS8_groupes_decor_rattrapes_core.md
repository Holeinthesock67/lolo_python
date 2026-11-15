# Lot AS8 – Groupes du décor rattrapés par un groupe du core

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Un groupe de cyclistes de l'engine rattrapé par un groupe du core plus rapide s'écarte et le laisse passer (contacts vers 60 m sur les cols) | GDScript | AS7 | Petite | En PR le 13 novembre, banc PC et captures à valider |

Série AS, suite du lot AS7 (même famille de cause que le correctif #719 du 6 novembre).

## 1. Constat

Recette PC rPK1 du 13 novembre (pack « Cols célèbres », PR #867), compteur de contacts du décor (`living_decor.gd`, lot P32) :
« ahead / core à 60 m, écarts 1,2 m » et « oncoming / core à 57 m, −2,5 m ». Hakone : 73 contacts en low, 390 en medium ;
Stelvio : 6, 4 et 57 ; Ticlio : 0, 6 et 12 ; pires images jusqu'à 150 ms.

Cause : dans `road_cyclists_model.gd`, un groupe `core` n'est déplacé que par le core (`_move` l'extrapole et s'arrête là), et
`core/road_cyclists.py` ne connaît pas les groupes que l'engine tire seul (décor lointain, au-delà de 55 m, ou liste pleine).
Un groupe du core plus rapide traverse donc un groupe `ahead` ou `oncoming` de l'engine qui roule sur sa ligne. L'inverse
(groupe de l'engine plus rapide qui rattrape un groupe du core) était déjà réglé par le dépassement du lot P32.

## 2. Règle (pas d'exception)

Celui qui voit l'autre l'évite. L'engine voit les groupes du core, le core ne voit pas ceux de l'engine : c'est donc toujours le
groupe de l'engine qui s'écarte (`_yield_to_core`, appelé par `_move` pour tout groupe de l'engine) :

- un groupe du core **du même sens**, plus rapide, dont la tête arrive à moins de `CATCH_M` + (écart de vitesse × `YIELD_S`,
  3 s) de sa queue et qui n'est pas encore passé, est un poursuivant ;
- le groupe de l'engine vise une place à `MIN_CENTRE_M` à gauche, dans son sens, du plus à gauche des poursuivants (vers
  l'axe, la même `pass_lat` que pour doubler, bornée au chemin étroit), et le laisse passer sur sa place ; il ne vise pas
  cette place si un autre groupe, un bot ou le cycliste (à moins de `PASS_START_M`) est dessus ou entre les deux ;
- tant qu'il est encore sur la ligne d'un poursuivant tout proche (moins de `CATCH_M`), il roule à sa vitesse : pas de
  contact même s'il n'a pas pu s'écarter à temps ;
- une fois le poursuivant passé, il se rabat à sa place sans se poser sur lui (`_side_blocked`, inchangé) ;
- les groupes d'en face gardent leurs écarts (rien ne change entre sens opposés).

Le core n'est pas modifié (pas de nouvelle révision IPC) ; la parité engine ↔ core des groupes de l'engine est intacte,
la règle ne joue qu'en présence d'un groupe `core`.

## 3. Tests

- `engine/tests/unit/test_road_cyclists_yield.gd` : sur route de 6 m et chemin étroit de 4 m (en file), `ahead` rattrapé
  par un groupe du core à 33 km/h, `oncoming` rattrapé par un groupe de son sens, rattrapé à 2 m par un groupe à 58 km/h
  (pas le temps de s'écarter), bot sur la place visée : aucun contact (critère de `living_decor._count_contacts`), le
  groupe du core passe, le groupe de l'engine s'écarte puis revient sur sa place. Sur `main`, 15 vérifications sur 22
  échouent (jusqu'à 50 images en contact).
- Inchangés et verts : `test_road_cyclists_model`, `test_road_cyclists_core`, `test_road_cyclists_parity`,
  `test_living_decor`, `test_bots_view_model`.

## 4. Recette PC

Banc sur les `.world` du pack Cols (`paquet/packs/cols_celebres/routes` : Hakone, Stelvio, Ticlio) en low, medium et high :
0 contact attendu, budgets GPU 8, 13 et 16 ms, pire image notée ; captures validées par le propriétaire avant fusion.
