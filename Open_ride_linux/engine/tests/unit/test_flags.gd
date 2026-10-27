extends SceneTree

## Tests sans écran des drapeaux `flags.gd` (Lot P12) : orientation du tissu, drapeau des villages sans
## mât, positions identiques d'un chargement à l'autre.
## Lancement : godot --headless --path engine --script res://tests/unit/test_flags.gd

const Flags := preload("res://scripts/flags.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


func _dir(from_deg: float) -> Vector3:
	var a := deg_to_rad(from_deg + 180.0)
	return Vector3(sin(a), 0.0, -cos(a))


func _points() -> Array:
	return [
		{"id": "n1", "kind": "flag", "x": 100.0, "y": 300.0, "z": 0.0, "radius_m": 150, "name": null},
		{"id": "v1", "kind": "village", "x": 150.0, "y": 300.0, "z": 50.0, "radius_m": 300, "name": "Bourg"},   # mât OSM à 71 m
		{"id": "v2", "kind": "village", "x": 2000.0, "y": 310.0, "z": -400.0, "radius_m": 300, "name": "Hameau"},
		{"id": "c1", "kind": "church_bell", "x": 2010.0, "y": 310.0, "z": -400.0, "radius_m": 300, "name": null},
	]


func _test_orientation() -> void:
	var f = Flags.new()
	root.add_child(f)
	f.set_points(_points())
	var ok := true
	var worst := 0.0
	for from_deg in [0.0, 90.0, 200.0, 315.0]:
		var dir := _dir(from_deg)
		for i in range(300):
			f.update({"dir": dir, "strength": 0.4, "gust": 0.1, "phase": i / 60.0}, 1.0 / 60.0)
		var cloth := Basis(Vector3.UP, f.current_yaw()) * Vector3.RIGHT
		var err := rad_to_deg(acos(clampf(cloth.dot(dir), -1.0, 1.0)))
		worst = maxf(worst, err)
		ok = ok and err <= 15.0
		var node_yaw: float = f._cloth_nodes[0].rotation.y
		ok = ok and is_equal_approx(node_yaw, f.current_yaw())
	_check(ok, "tissu orienté vers où souffle le vent (écart max %.1f°, ≤ 15°), pour 4 directions" % worst)
	f.queue_free()


func _test_villages() -> void:
	var a: Array[Vector3] = Flags.positions_for(_points())
	var b: Array[Vector3] = Flags.positions_for(_points())
	_check(a.size() == 2, "un mât OSM et un drapeau pour le village sans mât (%d drapeaux)" % a.size())
	_check(a == b, "drapeau du village au même endroit à chaque chargement")
	var d := Vector2(a[1].x - 2000.0, a[1].z + 400.0).length()
	_check(d >= Flags.VILLAGE_OFFSET_M.x and d <= Flags.VILLAGE_OFFSET_M.y,
		"drapeau du village à %.1f m du point village" % d)
	var many := []
	for i in range(40):
		many.append({"id": "f%d" % i, "kind": "flag", "x": float(i), "y": 0.0, "z": 0.0, "radius_m": 150, "name": null})
	var f = Flags.new()
	root.add_child(f)
	var n0: int = f.get_child_count()
	f.set_points(many)
	_check(f.visible_count() == Flags.MAX_FLAGS and f.get_child_count() == n0, "40 mâts : 30 drapeaux au plus, aucun nœud créé")
	f.queue_free()


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_orientation()
	_test_villages()
	await process_frame   # nœuds libérés avant la sortie (sinon erreurs du serveur de rendu factice)
	print("test_flags : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
