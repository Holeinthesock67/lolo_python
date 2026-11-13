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
	_check(three["name"] == "Col de la Croix" and three["km"] == 3 and three["pct"] == 7,
		"panneau d'approche : nom du sommet, distance et pente pour la mise en page (%s)" % str(three))
	# Mise en page du panneau d'approche : agrandie, aucun texte sous LETTER_HEIGHT_M, pente en couleur
	var lay: Dictionary = RoadsideProps.approach_layout(three)
	var smallest := 1.0
	for t in lay["texts"]:
		smallest = minf(smallest, float(t["letter"]))
	_check(lay["w"] >= RoadsideProps.APPROACH_MIN_W * RoadsideProps.APPROACH_SCALE - 1e-6 and smallest >= RoadsideProps.LETTER_HEIGHT_M - 1e-6
		and lay["texts"][0]["text"] == "3 km", "panneau d'approche : %.2f × %.2f m, lettres de %.3f m au moins" % [lay["w"], lay["h"], smallest])
	_check(RoadsideProps.slope_color(2) != RoadsideProps.slope_color(5) and RoadsideProps.slope_color(5) != RoadsideProps.slope_color(8)
		and RoadsideProps.slope_color(8) != RoadsideProps.slope_color(12) and lay["layers"][2]["color"] == RoadsideProps.slope_color(7),
		"pente moyenne : vert, bleu, rouge, noir")
	var summit := items.filter(func(it): return it["kind"] == "summit")
	_check(summit.size() == 2 and summit[0]["lines"] == ["Col de la Croix", "860 m"] and summit[1]["lines"] == summit[0]["lines"],
		"panneau du sommet : nom du point OSM et altitude arrondie au mètre (%s)" % str(summit[0]["lines"]))
	_check(int(summit[0]["side"]) == 1 and int(summit[1]["side"]) == -1,
		"panneau du sommet des deux côtés, un par sens de marche (demi-tour N17)")
	_check(items.filter(func(it): return it["kind"] != "summit" and int(it["side"]) != 1).is_empty(),
		"approche et bornes : à droite seulement")
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
		var p: Vector3 = RoadsideModel.prop_position(route, float(it["s"]), 6.0, int(it["side"]))
		var c: Vector3 = route.sample_point(float(it["s"]))
		# route vers l'est : droite = +z
		off_road = off_road and is_equal_approx(p.distance_to(c), 3.0 + 1.5) and (p.z > c.z) == (int(it["side"]) == 1)
	_check(off_road, "objets du côté de leur `side`, à 1,5 m du bord de la chaussée")
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
	var tops: Array = []
	for k in range(16):
		for n in props._chunks.get(k, []):
			if str((n as Node3D).name).begins_with("summit"):
				tops.append(n)
	var to_west: bool = tops.size() == 2 and (tops[0] as Node3D).global_transform.basis.z.dot(Vector3(-1, 0, 0)) > 0.99
	var to_east: bool = tops.size() == 2 and (tops[1] as Node3D).global_transform.basis.z.dot(Vector3(1, 0, 0)) > 0.99 \
		and (tops[1] as Node3D).global_position.z < route.sample_point(float(summit[1]["s"])).z
	_check(to_west and to_east, "panneau du sommet à gauche face au cycliste qui roule à rebours (%d panneaux)" % tops.size())
	var borne: Node3D = null
	for n in props._chunks.get(1, []):
		if str((n as Node3D).name).begins_with("km"):
			borne = n
	var faces := {}
	for c in borne.get_children():
		if c is Label3D:
			faces[signf((c as Label3D).global_transform.basis.z.dot(borne.global_transform.basis.z))] = true
	_check(borne != null and faces.has(1.0) and faces.has(-1.0),
		"borne kilométrique numérotée sur ses deux faces (%s)" % str(faces.keys()))
	for k in range(16):
		props.remove_chunk(k)
	await process_frame
	_check(props.prop_count() == 0 and props.get_child_count() == 0, "tronçons retirés : plus aucun objet")
	_test_japan(route, climbs, props)
	_test_guardrails(props)
	for k in range(16):
		props.remove_chunk(k)
	await process_frame
	_check(props.prop_count() == 0 and props.get_child_count() == 0, "tronçons retirés : plus aucun objet")
	props.queue_free()
	await process_frame
	print("test_roadside_model : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)


## Japon (lot JP5) : torii au pied des montées du biome japan, lanternes de part et d'autre du sommet.
func _test_japan(route, climbs: Array, props) -> void:
	var plain: Array = RoadsideModel.items(route, climbs, [], {}, 6.0)
	_check(plain.filter(func(it): return it["kind"] in ["torii", "lantern"]).is_empty(), "hors du Japon : ni torii ni lanterne")
	var other := func(_x: float, _z: float) -> String: return "temperate_forest"
	_check(RoadsideModel.items(route, climbs, [], {}, 6.0, other).filter(func(it): return it["kind"] == "torii").is_empty(),
		"biome tempéré : pas de torii")
	var japan := func(_x: float, _z: float) -> String: return "japan"
	var items: Array = RoadsideModel.items(route, climbs, [], {}, 6.0, japan)
	var torii := items.filter(func(it): return it["kind"] == "torii")
	var lanterns := items.filter(func(it): return it["kind"] == "lantern")
	_check(torii.size() == climbs.size() and int(torii[0]["side"]) == 0
		and absf(float(torii[0]["s"]) - float(climbs[0]["start_s"]) - RoadsideModel.TORII_AFTER_START_M) < 1.0,
		"biome japan : un torii au pied de chaque montée, sur l'axe de la route (%d)" % torii.size())
	_check(lanterns.size() == 2 * climbs.size() and int(lanterns[0]["side"]) != int(lanterns[1]["side"])
		and float(lanterns[0]["s"]) > float(climbs[0]["summit_s"]), "deux lanternes de pierre après le sommet, une de chaque côté")
	var c: Vector3 = route.sample_point(float(torii[0]["s"]))
	_check(RoadsideModel.prop_position(route, float(torii[0]["s"]), 6.0, 0).is_equal_approx(c), "torii centré sur la chaussée")
	props.road_width_m = 6.0
	for k in range(16):
		props.add_chunk(route, k, RoadsideModel.for_chunk(items, k))
	var gate: Node3D = null
	for k in range(16):
		for n in props._chunks.get(k, []):
			if str((n as Node3D).name).begins_with("torii"):
				gate = n
	var span := 0.0
	var top := 0.0
	if gate != null:
		for mi in gate.get_children():
			if mi is MeshInstance3D:
				var bb: AABB = (mi as MeshInstance3D).mesh.get_aabb()
				span = maxf(span, bb.size.x)
				top = maxf(top, bb.end.y)
	_check(gate != null and span > 6.0 + 2.0 * RoadsideProps.TORII_MARGIN_M and top >= 7.0,
		"torii par-dessus la route : %.1f m de large, %.1f m de haut" % [span, top])


## Route plate avec un virage à droite de 90° et de `radius` m qui commence à `bend_s` (pas de 10 m).
static func _bend_route(length_m: float, bend_s: float, radius: float):
	var ds := 10.0
	var n := int(length_m / ds) + 1
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	var p := Vector2.ZERO
	var bend_len := PI * 0.5 * radius
	for i in range(n):
		var s := i * ds
		var t := clampf((s - bend_s) / bend_len, 0.0, 1.0)
		var h := 90.0 + 90.0 * t
		if i > 0:
			var hm := deg_to_rad(90.0 + 90.0 * clampf((s - ds * 0.5 - bend_s) / bend_len, 0.0, 1.0))
			p += Vector2(sin(hm), -cos(hm)) * ds
		cols["lat"].append(35.2)
		cols["lon"].append(139.0)
		cols["alt_m"].append(500.0)
		cols["x"].append(p.x)
		cols["z"].append(p.y)
		cols["grade_pct"].append(0.0)
		cols["heading_deg"].append(h)
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": (n - 1) * ds, "type": "open"}
	d.merge(cols)
	var r = ClimbTest.RouteDataScript.new()
	r.load_route_dict(d)
	return r


## Glissières (lot JP8) : extérieur des virages serrés du biome japan seulement, coupées aux tronçons.
func _test_guardrails(props) -> void:
	var japan := func(_x: float, _z: float) -> String: return "japan"
	var other := func(_x: float, _z: float) -> String: return "temperate_forest"
	var straight = ClimbTest.make_route(3000.0, Callable(self, "_flat"))
	_check(RoadsideModel.guardrails(straight, japan).is_empty(), "ligne droite au Japon : pas de glissière")
	var bend = _bend_route(3000.0, 960.0, 50.0)
	_check(RoadsideModel.guardrails(bend, other).is_empty() and RoadsideModel.guardrails(bend, Callable()).is_empty(),
		"virage hors du Japon : pas de glissière")
	var rails: Array = RoadsideModel.guardrails(bend, japan)
	var ok := not rails.is_empty()
	var first := INF
	var last := -INF
	for r in rails:
		ok = ok and int(r["side"]) == -1 and r["kind"] == "guardrail"
		ok = ok and int(floor(float(r["s"]) / 1000.0)) == int(floor((float(r["s_end"]) - 0.01) / 1000.0))
		first = minf(first, float(r["s"]))
		last = maxf(last, float(r["s_end"]))
	var bend_end := 960.0 + PI * 0.5 * 50.0
	_check(ok and rails.size() == 2 and first <= 960.0 and first > 900.0 and last >= bend_end and last < bend_end + 60.0,
		"virage à droite de 50 m : glissière à gauche de %.0f à %.0f m, coupée à 1 km (%d morceaux)" % [first, last, rails.size()])
	_check(RoadsideModel.items(bend, [], [], {}, 6.0, japan).filter(func(it): return it["kind"] == "guardrail").size() == rails.size(),
		"glissières parmi les objets du bord de route")
	var mesh: ArrayMesh = RoadsideProps.guardrail_mesh(bend, float(rails[0]["s"]), float(rails[0]["s_end"]), -1, 6.0)
	var bb := mesh.get_aabb()
	var mid: Vector3 = bend.sample_point(float(rails[0]["s"]))
	var steps := int(ceil((float(rails[0]["s_end"]) - float(rails[0]["s"])) / RoadsideProps.GUARDRAIL_STEP_M))
	var posts := steps / RoadsideProps.GUARDRAIL_POST_EVERY + 1
	_check(mesh.surface_get_array_index_len(0) == (steps * RoadsideProps.GUARDRAIL_BANDS.size() * 4 + posts * 12) * 3,
		"glissière : lisse en %d bandes doubles faces et %d poteaux" % [RoadsideProps.GUARDRAIL_BANDS.size(), posts])
	_check(bb.end.y - mid.y > 0.85 and bb.end.y - mid.y < 1.1,
		"glissière de %.2f m de haut au-dessus de la route" % (bb.end.y - mid.y))
	props.road_width_m = 6.0
	props.add_chunk(bend, 0, RoadsideModel.for_chunk(rails, 0))
	var names := []
	for nd in props._chunks.get(0, []):
		names.append(str((nd as Node3D).name))
	_check(names.size() == 1 and names[0].begins_with("guardrail"), "glissière posée dans le tronçon 0 (%s)" % str(names))
	props.remove_chunk(0)
