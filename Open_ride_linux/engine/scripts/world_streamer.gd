extends Node3D

## Chargement par tronçons du ruban de route et des tuiles de terrain (lots E1 et E3).
##
## Fenêtre active, recalculée par update_window(s, v, caméra) à chaque image :
## - ruban : tronçons k dont l'intervalle [k × 1 000, (k + 1) × 1 000] touche (au sens strict)
##   [s − chunks_behind × 1 000 ; s + chunks_ahead × 1 000 + v × 10 s] ;
## - tuiles proches dont le carré passe à moins de 1 500 m de la caméra ou du point visé v × 10 s
##   plus loin ; tuiles lointaines présentes à moins de 12 km ;
## - tuile proche manquante : rien si une tuile lointaine couvre l'endroit (elle est dessinée dessous),
##   sinon tuile plate à l'altitude de la route la plus proche (format §10).
## Les tableaux de sommets se calculent dans WorkerThreadPool ; les ArrayMesh et MeshInstance3D se
## créent sur le fil principal, au plus MAX_NEW_PER_FRAME par image. Ce qui sort de la fenêtre est
## libéré tout de suite (free) ; un changement de parcours vide tout (set_world).
## Sans couche terrain : sol plat 5 m sous l'altitude minimale de la route, qui suit la caméra.
## Pas de class_name (charger par preload).

const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const TerrainMaterial := preload("res://scripts/terrain_material.gd")
const ThemeRenderParams := preload("res://scripts/theme_render_params.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")

const LOOKAHEAD_S := 10.0
const NEAR_RADIUS_M := 1500.0
const FAR_RADIUS_M := 12000.0
const MAX_NEW_PER_FRAME := 2
const MAX_RUNNING_TASKS := 4
const FLAT_GROUND_BELOW_M := 5.0
const FLAT_GROUND_COLOR := Color(0.33, 0.42, 0.28)

var route = null
var world_dir := ""
var has_terrain := false
var chunks_ahead: int = 3
var chunks_behind: int = 1
var vegetation_density_factor: float = 0.3
var tree_renderer: Node3D = null
var osm_streamer: Node3D = null

var _near_index: Dictionary = {}     # Vector2i -> true
var _far_index: Dictionary = {}
var _wanted: Dictionary = {}         # clé -> description du travail {kind, ...}
var _instances: Dictionary = {}      # clé -> MeshInstance3D
var _jobs: Dictionary = {}           # clé -> {task, arrays, origin, gen}
var _ready: Array = []               # travaux terminés, à instancier : {key, arrays, origin}
var _generation := 0
var _road_material: StandardMaterial3D
var _terrain_material: Material
var _road_width_m: float = RoadBuilder.ROAD_WIDTH_M
var _ground_color: Color = FLAT_GROUND_COLOR
var _ground: MeshInstance3D = null
var _theme_dict: Dictionary = {}
var _manifest: Variant = null

## Mesures pour le rapport de performance : clé de type -> [nombre, µs cumulées].
var build_stats: Dictionary = {}
var _stats_mutex := Mutex.new()


func _init() -> void:
	_road_material = RoadBuilder.make_material()
	_terrain_material = TerrainMaterial.create_material()


func _process(_delta: float) -> void:
	integrate(MAX_NEW_PER_FRAME)


func _exit_tree() -> void:
	_wait_all_jobs()


