# Lot FB1 – Filet de la boucle du core : une erreur d'un mode termine la séance, le core continue

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 2.x série FB : erreur d'un mode de jeu attrapée dans la boucle à 50 Hz, séance enregistrée avec son bilan | Python | N8 | Petite | **Livré le 25 novembre** (PR #1022) |

## 1. Objectif

Audit du 22 novembre (constats R3 et L10, validés par le propriétaire) : la boucle à 50 Hz (`CoreSession._loop`)
appelait `_step` et les remplissages de la trame des modes sans filet. Une exception dans un mode (Cyber-Rogue, WTF,
Dernier survivant, Grand Prix, Course, piste, monde ouvert) arrêtait tout le core ; le lanceur le relançait, mais la
reprise (`resume.py`) ne restaure pas les courses. La ligue d'hiver ajoute du code dans cette boucle : le filet passe
avant elle.

## 2. Travail fait

- `session.py` :
  - `_safe_step` appelle `_step` sous filet ; `_fill_mode_frames` regroupe les bots et les `_fill_*_frame` de la trame,
    sous le même filet ;
  - `_mode_failed` : pile au journal du core, ligne de jeu `mode_error` (mode, endroit `pas` ou `trame`, type et
    message de l'erreur) au journal de la séance, séance terminée par le `_finish(True)` habituel (FIT, bilan,
    expérience, records : une séance normale, état `FINISHED`), champ `summary.mode_error`, erreur IPC `mode_failed`
    avec le message « Le mode a rencontré une erreur, ta séance est enregistrée. » (bandeau d'erreur existant de
    l'engine, aucun écran ne change) ;
  - si `_finish` échoue aussi : `_drop_modes` ferme le journal, vide les modes et passe en `ERROR`, le core continue
    (message « Le mode a rencontré une erreur, le jeu continue. ») ;
  - une suite d'erreurs (moins d'une seconde entre deux) ne donne qu'un message et qu'une pile ; hors séance, une suite
    de plus de 5 s (`MODE_FAIL_LIMIT_S`) remonte : un core relancé vaut mieux qu'un core vivant et bloqué ;
  - une erreur du trainer (`driver.poll`) n'est pas attrapée : le lanceur relance le core, comme avant.
- Revue de code du 22 novembre : journal impossible à ouvrir au départ (disque plein, dossier protégé) : la séance
  ne roule plus sans journal, elle attend en pause (`recording_failed`) ; `resume` rouvre le journal ou refuse en mots.
- `journal.py` : `mode_error` ajouté à `GAME_KINDS`.
- Contrat IPC (`ipc_v1.md` §6 et §8, `state.schema.json`) : code `mode_failed`, `summary.mode_error` ; numéro de
  révision pris à la fusion.

## 3. Liens

- Reprise (`resume.py`, lot N8) : `_finish` écrit l'événement `stop`, le journal est terminé et le lanceur ne tente pas
  de reprise ; rien ne change dans `resume.py`.
- Ligue d'hiver (CH3) : une manche coupée par une erreur n'a pas d'arrivée, `_league_finish` ne compte rien et la manche
  se recourt dans la semaine, comme une manche plantée. Aucun changement de CH3 ; test
  `test_round_cut_by_mode_error_stays_open` (`test_league_session.py`).

## 4. Tests

`core/tests/test_mode_error_net.py` : mode qui lève une exception au pas (séance `FINISHED`, FIT écrit, bilan du mode
gardé, `mode_error` au bilan et au journal, journal terminé par `stop`, un seul message, nouvelle séance possible), à la
trame, erreur du trainer non attrapée, fin de séance qui échoue (`ERROR`, modes vidés), erreur répétée hors séance
(remonte après 5 s), journal impossible à ouvrir au départ (pause, puis reprise une fois le dossier rendu). Core pur : CI et cloud, pas de banc PC.

## Livraison

Fusionné dans `main` le 25 novembre 2026 (PR #1022), relevé par la passe de doc du 27 novembre 2026 (statut précédent : « **En revue** (22 novembre) »).
