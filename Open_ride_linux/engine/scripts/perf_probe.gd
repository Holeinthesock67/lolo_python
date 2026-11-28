extends RefCounted

## Sonde de performance du moteur (lot X13).
##
## Activée par `--perf-probe=FICHIER.csv` (engine_args.gd). Chaque seconde, une ligne est ajoutée au
## fichier : temps d'image (p50, p99, max), temps CPU et GPU de la vue mesurés par le RenderingServer,
## appels de dessin, objets et primitives dessinés, mémoire vidéo, tuiles chargées, instances d'arbres et
## tuiles proches écartées par le tri du visible (lot S1).
## Le fichier est vidé à chaque ligne : il se lit pendant l'essai (`engine/tests/perf_probe.py`, qui
## ajoute nvidia-smi et le CPU des processus, puis trace les courbes).
## Capture d'écran de test (`mark_capture`, lot X35) : la lecture de l'image et l'écriture du PNG coûtent 100 à
## 300 ms. Depuis le lot PI1, `main.gd` mesure ce coût et la sonde le retire de l'image de la capture, qui garde
## le reste de son temps dans p50, p99 et pire image : un gel de 3,9 s tombé sur une capture n'est plus caché
## (banc rPI1 du 19 novembre). La capture est aussi une étape (`capture`) de saccades.csv ; `capture` compte les
## images de capture de la seconde et `capture_max_ms` donne la pire, coût compris.
## Lot X15, à côté du fichier de la sonde :
## - `saccades.csv` : une ligne par image de plus de 33 ms (heure, durée, distance) avec les étapes du fil
##   principal faites depuis l'image précédente (`mark` : tuile de terrain intégrée, tronçon OSM ajouté,
##   arbres posés ; `mark_since` : mises à jour de chaque image, fenêtre du streaming, bots, herbe, détails
##   du sol, décor vivant, atmosphère, arches) et la capture du banc ; la cause est l'étape la plus longue si elle prend au moins le quart
##   de l'image ; Godot 4.3 ne publie pas le nombre de pipelines compilés, une image lente sans étape assez
##   longue est notée « inconnue » (rendu lent, envoi au GPU…) ; depuis Godot 4.4, le nombre de pipelines compilés
##   est publié (`Performance.PIPELINE_COMPILATIONS_*`) : colonne `pipelines` (compilés pendant l'image), et cause
##   « shaders » quand aucune étape n'explique l'image et qu'au moins un pipeline a été compilé (pire image, 17/11) ;
## - `taches.csv` : durée de chaque tâche de fond (`task` : terrain, route, arbres, bâtiments, OSM d'un tronçon) ;
## - `demarrage.txt` : « Démarrage : première image jouable à N ms » (depuis le lancement de l'engine), à la
##   première de 10 images de suite sous 33 ms une fois le parcours chargé (`route_ready`).
## Temps d'image (pire image, 17/11) : le plus grand du `delta` de Godot et du temps réel écoulé depuis l'image
## précédente. Godot borne `delta` quand il prend du retard (8 pas de physique au plus, 133 à 150 ms) : toutes les
## pires images des bancs plafonnaient à 150 ms. Le temps réel donne la vraie durée ; `delta_ms` de saccades.csv
## garde le `delta` de Godot pour comparer.
## `mark` et `task` sont statiques (appelées depuis le streaming et les fils de WorkerThreadPool) et ne
## font rien sans sonde ouverte.
## Pas de class_name : chargé par preload.

const COLUMNS := ["t_s", "unix_s", "fps", "frame_p50_ms", "frame_p99_ms", "frame_max_ms", "cpu_ms", "gpu_ms",
	"draw_calls", "objects", "primitives", "vram_mb", "texture_mb", "buffer_mb", "static_mb", "nodes",
	"near_tiles", "far_tiles", "osm_chunks", "trees", "culled_near", "capture", "capture_max_ms", "pipelines", "wind_phase", "wind_strength", "wind_gust", "preset"]
