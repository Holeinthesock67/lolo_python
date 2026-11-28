extends SceneTree

## Tests sans écran de drawn_road.gd, la chaussée dessinée unique (lot CD1, version simple) : épingle (deux portions
## à 16 m d'axe à axe), demi-tour avant l'arrivée (amorce d'arrivée qui repasse près de l'aller), boucle sans amorce,
## polyligne ajoutée (branche de carrefour, reprise de #1056), instance commune par route, `nearest` et `segments_in`,
## et `is_clear` toujours d'accord avec `distance` (aucun changement visible pour les poseurs, CD1a).
## Lancement : godot --headless --path engine --script res://tests/unit/test_drawn_road.gd

const DrawnRoad := preload("res://scripts/drawn_road.gd")
const RoadClearance := preload("res://scripts/road_clearance.gd")
const VegetationPlacer := preload("res://scripts/vegetation_placer.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const RoadBuilder := preload("res://scripts/road_builder.gd")
const OsmStreamer := preload("res://scripts/osm_streamer.gd")
const TreeRenderer := preload("res://scripts/tree_renderer.gd")

var _failures := 0
var _checked := 0


func _init() -> void:
	_test_hairpin()
	_test_leads()
	_test_loop()
	_test_polyline()
	_test_shared()
	_test_is_clear_matches_distance()
	_test_segments_in()
	_test_vegetation_corridor()
	_test_buildings()
	_test_rivers()
	_test_trees_in_water()
	print("test_drawn_road : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route à partir de points (x, z) donnés par `fn(s)`, tous les `ds` mètres, ouverte ou en boucle.
func _route(fn: Callable, length: float, ds: float, loop := false) -> Variant:
	var n := (roundi(length / ds) if loop else int(floor(length / ds))) + 1
	var data := {"version": "1.0", "type": "loop" if loop else "open", "ds_m": ds, "n": n, "length_m": ds * (n - 1),
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		var p: Vector2 = fn.call(i * ds)
		var nxt: Vector2 = fn.call(i * ds + 0.5) - fn.call(maxf(i * ds - 0.5, 0.0))
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


## Épingle : vers le nord en x = 0 sur 300 m, demi-tour de rayon 8 m, retour vers le sud en x = 16.
static func _hairpin_point(s: float) -> Vector2:
	var arc := PI * 8.0
	if s <= 300.0:
		return Vector2(0.0, -s)
	if s <= 300.0 + arc:
		var a := PI * (1.0 - (s - 300.0) / arc)
		return Vector2(8.0 + 8.0 * cos(a), -300.0 - 8.0 * sin(a))
	return Vector2(16.0, -300.0 + (s - 300.0 - arc))


func _hairpin() -> Variant:
	return _route(_hairpin_point, 600.0 + PI * 8.0, 5.0)


## Demi-tour serré avant l'arrivée (Almería, 26/11) : l'amorce d'arrivée repasse à 10 m de l'aller.
static func _u_turn_point(s: float) -> Vector2:
	var arc := PI * 5.0
	if s <= 400.0:
		return Vector2(s, 0.0)
	if s <= 400.0 + arc:
		var a := (s - 400.0) / 5.0
		return Vector2(400.0 + 5.0 * sin(a), -5.0 + 5.0 * cos(a))
	return Vector2(400.0 - (s - 400.0 - arc), -10.0)


## Cercle de 100 m de rayon centré sur l'origine (boucle : pas d'amorce).
static func _circle_point(s: float) -> Vector2:
	var a := s / 100.0
	return Vector2(100.0 * sin(a), -100.0 * cos(a))


func _test_hairpin() -> void:
	var road := DrawnRoad.new(_hairpin())
	_check(absf(road.distance(0.0, -100.0)) < 1e-4, "épingle : sur l'axe, distance nulle")
	_check(absf(road.distance(8.0, -100.0) - 8.0) < 1e-3, "épingle : entre les deux portions, 8 m de chacune")
	_check(road.is_clear(-5.0, -100.0, 4.0) and not road.is_clear(13.0, -100.0, 4.0),
		"épingle : is_clear voit la portion d'en face (13 m de l'une, 3 m de l'autre)")
	var near: Dictionary = road.nearest(-5.0, -100.0)
	_check(not near.is_empty() and absf(float(near["s"]) - 100.0) < 0.5 and int(near["side"]) == -1,
		"épingle : point à l'ouest de la montée vers le nord : s ≈ 100 m, à gauche (%s)" % str(near))
	near = road.nearest(3.0, -100.0)
	_check(not near.is_empty() and int(near["side"]) == 1 and absf(float(near["d"]) - 3.0) < 1e-3,
		"épingle : 3 m à l'est de la montée : à droite (%s)" % str(near))
	_check(road.nearest(500.0, 500.0).is_empty(), "loin de tout : nearest vide")
	_check(DrawnRoad.new(null).is_clear(0.0, 0.0, 10.0) and DrawnRoad.new(null).is_empty(), "sans route : toujours dégagé")


func _test_leads() -> void:
	var route = _route(_u_turn_point, 420.0 + PI * 5.0, 2.0)
	var road := DrawnRoad.new(route)
	var after: Dictionary = RoadBuilder.axis_sample(route, route.length_m + 0.5 * RoadBuilder.LEAD_OUT_M)
	var before: Dictionary = RoadBuilder.axis_sample(route, -0.5 * RoadBuilder.LEAD_IN_M)
	_check(road.distance(float(after["x"]), float(after["z"])) < 0.01, "amorce d'arrivée dans la chaussée")
	_check(road.distance(float(before["x"]), float(before["z"])) < 0.01, "amorce de départ dans la chaussée")
	var near: Dictionary = road.nearest(float(before["x"]), float(before["z"]))
	_check(not near.is_empty() and float(near["s"]) < -40.0, "amorce de départ : abscisse négative (%s)" % str(near))


func _test_loop() -> void:
	var route = _route(_circle_point, 2.0 * PI * 100.0, 2.0 * PI * 100.0 / 120.0, true)
	var road := DrawnRoad.new(route)
	_check(not road.is_empty(), "boucle : chaussée construite")
	_check(road.distance(0.0, -100.0) < 0.05 and road.is_clear(0.0, 0.0, 25.0), "boucle : axe sur le cercle, centre dégagé")
	# Pas d'amorce : à 50 m dans le prolongement du départ (vers l'ouest), rien.
	_check(road.distance(-50.0, -100.0) > 10.0, "boucle : pas d'amorce au départ")


func _test_polyline() -> void:
	var road := DrawnRoad.new(_hairpin())
	_check(road.is_clear(100.0, -100.0, 5.0), "branche de carrefour : dégagé avant l'ajout")
	road.add_polyline(PackedVector2Array([Vector2(50.0, -100.0), Vector2(150.0, -100.0)]))
	_check(not road.is_clear(100.0, -101.0, 5.0) and absf(road.distance(100.0, -103.0) - 3.0) < 1e-3,
		"branche de carrefour : tenue dégagée après l'ajout")
	_check(is_nan(float(road.nearest(100.0, -101.0)["s"])), "branche de carrefour : pas d'abscisse de route")
	# Pas de segment fantôme entre la fin de la route et le début de la branche.
	_check(road.is_clear(33.0, -200.0, 5.0), "branche de carrefour : rien entre la route et la branche")


func _test_shared() -> void:
	var r1 = _hairpin()
	var a = DrawnRoad.shared(r1)
	var b = DrawnRoad.shared(r1)
	_check(a != null and a == b, "instance commune : la même pour une même route")
	var r2 = _hairpin()
	_check(DrawnRoad.shared(r2) != a, "route neuve : chaussée à elle")
	_check(DrawnRoad.shared(null) == null, "sans route : pas de chaussée commune")
	var rc := RoadClearance.new(r1)
	_check(rc.drawn == a, "road_clearance.gd passe par la chaussée commune")
	_check(RoadClearance.new(r1, 10.0).drawn != a, "road_clearance.gd : autre taille de case, chaussée à part")
	var r3 = _hairpin()
	DrawnRoad.shared(r3)
	var w: WeakRef = weakref(r3)
	r3 = null
	_check(w.get_ref() == null, "instance commune : la route n'est pas tenue en vie par la chaussée")


## Aucun changement pour les poseurs (CD1a) : is_clear(d) ⇔ distance ≥ d, sur des points tirés autour de l'épingle.
func _test_is_clear_matches_distance() -> void:
	var road := DrawnRoad.new(_hairpin())
	var rng := RandomNumberGenerator.new()
	rng.seed = 1128
	var bad := 0
	for i in range(3000):
		var x := rng.randf_range(-30.0, 46.0)
		var z := rng.randf_range(-340.0, 20.0)
		var d := rng.randf_range(0.5, 25.0)
		if road.is_clear(x, z, d) != (road.distance(x, z) >= d):
			bad += 1
	_check(bad == 0, "is_clear d'accord avec distance sur 3 000 points (%d désaccords)" % bad)


func _test_segments_in() -> void:
	var road := DrawnRoad.new(_hairpin())
	var segs := road.segments_in(Rect2(-2.0, -110.0, 4.0, 20.0))
	var ok := not segs.is_empty()
	for sg in segs:
		ok = ok and absf(sg.x) < 0.5 and absf(sg.z) < 0.5   # seule la montée en x = 0, pas le retour en x = 16
	_check(ok, "segments_in : les segments de la seule portion touchée (%d)" % segs.size())
	_check(road.segments_in(Rect2(500.0, 500.0, 10.0, 10.0)).is_empty(), "segments_in : vide loin de la route")
	_check(road.touches(Rect2(-2.0, -110.0, 4.0, 20.0)) and not road.touches(Rect2(4.0, -110.0, 8.0, 20.0)),
		"touches : vrai sur l'axe, faux entre les deux portions")


## CD1b : le couloir des arbres (vegetation_placer.gd) est celui de la chaussée commune, amorces comprises.
func _test_vegetation_corridor() -> void:
	var route = _route(_u_turn_point, 420.0 + PI * 5.0, 2.0)
	var tile := Rect2(0.0, -100.0, 500.0, 200.0)
	var buckets := VegetationPlacer._road_buckets(route, tile, 7.0)
	_check(buckets.get("road") == DrawnRoad.shared(route), "arbres : chaussée commune de la route")
	var after: Dictionary = RoadBuilder.axis_sample(route, route.length_m + 0.5 * RoadBuilder.LEAD_OUT_M)
	_check(VegetationPlacer._near_road(buckets, float(after["x"]), float(after["z"]) + 5.0, 7.0),
		"arbres : pas d'arbre à 5 m de l'amorce d'arrivée")
	_check(not VegetationPlacer._near_road(buckets, 200.0, 60.0, 7.0), "arbres : à 60 m de la route, permis")
	_check(VegetationPlacer._road_buckets(route, Rect2(5000.0, 5000.0, 1000.0, 1000.0), 7.0).is_empty(),
		"arbres : tuile loin de la route, aucun contrôle")


static func _box(cx: float, cz: float, half: float) -> Array:
	return [[cx - half, cz - half], [cx + half, cz - half], [cx + half, cz + half], [cx - half, cz + half]]


## CD1c : bâtiments sur la chaussée dessinée retirés, amorces comprises ; les autres gardés.
func _test_buildings() -> void:
	var route = _route(_u_turn_point, 420.0 + PI * 5.0, 2.0)
	var road = DrawnRoad.shared(route)
	var after: Dictionary = RoadBuilder.axis_sample(route, route.length_m + 0.5 * RoadBuilder.LEAD_OUT_M)
	var ax := float(after["x"])
	var az := float(after["z"])
	var items := [
		{"id": "sur_route", "outer": _box(200.0, 0.0, 4.0)},
		{"id": "sur_amorce", "outer": _box(ax, az, 3.0)},
		{"id": "facade_1m", "outer": _box(150.0, 4.0 + 1.0, 4.0)},      # mur à 1 m de l'axe
		{"id": "bord_5m", "outer": _box(250.0, 5.0 + 4.0, 4.0)},        # mur à 5 m de l'axe (côté sud, loin du retour)
		{"id": "loin", "outer": _box(200.0, 60.0, 5.0)},
	]
	var kept := OsmStreamer.drop_buildings_on_road(items, road)
	var ids := kept.map(func(b): return b["id"])
	_check(not ids.has("sur_route") and not ids.has("sur_amorce") and not ids.has("facade_1m"),
		"bâtiments : retirés sur la route, sur l'amorce d'arrivée et à 1 m de l'axe (%s)" % str(ids))
	_check(ids.has("bord_5m") and ids.has("loin"), "bâtiments : gardés à 5 m de l'axe et loin (%s)" % str(ids))
	_check(OsmStreamer.drop_buildings_on_road(items, null).size() == items.size(), "bâtiments : sans chaussée, tout gardé")


## CD1c : un cours d'eau est coupé sur toute la chaussée dessinée, amorce et autre portion de l'épingle comprises.
func _test_rivers() -> void:
	var route = _hairpin()
	var road = DrawnRoad.shared(route)
	# Ruisseau d'est en ouest à z = −150 : coupe la montée (x = 0) ET le retour (x = 16).
	var river := {"kind": "stream", "width_m": 1.0, "points": [[-60.0, -150.0], [-20.0, -150.0], [8.0, -150.0], [40.0, -150.0], [80.0, -150.0]]}
	var parts := OsmStreamer.cut_lines_at_drawn_road([river], road)
	var touching := 0
	for part in parts:
		for i in range(1, part["points"].size()):
			var a := Vector2(part["points"][i - 1][0], part["points"][i - 1][1])
			var b := Vector2(part["points"][i][0], part["points"][i][1])
			if a.x < 16.0 + 4.5 and b.x > -4.5:
				touching += 1
	_check(parts.size() == 2 and touching == 0, "cours d'eau : coupé aux deux portions de l'épingle (%d morceaux)" % parts.size())
	# Ruisseau qui croise l'amorce de départ (au sud du départ, vers z > 0).
	var before: Dictionary = RoadBuilder.axis_sample(route, -0.5 * RoadBuilder.LEAD_IN_M)
	var bz := float(before["z"])
	var lead_river := {"kind": "stream", "width_m": 1.0, "points": [[-60.0, bz], [-20.0, bz], [20.0, bz], [60.0, bz]]}
	_check(OsmStreamer.cut_lines_at_drawn_road([lead_river], road).size() == 2, "cours d'eau : coupé sur l'amorce de départ")
	var far := {"kind": "river", "width_m": 4.0, "points": [[-200.0, -100.0], [-200.0, -200.0]]}
	_check(OsmStreamer.cut_lines_at_drawn_road([far], road).size() == 1, "cours d'eau loin de la route : gardé entier")
	_check(OsmStreamer.cut_lines_at_drawn_road([river], null).size() == 1, "cours d'eau : sans chaussée, rien n'est coupé")


## CD1c (reprise de #1056) : aucun arbre dans un lac, arbres de l'île et du bord gardés.
func _test_trees_in_water() -> void:
	var lake := {"kind": "lake", "outer": _box(0.0, 0.0, 100.0), "holes": [_box(0.0, 0.0, 20.0)]}
	var trees := PackedVector4Array([Vector4(50.0, 0.0, 50.0, 1.0), Vector4(5.0, 0.0, 5.0, 1.0), Vector4(150.0, 0.0, 0.0, 1.0)])
	var kept := TreeRenderer.exclude_water(trees, [lake])
	_check(kept.size() == 2 and kept[0].x == 5.0 and kept[1].x == 150.0,
		"arbres : retiré dans le lac, gardés sur l'île et sur la rive (%d gardés)" % kept.size())
	_check(TreeRenderer.exclude_water(trees, []).size() == 3, "arbres : sans eau, tous gardés")
