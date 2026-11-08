# Lot X58 – Fermeture de Godot bloquée sur NVIDIA

<!-- Ligne de l'index des lots, lue par scripts/index_lots.py (lot X54) -->
| Titre | Langage | Dépend de | Taille | Statut |
| --- | --- | --- | --- | --- |
| Série X : trouver pourquoi Godot ne se ferme pas en `--native` sur le pilote NVIDIA (fils vk/cuda en attente) et retirer si possible le contournement de 3 s du lanceur | Python + GDScript | X55 | Petite | En cours (outils livrés, passage PC à faire) |

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

## 6. Réalisation (8 novembre)

### 6.1 Outils (cloud, sans Godot)

- **Pile sans `sudo`** : `engine/tests/pile_gdb.py`. Ubuntu ne permet `ptrace` qu'aux ancêtres du processus
  (`kernel.yama.ptrace_scope = 1`) ; le banc des menus lance donc Godot sous gdb dès le départ (`--gdb`), gdb en est
  le parent. Si Godot sort seul, gdb sort avec le même code ; s'il reste bloqué 3 s après sa ligne de fin, le banc lui
  envoie SIGINT, gdb écrit la pile de tous les fils (`pile_gdb.txt`) puis le tue (code 99). Le rapport en donne le
  résumé : une ligne par fil, fils identiques regroupés, fil principal d'abord (14 images), bibliothèque de chaque
  fonction (`libnvidia-glcore`, `libvulkan`, `libc`). Godot officiel n'a pas de symboles : ses propres images sont
  `??@Godot…`, celles du pilote et de la libc suffisent à dire qui attend qui.
- **Banc des menus** (`menu_bench.py`) : `--repeter N` (10 fermetures de suite, critère 2), `--fermeture-stricte`
  (arrêt bloqué compté en échec au lieu d'INFO), `--fermeture MODE`, `--engine-arg ARG`, `--qualite low|medium|high`.
- **Manières de quitter** (`main.gd`, `_quit`, `OPENRIDE_QUIT_MODE`), à comparer sans rien recompiler :
  vide (actuelle), `differe` (deux images plus tard, hors du traitement du clic qui la demande : seule la voie souris
  bloquait au lot X55), `liberer` (vue 3D coupée, environnement et nœuds 3D libérés, puis deux images). Une seule sera
  gardée, la constante `QUIT_MODES` et la variable retirées ensuite.
- Tests : `core/tests/test_pile_gdb.py` (résumé, repères, vrai gdb sur un programme bloqué : code gardé, pile sur SIGINT).

### 6.2 Passage sur le PC (via la file du fil de fusion)

Prérequis : `gdb` installé (`sudo apt install gdb`, une fois, par l'utilisateur). Environ 35 min, tout en `--native`.

```
cd ~/Games/lolo_python/Open_ride_linux && git fetch origin && git checkout <branche du lot>
nvidia-smi --query-gpu=driver_version --format=csv,noheader > /tmp/x58_pilote.txt
B="python3 engine/tests/menu_bench.py --scenario quitter --native --fermeture-stricte"
O=~/OpenRide/mesures/x58
$B --voies souris --gdb --repeter 3 --out $O/1_pile_low                       # cause : pile des fils bloqués
$B --voies souris --gdb --repeter 3 --qualite medium --out $O/1_pile_medium
$B --voies souris --gdb --repeter 3 --qualite high --out $O/1_pile_high
$B --voies clavier,click --repeter 3 --out $O/2_autres_voies                  # témoin : bloquent-elles aussi ?
$B --voies souris --repeter 10 --fermeture differe --out $O/3_differe_low     # essais de correction
$B --voies souris --repeter 10 --fermeture liberer --out $O/3_liberer_low
$B --voies souris --repeter 3 --engine-arg=--rendering-driver --engine-arg=opengl3 --out $O/4_opengl   # diagnostic Vulkan
```

Une variante qui tient 10/10 en low est rejouée 10 fois en medium et en high (`--qualite`), puis sur les trois voies.
À rapporter : `resume.txt` de chaque dossier, `pile_gdb.txt` du premier passage bloqué, version du pilote.

### 6.3 Cause et décision

À écrire après le passage sur le PC.
