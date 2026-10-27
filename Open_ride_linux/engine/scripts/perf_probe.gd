extends RefCounted

## Sonde de performance du moteur (lot X13).
##
## Activée par `--perf-probe=FICHIER.csv` (engine_args.gd). Chaque seconde, une ligne est ajoutée au
## fichier : temps d'image (p50, p99, max), temps CPU et GPU de la vue mesurés par le RenderingServer,
## appels de dessin, objets et primitives dessinés, mémoire vidéo, tuiles chargées et instances d'arbres.
## Le fichier est vidé à chaque ligne : il se lit pendant l'essai (`engine/tests/perf_probe.py`, qui
## ajoute nvidia-smi et le CPU des processus, puis trace les courbes).
## Pas de class_name : chargé par preload.

const COLUMNS := ["t_s", "unix_s", "fps", "frame_p50_ms", "frame_p99_ms", "frame_max_ms", "cpu_ms", "gpu_ms",
	"draw_calls", "objects", "primitives", "vram_mb", "texture_mb", "buffer_mb", "static_mb", "nodes",
	"near_tiles", "far_tiles", "osm_chunks", "trees", "preset"]
const PERIOD_US := 1_000_000

var path := ""
var preset := ""
var _file: FileAccess = null
var _frames: Array[float] = []
var _cpu_sum := 0.0
var _gpu_sum := 0.0
var _start_us := 0
var _last_us := 0
var _viewport_rid := RID()
var rows_written := 0


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
	if viewport != null:
		_viewport_rid = viewport.get_viewport_rid()
		RenderingServer.viewport_set_measure_render_time(_viewport_rid, true)
	_start_us = Time.get_ticks_usec()
	_last_us = _start_us
	print("[perf-sonde] mesures chaque seconde dans ", csv_path)
	return true


func is_open() -> bool:
	return _file != null


## À appeler à chaque image. `streamer` : world_streamer.gd (ou null).
func frame(delta: float, streamer = null) -> void:
	if _file == null:
		return
	_frames.append(delta * 1000.0)
	if _viewport_rid.is_valid():
		_cpu_sum += RenderingServer.viewport_get_measured_render_time_cpu(_viewport_rid) \
			+ RenderingServer.get_frame_setup_time_cpu()
		_gpu_sum += RenderingServer.viewport_get_measured_render_time_gpu(_viewport_rid)
	var now := Time.get_ticks_usec()
	if now - _last_us < PERIOD_US:
		return
	var row := frame_stats(_frames)
	var n := maxi(_frames.size(), 1)
	row["t_s"] = float(now - _start_us) / 1e6
	row["unix_s"] = Time.get_unix_time_from_system()   # recalage avec nvidia-smi et le CPU des processus
	row["cpu_ms"] = _cpu_sum / n
	row["gpu_ms"] = _gpu_sum / n
	row.merge(render_counters())
	row.merge(world_counters(streamer))
	row["preset"] = preset
	_file.store_line(csv_line(row))
	_file.flush()
	rows_written += 1
	_frames.clear()
	_cpu_sum = 0.0
	_gpu_sum = 0.0
	_last_us = now


func close() -> void:
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
	var out := {"near_tiles": 0, "far_tiles": 0, "osm_chunks": 0, "trees": 0}
	if streamer == null:
		return out
	var tiles: Dictionary = streamer.loaded_tile_counts()
	out["near_tiles"] = int(tiles.get("near", 0))
	out["far_tiles"] = int(tiles.get("far", 0))
	if streamer.osm_streamer != null:
		out["osm_chunks"] = streamer.osm_streamer.loaded_chunk_count()
	if streamer.tree_renderer != null:
		out["trees"] = streamer.tree_renderer.get_active_tree_count()
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
