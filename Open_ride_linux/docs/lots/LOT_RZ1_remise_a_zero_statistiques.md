# Lot RZ1 – Remettre à zéro les statistiques d'un profil, avec sauvegarde et annulation

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Profils : « Remettre à zéro mes statistiques » et « Annuler la remise à zéro » dans « Gérer : <profil en cours> » (commandes `reset_profile_stats`, `undo_profile_reset`, champ `resets` de `profiles`, révision 1.31) | Python + GDScript | MJ7, MJ8, O33 (livrés) | Petite | En PR (22 novembre) |

## 1. Objectif

Demande du propriétaire du 22 novembre 2026 : démarrer la ligue d'hiver (série CH) le week-end du 28 novembre avec
un profil remis à zéro, la remise à zéro étant faite par lui-même juste avant de créer la saison. Elle doit être sûre
(sauvegarde automatique avant) et réversible.

Périmètre : le 22 novembre, le propriétaire a d'abord choisi « Tout le profil sportif » sur la carte de ce fil
(10 h 59), puis validé à 11 h 42 (« Ok go », fil de l'audit de cohérence du 22 novembre) un périmètre qui garde
l'historique du coach, les FIT et la cote du cycliste. Une carte de décision a départagé les deux ; ce cahier décrit
la variante recommandée « garder coach, FIT et mon Elo » (voir la livraison pour le choix final).

## 2. Spécification

| # | Règle |
| --- | --- |
| RZ1-1 | Date de départ des statistiques : la remise écrit `remise_stats.toml` (`[remise] depuis`, horodatage) dans le profil ; `ProfileContext.stats_since` la lit et `progression.recompute(since=…)` ne fait plus rien rapporter aux séances commencées avant (`before_reset`) : niveau, expérience, pièces, défis et cartes repartent de la remise. Les journaux et FIT restent en place (historique, coach, charge des 4 dernières semaines, estimation de W'). |
| RZ1-2 | Gardés (`profiles.KEPT_ON_RESET`) : `profil.toml` (nom, FTP, poids, FC max, réglages du joueur), `progression.toml`, `.verrou`, `derniers_choix.json`, `plan_state.toml`, `Activities/`, `.cache/`, `conseil.json`, `remise_stats.toml`. Tout le reste est mis de côté : records, profil V4 (équipement acheté, vies : le solde de pièces repart de zéro sans dette), cartes vues, ligue, segments du monde ouvert et tout fichier ajouté plus tard au profil. |
| RZ1-3 | Rien n'est effacé : ce qui est mis de côté est DÉPLACÉ dans `~/OpenRide/Profils/.remises_a_zero/<id>_AAAAMMJJ-HHMMSS/`, avec `remise.toml` (profil, date, type, liste) et une copie des fichiers gardés (`_gardes/`, dont l'ancienne date de départ). Deux sauvegardes dans la même seconde prennent la seconde suivante. |
| RZ1-4 | Cote Elo : celle du cycliste et son nombre de courses sont gardés, les écarts des bots et l'historique repartent de zéro (`ELO_KEEPS_RIDER`) ; l'ancien `elo.json` est dans la sauvegarde. |
| RZ1-5 | Profil en cours seulement, hors séance (`busy` sinon), confirmation exigée par le core (`"confirmed": true`, sinon `bad_args`). Refus `profile_invalid` : profil d'essai (il se vide, lot O33), sans profil. Une copie de la même commande ne fait pas de seconde remise. |
| RZ1-6 | Annulation : ce qui a été mis de côté depuis la remise est d'abord sauvegardé à son tour (type « annulation », listé seulement par la ligne de commande), puis ce que la remise avait mis de côté revient et la date de départ redevient celle d'avant. Séances, FTP et réglages d'aujourd'hui ne bougent pas. Après une remise ou une annulation, le profil est rechargé et un `hello_ack` complet suit, puis `profiles` avec `resets` (3 remises au plus, `{id, date, time}`), sous 1 600 octets. |
| RZ1-7 | Menu : « Gérer : <profil> » gagne « Remettre à zéro mes statistiques » (détail « sauvegarde faite avant, annulable » ; grisée avec « choisir ce profil d'abord » pour un autre profil) et, après une remise, « Annuler la remise à zéro » (détail « remise du JJ/MM à HH:MM »). |
| RZ1-8 | Confirmations aux mots écrits, « Non » par défaut, boutons courts (la boîte coupe les libellés longs) : « Remettre à zéro les statistiques de « <nom> » ? Niveau, pièces, cartes et records repartent de zéro. Séances, FTP, réglages et cote Elo gardés. Sauvegarde faite avant. », boutons « Non, garder mes statistiques » et « Oui, remettre à zéro » ; annulation : « Annuler la remise à zéro du JJ/MM à HH:MM ? Les statistiques d'avant reviennent ; les séances courues depuis comptent aussi. », boutons « Non, garder la remise » et « Oui, annuler la remise ». Ligne d'état : « Sauvegarde puis remise à zéro… », puis « Statistiques remises à zéro (sauvegarde faite) » ou « Statistiques d'avant remises en place ». |
| RZ1-9 | Ligne de commande : `openride-core profil remise-a-zero | remises [--json] | annuler-remise SAUVEGARDE` (`--profil ID`), refusée pendant une séance du profil (verrou). |

## 3. Contrat

Révision 1.31 (les 1.24 à 1.30 sont prises ou réservées par d'autres lots), ajouts compatibles : commandes
`reset_profile_stats` et `undo_profile_reset`, champ facultatif `resets` du message `profiles`
(`docs/contracts/ipc_v1.md` §4, schémas `cmd` et `profiles`).

## 4. Fichiers

- `core/src/openride_core/profiles.py` : `reset_stats`, `reset_entries`, `undo_reset`, `KEPT_ON_RESET`, `stats_since`.
- `core/src/openride_core/progression.py` (`recompute(since=…)`) et ses appelants (`garage.py`, `ipc_lists.py`, `tools/xp.py`, `tools/collection.py`, `tools/campagne_profil.py`).
- `core/src/openride_core/session.py` : commandes, rechargement, `resets` dans `profiles`.
- `core/src/openride_core/__main__.py` : sous-commandes `profil remise-a-zero | remises | annuler-remise`.
- `engine/scripts/profiles_view_model.gd`, `menu_flow.gd`, `main.gd`, `menu_model.gd` (confirmation aux boutons écrits).
- Tests : `core/tests/test_profil_remise_a_zero.py` (dans le `~/OpenRide` temporaire, jamais le vrai profil),
  `engine/tests/unit/test_profiles_view_model.gd`.

## 5. Recette

Captures du seul écran « Gérer : <profil> » et des deux confirmations, en low, medium et high (PR de menus), à valider
par le propriétaire avant fusion. Sur le PC, le samedi 28 novembre : remise à zéro depuis le menu, puis création de la
saison de la ligue.

Série PP (courbe de puissance, records de puissance, trophées) : ses recalculs devront lire `ctx.stats_since`
comme `progression.recompute` pour repartir de la remise (à faire dans la pile PP ou juste après sa fusion).
