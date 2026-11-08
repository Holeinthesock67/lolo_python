extends SceneTree

## Tests sans écran de la piste relevée (série VD, lot VD4) : une seule coupe générique (road_builder.gd), la route
## classique étant le cas bank = 0 ; profil de piste (côte d'azur à plat, piste relevée, balustrade) ; bouclage sans
## trou ; coureurs posés sur la pente (route_data.bank_right) ; vue de côté au-dessus de la piste (camera_views.gd).
## Lancement : godot --headless --path engine --script res://tests/unit/test_track_ribbon.gd

const RoadBuilder := preload("res://scripts/road_builder.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const CameraViews := preload("res://scripts/camera_views.gd")

const RADIUS := 23.0
const BANK := 42.0

var _failures := 0
var _checked := 0


func _init() -> void:
	_test_road_unchanged()
	_test_track()
	print("test_track_ribbon : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Boucle circulaire de 2πR, virages à gauche, relèvement constant `bank`, avec ou sans colonne bank_deg.
func _circle(bank_column: bool, bank: float = BANK) -> Dictionary:
	var length := 2.0 * PI * RADIUS
	var ds := 1.0
	var n := int(ceil(length / ds)) + 1
	var d := {"version": "1.0", "ds_m": ds, "n": n, "length_m": length, "type": "loop", "lat": [], "lon": [],
		"alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	if bank_column:
		d["bank_deg"] = []
	for i in range(n):
		var s := minf(i * ds, length)
		var a := s / RADIUS          # angle tourné, virage à gauche : le cap baisse
		var h := fposmod(90.0 - rad_to_deg(a), 360.0)
		# Départ vers l'est (cap 90°) ; centre au nord (−z) du départ.
		d["x"].append(RADIUS * sin(a))
		d["z"].append(-RADIUS + RADIUS * cos(a))
		d["alt_m"].append(200.0)
		d["lat"].append(46.0)
		d["lon"].append(2.0)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(h)
		if bank_column:
			d["bank_deg"].append(bank)
	d["x"][n - 1] = 0.0
	d["z"][n - 1] = 0.0
	return d


func _venue() -> Dictionary:
	return {"version": "1.0", "kind": "velodrome", "track_width_m": 7.0, "apron_width_m": 1.0, "safety_width_m": 4.0,
		"lines": [{"id": "measure", "offset_m": 0.2}, {"id": "sprinters", "offset_m": 0.85},
			{"id": "stayers", "offset_m": 2.45}], "marks": [], "geometry": {}}


func _test_road_unchanged() -> void:
	var route = RouteDataScript.new()
	if not route.load_world_dir("res://demo/demo.world"):
		_check(false, "demo.world chargé : " + route.load_error)
		return
	var before := RoadBuilder.build_chunk_arrays(route, 0)
	var zeros := []
	for i in range(route.n):
		zeros.append(0.0)
	route.bank_deg = PackedFloat64Array(zeros)
	var after := RoadBuilder.build_chunk_arrays(route, 0)
	_check(before[Mesh.ARRAY_VERTEX] == after[Mesh.ARRAY_VERTEX] and before[Mesh.ARRAY_NORMAL] == after[Mesh.ARRAY_NORMAL]
		and before[Mesh.ARRAY_TEX_UV] == after[Mesh.ARRAY_TEX_UV], "route sans relèvement : sommets, normales et UV inchangés (bank = 0)")
	_check(not RoadBuilder.is_track(route), "demo.world n'est pas une piste")
	_check(RoadBuilder.section_s(route, 0)[1] == RoadBuilder.SECTION_STEP_M, "route : une coupe tous les 2 m")


func _test_track() -> void:
	# Relèvement d'une route sans couche venue : coupe de route tournée, bord droit plus haut.
	var banked = RouteDataScript.new()
	_check(banked.load_route_dict(_circle(true)), "boucle relevée chargée : " + banked.load_error)
	var arr := RoadBuilder.build_chunk_arrays(banked, 0)
	var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
	var rise := v[3].y - v[2].y
	_check(absf(rise - RoadBuilder.ROAD_WIDTH_M * sin(deg_to_rad(BANK))) < 1e-3,
		"coupe relevée de 42° : bord droit %.2f m plus haut" % rise)

	# Piste : couche venue.
	var track = RouteDataScript.new()
	track.load_route_dict(_circle(true))
	track.venue = _venue()
	_check(track.is_track() and RoadBuilder.is_track(track), "couche venue : piste reconnue")
	_check(RoadBuilder.section_s(track, 0)[1] == RoadBuilder.TRACK_SECTION_STEP_M, "piste : une coupe tous les 1 m")
	arr = RoadBuilder.build_chunk_arrays(track, 0)
	v = arr[Mesh.ARRAY_VERTEX]
	var uv: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV]
	var center: Vector3 = track.sample_point(0.0)
	var sb := sin(deg_to_rad(BANK))
	_check(absf(v[2].y - (center.y - 0.2 * sb)) < 1e-3 and absf(v[3].y - (center.y + 6.8 * sb)) < 1e-3,
		"bord intérieur 0,2 m sous la ligne de mesure, bord extérieur 6,8 m au-dessus, sur la pente")
	_check(absf(v[0].y - v[1].y) < 1e-6 and absf(Vector2(v[0].x - v[1].x, v[0].z - v[1].z).length() - 5.0) < 1e-3,
		"côte d'azur et zone de sécurité à plat, 5 m vers l'intérieur")
	_check(absf(v[5].y - v[4].y - RoadBuilder.TRACK_BARRIER_H) < 1e-6, "balustrade verticale de 1 m")
	_check(uv[1].x == 0.0 and uv[3].x == 7.0 and uv[0].x == -5.0, "UV.x en m depuis le bord intérieur de la piste")
	var cuts := v.size() / RoadBuilder.VERTS_PER_SECTION
	var last := (cuts - 1) * RoadBuilder.VERTS_PER_SECTION
	var gap := 0.0
	for c in range(RoadBuilder.VERTS_PER_SECTION):
		gap = maxf(gap, (v[last + c] - v[c]).length())
	_check(gap < 1e-3, "bouclage : dernière coupe sur la première (écart %.5f m)" % gap)
	_check(RoadBuilder.build_skirt_arrays(arr).size() > 0, "les talus restent calculables (le streamer ne les pose pas)")

	# Coureurs sur la pente.
	var h := deg_to_rad(track.sample_heading_deg(0.0))
	var right: Vector3 = track.bank_right(0.0, h)
	_check(absf(right.y - sb) < 1e-6 and absf(right.length() - 1.0) < 1e-6, "bank_right relevé de 42°")
	var flat = RouteDataScript.new()
	flat.load_route_dict(_circle(false))
	_check(flat.bank_right(0.0, h) == Vector3(cos(h), 0.0, sin(h)), "sans relèvement : droite horizontale d'avant")

	# Vue de côté au-dessus de la piste.
	var views := CameraViews.new()
	views.set_view("side")
	var pos: Vector3 = track.sample_point(0.0) + right * 0.65
	var eye := views.goal(pos, h, 0.0, deg_to_rad(BANK)).origin
	var surface_y: float = center.y + right.y * (eye - center).dot(Vector3(cos(h), 0.0, sin(h))) / cos(deg_to_rad(BANK))
	_check(eye.y > surface_y + 0.5, "vue de côté au-dessus de la piste relevée (%.2f m au-dessus)" % (eye.y - surface_y))
	var eye0 := views.goal(pos, h, 0.0).origin
	_check(absf(eye0.y - pos.y - CameraViews.SIDE_HEIGHT_M) < 1e-4, "vue de côté sur une route : pose d'avant (%.4f m)" % (eye0.y - pos.y))
