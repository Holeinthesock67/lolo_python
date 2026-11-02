# Lot X50 – Banc de l'abri derrière les bots, sans vélo

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : banc de l'abri derrière les bots sans vélo (`draft_bench`) : gain en W par écart derrière 1 à 3 bots, part du temps à l'abri de chacun dans un groupe libre (abri des bots entre eux) | Python | P3, AS1 | Petite | Livré le 30 octobre (PR #619) |

## 1. Objectif

Le propriétaire a demandé le 30 octobre de faire les tests de l'abri (aspiration) en automatique, sans vélo. L'essai sur le vélo du bloc 7af (lot AS1) a montré le cycliste à l'abri 53 % du temps, mais pas l'abri des bots entre eux. Le test X48-2 vérifie déjà que chacun reçoit l'abri ; ce lot donne les chiffres : gain en watts par position derrière une file, et part du temps à l'abri de chaque coureur d'un groupe libre.

## 2. Spécification

| # | Règle |
| --- | --- |
| X50-1 | `python -m openride_core.tools.draft_bench [--puissance 250] [--groupe 230,240,250] [--cycliste 240] [--duree 600] [--json]` fait tourner la vraie `CoreSession` au pas de 20 ms sur un plat de 20 km écrit à la volée (1 120 m d'altitude, celle de `demo_world`), sans trainer réel ni engine. Journal, FIT et records restent dans un dossier temporaire. |
| X50-2 | Gain par position : une file de 1, 2 ou 3 bots roule à vitesse imposée (celle d'un cycliste seul à `--puissance` W), 0,5 m entre les roues. Le cycliste garde un écart de 0,5 à 20 m derrière le dernier bot pendant 120 s ; un régulateur PID règle la puissance du trainer simulé sans connaître l'abri. Moyenne des 60 dernières secondes : abri, puissance, gain en W et en % sur l'air libre. |
| X50-3 | Groupe libre : bots à puissance constante (`--groupe`) et cycliste à puissance constante (`--cycliste`), départ groupé à 1,5 m entre les roues, `--duree` s. Pour chacun : part du temps à l'abri (> 0,01), abri moyen et maximal, distance gagnée sur le même coureur seul (même physique, même parcours), watts gagnés (puissance qu'il faudrait seul pour la vitesse moyenne, moins la sienne). |
| X50-4 | Code 1 si : gain ou abri non décroissant avec l'écart ; abri qui ne croît pas avec le nombre de bots devant ; abri au-dessus de 0,45 (SRS §5) ; abri au-delà de 15 m ; écart moyen tenu à plus de 0,1 m de la cible ; coureur du groupe libre jamais abrité ou pas plus loin que seul. Code 2 pour un appel invalide. |

## 3. Fichiers

- `core/src/openride_core/tools/draft_bench.py` ;
- `core/tests/test_draft_bench.py` ;
- `docs/OUTILS_DE_TEST.md`.

## 4. Critères d'acceptation

1. `python -m openride_core.tools.draft_bench` sort en code 0 sur `main`, en moins de 30 s au cloud.
2. `pytest core/tests/test_draft_bench.py` passe en moins de 10 s.

## 5. Mesures du 30 octobre (cloud, 250 W, 38,4 km/h seul à 1 120 m)

| Écart | Derrière 1 bot | Derrière 2 bots | Derrière 3 bots |
| --- | --- | --- | --- |
| 0,5 m | 0,38 – 82 W (33 %) | 0,43 – 92 W (37 %) | 0,44 – 95 W (38 %) |
| 1 m | 0,34 – 72 W (29 %) | 0,38 – 81 W (32 %) | 0,40 – 86 W (34 %) |
| 2 m | 0,26 – 56 W (23 %) | 0,29 – 63 W (25 %) | 0,31 – 67 W (27 %) |
| 3 m | 0,20 – 44 W (18 %) | 0,23 – 49 W (20 %) | 0,24 – 52 W (21 %) |
| 5 m | 0,12 – 27 W (11 %) | 0,14 – 30 W (12 %) | 0,15 – 31 W (13 %) |
| 8 m | 0,06 – 13 W (5 %) | 0,07 – 14 W (6 %) | 0,07 – 15 W (6 %) |
| 10 m | 0,04 – 8 W (3 %) | 0,04 – 9 W (3 %) | 0,04 – 9 W (4 %) |
| 15 et 20 m | 0 | 0 | 0 |

Groupe libre, 10 min, bots à 230, 240 et 250 W et cycliste à 240 W : tout le monde finit groupé à 38,6 km/h (6 430 à 6 440 m).

| Coureur | À l'abri | Abri moyen | Gagné sur seul | Gain |
| --- | --- | --- | --- | --- |
| Bot 230 W | 36 % | 0,12 | + 252 m | 24 W |
| Bot 240 W | 25 % | 0,07 | + 158 m | 14 W |
| Bot 250 W | 9 % | 0,03 | + 69 m | 5 W |
| Cycliste 240 W | 27 % | 0,08 | + 165 m | 15 W |

Les bots s'abritent bien entre eux. Le groupe se tasse vite : en une dimension, deux coureurs côte à côte (même `s`) ne s'abritent pas (limite connue d'AS1, levée par AS2). C'est pourquoi la part du temps à l'abri reste sous les 53 % de l'essai sur le vélo, où le cycliste dosait sa puissance pour rester dans la roue.

## Livraison

PR #619, fusionnée le 30 octobre 2026. Statut remis à jour par la passe documentaire du 1er novembre, d'après les PR fusionnées ; statut précédent : « En PR (30 octobre) ».
