extends Node3D

## Gestionnaire et affichage par tronçons des couches OpenStreetMap (Lot E4 §4.1).
##
## Gère le chargement en tâche de fond et l'affichage par tronçon des couches :
## - Bâtiments extrudés avec jupe de 3 m (building_mesh.gd).
## - Eau : cours d'eau en ruban et plans d'eau avec îles (water_mesh.gd).
## - Points d'intérêt (poi) pour le modèle sonore.
## Au plus six nœuds de maillage par tronçon (bâtiments, cours d'eau, plans d'eau ; lot U9 : mer, écume, plages).
## Lot U9 : les aires `sea` de la couche eau sont dessinées en mer animée (sea_mesh.gd, shaders/sea.gdshader)
## au lieu d'un plan d'eau ; couche `coast` : écume le long du rivage et plages drapées sur le terrain ; dès
## le premier tronçon avec de la mer, un anneau d'horizon (`sea_horizon`) prolonge la mer jusqu'au-delà du
## brouillard et suit la caméra ; `shore_distance(x, z)` donne la distance au rivage des tronçons chargés
## (son des vagues, lot U11). Parcours sans mer : aucun de ces nœuds.
## Lot P16 : chaque tronçon garde aussi ses contours en x, z (forêts, bâtiments, eaux, avec leur
## rectangle englobant) pour le voisinage sonore (ambience_model.gd) et les exclusions des touffes
## d'herbe ; `layer_shapes()` les rassemble pour les tronçons chargés (`shapes_version` change à chaque
## ajout ou retrait).
## Lot P17 : la tâche de fond d'un tronçon place aussi ses animaux (fauna_placer.gd, avec la hauteur
## des tuiles proches du terrain) quand `fauna_enabled` ; le tronçon intégré émet `chunk_loaded(k,
## extras)` (`extras.fauna` : groupes d'animaux ; lot P25, quand `traffic_enabled` : `extras.traffic`, chemins
## de road_traffic_model.gd des routes voisines et des tracteurs des champs ; lot P29, quand `boats_enabled` :
## `extras.boats`, chemins des bateaux de boat_model.gd), le tronçon retiré `chunk_freed(k)`. Eau qui scintille
## (water_mesh.gd, P12) avec `set_water_shimmer(true)`, avant le chargement des tronçons.
## `biome_model` (biome_model.gd, série U, lot U17) : transmis au placement des animaux (faune par biome, U12)
## et, actif, donne à chaque bâtiment le style d'architecture de son biome ou de sa variante (lot U23).
## Pas de class_name (charger par preload).

