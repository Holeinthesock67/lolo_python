# Lot SV1 – Copies automatiques du profil et « Restaurer une sauvegarde »

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Profils : copie complète de chaque profil de joueur chaque semaine, avant les mises à jour et avant la remise à zéro, rotation, « Restaurer une sauvegarde » dans « Gérer : <profil en cours> » (commandes `list_profile_backups`, `restore_profile_backup`, message `profile_backups`, révision attribuée à la fusion) | Python + GDScript + Bash | RZ1 (#991) | Moyenne | En PR (23 novembre) |

## 1. Objectif

Audit de cohérence du 22 novembre 2026, lot validé par le propriétaire (« Ok lance tout ») : protéger le profil avant la
ligue d'hiver et les mises à jour. Cadrage : `/mnt/project-files/plans/CADRAGE_SV1_SAUVEGARDE_AUTO_2026-11-22.md`.

## 2. Spécification

| # | Règle |
| --- | --- |
| SV1-1 | Copie d'un profil de joueur (jamais le profil d'essai) : `~/OpenRide/Sauvegardes/profils/<id>/<AAAAMMJJ-HHMMSS>_<raison>/`, tout le dossier du profil sauf le verrou et `.cache/` (recalculé), avec `copie.toml` (profil, nom, raison, date, séances). Écrite dans un dossier `.tmp` renommé à la fin ; une copie en échec est effacée. |
| SV1-2 | Fichier identique (taille et date de modification) au même fichier de la copie précédente : lien dur vers cette copie précédente, jamais vers le fichier vivant (un journal complété en place ne change aucune copie). Huit copies hebdomadaires tiennent dans un seul dossier, à peu près la place d'un profil et des séances de la saison. |
| SV1-3 | Raisons et rotation (`profile_backups.REASONS`) : `semaine` 8 (une saison), `mise-a-jour` 3, `remise-a-zero` 3, `restauration` 3 ; au-delà, les plus anciennes de la même raison sont effacées, dans le dossier des copies du profil seulement. |
| SV1-4 | `semaine` : au lancement du core (`CoreSession.run`), dans un fil, si la dernière copie `semaine` a 7 jours ou plus et que le profil a autre chose que `profil.toml`. Une erreur est journalisée, le jeu continue. |
| SV1-5 | `mise-a-jour` : `scripts/update.sh` lance `openride-core profil sauvegarde --tous --raison mise-a-jour` (core d'avant la mise à jour) avant le `git pull`, seulement s'il y a une mise à jour et un dossier `Profils/`. Programme absent ou copie en échec : mise à jour refusée, rien changé, message en mots (lancer `install.sh`, ou libérer de la place). |
| SV1-6 | `remise-a-zero` : copie complète juste avant `reset_profile_stats` (RZ1, qui garde son propre « Annuler la remise à zéro »). |
| SV1-7 | Restauration (`restore_profile_backup {id, confirmed: true}`, hors séance, profil en cours) : copie `restauration` de l'état actuel d'abord, puis tout le dossier du profil (verrou excepté) remplacé par une copie (jamais un lien dur) des fichiers de la copie, réglages et FTP compris. Erreur en route : état d'avant remis. Puis profil rechargé, `hello_ack` complet, `profiles` et `profile_backups`. Sans `confirmed` : `bad_args` ; copie inconnue ou d'un autre profil : `profile_invalid`. |
| SV1-8 | `list_profile_backups` (à tout moment) : message `profile_backups` (`profile`, `items` : au plus 16 `{id, reason, date, time, sessions}`, les plus récentes d'abord). |
| SV1-9 | Menu : « Gérer : <profil> » finit par « Restaurer une sauvegarde » (détail « copie faite chaque semaine » ; grisée avec « choisir ce profil d'abord » pour un autre profil). Liste : « Copie de la semaine, dim. 22/11 à 13:05 », « Avant la mise à jour, … », « Avant la remise à zéro, … », « Avant une restauration, … », détail « 42 séances » ; vide : « Aucune copie pour l'instant ». Confirmation, « Non » par défaut : « Restaurer la copie du dim. 22/11 à 13:05 ? Ton profil revient à cet état (réglages et FTP compris). Ton profil actuel est sauvegardé avant. », boutons « Non, garder mon profil » et « Oui, restaurer ». Ligne d'état : « Copie du profil actuel puis restauration… », puis « Sauvegarde restaurée (profil d'avant copié) » et retour à « Gérer ». |
| SV1-10 | Ligne de commande : `openride-core profil sauvegarde [--tous] [--raison R] | sauvegardes [--json] | restaurer COPIE` (`--profil ID`) ; restauration refusée pendant une séance du profil (verrou). |

## 3. Contrat

Ajouts compatibles : commandes `list_profile_backups` et `restore_profile_backup`, message `profile_backups`
(`docs/contracts/ipc_v1.md`, schémas `cmd` et `profile_backups`). Numéro de révision pris à la fusion, au-dessus de main.

## 4. Fichiers

- `core/src/openride_core/profile_backups.py` (nouveau), `session.py`, `__main__.py`, `scripts/update.sh`.
- `engine/scripts/profiles_view_model.gd`, `menu_flow.gd`, `main.gd`, `ipc_client.gd`.
- Tests : `core/tests/test_profil_sauvegardes.py` (`~/OpenRide` temporaire), `engine/tests/unit/test_profiles_view_model.gd`,
  scénario de banc des menus `engine/tests/menu_scenarios/profils_sauvegardes.json`.

## 5. Recette

Captures de « Gérer », de la liste des copies et de la confirmation, en low, medium et high, à valider par le
propriétaire ; banc PC medium seul (PR de menus). Défauts à lui montrer : 8 copies hebdomadaires, restauration avec FTP et
réglages de la copie.
