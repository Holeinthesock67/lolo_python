extends SceneTree

## Détails de sol des biomes (lot U8, `ground_details.gd`) : rien sans modèle de biome, sortes par biome
## (rochers en montagne, herbes hautes et termitières en savane, rien en prairie), aucun objet à moins de
## 3 m du bord de la route sur un parcours de 5 km à épingle (deux branches à 30 m l'une de l'autre),
## budgets de `living(preset)` respectés et coupés avec le décor vivant, placement déterministe, teinte des
## rochers de la variante régionale, maillages construits par code.

const GroundDetails := preload("res://scripts/ground_details.gd")
const BiomeModel := preload("res://scripts/biome_model.gd")
const BiomeLayer := preload("res://scripts/biome_layer.gd")
const ThemeLoader := preload("res://scripts/theme_loader.gd")
const QualityPresets := preload("res://scripts/quality_presets.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

const ROAD_WIDTH_M := 6.0

var _failures := 0
var _checked := 0
var _theme: Dictionary


func _init() -> void:
	_theme = ThemeLoader.load_theme(ThemeLoader.DEFAULT_THEME_DIR)["theme"]
	_run()
	print("test_ground_details : %d vérifications, %d échecs" % [_checked, _failures])
	quit(1 if _failures > 0 else 0)


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Parcours de 5 km : 2 km plein sud en x = 0, demi-tour de 15 m de rayon, 2 km vers le nord en x = 30,
## puis 1 km en lacets. Points tous les 10 m.
func _route() -> Variant:
	var pts: Array[Vector2] = []
	var p := Vector2.ZERO
	pts.append(p)
	for i in range(200):
		p += Vector2(0.0, 10.0)
		pts.append(p)
	for i in range(1, 5):
		var a := PI * i / 4.0
		pts.append(Vector2(15.0 - 15.0 * cos(a), 2000.0 + 15.0 * sin(a)))
	p = pts[-1]
	for i in range(200):
		p += Vector2(0.0, -10.0)
		pts.append(p)
	for i in range(100):
		p += Vector2(10.0 * sin(i / 8.0), -10.0 * absf(cos(i / 8.0)) - 1.0).normalized() * 10.0
		pts.append(p)
	var d := {"version": "1.0", "ds_m": 10.0, "n": pts.size(), "length_m": 10.0 * (pts.size() - 1), "type": "open",
		"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(pts.size()):
		var q := pts[mini(i + 1, pts.size() - 1)] - pts[maxi(i - 1, 0)]
		d["lat"].append(45.0)
		d["lon"].append(6.0)
		d["alt_m"].append(500.0)
		d["x"].append(pts[i].x)
		d["z"].append(pts[i].y)
		d["grade_pct"].append(0.0)
		d["heading_deg"].append(fposmod(rad_to_deg(atan2(q.x, -q.y)), 360.0))
	var route = RouteDataScript.new()
	route.load_route_dict(d)
	return route


func _model(biome: String) -> Variant:
	var m := BiomeModel.new(_theme, BiomeLayer.new())
	if biome != "":
		m.set_forced(biome)
	return m


func _budgets(preset: String, enabled: bool = true) -> Dictionary:
	var l := QualityPresets.living(preset, enabled)
	return {"rock": l["ground_rocks"], "grass": l["ground_grass"], "termite": l["ground_termites"]}


## Parcourt le parcours jusqu'à `end_m` (tout par défaut, pas de 60 m) et renvoie les positions vues, sans doublon, par sorte.
func _sweep(g, route, end_m: float = INF) -> Dictionary:
	var out := {"rock": PackedVector3Array(), "grass": PackedVector3Array(), "termite": PackedVector3Array()}
	var seen := {"rock": {}, "grass": {}, "termite": {}}   # chaque objet une fois (il reste vu sur plusieurs pas)
	var s := 0.0
	while s <= minf(route.length_m, end_m):
		for i in range(200):
			g.update(s)
			if g.is_settled():
				break
		for kind in out:
			for p in g.get_positions(kind):
				seen[kind][p] = true
		s += GroundDetails.CHUNK_M
	for kind in out:
		out[kind] = PackedVector3Array(seen[kind].keys())
	return out


## Distance au plus proche segment de toute la route (force brute).
func _road_distance(route, p: Vector3) -> float:
	var best := INF
	var q := Vector2(p.x, p.z)
	for i in range(route.n - 1):
		var c := Geometry2D.get_closest_point_to_segment(q, Vector2(route.x[i], route.z[i]), Vector2(route.x[i + 1], route.z[i + 1]))
		best = minf(best, q.distance_to(c))
	return best


func _run() -> void:
	var route = _route()
	_check(route.length_m >= 5000.0, "parcours de %.1f km à épingle" % (route.length_m / 1000.0))

	# 1. Sans modèle de biome : rien n'est créé
	var g0 = GroundDetails.new()
	g0.configure(_budgets("high"), route, null, ROAD_WIDTH_M)
	_check(g0.get_child_count() == 0 and g0.get_capacity("rock") == 0, "sans modèle de biome : aucun détail (rendu d'avant la série U)")
	g0.free()

	# 2. Budgets de living(preset), coupés avec le décor vivant
	for preset in ["low", "medium", "high"]:
		var b := _budgets(preset)
		var g = GroundDetails.new()
		g.configure(b, route, _model("savanna"), ROAD_WIDTH_M)
		var ok: bool = g.get_capacity("rock") <= b["rock"] and g.get_capacity("grass") <= b["grass"] and g.get_capacity("termite") <= b["termite"]
		_check(ok and g.get_capacity("grass") > 0, "%s : capacités %d rochers, %d herbes, %d termitières dans les budgets %s" % [preset,
			g.get_capacity("rock"), g.get_capacity("grass"), g.get_capacity("termite"), str(b)])
		g.free()
	var b_off := _budgets("high", false)
	_check(b_off["rock"] == 0 and b_off["grass"] == 0 and b_off["termite"] == 0, "décor vivant coupé : budgets à zéro")

	# 3. Savane : herbes hautes et termitières, pas de rochers ; aucun objet à moins de 3 m du bord
	var gs = GroundDetails.new()
	gs.configure(_budgets("high"), route, _model("savanna"), ROAD_WIDTH_M, 7)
	var t0 := Time.get_ticks_usec()
	var sav := _sweep(gs, route)
	var sweep_ms := (Time.get_ticks_usec() - t0) / 1000.0
	_check(sav["grass"].size() > 0 and sav["termite"].size() > 0 and sav["rock"].size() == 0,
		"savane : %d herbes hautes, %d termitières, aucun rocher" % [sav["grass"].size(), sav["termite"].size()])
	var min_d := INF
	for kind in sav:
		for p in sav[kind]:
			min_d = minf(min_d, _road_distance(route, p))
	_check(min_d >= ROAD_WIDTH_M / 2.0 + GroundDetails.ROAD_CLEAR_M, "savane : objet le plus proche à %.2f m de l'axe (bord + 3 m = %.1f m), épingle comprise" % [min_d, ROAD_WIDTH_M / 2.0 + 3.0])
	var slots := 0
	for kind in ["rock", "grass", "termite"]:
		slots += gs.get_capacity(kind)
	var per_slot_us: float = sweep_ms * 1000.0 / (float(slots) / (GroundDetails.CHUNKS_BEHIND + GroundDetails.CHUNKS_AHEAD + 1) * route.length_m / GroundDetails.CHUNK_M)
	_check(per_slot_us * GroundDetails.MAX_PER_FRAME < 3000.0, "savane, high : %.1f µs par place, %.2f ms par image au plus (%d places par image ; borne du test 3 ms, conteneur lent)" % [per_slot_us,
		per_slot_us * GroundDetails.MAX_PER_FRAME / 1000.0, GroundDetails.MAX_PER_FRAME])

	# 4. Montagne : rochers seulement ; même règle de distance
	var ga = GroundDetails.new()
	ga.configure(_budgets("high"), route, _model("alpine"), ROAD_WIDTH_M, 7)
	# (2,3 km : première branche et épingle, pour tenir dans le délai du lanceur)
	var alp := _sweep(ga, route, 2300.0)
	min_d = INF
	for p in alp["rock"]:
		min_d = minf(min_d, _road_distance(route, p))
	_check(alp["rock"].size() > 0 and alp["grass"].size() == 0 and alp["termite"].size() == 0, "montagne : %d rochers, ni herbes ni termitières" % alp["rock"].size())
	_check(min_d >= ROAD_WIDTH_M / 2.0 + GroundDetails.ROAD_CLEAR_M, "montagne : rocher le plus proche à %.2f m de l'axe" % min_d)

	# 5. Prairie tempérée : aucun détail de sol
	var gp = GroundDetails.new()
	gp.configure(_budgets("high"), route, _model("temperate_grassland"), ROAD_WIDTH_M, 7)
	var pra := _sweep(gp, route, 1000.0)
	_check(pra["rock"].size() + pra["grass"].size() + pra["termite"].size() == 0, "prairie tempérée : aucun détail")

	# 6. Placement déterministe
	var ga2 = GroundDetails.new()
	ga2.configure(_budgets("high"), route, _model("alpine"), ROAD_WIDTH_M, 7)
	_check(_sweep(ga2, route, 2300.0)["rock"] == alp["rock"], "même graine : mêmes rochers")

	# 7. Teinte des rochers : variante régionale de la tuile, sinon roche du biome
	var layer := BiomeLayer.new()
	var g := PackedFloat32Array()
	g.resize(BiomeLayer.POINTS)
	g.fill(1.0)
	var names: Array[String] = ["alpine"]
	var grids: Array[PackedFloat32Array] = [g]
	layer.put_tile("near", 0, 0, {"biomes": names, "weights": grids, "variant": {"ground": "gres_rose", "roofs": null}})
	var th := _theme.duplicate(true)
	th["variants"] = {"gres_rose": {"rock_color": "#b56a5c"}}
	var gv = GroundDetails.new()
	gv.configure(_budgets("low"), route, BiomeModel.new(th, layer), ROAD_WIDTH_M)
	_check(gv.rock_color("alpine", 500.0, 500.0).is_equal_approx(Color.html("#b56a5c").darkened(0.12)), "rochers sur grès rose : teinte de la variante")
	var rock_alpine: Color = BiomeModel.new(_theme).params("alpine")["terrain"]["rock_color"]
	_check(gv.rock_color("alpine", 1500.0, 500.0).is_equal_approx(rock_alpine.darkened(0.12)), "hors de la tuile : roche du biome")

	# 8. Maillages construits par code
	for shape in range(GroundDetails.ROCK_SHAPES):
		var m := GroundDetails.build_rock_mesh(shape)
		var aabb := m.get_aabb()
		_check(m.get_faces().size() / 3 == 80 and aabb.size.y < aabb.size.x, "rocher %d : 80 faces, plus large que haut (%s)" % [shape, str(aabb.size)])
	var grass := GroundDetails.build_grass_mesh()
	_check(grass.get_aabb().size.y > 0.6 and grass.get_aabb().size.y <= GroundDetails.GRASS_HEIGHT_M + 0.01, "herbes hautes : %.2f m" % grass.get_aabb().size.y)
	_check(GroundDetails.build_termite_mesh().get_aabb().size.y >= 1.5, "termitière : %.2f m" % GroundDetails.build_termite_mesh().get_aabb().size.y)

	# Normales sortantes et faces avant de Godot (sinon rochers noirs, termitières invisibles)
	for pair in [["rocher", GroundDetails.build_rock_mesh(1)], ["termitière", GroundDetails.build_termite_mesh()]]:
		var arr: Array = (pair[1] as ArrayMesh).surface_get_arrays(0)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var nn: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
		var good := 0
		for i in range(0, v.size(), 3):
			var c := (v[i] + v[i + 1] + v[i + 2]) / 3.0
			# Cônes de la termitière : normale sortante toujours vers le haut ; rocher : opposée au centre
			var outward: bool = nn[i].y > 0.0 if pair[0] == "termitière" else nn[i].dot(c) > 0.0
			if outward and nn[i].dot((v[i + 1] - v[i]).cross(v[i + 2] - v[i])) < 0.0:
				good += 1
		_check(good == v.size() / 3, "%s : %d faces sur %d tournées vers l'extérieur" % [pair[0], good, v.size() / 3])

	for n in [gs, ga, gp, ga2, gv]:
		n.free()
