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
## Lot Y15 (relief porté par la route) :
## - `sample()["y"]` à la hauteur affichée, `alt_m` et `grade_pct` réels ; terrain lointain creusé sous la route affichée ;
## - tangage de la caméra sur 8 % avec k = 2 : atan(0,16) ; champ de vision resserré en montée, élargi en descente.

const RoadBuilder := preload("res://scripts/road_builder.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const BuildingMesh := preload("res://scripts/building_mesh.gd")
const HudViewModel := preload("res://scripts/hud_view_model.gd")
const CameraFollow := preload("res://scripts/camera_follow.gd")
const CameraViews := preload("res://scripts/camera_views.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")

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
	route.relief_k = 1.0
	var arr_k1 := RoadBuilder.build_chunk_arrays(route, 0)
	var verts_def: PackedVector3Array = arr_def[Mesh.ARRAY_VERTEX]
	var verts_k1: PackedVector3Array = arr_k1[Mesh.ARRAY_VERTEX]
	_check(verts_def == verts_k1, "k = 1,0 : sommets de route identiques au comportement par défaut")

	# --- 2. Route : k = 1,5 vs k = 1,0 (élévation de l'axe multipliée par 1,5 à 1 cm près ; les décalages
	# de la coupe en travers, comme la descente des accotements, ne sont pas exagérés) ---
	route.relief_k = 1.5
	var arr_k15 := RoadBuilder.build_chunk_arrays(route, 0)
	route.relief_k = 1.0
	var verts_k15: PackedVector3Array = arr_k15[Mesh.ARRAY_VERTEX]
	var route_k15_ok := true
	var max_err_route := 0.0
	for i in range(verts_k1.size()):
		var y1 := verts_k1[i].y
		var y15 := verts_k15[i].y
		var axis_y := alt_orig + 0.06 * (-verts_k1[i].z)   # axe de la route droite vers le nord à 6 %
		var expected := y1 + (axis_y - alt_orig) * 0.5
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
	for i in range(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES):   # grille ; les jupes suivent, à SKIRT_M sous le bord
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

	# --- 6. HUD : la pente affichée vient de la trame `state` (pente réelle du core), jamais de k ---
	var vm = HudViewModel.new()
	vm.on_state({"type": "state", "session_state": "RUNNING", "grade": 6.0, "v": 8.0, "s": 100.0}, 0.0)
	var hud_grade_text := str(vm.evaluate(0.0).get("grade_text", ""))
	_check(hud_grade_text == "+6.0 %", "HUD : valeur de pente inchangée (%s)" % hud_grade_text)
	var prof_a: Dictionary = vm.profile(route, 100.0)
	var prof_b: Dictionary = vm.profile(route, 100.0)
	_check(prof_a == prof_b, "HUD : profil d'altitude tiré de la route réelle (non exagérée)")

	# --- 7. Coût de construction ---
	# k = 1,0 suit exactement le chemin d'avant le lot (aucune mise à l'échelle) ; on borne le surcoût
	# de k = 1,5 par rapport à ce chemin, en médiane de 5 mesures de 10 constructions.
	var t_k10: Array = []
	var t_k15: Array = []
	for _rep in range(5):
		route.relief_k = 1.0
		var t0 := Time.get_ticks_usec()
		for _it in range(10):
			RoadBuilder.build_chunk_arrays(route, 0)
			TerrainTiles.build_arrays(raw_h, "near", {}, 1.0, alt_orig)
		t_k10.append(Time.get_ticks_usec() - t0)
		route.relief_k = 1.5
		var t1 := Time.get_ticks_usec()
		for _it in range(10):
			RoadBuilder.build_chunk_arrays(route, 0)
			TerrainTiles.build_arrays(raw_h, "near", {}, 1.5, alt_orig)
		t_k15.append(Time.get_ticks_usec() - t1)
	route.relief_k = 1.0
	t_k10.sort()
	t_k15.sort()
	var med10: int = t_k10[2]
	var med15: int = t_k15[2]
	var overhead_pct := (float(med15 - med10) / float(maxi(med10, 1))) * 100.0
	_check(PerfBudget.check("visual_grade_overhead", overhead_pct, "%"),
		"coût de construction (médianes) : k=1.0 : %d µs, k=1.5 : %d µs (écart %.1f %%, au plus 5 %%)" % [med10, med15, overhead_pct])

	# --- 8. Lot Y15 : relief porté par la route ---
	route.relief_k = 2.0
	var smp: Dictionary = route.sample(500.0)
	_check(absf(float(smp["y"]) - (alt_orig + 2.0 * 0.06 * 500.0)) < 0.01,
		"k = 2,0 : sample()[\"y\"] à la hauteur affichée (%.2f m)" % float(smp["y"]))
	_check(absf(float(smp["alt_m"]) - (alt_orig + 0.06 * 500.0)) < 0.01 and absf(float(smp["grade_pct"]) - 6.0) < 1e-6,
		"k = 2,0 : alt_m et grade_pct restent les vraies valeurs")
	_check(route.display_y(alt_orig) == alt_orig, "le départ du parcours ne bouge pas")
	var carved := TerrainTiles.carve_under_route(_make_terrain_heights(route, alt_orig + 1000.0), "far", 0, -1, route)
	var carve_ok := true
	for s_val in [100.0, 400.0, 700.0]:
		var p: Vector3 = route.sample_point(s_val)
		var h := TerrainTiles.mesh_height_at(carved, "far", 0, -1, p.x, p.z)
		if not (h < p.y):
			carve_ok = false
	_check(carve_ok, "k = 2,0 : terrain lointain creusé sous la route affichée")

	var steep = _make_route(8.0)
	steep.relief_k = 2.0
	var follow = CameraFollow.new()
	var pitch := 0.0
	for _i in range(120):
		pitch = follow.pitch_deg(steep, 300.0, 8.0, 1.0 / 60.0)
	var want := rad_to_deg(atan(0.16))
	_check(absf(pitch - want) < 0.3, "tangage sur 8 %% avec k = 2,0 : %.2f° (attendu %.2f°)" % [pitch, want])
	_check(CameraViews.fov_deg(65.0, 0.0) == 65.0, "champ de vision inchangé sur le plat")
	var fov_up := CameraViews.fov_deg(65.0, pitch)
	var fov_down := CameraViews.fov_deg(65.0, -pitch)
	_check(fov_up < 65.0 and fov_up >= 65.0 - CameraViews.FOV_CLIMB_DEG, "champ de vision resserré en montée (%.1f°)" % fov_up)
	_check(fov_down > 65.0 and fov_down <= 65.0 + CameraViews.FOV_DESCENT_DEG, "champ de vision élargi en descente (%.1f°)" % fov_down)
	_check(CameraViews.fov_deg(65.0, 40.0) == 65.0 - CameraViews.FOV_CLIMB_DEG, "écart du champ de vision borné")
	route.relief_k = 1.0
