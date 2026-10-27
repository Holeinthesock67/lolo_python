# Lot T11 – Recette de la série T sur le PC et le vélo

## 1. Objectif

Valider ensemble, sur le PC et le home trainer du propriétaire, tout ce qui a été codé sans maquette (décision du 27 octobre : « code d'abord, on validera ensemble avec le reste ») : un sprint, une montée réelle, chaque bonus, une course contre 4 bots à profil.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_T.md`.
2. Cahiers T3, T5, T7 à T10, T12 à T15.
3. `docs/SUIVI_AVANCEMENT.md` (procédure de recette des séries précédentes).

## 3. Prérequis

T3 à T10 et T12 à T15 livrés. Le PC doit être libre (aucun autre essai en cours).

## 4. Travail demandé

Une fiche de recette `docs/RECETTE_SERIE_T.md`, remplie pendant l'essai, avec pour chaque point « fait », « à corriger » et la remarque :

1. **Préparation :** `pytest -q` dans `core/` et `compiler/`, tests Godot sans écran ; compilation d'une trace réelle avec une montée (`openride-compiler build`), fichier `<trace>.segments.toml` avec un sprint manuel, `openride-compiler info`.
2. **Sprint :** panneaux d'approche, portiques, chrono, résultat, record écrit, points du maillot vert.
3. **Montée réelle :** catégorie, écart au record en direct, maillot à pois.
4. **Chaque bonus** (légèreté, aéro, puissance) activé par Z : effet ressenti sur la vitesse, aucun changement de résistance du trainer (sauf supplément de vent avec le bonus aéro), table « avec bonus ».
5. **ERG :** segments chronométrés, aucun bonus.
6. **Course contre 4 bots à profil** au niveau 100 % : encart des voisins, écarts stables dans les montées, grimpeur devant en montée, sprinteur au sprint ; ressenti sur l'équilibrage (T13).
7. **Menus :** écran « Records », option « Bonus » à « non ».
8. **Lisibilité du HUD** à la distance de pédalage ; rendu des lignes et des arches sur la GTX 1060 (budget de T8).
9. **Reprise :** coupure volontaire du core pendant un segment, reprise sans perte des lignes `powerup`, `segment`, `jersey`.

## 5. Fichiers concernés

- **Nouveau :** `docs/RECETTE_SERIE_T.md`.
- Corrections éventuelles : issues séparées, un lot de correction chacune.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Fiche de recette remplie et signée « validé » par le propriétaire.
2. Chaque « à corriger » a son issue.

## 8. Hors périmètre

- Recette des séries R et V.
