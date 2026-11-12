# Lot GP10 – Jusqu'à 11 adversaires

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : jusqu'à 11 bots avec objets, après le peloton d'environ 12 bots (lot PL1) | Python + GDScript | GP2, GP3, Y18, PL1 | Moyenne | En PR (12 novembre), bancs PC et captures à faire |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Porter le mode à 11 adversaires quand le core et l'engine savent afficher un peloton.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §8 ; plan du peloton après Y18.

## 3. Travail demandé

- Réglage « Adversaires » de 2 à 11 ; tirage et usage inchangés.
- Trame `gp` et `bots` sous la limite de 4 096 octets.

## 4. Critères d'acceptation

1. `ipc_budget` vert avec 11 bots et 12 objets.
2. Banc en `low`, `medium` et `high` au départ (pire cas), captures validées.

## 5. Livraison (12 novembre 2026)

- Core : borne du réglage `grandprix.opponents` portée à 2–11 (`config.BOUNDS`, comme `survivor.opponents` du lot DS8 ; la séance bornait déjà à `bots.MAX_CONSTANT_BOTS`). Tirage, usage des objets par les bots (GP3) et défaut (4) inchangés. Le réglage reste hors du menu jusqu'au lot GP9 (`config.PENDING_KEYS`).
- Trame : à 11 adversaires, la pire trame (`ipc_budget.worst_grandprix_state(11)`) fait 4 032 octets sans `devices`, sans allègement. La trame qui porte `devices` (une sur 30, 4 351 octets au pire) perdait ses bots ; une étape d'allègement s'ajoute avant celle-là : « objets des bots (trame avec devices) » retire `item` et `fx` des bots de cette trame-là seulement (3 817 octets), et l'engine garde les derniers reçus (`gp_hud_model.gd`, déjà le cas des bots loin). Les 11 bots restent dans la trame. Pas de nouvelle révision du contrat : le schéma ne change pas (`item` et `fx` y sont facultatifs) ; l'ordre d'allègement du §3 et le paragraphe `gp` de `ipc_v1.md` sont complétés.
- Engine : rien à changer, la bande de course a déjà 12 lignes (lot GP8, `gp_hud_model.MAX_ROWS`, `test_gp_hud.gd`).
- Tests : course complète de 3 tours à 11 adversaires (`test_grandprix_session.py` : trames valides sous 4 096 octets, la trame avec `devices` au plus lourd garde ses 11 bots, bilan sur 12) ; `test_ipc_budget.py` ; scénarios de banc `grand_prix` et `grand_prix_onze` (`test_sim_bench_scenarios.py`).
- Banc PC (pire cas au départ, 12 coureurs, chaos fou) : `engine/tests/sim_bench.py --scenario grand_prix_onze --quality low|medium|high --native --probe`, captures 35 m avant chaque rangée de boîtes et après chaque Z, à faire valider par le propriétaire. Repli si un budget n'est pas tenu : `BOT_DETAIL_MAX`, puis `BOT_LOD_M`.
- Constat à suivre (hors du lot) : la règle du banc « aucun contact » (lot P32) peut voir des frôlements dans ce mode. Course simulée de 3 tours : 1 frôlement à 4 adversaires, 3 à 11, tous à la limite de 1,7 m roue à roue : un coureur en voie imposée (esquive, flèches) ne déboîte pas pour doubler, et un coureur ralenti par un objet (glissade, nuage) est rattrapé dans sa roue. Ce n'est pas propre aux 11 adversaires ; correctif possible dans le placement (`draft.py`) d'une voie imposée, à décider.
