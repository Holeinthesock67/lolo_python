# Lot W5 – Profil d'arête : altitude, ponts et tunnels, lissage, pente bornée

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Profil d'arête : altitude, ponts et tunnels interpolés, lissage, pente bornée, indépendant du chemin | Python | W4 | Petite | Oui, après W4 (issue #259) |

## 1. Objectif

Donner à chaque arête du graphe (W4) un profil identique à celui d'une route compilée (pas de 10 m, altitude lissée, pente bornée, cap), **indépendant du chemin choisi** : le même profil sert à la route engagée et au fondu du terrain de tous les carrés (W7), si bien que le terrain ne dépend pas de la route prise.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §3.1 (modèle de surface, ponts et tunnels) et §5.4, `docs/contracts/world_format_v1.md` §4.
2. Code : `compiler/src/openride_compiler/pipeline.py` (`sample_positions`, `_smooth_altitude`, `_grade`, `_heading`), `elevation.py`, `constants.py`, `worldgen/graph.py`.

## 3. Prérequis

W4 livré.

## 4. Travail demandé

Module `worldgen/edge_profile.py` :

- `node_altitude(node, provider, frame)` : moyenne du relief au nœud et en 4 points à 10 m autour ; une valeur par nœud, mise en cache par identifiant, pour que deux arêtes qui se touchent aient la même altitude au nœud.
- `edge_profile(edge, provider, frame, node_alt) -> EdgeProfile` :
  1. rééchantillonnage au pas de 10 m le long de `points` (dernier point à `length_m` exactement, comme `sample_positions`) ;
  2. altitude brute du relief en chaque point ;
  3. portions `bridge` et `tunnel` : altitude remplacée par l'interpolation linéaire entre les deux extrémités de la portion (prolongées de 10 m de chaque côté pour sortir de la rampe d'accès) ;
  4. lissage Savitzky-Golay de `pipeline.py` (fenêtre 11, ordre 2) ; arête de moins de 11 points : moyenne glissante sur 3 points ;
  5. raccord aux nœuds : écart aux altitudes de nœud aux deux bouts corrigé par une rampe linéaire sur toute l'arête ;
  6. pente par différences centrées sur 20 m, bornée à ± 25 % (`GRADE_LIMIT_PCT`) ; cap lissé sur environ 30 m ;
  7. `reversed()` : même profil parcouru dans l'autre sens (pente opposée, cap + 180°), sans recalcul.
- `EdgeProfile` : `edge_id`, `s`, `x`, `z`, `alt_m`, `grade_pct`, `heading_deg`, `lat`, `lon`, `clamped_points`, `versions` (`EDGE_PROFILE_VERSION`, source du relief).
- `concat(profiles, s0)` : profils mis bout à bout en colonnes du format `route.json` (`s` continu, point de jonction non doublé), découpables en parties de 1 km (W1 §4.2).
- Tout en numpy, sans entrée-sortie ; une arête de 1 km se calcule en moins de 20 ms (mesuré dans le test, seuil indicatif).

## 5. Fichiers concernés

- **Nouveaux :** `compiler/src/openride_compiler/worldgen/edge_profile.py`, `compiler/tests/test_edge_profile.py`.
- **Modifiés :** `compiler/src/openride_compiler/pipeline.py` seulement si une fonction privée doit devenir publique (sans changer son comportement ; les tests existants le prouvent), `docs/SUIVI_AVANCEMENT.md`.
- **Interdits :** le reste.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. `pytest` passe dans `compiler/` ; tests de `pipeline.py` inchangés.
2. Relief en plan incliné à 5 % le long de l'arête : pente de 5 % à 0,05 près partout sauf aux deux bouts (raccord).
3. Vallée de 40 m de profondeur sous un pont de 200 m : la pente sur le pont reste celle de la droite entre ses extrémités (écart d'altitude maximal 0,5 m après lissage).
4. Deux arêtes qui se touchent : même altitude au nœud commun (1e-6 m).
5. `reversed()` : pentes opposées, altitudes inversées, mêmes positions.
6. `concat` de trois arêtes : colonnes de même longueur, `s` strictement croissant au pas de 10 m sauf la dernière valeur, valide pour `route.schema.json` une fois découpé.
7. Même arête calculée deux fois : profils identiques au bit près (déterminisme).

## 8. Hors périmètre

Choix des arêtes (W6), terrain (W7), RGE ALTI de l'IGN (option ultérieure).
