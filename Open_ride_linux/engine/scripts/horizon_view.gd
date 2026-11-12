extends Node3D

## Relief d'horizon (lot JP4, version 6.0) : tuiles `terrain/horizon/` du Format .world 1.8 (§5), maille de 500 m
## jusqu'à 40 km de la route, pour voir les grands sommets au-delà du brouillard (le mont Fuji depuis Hakone).
## - Toutes les tuiles sont construites une fois par parcours dans une tâche de fond (bg_tasks.gd, TerrainTiles.build_arrays),
##   puis posées d'un coup sur le fil principal ; aucune ombre portée.
## - Relief exagéré (lot Q2, `relief_k`, 2,5 par défaut) : plein jusqu'à RELIEF_FULL_M de la route, comme le terrain
##   lointain qu'il prolonge, puis ramené au relief réel à RELIEF_REAL_M : le Fuji garde sa vraie silhouette au lieu
##   de monter à 8 000 m.
## - Le shader (horizon.gdshader) ne dessine qu'au-delà de `inner_radius_m` (le terrain lointain couvre au moins
##   5 km autour de la route) et pose sa propre brume, réglée chaque image sur la couleur du brouillard.
## - La caméra voit jusqu'à EXTENT_M tant que des tuiles d'horizon sont affichées.
## Sans tuiles d'horizon (parcours d'avant la 1.8, `--no-horizon`, monde ouvert) : rien n'est créé.
## Pas de class_name (charger par preload).

const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const BgTasks := preload("res://scripts/bg_tasks.gd")
const HORIZON_SHADER := preload("res://shaders/horizon.gdshader")

const EXTENT_M := 45000.0           # vue de la caméra : 40 km de tuiles et marge
const INNER_RADIUS_M := 4500.0      # en deçà, le terrain lointain (± 5 km de la route) suffit
const RELIEF_FULL_M := 5000.0
const RELIEF_REAL_M := 15000.0
const ROUTE_PROBES := 64            # points de route gardés pour la distance à la route

var enabled := true
var material := ShaderMaterial.new()
var env: Environment = null
var sun: DirectionalLight3D = null

var _instances: Array[MeshInstance3D] = []
var _task := -1
var _job: Dictionary = {}
var _generation := 0


func _init() -> void:
	material.shader = HORIZON_SHADER
	material.set_shader_parameter("inner_radius_m", INNER_RADIUS_M)


func setup(environment: Environment, light: DirectionalLight3D) -> void:
	env = environment
	sun = light


## Couleurs unies du sol (bas, roche, neige) et limite de la neige (altitude réelle : l'horizon est au relief réel).
func set_colors(low: Color, rock: Color, snow: Color, snow_line_m: float) -> void:
	material.set_shader_parameter("low_color", low)
	material.set_shader_parameter("rock_color", rock)
	material.set_shader_parameter("snow_color", snow)
	material.set_shader_parameter("snow_line_m", snow_line_m)


## Nouveau parcours : tuiles d'horizon lues et maillées en fond.
func set_world(route, world_dir: String) -> void:
	clear()
	if not enabled or world_dir == "":
		return
	var index := TerrainTiles.scan_index(world_dir, "horizon")
	if index.is_empty():
		return
	_job = {"gen": _generation, "tiles": index.keys(), "out": []}
	_task = BgTasks.add(_build.bind(_job, route, world_dir), false, "horizon")


