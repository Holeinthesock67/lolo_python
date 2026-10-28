extends RefCounted

## Sonde de performance du moteur (lot X13).
##
## Activée par `--perf-probe=FICHIER.csv` (engine_args.gd). Chaque seconde, une ligne est ajoutée au
## fichier : temps d'image (p50, p99, max), temps CPU et GPU de la vue mesurés par le RenderingServer,
## appels de dessin, objets et primitives dessinés, mémoire vidéo, tuiles chargées, instances d'arbres et
## tuiles proches écartées par le tri du visible (lot S1).
## Le fichier est vidé à chaque ligne : il se lit pendant l'essai (`engine/tests/perf_probe.py`, qui
## ajoute nvidia-smi et le CPU des processus, puis trace les courbes).
## Les images d'une capture d'écran de test (`mark_capture`, lot X35) et les deux suivantes sont mises à
## part : la lecture de l'image et l'écriture du PNG coûtent 100 à 150 ms et faussaient p99 et pire image.
## Elles comptent dans les images/s, sortent de p50, p99 et pire image, et sont comptées dans `capture`
## (nombre d'images mises à part dans la seconde) et `capture_max_ms`.
## Lot X15, à côté du fichier de la sonde :
## - `saccades.csv` : une ligne par image de plus de 33 ms (heure, durée, distance) avec les étapes du fil
##   principal faites depuis l'image précédente (`mark` : tuile de terrain intégrée, tronçon OSM ajouté,
##   arbres posés) et la capture du banc ; la cause est l'étape la plus longue si elle prend au moins le quart
##   de l'image ; Godot 4.3 ne publie pas le nombre de pipelines compilés, une image lente sans étape assez
##   longue est notée « inconnue » (compilation de shader, rendu lent, ramasse-miettes…) ;
## - `taches.csv` : durée de chaque tâche de fond (`task` : terrain, route, arbres, bâtiments, OSM d'un tronçon) ;
## - `demarrage.txt` : « Démarrage : première image jouable à N ms » (depuis le lancement de l'engine), à la
##   première de 10 images de suite sous 33 ms une fois le parcours chargé (`route_ready`).
## `mark` et `task` sont statiques (appelées depuis le streaming et les fils de WorkerThreadPool) et ne
## font rien sans sonde ouverte.
## Pas de class_name : chargé par preload.

const COLUMNS := ["t_s", "unix_s", "fps", "frame_p50_ms", "frame_p99_ms", "frame_max_ms", "cpu_ms", "gpu_ms",
	"draw_calls", "objects", "primitives", "vram_mb", "texture_mb", "buffer_mb", "static_mb", "nodes",
	"near_tiles", "far_tiles", "osm_chunks", "trees", "culled_near", "capture", "capture_max_ms", "preset"]
const PERIOD_US := 1_000_000
const CAPTURE_FRAMES := 3   # image de la capture et les deux suivantes
const SACCADE_MS := 33.0     # image lente : plus de 33 ms (moins de 30 images/s)
const PLAYABLE_FRAMES := 10  # démarrage : images de suite sous SACCADE_MS
const CAUSE_SHARE := 0.25    # une étape explique une image lente si elle en prend au moins le quart
const SACCADE_COLUMNS := ["t_s", "unix_s", "frame_ms", "distance_m", "cause", "steps"]
const TASK_COLUMNS := ["t_s", "kind", "id", "ms"]

## Sonde ouverte : seule condition pour que `mark` et `task` retiennent quelque chose.
static var active := false
static var _mutex := Mutex.new()
static var _steps: Array = []    # [type, id, ms] du fil principal depuis la dernière image
static var _tasks: Array = []    # [type, id, ms] des tâches de fond depuis la dernière seconde

var path := ""
var preset := ""
var _file: FileAccess = null
var _frames: Array[float] = []
var _captured: Array[float] = []
var _capture_left := 0
var _cpu_sum := 0.0
var _gpu_sum := 0.0
var _start_us := 0
var _last_us := 0
var _viewport_rid := RID()
var rows_written := 0
var saccades_written := 0
var distance_m := 0.0          # position affichée (main.gd), notée avec chaque saccade
var startup_ms := -1           # première image jouable, -1 tant qu'elle n'est pas atteinte
var _saccades: FileAccess = null
var _task_file: FileAccess = null
var _route_ready := false
var _good_run := 0
var _good_run_start_ms := 0


