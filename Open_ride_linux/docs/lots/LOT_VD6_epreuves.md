# Lot VD6 – Épreuves de piste

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série VD : épreuves de piste en modules purs (toutes : poursuite, kilomètre, 200 m, scratch, points, tempo, élimination, keirin, omnium, heure) | Python | VD3, DS1, AS6 | Grande | À valider (version 4.0 proposée) |

Série VD (modèle « Vélodrome », demande du propriétaire du 5 novembre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_VD.md`. Rien ne se code avant la validation du plan par le propriétaire (lot VD0).

## 1. Objectif

Écrire les règles de toutes les épreuves du §5 (décision du propriétaire du 6 novembre : toutes dès la première livraison) dans un paquet `track/` du core, un fichier par épreuve, et les brancher dans la séance.

## 2. À lire

§5 du plan ; `core/src/openride_core/survivor.py` (élimination), `wtf/mode.py` (forme d'un mode), `replay.py` (fantôme), `records.py`, `jerseys.py` (barème) ; cahier AS6 (véhicule et abri, pour le derny du keirin).

## 3. Travail demandé

- Paquet `track/` : `pursuit.py`, `time_trial.py` (kilomètre, 500 m, 200 m lancé), `scratch.py`, `points.py`, `tempo.py`, `elimination.py` (règles de DS, sans copie de code), `keirin.py` (derny d'AS6 qui s'écarte à 3 tours de l'arrivée), `omnium.py` (enchaîne les épreuves et additionne les points), `hour.py` ; interface commune (`start`, `step`, `frame`, `summary`).
- Départ arrêté et départ lancé ; tours, cloche du dernier tour ; tours pris ; arrivée.
- Records par piste et par épreuve ; tours dans le journal et dans le FIT (`lap`).
- Pause et coupure du trainer figent l'épreuve.

## 4. Critères d'acceptation

1. Chaque épreuve a ses tests positifs et négatifs (course simulée de bout en bout, même graine, même résultat).
2. Trame `track` sous le budget de VD1.
3. Aucune épreuve ne renvoie de pente (test).

## 5. Fichiers touchés

- `core/src/openride_core/track/` (nouveau), `session.py`, `records.py`, `fit_export.py`, leurs tests.

Tout lot qui change l'affichage est mesuré en `low`, `medium` et `high` (budgets GPU : 6, 12 et 14 ms) et ses captures sont validées par le propriétaire avant la fusion.
