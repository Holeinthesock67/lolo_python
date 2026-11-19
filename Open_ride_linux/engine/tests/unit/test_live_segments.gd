extends SceneTree

## Monde ouvert, lot W21 : `segments.json` du dossier de séance (écrit par le core) relu par live_world.gd et posé
## sur la route ; portiques recalculés sans refaire ceux qui n'ont pas changé ; noms ajoutés au HUD de segment ;
## arches de bonus jusqu'au bout de la route connue. Sans écran.
## Lancement : godot --headless --path engine --script res://tests/unit/test_live_segments.gd

const LiveWorld := preload("res://scripts/live_world.gd")
const SegmentMarkers := preload("res://scripts/segment_markers.gd")
const SegmentHudModel := preload("res://scripts/segment_hud_model.gd")

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
		part["lat"].append(44.0)
		part["lon"].append(5.0 + s * 1.27e-5)
		part["alt_m"].append(300.0 + s * 0.05)
		part["x"].append(s)
		part["z"].append(0.0)
		part["grade_pct"].append(5.0)
		part["heading_deg"].append(90.0)
		s += 10.0
	part["n"] = part["x"].size()
	return part


func _publish(dir: String, length: float, rev: int, changed_from: int) -> void:
	var parts := int(ceil(length / 1000.0))
	for k in range(changed_from, parts):
		_write_json(dir.path_join("route").path_join("part_%d.json" % k), _part(k, length))
	_write_json(dir.path_join("junctions.json"), {"version": "1.0", "revision": rev, "junctions": []})
	_write_json(dir.path_join("live.json"), {"version": "1.0", "revision": rev,
		"route": {"parts": parts, "length_m": length, "changed_from_part": changed_from},
		"tiles": {"near": [], "far": []}, "layer_tiles": [], "status": "ok"})


func _seg(id: String, s0: float, s1: float) -> Dictionary:
	return {"id": id, "name": "Montée n°1 (4e cat.)", "type": "climb", "s_start": s0, "s_end": s1,
		"length_m": s1 - s0, "avg_grade_pct": 5.0, "gain_m": (s1 - s0) * 0.05, "category": "4", "source": "auto"}


func _count(marks: Array, kind: String) -> int:
	var n := 0
	for m in marks:
		if m["kind"] == kind:
			n += 1
	return n


func _init() -> void:
	var base := "user://w21_live_%d" % OS.get_process_id()
	var dir := base.path_join("ow-test.world")
	_write_json(dir.path_join("manifest.json"), {"format": "openride-world", "format_version": "1.4", "live": true,
		"layers": {}, "grid": {"near_m": 1000, "far_m": 5000, "e0": 0, "n0": 0}})
	_publish(dir, 3000.0, 1, 0)
	var lw = LiveWorld.new()
	_check(lw.open(dir), "séance ouverte")
	_check(lw.route.segments.is_empty() and not lw.check_segments(true), "sans segments.json : aucun segment")

	# --- segments.json écrit par le core ---
	_write_json(dir.path_join("segments.json"), {"version": "1.0", "segments": [_seg("owc1", 500.0, 1500.0),
		_seg("owc2", 2500.0, 3600.0)]})
	_check(lw.check_segments(true), "segments relus")
	_check(lw.route.segments.size() == 1 and lw.route.segments[0]["id"] == "owc1",
		"seul le segment déjà dans la route lue est posé (le second finit au-delà de 3 000 m)")
	_check(not lw.check_segments(true) or lw.route.segments.size() == 1, "fichier inchangé : même liste")
	_publish(dir, 4500.0, 2, 2)
	lw.on_open_world({"rev": 2})
	var done: Dictionary = lw.wait_poll()
	_check(done.has("route") and done.has("segments") and lw.route.segments.size() == 2,
		"route prolongée : le second segment est posé sur la nouvelle route")
	_write_json(dir.path_join("segments.json"), "pas une liste")
	_check(not lw.check_segments(true) and lw.route.segments.size() == 2, "fichier abîmé : la liste d'avant reste")

	# --- portiques ---
	var markers = SegmentMarkers.new()
	var every := 2000.0
	markers.refresh(lw.route, every)
	_check(_count(markers.marks, "start") == 2 and _count(markers.marks, "finish") == 2, "deux départs et deux sommets")
	_check(_count(markers.marks, "arch") == 2, "arches à 2 et 4 km : jusqu'au bout de la route connue (4,5 km)")
	markers.update(400.0, true)
	var near_node = null
	for i in markers._nodes:
		if markers.marks[i]["kind"] == "start" and markers.marks[i]["segment_id"] == "owc1":
			near_node = markers._nodes[i]
	_check(near_node != null, "portique du départ de la montée 1 en scène")
	_publish(dir, 5500.0, 3, 4)
	lw.on_open_world({"rev": 3})
	lw.wait_poll()
	markers.refresh(lw.route, every, 4000.0)
	var still := false
	for i in markers._nodes:
		if markers._nodes[i] == near_node:
			still = markers.marks[i]["segment_id"] == "owc1" and markers.marks[i]["kind"] == "start"
	_check(still, "route prolongée plus loin : le portique proche est gardé (pas de clignotement)")
	_check(_count(markers.marks, "arch") == 2, "arches à 2 et 4 km (route de 5,5 km)")
	markers.refresh(lw.route, every, 0.0)
	_check(markers._nodes.is_empty(), "route réécrite dès 0 m : les nœuds sont refaits")
	markers.free()

	# --- HUD de segment ---
	var hud = SegmentHudModel.new()
	hud.result = {"segment_id": "x"}
	hud.merge_segments(lw.route.segments)
	_check(hud.names.has("owc2") and hud.names["owc1"]["name"] == "Montée n°1 (4e cat.)", "noms ajoutés")
	_check(hud.result.get("segment_id", "") == "x", "le résultat affiché n'est pas effacé")

	lw.close()
	_remove_tree(base)
	print("test_live_segments : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