## Ouvre le fichier et active la mesure du temps de rendu de la vue. Renvoie false si le fichier ne
## s'ouvre pas (la sonde reste alors inactive).
func open(csv_path: String, viewport: Viewport, preset_name: String) -> bool:
	path = csv_path
	preset = preset_name
	DirAccess.make_dir_recursive_absolute(csv_path.get_base_dir())
	_file = FileAccess.open(csv_path, FileAccess.WRITE)
	if _file == null:
		printerr("Sonde de performance : impossible d'écrire ", csv_path)
		return false
	_file.store_line(";".join(COLUMNS))
	_file.flush()
	_saccades = FileAccess.open(csv_path.get_base_dir().path_join("saccades.csv"), FileAccess.WRITE)
	_task_file = FileAccess.open(csv_path.get_base_dir().path_join("taches.csv"), FileAccess.WRITE)
	if _saccades != null:
		_saccades.store_line(";".join(SACCADE_COLUMNS))
	if _task_file != null:
		_task_file.store_line(";".join(TASK_COLUMNS))
	_mutex.lock()
	_steps.clear()
	_tasks.clear()
	_mutex.unlock()
	active = true
	if viewport != null:
		_viewport_rid = viewport.get_viewport_rid()
		RenderingServer.viewport_set_measure_render_time(_viewport_rid, true)
	_start_us = Time.get_ticks_usec()
	_last_us = _start_us
	print("[perf-sonde] mesures chaque seconde dans ", csv_path)
	return true


func is_open() -> bool:
	return _file != null


## À appeler juste après une capture d'écran de test : les CAPTURE_FRAMES prochaines images sont mises à part.
func mark_capture() -> void:
	_capture_left = CAPTURE_FRAMES


## Étape du fil principal (lot X15) : `kind` (tuile, osm, arbres…), identifiant, durée en ms.
static func mark(kind: String, id: String, ms: float) -> void:
	if not active:
		return
	_mutex.lock()
	_steps.append([kind, id, ms])
	_mutex.unlock()


## Tâche de fond terminée (lot X15), depuis n'importe quel fil : type, identifiant du tronçon, durée en ms.
static func task(kind: String, id: String, ms: float) -> void:
	if not active:
		return
	_mutex.lock()
	_tasks.append([kind, id, ms])
	_mutex.unlock()


## Parcours chargé (main.gd) : le compte des images jouables commence.
func route_ready() -> void:
	_route_ready = true
	_good_run = 0


## Cause d'une image lente de `frame_ms` : capture du banc, sinon étape la plus longue du fil principal si
## elle prend au moins le quart de l'image (CAUSE_SHARE), sinon « inconnue » (les étapes restent listées).
## `steps` : [[type, id, ms], …] ; renvoie {cause, steps (texte « type id ms | … »)}.
static func saccade_cause(steps: Array, capture: bool, frame_ms: float) -> Dictionary:
	var parts := PackedStringArray()
	var worst: Array = []
	for st in steps:
		parts.append("%s %s %.1f" % [st[0], st[1], float(st[2])])
		if worst.is_empty() or float(st[2]) > float(worst[2]):
			worst = st
	var cause := "inconnue"
	if capture:
		cause = "capture"
	elif not worst.is_empty() and float(worst[2]) >= frame_ms * CAUSE_SHARE:
		cause = str(worst[0])
	return {"cause": cause, "steps": " | ".join(parts)}


func _frame_x15(frame_ms: float, capture: bool) -> void:
	_mutex.lock()
	var steps := _steps.duplicate()
	_steps.clear()
	_mutex.unlock()
	var now_ms := Time.get_ticks_msec()
	if frame_ms > SACCADE_MS:
		_good_run = 0
		if _saccades != null:
			var c := saccade_cause(steps, capture, frame_ms)
			_saccades.store_line(";".join(PackedStringArray([
				"%.3f" % (float(Time.get_ticks_usec() - _start_us) / 1e6), "%.3f" % Time.get_unix_time_from_system(),
				"%.1f" % frame_ms, "%.1f" % distance_m, c["cause"], str(c["steps"]).replace(";", ",")])))
			_saccades.flush()
			saccades_written += 1
	elif _route_ready and startup_ms < 0:
		if _good_run == 0:
			_good_run_start_ms = now_ms
		_good_run += 1
		if _good_run >= PLAYABLE_FRAMES:
			startup_ms = _good_run_start_ms
			var line := "Démarrage : première image jouable à %d ms" % startup_ms
			print(line)
			var f := FileAccess.open(path.get_base_dir().path_join("demarrage.txt"), FileAccess.WRITE)
			if f != null:
				f.store_line(line)


func _flush_tasks(t_s: float) -> void:
	_mutex.lock()
	var tasks := _tasks.duplicate()
	_tasks.clear()
	_mutex.unlock()
	if _task_file == null or tasks.is_empty():
		return
	for tk in tasks:
		_task_file.store_line("%.3f;%s;%s;%.2f" % [t_s, tk[0], str(tk[1]).replace(";", ","), float(tk[2])])
	_task_file.flush()


