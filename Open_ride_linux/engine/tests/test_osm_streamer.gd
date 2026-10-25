extends SceneTree

## Tests sans écran du streaming des couches OSM (Lot E4 §4.1).
## Lancement : godot --headless --path engine --script res://tests/test_osm_streamer.gd

const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const OsmLayers := preload("res://scripts/osm_layers.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const BuildingMesh := preload("res://scripts/building_mesh.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _make_synthetic_osm_world(dir: String) -> Variant:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir))
	for l in ["buildings", "vegetation", "water", "poi"]:
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(dir.path_join(l)))

	var manifest := {
		"version": "1.0",
		"layers": {
			"terrain": {"present": false},
			"buildings": {"present": true, "building_count": 300},
			"vegetation": {"present": true, "area_count": 5},
			"water": {"present": true, "line_count": 2, "area_count": 1},
			"poi": {"present": true, "point_count": 4},
		}
	}
	var f_man := FileAccess.open(dir.path_join("manifest.json"), FileAccess.WRITE)
	f_man.store_string(JSON.stringify(manifest))
	f_man.close()

	# Route synthétique de 3 000 m (3 tronçons de 1 km)
	var ds := 10.0
	var n := 301
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": 3000.0, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(500.0)
		d["x"].append(0.0)
		d["z"].append(i * ds)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(0.0)

	var f_route := FileAccess.open(dir.path_join("route.json"), FileAccess.WRITE)
	f_route.store_string(JSON.stringify(d))
	f_route.close()

	# Données pour chaque tronçon k in [0, 1, 2]
	for k in range(3):
		# Bâtiments (plusieurs par tronçon)
		var b_list := []
		for b_idx in range(10):
			var z_off := float(k * 1000 + b_idx * 80)
			b_list.append({
				"id": "b_%d_%d" % [k, b_idx],
				"outer": [[15.0, z_off], [25.0, z_off], [25.0, z_off + 10.0], [15.0, z_off + 10.0]],
				"holes": [],
				"base_y": 500.0,
				"height_m": 6.0,
				"roof": "flat",
				"hint": {"building": "yes"}
			})
		var f_b := FileAccess.open(dir.path_join("buildings/chunk_%d.json" % k), FileAccess.WRITE)
		f_b.store_string(JSON.stringify({"version": "1.0", "buildings": b_list}))
		f_b.close()

		# Eau (1 rivière et 1 lac)
		var w_doc := {
			"version": "1.0",
			"lines": [{
				"id": "river_%d" % k,
				"kind": "river",
				"width_m": 3.0,
				"points": [[-20.0, float(k * 1000), 499.5], [-20.0, float((k + 1) * 1000), 499.5]]
			}],
			"areas": [{
				"id": "lake_%d" % k,
				"kind": "lake",
				"level_y": 498.0,
				"outer": [[-80.0, float(k * 1000 + 200)], [-40.0, float(k * 1000 + 200)],
						  [-40.0, float(k * 1000 + 400)], [-80.0, float(k * 1000 + 400)]],
				"holes": []
			}]
		}
		var f_w := FileAccess.open(dir.path_join("water/chunk_%d.json" % k), FileAccess.WRITE)
		f_w.store_string(JSON.stringify(w_doc))
		f_w.close()

		# POI
		var poi_doc := {
			"version": "1.0",
			"points": [{
				"id": "poi_%d" % k,
				"kind": "church_bell",
				"x": 30.0,
				"y": 500.0,
				"z": float(k * 1000 + 500),
				"radius_m": 80.0,
				"name": "Cloche"
			}]
		}
		var f_p := FileAccess.open(dir.path_join("poi/chunk_%d.json" % k), FileAccess.WRITE)
		f_p.store_string(JSON.stringify(poi_doc))
		f_p.close()

	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _test_window_and_node_count(world_dir: String, route: Variant) -> void:
	var streamer = OsmStreamer.new()
	root.add_child(streamer)
	streamer.set_world(route, world_dir)

	# Fenêtre à s = 0 (lo = -1000, hi = 3000)
	streamer.update_window(-1000.0, 3000.0)
	streamer.flush()

	var expected_chunks := OsmLayers.chunks_for_window(-1000.0, 3000.0, route)
	_check(streamer.loaded_chunk_count() == expected_chunks.size(),
		"s = 0 : tronçons chargés = %d (attendu %d)" % [streamer.loaded_chunk_count(), expected_chunks.size()])

	# Au plus 3 nœuds par tronçon (bâtiments, cours d'eau, plans d'eau)
	var max_nodes_per_chunk := 0
	for k in streamer._chunk_instances.keys():
		var count: int = (streamer._chunk_instances[k] as Array).size()
		max_nodes_per_chunk = maxi(max_nodes_per_chunk, count)
	_check(max_nodes_per_chunk <= 3 and max_nodes_per_chunk > 0,
		"au plus 3 nœuds par tronçon (max relevé: %d)" % max_nodes_per_chunk)

	# Fenêtre avancée à s = 2500 m (lo = 1500, hi = 5500)
	streamer.update_window(1500.0, 5500.0)
	streamer.flush()
	var expected_late := OsmLayers.chunks_for_window(1500.0, 5500.0, route)
	_check(streamer.loaded_chunk_count() == expected_late.size(),
		"s = 2500 : tronçons chargés = %d (attendu %d)" % [streamer.loaded_chunk_count(), expected_late.size()])

	streamer.clear()
	streamer.free()


