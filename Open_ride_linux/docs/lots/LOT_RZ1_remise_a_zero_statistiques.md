# Lot RZ1 – Remettre à zéro les statistiques d'un profil, avec sauvegarde et annulation

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Profils : « Remettre à zéro mes statistiques » et « Annuler la remise à zéro » dans « Gérer : <profil en cours> » (commandes `reset_profile_stats`, `undo_profile_reset`, champ `resets` de `profiles`, révision 1.31) | Python + GDScript | MJ7, MJ8, O33 (livrés) | Petite | En PR (22 novembre) |

## 1. Objectif

Demande du propriétaire du 22 novembre 2026 : démarrer la ligue d'hiver (série CH) le week-end du 28 novembre avec
un profil remis à zéro, la remise à zéro étant faite par lui-même juste avant de créer la saison. Elle doit être sûre
(sauvegarde automatique avant) et réversible.

Périmètre choisi par le propriétaire le 22 novembre (carte « Que remettre à zéro dans ton profil avant la ligue ? »,
réponse « Tout le profil sportif ») : niveau, expérience et pièces sont recalculés depuis les séances, ils repartent
donc de zéro avec elles.

## 2. Spécification

| # | Règle |
| --- | --- |
| RZ1-1 | Remis à zéro : tout le dossier du profil sauf les fichiers gardés : séances et journaux (`Activities/`), records (`records.json`), courbe de puissance et caches (`.cache/`), cote Elo (`elo.json`, retour à 1 500 et courses de rodage), profil V4 (`profile.json` : équipement acheté, vies), cartes vues, conseil du jour, ligue (`ligue.json`) et tout fichier ajouté plus tard au profil. |
| RZ1-2 | Gardés (`profiles.KEPT_ON_RESET`) : `profil.toml` (nom, FTP, poids, FC max, réglages du joueur), `progression.toml`, `.verrou`, `derniers_choix.json` (derniers choix du menu), `plan_state.toml` (plan actif). |
| RZ1-3 | Rien n'est effacé : tout est déplacé dans `~/OpenRide/Profils/.remises_a_zero/<id>_AAAAMMJJ-HHMMSS/`, avec `remise.toml` (profil, date, liste) et une copie des fichiers gardés (`_gardes/`). |
| RZ1-4 | Profil en cours seulement, hors séance (`busy` sinon). Refus `profile_invalid` : profil d'essai (il se vide, lot O33), sans profil, rien à remettre à zéro, deux remises dans la même seconde. Une copie de la même commande ne fait pas de seconde remise. |
| RZ1-5 | Annulation : les statistiques courues depuis la remise sont d'abord mises de côté dans une nouvelle sauvegarde (annulable à son tour), puis celles de la remise reviennent. Les fichiers gardés (FTP changée depuis, par exemple) ne changent pas. |
| RZ1-6 | Après une remise ou une annulation, le profil est rechargé (progression, records, Elo, plan) et un `hello_ack` complet suit, puis `profiles` avec `resets` (3 au plus, `{id, date, time}`, les plus récentes d'abord), sous 1 600 octets. |
| RZ1-7 | Menu : « Gérer : <profil> » gagne « Remettre à zéro mes statistiques » (détail « sauvegarde faite avant, annulable » ; grisée avec « choisir ce profil d'abord » pour un autre profil) et, après une remise, « Annuler la remise à zéro » (détail « remise du JJ/MM à HH:MM »). |
| RZ1-8 | Confirmations aux mots écrits, « Non » par défaut, boutons courts (la boîte coupe les libellés longs) : « Remettre à zéro les statistiques de « <nom> » ? Séances, records, Elo, niveau et pièces repartent de zéro. FTP et réglages gardés. Sauvegarde faite avant. », boutons « Non, garder mes statistiques » et « Oui, remettre à zéro » ; annulation : « Annuler la remise à zéro du JJ/MM à HH:MM ? Les statistiques d'avant reviennent ; les séances courues depuis sont mises de côté. », boutons « Non, garder la remise » et « Oui, annuler la remise ». Ligne d'état : « Sauvegarde puis remise à zéro… », puis « Statistiques remises à zéro (sauvegarde faite) » ou « Statistiques d'avant remises en place ». |
| RZ1-9 | Ligne de commande : `openride-core profil remise-a-zero | remises [--json] | annuler-remise SAUVEGARDE` (`--profil ID`), refusée pendant une séance du profil (verrou). |

## 3. Contrat

Révision 1.31 (les 1.24 à 1.30 sont prises ou réservées par d'autres lots), ajouts compatibles : commandes
`reset_profile_stats` et `undo_profile_reset`, champ facultatif `resets` du message `profiles`
(`docs/contracts/ipc_v1.md` §4, schémas `cmd` et `profiles`).

## 4. Fichiers

- `core/src/openride_core/profiles.py` : `reset_stats`, `reset_entries`, `undo_reset`, `KEPT_ON_RESET`.
- `core/src/openride_core/session.py` : commandes, rechargement, `resets` dans `profiles`.
- `core/src/openride_core/__main__.py` : sous-commandes `profil remise-a-zero | remises | annuler-remise`.
- `engine/scripts/profiles_view_model.gd`, `menu_flow.gd`, `main.gd`, `menu_model.gd` (confirmation aux boutons écrits).
- Tests : `core/tests/test_profil_remise_a_zero.py` (dans le `~/OpenRide` temporaire, jamais le vrai profil),
  `engine/tests/unit/test_profiles_view_model.gd`.

## 5. Recette

Captures du seul écran « Gérer : <profil> » et des deux confirmations, en low, medium et high (PR de menus), à valider
par le propriétaire avant fusion. Sur le PC, le samedi 28 novembre : remise à zéro depuis le menu, puis création de la
saison de la ligue.