## À appeler à chaque image. `streamer` : world_streamer.gd (ou null).
func frame(delta: float, streamer = null) -> void:
	if _file == null:
		return
	var capture := _capture_left > 0
	if capture:
		_capture_left -= 1
		_captured.append(delta * 1000.0)
	else:
		_frames.append(delta * 1000.0)
	_frame_x15(delta * 1000.0, capture)
	if _viewport_rid.is_valid():
		_cpu_sum += RenderingServer.viewport_get_measured_render_time_cpu(_viewport_rid) \
			+ RenderingServer.get_frame_setup_time_cpu()
		_gpu_sum += RenderingServer.viewport_get_measured_render_time_gpu(_viewport_rid)
	var now := Time.get_ticks_usec()
	if now - _last_us < PERIOD_US:
		return
	var row := frame_stats(_frames)
	row.merge(capture_stats(_frames, _captured), true)
	var n := maxi(_frames.size() + _captured.size(), 1)
	row["t_s"] = float(now - _start_us) / 1e6
	row["unix_s"] = Time.get_unix_time_from_system()   # recalage avec nvidia-smi et le CPU des processus
	row["cpu_ms"] = _cpu_sum / n
	row["gpu_ms"] = _gpu_sum / n
	row.merge(render_counters())
	row.merge(world_counters(streamer))
	row["preset"] = preset
	_flush_tasks(row["t_s"])
	_file.store_line(csv_line(row))
	_file.flush()
	rows_written += 1
	_frames.clear()
	_captured.clear()
	_cpu_sum = 0.0
	_gpu_sum = 0.0
	_last_us = now


func close() -> void:
	active = false
	for f in [_saccades, _task_file]:
		if f != null:
			f.close()
	_saccades = null
	_task_file = null
	if _file != null:
		_file.close()
		_file = null
	if _viewport_rid.is_valid():
		RenderingServer.viewport_set_measure_render_time(_viewport_rid, false)


## Images par seconde et temps d'image (ms) d'une série : {fps, frame_p50_ms, frame_p99_ms, frame_max_ms}.
static func frame_stats(times_ms: Array) -> Dictionary:
	var n := times_ms.size()
	if n == 0:
		return {"fps": 0.0, "frame_p50_ms": 0.0, "frame_p99_ms": 0.0, "frame_max_ms": 0.0}
	var sorted := times_ms.duplicate()
	sorted.sort()
	var total := 0.0
	for t in sorted:
		total += float(t)
	return {
		"fps": float(n) / (total / 1000.0) if total > 0.0 else 0.0,
		"frame_p50_ms": float(sorted[int(floor(float(n) * 0.50))]),
		"frame_p99_ms": float(sorted[mini(int(floor(float(n) * 0.99)), n - 1)]),
		"frame_max_ms": float(sorted[n - 1]),
	}


## Images mises à part pour une capture : leur nombre, la pire, et les images/s de la seconde comptées
## avec elles (le temps passé reste du temps écoulé).
static func capture_stats(times_ms: Array, captured_ms: Array) -> Dictionary:
	var out := {"capture": captured_ms.size(), "capture_max_ms": 0.0}
	if captured_ms.is_empty():
		return out
	var total := 0.0
	for t in times_ms + captured_ms:
		total += float(t)
	out["capture_max_ms"] = float(captured_ms.max())
	out["fps"] = float(times_ms.size() + captured_ms.size()) / (total / 1000.0) if total > 0.0 else 0.0
	return out


## Compteurs du rendu de la dernière image et mémoire (Mo).
static func render_counters() -> Dictionary:
	const MB := 1048576.0
	return {
		"draw_calls": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
		"objects": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
		"primitives": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME),
		"vram_mb": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_VIDEO_MEM_USED) / MB,
		"texture_mb": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED) / MB,
		"buffer_mb": RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_BUFFER_MEM_USED) / MB,
		"static_mb": Performance.get_monitor(Performance.MEMORY_STATIC) / MB,
		"nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
	}


## Tuiles et objets du décor chargés par world_streamer.gd.
static func world_counters(streamer) -> Dictionary:
	var out := {"near_tiles": 0, "far_tiles": 0, "osm_chunks": 0, "trees": 0, "culled_near": 0}
	if streamer == null:
		return out
	var tiles: Dictionary = streamer.loaded_tile_counts()
	out["near_tiles"] = int(tiles.get("near", 0))
	out["far_tiles"] = int(tiles.get("far", 0))
	if streamer.osm_streamer != null:
		out["osm_chunks"] = streamer.osm_streamer.loaded_chunk_count()
	if streamer.tree_renderer != null:
		out["trees"] = streamer.tree_renderer.get_active_tree_count()
	if "culled_near" in streamer:
		out["culled_near"] = int(streamer.culled_near)
	return out


## Ligne CSV (séparateur « ; ») dans l'ordre de COLUMNS ; une colonne absente reste vide.
static func csv_line(row: Dictionary) -> String:
	var cells := PackedStringArray()
	for c in COLUMNS:
		var v = row.get(c, "")
		if v is float:
			cells.append("%.2f" % v)
		else:
			cells.append(str(v))
	return ";".join(cells)
