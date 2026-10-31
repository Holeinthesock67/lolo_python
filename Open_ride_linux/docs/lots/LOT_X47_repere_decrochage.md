# Lot X47 – Repère « décrochage » au journal (Z long, Maj+Z)

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X (outils de test) : repère « décrochage » au journal par Z long au Click (§7.1, SIM, ERG, monde ouvert) et `Maj+Z` au clavier, confirmé à l'écran, relu par `decrochages` | Python, GDScript | X42, X44 | Petite | Séance du 29 octobre ; en PR |

## 1. Objectif

Séance du 29 octobre : le cycliste sentait la résistance du trainer lâcher après une relance, mais rien dans le journal ne datait ce ressenti. L'outil `decrochages` (lot X44) cherche les chutes de puissance mesurées et les classe : trainer, fatigue, arrêt. Il lui manquait le repère du cycliste pour confirmer qu'une chute vue est bien celle qu'il a sentie.

## 2. Spécification

| # | Règle |
| --- | --- |
| X47-1 | §7.1 : Z long (« action spéciale du mode ») vaut « Repère « décrochage » au journal » en Classique SIM, en ERG et en monde ouvert. Il reste « Aucune » dans les menus et « Carte ou relique active » en Cyber-Rogue. L'ERG d'une session libre suit la colonne SIM pour Z, ce qui donne le même repère. |
| X47-2 | Clavier : `Maj+Z`, déjà synonyme de Z long (lot O17). Aucune touche nouvelle. |
| X47-3 | Le core, séance en cours (`RUNNING`), écrit `{"kind": "event", "ts": …, "event": "decrochage"}` au journal (`journal.EVENTS`). Il ajoute une ligne `WARNING` dans `core.log` avec la puissance, la cadence et la vitesse, et compte les repères (`dropout_marks`). Ni braquet, ni consigne, ni chronomètre ne changent. Le repère reste hors du FIT et de `TIMER_EVENTS`. |
| X47-4 | En pause, Z long ne fait rien. |
| X47-5 | L'engine joue le bip du Z long, comme avant, et affiche « Repère « décrochage » noté au journal » (`HudViewModel.dropout_mark_text`). Pas d'affichage en menu ni en Cyber-Rogue. |
| X47-6 | `matrice_boutons` (X42) lit la case « Repère « décrochage » » du §7.1 : un repère de plus, rien d'autre de changé, appui relayé à l'engine. `boutons_click` (G3) annonce ce rôle. |

## 3. Fichiers

- `core/src/openride_core/journal.py` et `core/src/openride_core/session.py` ;
- `core/src/openride_core/tools/matrice_boutons.py` et `tools/boutons_click.py` ;
- `engine/scripts/hud_view_model.gd`, `engine/scripts/main.gd`, `engine/tests/unit/test_hud_view_model.gd` ;
- `docs/SPECIFICATION_GENERALE.md` (§7.1), `docs/GUIDE_UTILISATION.md` ;
- `core/tests/test_repere_decrochage.py`.

## 4. Critères d'acceptation

1. `pytest` passe :
   - Z long en SIM et en ERG écrit un seul repère et ne change ni le braquet, ni le biais, ni le bloc, ni l'état ;
   - le repère se relit dans le journal et n'apparaît pas dans les événements du chronomètre ;
   - en pause, Z long ne fait rien.
2. La matrice des boutons (X42) est verte, Click et clavier, sur les cases Z long.
3. Tests Godot : le texte de confirmation n'apparaît qu'en roulant, hors Cyber-Rogue et hors menu.
4. Sur le PC (via le fil de fusion), en séance : Z long au Click (boîtier droit) et `Maj+Z` au clavier. Le bandeau s'affiche et `decrochages` relit le repère dans le journal.
