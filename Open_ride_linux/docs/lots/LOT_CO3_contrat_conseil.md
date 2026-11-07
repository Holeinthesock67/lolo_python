# Lot CO3 – Contrat du conseil

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : contrat IPC (`get_coach`, message `coach`), réglages `[coach]`, prochaine course dans le profil | Contrat | CO1 | Petite | En PR (version 5.0, révision 1.6 du contrat) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Ajout compatible au contrat IPC (révision libre à la fusion) pour que l'engine affiche le conseil calculé par le core.

## 2. Travail demandé

- Commande `get_coach {need?}` (besoin forcé facultatif, pour « Choisir un autre besoin ») ; message `coach` d'un seul datagramme (≤ 60 000 octets) : `need`, `rule`, `reason`, `workout` ou `route`, `duration_s`, `tss_estimate`, `alternatives`, `details` (répartition et cibles, CTL, ATL, forme, jours depuis la dernière séance dure, profil de puissance, causes de perte, prochaine course).
- Commande `set_next_race {date, kind}` et `clear_next_race` ; la prochaine course est écrite dans le profil du joueur (`conseil.json`, comme la suggestion de la montre du lot CO8).
- Réglages `[coach] objectif` (`endurance`, `courses`, `grimpeur`) et `[coach] temps_disponible_min` (30 à 120), portée profil (MJ4), dans `settings.py`.
- Schémas `docs/contracts/ipc/*.schema.json`, ligne au journal du contrat, `test_contract_ipc.py`.

## 3. Critères d'acceptation

`pytest -q` passe ; le message `coach` respecte son schéma sur les historiques synthétiques de CO1.

## 4. Réalisation (7 novembre, en PR)

- Révision 1.6 du contrat (la révision libre, ouverte par le lot PL1 ; `CONTRACT_REV` inchangé) : commandes `get_coach {need?}`, `set_next_race {date, kind?}`, `clear_next_race`, `set_watch_advice {type, duration_min?, target_w?}` et `clear_watch_advice` (celles du lot CO8, dans la même révision), toutes avec la réponse `coach` ; schéma `docs/contracts/ipc/coach.schema.json`, tableau des commandes, paragraphe « Séance conseillée » et ligne au journal de `ipc_v1.md`.
- Un seul calcul : `coach.advice_today` sert `openride-core coach` et `get_coach` ; le message `coach` reprend les clés de `--json`, durées en secondes, `route` à `null` jusqu'au lot CO9.
- « Choisir un autre besoin » : règle `CH` (`--besoin` en ligne de commande) ; le conseil du jour reste en première autre idée et sa raison en note.
- Prochaine course : date d'aujourd'hui à un an, type `course` ou `championnat`, gardée dans `conseil.json` du profil en cours jusqu'à son jour (`--prochaine-course AAAA-MM-JJ[:TYPE] --enregistrer`, `--effacer-course`).
- Réglages `[coach] objectif` et `[coach] temps_disponible_min` (30 à 120 min par pas de 15), portée profil, groupe Séance de Réglages (l'écran du conseil du lot CO5 les reprendra) ; défauts de la ligne de commande.
- Tests : `core/tests/test_coach_contrat.py` (schéma du message pour chaque règle, commandes IPC sur un profil fabriqué, saisies refusées, réglages du profil, ligne de commande).