const OsmLayers := preload("res://scripts/osm_layers.gd")
const BuildingMesh := preload("res://scripts/building_mesh.gd")
const WaterMesh := preload("res://scripts/water_mesh.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const FaunaPlacer := preload("res://scripts/fauna_placer.gd")
const RoadTrafficModel := preload("res://scripts/road_traffic_model.gd")
const BoatModel := preload("res://scripts/boat_model.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const PerfProbe := preload("res://scripts/perf_probe.gd")
const BgTasks := preload("res://scripts/bg_tasks.gd")
const SeaMesh := preload("res://scripts/sea_mesh.gd")
const SeaShader := preload("res://shaders/sea.gdshader")
const SeaFoamShader := preload("res://shaders/sea_foam.gdshader")
const BeachShader := preload("res://shaders/beach.gdshader")

signal chunk_loaded(k: int, extras: Dictionary)
signal chunk_freed(k: int)

const SKIRT_M := 3.0
const CHUNK_M := 1000.0
## Demi-largeur dégagée autour de l'axe de la route pour les cours d'eau (chaussée de 6 m, bas-côtés).
const ROAD_CLEAR_M := 4.0
const WATER_COLOR := Color(0.12, 0.32, 0.38, 1.0)

var route = null
var world_dir := ""
var layers_present: Array = []
var preset_name := "low"

var _building_material: ShaderMaterial
var _water_material: Material
var _sea_material: ShaderMaterial      # lot U9 : mer et horizon
var _foam_material: ShaderMaterial
var _beach_material: ShaderMaterial
var _horizon: MeshInstance3D = null
var _shores_by_chunk: Dictionary = {}  # k -> Array[PackedVector2Array] (lignes de côte, lot U9)

## Clé de tronçon "chunk:k" -> Array[MeshInstance3D] (au plus 6 nœuds)
var _chunk_instances: Dictionary = {}
var _wanted_chunks: Dictionary = {} # k -> true
var _jobs: Dictionary = {}          # k -> {task, result, gen}
var _ready_chunks: Array = []       # [ {k, meshes_data: [ {arrays, kind} ] } ]
var _generation := 0
var _theme: Dictionary = {}
var _pois_by_chunk: Dictionary = {}
var _shapes_by_chunk: Dictionary = {}   # k -> {forests, buildings, waters} (Lot P16)
var shapes_version := 0

var sound_player: Node = null
## Lot P17 : animaux placés dans la tâche de fond de chaque tronçon.
var fauna_enabled := false
var traffic_enabled := false           # Lot P25 : chemins des routes voisines et des tracteurs des champs
var boats_enabled := false             # Lot P29 : chemins des bateaux des plans d'eau et des cours d'eau
var biome_model = null
var water_shimmer := false


func _init() -> void:
	_init_materials()


func _init_materials() -> void:
	_building_material = BuildingMesh.make_material()
	BuildingMesh.apply_preset(_building_material, preset_name)
	_water_material = WaterMesh.make_material(water_shimmer)
	_sea_material = ShaderMaterial.new()
	_sea_material.shader = SeaShader
	_foam_material = ShaderMaterial.new()
	_foam_material.shader = SeaFoamShader
	_beach_material = ShaderMaterial.new()
	_beach_material.shader = BeachShader


## Matériau d'un nœud de tronçon selon sa sorte (meshes_data.kind).
func _material_for(kind: String) -> Material:
	match kind:
		"buildings":
			return _building_material
		"sea":
			return _sea_material
		"sea_foam":
			return _foam_material
		"beach":
			return _beach_material
	return _water_material


func set_preset(preset: String) -> void:
	preset_name = preset
	var vis_end := QualityPresets.building_visibility_end_m(preset)
	if _building_material != null:
		BuildingMesh.apply_preset(_building_material, preset)
	for k in _chunk_instances:
		for mi in _chunk_instances[k]:
			if is_instance_valid(mi) and (mi as MeshInstance3D).name.begins_with("osm_buildings"):
				(mi as MeshInstance3D).visibility_range_end = vis_end


## Eau qui scintille (Lot P12, `living(preset).water_shimmer`) : nouveau matériau pour les tronçons à venir
## et ceux déjà affichés.
func set_water_shimmer(on: bool) -> void:
	if on == water_shimmer and _water_material != null:
		return
	water_shimmer = on
	_water_material = WaterMesh.make_material(on)
	for k in _chunk_instances:
		for mi in _chunk_instances[k]:
			if mi is MeshInstance3D and (mi as MeshInstance3D).name.begins_with("osm_water"):
				(mi as MeshInstance3D).material_override = _water_material


func water_material() -> Material:
	return _water_material


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


## Monde vivant (lot W10) : nouvelle route après une révision ; les tronçons d'indice >= from_k sont
## reconstruits, les autres gardés (leurs travaux en cours gardent l'ancienne route, qui ne change plus).
func swap_route(new_route, from_k: int) -> void:
	for k in _jobs.keys():
		if k >= from_k:
			BgTasks.wait(_jobs[k]["task"])
			_jobs.erase(k)
	route = new_route
	_ready_chunks = _ready_chunks.filter(func(item): return item["k"] < from_k)
	for k in _chunk_instances.keys():
		if k >= from_k:
			_free_chunk(k)


func clear() -> void:
	_generation += 1
	_wait_all_jobs()
	_jobs.clear()
	_ready_chunks.clear()
	_wanted_chunks.clear()
	for k in _chunk_instances.keys():
		_free_chunk(k)
	_pois_by_chunk.clear()
	_shapes_by_chunk.clear()
	_shores_by_chunk.clear()
	if _horizon != null:
		remove_child(_horizon)
		_horizon.mesh = null
		_horizon.free()
		_horizon = null
	shapes_version += 1
	_update_sound_pois()


func _wait_all_jobs() -> void:
	for k in _jobs.keys():
		BgTasks.wait(_jobs[k]["task"])


func _free_chunk(k: int) -> void:
	if not _chunk_instances.has(k):
		return
	var nodes: Array = _chunk_instances[k]
	for mi in nodes:
		if mi is Node:
			if mi.get_parent() == self:
				remove_child(mi)
			if mi is MeshInstance3D:
				(mi as MeshInstance3D).mesh = null   # maillage libéré avant le nœud (rendu factice sans écran)
			mi.free()
	_chunk_instances.erase(k)
	_pois_by_chunk.erase(k)
	_shores_by_chunk.erase(k)
	if _shapes_by_chunk.erase(k):
		shapes_version += 1
	chunk_freed.emit(k)


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


## Anneau d'horizon (lot U9) : suit la caméra active à l'horizontale.
func _process(_delta: float) -> void:
	if _horizon == null or not is_inside_tree():
		return
	var cam := get_viewport().get_camera_3d()
	if cam != null:
		var c := cam.global_position
		_horizon.position = Vector3(c.x, 0.0, c.z)


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
				"fauna": fauna_enabled,
				"traffic": traffic_enabled,
				"boats": boats_enabled,
				"biome_model": biome_model,
			}
			job["task"] = BgTasks.add(_build_chunk_job.bind(job), false, "OSM chunk %d" % k)
			_jobs[k] = job


func _build_chunk_job(job: Dictionary) -> void:
	var t0 := Time.get_ticks_usec()
	var k: int = job["k"]
	var w_dir: String = job["world_dir"]
	var layers: Array = job["layers"]
	var th: Dictionary = job["theme"]

	var meshes_data := []
	var pois := []
	var shapes := {"forests": [], "buildings": [], "waters": []}

	# Relief affiché (lot Q2) : les hauteurs des couches suivent `route.display_y`, comme la route et le terrain.
	var r_disp = job.get("route")
	var v_scale: float = r_disp.relief_k if r_disp != null else 1.0

	# Hauteur du terrain affiché (tuiles proches, puis lointaines) : pose des bâtiments, des animaux et des
	# tracteurs
	var height_at := Callable()
	var ground_at := Callable()
	if job.get("route") != null:
		var tiles := {}
		height_at = _displayed(terrain_height_fn(w_dir, job["route"], true, tiles), r_disp, v_scale)
		ground_at = _displayed(terrain_height_fn(w_dir, job["route"], false, tiles), r_disp, v_scale)

	var b_items := []
	var w_items := {"lines": [], "areas": []}
	# Niveau de la mer affiché (format §8 : `level_y` = 0 ; relief exagéré, lot Q2) et mer du tronçon (lot U9)
	var sea_y: float = r_disp.display_y(0.0) if r_disp != null else 0.0
	var sea_info := {}
	var shores := []
	var boats := []
	# 1. Bâtiments
	var t_buildings := Time.get_ticks_usec()
	if layers.has("buildings"):
		var b_res := OsmLayers.load_chunk(w_dir, "buildings", k, job.get("route"))
		if b_res.get("ok", false):
			var items: Array = b_res.get("items", [])
			b_items = items
			for b in items:
				shapes["buildings"].append(_shape(b.get("outer", [])))
			if not items.is_empty():
				# Lot U23 : style d'architecture du biome (ou de la variante) au centre de chaque bâtiment
				var b_model = job.get("biome_model", null)
				var styled: bool = b_model != null and b_model.active()
				var grounded := ground_at.is_valid()
				if v_scale != 1.0 or styled or grounded:
					var dressed_items: Array = []
					for b in items:
						var bc: Dictionary = b.duplicate()
						if v_scale != 1.0 and bc.has("base_y"):
							bc["base_y"] = r_disp.display_y(float(bc["base_y"]))
						if grounded:
							# Terrain le plus haut le long des façades : rez-de-chaussée relevé sur une pente
							bc["ground_max_y"] = ground_max_along(bc.get("outer", []), ground_at)
						if styled and not bc.has("style"):
							var c: Vector2 = (_shape(bc.get("outer", []))["rect"] as Rect2).get_center()
							bc["style"] = b_model.building_style_at(c.x, c.y)
						dressed_items.append(bc)
					items = dressed_items
				var m := BuildingMesh.build(items, th, SKIRT_M)
				if int(m.get("built", 0)) > 0:
					var arr := _arrays_from_mesh_dict(m)
					if not arr.is_empty():
						meshes_data.append({"kind": "buildings", "arrays": arr})

	PerfProbe.task("batiments", str(k), (Time.get_ticks_usec() - t_buildings) / 1000.0)
	# 2. Eau (lines et areas)
	var t_water := Time.get_ticks_usec()
	var boats_us := 0
	if layers.has("water"):
		var w_res := OsmLayers.load_chunk(w_dir, "water", k, job.get("route"))
		if w_res.get("ok", false):
			var lines: Array = w_res.get("lines", [])
			w_items = {"lines": lines, "areas": w_res.get("areas", [])}
			for l in lines:
				var wl := _shape(l.get("points", []))
				wl["kind"] = str(l.get("kind", "river"))
				wl["area"] = false
				shapes["waters"].append(wl)
			for a in w_res.get("areas", []):
				var wa := _shape(a.get("outer", []))
				wa["kind"] = str(a.get("kind", "lake"))
				wa["area"] = true
				shapes["waters"].append(wa)
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
								new_pts.append([pt[0], pt[1], r_disp.display_y(float(pt[2]))])
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
							ac["level_y"] = r_disp.display_y(float(ac["level_y"]))
						scaled_areas.append(ac)
					areas = scaled_areas
				# Lot U9 : la mer (`sea`) a son maillage et son matériau ; les autres aires restent des plans d'eau.
				var split := SeaMesh.split_areas(areas)
				var a_mesh := WaterMesh.build_areas(split["inland"])
				if int(a_mesh.get("built", 0)) > 0:
					var arr := _arrays_from_mesh_dict(a_mesh)
					if not arr.is_empty():
						meshes_data.append({"kind": "water_areas", "arrays": arr})
				if not (split["sea"] as Array).is_empty():
					var b_model = job.get("biome_model", null)
					var color_at := func(x: float, z: float) -> Color:
						return SeaMesh.sea_color(th, b_model, x, z)
					var s_mesh := SeaMesh.build_sea(split["sea"], color_at)
					if int(s_mesh.get("built", 0)) > 0:
						var arr := _arrays_from_mesh_dict(s_mesh)
						if not arr.is_empty():
							meshes_data.append({"kind": "sea", "arrays": arr})
							sea_info = {"color": s_mesh["color"], "y": sea_y}
			# Bateaux (Lot P29) : sur l'eau affichée (cours d'eau coupés à la route, relief exagéré appliqué)
			if bool(job.get("boats", false)):
				var t_boats := Time.get_ticks_usec()
				var road := road_polyline(job["route"], k) if job.get("route") != null else PackedVector2Array()
				boats = BoatModel.water_paths(areas, lines, road)
				boats_us = Time.get_ticks_usec() - t_boats
	# Étapes de la tâche `osm` (lot U3, r790b : tâches de 20 s sur le parcours côtier, cause à localiser)
	PerfProbe.task("osm_eau", str(k), (Time.get_ticks_usec() - t_water - boats_us) / 1000.0)
	PerfProbe.task("osm_bateaux", str(k), boats_us / 1000.0)

	# Côte (lot U9) : écume côté mer des lignes de côte, plages drapées sur le terrain proche
	var t_coast := Time.get_ticks_usec()
	if layers.has("coast"):
		var c_res := OsmLayers.load_chunk(w_dir, "coast", k, job.get("route"))
		if c_res.get("ok", false):
			var c_lines: Array = c_res.get("lines", [])
			shores = SeaMesh.shore_polylines(c_lines)
			var f_mesh := SeaMesh.build_foam(c_lines, sea_y)
			if int(f_mesh.get("built", 0)) > 0:
				var arr := _arrays_from_mesh_dict(f_mesh)
				if not arr.is_empty():
					meshes_data.append({"kind": "sea_foam", "arrays": arr})
			var beaches: Array = c_res.get("beaches", [])
			if not beaches.is_empty() and job.get("route") != null:
				var raw_h := terrain_height_fn(w_dir, job["route"])
				var beach_h := raw_h
				if v_scale != 1.0:
					beach_h = func(x: float, z: float) -> float:
						return r_disp.display_y(float(raw_h.call(x, z)))
				var sand = SeaMesh.sand_color(th)
				var p_mesh := SeaMesh.build_beaches(beaches, beach_h, sand)
				if int(p_mesh.get("built", 0)) > 0:
					var arr := _arrays_from_mesh_dict(p_mesh)
					if not arr.is_empty():
						meshes_data.append({"kind": "beach", "arrays": arr})
	PerfProbe.task("osm_cote", str(k), (Time.get_ticks_usec() - t_coast) / 1000.0)

	# Forêts (voisinage sonore et animaux : les arbres sont dessinés par tree_renderer.gd)
	var t_veg := Time.get_ticks_usec()
	var veg_items := []
	if layers.has("vegetation"):
		var v_res := OsmLayers.load_chunk(w_dir, "vegetation", k, job.get("route"))
		if v_res.get("ok", false):
			veg_items = v_res.get("items", [])
			for a in veg_items:
				if str(a.get("kind", "")) == "wood":
					shapes["forests"].append(_shape(a.get("outer", [])))

	# 3. POI (pour sound_player)
	if layers.has("poi"):
		var poi_res := OsmLayers.load_chunk(w_dir, "poi", k, job.get("route"))
		if poi_res.get("ok", false):
			pois = poi_res.get("items", [])

	PerfProbe.task("osm_veg_poi", str(k), (Time.get_ticks_usec() - t_veg) / 1000.0)
	var t_fauna := Time.get_ticks_usec()
	# 4. Animaux (Lot P17, placement de P11) et tracteurs des champs (P25) : posés sur les tuiles proches
	# du terrain
	var fauna := []
	var traffic := []
	if bool(job.get("fauna", false)) and job.get("route") != null:
		var fz = th.get("fauna", {})
		fauna = FaunaPlacer.place_chunk(k, veg_items, pois, job["route"], fz if typeof(fz) == TYPE_DICTIONARY else {}, {
			"height_at": height_at,
			"buildings": b_items,
			"water": w_items,
			"biome_model": job.get("biome_model", null),
		})

	PerfProbe.task("osm_faune", str(k), (Time.get_ticks_usec() - t_fauna) / 1000.0)
	var t_traffic := Time.get_ticks_usec()
	# 5. Circulation des routes voisines et tracteurs des champs (Lot P25)
	if bool(job.get("traffic", false)) and job.get("route") != null:
		if layers.has("roads"):
			var r_res := OsmLayers.load_chunk(w_dir, "roads", k, job.get("route"))
			if r_res.get("ok", false):
				var lines: Array = r_res.get("items", [])
				if v_scale != 1.0:
					var scaled: Array = []
					for line in lines:
						var lc: Dictionary = line.duplicate()
						var new_pts: Array = []
						for pt in lc.get("points", []):
							new_pts.append([pt[0], pt[1], r_disp.display_y(float(pt[2]))])
						lc["points"] = new_pts
						scaled.append(lc)
					lines = scaled
				traffic.append_array(RoadTrafficModel.road_paths(lines))
		var t_fields := Time.get_ticks_usec()
		traffic.append_array(RoadTrafficModel.field_paths(veg_items, height_at))
		PerfProbe.task("osm_champs", str(k), (Time.get_ticks_usec() - t_fields) / 1000.0)

	PerfProbe.task("osm_circulation", str(k), (Time.get_ticks_usec() - t_traffic) / 1000.0)
	PerfProbe.task("osm", str(k), (Time.get_ticks_usec() - t0) / 1000.0)
	job["result"] = {
		"k": k,
		"meshes_data": meshes_data,
		"pois": pois,
		"shapes": shapes,
		"fauna": fauna,
		"traffic": traffic,
		"boats": boats,
		"sea": sea_info,
		"shores": shores,
	}


## Hauteur lue sur le relief exagéré quand `v_scale` ≠ 1, comme le terrain affiché (lot Q2)
static func _displayed(fn: Callable, r_disp, v_scale: float) -> Callable:
	if v_scale == 1.0:
		return fn
	return func(x: float, z: float) -> float:
		var y := float(fn.call(x, z))
		return y if is_nan(y) else float(r_disp.display_y(y))


## Pas des points lus le long des façades pour `ground_max_along` (m)
const GROUND_SAMPLE_M := 4.0


## Terrain le plus haut le long du contour `outer` ([[x, z], …]) : sommets et points tous les GROUND_SAMPLE_M
## sur chaque côté. null si le contour est vide ou si aucune hauteur n'est finie.
static func ground_max_along(outer: Array, height_at: Callable):
	var best := -INF
	var n := outer.size()
	for i in range(n):
		var a = outer[i]
		var b = outer[(i + 1) % n]
		if typeof(a) != TYPE_ARRAY or typeof(b) != TYPE_ARRAY or a.size() < 2 or b.size() < 2:
			continue
		var pa := Vector2(float(a[0]), float(a[1]))
		var pb := Vector2(float(b[0]), float(b[1]))
		var steps := maxi(1, ceili(pa.distance_to(pb) / GROUND_SAMPLE_M))
		for j in range(steps):
			var p := pa.lerp(pb, float(j) / steps)
			var y := float(height_at.call(p.x, p.y))
			if is_finite(y) and y > best:
				best = y
	return best if is_finite(best) else null


## Hauteur du terrain proche en (x, z), lue dans les tuiles `near` du parcours (cache par tuile) ; hors des
## tuiles proches, tuile lointaine (`far`, abaissée comme à l'affichage), puis altitude de la route la plus
## proche. Les champs loin de la route (tracteurs, lot P25) sont posés sur le lointain : avant, chaque point
## de rang cherchait la route la plus proche (20 s par tronçon côtier, essai r790d). Sans nœud : utilisable
## dans une tâche de fond. `caches` : tuiles lues, partagées entre plusieurs fonctions. `route_fallback` faux : NAN hors des tuiles (pose des bâtiments, sans deviner).
static func terrain_height_fn(w_dir: String, r, route_fallback: bool = true, caches: Dictionary = {}) -> Callable:
	var cache: Dictionary = caches.get_or_add("near", {})
	var far_cache: Dictionary = caches.get_or_add("far", {})
	var far_dy: float = TerrainTiles.LEVELS["far"]["y_offset"]
	return func(x: float, z: float) -> float:
		var t := TerrainTiles.tile_of("near", x, z)
		if not cache.has(t):
			cache[t] = TerrainTiles.load_filled(w_dir, "near", t.x, t.y, r)
		var h: PackedFloat32Array = cache[t]
		if not h.is_empty():
			return TerrainTiles.mesh_height_at(h, "near", t.x, t.y, x, z)
		var ft := TerrainTiles.tile_of("far", x, z)
		if not far_cache.has(ft):
			far_cache[ft] = TerrainTiles.load_tile(w_dir, "far", ft.x, ft.y)
		var fh: PackedFloat32Array = far_cache[ft]
		if not fh.is_empty():
			var y := TerrainTiles.mesh_height_at(fh, "far", ft.x, ft.y, x, z)
			if not is_nan(y):
				return y + far_dy
		if not route_fallback:
			return NAN
		return TerrainTiles.nearest_route_alt(r, x, z)


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
	if d.has("uvs2"):
		arr[Mesh.ARRAY_TEX_UV2] = d["uvs2"]
	if d.has("indices"):
		arr[Mesh.ARRAY_INDEX] = d["indices"]
	return arr


func _poll_jobs(wait: bool) -> void:
	for k in _jobs.keys():
		var job: Dictionary = _jobs[k]
		if not wait and not BgTasks.done(job["task"]):
			continue
		BgTasks.wait(job["task"])
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
		var t0 := Time.get_ticks_usec()

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

			mi.material_override = _material_for(kind)
			if kind == "buildings":
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
				mi.visibility_range_end = vis_end
			else:
				mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

			add_child(mi)
			nodes.append(mi)
			created += 1

		_chunk_instances[k] = nodes
		if not (item.get("shores", []) as Array).is_empty():
			_shores_by_chunk[k] = item["shores"]
		var sea: Dictionary = item.get("sea", {})
		if _horizon == null and not sea.is_empty():
			_make_horizon(float(sea["y"]), sea["color"])
		_shapes_by_chunk[k] = item.get("shapes", {"forests": [], "buildings": [], "waters": []})
		shapes_version += 1
		if not (item["pois"] as Array).is_empty():
			_pois_by_chunk[k] = item["pois"]
			_update_sound_pois()
		chunk_loaded.emit(k, {"fauna": item.get("fauna", []), "traffic": item.get("traffic", []), "boats": item.get("boats", [])})
		PerfProbe.mark("osm", str(k), (Time.get_ticks_usec() - t0) / 1000.0)

	_start_jobs()
	return created


## Anneau d'horizon de la mer (lot U9), créé une fois par parcours, au premier tronçon qui a de la mer.
func _make_horizon(sea_y: float, color: Color) -> void:
	var h := SeaMesh.build_horizon(sea_y - SeaMesh.HORIZON_BELOW_M, color)
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, _arrays_from_mesh_dict(h))
	_horizon = MeshInstance3D.new()
	_horizon.name = "sea_horizon"
	_horizon.mesh = mesh
	_horizon.material_override = _sea_material
	_horizon.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_horizon)
	if route != null and route.n >= 2:
		var p: Vector3 = route.sample_point(0.0)
		_horizon.position = Vector3(p.x, 0.0, p.z)


