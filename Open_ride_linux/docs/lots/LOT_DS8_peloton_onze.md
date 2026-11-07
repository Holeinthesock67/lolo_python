# Lot DS8 – Jusqu'à 11 adversaires

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série DS : jusqu'à 11 adversaires dans le mode, après le peloton d'environ 12 bots (lot PL1) | Python, GDScript | DS2, Y18, PL1 | Moyenne | En PR (6 novembre), bancs PC et captures à faire |

Série DS (mode « Dernier survivant », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/2.0/PLAN_SERIE_DS.md`.

## 1. Objectif

Porter le plateau du mode de 4 à 11 bots une fois le peloton d'environ 12 bots livré, et mesurer le coût.

## 2. À lire

`docs/2.0/PLAN_SERIE_DS.md` §2.1 et §7 ; cahier du lot Y18 ; `core/src/openride_core/ipc_budget.py`.

## 3. Travail demandé

- Réglage `survivor.opponents` étendu à 11 ; liste `bots` de la trame étendue par le contrat du peloton.
- Mesure au départ (pire cas) en `low`, `medium` et `high` ; repli : distances de LOD réduites.

## 4. Critères d'acceptation

1. Budgets GPU tenus au départ avec 11 bots : low 6 ms, medium 12 ms, high 14 ms.
2. Pire trame `state` sous 4 096 octets ; captures validées par le propriétaire.

## 5. Livraison (6 novembre 2026)

- Core : borne du réglage `survivor.opponents` portée à 2–11 (`config.BOUNDS`, `bots.MAX_CONSTANT_BOTS`) ; la liste `bots` est celle du peloton (trame allégée au-delà de 5 bots, `bots.light_frame`). Pire trame du mode à 11 adversaires (`ipc_budget.worst_survivor_state`, objet `survivor` au plus lourd) : 3 799 octets sur 4 096, sans allègement.
- Contacts : à 11, un bot éliminé qui se rangeait au bas-côté coupait la route d'un coureur à sa hauteur (deux contacts sur une course simulée de 12 km). `draft.side_guard` vaut aussi pour un placement coupé : le bot éliminé attend d'être dépassé avant de glisser. Après la tactique des bots du lot Y10 (#728), un frôlement au départ : un bot qui glissait devant un bot enfermé roue contre roue en diagonale derrière lui ; la garde compte ce bot enfermé dès 10 cm avant le chevauchement.
- Engine : bornes de l'écran Prêt à 2–11 (`menu_flow.SURVIVOR_OPPONENTS`, conseils « Possible : … » jusqu'à 11) ; liste des coureurs du HUD : nom gardé quand la trame allégée ne le porte pas, écart estimé (distance ÷ vitesse, comme le repli de `gaps.py`) pour un bot sans `gap_s`.
- Tests : course complète simulée à 11 adversaires sur 12 km (`test_survivor_courses.py` : une élimination par arche, bilan, aucun contact, trames sous 4 096 octets, noms reçus en 11 trames) ; `test_ipc_budget.py` ; `test_survivor_hud.gd`, `test_survivor_menu.gd`.
- Banc PC (pire cas au départ, 12 coureurs) : `sim_bench.py --scenario dernier_survivant_onze --quality low|medium|high` sur `demo_long` (la démonstration étirée à 12 km, même générateur et même terrain), captures toutes les 15 s. Repli si un budget n'est pas tenu : `BOT_DETAIL_MAX`, puis `BOT_LOD_M`.
- Le défaut reste 4 adversaires. La démonstration (5 km) accepte au plus 5 adversaires à 1 km.

### Banc PC r735 (7 novembre, 069ad816)

- GPU tenu dans les trois qualités (moyenne / p99) : low 4,94 / 5,93 ms, medium 6,60 / 7,93, high 8,27 / 9,13 (budgets 6, 12, 14).
- Deuxième élimination jamais vue : à 250 W sur les 3-4 % de la démo, 23 km/h, la séance de 360 s s'arrêtait vers 1,9 km. Scénario passé à 280 W et 480 s.
- Départ : pire image 149-150 ms en medium et high, au premier mètre ; d'après saccades.csv, ce sont les tuiles d'arbres et de route du départ (environ 30 ms d'arbres par tuile), comme le départ de la démo (#710), pas les 12 coureurs.
- Low : 6,4 secondes lentes par minute (au plus 3), alors que medium en a 1,9 et high 0,4 avec plus de bots détaillés. Low a été passé en premier, cache des shaders froid (cause déjà vue sur le test rogue, #712) : à repasser avec low en dernier avant d'y toucher.