const PERIOD_US := 1_000_000
const CAPTURE_FRAMES := 1   # image de la capture (son coût mesuré en est retiré)
const SACCADE_MS := 33.0     # image lente : plus de 33 ms (moins de 30 images/s)
const PLAYABLE_FRAMES := 10  # démarrage : images de suite sous SACCADE_MS
const CAUSE_SHARE := 0.25    # une étape explique une image lente si elle en prend au moins le quart
const SACCADE_COLUMNS := ["t_s", "unix_s", "frame_ms", "distance_m", "cause", "steps", "delta_ms", "pipelines", "process_ms"]
## Compteurs de pipelines compilés publiés par Godot (totaux depuis le lancement), sommés.
const PIPELINE_MONITORS := [Performance.PIPELINE_COMPILATIONS_CANVAS, Performance.PIPELINE_COMPILATIONS_MESH,
	Performance.PIPELINE_COMPILATIONS_SURFACE, Performance.PIPELINE_COMPILATIONS_DRAW,
	Performance.PIPELINE_COMPILATIONS_SPECIALIZATION]
const TASK_COLUMNS := ["t_s", "kind", "id", "ms"]

## Sonde ouverte : seule condition pour que `mark` et `task` retiennent quelque chose.
static var active := false
static var _mutex := Mutex.new()
static var _steps: Array = []    # [type, id, ms] du fil principal depuis la dernière image
static var _tasks: Array = []    # [type, id, ms] des tâches de fond depuis la dernière seconde

var path := ""
var preset := ""
## Vent du décor de l'image (`living_world.last_wind`, posé par main.gd avant `frame`) : colonnes wind_phase,
## wind_strength et wind_gust (lot EC10, revue E12-51 : vitesse de la phase vérifiée sur une longue séance,
## `engine/tests/wind_phase_check.py`).
var wind: Dictionary = {}
var _file: FileAccess = null
var _frames: Array[float] = []
var _captured: Array[float] = []
var _capture_left := 0
var _capture_cost_ms := 0.0    # coût mesuré de la capture en attente, retiré de son image
var _capture_removed_ms := 0.0 # coût des captures retiré depuis la dernière ligne (images/s)
var _pending: Dictionary = {}  # saccade écrite à l'image suivante (process_ms lu deux fois)
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
var _prev_frame_us := 0        # heure de l'image précédente (temps réel de l'image)
var _pipelines_total := -1     # total des pipelines compilés à l'image précédente (-1 : pas encore lu)
var _pipelines_sec := 0        # pipelines compilés depuis la dernière ligne


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
	_prev_frame_us = 0
	_pipelines_total = -1
	_pipelines_sec = 0
	print("[perf-sonde] mesures chaque seconde dans ", csv_path)
	return true


func is_open() -> bool:
	return _file != null


## À appeler juste après une capture d'écran de test, avec son coût mesuré (lecture de l'image et PNG, ms) :
## retiré de l'image en cours, et noté comme étape `capture` pour la cause de la saccade.
func mark_capture(cost_ms: float = 0.0) -> void:
	_capture_left = CAPTURE_FRAMES
	_capture_cost_ms = maxf(cost_ms, 0.0)
	mark("capture", "", _capture_cost_ms)


## Étape du fil principal (lot X15) : `kind` (tuile, osm, arbres…), identifiant, durée en ms.
static func mark(kind: String, id: String, ms: float) -> void:
	if not active:
		return
	_mutex.lock()
	_steps.append([kind, id, ms])
	_mutex.unlock()


## Étape du fil principal commencée à `t0_us` (Time.get_ticks_usec) et finie maintenant : comme `mark`.
## Sert aux mises à jour faites à chaque image (décor vivant, herbe, bots…) : une saccade dont la cause était
## « inconnue » nomme alors l'étape qui a pris le temps. Sans sonde ouverte : rien (un test de booléen).
static func mark_since(kind: String, id: String, t0_us: int) -> void:
	if not active:
		return
	mark(kind, id, (Time.get_ticks_usec() - t0_us) / 1000.0)


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