## Distance (m) de (x, z) au rivage le plus proche des tronçons chargés (lot U9, pour le son des vagues du lot
## U11) ; INF sans côte chargée.
func shore_distance(x: float, z: float) -> float:
	var best := INF
	for k in _shores_by_chunk:
		best = minf(best, SeaMesh.shore_distance(_shores_by_chunk[k], x, z))
	return best


## Anneau d'horizon de la mer, ou null (tests).
func sea_horizon() -> MeshInstance3D:
	return _horizon


## Contour `[[x, z], …]` -> `{points: PackedVector2Array, rect: Rect2}`.
static func _shape(pts: Array) -> Dictionary:
	var out := PackedVector2Array()
	var rect := Rect2()
	for i in range(pts.size()):
		var q := Vector2(float(pts[i][0]), float(pts[i][1]))
		out.append(q)
		rect = Rect2(q, Vector2.ZERO) if i == 0 else rect.expand(q)
	return {"points": out, "rect": rect}


## Contours des tronçons chargés (Lot P16) : `{forests, buildings, waters}`, chacun une liste de
## `{points, rect}` (eaux : plus `kind` et `area`).
func layer_shapes() -> Dictionary:
	var out := {"forests": [], "buildings": [], "waters": []}
	for k in _shapes_by_chunk:
		var sh: Dictionary = _shapes_by_chunk[k]
		for key in out:
			out[key].append_array(sh.get(key, []))
	return out


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
