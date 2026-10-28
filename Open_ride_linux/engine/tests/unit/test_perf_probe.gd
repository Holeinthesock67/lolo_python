extends SceneTree

## Tests unitaires sans écran de la sonde de performance (perf_probe.gd, lot X13).
## Lancement : godot --headless --path engine --script res://tests/unit/test_perf_probe.gd

const PerfProbe := preload("res://scripts/perf_probe.gd")
const EngineArgs := preload("res://scripts/engine_args.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	var empty: Dictionary = PerfProbe.frame_stats([])
	_check(empty["fps"] == 0.0 and empty["frame_p99_ms"] == 0.0, "aucune image : tout à 0")

	var times: Array = []
	for i in 99:
		times.append(16.0)
	times.append(50.0)
	var st: Dictionary = PerfProbe.frame_stats(times)
	_check(absf(st["fps"] - 100.0 / 1.634) < 0.01, "images/s = nombre d'images / durée (%.2f)" % st["fps"])
	_check(st["frame_p50_ms"] == 16.0 and st["frame_max_ms"] == 50.0, "p50 16 ms, max 50 ms")
	_check(st["frame_p99_ms"] == 50.0, "p99 prend l'image lente sur 100")

	var line: String = PerfProbe.csv_line({"t_s": 1.0, "fps": 59.94, "draw_calls": 120, "preset": "low"})
	var cells := line.split(";")
	_check(cells.size() == PerfProbe.COLUMNS.size(), "une cellule par colonne (%d)" % cells.size())
	_check(cells[0] == "1.00" and cells[PerfProbe.COLUMNS.find("fps")] == "59.94" and cells[PerfProbe.COLUMNS.find("draw_calls")] == "120",
		"nombres écrits (réels à 2 décimales)")
	_check(cells[PerfProbe.COLUMNS.find("gpu_ms")] == "" and cells[cells.size() - 1] == "low", "colonne absente vide, préréglage en fin")

	var rc: Dictionary = PerfProbe.render_counters()
	var keys_ok := true
	for k in ["draw_calls", "objects", "primitives", "vram_mb", "texture_mb", "buffer_mb", "static_mb", "nodes"]:
		keys_ok = keys_ok and rc.has(k) and PerfProbe.COLUMNS.has(k)
	_check(keys_ok and rc["static_mb"] > 0.0, "compteurs du rendu lus (mémoire statique %.1f Mo)" % rc["static_mb"])
	var wc: Dictionary = PerfProbe.world_counters(null)
	_check(wc["near_tiles"] == 0 and wc["trees"] == 0, "sans décor : compteurs du décor à 0")

	var args: Dictionary = EngineArgs.parse(PackedStringArray(["--perf-probe=~/sonde/a.csv"]))
	_check(args["perf_probe"] == OS.get_environment("HOME") + "/sonde/a.csv", "--perf-probe lu, ~ développé")
	_check(EngineArgs.parse(PackedStringArray())["perf_probe"] == "", "sonde inactive par défaut")

	# Écriture réelle : en-tête puis une ligne par seconde.
	var dir := OS.get_user_data_dir().path_join("test_perf_probe")
	var csv := dir.path_join("sonde.csv")
	var probe = PerfProbe.new()
	_check(probe.open(csv, null, "medium"), "fichier ouvert")
	probe.frame(0.016)
	_check(probe.rows_written == 0, "pas de ligne avant une seconde")
	probe._last_us -= PerfProbe.PERIOD_US
	probe.frame(0.020)
	probe.close()
	var text := FileAccess.get_file_as_string(csv)
	var lines := text.strip_edges().split("\n")
	_check(lines.size() == 2 and lines[0] == ";".join(PerfProbe.COLUMNS), "en-tête et une ligne écrits")
	_check(lines.size() == 2 and lines[1].ends_with(";medium") and lines[1].split(";")[PerfProbe.COLUMNS.find("fps")] == "55.56",
		"ligne : 2 images en 36 ms, 55.56 images/s")
	# Capture d'écran (lot X35) : l'image de la capture et les deux suivantes sortent de p99 et pire image.
	var cs: Dictionary = PerfProbe.capture_stats([16.0, 16.0], [])
	_check(cs["capture"] == 0 and not cs.has("fps"), "sans capture : rien à corriger")
	probe = PerfProbe.new()
	_check(probe.open(csv, null, "low"), "fichier rouvert")
	for i in 10:
		probe.frame(0.016)
	probe.mark_capture()
	probe.frame(0.150)
	probe.frame(0.030)
	probe.frame(0.016)
	probe.frame(0.016)
	probe._last_us -= PerfProbe.PERIOD_US
	probe.frame(0.016)
	probe.close()
	lines = FileAccess.get_file_as_string(csv).strip_edges().split("\n")
	var cells2 := lines[1].split(";") if lines.size() == 2 else PackedStringArray()
	var col := func(name: String) -> String: return cells2[PerfProbe.COLUMNS.find(name)] if cells2.size() == PerfProbe.COLUMNS.size() else "?"
	_check(col.call("capture") == "3" and col.call("capture_max_ms") == "150.00",
		"3 images de capture mises à part, pire 150 ms (%s, %s)" % [col.call("capture"), col.call("capture_max_ms")])
	_check(col.call("frame_max_ms") == "16.00" and col.call("frame_p99_ms") == "16.00",
		"p99 et pire image sans la capture (%s, %s)" % [col.call("frame_p99_ms"), col.call("frame_max_ms")])
	_check(col.call("fps") == "38.66", "images/s avec les images de la capture : 15 images en 388 ms (%s)" % col.call("fps"))
	# Saccades et démarrage (lot X15).
	_check(not PerfProbe.active, "sonde fermée : inactive")
	PerfProbe.mark("tuile", "near:0:0", 50.0)
	PerfProbe.task("osm", "3", 80.0)
	_check(PerfProbe._steps.is_empty() and PerfProbe._tasks.is_empty(), "sans sonde, mark et task ne retiennent rien")
	var t_calls := Time.get_ticks_usec()
	for i in 10000:
		PerfProbe.mark("tuile", "near:0:0", 1.0)
	var per_call_us := float(Time.get_ticks_usec() - t_calls) / 10000.0
	print("mark sans sonde : %.2f µs par appel" % per_call_us)
	_check(per_call_us < 20.0, "sans sonde, mark coûte moins de 20 µs (%.2f µs ; une dizaine d'appels par seconde)" % per_call_us)
	var sc: Dictionary = PerfProbe.saccade_cause([["tuile", "near:1:2", 12.0], ["arbres", "near:1:2", 30.5]], false, 60.0)
	_check(sc["cause"] == "arbres" and sc["steps"] == "tuile near:1:2 12.0 | arbres near:1:2 30.5",
		"cause : l'étape la plus longue (%s)" % sc["cause"])
	_check(PerfProbe.saccade_cause([["arbres", "near:1:2", 18.5]], false, 147.0)["cause"] == "inconnue",
		"étape de moins du quart de l'image : inconnue")
	_check(PerfProbe.saccade_cause([], false, 40.0)["cause"] == "inconnue" and PerfProbe.saccade_cause([["osm", "4", 9.0]], true, 40.0)["cause"] == "capture",
		"sans étape : inconnue ; capture prioritaire")
	probe = PerfProbe.new()
	_check(probe.open(csv, null, "low") and PerfProbe.active, "sonde rouverte : active")
	probe.route_ready()
	probe.distance_m = 1234.5
	PerfProbe.mark("tuile", "near:1:2", 40.0)
	probe.frame(0.045)                 # saccade due à la tuile
	probe.frame(0.016)                 # étapes déjà comptées : rien à signaler
	probe.frame(0.060)                 # saccade sans étape
	PerfProbe.task("arbres", "1:2", 7.25)
	for i in PerfProbe.PLAYABLE_FRAMES - 1:
		probe.frame(0.016)
	_check(probe.startup_ms < 0, "9 images jouables : pas encore démarré")
	probe.frame(0.016)
	_check(probe.startup_ms >= 0, "10 images de suite sous 33 ms : démarrage noté (%d ms)" % probe.startup_ms)
	probe._last_us -= PerfProbe.PERIOD_US
	probe.frame(0.016)
	probe.close()
	_check(not PerfProbe.active, "sonde refermée : inactive")
	var sac := FileAccess.get_file_as_string(dir.path_join("saccades.csv")).strip_edges().split("\n")
	_check(sac.size() == 3 and sac[0] == ";".join(PerfProbe.SACCADE_COLUMNS) and probe.saccades_written == 2, "deux saccades écrites")
	var s1 := sac[1].split(";") if sac.size() == 3 else PackedStringArray(["", "", "", "", "", ""])
	_check(s1[2] == "45.0" and s1[3] == "1234.5" and s1[4] == "tuile" and s1[5] == "tuile near:1:2 40.0",
		"saccade 1 : 45 ms à 1234,5 m, cause tuile (%s)" % sac[1] if sac.size() > 1 else "?")
	_check(sac.size() == 3 and sac[2].split(";")[4] == "inconnue", "saccade 2 sans étape : inconnue")
	var tasks := FileAccess.get_file_as_string(dir.path_join("taches.csv")).strip_edges().split("\n")
	_check(tasks.size() == 2 and tasks[1].ends_with(";arbres;1:2;7.25"), "tâche de fond écrite à la seconde (%s)" % tasks[-1])
	_check(FileAccess.get_file_as_string(dir.path_join("demarrage.txt")).begins_with("Démarrage : première image jouable à "),
		"demarrage.txt écrit")
	for f in ["saccades.csv", "taches.csv", "demarrage.txt"]:
		DirAccess.remove_absolute(dir.path_join(f))
	DirAccess.remove_absolute(csv)
	DirAccess.remove_absolute(dir)

	print("test_perf_probe : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
