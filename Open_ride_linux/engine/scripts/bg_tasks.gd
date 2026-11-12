extends RefCounted

## Tâches de fond du jeu : toutes passent par ici, jamais par WorkerThreadPool directement (lot X58).
##
## Cause du blocage à la fermeture (PC, GTX 1060, Vulkan comme OpenGL, passages r805, r805b et r805c du 9 novembre) :
## Godot 4.7 attend, dans WorkerThreadPool::exit_languages_threads (Main::cleanup), que chaque fil du pool se déclare
## inactif ; un fil ne le fait que si la file des tâches ET la file des tâches de basse priorité de Godot sont vides
## (core/object/worker_thread_pool.cpp, _handle_runlevel). Les piles gdb des 22 fermetures bloquées sont identiques :
## fil principal dans cette attente, quatre WorkerThread endormis sans tâche. Dans chacune, quatre maillages du
## terrain (world_streamer.gd, « maillage near:1:-1 », « far:0:0 »…) attendaient dans la file de basse priorité de
## Godot sans jamais démarrer : ni finis, ni sautés au bout de 8 s alors que les fils dormaient (r805c). La place de
## basse priorité (une seule avec quatre fils) restait prise sans tâche visible ; ce qui la tient est dans Godot.
##
## Le registre ne confie donc plus rien à la file de basse priorité de Godot. Il tient sa propre file : une tâche
## « basse priorité » est confiée à Godot en haute priorité, et seulement quand moins de LOW_MAX des siennes tournent
## (même nombre que Godot : threading/worker_pool/low_priority_thread_ratio des fils, au moins 1) ; les autres
## attendent dans `_fifo`, et la fin de chacune lance la suivante. Une tâche attendue avant son tour (`wait`) part
## tout de suite. À la fermeture, `drain` vide `_fifo` sans rien lancer, une tâche confiée qui n'a pas encore démarré
## rend la main sans travailler, et `drain` attend celles qui tournent : les deux files de Godot sont vides quand il
## arrête son pool. Les identifiants sont ceux du registre, pas ceux de Godot.
##
## Quatrième passage (r805d, 0 fermeture propre sur 50, même pile) : le mécanisme exact est l'anomalie de Godot
## godotengine/godot#125097 (correctif proposé #125099) : au passage en RUNLEVEL_PRE_EXIT_LANGUAGES, un fil qui voit
## une file non vide ne se compte pas et se rendort ; quand la file se vide, personne ne le réveille. Toute tâche
## confiée à Godot et pas encore démarrée à cet instant (haute priorité comprise) suffit donc. Les nœuds libérés après
## `drain` (attentes et demandes de leurs `_exit_tree` et NOTIFICATION_PREDELETE) en confiaient encore : depuis,
## après `drain`, `add` ne confie plus rien (la tâche est comptée « abandonnée ») et `wait` d'une tâche encore dans la
## file du registre l'abandonne au lieu de la lancer.
## Pas de class_name : charger par preload("res://scripts/bg_tasks.gd").

static var _mutex := Mutex.new()
# identifiant du registre → {"desc", "action", "low": basse priorité, "gid": identifiant Godot (-1 : encore dans _fifo)}
static var _tasks := {}
static var _fifo: Array = []      # identifiants des tâches de basse priorité pas encore confiées à Godot
static var _low_running := 0      # tâches de basse priorité confiées à Godot et pas finies
static var _next_id := 1
static var _closing := false      # fermeture demandée : plus rien ne démarre
static var _skipped := 0          # tâches qui n'ont rien fait depuis la fermeture
static var _low_max := 0          # 0 : pas encore calculé


## Comme WorkerThreadPool.add_task (basse priorité par défaut, comme lui) : identifiant du registre.
static func add(action: Callable, high_priority := false, description := "") -> int:
	_mutex.lock()
	var id := _next_id
	_next_id += 1
	if _closing:   # après `drain` : rien ne doit plus entrer dans les files de Godot (voir l'en-tête)
		_skipped += 1
		_mutex.unlock()
		return id   # absent du registre : done() vrai, wait() OK
	_tasks[id] = {"desc": description, "action": action, "low": not high_priority, "gid": -1}
	if high_priority or _low_running < low_max():
		_dispatch(id)
	else:
		_fifo.append(id)
	_mutex.unlock()
	return id


