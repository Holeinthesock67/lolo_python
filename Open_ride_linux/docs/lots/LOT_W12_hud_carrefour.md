# Lot W12 – Engine : HUD du carrefour et attributions

## 1. Objectif

Montrer à l'approche d'un carrefour les branches possibles (flèche, type de route, pente des 500 premiers mètres), celle que le jeu prendra, le choix du cycliste et le verrouillage (plan §2.3) ; afficher les attributions des données pendant la séance.

## 2. À lire

1. `docs/2.0/PLAN_SERIE_W.md` §2.3, §5.4 et §8 (W-Q1), `LOT_W1_contrat_monde_vivant.md` §4.3 (`state.open_world`).
2. Code : `engine/scripts/hud_view_model.gd`, `hud_view.gd`, `banner.gd`, `ipc_client.gd`, `main.gd`.

## 3. Prérequis

W1 livré.

## 4. Travail demandé

- **Modèle sans affichage** `junction_view_model.gd` : depuis `state.open_world.next`, visible de 300 m à 0 m du carrefour ; jusqu'à 4 branches triées de gauche à droite par angle ; pour chacune : flèche (angle arrondi à 15°), libellé de classe (« grande route », « route », « petite route », « piste cyclable », « chemin revêtu »), pente arrondie à 1 % ; branche par défaut, branche choisie, verrouillage (cadenas, branches non choisies grisées) ; distance au carrefour.
- **Clavier :** ← et → envoient `choose_branch` vers la branche voisine ; le Click passe par le core (W9).
- **Affichage :** panneau en haut au centre, sans masquer le profil d'altitude ni le bandeau ERG ; pente colorée comme le profil du HUD.
- **Attributions :** ligne discrète en bas à droite pendant le monde ouvert (« © OpenStreetMap, OpenMapTiles, Copernicus ») ; crédits complets dans le menu (W11).
- Pas de `class_name`.

## 5. Fichiers concernés

- **Nouveaux :** `engine/scripts/junction_view_model.gd`, `engine/scripts/junction_view.gd`, `engine/tests/unit/test_junction_view_model.gd`.
- **Modifiés :** `engine/scripts/hud_view.gd`, `main.gd` (branchement seulement).

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Tests Godot sans écran passent.
2. Modèle : invisible à 301 m, visible à 300 m ; ordre des branches par angle ; libellés et pentes arrondis comme demandé ; verrouillage reflété ; disparaît après le carrefour.
3. ← puis → depuis la branche par défaut : deux `choose_branch` vers les bonnes branches ; rien quand c'est verrouillé.
4. Panneau, profil d'altitude et bandeau ERG sans recouvrement en 1 920 × 1 080 et 1 280 × 720 (même méthode que `test_banner_layout.gd`).

**Sur le PC (le propriétaire) :** lisibilité en roulant (W16).

## 8. Hors périmètre

Amorces 3D des branches (W10).
