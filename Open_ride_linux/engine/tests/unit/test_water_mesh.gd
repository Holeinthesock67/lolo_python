extends SceneTree

## Tests unitaires sans écran du maillage de l'eau `water_mesh.gd` (Lot L2) et de son matériau, avec ou
## sans reflets animés (Lot P12).
## Lancement : godot --headless --path engine --script res://tests/unit/test_water_mesh.gd

const WaterMesh := preload("res://scripts/water_mesh.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _mesh_area_and_up(res: Dictionary) -> Dictionary:
	var verts: PackedVector3Array = res["vertices"]
	var norms: PackedVector3Array = res["normals"]
	var idx: PackedInt32Array = res["indices"]
	var area := 0.0
	var all_up := true
	for t in range(0, idx.size(), 3):
		var a := verts[idx[t]]
		var b := verts[idx[t + 1]]
		var c := verts[idx[t + 2]]
		area += 0.5 * (b - a).cross(c - a).length()
		var pn := Plane(a, b, c).normal
		if pn.y < 0.99 or norms[idx[t]].y < 0.99:
			all_up = false
	return {"area": area, "all_up": all_up}


func _dist_to_polyline(p: Vector2, poly: Array[Vector2]) -> float:
	var best := INF
	for i in range(poly.size() - 1):
		var q := Geometry2D.get_closest_point_to_segment(p, poly[i], poly[i + 1])
		best = minf(best, p.distance_to(q))
	return best


# Critère 2 : rivière droite de 100 m, width_m 6
func _test_straight_river() -> void:
	var line := {
		"id": "w_straight",
		"kind": "river",
		"width_m": 6.0,
		"points": [
			[0.0, 0.0, 500.0],
			[0.0, -50.0, 500.0],
			[0.0, -100.0, 500.0],
		],
	}
	var res: Dictionary = WaterMesh.build_lines([line])
	_check(res["built"] == 1 and res["skipped"] == 0, "rivière droite 100 m : built = 1, skipped = 0")
	var stats := _mesh_area_and_up(res)
	_check(absf(stats["area"] - 600.0) <= 6.0 and stats["all_up"],
		"rivière droite 100 m × 6 m : aire = %.2f m² (attendu 600 ± 1 %%)" % stats["area"])
	var verts: PackedVector3Array = res["vertices"]
	var uvs: PackedVector2Array = res["uvs"]
	var offsets_ok := true
	var y_ok := true
	for v in verts:
		if not is_equal_approx(absf(v.x), 3.0):
			offsets_ok = false
		if not is_equal_approx(v.y, 500.05):
			y_ok = false
	_check(offsets_ok and y_ok, "rivière droite : tous les sommets à ± 3 m de l'axe et à y + 0,05 m")
	var u_last := uvs[uvs.size() - 1].x
	_check(is_equal_approx(u_last, 100.0) and is_equal_approx(uvs[0].y, 0.0) and is_equal_approx(uvs[1].y, 1.0),
		"rivière droite : u final = %.2f (attendu 100) et v dans {0, 1}" % u_last)


# Critère 3 : rivière en angle droit (et points confondus consécutifs ignorés)
func _test_right_angle_river() -> void:
	var line := {
		"id": "w_bend",
		"kind": "river",
		"width_m": 6.0,
		"points": [
			[0.0, 0.0, 400.0],
			[40.0, 0.0, 400.0],
			[40.0, 0.0, 400.0], # doublon consécutif ignoré
			[40.0, 40.0, 400.0],
		],
	}
	var res: Dictionary = WaterMesh.build_lines([line])
	var stats := _mesh_area_and_up(res)
	var poly: Array[Vector2] = [Vector2(0.0, 0.0), Vector2(40.0, 0.0), Vector2(40.0, 40.0)]
	var max_dist := 0.0
	var verts: PackedVector3Array = res["vertices"]
	for v in verts:
		max_dist = maxf(max_dist, _dist_to_polyline(Vector2(v.x, v.z), poly))
	_check(res["built"] == 1 and max_dist <= 6.0 + 1e-4,
		"rivière en angle droit : distance max à la polyligne = %.3f m (≤ width_m = 6 m)" % max_dist)
	_check(stats["all_up"], "rivière en angle droit : aucun triangle retourné (normales toutes vers +y)")


# Critère 4 : lac 100 m × 50 m avec une île de 10 m × 10 m
func _test_lake_with_island() -> void:
	var outer := [[0.0, 0.0], [100.0, 0.0], [100.0, 50.0], [0.0, 50.0]]
	var island := [[45.0, 20.0], [45.0, 30.0], [55.0, 30.0], [55.0, 20.0]]
	var lake := {
		"id": "w_lake",
		"kind": "lake",
		"level_y": 1002.0,
		"outer": outer,
		"holes": [island],
	}
	var res: Dictionary = WaterMesh.build_areas([lake])
	var stats := _mesh_area_and_up(res)
	_check(res["built"] == 1 and absf(stats["area"] - 4900.0) <= 0.1 and stats["all_up"],
		"lac 100×50 avec île 10×10 : aire = %.3f m² (attendu 4 900,0 ± 0,1)" % stats["area"])
	var verts: PackedVector3Array = res["vertices"]
	var uvs: PackedVector2Array = res["uvs"]
	var idx: PackedInt32Array = res["indices"]
	var all_at_level := true
	var uv_matches_xz := true
	for i in range(verts.size()):
		if not is_equal_approx(verts[i].y, 1002.0):
			all_at_level = false
		if not is_equal_approx(uvs[i].x, verts[i].x) or not is_equal_approx(uvs[i].y, verts[i].z):
			uv_matches_xz = false
	var island_rect := Rect2(Vector2(45.01, 20.01), Vector2(9.98, 9.98))
	var tri_on_island := false
	for t in range(0, idx.size(), 3):
		var a := verts[idx[t]]
		var b := verts[idx[t + 1]]
		var c := verts[idx[t + 2]]
		var center := Vector2((a.x + b.x + c.x) / 3.0, (a.z + b.z + c.z) / 3.0)
		if island_rect.has_point(center):
			tri_on_island = true
	_check(all_at_level and uv_matches_xz and not tri_on_island,
		"lac avec île : sommets tous à level_y, UV = (x, z), aucun triangle sur l'île")


# Critère 5 : width_m absent -> largeur de 2 m (et kind inconnu accepté)
func _test_default_width_and_unknown_kind() -> void:
	var line := {
		"id": "w_default",
		"kind": "torrent_inconnu",
		"points": [[0.0, 0.0, 200.0], [20.0, 0.0, 200.0]],
	}
	var res: Dictionary = WaterMesh.build_lines([line])
	var verts: PackedVector3Array = res["vertices"]
	var width := verts[0].distance_to(verts[1])
	_check(res["built"] == 1 and is_equal_approx(width, 2.0),
		"width_m absent et kind inconnu : largeur = %.2f m (attendu 2,00 m)" % width)


# Critère 6 : cas invalides comptés dans skipped, aucune erreur Godot
func _test_invalid_cases() -> void:
	var bad_lines := [
		{"id": "l_1pt", "kind": "river", "width_m": 4.0, "points": [[0.0, 0.0, 100.0]]},
		{"id": "l_dup", "kind": "river", "width_m": 4.0, "points": [[5.0, 5.0, 100.0], [5.0, 5.0, 100.0], [5.0, 5.0, 100.0]]},
	]
	var rl: Dictionary = WaterMesh.build_lines(bad_lines)
	_check(rl["built"] == 0 and rl["skipped"] == 2 and rl["errors"].size() == 2,
		"cours d'eau invalides (1 point, points confondus) : skipped = %d" % rl["skipped"])

	var bad_areas := [
		{"id": "a_2pts", "kind": "lake", "level_y": 500.0, "outer": [[0.0, 0.0], [10.0, 0.0]], "holes": []},
		{"id": "a_bad_lvl", "kind": "lake", "level_y": "haut", "outer": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]], "holes": []},
	]
	var ra: Dictionary = WaterMesh.build_areas(bad_areas)
	_check(ra["built"] == 0 and ra["skipped"] == 2 and ra["errors"].size() == 2,
		"plans d'eau invalides (anneau de 2 points, level_y texte) : skipped = %d" % ra["skipped"])


