# Lot V8 – Menu « Garage » : équipement, achats et avatar, aperçu en 3D

## 1. Objectif

Ajouter au menu une section « Garage » pilotée au Click : choisir et acheter cadre, roues et tenues, régler l'avatar, voir la fiche de chaque pièce (masse, CdA, terrain conseillé, niveau, prix, défi) et un aperçu 3D qui tourne.

**Lot interne :** il modifie le menu et la scène ; recette à l'œil.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_V.md` §2.2 et §2.3 ; `LOT_V1_contrat_progression.md` (§4.3, §4.4) ; `LOT_N6_affichage_menus.md`, `LOT_K5_navigation_menus.md` (règles du Click : + / − pour se déplacer, appui long pour valider ou revenir, confirmation des actions irréversibles).
2. Code : `menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `ipc_client.gd`, `devices_view_model.gd` (exemple d'écran ajouté par N13), `avatar_model.gd`, `avatar_view.gd` (V6, V7).

## 3. Prérequis

V1 validé, V11 livré (le core répond aux commandes), V6 livré (V7 souhaité pour l'aperçu des pièces), N6 livré.

## 4. Travail demandé

- **Modèle sans affichage** `engine/scripts/garage_view_model.gd` et son test : écrans « Garage » (Vélo, Tenue, Avatar, Caméra), listes par emplacement depuis le message `garage` (état verrouillé, achetable, possédé, choisi ; tri par niveau), fiche d'une pièce (« Grimpeur — −1,5 kg, CdA = — Conseillé : col — Niveau 5 — 150 pièces »), achat avec confirmation (« Acheter Grimpeur pour 150 pièces ? Solde après : 40 »), refus lisibles pour `item_locked` et `not_enough_coins`.
- **Avatar :** une ligne par réglage, valeur changée par + / − (listes et palettes du contrat), « Enregistrer » envoie `set_avatar` ; « Annuler » rend les valeurs précédentes.
- **Caméra :** choix subjective / suivi (V6), enregistré dans les réglages de l'engine.
- **En-tête :** niveau, barre d'expérience vers le niveau suivant et solde de pièces (depuis `hello_ack`, puis les messages `progression`).
- **Aperçu 3D :** l'avatar équipé tourne lentement à droite du menu ; l'aperçu suit la pièce sélectionnée avant achat.
- **Conseil du parcours :** sur l'écran « Prêt », une ligne « Parcours vallonné : conseillé Polyvalent léger, Profilées » quand l'équipement choisi n'est pas celui conseillé (champ `terrain` de l'élément de `routes`, contrat V1 §4.3, rempli par V11).

## 5. Fichiers concernés

Nouveaux : `garage_view_model.gd`, `garage_view.gd`, leurs tests. Modifiés : `menu_model.gd`, `menu_flow.gd`, `menu_view.gd`, `ipc_client.gd` (`list_garage`, `equip`, `buy`, `set_avatar`, message `garage`), `fake_core.py`, `engine/tests/test_menu_ipc.gd`, `docs/SUIVI_AVANCEMENT.md`.

## 6. Modifications de contrat autorisées

Aucune au-delà de V1.

## 7. Critères d'acceptation

1. Toutes les suites passent ; le modèle est testé sans écran (états, fiches, confirmation, refus, annulation de l'avatar).
2. Avec le faux core : acheter puis choisir une pièce au clavier ou au Click ; solde et aperçu mis à jour par le message `progression`.
3. Pendant une séance, le Garage n'est pas accessible (le core répondrait `busy`).

**Sur le PC cible (le propriétaire) :** tout se règle au Click sans clavier.

## 8. Hors périmètre

Bilan de fin de séance (V9), calculs (core).
