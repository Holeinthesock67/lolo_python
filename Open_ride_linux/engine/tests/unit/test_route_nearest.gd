extends SceneTree

## Point de route le plus proche (route_data.gd `nearest_index`, terrain_tiles.gd `nearest_route_alt`) :
## même résultat que le parcours de tous les points, sur la demo, une boucle et des points loin de la route ;
## coût d'un appel (saccades du 04/11 : appelé trois fois par touffe d'herbe sur un parcours sans terrain).
## Lancement : godot --headless --path engine --script res://tests/unit/test_route_nearest.gd

const RouteDataScript := preload("res://scripts/route_data.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const PerfBudget := preload("res://tests/perf_budget.gd")
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


## Boucle de 2 km de rayon 318 m, points tous les 10 m.
func _loop() -> Variant:
	var n := 201
	var d := {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": 2000.0, "type": "loop",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var r := 2000.0 / TAU
	for i in range(n):
		var a := TAU * float(i) / float(n - 1)
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(200.0 + 30.0 * sin(3.0 * a))
		d["x"].append(r * cos(a))
		d["z"].append(r * sin(a))
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(0.0)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _same_as_linear(route, label: String) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 0x5ACC
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for k in range(route.n):
		lo = Vector2(minf(lo.x, route.x[k]), minf(lo.y, route.z[k]))
		hi = Vector2(maxf(hi.x, route.x[k]), maxf(hi.y, route.z[k]))
	var bad := 0
	var tries := 3000
	for i in range(tries):
		var p: Vector2
		if i % 3 == 0:   # près de la route : là où l'herbe et les détails du sol sont posés
			var k := rng.randi_range(0, route.n - 1)
			p = Vector2(route.x[k], route.z[k]) + Vector2(rng.randf_range(-20.0, 20.0), rng.randf_range(-20.0, 20.0))
		elif i % 3 == 1:
			p = Vector2(rng.randf_range(lo.x, hi.x), rng.randf_range(lo.y, hi.y))
		else:            # loin, hors du rectangle de la route
			p = Vector2(rng.randf_range(lo.x - 3000.0, hi.x + 3000.0), rng.randf_range(lo.y - 3000.0, hi.y + 3000.0))
		if route.nearest_index(p.x, p.y) != route._nearest_index_linear(p.x, p.y):
			bad += 1
	_check(bad == 0, "%s : même point que le parcours de tous les points (%d écart(s) sur %d)" % [label, bad, tries])


func _initialize() -> void:
	var demo = RouteDataScript.new()
	_check(demo.load_world_dir("res://demo/demo.world"), "demo intégrée chargée (%d points)" % demo.n)
	_same_as_linear(demo, "demo")
	_same_as_linear(_loop(), "boucle")
	var k := 250
	_check(is_equal_approx(TerrainTiles.nearest_route_alt(demo, demo.x[k] + 3.0, demo.z[k] - 2.0), demo.alt_m[k]),
		"nearest_route_alt : altitude du point le plus proche")
	# Route changée après le chargement (n différent) : repli sur le parcours de tous les points.
	var cut = RouteDataScript.new()
	cut.load_world_dir("res://demo/demo.world")
	cut.n = 100
	_check(cut.nearest_index(demo.x[400], demo.z[400]) == cut._nearest_index_linear(demo.x[400], demo.z[400]),
		"grille périmée : même résultat que le parcours de tous les points")
	var calls := 3000
	var t0 := Time.get_ticks_usec()
	for i in range(calls):
		var j: int = (i * 37) % demo.n
		TerrainTiles.nearest_route_alt(demo, demo.x[j] + 8.0, demo.z[j] + 5.0)
	var per_call_ms := (Time.get_ticks_usec() - t0) / 1000.0 / calls
	_check(PerfBudget.check("route_nearest_alt", per_call_ms), "coût d'un appel près de la route : %.4f ms" % per_call_ms)
	_test_far_points_cost(demo)
	_test_height_fn_far_tile(demo)
	print("test_route_nearest : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)


## Points à 1 à 3 km de la route (champs des tracteurs, essai r790d : 20 s par tronçon côtier) : les cases
## occupées seules sont lues au-delà de quelques anneaux, coût borné comme près de la route.
func _test_far_points_cost(route) -> void:
	var calls := 600
	var t0 := Time.get_ticks_usec()
	for i in range(calls):
		var j: int = (i * 37) % route.n
		var a := TAU * float(i) / float(calls)
		var d := 1000.0 + 2000.0 * float(i % 7) / 6.0
		TerrainTiles.nearest_route_alt(route, route.x[j] + d * cos(a), route.z[j] + d * sin(a))
	var per_call_ms := (Time.get_ticks_usec() - t0) / 1000.0 / calls
	_check(PerfBudget.check("route_nearest_far", per_call_ms), "coût d'un appel à 1-3 km de la route : %.4f ms" % per_call_ms)


## terrain_height_fn hors des tuiles proches : tuile lointaine abaissée comme à l'affichage, puis route.
func _test_height_fn_far_tile(route) -> void:
	var wd := "user://test_route_nearest.world"
	var far_dir := wd.path_join("terrain").path_join("far")
	DirAccess.make_dir_recursive_absolute(far_dir)
	var hs := PackedFloat32Array()
	hs.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
	hs.fill(123.0)
	hs[0] = NAN   # coin (0, 0) inconnu : repli sur la route
	var f := FileAccess.open(TerrainTiles.tile_path(wd, "far", 0, 0), FileAccess.WRITE)
	f.store_buffer(hs.to_byte_array())
	f.close()
	var h := OsmStreamer.terrain_height_fn(wd, route)
	var far_dy: float = TerrainTiles.LEVELS["far"]["y_offset"]
	_check(is_equal_approx(float(h.call(2500.0, 2500.0)), 123.0 + far_dy),
		"hors des tuiles proches : hauteur de la tuile lointaine (%.2f)" % float(h.call(2500.0, 2500.0)))
	_check(is_equal_approx(float(h.call(1.0, 1.0)), TerrainTiles.nearest_route_alt(route, 1.0, 1.0)),
		"lointain inconnu (NaN) : altitude de la route la plus proche")
	_check(is_equal_approx(float(h.call(-2500.0, -2500.0)), TerrainTiles.nearest_route_alt(route, -2500.0, -2500.0)),
		"sans tuile : altitude de la route la plus proche")
	DirAccess.remove_absolute(TerrainTiles.tile_path(wd, "far", 0, 0))