## Cause d'une image lente de `frame_ms` : étape la plus longue du fil principal (la capture du banc en est une) si
## elle prend au moins le quart de l'image (CAUSE_SHARE), sinon « inconnue » (les étapes restent listées).
## `steps` : [[type, id, ms], …] ; renvoie {cause, steps (texte « type id ms | … »)}.
## `pipelines` : pipelines compilés pendant l'image ; sans étape qui explique l'image, cause « shaders » s'il y en a,
## sinon « scripts » si les `_process` de l'image (`process_ms`, Performance.TIME_PROCESS) en prennent le quart
## (travail des scripts pas encore noté par une étape), sinon « inconnue » (rendu, envoi au GPU, pilote…).
static func saccade_cause(steps: Array, frame_ms: float, pipelines: int = 0,
		process_ms: float = 0.0) -> Dictionary:
	var parts := PackedStringArray()
	var worst: Array = []
	for st in steps:
		parts.append("%s %s %.1f" % [st[0], st[1], float(st[2])])
		if worst.is_empty() or float(st[2]) > float(worst[2]):
			worst = st
	var cause := "inconnue"
	if not worst.is_empty() and float(worst[2]) >= frame_ms * CAUSE_SHARE:
		cause = str(worst[0])
	elif pipelines > 0:
		cause = "shaders"
	elif process_ms >= frame_ms * CAUSE_SHARE:
		cause = "scripts"
	return {"cause": cause, "steps": " | ".join(parts)}


## Saccade en attente écrite avec le `process_ms` le plus grand des deux lectures : Godot publie TIME_PROCESS après
## l'image, et selon l'ordre des nœuds le temps de l'image lente se lit à cette image ou à la suivante.
func _write_pending(process_now_ms: float) -> void:
	if _pending.is_empty() or _saccades == null:
		_pending = {}
		return
	var pr := maxf(float(_pending["process_ms"]), process_now_ms)
	var c := saccade_cause(_pending["steps"], _pending["frame_ms"], _pending["pipelines"], pr)
	_saccades.store_line(";".join(PackedStringArray([
		"%.3f" % _pending["t_s"], "%.3f" % _pending["unix_s"], "%.1f" % _pending["frame_ms"],
		"%.1f" % _pending["distance_m"], c["cause"], str(c["steps"]).replace(";", ","),
		"%.1f" % _pending["delta_ms"], str(_pending["pipelines"]), "%.1f" % pr])))
	_saccades.flush()
	saccades_written += 1
	_pending = {}


func _frame_x15(frame_ms: float, delta_ms: float = NAN, pipelines: int = 0, process_ms: float = 0.0) -> void:
	_mutex.lock()
	var steps := _steps.duplicate()
	_steps.clear()
	_mutex.unlock()
	_write_pending(process_ms)
	var now_ms := Time.get_ticks_msec()
	if frame_ms > SACCADE_MS:
		_good_run = 0
		if _saccades != null:
			_pending = {"t_s": float(Time.get_ticks_usec() - _start_us) / 1e6, "unix_s": Time.get_unix_time_from_system(),
				"frame_ms": frame_ms, "distance_m": distance_m, "steps": steps, "pipelines": pipelines,
				"delta_ms": frame_ms if is_nan(delta_ms) else delta_ms, "process_ms": process_ms}
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


## Temps d'image (ms) : le plus grand du `delta` de Godot et du temps réel depuis l'image précédente
## (`prev_us`, 0 : première image, `delta` seul). Godot borne `delta` à 8 pas de physique quand il prend du retard.
static func frame_time_ms(delta: float, prev_us: int, now_us: int) -> float:
	var wall := float(now_us - prev_us) / 1000.0 if prev_us > 0 else 0.0
	return maxf(delta * 1000.0, wall)


