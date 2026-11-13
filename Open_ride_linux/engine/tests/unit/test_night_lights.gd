extends SceneTree

## Tests unitaires sans écran des lumières de nuit (lot P35) : allumage selon le soleil (night_lights.gd),
## globaux des shaders, lampes du vélo, luminaires des villages (street_lights.gd) et éclairage du vélo du
## joueur (bike_lights.gd).
## Lancement : godot --headless --path engine --script res://tests/unit/test_night_lights.gd

const NightLights := preload("res://scripts/night_lights.gd")
const StreetLights := preload("res://scripts/street_lights.gd")
const BikeLights := preload("res://scripts/bike_lights.gd")
const AvatarView := preload("res://scripts/avatar_view.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")
const AvatarModel := preload("res://scripts/avatar_model.gd")
const MoonView := preload("res://scripts/moon_view.gd")
const Fireflies := preload("res://scripts/fireflies.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		print("[ÉCHEC] ", msg)


func _test_level() -> void:
	_check(NightLights.level({"active": false, "sun_elevation_deg": -30.0}) == 0.0, "jour et nuit coupé : rien d'allumé, même soleil couché")
	_check(NightLights.level({"active": true, "sun_elevation_deg": 30.0}) == 0.0, "plein jour : rien d'allumé")
	_check(NightLights.level({"active": true, "sun_elevation_deg": NightLights.ON_DEG}) == 0.0, "soleil à %.0f° : rien encore" % NightLights.ON_DEG)
	var dusk := NightLights.level({"active": true, "sun_elevation_deg": 0.0})
	_check(dusk > 0.0 and dusk < 1.0, "coucher : lumières qui montent (%.2f)" % dusk)
	_check(NightLights.level({"active": true, "sun_elevation_deg": -10.0}) == 1.0, "nuit : tout allumé")
	NightLights.apply(0.7, true)
	_check(is_equal_approx(NightLights.current, 0.7) and NightLights.enabled, "lumières allumées à 70 %")
	NightLights.apply(0.7, false)
	_check(NightLights.current == 0.0 and not NightLights.enabled, "jour et nuit coupé : tout éteint (image d'aujourd'hui)")
	_check("night_glow" in RenderingServer.global_shader_parameter_get_list()
			and "night_lamps" in RenderingServer.global_shader_parameter_get_list(), "globaux night_glow et night_lamps déclarés")


func _test_bike() -> void:
	var mesh := NightLights.bike_lamps_mesh()
	var arr := mesh.surface_get_arrays(0)
	var cols: PackedColorArray = arr[Mesh.ARRAY_COLOR]
	var lit := 0
	for c in cols:
		if c.a > 0.5:
			lit += 1
	_check(mesh.get_surface_count() == 1 and lit == 12, "phare et feu arrière : un maillage, deux faces de verre (%d sommets)" % lit)
	var av = AvatarView.new()
	root.add_child(av)
	NightLights.apply(0.0, false)
	av.configure(AvatarModel.DEFAULTS.duplicate(), 0)
	var lamps: Node3D = av.find_child("Lamps", true, false)
	_check(lamps != null and not lamps.visible, "avatar : lampes cachées quand le jour et la nuit est coupé")
	NightLights.apply(0.0, true)
	av.apply_pose(0.0, false)
	_check(lamps.visible, "avatar : lampes présentes dès que le jour et la nuit est actif")
	av.queue_free()
	var bl = BikeLights.new()
	root.add_child(bl)
	NightLights.apply(0.0, true)
	bl.place(Vector3(1, 2, 3), Vector3.ZERO)
	_check(not bl.visible, "vélo : projecteur éteint de jour (aucun coût)")
	NightLights.apply(1.0, true)
	bl.place(Vector3(1, 2, 3), Vector3.ZERO)
	_check(bl.visible and bl.spot.light_energy > 0.0 and not bl.spot.shadow_enabled and bl.position == Vector3(1, 2, 3),
			"vélo : projecteur allumé la nuit, sans ombre, posé sur le vélo")
	var fwd: Vector3 = -(bl.basis * bl.spot.basis).z
	_check(fwd.z < -0.9 and fwd.y < 0.0, "vélo : projecteur vers l'avant et un peu vers la route (%s)" % fwd)
	bl.queue_free()


## Route droite vers le nord (−z), 2 km.
func _straight():
	var d := {"version": "1.0", "ds_m": 10.0, "n": 201, "length_m": 2000.0, "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(201):
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(200.0)
		d["x"].append(0.0)
		d["z"].append(-10.0 * i)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(0.0)
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _house(x: float, z: float) -> Dictionary:
	var pts := PackedVector2Array([Vector2(x, z), Vector2(x + 8, z), Vector2(x + 8, z - 8), Vector2(x, z - 8)])
	var rect := Rect2(Vector2(x, z - 8), Vector2(8, 8))
	return {"points": pts, "rect": rect}


func _test_street() -> void:
	var route = _straight()
	var village := [_house(12.0, -300.0), _house(-15.0, -400.0), _house(12.0, -500.0)]
	var items := StreetLights.positions(route, 0, village)
	_check(not items.is_empty(), "village : des luminaires (%d)" % items.size())
	var inside := true
	var sides := {}
	for it in items:
		inside = inside and float(it["s"]) > 250.0 and float(it["s"]) < 560.0
		sides[int(it["side"])] = true
	_check(inside, "luminaires seulement près des maisons")
	_check(sides.has(1) and sides.has(-1), "luminaires des deux côtés, en alternance")
	_check(StreetLights.positions(route, 0, []).is_empty(), "rase campagne : aucun luminaire")
	_check(StreetLights.positions(route, 1, village).is_empty(), "tronçon suivant, sans maison : aucun luminaire")
	var sl = StreetLights.new()
	root.add_child(sl)
	sl.set_preset("medium")
	sl.add_chunk(route, 0, village)
	_check(sl.count() == items.size(), "un tronçon : un MultiMesh de %d luminaires" % sl.count())
	var xf: Transform3D = StreetLights.lamp_transform(items[0])
	var head: Vector3 = xf * Vector3(-StreetLights.ARM_M, StreetLights.POLE_H, 0.0)
	var foot: Vector3 = xf.origin
	_check(absf(head.x) < absf(foot.x), "crosse au-dessus de la chaussée (pied x=%.1f, tête x=%.1f)" % [foot.x, head.x])
	NightLights.apply(1.0, true)
	sl.update(Vector3(0, 202, -400), 0.0)
	var on := 0
	for c in sl.get_children():
		if c is SpotLight3D and c.visible:
			on += 1
	_check(on == StreetLights.LIGHTS_BY_PRESET["medium"], "medium : %d projecteurs sous les luminaires proches" % on)
	sl.set_preset("low")
	sl.update(Vector3(0, 202, -400), 1.0)
	var spots := 0
	for c in sl.get_children():
		if c is SpotLight3D and not c.is_queued_for_deletion():
			spots += 1
	_check(spots == 0, "low : luminaires dessinés, aucun projecteur")
	var posts := StreetLights.post_positions(route, 0, village)
	var in_village := false
	for it in posts:
		in_village = in_village or int(it["s"]) in [300, 400, 500]
	_check(posts.size() == 2 * 17 and not in_village, "balises des deux côtés, aucune près des maisons (%d)" % posts.size())
	_check(StreetLights.post_positions(route, 0, []).size() == 2 * 20, "rase campagne : balises tous les 50 m des deux côtés")
	_check(sl.post_count() == posts.size(), "balises du tronçon dessinées (%d)" % sl.post_count())
	sl.remove_chunk(0)
	_check(sl.count() == 0 and sl.post_count() == 0, "tronçon libéré : luminaires et balises retirés")
	sl.queue_free()


func _test_sky() -> void:
	var moon = MoonView.new()
	root.add_child(moon)
	moon.update(Vector3.ZERO, {})
	_check(not moon.visible, "lune cachée de jour et quand le jour et la nuit est coupé")
	moon.update(Vector3(10, 0, 0), {"active": true, "stars": 1.0, "moon_illumination": 0.6,
		"moon_direction": Vector3(0, 1, -1).normalized()})
	_check(moon.visible and moon.position.distance_to(Vector3(10, 0, 0) + Vector3(0, 1, -1).normalized() * MoonView.DIST_M) < 0.01,
		"lune la nuit, dans sa direction, loin devant le décor")
	moon.update(Vector3.ZERO, {"active": true, "stars": 1.0, "moon_illumination": 0.0, "moon_direction": Vector3.UP})
	_check(not moon.visible, "nouvelle lune : rien à voir")
	moon.queue_free()
	_check(Fireflies.wanted(1.0, "summer", 0.0, "temperate_forest"), "lucioles : nuit d'été en forêt")
	_check(not Fireflies.wanted(1.0, "winter", 0.0, "temperate_forest") and not Fireflies.wanted(1.0, "summer", 0.5, "wetland")
		and not Fireflies.wanted(0.2, "summer", 0.0, "wetland") and not Fireflies.wanted(1.0, "summer", 0.0, "sand_desert"),
		"pas de lucioles l'hiver, sous la pluie, au crépuscule ni au désert")


func _init() -> void:
	_test_level()
	_test_sky()
	_test_bike()
	_test_street()
	NightLights.apply(0.0, false)
	print("test_night_lights : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)
