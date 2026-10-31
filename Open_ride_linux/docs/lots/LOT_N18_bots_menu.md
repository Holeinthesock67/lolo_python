# Lot N18 – Bots réglés depuis les menus

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| 1.x série N : bots réglés depuis les menus (réglages et écran de pause) | Python + GDScript | O3, O4 ; O7 utile | Moyenne | Non : interne (contrat et menus), **version 1.x** |

## 1. Objectif

Régler les bots de la séance depuis les menus au lieu de `config.toml` : nombre, puissance de chacun, fantôme, avant la séance dans les réglages, et pendant la séance dans l'écran de pause. Demande du propriétaire du 27 octobre (décision D11 de l'audit de cohérence) : ce réglage passe par les menus, pas par un geste du Click. Version 1.x.

## 2. À lire

1. `docs/SPECIFICATION_GENERALE.md` §5.1 (exigence 1.x-UI-2) et §7.1 ; `docs/SRS_v1.1.md` §13 (bots) ; `docs/lots/LOT_N9_bots_core.md` ; `docs/lots/LOT_O3_reglages_core.md` et `docs/lots/LOT_O4_menu_reglages.md` (réglages au menu) ; `docs/lots/LOT_O7_affichage_bots.md`.
2. Code : `core/src/openride_core/config.py` (section des bots), le module des bots du core (N9), le module des réglages (O3), le menu des réglages (O4).

## 3. Prérequis

La 1.0 publiée ; O3 et O4 fusionnés ; O7 utile pour voir les bots, pas indispensable.

## 4. Travail demandé

- **Réglages (O3, O4) :** nouvelles entrées « Bots » : nombre (0 à 4), puissance de chaque bot en watts ou en % de la FTP, fantôme (aucun, meilleure séance sur ce parcours, séance choisie dans l'historique) ; écrites dans `config.toml` comme les autres réglages.
- **Écran de pause :** mêmes entrées, appliquées à la reprise : un bot ajouté part à la position du cycliste, un bot retiré disparaît, une puissance changée s'applique tout de suite.
- **Contrat :** avant la séance, `list_settings` et `set_setting` (révision 1.3). Pendant la séance, `set_setting` répond `busy` (décision D6 de l'audit IPC) : l'écran de pause envoie donc une commande dédiée `set_bots`, comme `set_difficulty` pour la difficulté (première révision libre à la fusion).
- **Journal :** événement `bots` à chaque changement (liste des bots et puissances).

## 5. Fichiers concernés

- **Modifiés :** `settings.py`, `config.py`, le module des bots, `session.py`, l'écran de pause et le menu des réglages de l'engine, leurs tests, la spécification générale, l'index, le suivi.

## 6. Modifications de contrat autorisées

Nouvelles clés de réglage ; commande `set_bots` (acceptée en `PAUSED`).

## 7. Critères d'acceptation

1. Tests du core et de l'engine au vert.
2. Réglages : trois bots à 180, 220 et 260 W enregistrés, présents à la séance suivante.
3. Écran de pause : un bot retiré n'est plus dans `bots` à la trame suivant la reprise ; le journal le note.
4. Tout se règle au Click selon le §7.1 et au clavier.

## 8. Hors périmètre

Bots à profil (série T, lots T12 et T13).
