# Lot O33 – Vider le profil d'essai et restaurer un profil supprimé depuis le menu

## 1. Objectif

Audit des options du 31 octobre (`docs/AUDIT_OPTIONS_MENUS_2026-10-31.md`, §7), accepté par le propriétaire le 31 octobre. Deux gestes des profils demandaient encore le terminal ou le gestionnaire de fichiers :

- vider le profil d'essai : `openride-core profil essai --vider` ;
- récupérer un profil supprimé : déplacer son dossier hors de `Profils/.corbeille/` à la main.

## 2. Spécification

| # | Règle |
| --- | --- |
| O33-1 | « Gérer un profil » finit par deux lignes : « Restaurer un profil supprimé » (détail : nombre de profils dans la corbeille ; grisée si elle est vide ou s'il y a déjà huit profils) et « Vider le profil d'essai » (détail : ce qui est effacé). |
| O33-2 | « Vider le profil d'essai » demande une confirmation, avec « Non » par défaut, puis envoie `clear_trial_profile`. Le core efface les séances, les records, le plan, le profil V4 (pièces, Garage) et les caches de `_essai`. Il garde `profil.toml` et la surcharge de progression, comme la commande. Si l'essai est le profil en cours, il est rechargé et un `hello_ack` complet suit. Si un autre OpenRide l'utilise, le core répond `profile_invalid`. |
| O33-3 | « Restaurer un profil supprimé » ouvre la corbeille : les 5 plus récents, avec leur nom et la date de suppression. A maintenu envoie `restore_profile`. Le profil reprend son identifiant et tout son contenu. |
| O33-4 | La restauration est refusée, avec `profile_invalid` et la raison sur la ligne d'état, si l'identifiant ou le nom a été repris entre-temps, ou s'il y a déjà huit profils joueur. |
| O33-5 | Le message `profiles` gagne le champ facultatif `trash` (`{id, name, deleted}`, 5 au plus) ; il reste sous 1 600 octets. Un dossier de la corbeille illisible ou mal nommé est ignoré. |
| O33-6 | Après la réponse, la ligne d'état dit « Profil d'essai vidé » ou « Profil restauré : <nom> ». La restauration ramène à « Gérer un profil ». |

## 3. Contrat

Révision 1.5, ajouts compatibles : commandes `clear_trial_profile` et `restore_profile`, champ `trash` du message `profiles` (`docs/contracts/ipc_v1.md` §4, schémas `cmd` et `profiles`).

## 4. Fichiers

- Core : `profiles.py` (`trash_entries`, `restore`), `session.py` (`_clear_trial`, rechargement du profil en cours dans `_select_profile`, champ `trash`).
- Engine : `profiles_view_model.gd` (lignes, écran RESTORE, messages), `menu_flow.gd`, `main.gd`.
- Docs : contrat et schémas, `GUIDE_UTILISATION.md` §7 (`profil essai --vider` n'y est plus cité), `CLAUDE.md`.
- Tests : `core/tests/test_profils_corbeille.py`, `core/tests/test_contract_ipc.py`, `engine/tests/unit/test_profiles_view_model.gd`.

## 5. Critères d'acceptation

1. `pytest -q` passe dans `core/`, et `run_engine_tests.sh` passe.
2. Supprimer un profil, puis le restaurer depuis « Gérer un profil » : il revient avec son niveau et ses séances.
3. Sur le profil d'essai (Session simulée), « Vider le profil d'essai » remet le niveau à 1 sans relancer.

## 6. Hors périmètre

Vider la corbeille pour de bon (rien n'est effacé définitivement depuis le menu) ; restaurer la sauvegarde de migration `Sauvegardes/`.