## Places de basse priorité, comme Godot : CLAMP(fils × ratio, 1, fils - 1).
static func low_max() -> int:
	if _low_max == 0:
		var threads: int = ProjectSettings.get_setting("threading/worker_pool/max_threads", -1)
		if threads <= 0:
			threads = OS.get_processor_count()
		var ratio: float = ProjectSettings.get_setting("threading/worker_pool/low_priority_thread_ratio", 0.3)
		_low_max = clampi(int(threads * ratio), 1, maxi(1, threads - 1))
	return _low_max


## Confie la tâche à Godot, en haute priorité (verrou du registre tenu).
static func _dispatch(id: int) -> void:
	var t: Dictionary = _tasks[id]
	if t["low"]:
		_low_running += 1
	t["gid"] = WorkerThreadPool.add_task(_run.bind(id), true, t["desc"])


## Exécutée dans le fil de travail : le travail demandé (sauf fermeture), puis la tâche suivante de la file.
static func _run(id: int) -> void:
	_mutex.lock()
	var t: Dictionary = _tasks.get(id, {})
	var closing := _closing
	if closing:
		_skipped += 1
	_mutex.unlock()
	if not closing and not t.is_empty():
		(t["action"] as Callable).call()
	_mutex.lock()
	if t.get("low", false):
		_low_running -= 1
		if not _closing and not _fifo.is_empty() and _low_running < low_max():
			_dispatch(_fifo.pop_front())
	_mutex.unlock()


## Tâche finie ; vrai aussi pour une tâche déjà attendue ou abandonnée à la fermeture.
static func done(id: int) -> bool:
	_mutex.lock()
	var gid: int = _tasks[id]["gid"] if _tasks.has(id) else -2
	_mutex.unlock()
	if gid == -2:
		return true
	if gid == -1:
		return false
	return WorkerThreadPool.is_task_completed(gid)


## Comme WorkerThreadPool.wait_for_task_completion. Une tâche encore dans la file du registre part tout de suite ;
## une tâche déjà attendue (par `drain` avant la libération des nœuds qui attendent les leurs) rend OK.
static func wait(id: int) -> Error:
	_mutex.lock()
	if not _tasks.has(id):
		_mutex.unlock()
		return OK
	if _tasks[id]["gid"] == -1:
		_fifo.erase(id)
		if _closing:   # abandonnée à la fermeture, jamais confiée à Godot
			_tasks.erase(id)
			_mutex.unlock()
			return OK
		_dispatch(id)
	var gid: int = _tasks[id]["gid"]
	_mutex.unlock()
	var err := WorkerThreadPool.wait_for_task_completion(gid)
	if err != ERR_BUSY:
		_mutex.lock()
		_tasks.erase(id)
		_mutex.unlock()
	return err


## Remet le registre hors fermeture (tests seulement).
static func reopen_for_tests() -> void:
	_closing = false
	_skipped = 0


## Tâches lancées et pas encore attendues (file du registre comprise).
static func pending_count() -> int:
	_mutex.lock()
	var n := _tasks.size()
	_mutex.unlock()
	return n


## Tâches de basse priorité dans la file du registre, pas encore confiées à Godot.
static func queued_count() -> int:
	_mutex.lock()
	var n := _fifo.size()
	_mutex.unlock()
	return n


## Fermeture : la file du registre est abandonnée, les tâches confiées qui n'ont pas démarré ne font rien, celles
## qui tournent sont attendues, sans bloquer les images, au plus `max_s` secondes. Renvoie [tâches attendues,
## descriptions de celles qui tournent encore au bout du délai, tâches qui n'ont rien fait]. Les tâches lancées
## ensuite ne font rien non plus.
static func drain(tree: SceneTree, max_s: float) -> Array:
	_mutex.lock()
	_closing = true
	for id in _fifo:
		_tasks.erase(id)
		_skipped += 1
	_fifo.clear()
	_mutex.unlock()
	var start := Time.get_ticks_msec()
	var waited := 0
	while true:
		_mutex.lock()
		var ids: Array = _tasks.keys()
		_mutex.unlock()
		var left: Array = []
		for id in ids:
			if done(id):
				wait(id)
				waited += 1
			else:
				left.append(id)
		if left.is_empty() or Time.get_ticks_msec() - start >= max_s * 1000.0:
			var names := PackedStringArray()
			_mutex.lock()
			for id in left:
				names.append(str(_tasks[id]["desc"]) if _tasks.has(id) else "?")
			var skipped := _skipped
			_mutex.unlock()
			return [waited, names, skipped]
		await tree.process_frame
	return [waited, PackedStringArray(), 0]
