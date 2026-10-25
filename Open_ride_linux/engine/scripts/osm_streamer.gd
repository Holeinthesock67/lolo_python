extends Node3D

## Gestionnaire et affichage par tronçons des couches OpenStreetMap (Lot E4 §4.1).
##
## Gère le chargement en tâche de fond et l'affichage par tronçon des couches :
## - Bâtiments extrudés avec jupe de 3 m (building_mesh.gd).
## - Eau : cours d'eau en ruban et plans d'eau avec îles (water_mesh.gd).
## - Points d'intérêt (poi) pour le modèle sonore.
## Au plus trois nœuds de maillage par tronçon (bâtiments, cours d'eau, plans d'eau).
## Pas de class_name (charger par preload).

const OsmLayers := preload("res://scripts/osm_layers.gd")
const BuildingMesh := preload("res://scripts/building_mesh.gd")
const WaterMesh := preload("res://scripts/water_mesh.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")

const SKIRT_M := 3.0
const CHUNK_M := 1000.0
## Demi-largeur dégagée autour de l'axe de la route pour les cours d'eau (chaussée de 6 m, bas-côtés).
const ROAD_CLEAR_M := 4.0
const WATER_COLOR := Color(0.12, 0.32, 0.38, 1.0)

var route = null
var world_dir := ""
var layers_present: Array = []
var preset_name := "low"
var visual_grade_scale: float = 1.0

var _building_material: StandardMaterial3D
var _water_material: StandardMaterial3D

## Clé de tronçon "chunk:k" -> Array[MeshInstance3D] (au plus 3 nœuds)
var _chunk_instances: Dictionary = {}
var _wanted_chunks: Dictionary = {} # k -> true
var _jobs: Dictionary = {}          # k -> {task, result, gen}
var _ready_chunks: Array = []       # [ {k, meshes_data: [ {arrays, kind} ] } ]
var _generation := 0
var _theme: Dictionary = {}
var _pois_by_chunk: Dictionary = {}

var sound_player: Node = null


func _init() -> void:
	_init_materials()


func _init_materials() -> void:
	_building_material = StandardMaterial3D.new()
	_building_material.vertex_color_use_as_albedo = true
	_building_material.roughness = 0.85

	_water_material = StandardMaterial3D.new()
	_water_material.albedo_color = WATER_COLOR
	_water_material.roughness = 0.10


func set_preset(preset: String) -> void:
	preset_name = preset
	var vis_end := QualityPresets.building_visibility_end_m(preset)
	if _building_material != null:
		_building_material.distance_fade_max_distance = vis_end


func set_world(new_route, new_world_dir: String, manifest: Dictionary = {}, theme: Dictionary = {}) -> void:
	clear()
	route = new_route
	world_dir = new_world_dir
	_theme = theme
	if manifest.is_empty() and FileAccess.file_exists(world_dir.path_join("manifest.json")):
		var parsed = JSON.parse_string(FileAccess.get_file_as_string(world_dir.path_join("manifest.json")))
		if typeof(parsed) == TYPE_DICTIONARY:
			manifest = parsed
	layers_present = OsmLayers.layers_present(manifest)


func clear() -> void:
	_generation += 1
	_wait_all_jobs()
	_jobs.clear()
	_ready_chunks.clear()
	_wanted_chunks.clear()
	for k in _chunk_instances.keys():
		_free_chunk(k)
	_pois_by_chunk.clear()
	_update_sound_pois()


func _wait_all_jobs() -> void:
	for k in _jobs.keys():
		WorkerThreadPool.wait_for_task_completion(_jobs[k]["task"])


func _free_chunk(k: int) -> void:
	if not _chunk_instances.has(k):
		return
	var nodes: Array = _chunk_instances[k]
	for mi in nodes:
		if mi is Node:
			if mi.get_parent() == self:
				remove_child(mi)
			mi.free()
	_chunk_instances.erase(k)
	_pois_by_chunk.erase(k)


func update_window(s_from: float, s_to: float) -> void:
	if route == null or world_dir.is_empty():
		return

	var wanted_k := OsmLayers.chunks_for_window(s_from, s_to, route)
	var wanted := {}
	for k in wanted_k:
		wanted[k] = true
	_wanted_chunks = wanted

	# Libérer les tronçons sortis
	for k in _chunk_instances.keys():
		if not _wanted_chunks.has(k):
			_free_chunk(k)

	_ready_chunks = _ready_chunks.filter(func(item): return _wanted_chunks.has(item["k"]))
	_start_jobs()
	_update_sound_pois()


