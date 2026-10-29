# Lot CT3 – Cerveau des bots : suivre ou lâcher, erreurs, relais appuyé

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Donner aux bots de la Course tactique les décisions qui rendent la W′ lisible utile : un bot qui suit une attaque alors que sa réserve ne le permet pas explose ; un bot prudent laisse filer ; après un relais appuyé du cycliste, le bot suivant prend le sien (« cohésion d'échappée »), avec la règle de relais unique de Y10.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Cahier `LOT_Y10_comportement_bots_core.md` (relais, attaques, réponses) ; cahiers AS1 et AS4 ; code `bot_tactics.py` (Y10), `bots.py`.

## 3. Prérequis

Y10, AS1 et AS4 livrés ; CT2 livré.

## 4. Travail demandé

- **Réponse à une attaque** : la règle de Y10 (suivre si réserve au-dessus de 40 %) devient une estimation : le bot suit si sa réserve couvre l'effort estimé (écart qui grandit, durée de 10 s par défaut), avec un taux d'erreur selon le profil et la difficulté (50 % par défaut : 15 % d'erreur, 0 % à 0, 30 % à 100). Un bot qui se trompe suit et peut faire Burnout.
- **Relais appuyé** : après un relais du cycliste d'au moins 15 s en tête, le bot suivant prend un relais au paramètre `relay_push_pct` (110 % de sa puissance de stratégie, 20 s), dans la règle de relais de Y10 ; pas de deuxième mécanique.
- **Erreurs de trajectoire** : chance de rater un virage (CT7) quand la réserve est sous 20 %, valeur `lane_err` dans la trame.
- Déterminisme : tirages depuis la graine de la séance.

## 5. Fichiers concernés

- **Modifiés :** `bot_tactics.py`, `bots.py`, `tactical/balance.toml`, tests correspondants, ce cahier, `00_INDEX.md`.
- **Interdits :** l'engine, le comportement des bots du mode classique hors réglage explicite.

## 6. Modifications de contrat autorisées

Aucune : les champs viennent du lot CT1.

## 7. Critères d'acceptation

1. `pytest -q` passe ; pas d'un bot sous 0,1 ms.
2. Attaque de 10 s à 150 % de la CP du cycliste contre un bot à 5 % de réserve : sur 100 tirages à difficulté 50 %, le bot suit et fait Burnout dans 10 à 20 % des cas, il laisse filer sinon.
3. Relais de 15 s du cycliste : le bot suivant prend la tête dans les 5 s, à 110 % pendant 20 s.
4. Même graine, même course.

## 8. Hors périmètre

Bots qui utilisent des capacités (à proposer après la recette CT12).
