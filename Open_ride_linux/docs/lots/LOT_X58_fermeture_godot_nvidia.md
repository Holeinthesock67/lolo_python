# Lot X58 – Fermeture de Godot bloquée sur NVIDIA

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X : trouver pourquoi Godot ne se ferme pas en `--native` sur le pilote NVIDIA (fils vk/cuda en attente) et retirer si possible le contournement de 3 s du lanceur | Python + GDScript | X55 | Petite | Prêt (après la 1.0) |

Suite du lot X55 (31 octobre) : sur le PC cible, la fermeture par la souris bloque après « scène libérée, arrêt des serveurs de Godot », seulement en `--native` (fils `vk*` et `cuda` en futex) ; le lanceur tue Godot au bout de 3 s (`launcher.ENGINE_SHUTDOWN_S`). Le cahier X55 renvoyait la cause « après la 1.0 », sans lot. Cahier rédigé le 8 novembre.

## 1. Objectif

Connaître la cause, puis fermer proprement sans tuer le processus.

## 2. À lire

`docs/lots/LOT_X55_banc_menus_silences_fermeture.md` ; `core/src/openride_core/launcher.py` (`ENGINE_DONE`, `ENGINE_SHUTDOWN_S`) ; `engine/scripts/main.gd` (`_quit`, `_exit_tree`).

## 3. Travail demandé

- Pile `gdb` des fils bloqués sur le PC (avec `sudo`, `ptrace` refusé sinon), via la file du PC.
- Essais ciblés : libération explicite des ressources Vulkan avant `quit`, version du pilote, Godot 4.7.x suivant.
- Si une correction tient sur 10 fermetures de suite : retirer le contournement ; sinon le garder et noter la cause.

## 4. Critères d'acceptation

1. Rapport de la cause dans le cahier.
2. Banc des menus (étape `sortie`) vert en `--native`, 10 fois sur 10.

## 5. Fichiers touchés

`core/src/openride_core/launcher.py`, `engine/scripts/main.gd`, `engine/tests/` (banc des menus).
