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
- **Manières de quitter essayées** au premier passage (variable `OPENRIDE_QUIT_MODE`, retirée depuis) : `differe`
  (deux images plus tard), `liberer` (nœuds 3D libérés : plantage, code -6), `compilations` (fin des compilations
  de pipelines). Aucune ne corrigeait : voir §6.3.
- Tests : `core/tests/test_pile_gdb.py` (résumé, repères, vrai gdb sur un programme bloqué : code gardé, pile sur SIGINT).

### 6.2 Premier passage sur le PC (r805, 9 novembre, pilote NVIDIA 580.178.04)

Branche 278924b2, scénario `quitter` en `--native`, `--fermeture-stricte`. Blocages : souris 4 sur 9 (low, medium,
high), clavier 2 sur 3, Click 2 sur 3, `differe` 8 sur 10, `compilations` 5 sur 10, `liberer` 10 sur 10 en plantage
(code -6), OpenGL (`--rendering-driver opengl3`) 2 sur 3. Le blocage ne tient donc ni à la souris ni à Vulkan.
Fichiers : `/mnt/project-files/mesures/2026-11-09-x58-r805/` (`brut/`, quatre `pile_gdb.txt`).

### 6.3 Cause

Les quatre piles sont identiques. Le fil principal attend dans `pthread_cond_wait`, appelé de `main` (0x42d0fe dans
le Godot 4.7.2 officiel) ; le désassemblage de cet endroit est la boucle de `WorkerThreadPool::exit_languages_threads`
(appelée par `Main::cleanup`) : `_switch_runlevel(RUNLEVEL_PRE_EXIT_LANGUAGES)` puis attente que
`num_idle_threads` vaille le nombre de fils. Les quatre `WorkerThread` dorment dans leur attente de tâche (même
verrou `task_mutex`). Dans `core/object/worker_thread_pool.cpp` (4.7.2), un fil ne se compte inactif que si
`task_queue` ET `low_priority_task_queue` sont vides : une tâche de basse priorité restée dans sa file au moment de
quitter (avec 4 fils, une seule tâche de basse priorité tourne à la fois) bloque donc le décompte sans fin, alors
que les fils n'ont rien à faire. Le jeu lance toutes ses tâches en basse priorité (fonds sonores, décor, forêt,
maillages, avatars), dont certaines ne sont jamais attendues.

### 6.4 Correction

- `engine/scripts/bg_tasks.gd` : registre de toutes les tâches de fond du jeu (`add`, `wait`, `done`), qui garde les
  tâches lancées et pas encore attendues ; plus aucun appel direct à `WorkerThreadPool` dans `engine/scripts/`
  (vérifié par `core/tests/test_pile_gdb.py`).
- `main.gd` `_quit` : `BgTasks.drain` attend ces tâches (sans bloquer les images, au plus `QUIT_TASKS_MAX_S` = 5 s)
  avant `get_tree().quit` ; le journal dit combien et nomme celles qui tourneraient encore
  (« Fermeture : tâches de fond attendues (N) … »). Les attentes des nœuds libérés ensuite rendent OK sans erreur.
- Test `engine/tests/unit/test_bg_tasks.gd` (12 tâches de basse priorité en file, drain, délai dépassé nommé).
- Contournement de 3 s du lanceur gardé tant que le PC n'a pas confirmé 10 sur 10.

### 6.5 Deuxième passage sur le PC (r805b, 9 novembre, tête 323f8ac0)

12 fermetures propres sur 50 (souris low 2/10, clavier 0/10, Click 0/10, souris medium 7/10, high 3/10). Dans 30
fermetures, « tâches de fond attendues (0), encore en cours au bout de 5 s : maillage far:0:0, maillage near:1:-1… »
(quatre maillages du terrain encore en file ; `world_streamer._exit_tree` les attend ensuite, la scène n'est libérée
que vers 9 s) ; les fermetures propres sont celles où tout avait été attendu (6 à 10 tâches). La cause est donc
confirmée : tâche de basse priorité pas finie au moment de quitter = arrêt de Godot bloqué. Fichiers :
`/mnt/project-files/mesures/2026-11-09-x58-r805b/`.

Correction complétée : à la fermeture, `main.gd` cesse de traiter ses nœuds (`PROCESS_MODE_DISABLED` : plus de
nouvelle tâche du streaming), `BgTasks.drain` passe en fermeture (une tâche pas encore démarrée rend la main sans
rien faire ; le journal dit combien), attend celles qui tournent, au plus 8 s.

### 6.6 Troisième passage sur le PC (via la file du fil de fusion)

```
cd <worktree de la branche du lot>
B="python3 engine/tests/menu_bench.py --scenario quitter --native --fermeture-stricte --gdb"
O=~/OpenRide/mesures/x58c
$B --voies souris,clavier,click --repeter 10 --out $O/low
$B --voies souris --repeter 10 --qualite medium --out $O/medium
$B --voies souris --repeter 10 --qualite high --out $O/high
```

Attendu : 50 sur 50 sans « arrêt de Godot bloqué » ; sinon `pile_gdb.txt` et la ligne « Fermeture : tâches de
fond attendues » du journal de l'engine. Si 50 sur 50 : retrait du contournement de 3 s dans cette même PR, puis un dernier passage (critère 2).
