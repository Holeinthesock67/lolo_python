extends SceneTree

## Photos automatiques de la séance (photo_moments_model.gd, idée M9 de l'audit du 22 novembre) : photo à
## l'arrivée et aux records, délai d'un record, rien en Cyber-Rogue ni réglage coupé, six au plus, série
## remise à zéro au départ suivant, noms de fichiers et ligne du bilan en mots ; main.gd branché.
## Lancement : godot --headless --path engine --script res://tests/unit/test_photo_moments_model.gd

const Model := preload("res://scripts/photo_moments_model.gd")
const NOW := {"year": 2026, "month": 11, "day": 28, "hour": 10, "minute": 12}

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_photo_moments_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


static func _st(session: String, mode := "") -> Dictionary:
	return {"session_state": session, "mode": mode}


func _take(m, reqs: Array) -> void:
	for r in reqs:
		m.add_photo(r, NOW)


func _run() -> void:
	var m = Model.new()
	_check(m.on_state(_st("READY"), 0.0).is_empty(), "départ : aucune photo")
	_check(m.on_state(_st("RUNNING"), 1.0).is_empty(), "en route : aucune photo")
	# Record : photo 1,2 s plus tard, pas avant
	m.on_segment_result({"kind": "climb", "pr": true, "name": "Côte du village"}, 10.0)
	m.on_segment_result({"kind": "sprint", "pr": false, "name": "Sprint"}, 10.0)
	m.on_segment_result({"kind": "arch", "pr": true}, 10.0)
	_check(m.on_state(_st("RUNNING"), 11.0).is_empty(), "record : pas de photo avant le délai")
	var r: Array = m.on_state(_st("RUNNING"), 11.3)
	_check(r.size() == 1 and r[0]["kind"] == "record" and r[0]["label"] == "record « Côte du village »",
		"record de montée : une photo après le délai (%s)" % str(r))
	_take(m, r)
	_check(m.folder == "2026-11-28_1012", "dossier de la séance à la première photo (%s)" % m.folder)
	_check(m.photos[0]["file"] == "1_record_cote-du-village.jpg", "nom de la photo du record (%s)" % m.photos[0]["file"])
	# Record pendant la pause : attend la reprise ; record oublié si la séance finit avant
	m.on_segment_result({"kind": "sprint", "pr": true, "name": ""}, 20.0)
	_check(m.on_state(_st("PAUSED"), 22.0).is_empty(), "pause : pas de photo")
	r = m.on_state(_st("RUNNING"), 23.0)
	_check(r.size() == 1 and r[0]["label"] == "record de sprint", "reprise : photo du record gardé (%s)" % str(r))
	_take(m, r)
	m.on_segment_result({"kind": "climb", "pr": true, "name": "Col"}, 30.0)
	r = m.on_state(_st("FINISHED"), 30.1)
	_check(r.size() == 1 and r[0]["kind"] == "arrivee", "arrivée : une photo tout de suite, record en attente oublié")
	_take(m, r)
	_check(m.on_state(_st("FINISHED"), 40.0).is_empty(), "arrivée : une seule photo")
	_check(m.photos.size() == 3 and m.photos[2]["file"] == "3_arrivee.jpg", "trois photos, la dernière « 3_arrivee.jpg »")
	var lines: Array = Model.photo_lines(m.photos, m.folder)
	_check(lines == ["Photos de la séance : 3 (record « Côte du village », record de sprint, arrivée) dans ~/OpenRide/Captures/2026-11-28_1012"],
		"ligne du bilan en mots (%s)" % str(lines))
	_check(Model.photo_lines([], "") == [], "sans photo : aucune ligne")
	_check(Model.photo_lines([{"label": "arrivée"}], "d") == ["Photo de la séance (arrivée) dans ~/OpenRide/Captures/d"],
		"une photo : singulier")
	# Séance suivante : série remise à zéro, la ligne du bilan reste jusque-là
	m.on_state(_st("IDLE"), 50.0)
	_check(m.photos.size() == 3, "retour au menu : photos gardées pour le bilan")
	m.on_state(_st("READY"), 51.0)
	_check(m.photos.is_empty() and m.folder == "", "nouveau départ : nouvelle série")
	# Au plus six photos
	m.on_state(_st("RUNNING"), 52.0)
	for i in 8:
		m.on_segment_result({"kind": "climb", "pr": true, "name": "M%d" % i}, 52.0)
	r = m.on_state(_st("RUNNING"), 60.0)
	_check(r.size() == Model.MAX_PHOTOS - 1, "cinq photos de record au plus (%d)" % r.size())
	_take(m, r)
	r = m.on_state(_st("FINISHED"), 61.0)
	_check(r.size() == 1 and r[0]["kind"] == "arrivee", "la sixième place reste à l'arrivée")
	# Cyber-Rogue et réglage coupé : aucune photo
	var rogue = Model.new()
	rogue.on_state(_st("RUNNING", "ROGUE"), 0.0)
	_check(rogue.on_state(_st("FINISHED", "ROGUE"), 1.0).is_empty(), "Cyber-Rogue : pas de photo d'arrivée")
	var off = Model.new()
	off.enabled = false
	off.on_state(_st("RUNNING"), 0.0)
	off.on_segment_result({"kind": "climb", "pr": true, "name": "Col"}, 0.0)
	_check(off.on_state(_st("RUNNING"), 5.0).is_empty() and off.on_state(_st("FINISHED"), 6.0).is_empty(),
		"réglage coupé : aucune photo")
	_check(Model.slugify("L'Alpe d'Huez — 21 virages !") == "l-alpe-d-huez-21-virages", "nom de fichier sans accent ni signe")
	var main_code := FileAccess.get_file_as_string("res://scripts/main.gd")
	_check(main_code.contains("for req in photo_moments.on_state(state,") and main_code.contains("photo_moments.on_segment_result(msg,"),
		"main.gd : modèle branché sur state et segment_result")
	_check(main_code.contains("if (ipc.test_mode and base == \"\") or DisplayServer.get_name() == \"headless\":"),
		"main.gd : aucune photo en mode test ni sans écran")
	_check(main_code.contains("WorkerThreadPool.add_task(func() -> void:\n\t\tDirAccess.make_dir_recursive_absolute(dir)"),
		"main.gd : écriture du JPEG hors de l'image")
	_check(main_code.contains("menu_view.summary.result_lines = PhotoMomentsModel.photo_lines(photo_moments.photos, photo_moments.folder)")
		and main_code.contains("if str(st[\"screen\"]) == \"summary\" else []"),
		"main.gd : ligne des photos dans l'encart du résultat, bilan de la séance seulement")