## Nouveau parcours (ou parcours rechargé) : tout est vidé puis reconstruit au fil des images.
func set_world(new_route, new_world_dir: String) -> void:
	clear()
	route = new_route
	world_dir = new_world_dir
	has_terrain = false
	_manifest = JSON.parse_string(FileAccess.get_file_as_string(world_dir.path_join("manifest.json"))) \
		if FileAccess.file_exists(world_dir.path_join("manifest.json")) else null
	if typeof(_manifest) == TYPE_DICTIONARY:
		var layers = _manifest.get("layers", {})
		if typeof(layers) == TYPE_DICTIONARY and typeof(layers.get("terrain")) == TYPE_DICTIONARY:
			has_terrain = bool(layers["terrain"].get("present", false))
	if has_terrain:
		_near_index = TerrainTiles.scan_index(world_dir, "near")
		_far_index = TerrainTiles.scan_index(world_dir, "far")
		if _near_index.is_empty() and _far_index.is_empty():
			push_warning("Couche terrain déclarée mais aucune tuile trouvée : sol plat")
			has_terrain = false
	if not has_terrain:
		_make_ground()
	if osm_streamer != null:
		osm_streamer.set_world(route, world_dir)


func _has_layer(layer_name: String) -> bool:
	if typeof(_manifest) == TYPE_DICTIONARY:
		var layers = _manifest.get("layers", {})
		if typeof(layers) == TYPE_DICTIONARY and typeof(layers.get(layer_name)) == TYPE_DICTIONARY:
			return bool(layers[layer_name].get("present", false))
	return false


func _get_vegetation_areas(t: Vector2i) -> Array:
	if not _has_layer("vegetation") or world_dir == "":
		return []
	var areas := []
	var tile_rect := Rect2(t.x * 1000.0, t.y * 1000.0, 1000.0, 1000.0)
	var count := RoadBuilder.chunk_count(route) if route != null else 0
	for k in range(count):
		var s0 := k * RoadBuilder.CHUNK_LENGTH_M
		var s1 := (k + 1) * RoadBuilder.CHUNK_LENGTH_M
		var p0: Vector3 = route.sample_point(s0)
		var p1: Vector3 = route.sample_point(s1)
		var r_bounds := Rect2(Vector2(p0.x, p0.z), Vector2.ZERO).expand(Vector2(p1.x, p1.z)).grow(100.0)
		if r_bounds.intersects(tile_rect):
			var res := OsmLayers.load_chunk(world_dir, "vegetation", k)
			if res.get("ok", false):
				areas.append_array(res.get("items", []))
	return areas


## Retire tout : objets de scène, travaux en cours (attendus puis ignorés), sol plat.
func clear() -> void:
	_generation += 1
	_wait_all_jobs()
	_jobs.clear()
	_ready.clear()
	_wanted.clear()
	for key in _instances.keys():
		_free_instance(key)
	if tree_renderer != null:
		tree_renderer.clear()
	if osm_streamer != null:
		osm_streamer.clear()
	if _ground != null:
		remove_child(_ground)
		_ground.mesh = null
		_ground.free()
		_ground = null
	_near_index = {}
	_far_index = {}
	route = null


# --- fenêtre -----------------------------------------------------------------------------

## Tronçons de route voulus pour la position s et la vitesse v.
func road_window(s_pos: float, v: float) -> Array:
	var out := []
	if route == null:
		return out
	var count := RoadBuilder.chunk_count(route)
	if count == 0:
		return out
	var lo := s_pos - float(chunks_behind) * RoadBuilder.CHUNK_LENGTH_M
	var hi := s_pos + float(chunks_ahead) * RoadBuilder.CHUNK_LENGTH_M + maxf(v, 0.0) * LOOKAHEAD_S
	var k_lo := floori(lo / RoadBuilder.CHUNK_LENGTH_M)
	var k_hi := ceili(hi / RoadBuilder.CHUNK_LENGTH_M) - 1
	for k in range(k_lo, k_hi + 1):
		var kk := k
		if route.is_loop():
			kk = posmod(k, count)
		elif k < 0 or k >= count:
			continue
		if not out.has(kk):
			out.append(kk)
	if route.is_loop() and k_hi - k_lo + 1 >= count:
		out = range(count)
	return out


