extends SceneTree

## Tests sans écran de la salle couverte du vélodrome (série VD, lot VD5, velodrome_hall.gd) : salle fermée
## autour de la piste, tribunes derrière la balustrade, toit au-dessus de tout, public du préréglage et
## sous-ensemble stable, ambiance intérieure gardée puis rendue, rien sur une route.
## Lancement : godot --headless --path engine --script res://tests/unit/test_velodrome_hall.gd

const Hall := preload("res://scripts/velodrome_hall.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")

const RADIUS := 23.0
const BANK := 42.0

var _failures := 0
var _checked := 0


func _init() -> void:
	var track = _track()
	_test_geometry(track)
	_test_crowd(track)
	_test_ambience()
	_test_road()
	print("test_velodrome_hall : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Boucle circulaire relevée de 42° avec une couche venue, virages à gauche.
func _track():
	var length := 2.0 * PI * RADIUS
	var n := int(ceil(length)) + 1
	var d := {"version": "1.0", "ds_m": 1.0, "n": n, "length_m": length, "type": "loop", "lat": [], "lon": [],
		"alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": [], "bank_deg": []}
	for i in range(n):
		var a := minf(i, length) / RADIUS
		d["x"].append(RADIUS * sin(a))
		d["z"].append(-RADIUS + RADIUS * cos(a))
		d["alt_m"].append(200.0)
		d["lat"].append(46.0)
		d["lon"].append(2.0)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(fposmod(90.0 - rad_to_deg(a), 360.0))
		d["bank_deg"].append(BANK)
	d["x"][n - 1] = 0.0
	d["z"][n - 1] = 0.0
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	r.venue = {"version": "1.0", "kind": "velodrome", "track_width_m": 7.0, "apron_width_m": 1.0, "safety_width_m": 4.0,
		"lines": [{"id": "measure", "offset_m": 0.2}], "marks": [], "geometry": {}}
	return r


func _test_geometry(track) -> void:
	var arr := Hall.build_arrays(track)
	var info: Dictionary = arr["info"]
	var center: Vector3 = info["center"]
	_check(Vector2(center.x, center.z - (-RADIUS)).length() < 0.5, "centre de la salle au centre de l'anneau")
	var ol: Array = info["outline"]
	var o: Dictionary = ol[0]
	_check(absf(float(o["barrier_d"]) - 6.8 * cos(deg_to_rad(BANK))) < 1e-3
		and absf(float(o["barrier_y"]) - (200.0 + 6.8 * sin(deg_to_rad(BANK)) + 1.0)) < 0.05,
		"contour : haut de la balustrade à la place dessinée par road_builder.gd")
	_check(Vector3(o["out"]).dot(Vector3(o["p"]) - center) > 0.0, "contour : « extérieur » tourné vers l'extérieur de l'anneau")
	var pr := Hall.stand_profile(o)
	var rising := true
	for k in range(1, pr.size()):
		rising = rising and float(pr[k][0]) >= float(pr[k - 1][0]) and float(pr[k][1]) >= float(pr[k - 1][1])
	_check(rising and pr.size() == 2 + 2 * Hall.ROWS + 1, "tribunes : %d gradins qui montent en s'éloignant de la piste" % Hall.ROWS)
	var stands: PackedVector3Array = arr["stands"][Mesh.ARRAY_VERTEX]
	var min_d := INF
	for p in stands:
		min_d = minf(min_d, Vector2(p.x - center.x, p.z - center.z).length())
	_check(min_d >= RADIUS + 6.8 * cos(deg_to_rad(BANK)) - 0.05, "tribunes toutes derrière la balustrade")
	var roof: PackedVector3Array = arr["roof"][Mesh.ARRAY_VERTEX]
	var walls: PackedVector3Array = arr["walls"][Mesh.ARRAY_VERTEX]
	var top_stand := -INF
	for p in stands:
		top_stand = maxf(top_stand, p.y)
	var low_roof := INF
	for p in roof:
		low_roof = minf(low_roof, p.y)
	_check(low_roof >= top_stand + Hall.WALL_ABOVE_M - 1e-3, "toit au-dessus du dernier gradin (%.1f m)" % (low_roof - top_stand))
	_check(absf(float(info["roof_top"]) - float(info["wall_top"]) - Hall.ROOF_RISE_M) < 1e-3, "coupole de %.0f m de flèche" % Hall.ROOF_RISE_M)
	var wall_low := INF
	for p in walls:
		wall_low = minf(wall_low, p.y)
	_check(wall_low < float(info["floor_y"]), "mur jusque sous la pelouse : salle fermée")
	var ring: Array = info["wall_ring"]
	var gap := 0.0
	for i in range(ring.size()):
		gap = maxf(gap, (ring[(i + 1) % ring.size()] - ring[i]).length())
	_check(gap < 4.0, "mur fermé sur tout le tour (écart maximal %.2f m entre deux points)" % gap)
	var floor_n: PackedVector3Array = arr["floor"][Mesh.ARRAY_NORMAL]
	var up := true
	for nn in floor_n:
		up = up and nn.y > 0.99
	_check(floor_n.size() > 0 and up, "pelouse centrale horizontale, normales vers le haut")
	var lights: PackedVector3Array = arr["lights"][Mesh.ARRAY_VERTEX]
	_check(lights.size() == ol.size() * Hall.RAMPS.size() * 6, "trois rampes d'éclairage sur tout le tour")


func _test_crowd(track) -> void:
	var seats := Hall.seats(track)
	# Chaque gradin, plus long que la piste, a une place tous les SEAT_PITCH_M (la piste de 250 m en a ~9 000).
	_check(seats.size() >= Hall.ROWS * track.length_m / Hall.SEAT_PITCH_M, "%d places sur %d gradins" % [seats.size(), Hall.ROWS])
	var t: Transform3D = seats[0]
	var to_track := -t.basis.z
	var radial := Vector3(t.origin.x, 0.0, t.origin.z + RADIUS).normalized()
	_check(to_track.dot(radial) < -0.9, "spectateurs tournés vers la piste")
	var low := Hall.occupied(seats.size(), QualityPresets.velodrome_crowd("low"))
	var med := Hall.occupied(seats.size(), QualityPresets.velodrome_crowd("medium"))
	var high := Hall.occupied(seats.size(), QualityPresets.velodrome_crowd("high"))
	var want := func(q: String) -> float: return minf(QualityPresets.velodrome_crowd(q), seats.size())
	_check(absf(low.size() - want.call("low")) < 0.1 * want.call("low") and absf(med.size() - want.call("medium")) < 0.08 * want.call("medium")
		and absf(high.size() - want.call("high")) < 0.06 * want.call("high"),
		"public : %d, %d, %d personnes en low, medium, high" % [low.size(), med.size(), high.size()])
	var subset := true
	for i in low:
		subset = subset and med.has(i)
	_check(subset, "place prise en low toujours prise en medium (sous-ensemble stable)")
	var hall := Hall.new()
	hall.build(track, "medium")
	_check(hall.built and hall.crowd_count == med.size() and hall.get_node_or_null("Crowd") != null, "salle posée, public de medium")
	var shadowless := true
	for c in hall.get_children():
		if c is GeometryInstance3D:
			shadowless = shadowless and (c as GeometryInstance3D).cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_check(shadowless, "salle et public sans ombre portée (ombres : coureurs seulement)")
	hall.set_quality("high")
	_check(hall.crowd_count == high.size(), "préréglage high : public de high, sans reconstruire la salle")
	hall.free()


func _test_ambience() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.fog_enabled = true
	var sun := DirectionalLight3D.new()
	sun.light_energy = 1.3
	var basis0 := sun.basis
	var hall := Hall.new()
	hall.apply_indoor(env, sun)
	_check(env.background_mode == Environment.BG_COLOR and not env.fog_enabled and not env.volumetric_fog_enabled
		and env.ambient_light_source == Environment.AMBIENT_SOURCE_COLOR, "salle : fond uni, sans ciel ni brouillard")
	_check((-sun.global_transform.basis.z).y < -0.8 if sun.is_inside_tree() else (-sun.basis.z).y < -0.8, "lumière zénithale")
	hall.apply_indoor(env, sun)   # rappel après un changement de préréglage : l'état d'avant reste celui d'origine
	hall.restore(env, sun)
	_check(env.background_mode == Environment.BG_SKY and env.fog_enabled and is_equal_approx(sun.light_energy, 1.3)
		and sun.basis.is_equal_approx(basis0) and not hall.is_indoor(), "retour sur route : ciel, brouillard et soleil d'avant")
	hall.free()
	sun.free()


func _test_road() -> void:
	var route = RouteDataScript.new()
	route.load_world_dir("res://demo/demo.world")
	var hall := Hall.new()
	hall.build(route, "high")
	_check(not hall.built and hall.get_child_count() == 0, "route : pas de salle")
	hall.free()
