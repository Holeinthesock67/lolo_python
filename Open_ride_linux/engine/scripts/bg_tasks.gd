extends RefCounted

## Tâches de fond du jeu : toutes passent par ici, jamais par WorkerThreadPool directement (lot X58).
##
## Cause du blocage à la fermeture (PC, GTX 1060, Vulkan comme OpenGL, une fermeture sur deux, passage r805 du
## 9 novembre) : Godot 4.7 attend, dans WorkerThreadPool::exit_languages_threads (Main::cleanup), que chaque fil du
## pool se déclare inactif ; un fil ne le fait que si la file des tâches ET la file des tâches de basse priorité sont
## vides. Une tâche de basse priorité lancée par le jeu et pas encore exécutée au moment de quitter (seule une à la
## fois peut tourner avec 4 fils) restait dans sa file : les quatre fils dormaient, le fil principal attendait leur
## décompte sans fin (pile gdb : fil principal dans pthread_cond_wait appelé de main, fils WorkerThread 0 à 3 dans
## leur attente de tâche, même verrou).
##
## Ce registre garde chaque tâche lancée et pas encore attendue ; à la fermeture, `drain` les attend toutes (au plus
## quelques secondes), si bien que les deux files sont vides quand Godot arrête son pool. Pas de class_name : charger
## par preload("res://scripts/bg_tasks.gd").

static var _mutex := Mutex.new()
static var _pending := {}   # identifiant de tâche → description, tâches lancées et pas encore attendues


## Comme WorkerThreadPool.add_task (basse priorité par défaut, comme lui), tâche gardée jusqu'à son attente.
static func add(action: Callable, high_priority := false, description := "") -> int:
	_mutex.lock()
	var id := WorkerThreadPool.add_task(action, high_priority, description)
	_pending[id] = description
	_mutex.unlock()
	return id


## Tâche finie ; vrai aussi pour une tâche déjà attendue (par `drain` à la fermeture, par exemple).
static func done(id: int) -> bool:
	if not _has(id):
		return true
	return WorkerThreadPool.is_task_completed(id)


## Comme WorkerThreadPool.wait_for_task_completion ; la tâche sort du registre une fois attendue. Une tâche déjà
## attendue (par `drain` avant la libération des nœuds qui attendent les leurs) rend OK, sans erreur de Godot.
static func wait(id: int) -> Error:
	if not _has(id):
		return OK
	var err := WorkerThreadPool.wait_for_task_completion(id)
	if err != ERR_BUSY:
		_mutex.lock()
		_pending.erase(id)
		_mutex.unlock()
	return err


static func _has(id: int) -> bool:
	_mutex.lock()
	var ok := _pending.has(id)
	_mutex.unlock()
	return ok


static func pending_count() -> int:
	_mutex.lock()
	var n := _pending.size()
	_mutex.unlock()
	return n


## Fermeture : attend les tâches lancées et pas encore attendues, sans bloquer les images (une tâche en file ne
## démarre qu'après d'autres), au plus `max_s` secondes. Renvoie [tâches attendues, descriptions de celles qui
## tournent encore au bout du délai].
static func drain(tree: SceneTree, max_s: float) -> Array:
	var start := Time.get_ticks_msec()
	var waited := 0
	while true:
		_mutex.lock()
		var ids: Array = _pending.keys()
		_mutex.unlock()
		var left: Array = []
		for id in ids:
			if done(id):
				wait(id)
				waited += 1
			else:
				left.append(id)
		if left.is_empty() or Time.get_ticks_msec() - start >= max_s * 1000.0:
			_mutex.lock()
			var names := PackedStringArray()
			for id in left:
				names.append(str(_pending.get(id, "?")))
			_mutex.unlock()
			return [waited, names]
		await tree.process_frame
	return [waited, PackedStringArray()]