static func _rect_distance(level: String, t: Vector2i, x: float, z: float) -> float:
	var size: float = TerrainTiles.LEVELS[level]["size"]
	var dx := maxf(maxf(t.x * size - x, 0.0), x - (t.x + 1) * size)
	var dz := maxf(maxf(t.y * size - z, 0.0), z - (t.y + 1) * size)
	return Vector2(dx, dz).length()


## Tuiles proches voulues autour des points donnés (positions x, z), avec leur nature :
## "near" (fichier présent) ou "flat" (ni proche ni lointaine) ; les tuiles couvertes par le
## lointain seul ne sont pas listées.
func near_window(points: Array) -> Dictionary:
	var out := {}
	if route == null or not has_terrain:
		return out
	for p in points:
		var lo := TerrainTiles.tile_of("near", p.x - NEAR_RADIUS_M, p.y - NEAR_RADIUS_M)
		var hi := TerrainTiles.tile_of("near", p.x + NEAR_RADIUS_M, p.y + NEAR_RADIUS_M)
		for ix in range(lo.x, hi.x + 1):
			for iz in range(lo.y, hi.y + 1):
				var t := Vector2i(ix, iz)
				if out.has(t) or _rect_distance("near", t, p.x, p.y) > NEAR_RADIUS_M:
					continue
				if _near_index.has(t):
					out[t] = "near"
				elif not _far_covers(t):
					out[t] = "flat"
	return out


## Une tuile proche (1 000 m) est toujours entièrement dans une seule tuile lointaine (5 000 m).
func _far_covers(near_tile: Vector2i) -> bool:
	var c := TerrainTiles.tile_origin("near", near_tile.x, near_tile.y) + Vector3(1.0, 0.0, 1.0)
	return _far_index.has(TerrainTiles.tile_of("far", c.x, c.z))


## Tuiles lointaines présentes à moins de 12 km de la caméra.
func far_window(cam_x: float, cam_z: float) -> Array:
	var out := []
	for t in _far_index:
		if _rect_distance("far", t, cam_x, cam_z) <= FAR_RADIUS_M:
			out.append(t)
	return out


## Met à jour la fenêtre active : libère ce qui en sort, lance la génération de ce qui y entre.
func update_window(s_pos: float, v: float, cam_pos: Vector3) -> void:
	if route == null:
		return
	var wanted := {}
	for k in road_window(s_pos, v):
		wanted["road:%d" % k] = {"kind": "road", "k": k, "dist": 0.0}
	if has_terrain:
		var ahead: Vector3 = route.sample_point(route.wrap_s(s_pos + maxf(v, 0.0) * LOOKAHEAD_S))
		var near := near_window([Vector2(cam_pos.x, cam_pos.z), Vector2(ahead.x, ahead.z)])
		for t in near:
			wanted["%s:%d:%d" % [near[t], t.x, t.y]] = {"kind": near[t], "tile": t,
				"dist": _rect_distance("near", t, cam_pos.x, cam_pos.z)}
		for t in far_window(cam_pos.x, cam_pos.z):
			wanted["far:%d:%d" % [t.x, t.y]] = {"kind": "far", "tile": t,
				"dist": 10000.0 + _rect_distance("far", t, cam_pos.x, cam_pos.z)}
	_wanted = wanted
	for key in _instances.keys():
		if not _wanted.has(key):
			_free_instance(key)
	_ready = _ready.filter(func(r): return _wanted.has(r["key"]))
	_start_jobs()
	if _ground != null:
		_ground.position = Vector3(cam_pos.x, _ground.position.y, cam_pos.z)
	if tree_renderer != null:
		tree_renderer.enforce_budget(cam_pos)
	if osm_streamer != null and route != null:
		osm_streamer.update_window(s_pos - float(chunks_behind) * 1000.0, s_pos + float(chunks_ahead) * 1000.0 + v * LOOKAHEAD_S)


