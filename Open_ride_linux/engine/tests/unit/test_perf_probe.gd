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
	DirAccess.remove_absolute(csv)
	DirAccess.remove_absolute(dir)

	print("test_perf_probe : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