## Exécuté dans une tâche de fond (bg_tasks.gd).
static func _build(job: Dictionary, route, world_dir: String) -> void:
	var k: float = route.relief_k if route != null else 1.0
	var alt_orig: float = route.alt_m[0] if route != null and route.n > 0 else 0.0
	var probes := route_probes(route)
	for t in job["tiles"]:
		var heights := TerrainTiles.load_filled(world_dir, "horizon", t.x, t.y, route)
		if heights.is_empty():
			continue
		var o := TerrainTiles.tile_origin("horizon", t.x, t.y)
		var cell: float = TerrainTiles.LEVELS["horizon"]["cell"]
		var n := TerrainTiles.SAMPLES
		var disp := PackedFloat32Array()
		disp.resize(n * n)
		for j in range(n):
			for i in range(n):
				var p := Vector2(o.x + i * cell, o.z + j * cell)
				disp[j * n + i] = display_height(heights[j * n + i], p, probes, k, alt_orig)
		var edges := TerrainTiles.load_neighbour_edges(world_dir, "horizon", t.x, t.y)
		var shown := {}
		for side in edges:
			var e: PackedFloat32Array = edges[side]
			var out_e := PackedFloat32Array()
			out_e.resize(e.size())
			for m in range(e.size()):
				var q := Vector2(o.x, o.z)
				match side:
					"west": q += Vector2(-cell, m * cell)
					"east": q += Vector2(n * cell, m * cell)
					"north": q += Vector2(m * cell, -cell)
					_: q += Vector2(m * cell, n * cell)
				out_e[m] = display_height(e[m], q, probes, k, alt_orig)
			shown[side] = out_e
		(job["out"] as Array).append({"tile": t, "arrays": TerrainTiles.build_arrays(disp, "horizon", shown, 1.0, 0.0)})


## Points de la route (x, z) gardés pour la distance à la route : ROUTE_PROBES au plus, régulièrement espacés.
static func route_probes(route) -> PackedVector2Array:
	var out := PackedVector2Array()
	if route == null or route.n == 0:
		out.append(Vector2.ZERO)
		return out
	var step := maxi(1, int(ceil(float(route.n) / ROUTE_PROBES)))
	for i in range(0, route.n, step):
		out.append(Vector2(route.x[i], route.z[i]))
	return out


## Hauteur affichée d'un sommet d'horizon : relief exagéré `k` près de la route, réel au-delà de RELIEF_REAL_M.
static func display_height(alt: float, p: Vector2, probes: PackedVector2Array, k: float, alt_orig: float) -> float:
	if k == 1.0:
		return alt
	var d2 := INF
	for q in probes:
		d2 = minf(d2, p.distance_squared_to(q))
	var w := 1.0 - smoothstep(RELIEF_FULL_M, RELIEF_REAL_M, sqrt(d2))
	return alt_orig + (alt - alt_orig) * (1.0 + (k - 1.0) * w)


func clear() -> void:
	_generation += 1
	if _task >= 0:
		BgTasks.wait(_task)
		_task = -1
	_job = {}
	for mi in _instances:
		remove_child(mi)
		mi.free()
	_instances.clear()


func tile_count() -> int:
	return _instances.size()


## Attend la fin de la tâche de fond et pose les tuiles (essais).
func flush() -> void:
	if _task >= 0:
		BgTasks.wait(_task)
		_task = -1
		_integrate()


func _integrate() -> void:
	if _job.is_empty() or int(_job["gen"]) != _generation:
		return
	for item in _job["out"]:
		var mesh := ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, item["arrays"])
		mesh.surface_set_material(0, material)
		var mi := MeshInstance3D.new()
		var t: Vector2i = item["tile"]
		mi.name = "horizon_%d_%d" % [t.x, t.y]
		mi.mesh = mesh
		mi.position = TerrainTiles.tile_origin("horizon", t.x, t.y)
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mi)
		_instances.append(mi)
	_job = {}


func _process(_delta: float) -> void:
	if _task >= 0 and BgTasks.done(_task):
		flush()
	if _instances.is_empty():
		return
	var cam := get_viewport().get_camera_3d()
	if cam != null and cam.far < EXTENT_M:
		cam.far = EXTENT_M
	if env != null:
		material.set_shader_parameter("haze_color", env.fog_light_color)
		material.set_shader_parameter("fog_begin_m", env.fog_depth_begin)
		material.set_shader_parameter("fog_end_m", env.fog_depth_end)
	if sun != null:
		material.set_shader_parameter("sun_dir", sun.global_transform.basis.z)


func _exit_tree() -> void:
	if _task >= 0:
		BgTasks.wait(_task)
		_task = -1
