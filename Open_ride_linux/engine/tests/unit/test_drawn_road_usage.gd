extends SceneTree

## Test d'usage de la chaussée dessinée (lot CD1d) : celui qui empêche un cinquième axe. Sur un monde synthétique qui
## réunit les cas difficiles (demi-tour serré avant l'arrivée : retour à 6 m d'axe de l'aller, amorce d'arrivée qui
## longe l'aller sur 200 m), chaque poseur ne pose rien à moins de son écart de drawn_road.gd.
## La liste des scripts qui posent quelque chose au bord de la route est tenue ici : un script qui pose à côté de la
## route (décalage latéral `right *` à partir d'un point de la route) sans être dans POSEURS ni dans HORS_DECOR fait
## échouer le test.
## Lancement : godot --headless --path engine --script res://tests/unit/test_drawn_road_usage.gd

const DrawnRoad := preload("res://scripts/drawn_road.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const GrassTufts := preload("res://scripts/grass_tufts.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const StreetLights := preload("res://scripts/street_lights.gd")
const RoadsideModel := preload("res://scripts/roadside_model.gd")
const CrowdModel := preload("res://scripts/crowd_model.gd")
const PassersbyModel := preload("res://scripts/passersby_model.gd")

const HALF_M := 3.0
const TOL_M := 1e-3

## Poseurs contrôlés par ce test ou par un test qui leur est propre (test_grass_tufts, test_ground_details,
## test_volcano_fx, test_forest_impostors, test_fauna_placer : même chaussée, via road_clearance.gd ou _road_buckets).
const POSEURS := ["grass_tufts.gd", "ground_details.gd", "volcano_fx.gd", "vegetation_placer.gd", "forest_impostors.gd",
	"fauna_placer.gd", "osm_streamer.gd", "street_lights.gd", "roadside_model.gd", "crowd_model.gd", "passersby_model.gd"]
## Scripts qui calculent un point à côté de la route sans poser de décor fixe : usagers de la chaussée (règle de
## road_rules.gd et road_space.py), ruban lui-même, marques peintes SUR la chaussée, caméra et pose du cycliste.
const HORS_DECOR := ["main.gd", "rider_pose.gd", "road_builder.gd", "road_cyclists_model.gd", "route_data.gd",
	"segment_markers.gd", "sky_traffic_model.gd", "traffic_model.gd"]

var _failures := 0
var _checked := 0
var _road = null


func _init() -> void:
	var route = _tight_u_turn()
	_road = DrawnRoad.shared(route)
	_test_registry()
	_test_grass(route)
	_test_trees(route)
	_test_street_lights(route)
	_test_roadside(route)
	_test_crowd(route)
	_test_passersby(route)
	print("test_drawn_road_usage : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## 400 m vers l'est en z = 0, demi-cercle de rayon 3 m vers le nord, 40 m vers l'ouest en z = −6, arrivée ; l'amorce
## d'arrivée (200 m vers l'ouest) longe l'aller à 6 m d'axe. Points tous les 2 m, route ouverte, montée régulière.
static func _point(s: float) -> Vector2:
	var arc := PI * 3.0
	if s <= 400.0:
		return Vector2(s, 0.0)
	if s <= 400.0 + arc:
		var a := (s - 400.0) / 3.0
		return Vector2(400.0 + 3.0 * sin(a), -3.0 + 3.0 * cos(a))
	return Vector2(400.0 - (s - 400.0 - arc), -6.0)


func _tight_u_turn() -> Variant:
	var ds := 2.0
	var n := int(floor((440.0 + PI * 3.0) / ds)) + 1
	var data := {"version": "1.0", "type": "open", "ds_m": ds, "n": n, "length_m": ds * (n - 1),
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var p := _point(i * ds)
		var nxt := _point(i * ds + 0.5) - _point(maxf(i * ds - 0.5, 0.0))
		data["lat"].append(45.0)
		data["lon"].append(6.0)
		data["alt_m"].append(500.0 + i * ds * 0.05)
		data["x"].append(p.x)
		data["z"].append(p.y)
		data["grade_pct"].append(5.0)
		data["heading_deg"].append(fposmod(rad_to_deg(atan2(nxt.x, -nxt.y)), 360.0))
	var route = RouteDataScript.new()
	route.load_route_dict(data)
	return route


## Plus petite distance des points `pts` (Vector3) à la chaussée dessinée.
func _closest(pts: Array) -> float:
	var best := INF
	for p in pts:
		best = minf(best, _road.distance(p.x, p.z))
	return best


func _test_registry() -> void:
	var missing := []
	var dir := DirAccess.open("res://scripts")
	for f in dir.get_files():
		if not f.ends_with(".gd"):
			continue
		var src := FileAccess.get_file_as_string("res://scripts/" + f)
		var lateral := src.contains("right * ") or src.contains("* right")
		var from_route := src.contains("sample(") or src.contains("sample_point(")
		if lateral and from_route and not (f in POSEURS) and not (f in HORS_DECOR):
			missing.append(f)
	_check(missing.is_empty(), "poseurs : tous déclarés (nouveaux sans entrée : %s)" % str(missing))


func _test_grass(route) -> void:
	var g = GrassTufts.new()
	root.add_child(g)
	g.configure(8000, route, HALF_M * 2.0)
	var pts := []
	for k in range(0, int(ceil(route.length_m / GrassTufts.CHUNK_M)) + 1):
		var stations: PackedVector4Array = g.chunk_stations(k)
		for slot in range(g._per_chunk):
			var xf: Variant = g.tuft_transform(k, slot, stations)
			if xf != null:
				pts.append((xf as Transform3D).origin)
	g.queue_free()
	var d := _closest(pts)
	_check(pts.size() > 0 and d >= HALF_M + GrassTufts.ROAD_CLEAR_M - TOL_M,
		"herbe : %d touffes, la plus proche à %.2f m de l'axe" % [pts.size(), d])


func _test_trees(route) -> void:
	var placer = VegetationPlacer.new()
	var flat := func(_x: float, _z: float) -> float: return 500.0
	var pts := []
	for tz in [-1, 0]:
		var trees: PackedVector4Array = placer.place_tile(0, tz, 1000.0, flat, route, {})
		for t in trees:
			pts.append(Vector3(t.x, t.y, t.z))
	var corridor := VegetationPlacer.DEFAULT_ROAD_WIDTH_M * 0.5 + VegetationPlacer.ROAD_MARGIN_M
	var d := _closest(pts)
	_check(pts.size() > 0 and d >= corridor - TOL_M, "arbres : %d, le plus proche à %.2f m de l'axe" % [pts.size(), d])


func _test_street_lights(route) -> void:
	# Village le long de l'aller et du retour : candélabres partout où un bâtiment est proche.
	var buildings := []
	for x in range(150, 420, 20):
		for z in [12.0, -18.0]:
			var pts := PackedVector2Array([Vector2(x, z), Vector2(x + 8.0, z), Vector2(x + 8.0, z + 6.0), Vector2(x, z + 6.0)])
			buildings.append({"points": pts, "rect": Rect2(x, z, 8.0, 6.0)})
	var lamps := []
	var posts := []
	for k in range(0, int(ceil(route.length_m / StreetLights.CHUNK_M)) + 1):
		for it in StreetLights.positions(route, k, buildings, HALF_M * 2.0):
			lamps.append(it["pos"])
		for it in StreetLights.post_positions(route, k, [], HALF_M * 2.0):
			posts.append(it["pos"])
	var dl := _closest(lamps)
	var dp := _closest(posts)
	_check(lamps.size() > 0 and dl >= HALF_M + DrawnRoad.EDGE_GUARD_M - TOL_M,
		"candélabres : %d, le plus proche à %.2f m de l'axe" % [lamps.size(), dl])
	_check(posts.size() > 0 and dp >= HALF_M + DrawnRoad.EDGE_GUARD_M - TOL_M,
		"balises : %d, la plus proche à %.2f m de l'axe" % [posts.size(), dp])


func _climb(route) -> Dictionary:
	return {"start_s": 0.0, "summit_s": route.length_m - 1.0, "length_m": route.length_m - 1.0,
		"summit_alt_m": 500.0 + route.length_m * 0.05, "dir": 1}


func _test_roadside(route) -> void:
	var pts := []
	for it in RoadsideModel.items(route, [_climb(route)], [], {}, HALF_M * 2.0):
		if int(it["side"]) != 0 and it["kind"] in ["summit", "approach", "km", "lantern"]:
			pts.append(RoadsideModel.prop_position(route, float(it["s"]), HALF_M * 2.0, int(it["side"])))
	var d := _closest(pts)
	_check(pts.size() > 0 and d >= HALF_M + DrawnRoad.EDGE_GUARD_M - TOL_M,
		"panneaux et bornes : %d, le plus proche à %.2f m de l'axe" % [pts.size(), d])


func _test_crowd(route) -> void:
	var crowd = CrowdModel.new()
	crowd.configure(route, [_climb(route)], {}, true, 7, HALF_M * 2.0)
	var pts: Array = crowd.spectators.map(func(sp): return sp["pos"])
	var d := _closest(pts)
	_check(pts.size() > 0 and d >= HALF_M + DrawnRoad.EDGE_GUARD_M - TOL_M,
		"spectateurs : %d, le plus proche à %.2f m de l'axe" % [pts.size(), d])


func _test_passersby(route) -> void:
	var people = PassersbyModel.new()
	var buildings := [{"outer": [[200.0, 10.0], [210.0, 10.0], [210.0, 16.0], [200.0, 16.0]]}]
	people.configure(route, buildings, {}, 3, HALF_M * 2.0)
	var pts := []
	for p in people.people:
		for q in p["path"]:
			pts.append(q)
	var d := _closest(pts)
	_check(d >= HALF_M + DrawnRoad.EDGE_GUARD_M - TOL_M,
		"passants : %d personnes, %d points de chemin, le plus proche à %.2f m de l'axe" % [people.people.size(), pts.size(), d])
