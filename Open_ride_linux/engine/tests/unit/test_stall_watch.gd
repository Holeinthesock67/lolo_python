extends SceneTree

## Tests unitaires sans écran du détecteur de gel du fil principal (lot GL2, `stall_watch.gd`) : rien sans
## battement, rien sous une seconde, ligne de début avec l'étape en cours, rappel toutes les 5 s, ligne de fin
## avec la durée et la part de chaque étape vue, étape posée depuis un autre fil ignorée, étape nommée pendant
## l'attente d'une tâche de fond (`bg_tasks.gd`), vrai fil de surveillance démarré puis arrêté.
## Lancement : godot --headless --path engine --script res://tests/unit/test_stall_watch.gd

const StallWatch := preload("res://scripts/stall_watch.gd")
const BgTasks := preload("res://scripts/bg_tasks.gd")

var _failures := 0
var _checked := 0
var _seen_in_task := ""


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _run() -> void:
	StallWatch.reset_for_tests()
	var w = StallWatch.new()
	_check(w.check(Time.get_ticks_usec() + 5_000_000) == "", "aucun battement encore : rien à signaler")

	StallWatch.beat()
	var t0: int = StallWatch.snapshot()[0]
	_check(w.check(t0 + 900_000) == "", "900 ms sans image : sous le seuil, rien")
	StallWatch.step("monde ouvert : nouvelle route dans les tuiles et l'OSM")
	var t_step: int = StallWatch.snapshot()[2]
	var line: String = w.check(t0 + 1_200_000)
	_check(line.begins_with("[gel] fil principal bloqué depuis 1200 ms : étape « monde ouvert : nouvelle route dans les tuiles et l'OSM »"),
		"début du blocage avec l'étape en cours : « %s »" % line)
	_check(line.ends_with("(depuis %d ms)" % int((t0 + 1_200_000 - t_step) / 1000.0)), "âge de l'étape donné")
	_check(w.check(t0 + 1_300_000) == "", "relevé suivant pendant le blocage : pas de nouvelle ligne")
	StallWatch.step("attente de la tâche « osm 5 »")
	for i in 10:
		w.check(t0 + 1_400_000 + i * 100_000)
	var again: String = w.check(t0 + 6_300_000)
	_check(again.begins_with("[gel] toujours bloqué depuis 6300 ms : étape « attente de la tâche « osm 5 » »"),
		"rappel au bout de 5 s : « %s »" % again)

	# L'image repart : ligne de fin, durée du battement d'avant au suivant.
	StallWatch.beat()
	var t1: int = StallWatch.snapshot()[0]
	var fin: String = w.check(t1 + 20_000)
	var ms := int((t1 - t0) / 1000.0)
	_check(fin.begins_with("[gel] fin du blocage : %d ms sans image ; étapes vues : " % ms), "fin du blocage : « %s »" % fin)
	_check(fin.find("monde ouvert : nouvelle route dans les tuiles et l'OSM") >= 0 and fin.find("osm 5") >= 0,
		"les deux étapes vues sont citées")
	_check(fin.find("%") > 0, "part de chaque étape en pour cent")
	_check(w.stalls == 1 and w.last_report == fin, "un blocage compté")
	_check(w.check(t1 + 40_000) == "", "après la fin : plus rien")

	# Étape posée depuis un autre fil : ignorée (tâches de fond).
	StallWatch.step("étape du fil principal")
	var th := Thread.new()
	th.start(func(): StallWatch.step("étape d'une tâche de fond"))
	th.wait_to_finish()
	_check(StallWatch.snapshot()[1] == "étape du fil principal", "étape d'un autre fil ignorée")

	# Attente d'une tâche de fond : l'étape la nomme pendant l'attente, puis l'étape d'avant revient.
	StallWatch.step("fenêtre des tuiles et tronçons")
	var id := BgTasks.add(func():
		OS.delay_msec(300)
		, true, "maillage near:1:-1")
	var probe := Thread.new()
	probe.start(func():
		OS.delay_msec(150)
		_seen_in_task = str(StallWatch.snapshot()[1]))
	BgTasks.wait(id)
	probe.wait_to_finish()
	_check(_seen_in_task == "attente de la tâche « maillage near:1:-1 »", "pendant l'attente : « %s »" % _seen_in_task)
	_check(StallWatch.snapshot()[1] == "fenêtre des tuiles et tronçons", "après l'attente : étape d'avant reposée")

	# Vrai fil : démarré, arrêté sans rester bloqué.
	var live = StallWatch.new()
	StallWatch.beat()
	live.start()
	OS.delay_msec(250)
	StallWatch.beat()
	live.stop()
	_check(live.stalls == 0, "fil de surveillance : aucun gel en 250 ms")
	StallWatch.reset_for_tests()


func _initialize() -> void:
	_run()
	print("test_stall_watch : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