func _start_jobs() -> void:
	var queued := {}
	for r in _ready:
		queued[r["key"]] = true
	var todo := []
	for key in _wanted:
		if not _instances.has(key) and not _jobs.has(key) and not queued.has(key):
			todo.append(key)
	todo.sort_custom(func(a, b): return float(_wanted[a]["dist"]) < float(_wanted[b]["dist"]))
	for key in todo:
		if _jobs.size() >= MAX_RUNNING_TASKS:
			break
		var job := {"key": key, "spec": _wanted[key], "arrays": [], "origin": Vector3.ZERO, "gen": _generation,
			"route": route, "world_dir": world_dir, "road_width_m": _road_width_m}
		job["task"] = WorkerThreadPool.add_task(_build_job.bind(job), false, "maillage " + key)
		_jobs[key] = job


## Exécuté dans un fil de WorkerThreadPool : calcule seulement les tableaux de sommets.
func _build_job(job: Dictionary) -> void:
	var t0 := Time.get_ticks_usec()
	var spec: Dictionary = job["spec"]
	var r = job["route"]
	match spec["kind"]:
		"road":
			job["arrays"] = RoadBuilder.build_chunk_arrays(r, spec["k"], float(job.get("road_width_m", RoadBuilder.ROAD_WIDTH_M)))
		"near", "far":
			var t: Vector2i = spec["tile"]
			var heights := TerrainTiles.load_filled(job["world_dir"], spec["kind"], t.x, t.y, r)
			if heights.is_empty():
				return
			if spec["kind"] == "far":
				heights = TerrainTiles.carve_under_route(heights, "far", t.x, t.y, r)
			var edges := TerrainTiles.load_neighbour_edges(job["world_dir"], spec["kind"], t.x, t.y)
			job["arrays"] = TerrainTiles.build_arrays(heights, spec["kind"], edges)
			job["origin"] = TerrainTiles.tile_origin(spec["kind"], t.x, t.y)
			if spec["kind"] == "near" and tree_renderer != null:
				job["trees_data"] = tree_renderer.prepare_tile(t.x, t.y, heights, r, _theme_dict,
					vegetation_density_factor, _get_vegetation_areas(t))
		"flat":
			var t: Vector2i = spec["tile"]
			var c := TerrainTiles.tile_origin("near", t.x, t.y) + Vector3(500.0, 0.0, 500.0)
			var alt := TerrainTiles.nearest_route_alt(r, c.x, c.z)
			var flat_h := TerrainTiles.flat_heights(alt)
			job["arrays"] = TerrainTiles.build_arrays(flat_h, "near")
			job["origin"] = TerrainTiles.tile_origin("near", t.x, t.y)
			if tree_renderer != null:
				job["trees_data"] = tree_renderer.prepare_tile(t.x, t.y, flat_h, r, _theme_dict,
					vegetation_density_factor, [])
	var dt := Time.get_ticks_usec() - t0
	_stats_mutex.lock()
	var st: Array = build_stats.get(spec["kind"], [0, 0])
	build_stats[spec["kind"]] = [st[0] + 1, st[1] + dt]
	_stats_mutex.unlock()


func _poll_jobs(wait: bool) -> void:
	for key in _jobs.keys():
		var job: Dictionary = _jobs[key]
		if not wait and not WorkerThreadPool.is_task_completed(job["task"]):
			continue
		WorkerThreadPool.wait_for_task_completion(job["task"])
		_jobs.erase(key)
		if job["gen"] == _generation and _wanted.has(key) and not (job["arrays"] as Array).is_empty():
			var ready_item := {"key": key, "arrays": job["arrays"], "origin": job["origin"], "kind": job["spec"]["kind"]}
			if job.has("trees_data"):
				ready_item["trees_data"] = job["trees_data"]
			_ready.append(ready_item)


func _wait_all_jobs() -> void:
	for key in _jobs.keys():
		WorkerThreadPool.wait_for_task_completion(_jobs[key]["task"])


