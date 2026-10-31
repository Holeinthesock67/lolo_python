# Lot MJ8 – Engine : écrans des profils et bandeau ESSAI

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série MJ : écrans « Qui roule ? », nom du profil, gestion, bandeau ESSAI (maquettes A à F validées) | GDScript | MJ7 | Moyenne | **Livré le 30 octobre** (branche `claude/project-thread-grv91v-mj8b`), captures low, medium et high à valider sur le PC avant fusion |

Série MJ, plan `docs/2.0/PLAN_SERIE_MJ.md` §3 et §4.4 ; maquettes A à F validées le 29 octobre (https://claude.ai/artifact/GhbjhMXyyb5GALuhhqoMqj).

## 1. Objectif

Écran « Qui roule ? » (A, seulement avec au moins deux profils joueurs), ligne « Profil » de l'accueil (B), profil créé (C), bandeau ESSAI au HUD (D), saisie du nom au Click, au clavier et à la souris (E), gestion : renommer, supprimer avec confirmation « Non » par défaut (F).

## 2. À lire

Maquettes ; plan §3.1 et §3.3 ; spécification §7.1 (boutons) ; `menu_model.gd`, `docs/PRESENTATION_MENUS.md`.

## 3. Prérequis

MJ7 ; maquettes validées (fait).

## 4. Travail demandé

- Mêmes boutons que les autres menus, aucun bouton nouveau : + / − pour choisir, A maintenu pour valider, Y pour revenir ; dans la grille de lettres, Z écrit la lettre et Y efface ; + et − maintenus sautent d'une ligne.
- Titre « OpenRide — <nom> » ; « OpenRide — PROFIL D'ESSAI » et bandeau « ESSAI » sur le profil d'essai.
- Scénarios `menu_bench` (Click, clavier, souris) et captures `visual_check`.

## 5. Fichiers concernés

Scripts de menu de l'engine, `menu_bench`, tests unitaires de l'engine ; interdits : le core.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Scénarios du banc des menus verts au Click, au clavier et à la souris.
2. **Captures montrées au propriétaire en low, medium et high avant fusion.**

## 8. Hors périmètre

Recette sur le PC (MJ10).

## Livraison

Livré le 30 octobre 2026 (branche `claude/project-thread-grv91v-mj8b`, empilée sur MJ7). **Captures low, medium et high à montrer au propriétaire avant fusion** (sur le PC, via la file des mesures).

- `profiles_view_model.gd` : « Qui roule ? » (profil en cours en premier et présélectionné, niveau et dernière séance, « Nouveau profil » sous huit profils, « Gérer un profil »), grille du nom (46 cases : lettres, é è ê à ç ô ï ü, tiret, espace, chiffres, puis « Effacer » et « Valider » ; majuscule en début de mot ; 16 caractères au plus ; nom proposé « Cycliste N »), gestion (renommer, supprimer : le profil en cours et le dernier profil sont grisés), titres et bandeau du profil d'essai, erreurs `name_invalid`, `profile_invalid` et `busy` sur la ligne d'état.
- `menu_flow.gd` : écrans `profiles`, `profile_name`, `profile_manage_list`, `profile_manage` ; « Qui roule ? » après l'écran de connexion avec au moins deux profils joueur (jamais sur le profil d'essai) ; ligne « Profil : … » en tête de l'accueil ; nouveau `hello_ack` d'un autre profil : retour à l'accueil.
- Écart à la maquette F : « Gérer » s'ouvre par la ligne « Gérer un profil » de « Qui roule ? » puis le profil, pour garder « un seul A maintenu » sur le profil présélectionné (plan §3.1).
- `menu_view.gd` : grille à la place de la liste (cases cliquables) ; `button_help.gd` : aide de la grille (Z Écrire, Y Effacer ; au clavier, lettres et Retour arrière).
- `main.gd` : commandes `list_profiles`, `select_profile`, `create_profile`, `rename_profile`, `delete_profile` ; liste demandée à chaque `hello_ack` ; titre de la fenêtre ; bandeau « ESSAI » en haut du HUD ; saisie du nom au clavier ; un clic sur la grille écrit la lettre. `ipc_client.gd` : message `profiles`.
- Tests : `engine/tests/unit/test_profiles_view_model.gd`, scénario `engine/tests/menu_scenarios/profils.json` (Click, clavier, souris).
