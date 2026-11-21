# Lot PP7 – Objectifs : défi « bats ton record » et fantôme du record

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Défi « bats ton record » dans « Ma puissance », parcours proposé, fantôme du record sur l'écran Prêt ; trophées par palier en PP7b | Python + GDScript | PP3, PP5 | Moyenne | PR ouverte le 21 novembre (série PP, 6.0), captures à valider par le propriétaire ; PP7b (trophées) en cahier |

## 1. Objectif

Idées du §8.3 du plan `docs/6.0/PLAN_SERIE_PP.md`, retenues par le propriétaire le 21 novembre (Q4) : donner un but à la séance à partir de la courbe, au menu seulement, en watts et en mots.

## 2. Travail demandé (PP7)

### 2.1 Core

`core/src/openride_core/tools/power_challenge.py` (`python -m openride_core.tools.power_challenge [--json]`) :

- **durée du défi** : point faible du profil (PP5), sinon le record vieillissant, sinon 5 min ;
- **cible** : record des 6 mois sur cette durée + 1 W ;
- **parcours proposé** (1 min et plus) : parcours prêt dont la montée principale dure, à la puissance visée, au moins la durée du défi et au plus 2,5 fois (vitesse d'équilibre de `route_stats`), le plus court d'entre eux ; parcours du vélodrome et du Grand Prix écartés ; en dessous d'une minute, n'importe quel sprint.
- Sans record sur la durée retenue : pas de défi.
- Contrat : objet facultatif `challenge` du message `power_curve` (même révision 1.29) ; le catalogue des parcours est lu dans le même fil que la courbe, un catalogue illisible n'empêche pas la courbe.

### 2.2 Engine

- Ligne « Défi : 1 min à 431 W », avec le parcours proposé ou « parcours au choix » ; carte : la cible, pourquoi cette durée, le parcours, « A : rouler ce défi, avec le fantôme de ton record ».
- **Fantôme du record** : A ouvre l'écran Prêt « défi : 1 min » sur le parcours proposé (`select_route`, session libre), avec un bot à puissance constante à la cible dans l'argument `bots` de `start` (détail « fantôme à 431 W ») ; sans parcours proposé, la liste des parcours s'ouvre d'abord. Aucune commande nouvelle ; rien pendant la séance.

## 3. PP7b – Trophées par palier (cahier, à coder ensuite)

- Nouvelle règle `puissance` du catalogue de la collection (série BC, `data/collection.toml`) : `seconds` et `watts` (exemple : 300 W sur 5 min), gagnée par la première séance comptée qui tient le palier (courbe de la séance, cache commun du lot PP1).
- Paliers proposés : 5 s (600, 800, 1 000 W), 1 min (350, 450 W), 5 min (250, 300, 350 W), 20 min (200, 250, 300 W) ; rareté croissante ; à valider par le propriétaire avant le code.
- Annonce au bilan par `summary.collection` (existant) : rien de nouveau dans le contrat.

## 4. Critères d'acceptation

1. `core/tests/test_power_challenge.py` (durée, cible, parcours retenu ou écarté, sprint, pas de record) et `test_power_curve_ipc.py` (objet `challenge` conforme au schéma).
2. `engine/tests/unit/test_power_menu.gd` : ligne, carte, écran Prêt avec le fantôme à la cible, liste des parcours sans parcours proposé.
3. Banc des menus : scénario `ma_puissance` vert en low, medium et high, captures `ma_puissance_defi`, `ma_puissance_defi_parcours` et `ma_puissance_defi_pret` ; **captures validées par le propriétaire avant fusion**.

## 5. Livraison

21 novembre 2026, PR empilée sur PP5. Aucune donnée réelle : cycliste fictif à 250 W.
