# Lot CO3 – Contrat du conseil

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : contrat IPC (`get_coach`, message `coach`), réglages `[coach]`, prochaine course dans le profil | Contrat | CO1 | Petite | Prêt (version 5.0, décision du propriétaire) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Ajout compatible au contrat IPC (révision libre à la fusion) pour que l'engine affiche le conseil calculé par le core.

## 2. Travail demandé

- Commande `get_coach {need?}` (besoin forcé facultatif, pour « Choisir un autre besoin ») ; message `coach` d'un seul datagramme (≤ 60 000 octets) : `need`, `rule`, `reason`, `workout` ou `route`, `duration_s`, `tss_estimate`, `alternatives`, `details` (répartition et cibles, CTL, ATL, forme, jours depuis la dernière séance dure, profil de puissance, causes de perte, prochaine course).
- Commande `set_next_race {date, kind}` et `clear_next_race` ; la prochaine course est écrite dans le profil du joueur (`profile.py`).
- Réglages `[coach] objectif` (`endurance`, `courses`, `grimpeur`) et `[coach] temps_disponible_min` (30 à 120), portée profil (MJ4), dans `settings.py`.
- Schémas `docs/contracts/ipc/*.schema.json`, ligne au journal du contrat, `test_contract_ipc.py`.

## 3. Critères d'acceptation

`pytest -q` passe ; le message `coach` respecte son schéma sur les historiques synthétiques de CO1.
