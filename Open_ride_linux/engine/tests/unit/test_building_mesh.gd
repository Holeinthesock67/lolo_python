extends SceneTree

## Tests unitaires sans écran du maillage des bâtiments `building_mesh.gd` (Lot L1).
## Lancement : godot --headless --path engine --script res://tests/unit/test_building_mesh.gd

const BuildingMesh := preload("res://scripts/building_mesh.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")

# Couleurs figées attendues pour `w123456` avec le thème par défaut (critère 5)
const EXPECTED_WALL_HEX_W123456 := "cdb48a"
const EXPECTED_ROOF_HEX_W123456 := "a65a3a"

var _failures := 0
var _checked := 0
var _theme := {}


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _building(id: String, outer: Array, base_y: float = 100.0, height_m: float = 6.0, holes: Array = [], roof: String = "flat") -> Dictionary:
	return {
		"id": id,
		"outer": outer,
		"holes": holes,
		"base_y": base_y,
		"height_m": height_m,
		"roof": roof,
		"hint": {"building": "yes", "colour": null},
	}


func _roof_area_and_checks(res: Dictionary, expected_top_y: float, hole_rect: Rect2 = Rect2()) -> Dictionary:
	var verts: PackedVector3Array = res["vertices"]
	var norms: PackedVector3Array = res["normals"]
	var idx: PackedInt32Array = res["indices"]
	var roof_area := 0.0
	var roof_tris := 0
	var wall_tris := 0
	var all_roof_at_top := true
	var all_roof_facing_up := true
	var center_in_hole := false
	for t in range(0, idx.size(), 3):
		var a := verts[idx[t]]
		var b := verts[idx[t + 1]]
		var c := verts[idx[t + 2]]
		var n := norms[idx[t]]
		if n.y > 0.9:
			roof_tris += 1
			if not (is_equal_approx(a.y, expected_top_y) and is_equal_approx(b.y, expected_top_y) and is_equal_approx(c.y, expected_top_y)):
				all_roof_at_top = false
			var cross := (b - a).cross(c - a)
			roof_area += 0.5 * cross.length()
			var pn := Plane(a, b, c).normal
			if pn.y < 0.99:
				all_roof_facing_up = false
			if hole_rect.size != Vector2.ZERO:
				var center_xz := Vector2((a.x + b.x + c.x) / 3.0, (a.z + b.z + c.z) / 3.0)
				if hole_rect.has_point(center_xz):
					center_in_hole = true
		else:
			wall_tris += 1
	return {
		"roof_area": roof_area,
		"roof_tris": roof_tris,
		"wall_tris": wall_tris,
		"all_roof_at_top": all_roof_at_top,
		"all_roof_facing_up": all_roof_facing_up,
		"center_in_hole": center_in_hole,
	}


# Critère 2 : boîte 10 m × 8 m × 6 m
func _test_box() -> void:
	var outer := [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]]
	var b := _building("box_10x8x6", outer, 120.0, 6.0)
	var res: Dictionary = BuildingMesh.build([b], _theme)
	_check(res["built"] == 1 and res["skipped"] == 0 and res["errors"].is_empty(),
		"boîte 10×8×6 : built = 1, skipped = 0")
	var stats := _roof_area_and_checks(res, 126.0)
	_check(stats["wall_tris"] == 8, "boîte 10×8×6 : 4 murs = 8 triangles (%d)" % stats["wall_tris"])
	_check(absf(stats["roof_area"] - 80.0) <= 0.01,
		"boîte 10×8×6 : aire du toit = %.4f m² (attendu 80,00 ± 0,01)" % stats["roof_area"])
	_check(stats["all_roof_at_top"], "boîte 10×8×6 : sommets du toit tous à base_y + 6 (126 m)")
	_check(stats["all_roof_facing_up"], "boîte 10×8×6 : triangles du toit orientés vers l'extérieur (+y)")

	var verts: PackedVector3Array = res["vertices"]
	var norms: PackedVector3Array = res["normals"]
	var center := Vector3(5.0, 123.0, 4.0)
	var walls_ok := true
	for w in range(4):
		var v0 := verts[w * 4]
		var v1 := verts[w * 4 + 1]
		var v2 := verts[w * 4 + 2]
		var v3 := verts[w * 4 + 3]
		var mid := (v0 + v1 + v2 + v3) * 0.25
		var n := norms[w * 4]
		var out_vec := Vector3(mid.x - center.x, 0.0, mid.z - center.z)
		var pn := Plane(v0, v1, v2).normal
		if not is_equal_approx(n.length(), 1.0) or not is_equal_approx(n.y, 0.0) or n.dot(out_vec) <= 0.0 or pn.dot(n) < 0.99:
			walls_ok = false
	_check(walls_ok, "boîte 10×8×6 : normales des 4 murs unitaires, horizontales et tournées vers l'extérieur")


