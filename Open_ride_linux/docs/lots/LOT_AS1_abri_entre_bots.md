# Lot AS1 – Les bots s'abritent entre eux et derrière le cycliste

Série AS (aspiration plus fine), demandée par le propriétaire le 29 octobre 2026. Décision du même jour : AS1 en 1.x, AS2 à AS7 en 2.0.

## 1. Objectif

Aujourd'hui, seul le cycliste profite de l'abri (lot P3). Les bots roulent seuls à puissance fixe : un bot que le cycliste rattrape ne s'accroche jamais à lui, et un groupe de bots ne va pas plus vite qu'un bot seul. Ce lot donne aux bots le même abri que le cycliste, derrière les autres bots et derrière le cycliste. Il ajoute aussi une règle simple de suivi aux bots à profil : on peut alors rouler en groupe, prendre des relais et se faire déposer.

## 2. À lire

1. `docs/lots/00_INDEX.md`, `docs/lots/LOT_P3_aspiration_bots.md`, `docs/lots/LOT_N9_bots_core.md`, `docs/lots/LOT_T12_bots_profil.md`, `docs/lots/LOT_T13_equilibrage_bots.md`.
2. `docs/SRS_v1.1.md` §5.
3. Code : `core/src/openride_core/draft.py`, `bots.py`, `physics.py`, `session.py` (`_update_draft`).

## 3. Prérequis

P3, T12 et T13 livrés.

## 4. Travail demandé

- **Sources d'abri communes.** Dans `draft.py`, une fonction `draft_for(rider_s, sources, …)` sert pour tous : les sources sont les bots `constant` (profil compris) et le cycliste, sauf le coureur lui-même. Le fantôme n'abrite toujours pas et ne s'abrite pas. `best_draft` du cycliste devient un appel de cette fonction, sans changer son résultat (tests de P3 inchangés).
- **Abri des bots.** À chaque pas, chaque bot calcule son abri (même courbe, effet de file, vent de travers, lissage de 1 s), et `ConstantPowerBot.step` le passe à `RiderPhysics.step(alpha_draft=…)`. La poussée vers l'avant (`push_bonus`) vaut aussi pour un bot suivi par un autre bot.
- **Ordre de calcul.** Les abris se calculent sur les positions du pas précédent, pour tous, avant de faire avancer qui que ce soit. Le résultat ne dépend donc pas de l'ordre des bots.
- **Suivi des bots à profil.** Un bot à profil qui arrive à moins de 3 m derrière un coureur garde la roue tant que la puissance nécessaire reste sous sa puissance de stratégie : il baisse sa puissance pour ne pas doubler, au plus jusqu'à 60 % de sa CP. Il repart selon sa stratégie de segment (attaque en montée, sprint) ou si la roue ralentit sous 85 % de sa vitesse de croisière seule. Les bots à puissance constante gardent leur puissance fixe (ils profitent de l'abri en allant plus vite, sans tactique).
- **Calibrage.** `calibrate` (T13) reste calculé sans abri. Le bilan de calibrage dans le cahier T13 dit que l'abri peut faire finir un bot plus tôt quand il roule en groupe.
- **Coût.** 6 coureurs (5 bots et le cycliste) : moins de 0,1 ms par pas de 50 Hz pour tous les abris (mesure sur 10 000 pas dans le test).

## 5. Fichiers concernés

- **Modifiés :** `core/src/openride_core/draft.py`, `core/src/openride_core/bots.py`, `core/src/openride_core/session.py`, `core/tests/test_draft.py`, `core/tests/test_bots.py`, `docs/SRS_v1.1.md` (§5), `docs/SUIVI_AVANCEMENT.md` (une ligne), `docs/lots/00_INDEX.md` (statut).
- **Interdits :** l'engine, le contrat IPC.

## 6. Modifications de contrat autorisées

Aucune. `draft` et `draft_bot` restent ceux du cycliste.

## 7. Critères d'acceptation

1. `(cd core && pytest -q)` passe en entier, tests de P3 compris, sans les modifier.
2. Deux bots à 250 W collés (écart 0,5 m) sur le plat : le second va plus vite qu'un bot seul et reste dans la roue du premier pendant 10 min simulées.
3. Bot à 250 W qui rattrape le cycliste à 240 W : une fois derrière lui, son abri dépasse 0,3 (vérifié sur la valeur interne du bot).
4. Bot à profil derrière le cycliste à 0,9 × sa puissance de stratégie : il reste dans la roue sur le plat, puis attaque dans une montée marquée `climb` quand sa réserve le permet.
5. Le résultat ne dépend pas de l'ordre de la liste des bots (deux ordres, mêmes positions à 1 mm près après 60 s).
6. Fantôme : ni abri donné, ni abri reçu.
7. Coût : moins de 0,1 ms par pas avec 5 bots et le cycliste.
8. ERG : la commande au trainer ne change pas.

**Sur le vélo (le propriétaire) :** séance de 10 min avec 3 bots à 230, 240 et 250 W : ils se regroupent et roulent en file.

## 8. Hors périmètre

Position sur le côté et placement automatique (AS2), bordure (AS3), plafond des groupes (AS4), véhicules et cyclistes du décor (AS6, AS7).
