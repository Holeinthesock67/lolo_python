# Lot AS5 – Ressentir l'abri : son, watts économisés, bilan

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série AS : ressentir l'abri (souffle plus faible, watts économisés au HUD, temps et énergie au bilan) | Python + GDScript | P3, P10, P17 | Moyenne | En PR le 31 octobre (#640, version 2.0) : captures à valider, essai sur le vélo |

Série AS, version 2.0 (décision du propriétaire du 29 octobre 2026).

## 1. Objectif

On voit déjà l'abri (pastille « Abri 30 % », jauge au-dessus du bot de la PR #566). Ce lot le fait aussi entendre et mesurer : le souffle du vent baisse dans la roue, le HUD dit combien de watts on économise, et le bilan de fin de séance dit combien de temps on a passé dans la roue et l'énergie gagnée.

## 2. À lire

`docs/lots/LOT_P3_aspiration_bots.md`, `LOT_P10_sons_velo.md` (son du vent selon la vitesse de l'air), `docs/AUDIO.md` ; code `session.py`, `tools/session_summary.py`, `engine/scripts/wind_view_model.gd`, `hud_view.gd`, le son du vent de P10.

## 3. Prérequis

P3, P10 et P17 livrés ; AS1 conseillé.

## 4. Travail demandé

- **Watts économisés.** Le core calcule `draft_w` : puissance aérodynamique sans abri moins puissance avec abri, à la vitesse et au vent du moment. Il l'envoie arrondi au watt, seulement quand `draft` est au moins 0,02. Le HUD l'affiche sous la pastille, « −48 W », en medium et high. En low, la pastille reste seule.
- **Son.** Le volume du souffle (P10) suit la vitesse de l'air ressentie dans l'abri : `va × (1 − draft)^0,5`. On entend donc le calme en entrant dans la roue. Le lissage est le même que celui de l'abri (1 s).
- **Bilan.** `draft_time_s` (déjà calculé, P3) et `draft_kj` (énergie économisée) entrent dans le bilan IPC (`summary`) et dans l'écran de bilan : « 12 min dans la roue, 9 kJ économisés ».

## 5. Fichiers concernés

`core/src/openride_core/session.py`, `tools/session_summary.py`, tests ; `engine/scripts/wind_view_model.gd`, `hud_view.gd`, le script du son du vent, l'écran de bilan, `engine/tests/visual_check.py`, `hud_galerie.py` ; `docs/contracts/ipc_v1.md`, schémas `state` et `summary` ; `docs/GUIDE_UTILISATION.md`.

## 6. Modifications de contrat autorisées

Champ facultatif `draft_w` dans `state` ; champs facultatifs `draft_time_s` et `draft_kj` dans `summary`. Révision de la 2.0.

## 7. Critères d'acceptation

1. `pytest` et tests de l'engine sans écran passent ; `visual_check.py` en low, medium et high, captures montrées au propriétaire avant fusion.
2. Cycliste à 40 km/h, abri 0,30, CdA 0,32 : `draft_w` à ±2 W du calcul à la main.
3. Sans abri : pas de `draft_w`, HUD inchangé.
4. Volume du souffle : baisse d'au moins 3 dB dans la roue (abri 0,35) à vitesse égale ; sans « tac-tac » (règles du lot du 28 octobre).
5. Bilan : temps et énergie cohérents avec le journal à 1 % près.

**Sur le vélo (le propriétaire) :** entrer dans la roue d'un bot s'entend et se lit.

## 8. Hors périmètre

Vibrations, retour haptique.
