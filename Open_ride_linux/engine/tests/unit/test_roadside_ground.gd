extends SceneTree

## Tests sans écran de `roadside_ground.gd` (13 novembre 2026, « les bornes kilométriques lévitent ») : profil de la
## chaussée et de ses talus, pied posé au plus bas des appuis, borne posée par roadside_props.gd sur un flanc.
## Lancement : godot --headless --path engine --script res://tests/unit/test_roadside_ground.gd

const RoadsideGround := preload("res://scripts/roadside_ground.gd")
const RoadsideProps := preload("res://scripts/roadside_props.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const TerrainTiles := preload("res://scripts/terrain_tiles.gd")

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
	call_deferred("_run")


func _run() -> void:
	# Profil en travers : chaussée, bas-côté, talus, puis rien
	var half := RoadBuilder.ROAD_WIDTH_M * 0.5
	_check(RoadsideGround.road_surface_y(10.0, 1.0, half) == 10.0, "chaussée à la hauteur de la route")
	_check(is_equal_approx(RoadsideGround.road_surface_y(10.0, half + RoadBuilder.SHOULDER_WIDTH_M, half),
		10.0 - RoadBuilder.SHOULDER_DROP_M), "bord extérieur du bas-côté SHOULDER_DROP_M plus bas")
	var outer := half + RoadBuilder.SHOULDER_WIDTH_M
	_check(is_equal_approx(RoadsideGround.road_surface_y(10.0, outer + RoadBuilder.SKIRT_OUT_M, half),
		10.0 - RoadBuilder.SHOULDER_DROP_M - RoadBuilder.SKIRT_DROP_M), "pied du talus SKIRT_DROP_M plus bas")
	_check(is_inf(RoadsideGround.road_surface_y(10.0, outer + RoadBuilder.SKIRT_OUT_M + 0.1, half)), "rien au-delà du talus")

	# Sans sol : hauteur inchangée
	var xf := Transform3D(Basis(), Vector3(4.5, 10.0, 0.0))
	_check(RoadsideGround.foot_y(Callable(), xf, Vector3(0, 10, 0), Vector3.RIGHT, half) == 10.0,
		"sans couche terrain : hauteur de la route gardée")

	# Flanc qui descend vers +x (pente 40 %) : terrain 1 m sous la route à 2,5 m de l'axe
	var slope := func(x: float, _z: float) -> float: return 11.0 - 0.4 * x
	var y := RoadsideGround.foot_y(slope, xf, Vector3(0, 10, 0), Vector3.RIGHT, half)
	var talus := RoadsideGround.road_surface_y(10.0, 4.5, half)
	_check(is_equal_approx(y, maxf(slope.call(4.5, 0.0), talus) - RoadsideGround.FOOT_SINK_M),
		"un appui : sol visible (le plus haut du terrain et du talus) moins FOOT_SINK_M (%.2f)" % y)
	var feet := PackedVector3Array([Vector3(-0.2, 0, 0), Vector3(0.2, 0, 0)])
	var y2 := RoadsideGround.foot_y(slope, xf, Vector3(0, 10, 0), Vector3.RIGHT, half, feet)
	var low := minf(maxf(slope.call(4.3, 0.0), RoadsideGround.road_surface_y(10.0, 4.3, half)),
		maxf(slope.call(4.7, 0.0), RoadsideGround.road_surface_y(10.0, 4.7, half)))
	_check(is_equal_approx(y2, low - RoadsideGround.FOOT_SINK_M), "deux appuis : posé sur le plus bas, l'autre enterré")
	# Terrain au-dessus du talus (déblai) : le pied monte sur le terrain
	var bank := func(x: float, _z: float) -> float: return 10.0 + 0.3 * x
	var y3 := RoadsideGround.foot_y(bank, xf, Vector3(0, 10, 0), Vector3.RIGHT, half)
	_check(is_equal_approx(y3, bank.call(4.5, 0.0) - RoadsideGround.FOOT_SINK_M), "déblai : pied sur le terrain, au-dessus de la route")

	# Appuis d'une borne construite : socle au sol ; panneau de col : poteaux seulement, pas la plaque en hauteur
	var props = RoadsideProps.new()
	root.add_child(props)
	var km: Node3D = props.build_prop({"kind": "km", "s": 1000.0, "lines": ["km 1"]})
	var kf: PackedVector3Array = RoadsideProps.feet(km)
	var span := 0.0
	for f in kf:
		span = maxf(span, absf(f.x))
	_check(kf.size() >= 4 and span >= RoadsideProps.KM_W * 0.5, "borne : appuis aux coins du socle (%d, demi-largeur %.2f m)" % [kf.size(), span])
	var sign: Node3D = props.build_prop({"kind": "summit", "s": 1000.0, "lines": ["Col d'essai", "1 234 m"]})
	var sf: PackedVector3Array = RoadsideProps.feet(sign)
	var all_low := true
	for f in sf:
		all_low = all_low and f.y == 0.0
	_check(not sf.is_empty() and all_low, "panneau de col : appuis au sol (poteaux), %d points" % sf.size())
	km.free()
	sign.free()
	props.queue_free()

	# Monde ouvert : tuile écrite pendant la séance, après une première lecture (tuile absente alors)
	var route = RouteDataScript.new()
	_check(route.load_world_dir("res://demo/demo.world"), "démo lisible")
	var dir := OS.get_user_data_dir().path_join("test_roadside_ground_%d" % Time.get_ticks_usec())
	DirAccess.make_dir_recursive_absolute(dir)
	var p0: Vector3 = route.sample_point(100.0)
	var ground := RoadsideGround.ground_fn(dir, route)
	var before := float(ground.call(p0.x + 5.0, p0.z))
	_check(absf(before - TerrainTiles.nearest_route_alt(route, p0.x + 5.0, p0.z)) < 1e-3, "tuile absente : altitude de la route")
	var t := TerrainTiles.tile_of("near", p0.x + 5.0, p0.z)
	var path := TerrainTiles.tile_path(dir, "near", t.x, t.y)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var heights := PackedFloat32Array()
	heights.resize(TerrainTiles.SAMPLES * TerrainTiles.SAMPLES)
	heights.fill(before - 3.0)
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_buffer(heights.to_byte_array())
	f.close()
	_check(absf(float(ground.call(p0.x + 5.0, p0.z)) - before) < 1e-3, "tuile relue au plus tôt MISSING_RETRY_MS plus tard")
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < RoadsideGround.MISSING_RETRY_MS + 50:
		await process_frame
	var after := float(ground.call(p0.x + 5.0, p0.z))
	_check(absf(after - (before - 3.0)) < 1e-3, "tuile écrite pendant la séance : relue ensuite (%.2f, attendu %.2f)" % [after, before - 3.0])
	DirAccess.remove_absolute(path)
	for d in [path.get_base_dir(), path.get_base_dir().get_base_dir(), dir]:
		DirAccess.remove_absolute(d)
	await process_frame
	print("test_roadside_ground : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
