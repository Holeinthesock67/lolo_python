extends SceneTree

## Tests sans écran des objets du bord de route `roadside_model.gd` et de leur affichage
## `roadside_props.gd` (Lot P14) : panneaux d'approche et de col, bornes, eau, côté de la route.
## Lancement : godot --headless --path engine --script res://tests/unit/test_roadside_model.gd

const ClimbDetector := preload("res://scripts/climb_detector.gd")
const RoadsideModel := preload("res://scripts/roadside_model.gd")
const RoadsideProps := preload("res://scripts/roadside_props.gd")
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


func _col(s: float) -> float:
	return 7.0 if s >= 2000.0 and s < 10000.0 else 0.0


func _flat(_s: float) -> float:
	return 0.0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_check(RoadsideModel.format_int(1234) == "1 234" and RoadsideModel.format_int(860) == "860"
		and RoadsideModel.format_int(12345678) == "12 345 678" and RoadsideModel.format_dec(7.26, 1) == "7,3"
		and RoadsideModel.format_dec(7.0, 1) == "7,0", "nombres au format français")
	var route = ClimbTest.make_route(16000.0, Callable(self, "_col"))
	var climbs: Array = ClimbDetector.detect(route)
	var pois := [{"id": "n1", "kind": "viewpoint", "x": 10100.0, "y": 860.0, "z": 40.0, "radius_m": 200, "name": "Col de la Croix"}]
	var items: Array = RoadsideModel.items(route, climbs, pois)
	var approach := items.filter(func(it): return it["kind"] == "approach")
	var at := []
	for it in approach:
		at.append(int(round((float(climbs[0]["summit_s"]) - float(it["s"])) / 1000.0)))
	_check(at == [5, 3, 2, 1], "panneaux d'approche à 5, 3, 2 et 1 km du sommet (%s)" % str(at))
	var three: Dictionary = approach[1]
	_check(three["lines"] == ["Sommet à 3 km", "Pente moyenne 7 %"], "textes « Sommet à 3 km » et « Pente moyenne 7 %% » (%s)" % str(three["lines"]))
	var summit := items.filter(func(it): return it["kind"] == "summit")
	_check(summit.size() == 1 and summit[0]["lines"] == ["Col de la Croix", "860 m"],
		"panneau du sommet : nom du point OSM et altitude arrondie au mètre (%s)" % str(summit[0]["lines"]))
	var unnamed: Array = RoadsideModel.items(route, climbs, [])
	_check(unnamed.filter(func(it): return it["kind"] == "summit")[0]["lines"][0] == "Sommet", "sans point nommé : « Sommet »")
	var kms := items.filter(func(it): return it["kind"] == "km")
	_check(kms.size() == 16 and kms[0]["text"] == "km 1", "bornes : une par kilomètre (%d sur 16 km)" % kms.size())

	var loop = ClimbTest.make_route(5000.0, Callable(self, "_flat"))
	loop.type = "loop"
	var seen := {}
	var dup := false
	for it in RoadsideModel.items(loop, [], []):
		var key := int(round(fposmod(float(it["s"]), loop.length_m)))
		dup = dup or seen.has(key)
		seen[key] = true
	_check(not dup and seen.size() == 4, "boucle de 5 km : 4 bornes, aucune en double au départ (%d)" % seen.size())

	# Eau : un ruisseau qui passe sous la route à 3 km, une mare à droite à 4 km
	var water := {"lines": [{"id": "s", "kind": "stream", "width_m": 3.0, "points": [[3000.0, -50.0, 300.0], [3000.0, 50.0, 300.0]]}],
		"areas": [{"id": "p", "kind": "pond", "level_y": 300.0, "outer": [[3970.0, 2.0], [4035.0, 2.0], [4035.0, 20.0], [3970.0, 20.0]]}]}
	var wet: Array = RoadsideModel.items(route, [], [], water)
	var dry := true
	var shifted := []
	for it in wet:
		var p: Vector3 = RoadsideModel.prop_position(route, float(it["s"]))
		dry = dry and not RoadsideModel._in_water(p, water)
		if it["text"] in ["km 3", "km 4"]:
			shifted.append(snappedf(float(it["s"]), 1.0))
	_check(dry and shifted == [3010.0, 4040.0], "aucun objet dans l'eau ni sur le pont : bornes avancées (%s)" % str(shifted))
	var off_road := true
	for it in items:
		var p: Vector3 = RoadsideModel.prop_position(route, float(it["s"]))
		var c: Vector3 = route.sample_point(float(it["s"]))
		off_road = off_road and is_equal_approx(p.distance_to(c), 3.0 + 1.5) and p.z > c.z   # route vers l'est : droite = +z
	_check(off_road, "tous les objets sur le côté droit, à 1,5 m du bord de la chaussée")
	_check(RoadsideModel.paint_marks(climbs).size() == 5, "chiffres peints de 5 à 1 km du sommet")

	# Affichage
	var props = RoadsideProps.new()
	root.add_child(props)
	for k in range(16):
		props.add_chunk(route, k, RoadsideModel.for_chunk(items, k))
	_check(props.prop_count() == items.size(), "tous les objets posés, tronçon par tronçon (%d)" % props.prop_count())
	var sign: Node3D = props._chunks[9][0]
	var lh := RoadsideProps.letter_height_m(sign)
	var face := sign.global_transform.basis.z
	_check(lh >= RoadsideProps.LETTER_HEIGHT_M - 1e-6 and face.dot(Vector3(-1, 0, 0)) > 0.99,
		"panneau lisible à 30 m (lettres de %.2f m), face au cycliste qui arrive" % lh)
	for k in range(16):
		props.remove_chunk(k)
	await process_frame
	_check(props.prop_count() == 0 and props.get_child_count() == 0, "tronçons retirés : plus aucun objet")
	props.queue_free()
	await process_frame
	print("test_roadside_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
