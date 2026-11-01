# Lot W6 – Navigateur : balade, destination, boucle de X km

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Navigateur : balade, destination, boucle de X km | Python | W4 | Moyenne | Livré le 27 octobre (PR #309) |

## 1. Objectif

Choisir la branche par défaut à chaque carrefour quand le cycliste ne touche à rien (plan §2.4 et §5.4), selon trois modes : balade (garder le cap en préférant les petites routes), vers une destination, ou boucle de X km qui revient au départ.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §2 et §5.4, `LOT_W1_contrat_monde_vivant.md` §4.3 (`nav`, `target`, `loop_km`, `seed`), `LOT_W4_graphe_routier.md`.

## 3. Prérequis

W4 livré. Pas besoin de W5 : le navigateur ne lit que la géométrie et, s'ils sont fournis, les profils.

## 4. Travail demandé

Module `worldgen/navigator.py`, pur (aucune entrée-sortie) et déterministe pour une même graine :

- `Navigator(graph, mode, start_xz, start_heading_deg, seed, target_xz=None, loop_m=None)`.
- `choose(node, arriving_edge, history) -> Choice(branch_edge_id, scores)` : `history` = arêtes déjà parcourues dans la séance.
- **Coût d'une branche** (le plus petit gagne), somme pondérée, poids en constantes nommées en tête du module :
  - balade : écart angulaire entre le cap de la branche, moyenné sur ses 300 premiers mètres, et le cap de balade ; le cap de balade part de `start_heading_deg` et dérive lentement (marche aléatoire de ± 20° au plus sur 10 km, tirée de la graine) ;
  - classe : `m`, `t` et `c` préférées, `s` neutre, `p` pénalisée, `k` légèrement pénalisée ;
  - impasse (`dead_end`) : pénalité qui l'exclut sauf s'il n'y a rien d'autre ;
  - déjà parcourue : pénalité, plus forte si parcourue dans les 5 dernières minutes ;
  - pente : aucune préférence en balade (le cycliste veut le relief réel) ;
  - égalité : départagée par la graine.
- **Destination :** plus court chemin (A* sur la longueur pondérée par classe) dans le graphe connu ; si la cible est hors du graphe, cap vers la cible avec le coût de balade ; arrivée à moins de 200 m : `arrived` vrai, puis balade.
- **Boucle :** budget `loop_m` ; aller tant que la distance parcourue est inférieure à 40 % du budget en préférant s'éloigner, puis à chaque carrefour estimer le plus court retour ; dès que `parcouru + retour ≥ budget − 1 km`, suivre le retour. Écart final visé : longueur réelle entre 90 et 115 % de `loop_m` sur un graphe en grille.
- **Demi-tour au bout d'une impasse** prise par le cycliste : `choose` renvoie l'arête retournée.
- Pas de temps réel : chaque `choose` prend moins de 50 ms sur un graphe de 5 000 arêtes.

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/worldgen/navigator.py`, `compiler/tests/test_navigator.py`.
- **Modifiés :** `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/`.
2. Croix avec une branche principale (`p`) tout droit et une petite route (`m`) à 20° : la balade prend la petite route ; à 120°, elle garde le tout droit.
3. Impasse tout droit et route à 60° : la route est choisie.
4. Grille de 200 m sur 10 × 10 km : destination à 6 km atteinte, longueur au plus 1,3 fois la distance à vol d'oiseau.
5. Boucle de 20 km sur la même grille, 20 graines : retour au départ à moins de 200 m, longueur entre 18 et 23 km pour toutes les graines.
6. Même graine, même suite de choix ; graines différentes, suites différentes en balade sur la grille.
7. Balade de 30 km sur la grille : aucune arête parcourue deux fois.

## 8. Hors périmètre

Choix du cycliste et verrouillage (W8, W9), affichage (W12).

## Livraison

PR #309, fusionnée le 27 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « Oui, après W4 (issue #260) ».