## Total des pipelines compilés depuis le lancement (0 sans rendu, sous --headless).
static func pipeline_total() -> int:
	var n := 0
	for m in PIPELINE_MONITORS:
		n += int(Performance.get_monitor(m))
	return n


## À appeler à chaque image. `streamer` : world_streamer.gd (ou null).
func frame(delta: float, streamer = null) -> void:
	if _file == null:
		return
	var t_us := Time.get_ticks_usec()
	var frame_ms := frame_time_ms(delta, _prev_frame_us, t_us)
	_prev_frame_us = t_us
	var total := pipeline_total()
	var pipelines := maxi(total - _pipelines_total, 0) if _pipelines_total >= 0 else 0
	_pipelines_total = total
	_pipelines_sec += pipelines
	# Image d'une capture : son coût mesuré en est retiré, le reste compte comme toute image.
	var own := frame_ms
	if _capture_left > 0:
		_capture_left -= 1
		own = maxf(frame_ms - _capture_cost_ms, 0.0)
		_captured.append(frame_ms)
		_capture_removed_ms += frame_ms - own
		_capture_cost_ms = 0.0
	_frames.append(own)
	# Temps des `_process` publié par Godot (voir `_write_pending`).
	var process_ms := float(Performance.get_monitor(Performance.TIME_PROCESS)) * 1000.0
	_frame_x15(frame_ms, delta * 1000.0, pipelines, process_ms)
	if _viewport_rid.is_valid():
		_cpu_sum += RenderingServer.viewport_get_measured_render_time_cpu(_viewport_rid) \
			+ RenderingServer.get_frame_setup_time_cpu()
		_gpu_sum += RenderingServer.viewport_get_measured_render_time_gpu(_viewport_rid)
	var now := Time.get_ticks_usec()
	if now - _last_us < PERIOD_US:
		return
	var row := frame_stats(_frames)
	row.merge(capture_stats(_frames, _captured, _capture_removed_ms), true)
	var n := maxi(_frames.size(), 1)
	row["t_s"] = float(now - _start_us) / 1e6
	row["unix_s"] = Time.get_unix_time_from_system()   # recalage avec nvidia-smi et le CPU des processus
	row["cpu_ms"] = _cpu_sum / n
	row["gpu_ms"] = _gpu_sum / n
	row.merge(render_counters())
	row.merge(world_counters(streamer))
	row["pipelines"] = _pipelines_sec
	if not wind.is_empty():
		row["wind_phase"] = float(wind.get("phase", 0.0))
		row["wind_strength"] = float(wind.get("strength", 0.0))
		row["wind_gust"] = float(wind.get("gust", 0.0))
	row["preset"] = preset
	_flush_tasks(row["t_s"])
	_file.store_line(csv_line(row))
	_file.flush()
	rows_written += 1
	_frames.clear()
	_captured.clear()
	_capture_removed_ms = 0.0
	_cpu_sum = 0.0
	_gpu_sum = 0.0
	_pipelines_sec = 0
	_last_us = now


func close() -> void:
	_write_pending(0.0)
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


## Images de capture de la seconde : leur nombre, la pire (coût compris), et les images/s de la seconde avec le
## coût des captures (`removed_ms`, retiré des temps d'image `times_ms` mais bien écoulé).
static func capture_stats(times_ms: Array, captured_ms: Array, removed_ms: float = 0.0) -> Dictionary:
	var out := {"capture": captured_ms.size(), "capture_max_ms": 0.0}
	if captured_ms.is_empty():
		return out
	var total := removed_ms
	for t in times_ms:
		total += float(t)
	out["capture_max_ms"] = float(captured_ms.max())
	out["fps"] = float(times_ms.size()) / (total / 1000.0) if total > 0.0 else 0.0
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
