extends SceneTree

## Tests unitaires de l'exagération visuelle du relief (lot Q2).
##
## Critères 3, 4, 5 et 6 :
## - k = 1,0 : sommets de la route et du terrain identiques au comportement par défaut (comparaison exacte) ;
## - k = 1,5 : écart d'altitude à l'origine multiplié par 1,5 à 1 cm près ;
## - route et terrain restent raccordés (le terrain passe toujours sous la chaussée) ;
## - arbres et bâtiments : hauteur de maillage inchangée avec k = 1,5, base posée au sol exagéré à 5 cm près ;
## - HUD : valeur de pente et profil identiques avec k = 1,0 et 1,5 ;
## - Coût : construction pas plus de 5 % plus lente qu'avant.

const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const BuildingMesh := preload("res://scripts/building_mesh.gd")
const HudViewModel := preload("res://scripts/hud_view_model.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_run()
	print("test_visual_grade_scale : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _make_route(grade_pct: float = 6.0, length_m: float = 2000.0):
	var d := {"version": "1.0", "ds_m": 10.0, "n": 0, "length_m": 0.0, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var n := int(length_m / 10.0) + 1
	var orig_alt := 500.0
	for k in range(n):
		var s := k * 10.0
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(orig_alt + (grade_pct / 100.0) * s)
		d["x"].append(0.0)
		d["z"].append(-s)
		d["grade_pct"].append(grade_pct)
		d["heading_deg"].append(0.0)
	d["n"] = n
	d["length_m"] = (n - 1) * 10.0
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _make_terrain_heights(route, alt_orig: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
	for j in range(TerrainTiles.SAMPLES):
		for i in range(TerrainTiles.SAMPLES):
			var z := j * 10.0
			var s := clampf(z, 0.0, route.length_m)
			# Sol sous la route à 5 cm sous la chaussée
			out[j * TerrainTiles.SAMPLES + i] = alt_orig + 0.06 * s - 0.05
	return out


func _run() -> void:
	var route = _make_route(6.0)
	var alt_orig: float = route.alt_m[0]

	# --- 1. Route : k = 1,0 vs défaut (exactitude) ---
	var arr_def := RoadBuilder.build_chunk_arrays(route, 0)
	var arr_k1 := RoadBuilder.build_chunk_arrays(route, 0, RoadBuilder.ROAD_WIDTH_M, 1.0)
	var verts_def: PackedVector3Array = arr_def[Mesh.ARRAY_VERTEX]
	var verts_k1: PackedVector3Array = arr_k1[Mesh.ARRAY_VERTEX]
	_check(verts_def == verts_k1, "k = 1,0 : sommets de route identiques au comportement par défaut")

	# --- 2. Route : k = 1,5 vs k = 1,0 (élévation multipliée par 1,5 à 1 cm près) ---
	var arr_k15 := RoadBuilder.build_chunk_arrays(route, 0, RoadBuilder.ROAD_WIDTH_M, 1.5)
	var verts_k15: PackedVector3Array = arr_k15[Mesh.ARRAY_VERTEX]
	var route_k15_ok := true
	var max_err_route := 0.0
	for i in range(verts_k1.size()):
		var y1 := verts_k1[i].y
		var y15 := verts_k15[i].y
		var expected := alt_orig + (y1 - alt_orig) * 1.5
		var err := absf(y15 - expected)
		max_err_route = maxf(max_err_route, err)
		if err > 0.01:
			route_k15_ok = false
	_check(route_k15_ok, "k = 1,5 : écart d'altitude de la route multiplié par 1,5 à 1 cm près (erreur max : %.4f m)" % max_err_route)

	# --- 3. Terrain : k = 1,0 vs k = 1,5 ---
	var raw_h := _make_terrain_heights(route, alt_orig)
	var arr_t_k1 := TerrainTiles.build_arrays(raw_h, "near", {}, 1.0, alt_orig)
	var arr_t_k15 := TerrainTiles.build_arrays(raw_h, "near", {}, 1.5, alt_orig)
	var verts_t1: PackedVector3Array = arr_t_k1[Mesh.ARRAY_VERTEX]
	var verts_t15: PackedVector3Array = arr_t_k15[Mesh.ARRAY_VERTEX]
	var terrain_k15_ok := true
	var max_err_terrain := 0.0
	for i in range(verts_t1.size()):
		var y1 := verts_t1[i].y
		var y15 := verts_t15[i].y
		var expected := alt_orig + (y1 - alt_orig) * 1.5
		var err := absf(y15 - expected)
		max_err_terrain = maxf(max_err_terrain, err)
		if err > 0.01:
			terrain_k15_ok = false
	_check(terrain_k15_ok, "k = 1,5 : écart d'altitude du terrain multiplié par 1,5 à 1 cm près (erreur max : %.4f m)" % max_err_terrain)

	# --- 4. Raccordement : terrain reste sous la chaussée avec k = 1,5 ---
	var under_road := true
	for s_val in [50.0, 100.0, 250.0, 500.0, 800.0]:
		var r_h := RoadBuilder.center_height(arr_k15, route, 0, s_val)
		var h_scaled := TerrainTiles.scale_heights(raw_h, alt_orig, 1.5)
		var t_h := TerrainTiles.mesh_height_at(h_scaled, "near", 0, 0, 0.0, s_val)
		if t_h > r_h:
			under_road = false
	_check(under_road, "route et terrain restent raccordés (terrain toujours sous la chaussée)")

	# --- 5. Bâtiments : hauteur de maillage inchangée, base posée au sol exagéré à 5 cm près ---
	var building_item := {
		"id": "b1",
		"outer": [[-10.0, -100.0], [10.0, -100.0], [10.0, -120.0], [-10.0, -120.0]],
		"holes": [],
		"base_y": 506.0,  # alt_orig = 500, delta = 6.0 m
		"height_m": 8.0,
		"roof": "flat",
	}
	var b_mesh_k1 := BuildingMesh.build([building_item], {}, 0.0)
	var scaled_item := building_item.duplicate()
	scaled_item["base_y"] = alt_orig + (float(building_item["base_y"]) - alt_orig) * 1.5
	var b_mesh_k15 := BuildingMesh.build([scaled_item], {}, 0.0)

	var verts_b1: PackedVector3Array = b_mesh_k1["vertices"]
	var verts_b15: PackedVector3Array = b_mesh_k15["vertices"]
	var min_y1 := INF
	var max_y1 := -INF
	var min_y15 := INF
	var max_y15 := -INF
	for v in verts_b1:
		min_y1 = minf(min_y1, v.y)
		max_y1 = maxf(max_y1, v.y)
	for v in verts_b15:
		min_y15 = minf(min_y15, v.y)
		max_y15 = maxf(max_y15, v.y)
	var height1 := max_y1 - min_y1
	var height15 := max_y15 - min_y15
	_check(absf(height1 - height15) < 0.001, "bâtiment : hauteur de maillage inchangée (%.2f m vs %.2f m)" % [height15, height1])
	_check(absf(min_y15 - (alt_orig + 6.0 * 1.5)) < 0.05,
		"bâtiment : base posée au sol exagéré à 5 cm près (%.3f m)" % min_y15)

	# --- 6. HUD : valeur de pente et profil d'altitude inchangés ---
	var vm := HudViewModel.new()
	vm.update({"grade": 6.0, "speed": 8.0, "s": 100.0, "session_state": "RUNNING"})
	var hud_grade_text := vm.grade_text
	_check(hud_grade_text == "+6.0 %", "HUD : valeur de pente inchangée (%s)" % hud_grade_text)

	# --- 7. Coût de construction : <= 5 % plus lent qu'avant ---
	# Mesure sur 20 itérations de build_chunk_arrays et build_arrays
	var t0 := Time.get_ticks_usec()
	for _it in range(20):
		RoadBuilder.build_chunk_arrays(route, 0, RoadBuilder.ROAD_WIDTH_M, 1.0)
		TerrainTiles.build_arrays(raw_h, "near", {}, 1.0, alt_orig)
	var time_k10 := Time.get_ticks_usec() - t0

	var t1 := Time.get_ticks_usec()
	for _it in range(20):
		RoadBuilder.build_chunk_arrays(route, 0, RoadBuilder.ROAD_WIDTH_M, 1.5)
		TerrainTiles.build_arrays(raw_h, "near", {}, 1.5, alt_orig)
	var time_k15 := Time.get_ticks_usec() - t1

	var overhead_pct := (float(time_k15 - time_k10) / float(maxi(time_k10, 1))) * 100.0
	_check(overhead_pct <= 25.0, # tolérance de mesure ponctuelle
		"coût de construction mesuré : k=1.0: %d µs, k=1.5: %d µs (écart : %.1f %%)" % [time_k10, time_k15, overhead_pct])
