extends SceneTree

## Monde ouvert, règle sol / route (22/11) : le générateur règle de nouveau le sol d'une tuile proche déjà
## affichée quand la route engagée change près d'elle. À la révision suivante, l'engine refait cette tuile (fichier
## changé), garde l'ancien maillage jusqu'au nouveau, et laisse les tuiles inchangées telles quelles.
## Lancement : godot --headless --path engine --script res://tests/unit/test_live_ground_reload.gd

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


func _write_tile(dir: String, ix: int, iz: int, h: float) -> void:
	var path := dir.path_join("terrain").path_join("near").path_join("tile_%d_%d.f32" % [ix, iz])
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var a := PackedFloat32Array()
	a.resize(101 * 101)
	a.fill(h)
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_buffer(a.to_byte_array())
	f.close()


func _first_y(mi: MeshInstance3D) -> float:
	var v: PackedVector3Array = mi.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	return v[v.size() / 2].y


func _init() -> void:
	var base := "user://sol_reload_%d" % OS.get_process_id()
	var dir := base.path_join("ow-test.world")
	_write_json(dir.path_join("manifest.json"), {"format": "openride-world", "format_version": "1.10", "live": true,
		"layers": {"terrain": {"present": true, "near_cell_m": 10, "far_cell_m": 50}}})
	_write_tile(dir, 0, 0, 598.0)
	_write_tile(dir, 0, -1, 598.0)
	_publish(dir, 2500.0, 1, 0, 0)

	var lw = LiveWorld.new()
	_check(lw.open(dir), "monde vivant ouvert")
	var st = WorldStreamer.new()
	root.add_child(st)
	st.set_world(lw.route, dir)
	st.update_window(500.0, 0.0, Vector3(500.0, 1.4, 0.0))
	st.flush()
	_check(st._instances.has("near:0:0") and st._instances.has("near:0:-1"), "deux tuiles proches affichées : %s" % str(st._instances.keys()))
	var old_a: MeshInstance3D = st._instances["near:0:0"]
	var old_b: MeshInstance3D = st._instances["near:0:-1"]
	var y_a := _first_y(old_a)

	# Révision : la route change près de la tuile (0, 0), que le générateur règle de nouveau (sol plus bas).
	_write_tile(dir, 0, 0, 596.5)
	_publish(dir, 4500.0, 2, 2, 2)
	lw.on_open_world({"rev": 2})
	var upd := lw.wait_poll()
	st.swap_route(upd["route"], int(upd["from_part"]))
	_check(st.stale_near_count() == 1, "une tuile proche à refaire (fichier changé) : %d" % st.stale_near_count())
	_check(is_same(st._instances["near:0:0"], old_a), "ancien maillage gardé tant que le nouveau n'est pas prêt")
	st.update_window(500.0, 0.0, Vector3(500.0, 1.4, 0.0))
	st.flush()
	_check(st._instances.has("near:0:0") and not is_same(st._instances["near:0:0"], old_a), "tuile (0, 0) refaite")
	_check(absf(_first_y(st._instances["near:0:0"]) - (y_a - 1.5)) < 1e-3,
		"sol de la tuile refaite : celui du fichier réécrit (%.3f → %.3f)" % [y_a, _first_y(st._instances["near:0:0"])])
	_check(is_same(st._instances["near:0:-1"], old_b), "tuile inchangée gardée telle quelle")
	_check(st.stale_near_count() == 0, "plus rien à refaire")

	# Révision sans changement de sol : rien n'est refait.
	var kept: MeshInstance3D = st._instances["near:0:0"]
	_publish(dir, 4500.0, 3, 4, 4)
	lw.on_open_world({"rev": 3})
	upd = lw.wait_poll()
	st.swap_route(upd["route"], int(upd["from_part"]))
	st.update_window(500.0, 0.0, Vector3(500.0, 1.4, 0.0))
	st.flush()
	_check(st.stale_near_count() == 0 and is_same(st._instances["near:0:0"], kept), "révision sans sol changé : tuile gardée")

	st.clear()
	st.queue_free()
	lw.close()
	_remove_tree(base)
	print("test_live_ground_reload : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
