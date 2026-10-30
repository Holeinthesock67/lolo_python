# Lot MJ8 – Engine : écrans des profils et bandeau ESSAI

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
