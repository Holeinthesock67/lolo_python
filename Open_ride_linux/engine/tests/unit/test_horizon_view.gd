extends SceneTree

## Tests unitaires sans écran du relief d'horizon (horizon_view.gd, lot JP4, version 6.0) : niveau « horizon » de
## terrain_tiles (maille 500 m, tuiles de 50 km, posé sous le terrain lointain) ; relief exagéré près de la route et
## réel au-delà de RELIEF_REAL_M (le Fuji ne monte pas à 8 000 m) ; points de route gardés ; rien n'est créé sans
## tuiles d'horizon (parcours d'avant la 1.8) ni avec `--horizon=off`.
## Lancement : godot --headless --path engine --script res://tests/unit/test_horizon_view.gd

const HorizonView := preload("res://scripts/horizon_view.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _init() -> void:
	_test_level()
	_test_display_height()
	_test_probes()
	_test_no_tiles()
	print("test_horizon_view : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _route(count: int) -> Object:
	var r = RouteDataScript.new()
	r.n = count
	for i in range(count):
		r.x.append(i * 10.0)
		r.z.append(0.0)
		r.alt_m.append(100.0)
	r.relief_k = 2.5
	return r


func _test_level() -> void:
	var lv: Dictionary = TerrainTiles.LEVELS.get("horizon", {})
	_check(not lv.is_empty(), "niveau horizon connu de terrain_tiles")
	_check(is_equal_approx(float(lv.get("cell", 0.0)), 500.0), "maille de 500 m (Format .world 1.8, §5)")
	_check(is_equal_approx(float(lv.get("size", 0.0)), 50000.0), "tuiles de 50 km")
	_check(float(lv.get("y_offset", 0.0)) < 0.0, "horizon posé sous le terrain lointain (pas de scintillement)")
	_check(TerrainTiles.tile_origin("horizon", 1, -1) == Vector3(50000.0, 0.0, -50000.0), "origine de tuile")


func _test_display_height() -> void:
	var probes := PackedVector2Array([Vector2.ZERO])
	_check(is_equal_approx(HorizonView.display_height(3776.0, Vector2(30000.0, 0.0), probes, 1.0, 0.0), 3776.0),
		"relief réel : hauteur inchangée")
	var near := HorizonView.display_height(1100.0, Vector2(2000.0, 0.0), probes, 2.5, 100.0)
	_check(is_equal_approx(near, 100.0 + 1000.0 * 2.5), "près de la route : relief exagéré comme le terrain lointain")
	var far := HorizonView.display_height(3776.0, Vector2(25000.0, 0.0), probes, 2.5, 800.0)
	_check(is_equal_approx(far, 3776.0), "à 25 km : relief réel, le Fuji garde 3 776 m (%.0f)" % far)
	var mid := HorizonView.display_height(1100.0, Vector2(10000.0, 0.0), probes, 2.5, 100.0)
	_check(mid > 1100.0 and mid < 2600.0, "entre 5 et 15 km : passage progressif (%.0f)" % mid)


func _test_probes() -> void:
	var p0 := HorizonView.route_probes(null)
	_check(p0.size() == 1 and p0[0] == Vector2.ZERO, "sans parcours : origine seule")
	var p := HorizonView.route_probes(_route(1000))
	_check(p.size() <= HorizonView.ROUTE_PROBES and p.size() >= HorizonView.ROUTE_PROBES / 2,
		"au plus %d points de route gardés (%d)" % [HorizonView.ROUTE_PROBES, p.size()])
	_check(p[0] == Vector2(0.0, 0.0), "premier point de la route gardé")


func _test_no_tiles() -> void:
	var dir := OS.get_user_data_dir().path_join("horizon_test_vide.world")
	DirAccess.make_dir_recursive_absolute(dir.path_join("terrain/far"))
	var hv = HorizonView.new()
	hv.set_world(_route(10), dir)
	hv.flush()
	_check(hv.tile_count() == 0, "parcours sans tuiles d'horizon : rien n'est créé")
	hv.enabled = false
	hv.set_world(_route(10), dir)
	_check(hv.tile_count() == 0, "--horizon=off : rien n'est créé")
	hv.free()
