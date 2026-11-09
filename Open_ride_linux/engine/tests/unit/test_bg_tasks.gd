extends SceneTree

## Registre des tâches de fond (bg_tasks.gd, lot X58) : tâches de basse priorité plus nombreuses que les fils
## permis (elles attendent en file), `drain` les attend toutes sans bloquer les images, puis une attente d'une
## tâche déjà attendue rend OK sans erreur de Godot ; à la fin le test quitte avec des files vides (sinon l'arrêt
## du pool de Godot 4.7 peut attendre sans fin, cause du blocage de la fermeture sur le PC).
## Lancement : godot --headless --path engine --script res://tests/unit/test_bg_tasks.gd

const BgTasks := preload("res://scripts/bg_tasks.gd")

var _failures := 0
var _checked := 0
var _ran := 0
var _ran_mutex := Mutex.new()
var _slow_started := false


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _job() -> void:
	OS.delay_msec(30)
	_ran_mutex.lock()
	_ran += 1
	_ran_mutex.unlock()


func _slow_job() -> void:
	_slow_started = true
	OS.delay_msec(600)


func _run() -> void:
	# 1. Sans fermeture : `drain` attend tout, sans bloquer les images.
	var ids: Array = []
	for i in range(12):
		ids.append(BgTasks.add(_job, false, "essai %d" % i))
	_check(BgTasks.pending_count() == 12, "12 tâches gardées par le registre")
	var frames := [0]
	var count_frames := func() -> void: frames[0] += 1
	process_frame.connect(count_frames)
	BgTasks.reopen_for_tests()
	var got: Array = await _drain_open(10.0)
	process_frame.disconnect(count_frames)
	_check(got[0] == 12 and got[1].is_empty(), "drain : 12 tâches attendues, aucune encore en cours (%s)" % str(got))
	_check(BgTasks.pending_count() == 0, "registre vide après drain")
	_check(frames[0] > 0, "drain laisse passer les images (%d images)" % frames[0])
	_check(BgTasks.wait(ids[0]) == OK and BgTasks.done(ids[0]), "tâche déjà attendue : wait rend OK, done vrai")
	# 2. Fermeture : une tâche lente qui tourne déjà est nommée au bout du délai ; celles en file sont sautées.
	BgTasks.reopen_for_tests()
	_ran = 0
	var slow: int = BgTasks.add(_slow_job, false, "lente")
	while not _slow_started:
		await process_frame
	for i in range(6):
		BgTasks.add(_job, false, "en file %d" % i)
	var late: Array = await BgTasks.drain(self, 0.1)
	_check(late[1].has("lente"), "délai dépassé : la tâche encore en cours est nommée (%s)" % str(late))
	var rest: Array = await BgTasks.drain(self, 5.0)
	_check(rest[1].is_empty() and BgTasks.pending_count() == 0, "tout attendu ensuite (%s)" % str(rest))
	_check(rest[2] + _ran == 6 and rest[2] > 0, "tâches en file sautées après la fermeture (%d sautées, %d faites)" % [rest[2], _ran])
	_check(BgTasks.done(slow), "tâche lente finie")
	print("test_bg_tasks : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


## drain sans fermeture (partie 1) : attend comme drain, puis rouvre le registre.
func _drain_open(max_s: float) -> Array:
	var got: Array = await BgTasks.drain(self, max_s)
	BgTasks.reopen_for_tests()
	return got