# Critère 3 : bâtiment en L (6 sommets, concave) et cour intérieure (trou 4×4 dans 20×20)
func _test_l_shape_and_courtyard() -> void:
	# Bâtiment en L : rectangle 20×20 privé d'un coin 10×10 -> aire = 400 - 100 = 300 m²
	var l_outer := [[0.0, 0.0], [20.0, 0.0], [20.0, 10.0], [10.0, 10.0], [10.0, 20.0], [0.0, 20.0]]
	var res_l: Dictionary = BuildingMesh.build([_building("b_l", l_outer, 50.0, 8.0)], _theme)
	var stats_l := _roof_area_and_checks(res_l, 58.0)
	_check(res_l["built"] == 1 and absf(stats_l["roof_area"] - 300.0) <= 0.01 and stats_l["all_roof_facing_up"],
		"bâtiment en L (6 sommets, concave) : aire du toit = %.4f m² (attendu 300,00 ± 0,01)" % stats_l["roof_area"])

	# Cour intérieure : trou 4×4 ([8..12] × [8..12]) dans 20×20 -> aire = 400 - 16 = 384 m²
	var c_outer := [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]]
	var hole := [[8.0, 8.0], [8.0, 12.0], [12.0, 12.0], [12.0, 8.0]]
	var res_c: Dictionary = BuildingMesh.build([_building("b_cour", c_outer, 100.0, 9.0, [hole])], _theme)
	var hole_rect := Rect2(Vector2(8.01, 8.01), Vector2(3.98, 3.98))
	var stats_c := _roof_area_and_checks(res_c, 109.0, hole_rect)
	_check(res_c["built"] == 1 and absf(stats_c["roof_area"] - 384.0) <= 0.01,
		"cour intérieure (trou 4×4 dans 20×20) : aire du toit = %.4f m² (attendu 384,00 ± 0,01)" % stats_c["roof_area"])
	_check(not stats_c["center_in_hole"] and stats_c["all_roof_facing_up"],
		"cour intérieure : aucun triangle de toit dans le trou, faces orientées vers +y")
	_check(stats_c["wall_tris"] == 16,
		"cour intérieure : 4 murs extérieurs + 4 murs de cour = 16 triangles (%d)" % stats_c["wall_tris"])


# Critère 4 : anneau horaire retourné donne le même maillage (à l'ordre près) et est compté
func _test_clockwise_ring() -> void:
	var ccw := [[0.0, 0.0], [12.0, 0.0], [12.0, 9.0], [0.0, 9.0]]
	var cw := [[0.0, 9.0], [12.0, 9.0], [12.0, 0.0], [0.0, 0.0]]
	var r_ccw: Dictionary = BuildingMesh.build([_building("b_orient", ccw, 10.0, 5.0, [], "gabled")], _theme)
	var r_cw: Dictionary = BuildingMesh.build([_building("b_orient", cw, 10.0, 5.0, [], "gabled")], _theme)
	_check(r_ccw["reversed_rings"] == 0 and r_cw["reversed_rings"] == 1,
		"anneau horaire détecté et retourné (reversed_rings = %d)" % r_cw["reversed_rings"])
	_check(r_cw["gabled_as_flat"] == 1,
		"toit gabled traité comme flat et compté (gabled_as_flat = %d)" % r_cw["gabled_as_flat"])
	var v_ccw: PackedVector3Array = r_ccw["vertices"]
	var v_cw: PackedVector3Array = r_cw["vertices"]
	var s_ccw := _roof_area_and_checks(r_ccw, 15.0)
	var s_cw := _roof_area_and_checks(r_cw, 15.0)
	_check(v_ccw == v_cw and is_equal_approx(s_ccw["roof_area"], s_cw["roof_area"]),
		"anneau horaire retourné : même maillage que l'anneau antihoraire (%d sommets)" % v_cw.size())


