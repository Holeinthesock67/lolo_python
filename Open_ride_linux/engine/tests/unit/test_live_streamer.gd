extends SceneTree

## Rendu par tronçons d'un monde vivant (lot W10) : route prolongée sans reconstruire les tronçons
## inchangés, amorces des branches, couche bâtiments lue par carré. Sans écran (maillages sans rendu).
## Lancement : godot --headless --path engine --script res://tests/unit/test_live_streamer.gd

const LiveWorld := preload("res://scripts/live_world.gd")
const WorldStreamer := preload("res://scripts/world_streamer.gd")

var _checked := 0
var _failures := 0


func _check(ok: bool, what: String) -> void:
	_checked += 1
	if not ok:
		_failures += 1
		printerr("[ÉCHEC] ", what)
	else:
		print("[OK] ", what)


func _write_json(path: String, obj: Variant) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(obj))
	f.close()


func _remove_tree(path: String) -> void:
	var d := DirAccess.open(path)
	if d == null:
		return
	for sub in d.get_directories():
		_remove_tree(path.path_join(sub))
	for f in d.get_files():
		d.remove(f)
	DirAccess.remove_absolute(path)


func _part(k: int, length: float) -> Dictionary:
	var lo := 1000.0 * k
	var hi := minf(1000.0 * (k + 1), length)
	var part := {"version": "1.0", "ds_m": 10.0, "length_m": hi - lo, "type": "open", "s0_m": lo,
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var s := lo
	while s <= hi + 1e-6:
		part["lat"].append(45.0)
		part["lon"].append(6.0 + s * 1.27e-5)
		part["alt_m"].append(600.0)
		part["x"].append(s)
		part["z"].append(0.0)
		part["grade_pct"].append(0.0)
		part["heading_deg"].append(90.0)
		s += 10.0
	part["n"] = part["x"].size()
	return part


func _junction(s_m: float) -> Dictionary:
	var branches := []
	for i in range(2):
		branches.append({"index": i, "heading_deg": 90.0, "angle_deg": 0.0, "road_class": "t", "grade_pct_500m": 0.0,
			"dead_end": false, "preview": {"x": [s_m, s_m + 250.0, s_m + 500.0], "y": [600.0, 600.0, 600.0],
			"z": [0.0, 30.0 * (i + 1), 60.0 * (i + 1)]}})
	return {"id": "j1", "s_m": s_m, "x": s_m, "z": 0.0, "lock_s_m": s_m - 30.0, "default": 0, "chosen": 0,
		"locked": false, "branches": branches}


func _publish(dir: String, length: float, rev: int, changed_from: int, first_part: int) -> void:
	for k in range(first_part, int(ceil(length / 1000.0))):
		_write_json(dir.path_join("route").path_join("part_%d.json" % k), _part(k, length))
	_write_json(dir.path_join("junctions.json"), {"version": "1.0", "revision": rev, "junctions": [_junction(800.0)]})
	_write_json(dir.path_join("live.json"), {"version": "1.0", "revision": rev,
		"route": {"parts": int(ceil(length / 1000.0)), "length_m": length, "changed_from_part": changed_from},
		"tiles": {"near": [], "far": []}, "layer_tiles": [], "status": "ok"})


func _init() -> void:
	var base := "user://w10_stream_%d" % OS.get_process_id()
	var dir := base.path_join("ow-test.world")
	_write_json(dir.path_join("manifest.json"), {"format": "openride-world", "format_version": "1.4", "live": true,
		"layers": {"buildings": {"present": true}}})
	var building := {"id": "w1", "outer": [[10.0, 40.0], [30.0, 40.0], [30.0, 60.0], [10.0, 60.0]], "holes": [],
		"base_y": 600.0, "height_m": 6.0, "roof": "flat", "hint": {"building": "house", "colour": null}}
	_write_json(dir.path_join("buildings").path_join("tile_0_0.json"), {"version": "1.0", "buildings": [building]})
	_publish(dir, 2500.0, 1, 0, 0)

	var lw = LiveWorld.new()
	_check(lw.open(dir), "monde vivant ouvert")
	var st = WorldStreamer.new()
	root.add_child(st)
	st.set_world(lw.route, dir)
	st.update_window(500.0, 0.0, Vector3(500.0, 1.4, 0.0))
	st.flush()
	var roads_before: Dictionary = {}
	for key in st._instances:
		if (key as String).begins_with("road:"):
			roads_before[key] = st._instances[key]
	_check(roads_before.has("road:0") and roads_before.has("road:1") and roads_before.has("road:2"), "tronçons 0 à 2 construits : %s" % str(roads_before.keys()))
	_check(st.osm_streamer == null, "(sans OSM streamer : seuls les tronçons de route sont vérifiés ici)")

	# Amorces : carrefour à 800 m, branche 0 suivie, branche 1 dessinée.
	st.set_previews(lw.previews(500.0))
	_check(st.preview_count() == 1, "une amorce (branche non suivie)")
	st.set_previews(lw.previews(900.0))
	_check(st.preview_count() == 0, "carrefour dépassé : amorce libérée")
	st.set_previews(lw.previews(500.0))

	# Révision : route prolongée à 4 500 m, partie 2 réécrite.
	_publish(dir, 4500.0, 2, 2, 2)
	lw.on_open_world({"rev": 2})
	var upd := lw.wait_poll()
	_check(upd.has("route"), "révision 2 lue")
	st.swap_route(upd["route"], int(upd["from_part"]))
	_check(st._instances.has("road:0") and st._instances.has("road:1"), "tronçons 0 et 1 gardés")
	_check(is_same(st._instances["road:0"], roads_before["road:0"]) and is_same(st._instances["road:1"], roads_before["road:1"]),
		"tronçons 0 et 1 : mêmes nœuds")
	_check(not st._instances.has("road:2"), "tronçon 2 libéré pour être reconstruit")
	st.update_window(2200.0, 0.0, Vector3(2200.0, 1.4, 0.0))
	st.flush()
	_check(st._instances.has("road:2") and st._instances.has("road:3") and st._instances.has("road:4"),
		"tronçons 2 à 4 construits sur la route prolongée")
	_check(not is_same(st._instances["road:2"], roads_before["road:2"]), "tronçon 2 refait")
	_check(st.preview_count() == 1, "amorces conservées par la révision")

	st.clear()
	_check(st.preview_count() == 0, "clear() libère les amorces")
	st.queue_free()
	lw.close()
	_remove_tree(base)
	print("test_live_streamer : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
