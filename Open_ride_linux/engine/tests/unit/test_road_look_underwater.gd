extends SceneTree

## Tests sans écran du lot SM2 hors épave : aspect de la chaussée par biome (`biomes.<id>.road` du thème,
## road_surface.gd et road_builder.gd : piste de sable du fond marin) et parcours sous l'eau sans passants
## (living_decor.gd `_prepare_job`, ni au village ni en campagne).
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_look_underwater.gd

const RoadSurface := preload("res://scripts/road_surface.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const LivingDecor := preload("res://scripts/living_decor.gd")
const ClimbTest := preload("res://tests/unit/test_climb_detector.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _flat(_s: float) -> float:
	return 0.0


## Fond marin à l'est de x = 2000 m, prairie avant, fondu sur 200 m.
func _weights(x: float, _z: float) -> Dictionary:
	var w := clampf((x - 1900.0) / 200.0, 0.0, 1.0)
	return {"reef": w, "temperate_grassland": 1.0 - w}


func _load_theme() -> Dictionary:
	var f := FileAccess.open("res://themes/default/theme.json", FileAccess.READ)
	return JSON.parse_string(f.get_as_text())


func _test_look() -> void:
	var theme := _load_theme()
	var looks := RoadSurface.biome_looks(theme)
	_check(looks.size() == 1 and looks.has("reef"), "thème par défaut : seul le fond marin donne un aspect de chaussée (%s)" % str(looks.keys()))
	var sand: Color = looks.get("reef", Color.BLACK)
	_check(sand.r > sand.b and sand.r > 0.6, "piste du fond marin couleur sable (%s)" % sand.to_html(false))
	var half := RoadSurface.look_from_weights({"reef": 0.5, "temperate_grassland": 0.5}, looks)
	_check(is_equal_approx(float(half["weight"]), 0.5) and (half["color"] as Color).is_equal_approx(sand),
		"part de la piste = poids du biome, couleur du biome")
	_check(float(RoadSurface.look_from_weights({"alpine": 1.0}, looks)["weight"]) == 0.0, "autre biome : bitume")
	var route = ClimbTest.make_route(4000.0, Callable(self, "_flat"))
	var look := {"weights_at": Callable(self, "_weights"), "looks": looks}
	var before := RoadSurface.section(route, 1000.0, "off", {}, 6.0, look)
	var after := RoadSurface.section(route, 3000.0, "off", {}, 6.0, look)
	_check(float(before["weight"]) == 0.0 and is_equal_approx(float(after["weight"]), 1.0),
		"option gravel coupée : bitume en prairie, piste sur le fond marin")
	_check(float(after["left_m"]) == 3.0 and float(after["right_m"]) == 3.0, "piste de la largeur de la route (physique et cyclistes inchangés)")
	var plain := RoadBuilder.build_chunk_arrays(route, 0, 6.0, {"mode": "off", "surfaces": {}})
	_check(plain[Mesh.ARRAY_COLOR] == null, "sans aspect par biome : tableaux d'avant (pas de couleurs)")
	var arrs := RoadBuilder.build_chunk_arrays(route, 3, 6.0, {"mode": "off", "surfaces": {}, "look": look})
	var cols: PackedColorArray = arrs[Mesh.ARRAY_COLOR]
	var all_sand := true
	for c in cols:
		all_sand = all_sand and c.a < 0.01 and Color(c.r, c.g, c.b).is_equal_approx(sand)
	_check(cols.size() > 0 and all_sand, "tronçon sur le fond marin : piste couleur sable, sans marquage (a = 0)")
	var verts_plain := (RoadBuilder.build_chunk_arrays(route, 3, 6.0, {"mode": "off", "surfaces": {}})[Mesh.ARRAY_VERTEX] as PackedVector3Array)
	_check(verts_plain == (arrs[Mesh.ARRAY_VERTEX] as PackedVector3Array), "même géométrie que le bitume")


func _test_no_passersby_underwater() -> void:
	var route = ClimbTest.make_route(8000.0, Callable(self, "_flat"))
	var counts := {}
	for uw in [false, true]:
		var job := {"gen": 0, "route": route, "world_dir": "", "layers": [], "road_width_m": 6.0,
			"crowd_all_climbs": false, "biome_at": Callable(), "underwater": uw, "result": {}}
		LivingDecor._prepare_job(job)
		counts[uw] = (job["result"]["passersby"].people as Array).size()
	_check(counts[false] > 0, "à l'air libre : promeneurs en campagne (%d)" % counts[false])
	_check(counts[true] == 0, "sous l'eau : aucun passant (%d)" % counts[true])


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_look()
	_test_no_passersby_underwater()
	await process_frame
	print("test_road_look_underwater : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