# Critère 5 : déterminisme et couleur figée pour un id donné
func _test_determinism_and_colors() -> void:
	var b_list := [
		_building("w123456", [[0.0, 0.0], [10.0, 0.0], [10.0, 8.0], [0.0, 8.0]], 200.0, 7.0),
		_building("w654321", [[30.0, 0.0], [42.0, 0.0], [42.0, 10.0], [30.0, 10.0]], 205.0, 6.0),
	]
	var r1: Dictionary = BuildingMesh.build(b_list, _theme)
	var r2: Dictionary = BuildingMesh.build(b_list, _theme)
	_check(r1["vertices"] == r2["vertices"] and r1["normals"] == r2["normals"]
		and r1["colors"] == r2["colors"] and r1["indices"] == r2["indices"],
		"déterminisme : deux appels identiques produisent des tableaux strictement égaux")
	var cols: PackedColorArray = r1["colors"]
	var wall_hex := cols[0].to_html(false)
	var roof_hex := cols[16].to_html(false)
	_check(wall_hex == EXPECTED_WALL_HEX_W123456 and roof_hex == EXPECTED_ROOF_HEX_W123456,
		"couleur figée de w123456 : mur #%s, toit #%s" % [wall_hex, roof_hex])


# Critère 6 : cinq cas invalides -> skipped = 5, aucune erreur Godot
func _test_invalid_cases() -> void:
	var bad_buildings := [
		_building("bad_2pts", [[0.0, 0.0], [10.0, 0.0]], 100.0, 5.0),
		_building("bad_zero_area", [[0.0, 0.0], [5.0, 0.0], [10.0, 0.0]], 100.0, 5.0),
		_building("bad_height0", [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]], 100.0, 0.0),
		_building("bad_non_num", [["a", 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]], 100.0, 5.0),
		_building("bad_crossed", [[0.0, 0.0], [10.0, 10.0], [10.0, 0.0], [0.0, 10.0]], 100.0, 5.0),
	]
	var res: Dictionary = BuildingMesh.build(bad_buildings, _theme)
	_check(res["built"] == 0 and res["skipped"] == 5 and res["errors"].size() == 5 and res["vertices"].is_empty(),
		"5 cas invalides (2 points, aire nulle, height_m 0, non numérique, anneau croisé) : skipped = %d" % res["skipped"])

	# Trou touchant le bord : ignoré proprement (§6)
	var hole_touch := _building(
		"bad_hole_touch",
		[[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]],
		100.0,
		6.0,
		[[[0.0, 5.0], [0.0, 10.0], [5.0, 10.0], [5.0, 5.0]]]
	)
	var res_ht: Dictionary = BuildingMesh.build([hole_touch], _theme)
	_check(res_ht["built"] == 0 and res_ht["skipped"] == 1,
		"trou qui touche le bord de outer : bâtiment ignoré (skipped = 1)")


# Critère 7 : 500 bâtiments rectangulaires en moins de 100 ms
func _test_performance_500() -> void:
	var list_500 := []
	for i in range(500):
		var x0 := float((i % 25) * 20)
		var z0 := float((i / 25) * 20)
		list_500.append(_building("b_%d" % i, [[x0, z0], [x0 + 10.0, z0], [x0 + 10.0, z0 + 8.0], [x0, z0 + 8.0]], 100.0, 6.0))
	var t0 := Time.get_ticks_usec()
	var res: Dictionary = BuildingMesh.build(list_500, _theme)
	var elapsed_ms := (Time.get_ticks_usec() - t0) / 1000.0
	print("Maillage de 500 bâtiments rectangulaires : %.2f ms (%d sommets, %d indices)" % [
		elapsed_ms, res["vertices"].size(), res["indices"].size()])
	_check(res["built"] == 500 and elapsed_ms < 100.0,
		"500 bâtiments rectangulaires maillés en %.2f ms (< 100 ms)" % elapsed_ms)


func _test_skirt() -> void:
	var b := _building("b_skirt", [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]], 100.0, 5.0)
	var res: Dictionary = BuildingMesh.build([b], _theme, 3.0)
	var verts: PackedVector3Array = res["vertices"]
	var min_y := INF
	for v in verts:
		min_y = minf(min_y, v.y)
	_check(absf(min_y - 97.0) < 1e-4, "jupe de 3 m sous base_y : min_y = %.2f (attendu 97.0)" % min_y)


func _init() -> void:
	var tl = ThemeLoader.new()
	_theme = tl.load_named("default")["theme"]
	_test_box()
	_test_l_shape_and_courtyard()
	_test_clockwise_ring()
	_test_determinism_and_colors()
	_test_invalid_cases()
	_test_performance_500()
	_test_skirt()
	print("test_building_mesh : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
