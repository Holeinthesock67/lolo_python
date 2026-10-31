# Lot MJ2 – Profil d'essai

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série MJ : profil d'essai `_essai` (séances simulées comptées), `profile_id` au journal, `openride-core profil essai [--vider]`, Session simulée sur `_essai` | Python | MJ1 | Petite | **Livré le 29 octobre** (branche `claude/project-thread-grv91v-mj2`) |

Série MJ, plan `docs/2.0/PLAN_SERIE_MJ.md` §4.

## 1. Objectif

Un profil `_essai` où les séances simulées rapportent expérience et pièces, pour tester la progression, les achats et l'équipement sans jamais toucher le vrai profil. La « Session simulée » du menu roule dessus.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_MJ.md` §2.2, §2.3, §4.
2. `docs/lots/LOT_MJ1_contexte_profil.md`.
3. Code : `profiles.py`, `progression.py` (`ineligible_reason`, `recompute`), `garage.py`, `recorder.py`, `journal.py`, `fit_export.py`, `launcher.py` (`sim_core_cmd`), `tools/xp.py`.

## 3. Prérequis

MJ1.

## 4. Travail demandé

- **`profil.toml` minimal** dans le dossier du profil : `[profil] id`, `nom`, `type` (`joueur` ou `essai`), `cree`, `seances_comptees`. Écrit à la première utilisation de `_essai` (« Profil d'essai », `type = "essai"`, `seances_comptees = ["live", "simulated"]`) ; lu par `ProfileContext`. Un profil sans `profil.toml`, et le contexte historique, valent `type = "joueur"`, `seances_comptees = ["live"]`. Fichier abîmé ou valeur inconnue : erreur lisible (`ProfileContextError`).
- **Séances comptées par donnée** : `progression.recompute` reçoit les sources comptées et l'identifiant du profil ; `ineligible_reason` refuse une source absente de la liste (raison = la source, comme aujourd'hui). Pas de cas particulier ailleurs : pièces, défis et Garage suivent.
- **Journal marqué** : l'en-tête gagne `profile_id` et `profile_type` quand un profil est choisi (rien de changé en contexte historique). Un profil ne compte que les journaux de son identifiant ; un journal sans `profile_id` appartient à un profil `joueur` (journaux d'avant), jamais au profil d'essai. Les journaux écartés sont comptés et signalés par `openride-core xp`.
- **FIT suffixé `_essai`** pour les séances du profil d'essai.
- **Commandes** : `openride-core profil essai` (chemin, séances, niveau, pièces) et `openride-core profil essai --vider` (journaux, FIT, records, plan, profil V4 et caches effacés ; `profil.toml` et `progression.toml` propres au profil gardés) ; `openride-core xp --profil _essai` (option du lot MJ1).
- **Session simulée** (code 65 du lanceur) : le core est relancé avec `--profil _essai` en plus du matériel simulé ; la reprise après plantage cherche alors les journaux du profil d'essai. Le retour au vrai matériel (code 64) revient au profil de départ.

## 5. Fichiers concernés

- **Modifiés :** `profiles.py`, `progression.py`, `garage.py`, `recorder.py`, `fit_export.py`, `session.py`, `launcher.py`, `__main__.py`, `tools/xp.py`, tests associés, `docs/GUIDE_UTILISATION.md` (Session simulée), `docs/OUTILS_DE_TEST.md`, suivi et index.
- **Interdits :** l'engine, le contrat IPC (`hello_ack.config.profile` vient avec MJ6 et MJ7).

## 6. Modifications de contrat autorisées

Aucune. Les deux clés d'en-tête sont du format du journal, pas de l'IPC.

## 7. Critères d'acceptation

1. Séance simulée de 15 min sur `_essai` : `xp_result` non nul et pièces gagnées ; la même séance en contexte historique ou sur un profil `joueur` : refusée (`simulated`), comme aujourd'hui.
2. Journal d'essai copié dans un profil `joueur` : ignoré, avec un avertissement dans `xp`.
3. `profil essai --vider` : progression à zéro, `profil.toml` gardé.
4. `sim_core_cmd` ajoute `--profil _essai` ; la reprise après plantage d'une session simulée retrouve le journal du profil d'essai.
5. `(cd core && pytest -q)` passe en entier.

## 8. Hors périmètre

Campagne accélérée et garde-fou d'empreinte (MJ3) ; bandeau ESSAI à l'écran (MJ8).

## Livraison

Livré le 29 octobre 2026 (branche `claude/project-thread-grv91v-mj2`, empilée sur MJ1).

- `profiles.py` : description `profil.toml` lue par `ProfileContext.for_id` (`type`, `nom`, `cree`, `seances_comptees`, contrôles et `ProfileContextError`), valeurs par défaut en table (`DEFAULTS` pour `_essai`, `PLAYER_DEFAULTS`), `ensure_description` (écrit à la première séance), `owns` (journal du profil), `journal_header`, `fit_suffix`, `clear` (profil d'essai seulement).
- `progression.py` : `recompute(..., counted, owns)` et `ineligible_reason(..., counted)` ; `SessionFacts.profile_id` ; raison `other_profile` ; cache des faits en version 2.
- Journal : `profile_id` et `profile_type` dans l'en-tête (`journal.py`, `recorder.py`, `session.py`), absents sans profil.
- `openride-core profil essai [--vider] [--json]` ; `xp` affiche le profil et le marque « PROFIL D'ESSAI ».
- Lanceur : `SIM_CORE_ARGS` porte `--profil _essai` (tout `--profil` donné est remplacé) ; en session simulée, la reprise cherche les journaux du profil d'essai et `recover` y écrit le FIT.
- Tests : `core/tests/test_profil_essai.py`.
