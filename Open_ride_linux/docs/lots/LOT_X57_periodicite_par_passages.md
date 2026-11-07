# Lot X57 – Périodicité des à-coups comptée par passages

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : périodicité des à-coups des bancs comptée en passages distincts et non en images (`perf_probe.hitch_period`) | Python | PL1 | Petite | **En PR** (3.0) ; rebanc r735c sur le PC via la file du fil de fusion |

## 1. Constat

Banc r735c du 7 novembre (Dernier survivant à 11 adversaires, PR #735) : tous les budgets passent dans les trois qualités, sauf « à-coups : périodicité en distance » en low (une image lente tous les 778 m, 11 sur 18) et en high (tous les 624 m, 10 sur 16). Le détail par distance montre des paquets, pas une période : en low, 6 images de 1 614 à 1 762 m et 7 images de 2 402 à 2 445 m ; la « période » ne revient que 2 ou 3 fois sur 2,5 km.

Cause : `hitch_period` comptait la couverture en images (`top / (span / P + 1)`). Un paquet de 7 images sur un seul passage valait 7 passages, et la fenêtre de phase (2 × 5 % de P, soit 78 m à 778 m) avalait un paquet entier.

## 2. Spécification

| # | Règle |
| --- | --- |
| X57-1 | Pour chaque période P, la fenêtre de phase retenue est celle qui revient au plus grand nombre de passages distincts (`int(distance // P)`), à égalité celle qui a le plus d'images. Une fenêtre à cheval sur la fin du tour compte un passage, pas deux. |
| X57-2 | Couverture = passages où la fenêtre revient / passages de P sur la route parcourue (au plus 1) ; il faut au moins `min_hits` passages (4), et non plus 4 images. Part et seuil de score (0,6) inchangés : le contrôle n'est pas assoupli pour une vraie saccade périodique. |
| X57-3 | Le texte du contrôle donne le nombre d'images et de passages : « (17 images sur 17, revenue à 17 passages, causes : …) ». |

## 3. Fichiers

- `engine/tests/perf_probe.py` (`hitch_period`, `hitch_checks`) ;
- `core/tests/test_perf_probe_hitches.py` ;
- `docs/OUTILS_DE_TEST.md`, `CHANGELOG.md`.

## 4. Vérification sur les CSV archivés (cloud, seuil de score 0,6)

| Fichier | Contrôle d'avant | Par passages |
| --- | --- | --- |
| 40 m, démo intégrée sans terrain, low (#710) | 40 m (15 images) | 40 m (15 images, 11 passages) |
| 40 m, démo intégrée sans terrain, medium (#710) | 40 m (90) | 40 m (90 images, 11 passages) |
| 40 m, séance DS9 du 4 novembre | 40 m (926) | 40 m (926 images, 91 passages) |
| r735c low | 778 m (11) | aucune |
| r735c high | 624 m (10) | aucune |
| r735b medium | 761 m (7) | aucune |
| témoin peloton low (ds8-b) | 936 m (4) | aucune |
| séance FTP du 4 novembre | 293 m (23) | aucune |

Les 49 autres CSV de saccades archivés (bancs #710, ds8, ds8-b, ds8-c, bots Y10) ne donnaient de période ni avant ni après.

Séance FTP relue à la main : 17 des 23 images de l'ancienne période sont à 5 000 m pile, de 1 117 à 1 154 s, cycliste arrêté sur l'arrivée (un seul passage). Les 6 autres (884, 1 474, 2 637, 3 527 m…) tombent près de la phase 0 à 19 m, sur 5 passages de 17 : pas de période.

## 5. Critères d'acceptation

1. La saccade de 40 m (#710, DS9) reste détectée, y compris avec plusieurs images lentes par tronçon.
2. Deux paquets éloignés, ou un paquet d'arrêt à l'arrivée, ne forment pas une période.
3. Rebanc r735c sur le PC (low, medium, high) : plus d'échec « périodicité en distance ». À passer par la file du fil de fusion.

## 6. Suite, à part

Les deux paquets réels de r735c (bots 12 à 15 ms vers 1,3 à 1,7 km, décor 8 à 14 ms vers 2,1 à 2,8 km de demo_long) restent sous 3 images lentes par minute ; ils relèvent d'un autre lot.
