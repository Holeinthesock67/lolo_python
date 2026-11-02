# Lot GP9 – Menu : entrée du mode, réglages et objets

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série GP : entrée « Grand Prix des objets » à l'accueil, écran de réglages et écran des objets désactivables | GDScript | GP2 | Petite | Prêt (version 4.0 proposée) |

Série GP (mode « Grand Prix des objets », demande du propriétaire du 31 octobre 2026). Plan de la série : `docs/4.0/PLAN_SERIE_GP.md`.

## 1. Objectif

Tout régler depuis le menu, sans ligne de commande.

## 2. À lire

`docs/4.0/PLAN_SERIE_GP.md` §4.4 ; `engine/scripts/menu_flow.gd` ; écran des règles du Mode WTF (WTF3).

## 3. Travail demandé

- Entrée visible quand le core annonce le mode ; parcours (circuit et tours, ou distance) ; réglages du §4.4 ; une case par objet ; « Lancer ».
- Navigation au Click et au clavier selon le plan des boutons (§7.1), sans exception.
- Scénario `menu_bench` du mode.

## 4. Critères d'acceptation

1. Réglages repris à la séance suivante.
2. Test `test_options_menus` à jour : chaque réglage `[grandprix]` atteignable par le menu.