func _start_jobs() -> void:
	var queued := {}
	for item in _ready_chunks:
		queued[item["k"]] = true

	for k in _wanted_chunks:
		if not _chunk_instances.has(k) and not _jobs.has(k) and not queued.has(k):
			var job := {
				"k": k,
				"gen": _generation,
				"world_dir": world_dir,
				"layers": layers_present.duplicate(),
				"theme": _theme,
				"route": route,
				"visual_grade_scale": visual_grade_scale,
			}
			job["task"] = WorkerThreadPool.add_task(_build_chunk_job.bind(job), false, "OSM chunk %d" % k)
			_jobs[k] = job


func _build_chunk_job(job: Dictionary) -> void:
	var k: int = job["k"]
	var w_dir: String = job["world_dir"]
	var layers: Array = job["layers"]
	var th: Dictionary = job["theme"]

	var meshes_data := []
	var pois := []

	var v_scale: float = float(job.get("visual_grade_scale", 1.0))
	var alt_orig: float = job["route"].alt_m[0] if job.get("route") != null and job["route"].n > 0 else 0.0

	# 1. Bâtiments
	if layers.has("buildings"):
		var b_res := OsmLayers.load_chunk(w_dir, "buildings", k)
		if b_res.get("ok", false):
			var items: Array = b_res.get("items", [])
			if not items.is_empty():
				if v_scale != 1.0:
					var scaled_items: Array = []
					for b in items:
						var bc: Dictionary = b.duplicate()
						if bc.has("base_y"):
							bc["base_y"] = alt_orig + (float(bc["base_y"]) - alt_orig) * v_scale
						scaled_items.append(bc)
					items = scaled_items
				var m := BuildingMesh.build(items, th, SKIRT_M)
				if int(m.get("built", 0)) > 0:
					var arr := _arrays_from_mesh_dict(m)
					if not arr.is_empty():
						meshes_data.append({"kind": "buildings", "arrays": arr})

	# 2. Eau (lines et areas)
	if layers.has("water"):
		var w_res := OsmLayers.load_chunk(w_dir, "water", k)
		if w_res.get("ok", false):
			var lines: Array = w_res.get("lines", [])
			if job.get("route") != null:
				lines = cut_lines_at_road(lines, road_polyline(job["route"], k))
			if not lines.is_empty():
				if v_scale != 1.0:
					var scaled_lines: Array = []
					for line in lines:
						var lc: Dictionary = line.duplicate()
						var pts: Array = lc.get("points", [])
						var new_pts: Array = []
						for pt in pts:
							if pt.size() >= 3:
								new_pts.append([pt[0], pt[1], alt_orig + (float(pt[2]) - alt_orig) * v_scale])
							else:
								new_pts.append(pt)
						lc["points"] = new_pts
						scaled_lines.append(lc)
					lines = scaled_lines
				var l_mesh := WaterMesh.build_lines(lines)
				if int(l_mesh.get("built", 0)) > 0:
					var arr := _arrays_from_mesh_dict(l_mesh)
					if not arr.is_empty():
						meshes_data.append({"kind": "water_lines", "arrays": arr})

			var areas: Array = w_res.get("areas", [])
			if not areas.is_empty():
				if v_scale != 1.0:
					var scaled_areas: Array = []
					for area in areas:
						var ac: Dictionary = area.duplicate()
						if ac.has("level_y"):
							ac["level_y"] = alt_orig + (float(ac["level_y"]) - alt_orig) * v_scale
						scaled_areas.append(ac)
					areas = scaled_areas
				var a_mesh := WaterMesh.build_areas(areas)
				if int(a_mesh.get("built", 0)) > 0:
					var arr := _arrays_from_mesh_dict(a_mesh)
					if not arr.is_empty():
						meshes_data.append({"kind": "water_areas", "arrays": arr})

	# 3. POI (pour sound_player)
	if layers.has("poi"):
		var poi_res := OsmLayers.load_chunk(w_dir, "poi", k)
		if poi_res.get("ok", false):
			pois = poi_res.get("items", [])

	job["result"] = {
		"k": k,
		"meshes_data": meshes_data,
		"pois": pois,
	}


## Axe de la route (x, z) sur le tronçon k, élargi de 200 m de part et d'autre.
static func road_polyline(r, k: int) -> PackedVector2Array:
	var out := PackedVector2Array()
	if r == null or r.n < 2:
		return out
	var ds: float = maxf(r.ds_m, 0.01)
	var i0 := clampi(floori((k * CHUNK_M - 200.0) / ds), 0, r.n - 1)
	var i1 := clampi(ceili(((k + 1) * CHUNK_M + 200.0) / ds), 0, r.n - 1)
	for i in range(i0, i1 + 1):
		out.append(Vector2(r.x[i], r.z[i]))
	return out


