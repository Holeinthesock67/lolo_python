extends SceneTree

## Tests sans écran de road_clearance.gd et du garde-fou de la chaussée des touffes d'herbe (31 octobre :
## « l'herbe ne doit pas passer par-dessus la route »). Épingle synthétique : deux portions de route à 16 m
## d'axe à axe, où une touffe posée depuis une portion tombait sur l'autre.
## Lancement : godot --headless --path engine --script res://tests/unit/test_road_clearance.gd

const RoadClearance := preload("res://scripts/road_clearance.gd")
const GrassTufts := preload("res://scripts/grass_tufts.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_test_distance()
	_test_hairpin_tufts()
	_test_lead_tufts()
	print("test_road_clearance : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Épingle : montée vers le nord en x = 0 sur 300 m, demi-tour de rayon 8 m, retour vers le sud en x = 16
## (points tous les 5 m d'abscisse curviligne, comme un .world).
static func _hairpin_point(s: float) -> Vector2:
	var arc := PI * 8.0
	if s <= 300.0:
		return Vector2(0.0, -s)
	if s <= 300.0 + arc:
		var a := PI * (1.0 - (s - 300.0) / arc)
		return Vector2(8.0 + 8.0 * cos(a), -300.0 - 8.0 * sin(a))
	return Vector2(16.0, -300.0 + (s - 300.0 - arc))


func _hairpin() -> Variant:
	var ds := 5.0
	var n := int(floor((600.0 + PI * 8.0) / ds)) + 1
	var data := {"version": "1.0", "type": "open", "ds_m": ds, "n": n, "length_m": ds * (n - 1),
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var p := _hairpin_point(i * ds)
		var nxt := _hairpin_point(i * ds + 0.5) - _hairpin_point(maxf(i * ds - 0.5, 0.0))
		data["lat"].append(45.0)
		data["lon"].append(6.0)
		data["alt_m"].append(500.0)
		data["x"].append(p.x)
		data["z"].append(p.y)
		data["grade_pct"].append(0.0)
		data["heading_deg"].append(fposmod(rad_to_deg(atan2(nxt.x, -nxt.y)), 360.0))
	var route = RouteDataScript.new()
	route.load_route_dict(data)
	return route


func _test_distance() -> void:
	var route = _hairpin()
	var rc := RoadClearance.new(route)
	_check(absf(rc.distance(0.0, -100.0)) < 1e-4, "sur l'axe : distance nulle")
	_check(absf(rc.distance(8.0, -100.0) - 8.0) < 1e-3, "entre les deux portions : 8 m de chacune")
	_check(absf(rc.distance(-5.0, -100.0) - 5.0) < 1e-3, "côté extérieur : 5 m")
	_check(rc.is_clear(-5.0, -100.0, 4.0) and not rc.is_clear(13.0, -100.0, 4.0),
		"is_clear voit la portion d'en face (13 m de l'une, 3 m de l'autre)")
	_check(RoadClearance.new(null).is_clear(0.0, 0.0, 10.0), "sans route : toujours dégagé")


func _test_hairpin_tufts() -> void:
	var route = _hairpin()
	var g = GrassTufts.new()
	root.add_child(g)
	g.configure(8000, route, 6.0)
	var rc := RoadClearance.new(route)
	var placed := 0
	var nearest := INF
	var stopped := 0
	for k in range(0, int(ceil(route.length_m / GrassTufts.CHUNK_M)) + 1):
		var stations: PackedVector4Array = g.chunk_stations(k)
		for slot in range(g._per_chunk):
			var xf: Variant = g.tuft_transform(k, slot, stations)
			if xf == null:
				continue
			placed += 1
			var p: Vector3 = (xf as Transform3D).origin
			nearest = minf(nearest, rc.distance(p.x, p.z) - 3.0)
	# Sans le garde-fou : mêmes places, distance mesurée seulement à la portion qui les pose.
	var saved = g._road
	g._road = null
	for k in range(0, int(ceil(route.length_m / GrassTufts.CHUNK_M)) + 1):
		var stations: PackedVector4Array = g.chunk_stations(k)
		for slot in range(g._per_chunk):
			var xf: Variant = g.tuft_transform(k, slot, stations)
			if xf != null and rc.distance((xf as Transform3D).origin.x, (xf as Transform3D).origin.z) < 3.0:
				stopped += 1
	g._road = saved
	g.queue_free()
	_check(stopped > 0, "sans garde-fou, des touffes tombent sur la portion d'en face (%d)" % stopped)
	_check(placed > 0 and nearest >= GrassTufts.ROAD_CLEAR_M - 1e-3,
		"avec garde-fou : %d touffes, la plus proche à %.2f m du bord de la chaussée" % [placed, nearest])


## Demi-tour serré avant l'arrivée : 400 m vers l'est en z = 0, demi-cercle de rayon 5 m vers le nord, 20 m vers
## l'ouest en z = −10, arrivée. L'amorce d'arrivée (200 m vers l'ouest) passe à 10 m d'axe de la portion d'aller,
## au milieu de ses touffes (comme à Almería, 26/11). Points tous les 2 m, route ouverte.
static func _u_turn_point(s: float) -> Vector2:
	var arc := PI * 5.0
	if s <= 400.0:
		return Vector2(s, 0.0)
	if s <= 400.0 + arc:
		var a := (s - 400.0) / 5.0
		return Vector2(400.0 + 5.0 * sin(a), -5.0 + 5.0 * cos(a))
	return Vector2(400.0 - (s - 400.0 - arc), -10.0)


func _u_turn_route() -> Variant:
	var ds := 2.0
	var n := int(floor((420.0 + PI * 5.0) / ds)) + 1
	var data := {"version": "1.0", "type": "open", "ds_m": ds, "n": n, "length_m": ds * (n - 1),
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var p := _u_turn_point(i * ds)
		var nxt := _u_turn_point(i * ds + 0.5) - _u_turn_point(maxf(i * ds - 0.5, 0.0))
		data["lat"].append(45.0)
		data["lon"].append(6.0)
		data["alt_m"].append(500.0)
		data["x"].append(p.x)
		data["z"].append(p.y)
		data["grade_pct"].append(0.0)
		data["heading_deg"].append(fposmod(rad_to_deg(atan2(nxt.x, -nxt.y)), 360.0))
	var route = RouteDataScript.new()
	route.load_route_dict(data)
	return route


## Bancs du monde ouvert du 26/11 (Almería, Funchal) : touffes d'herbe et rochers posés sur l'amorce de chaussée
## que road_builder.gd dessine après l'arrivée et avant le départ. Le garde-fou compte maintenant les amorces.
func _test_lead_tufts() -> void:
	var route = _u_turn_route()
	var rc := RoadClearance.new(route)
	var after: Dictionary = RoadBuilder.axis_sample(route, route.length_m + 0.5 * RoadBuilder.LEAD_OUT_M)
	var before: Dictionary = RoadBuilder.axis_sample(route, -0.5 * RoadBuilder.LEAD_IN_M)
	_check(rc.distance(float(after["x"]), float(after["z"])) < 0.01 and rc.distance(float(before["x"]), float(before["z"])) < 0.01,
		"amorces du départ et de l'arrivée dans l'axe du garde-fou")
	var g = GrassTufts.new()
	root.add_child(g)
	g.configure(8000, route, 6.0)
	var on_lead := 0
	var placed := 0
	# Distance mesurée à la chaussée dessinée : route et amorces, segments droits des amorces comptés à part.
	var leads: Array = RoadBuilder.lead_segments(route)
	for k in range(0, int(ceil(route.length_m / GrassTufts.CHUNK_M)) + 1):
		var stations: PackedVector4Array = g.chunk_stations(k)
		for slot in range(g._per_chunk):
			var xf: Variant = g.tuft_transform(k, slot, stations)
			if xf == null:
				continue
			placed += 1
			var p: Vector3 = (xf as Transform3D).origin
			for seg in leads:
				var q := Vector2(p.x, p.z)
				if q.distance_to(Geometry2D.get_closest_point_to_segment(q, seg[0], seg[1])) < 3.0:
					on_lead += 1
	g.queue_free()
	_check(placed > 0 and on_lead == 0, "demi-tour avant l'arrivée : %d touffes, %d sur l'amorce d'arrivée ou de départ" % [placed, on_lead])
	# Boucle : pas d'amorce, axe inchangé.
	var loop := RoadClearance.new(_hairpin())
	_check(not loop.is_empty(), "route sans amorce dessinée : garde-fou construit")
