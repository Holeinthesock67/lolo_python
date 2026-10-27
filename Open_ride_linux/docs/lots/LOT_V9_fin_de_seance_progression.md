# Lot V9 – Fin de séance : expérience, pièces, temps gagné par l'équipement, niveau et déblocages

## 1. Objectif

Montrer à la fin de chaque séance ce qu'elle a rapporté : expérience par source, pièces, temps gagné ou perdu grâce à l'équipement, passage de niveau, pièces débloquées et défis réussis.

**Lot interne :** il modifie l'écran de fin de séance ; recette à l'œil.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.1, §2.1 bis, §2.2 (« un gain compté ») ; `LOT_V1_contrat_progression.md` §4.2 ; `LOT_N4_modele_fin_seance.md`.
2. Code : `summary_view_model.gd`, `summary_view.gd`, `menu_model.gd`, `banner.gd`, `ipc_client.gd`.

## 3. Prérequis

V1 validé, V11 livré, N4 et N6 livrés.

## 4. Travail demandé

- **Modèle sans affichage** `engine/scripts/progress_view_model.gd` et son test : à partir du message `xp_result`, lignes `{label, value}` dans l'ordre du plan (« Distance 30,2 km — 604 XP », « Entraînement terminé — +120 XP »…), total, pièces (« +30 pièces — solde 240 »), temps de l'équipement (« Équipement : −42 s sur la séance », ligne absente si `null`), barre d'expérience avant et après, passage de niveau, déblocages et défis ; séance refusée : une seule ligne explicative (« Séance de moins de 5 minutes : pas d'expérience »). Format français, comme N4.
- **Affichage :** bloc « Progression » sous le bilan de N4 ; bandeau « Niveau 12 ! » et liste « Débloqué : cadre Aéro » quand c'est le cas ; animation courte de la barre d'expérience (coupée en qualité basse si elle coûte).
- **Menu de fin :** élément « Aller au Garage » quand une pièce est devenue achetable.

## 5. Fichiers concernés

Nouveaux : `progress_view_model.gd`, son test. Modifiés : `summary_view.gd`, `summary_view_model.gd` (menu de fin), `ipc_client.gd` (lecture de `xp_result`), `fake_core.py`, tests graphiques, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune au-delà de V1.

## 7. Critères d'acceptation

1. Toutes les suites passent ; le modèle couvre : séance SIM, séance ERG terminée, séance refusée, passage de niveau, niveau 50 (pas de seuil suivant), message `xp_result` absent (rien d'affiché, bilan de N4 inchangé).
2. Capture du faux core en fin de séance : bloc « Progression » lisible, bandeau de niveau présent quand `level_after` > `level_before`.

**Sur le PC cible (le propriétaire) :** relecture du bilan après une vraie séance.

## 8. Hors périmètre

Calcul (core), Garage (V8).
