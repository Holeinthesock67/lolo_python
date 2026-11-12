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

### 6.6 Troisième passage sur le PC (r805c, 9 novembre, tête 81df972a)

32 fermetures propres sur 50 (souris low 7/10, clavier 0/10, Click 5/10, souris medium 10/10, high 10/10). Les 24
fermetures où « 4 attendues, dont 4 sautées » sont propres ; dans les 26 autres, « 0 attendues, dont 0 sautées,
encore en cours au bout de 8 s » : les quatre maillages du terrain n'ont jamais démarré, alors que les 18 piles gdb
montrent les quatre fils endormis sans tâche. Ils étaient donc dans la file de basse priorité de Godot, derrière une
place de basse priorité (une seule avec quatre fils) prise sans tâche visible du jeu. Attendre plus ne sert à rien.
Fichiers : `/mnt/project-files/mesures/2026-11-09-x58-r805c/`.

Correction (registre `bg_tasks.gd` réécrit) : plus rien du jeu dans la file de basse priorité de Godot. Le registre
tient sa propre file ; une tâche de basse priorité est confiée à Godot en haute priorité, seulement quand moins de
`low_max()` des siennes tournent (même nombre que Godot : `threading/worker_pool/low_priority_thread_ratio` des fils,
au moins 1, donc le même partage des fils en jeu) ; la fin de chacune lance la suivante ; `wait` d'une tâche encore
en file la lance tout de suite. À la fermeture, la file du registre est abandonnée sans rien lancer. Effet attendu
aussi en jeu : ces maillages ne restent plus bloqués derrière la place de basse priorité de Godot.

### 6.7 Quatrième passage sur le PC (r805d, 11 novembre, tête 52c9ba6f)

0 fermeture propre sur 50, sur toutes les voies et les trois qualités. La vidange des tâches du jeu dure environ
130 ms (0 ou 1 tâche attendue) ; les 50 piles gdb sont identiques : fil principal dans
`WorkerThreadPool::exit_languages_threads` (0x42d0fe), les quatre fils de travail endormis. Aucun fil n'est donc
« non rejoint » : c'est le pool de Godot qui attend que ses fils se déclarent inactifs, et ils ne le font jamais.
Fichiers : `/mnt/project-files/mesures/2026-11-11-x58-r805d/`.

Mécanisme exact : anomalie de Godot 4.7 godotengine/godot#125097 (correctif proposé #125099, pas fusionné). Au
passage en `RUNLEVEL_PRE_EXIT_LANGUAGES`, chaque fil est réveillé une fois ; s'il voit une des deux files non vide, il
ne se compte pas inactif et se rendort, et personne ne le réveille quand la file se vide. Une seule tâche confiée à
Godot et pas encore démarrée à cet instant suffit, y compris les tâches de Godot lui-même (cache des pipelines,
chargements en fil) : le jeu ne peut pas l'empêcher depuis GDScript. Le registre `bg_tasks.gd` garde ses règles et
ne confie plus rien à Godot après `drain` (les `_exit_tree` qui attendent ou lancent encore une tâche).

### 6.8 Correction : sortie immédiate après la ligne de fin

Tout le travail du jeu est fait quand main.gd écrit « Fermeture : scène libérée, arrêt des serveurs de Godot
(code N) » (séance, `bye` au core, fichiers fermés, tâches de fond attendues) ; ce qui suit est l'arrêt de Godot,
seul à bloquer. main.gd s'arrête donc lui-même juste après cette ligne (`OS.kill(OS.get_process_id())`, SIGKILL),
seulement pour une fermeture demandée par `_quit`. `run/flush_stdout_on_print=true` (project.godot) garantit que la
ligne est écrite avant. Le lanceur (`ENGINE_SELF_KILLED` : -9, ou 137 à travers un shell ou gdb) lit le reste du
tuyau puis retient le code annoncé, sans attente ; le banc des menus fait de même (« sortie immédiate ») et le script
gdb sort avec 128 + le signal. `ENGINE_SHUTDOWN_S` (3 s) reste le filet si le processus ne sort toujours pas ; il ne
sert plus dans une fermeture normale. Ce qui est perdu : la dernière écriture du cache des pipelines par Godot à
l'arrêt (il l'écrit aussi en jeu) et la fin du journal interne de Godot.

### 6.9 Cinquième passage sur le PC (r805e, via la file du fil de fusion)

```
cd <worktree de la branche du lot>
B="python3 engine/tests/menu_bench.py --scenario quitter --native --fermeture-stricte --gdb"
O=~/OpenRide/mesures/x58e
$B --voies souris,clavier,click --repeter 10 --out $O/low
$B --voies souris --repeter 10 --qualite medium --out $O/medium
$B --voies souris --repeter 10 --qualite high --out $O/high
```

Attendu : 50 sur 50 « sortie immédiate » avec le bon code, aucune pile gdb ; puis un lancement par le lanceur
(Quitter, puis « Relancer » : code 64) pour vérifier qu'aucun plantage n'est compté et que le démarrage suivant ne
recompile pas tous les shaders.
