# Lot CT11 – HUD, menus et bilan de la Course tactique

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série CT : hUD, menus et bilan de la Course tactique | GDScript | CT9, CT10 | Grande | Prêt (version 5.0) |

Série CT (version 5.0, mode « Course tactique »). Plan de la série : `docs/5.0/PLAN_SERIE_CT.md`.

## 1. Objectif

Rendre le mode jouable sans terminal : entrée à l'accueil, écran de départ, HUD, pause et bilan, dans la charte cartoon validée.

## 2. À lire

1. `docs/5.0/PLAN_SERIE_CT.md` (décisions du propriétaire du 29 octobre), `docs/SPECIFICATION_GENERALE.md` §6.1 et §7.1, `docs/contracts/ipc_v1.md`.
2. Cahiers `LOT_N15_menu_principal.md`, `LOT_R13_menu_cyber_rogue.md` et `LOT_R11_hud_diegetique.md` (modèles) ; `docs/PRESENTATION_MENUS.md` ; code `engine/scripts/hud*.gd`, menus.

## 3. Prérequis

CT9 validé ; CT10 livré.

## 4. Travail demandé

- **Accueil** : entrée « Course tactique » seulement si `tactical` est dans `modes`.
- **Écran de départ** : circuit (graine ou liste), durée, bots (profils, niveau), intensité des relances, réglage « Effets » ; avertissement « relances en danseuse : vérifiez la fixation du vélo ».
- **HUD** : W′ du cycliste près de la puissance, jauge de capacités à 3 paliers, catapulte sur la jauge en arc au-dessus du bot (choix C), rétro-radar dans le bandeau `bot_behind`, vitesse critique en approche de virage, choix de variante.
- **Pause** (Y) et **bilan** (`summary.tactical`).
- **Guide d'utilisation** : boutons du mode ; banc des menus (scénarios JSON) étendu.

## 5. Fichiers concernés

- **Modifiés :** scripts du HUD et des menus, `docs/GUIDE_UTILISATION.md`, scénarios du banc des menus, ce cahier, `00_INDEX.md`.
- **Interdits :** le core.

## 6. Modifications de contrat autorisées

Aucune.

## 7. Critères d'acceptation

1. Banc des menus au Click, au clavier et à la souris passe.
2. `test_docs_coherence.py` passe (raccourcis du guide).
3. Captures en 1680×1050 et 1024×600 validées par le propriétaire avant fusion.

## 8. Hors périmètre

Classements en ligne.