# Critère 7 : déterminisme
func _test_determinism() -> void:
	var lines := [{"id": "w1", "kind": "stream", "width_m": 3.0, "points": [[0.0, 0.0, 100.0], [30.0, -20.0, 99.0], [60.0, -10.0, 98.0]]}]
	var areas := [{"id": "a1", "kind": "pond", "level_y": 95.0, "outer": [[0.0, 0.0], [20.0, 0.0], [20.0, 15.0], [0.0, 15.0]], "holes": []}]
	var l1: Dictionary = WaterMesh.build_lines(lines)
	var l2: Dictionary = WaterMesh.build_lines(lines)
	var a1: Dictionary = WaterMesh.build_areas(areas)
	var a2: Dictionary = WaterMesh.build_areas(areas)
	_check(l1["vertices"] == l2["vertices"] and l1["uvs"] == l2["uvs"] and l1["indices"] == l2["indices"]
		and a1["vertices"] == a2["vertices"] and a1["uvs"] == a2["uvs"] and a1["indices"] == a2["indices"],
		"déterminisme : deux appels identiques produisent des tableaux strictement égaux")


# Lot P12 : sans shimmer, le matériau d'E4 inchangé ; avec, des ondes qui défilent dans le sens du vent
func _test_shimmer_material() -> void:
	var plain = WaterMesh.make_material(false)
	_check(plain is StandardMaterial3D and plain.albedo_color == OsmStreamer.WATER_COLOR
		and is_equal_approx(plain.roughness, 0.10),
		"sans shimmer : StandardMaterial3D de la couleur et de la rugosité d'E4")
	WaterMesh.update_shimmer(plain, {"dir": Vector3(1, 0, 0), "strength": 1.0}, 1.0)
	_check(plain.albedo_color == OsmStreamer.WATER_COLOR, "sans shimmer : update_shimmer sans effet")
	var sh = WaterMesh.make_material(true)
	_check(sh is ShaderMaterial and (sh as ShaderMaterial).shader != null, "avec shimmer : matériau du shader water_shimmer")
	var f0: Vector2 = sh.get_shader_parameter("flow")
	for i in range(60):
		WaterMesh.update_shimmer(sh, {"dir": Vector3(0, 0, -1), "strength": 0.5}, 1.0 / 60.0)
	var f1: Vector2 = sh.get_shader_parameter("flow")
	var half := TAU * 50.0   # décalage replié modulo 200π
	var step := Vector2(wrapf(f1.x - f0.x, -half, half), wrapf(f1.y - f0.y, -half, half))
	_check(step.y < 0.0 and absf(step.x) < 1e-6 and absf(step.length() - (0.05 + 0.6 * 0.5)) < 0.01,
		"ondes poussées vers le nord par un vent de 30 km/h (%.3f m en 1 s)" % step.length())


func _init() -> void:
	_test_straight_river()
	_test_right_angle_river()
	_test_lake_with_island()
	_test_default_width_and_unknown_kind()
	_test_invalid_cases()
	_test_determinism()
	_test_shimmer_material()
	print("test_water_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
