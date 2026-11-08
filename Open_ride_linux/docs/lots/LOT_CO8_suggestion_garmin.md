# Lot CO8 – Suggestion de la montre Garmin

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Séance conseillée : saisie de la suggestion de la montre Garmin (type, durée, cible), règle RG | Python | CO1, CO3 | Petite | En PR #770 avec CO3 et CO5, complet (version 5.0) |

Série CO (version 5.0, séance conseillée par OpenRide). Plan de la série : `docs/5.0/PLAN_SERIE_CO.md`.

## 1. Objectif

Demande du propriétaire du 7 novembre : entrer dans le jeu l'entraînement suggéré par la montre Garmin, pour que le jeu propose une séance qui y correspond (plan §4 bis).

## 2. Travail demandé

- Correspondance type Garmin → besoin dans `coach.toml` (Repos, Récupération, Fond, Tempo, Seuil, VO2 max, Anaérobie, Sprint), sous-famille gardée pour le choix de l'entraînement.
- Commandes `set_watch_advice {type, duration_min, target_w?}` et `clear_watch_advice` (même révision du contrat que CO3) ; suggestion écrite dans le profil du joueur avec sa date, ignorée dès le lendemain.
- Règle RG dans `coach.py` (déjà écrite par CO1, avec `coach --montre`), avant R0 à R7 : besoin de la montre, durée de la montre à la place du temps disponible, note quand R1 ou R2 divergent ; raison « Suggestion de ta montre : Seuil, 50 min. »
- Aucune connexion à Garmin Connect, aucun identifiant (règle de confidentialité).

## 3. Tests

`core/tests/test_coach.py` : chaque type Garmin donne le besoin attendu ; suggestion de la veille ignorée ; RG avec course hier affiche la note ; « Repos » ne propose pas d'entraînement en premier.

## 4. Critères d'acceptation

`pytest -q` passe ; `openride-core coach --json` rend `rule = "RG"` le jour de la saisie.

## 5. Réalisation (7 novembre, en PR)

- Suggestion gardée pour la journée dans `conseil.json` du profil en cours (`save_watch`, `saved_watch`, `clear_watch` de `coach.py`, écriture sûre, autres clés gardées pour la prochaine course de CO3) ; une suggestion d'un autre jour ou abîmée est ignorée.
- Ligne de commande : `openride-core coach --montre seuil:50 --enregistrer`, puis `openride-core coach` la reprend le même jour ; `--effacer-montre`.
- Sous-famille de la montre : l'entraînement de la zone dominante voulue est choisi d'abord (tempo → Z3, seuil → Z4, VO2 max → Z5).
- Les commandes IPC `set_watch_advice` et `clear_watch_advice` sont écrites avec le contrat du conseil (CO3, révision 1.12 comme `get_coach`, réponse `coach`) pour ne pas ouvrir deux révisions ; l'écran de saisie est dans CO5.
- Écran « Ma montre » du conseil livré avec CO5 (même PR #770) : les huit types de la montre, durée, cible en watts facultative, Enregistrer et Effacer ; captures validées par le propriétaire le 8 novembre. Les huit types sont vérifiés par `test_rg_watch_first_with_notes`. Rien d'autre à faire pour CO8 ; l'usage réel est jugé par la recette CO7 (au moins 3 suggestions de la montre).
