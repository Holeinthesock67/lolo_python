# Lot VD7 – Bots en piste

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : bots du peloton PL1 sur la piste (hauteur, relais, attaques, stratégies d'épreuve) et module commun `bot_tactics.py` réutilisable par les autres modes | Python | VD3, VD6, PL1 | Moyenne | Livré le 8 novembre (PR #769, version 4.0) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Plan validé par le propriétaire le 6 novembre (lot VD0).

## 1. Objectif

Faire courir le peloton d'environ 12 bots sur la piste, avec des stratégies propres à chaque épreuve et la physique commune.

## 2. À lire

§6 du plan ; `core/src/openride_core/bots.py`, `draft.py` ; cahier PL1.

## 3. Travail demandé

- Hauteur sur la piste par bot (corde, ligne des stayers, attaque par le haut).
- Stratégies : élimination (DS), points et tempo (sprints), scratch, keirin (placement derrière le derny, puis sprint), omnium, poursuite à allure constante ; coéquipiers des épreuves par équipes (relais réguliers, s'écarter au bon moment, relais de l'américaine avec le joueur).
- Module commun `bot_tactics.py` (§6.1 du plan, décision du propriétaire du 6 novembre) : coalitions, marquage, bluff, gestion du classement, fatigue visible, personnalités (attaquant, suiveur, opportuniste) ; chaque mode active les siens par une table, sans code propre ; prolonge Y10 sans le dupliquer.
- Réglage « Tactique des bots : aucune, simple, complète » à l'écran Prêt du vélodrome.
- Aucune règle physique propre aux bots.

## 4. Critères d'acceptation

1. Courses simulées de 4 et 11 bots, reproductibles.
2. Chaque comportement du §6.1 a son test positif et négatif (coalition qui prend un tour, marquage du leader, bluff suivi d'un relâchement, leader qui surveille, bot vide qui décroche, caractère stable d'une course à l'autre) ; un test vérifie qu'aucun comportement ne modifie la physique ni ne recharge la réserve W′ en dehors de son modèle.
3. Le module ne dépend pas du paquet `track/` (test d'import) : il est utilisable par le classique, DS et GP.
4. Pas de bots superposés à la même place (écart minimum testé).

## 5. Fichiers touchés

- `bots.py` (après PL1), `bot_tactics.py` (nouveau), `track/`, leurs tests.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.

## 6. Livraison (7 novembre, demande du propriétaire : « Lance tout »)

- `bot_tactics.py` (module commun, sans dépendance au paquet `track/`, test d'import) : six comportements du §6.1 du plan, écrits une fois. Le mode décrit la course dans une `RaceView` (ordre sur la piste, classement, prochain objectif : sprint, arrivée ou élimination, tours restants) ; `race_update` pose l'intention de chaque bot (`RaceIntent`), `Tactics.race_power` l'applique à la puissance demandée et à la place :
  - coalitions : 2 ou 3 voisins (moins de 2 s) à plus de 60 % de réserve, loin de tout objectif, roulent à 1,12 × CP ; défaites à moins d'un tour et demi de l'objectif suivant (ils redeviennent rivaux), dans les 3 derniers tours, ou sous 35 % de réserve ; une à la fois, 60 s entre deux ;
  - marquage : le premier du classement à moins de 4 s, laissé à plus de 6 s ; à plus de 0,6 s derrière lui, retour à 1,25 × CP ;
  - bluff : fausse attaque de 3 à 5 s à 1,35 × CP entre 450 et 250 m d'un objectif, puis 5 s relevé (0,8 × CP), une fois par objectif ;
  - gestion du classement (3 derniers tours) : le leader surveille (0,95 × CP au plus) et marque son dauphin ; derrière, tout pour le tout (1,2 × CP jusqu'à 15 % de réserve) ;
  - fatigue visible : sous 8 % de réserve, 0,75 × CP au plus et monte en haut de la piste, jusqu'à 25 % ; la fatigue se voit à la place en haut de la piste et à la baisse d'allure (`wbal_pct` est déjà dans la trame ; l'engine ne change pas encore la posture d'un bot fatigué, écart noté au lot VD9) ;
  - personnalités : attaquant, suiveur ou opportuniste, tiré du nom du bot (même nom, même caractère d'une course à l'autre), règle la chance de chaque comportement (`RATES`).
- Réglage « Tactique des bots : aucune, simple, complète » : réglage `bot_tactics` de `start.track` (complète par défaut, épreuves avec bots seulement), lignes `track_none`, `track_simple` (marquage, classement, fatigue) et `track_full` de `MODE_TACTICS` ; poursuites : `track_paced` (l'épreuve règle l'allure et les relais, seule la fatigue se voit). Écran Prêt : lot VD10.
- `bots.py` : consigne d'épreuve `RaceHint` (puissance en part de la CP, pic de sprint, roue imposée, place sur la piste) lue par `ProfileBot`, puis `race_power` ; une roue imposée (le derny) n'est jamais doublée (freinage roue contre roue comme au lot PL1). Aucune règle physique propre aux bots : même physique, même abri, même modèle W′bal (test).
- `track/bot_plan.py` : consignes de chaque épreuve. Peloton (scratch, points, tempo, keirin, américaine) : sprint vers la prochaine ligne qui rapporte, parti à une distance tirée par bot et par ligne selon le profil (sprinteur 200 à 280 m, diesel 450 à 650 m) ; points : les 6 premiers sur la piste disputent un sprint intermédiaire au-dessus de 50 % de réserve ; tempo : les 3 premiers. Keirin : derrière le derny (roue imposée), sprint entre 1 et 1,6 tour après son départ (sprinteur : 200 à 280 m). Élimination : consignes de survie du Dernier survivant (`survival_hints`). Poursuite : départ arrêté 12 s à 1,3 × CP puis allure constante à la CP, à la corde. Poursuite et vitesse par équipes : meneur à 1,1 et 1,4 × CP, relayeur qui remonte 4 s en haut de la piste, les autres dans les roues. Américaine : coureur au repos en haut de la piste à allure libre, relais lancé à la vitesse du relayé (bot ou cycliste). Coureur sorti : allure libre en haut de la piste. Omnium : consignes de l'épreuve en cours, tour neutralisé à 0,75 × CP.
- Séance : `_track_before_bots` avant le pas des bots (consignes, `race_update`), graine de l'épreuve = graine de la tactique (`bot_tactics_seed` des essais) ; relais de l'américaine appliqués au message `relay`.
- Tests : `core/tests/test_track_bots.py` (comportements positifs et négatifs, coalition qui prend un tour, physique et W′ inchangés, import, consignes de chaque épreuve, scratchs simulés de 4 et 11 bots reproductibles sans bots superposés).