## Cours d'eau coupés là où ils croisent la chaussée : un segment qui coupe l'axe de la route ou
## passe à moins de ROAD_CLEAR_M + largeur / 2 de l'axe est retiré (passage sous un pont), et la
## ligne est scindée. Défaut vu au banc simulé le 25 octobre : le ruban d'eau, posé au niveau du
## terrain (donc de la chaussée près de la route), recouvrait la route.
static func cut_lines_at_road(lines: Array, road: PackedVector2Array) -> Array:
	if road.size() < 2:
		return lines
	var out := []
	for line in lines:
		if typeof(line) != TYPE_DICTIONARY:
			continue
		var pts: Array = line.get("points", [])
		var clear := ROAD_CLEAR_M + float(line.get("width_m", 0.0)) * 0.5
		var part := []
		for i in range(pts.size()):
			if i > 0:
				var a := Vector2(float(pts[i - 1][0]), float(pts[i - 1][1]))
				var b := Vector2(float(pts[i][0]), float(pts[i][1]))
				if _segment_near_road(a, b, road, clear):
					if part.size() >= 2:
						var piece: Dictionary = line.duplicate()
						piece["points"] = part
						out.append(piece)
					part = []
			part.append(pts[i])
		if part.size() >= 2:
			var piece: Dictionary = line.duplicate()
			piece["points"] = part
			out.append(piece)
	return out


static func _segment_near_road(a: Vector2, b: Vector2, road: PackedVector2Array, clear: float) -> bool:
	var lo := Vector2(minf(a.x, b.x), minf(a.y, b.y)) - Vector2(clear, clear)
	var hi := Vector2(maxf(a.x, b.x), maxf(a.y, b.y)) + Vector2(clear, clear)
	for i in range(road.size() - 1):
		var c := road[i]
		var d := road[i + 1]
		if maxf(c.x, d.x) < lo.x or minf(c.x, d.x) > hi.x or maxf(c.y, d.y) < lo.y or minf(c.y, d.y) > hi.y:
			continue
		if Geometry2D.segment_intersects_segment(a, b, c, d) != null:
			return true
		var pts := Geometry2D.get_closest_points_between_segments(a, b, c, d)
		if (pts[0] as Vector2).distance_to(pts[1]) < clear:
			return true
	return false


static func _arrays_from_mesh_dict(d: Dictionary) -> Array:
	var verts: PackedVector3Array = d.get("vertices", PackedVector3Array())
	if verts.is_empty():
		return []
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	if d.has("normals"):
		arr[Mesh.ARRAY_NORMAL] = d["normals"]
	if d.has("colors"):
		arr[Mesh.ARRAY_COLOR] = d["colors"]
	if d.has("uvs"):
		arr[Mesh.ARRAY_TEX_UV] = d["uvs"]
	if d.has("indices"):
		arr[Mesh.ARRAY_INDEX] = d["indices"]
	return arr


func _poll_jobs(wait: bool) -> void:
	for k in _jobs.keys():
		var job: Dictionary = _jobs[k]
		if not wait and not WorkerThreadPool.is_task_completed(job["task"]):
			continue
		WorkerThreadPool.wait_for_task_completion(job["task"])
		_jobs.erase(k)
		if job["gen"] == _generation and _wanted_chunks.has(k):
			_ready_chunks.append(job["result"])


func integrate(max_new: int) -> int:
	_poll_jobs(false)
	var created := 0
	while created < max_new and not _ready_chunks.is_empty():
		var item: Dictionary = _ready_chunks.pop_front()
		var k: int = item["k"]
		if not _wanted_chunks.has(k) or _chunk_instances.has(k):
			continue

		var nodes: Array[MeshInstance3D] = []
		var m_list: Array = item["meshes_data"]
		var vis_end := QualityPresets.building_visibility_end_m(preset_name)

		for m in m_list:
			var kind: String = m["kind"]
			var mesh := ArrayMesh.new()
			mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, m["arrays"])

			var mi := MeshInstance3D.new()
			mi.name = "osm_%s_%d" % [kind, k]
			mi.mesh = mesh

			if kind == "buildings":
				mi.material_override = _building_material
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
				mi.visibility_range_end = vis_end
			else:
				mi.material_override = _water_material
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

			add_child(mi)
			nodes.append(mi)
			created += 1

		_chunk_instances[k] = nodes
		if not (item["pois"] as Array).is_empty():
			_pois_by_chunk[k] = item["pois"]
			_update_sound_pois()

	_start_jobs()
	return created


func _update_sound_pois() -> void:
	if sound_player == null:
		return
	var all_pois := []
	for k in _pois_by_chunk.keys():
		all_pois.append_array(_pois_by_chunk[k])
	sound_player.set_pois(all_pois)


func flush() -> void:
	while true:
		_poll_jobs(true)
		integrate(1 << 30)
		if _jobs.is_empty() and _ready_chunks.is_empty():
			break


func loaded_chunk_count() -> int:
	return _chunk_instances.size()


func loaded_node_count() -> int:
	var total := 0
	for k in _chunk_instances.keys():
		total += (_chunk_instances[k] as Array).size()
	return total
