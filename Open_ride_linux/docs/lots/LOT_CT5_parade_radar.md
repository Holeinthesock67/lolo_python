# Lot CT5 – Parade et rétro-radar : décrocher une sangsue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : parade et rétro-radar : décrocher une sangsue | Python | AS2, CT4 | Petite | Prêt (version 5.0) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Celui qui est en tête voit qu'un poursuivant charge sa catapulte dans sa roue et peut le décrocher en cassant le rythme : il coupe son effort quelques secondes, le poursuivant plus rapide déborde, prend le vent et perd sa charge.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Cahiers AS2, `LOT_T16_ecarts_temps_passage.md` ; code `gaps.py`, `draft.py`, `tactical/catapulte.py`.

## 3. Prérequis

AS2 et CT4 livrés.

## 4. Travail demandé

- **Rétro-radar** : champ `leech` de `state.tactical` : le bot qui reçoit l'abri du cycliste et sa `sling_pct`, mis à jour à 2 Hz.
- **Parade** : aucune règle spéciale. Avec AS2, un suiveur plus rapide de plus de 0,5 m/s à moins de 3 m déborde ; CT4 vide sa charge quand il passe devant. Vérifier que cela suffit ; si le suiveur freine au lieu de déborder, ajouter à `bot_tactics.py` la règle « un bot dont la catapulte charge ne freine pas sous 90 % de sa puissance de stratégie ».
- **Pour le cycliste suiveur** : même chose (le placement automatique d'AS2 le fait déborder).
- **Pas de condition de virage** : la parade marche partout sur le plat.

## 5. Fichiers concernés

- **Modifiés :** `session.py`, `bot_tactics.py` (si nécessaire), tests correspondants, ce cahier, `00_INDEX.md`.
- **Interdits :** l'engine.

## 6. Modifications de contrat autorisées

Aucune : les champs viennent du lot CT1.

## 7. Critères d'acceptation

1. `pytest -q` passe.
2. Bot à 1 m dans la roue, charge à 80 % : le cycliste coupe 2 s, le bot passe devant et sa charge tombe à 0.
3. `leech` présent quand un bot reçoit l'abri du cycliste, absent sinon.

## 8. Hors périmètre

Affichage du radar (CT11).