func _test_tolerance(world_dir: String, route: Variant) -> void:
	# Fichier corrompu ou version 2
	var bad_dir := "user://bad_osm_world"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(bad_dir.path_join("buildings")))
	var f_v2 := FileAccess.open(bad_dir.path_join("buildings/chunk_0.json"), FileAccess.WRITE)
	f_v2.store_string(JSON.stringify({"version": "2.0", "buildings": []}))
	f_v2.close()

	var streamer = OsmStreamer.new()
	root.add_child(streamer)
	# Doit s'exécuter sans aucune erreur Godot
	streamer.set_world(route, bad_dir, {"layers": {"buildings": {"present": true}}})
	streamer.update_window(0.0, 1000.0)
	streamer.flush()
	_check(true, "version majeure 2 gérée sans plantage ni exception")

	streamer.clear()
	streamer.free()


func _test_skirt_presence(world_dir: String, route: Variant) -> void:
	var streamer = OsmStreamer.new()
	root.add_child(streamer)
	streamer.set_world(route, world_dir)
	streamer.update_window(0.0, 1000.0)
	streamer.flush()

	var nodes: Array = streamer._chunk_instances.get(0, [])
	var b_node: MeshInstance3D = null
	for n in nodes:
		if "buildings" in n.name:
			b_node = n
			break
	_check(b_node != null and b_node.mesh != null, "nœud des bâtiments trouvé")
	if b_node != null and b_node.mesh != null:
		var verts: PackedVector3Array = b_node.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
		var min_y := INF
		for v in verts:
			min_y = minf(min_y, v.y)
		# base_y = 500, jupe de 3 m -> min_y = 497 m
		_check(absf(min_y - 497.0) < 0.05, "jupe de 3 m sous base_y dans la scène : min_y = %.2f (attendu 497.0)" % min_y)

	streamer.clear()
	streamer.free()


## Dans la scène, seul WorldStreamer reçoit _process : il doit faire entrer les tronçons OSM
## préparés (bâtiments et eau), sans flush() (défaut trouvé au banc simulé le 25 octobre).
func _test_pumped_by_world_streamer(world_dir: String, route: Variant) -> void:
	var ws = WorldStreamer.new()
	var osm = OsmStreamer.new()
	ws.osm_streamer = osm
	ws.add_child(osm)
	root.add_child(ws)
	osm.set_world(route, world_dir)
	osm.update_window(-1000.0, 3000.0)
	var expected := OsmLayers.chunks_for_window(-1000.0, 3000.0, route).size()
	var frames := 0
	while osm.loaded_chunk_count() < expected and frames < 500:
		OS.delay_msec(5)
		ws._process(1.0 / 60.0)
		frames += 1
	_check(osm.loaded_chunk_count() == expected,
		"tronçons OSM entrés dans la scène par WorldStreamer._process : %d/%d en %d images"
		% [osm.loaded_chunk_count(), expected, frames])
	osm.clear()
	ws.free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var tmp_world := "user://test_osm_streamer_world"
	var route = _make_synthetic_osm_world(tmp_world)

	_test_window_and_node_count(tmp_world, route)
	_test_tolerance(tmp_world, route)
	_test_skirt_presence(tmp_world, route)
	_test_pumped_by_world_streamer(tmp_world, route)

	print("test_osm_streamer : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