## Relève les travaux terminés et crée au plus `max_new` objets de scène (fil principal).
func integrate(max_new: int) -> int:
	_poll_jobs(false)
	var created := 0
	while created < max_new and not _ready.is_empty():
		var r: Dictionary = _ready.pop_front()
		if not _wanted.has(r["key"]) or _instances.has(r["key"]):
			continue
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, r["arrays"])
		mesh.surface_set_material(0, _road_material if r["kind"] == "road" else _terrain_material)
		var mi := MeshInstance3D.new()
		mi.name = (r["key"] as String).replace(":", "_")
		mi.mesh = mesh
		mi.position = r["origin"]
		add_child(mi)
		_instances[r["key"]] = mi
		if r.has("trees_data") and tree_renderer != null and not (r["trees_data"] as Dictionary).is_empty():
			tree_renderer.add_tile(r["trees_data"])
		created += 1
	_start_jobs()
	return created


## Attend et instancie tout ce que demande la fenêtre courante (tests, chargement initial).
func flush() -> void:
	while true:
		_poll_jobs(true)
		integrate(1 << 30)
		if _jobs.is_empty() and _ready.is_empty():
			break


## Attend les travaux en cours sans dépasser le budget d'objets par image (tests en temps simulé).
func wait_jobs() -> void:
	_poll_jobs(true)


func _free_instance(key: String) -> void:
	var mi: MeshInstance3D = _instances[key]
	_instances.erase(key)
	remove_child(mi)
	mi.mesh = null   # maillage libéré avant le nœud (évite une erreur du rendu factice sans écran)
	mi.free()
	if key.begins_with("near:") and tree_renderer != null:
		var parts := key.split(":")
		tree_renderer.remove_tile(Vector2i(int(parts[1]), int(parts[2])))


## Configure les matériaux de route et de terrain selon le thème (Lot E2).
func set_theme(theme_dict: Dictionary, theme_dir: String = "") -> void:
	_theme_dict = theme_dict
	var r_params := ThemeRenderParams.road_params(theme_dict)
	_road_width_m = float(r_params["width_m"])
	var road_tex: Texture2D = ThemeLoader.texture_for(theme_dict, theme_dir, "road.texture") if theme_dir != "" else null
	_road_material = RoadBuilder.make_material(r_params["color"], road_tex)

	if _terrain_material is ShaderMaterial:
		TerrainMaterial.apply_to_material(_terrain_material, theme_dict, theme_dir)

	var tu := ThemeRenderParams.terrain_uniforms(theme_dict)
	_ground_color = tu["grass_color"]
	if _ground != null and _ground.mesh != null and _ground.mesh.material is StandardMaterial3D:
		(_ground.mesh.material as StandardMaterial3D).albedo_color = _ground_color


func _make_ground() -> void:
	if _ground != null:
		return
	var min_alt := INF
	if route:
		for a in route.alt_m:
			min_alt = minf(min_alt, a)
	if is_inf(min_alt):
		min_alt = 0.0
	var plane := PlaneMesh.new()
	plane.size = Vector2(2.0 * FAR_RADIUS_M, 2.0 * FAR_RADIUS_M)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = _ground_color
	mat.roughness = 1.0
	plane.material = mat
	_ground = MeshInstance3D.new()
	_ground.name = "FlatGround"
	_ground.mesh = plane
	_ground.position = Vector3(0.0, min_alt - FLAT_GROUND_BELOW_M, 0.0)
	add_child(_ground)


# --- état, pour les tests et le journal ------------------------------------------------------

func loaded_keys() -> Array:
	var keys := _instances.keys()
	keys.sort()
	return keys


func wanted_keys() -> Array:
	var keys := _wanted.keys()
	keys.sort()
	return keys


func instance(key: String) -> MeshInstance3D:
	return _instances.get(key)


func has_ground() -> bool:
	return _ground != null


func ground_height() -> float:
	return _ground.position.y if _ground != null else NAN
