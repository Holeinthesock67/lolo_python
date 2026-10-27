extends SceneTree

## Tests sans écran du placement des animaux `fauna_placer.gd` (Lot P11).
## Lancement : godot --headless --path engine --script res://tests/unit/test_fauna_placer.gd

const FaunaPlacer := preload("res://scripts/fauna_placer.gd")
const FaunaBehaviour := preload("res://scripts/fauna_behaviour.gd")
const RouteDataScript := preload("res://scripts/route_data.gd")

var _failures := 0
var _checked := 0


func _check(cond: bool, msg: String) -> void:
	_checked += 1
	if cond:
		print("[OK] ", msg)
	else:
		_failures += 1
		printerr("[ÉCHEC] ", msg)


## Route droite le long de l'axe x, de 0 à 3 000 m (z = 0).
func _route():
	var n := 301
	var cols := {"lat": [], "lon": [], "alt_m": [], "x": [], "z": [], "grade_pct": [], "heading_deg": []}
	for i in range(n):
		cols["lat"].append(48.9)
		cols["lon"].append(7.1)
		cols["alt_m"].append(250.0)
		cols["x"].append(i * 10.0)
		cols["z"].append(0.0)
		cols["grade_pct"].append(0.0)
		cols["heading_deg"].append(90.0)
	var d := {"version": "1.0", "ds_m": 10.0, "n": n, "length_m": 3000.0, "type": "open"}
	d.merge(cols)
	var r = RouteDataScript.new()
	r.load_route_dict(d)
	return r


func _square(x0: float, z0: float, size: float) -> Array:
	return [[x0, z0], [x0 + size, z0], [x0 + size, z0 + size], [x0, z0 + size]]


func _wood(id: String, x0: float, z0: float, size: float) -> Dictionary:
	return {"id": id, "kind": "wood", "outer": _square(x0, z0, size), "holes": [], "density": 0.8}


func _flat(_x: float, _z: float) -> float:
	return 250.0


func _hill(x: float, z: float) -> float:
	return 250.0 + 0.2 * (x - 400.0) + 0.1 * z


func _steep(x: float, _z: float) -> float:
	return 250.0 + 0.5 * x


func _test_determinism_and_exclusions() -> void:
	var route = _route()
	var pois := [
		{"id": "n1", "kind": "livestock", "x": 500.0, "y": 250.0, "z": 6.0, "radius_m": 200.0},
		{"id": "n2", "kind": "livestock", "x": 800.0, "y": 250.0, "z": 25.0, "radius_m": 200.0},
		{"id": "n3", "kind": "church_bell", "x": 600.0, "y": 250.0, "z": 50.0, "radius_m": 300.0},
	]
	var woods := [_wood("w1", 100.0, 40.0, 300.0), _wood("w2", 600.0, -400.0, 250.0)]
	var ctx := {
		"height_at": Callable(self, "_flat"),
		"buildings": [{"id": "b1", "outer": _square(780.0, 15.0, 25.0)}],
		"water": {"areas": [{"id": "l1", "kind": "pond", "level_y": 249.0, "outer": _square(510.0, 15.0, 20.0)}],
			"lines": [{"id": "s1", "kind": "stream", "width_m": 3.0, "points": [[470.0, -40.0, 249.0], [470.0, 40.0, 249.0]]}]},
	}
	var density := {"birds": 1.0, "livestock": 1.0, "deer": 1.0}
	var a: Array = FaunaPlacer.place_chunk(0, woods, pois, route, density, ctx)
	var b: Array = FaunaPlacer.place_chunk(0, woods, pois, route, density, ctx)
	_check(str(a) == str(b) and not a.is_empty(), "placement déterministe : même tronçon, même résultat (%d groupes)" % a.size())

	var herds := 0
	var beasts := 0
	var min_axis := INF
	var in_forbidden := 0
	var herd_ok := true
	for g in a:
		if g["type"] == "herd":
			herds += 1
			var n: int = (g["members"] as Array).size()
			herd_ok = herd_ok and n >= 3 and n <= 12
			for m in g["members"]:
				var p: Vector3 = m["pos"]
				beasts += 1
				min_axis = minf(min_axis, absf(p.z))
				if (p.x >= 780.0 and p.x <= 805.0 and p.z >= 15.0 and p.z <= 40.0) \
						or (p.x >= 510.0 and p.x <= 530.0 and p.z >= 15.0 and p.z <= 35.0) \
						or absf(p.x - 470.0) < 1.5:
					in_forbidden += 1
		elif g["type"] == "deer":
			min_axis = minf(min_axis, absf((g["pos"] as Vector3).z))
	_check(herds == 2 and herd_ok, "deux points livestock : deux troupeaux de 3 à 12 bêtes (%d bêtes)" % beasts)
	_check(min_axis >= 4.0, "aucune bête à moins de 4 m de l'axe de la route (minimum %.1f m)" % min_axis)
	_check(in_forbidden == 0, "aucune bête dans l'eau, sur le ruisseau ou dans un bâtiment (%d)" % in_forbidden)
	var flocks := a.filter(func(g): return g["type"] == "birds")
	_check(flocks.size() == 2, "une bande d'oiseaux par forêt d'au moins 2 ha (%d)" % flocks.size())


func _test_birds_altitude() -> void:
	var woods := [_wood("w1", 0.0, 0.0, 400.0), _wood("w2", 500.0, 100.0, 300.0), _wood("w3", 900.0, -300.0, 160.0)]
	var groups: Array = FaunaPlacer.place_chunk(3, woods, [], null, {"birds": 1.0}, {"height_at": Callable(self, "_hill")})
	var beh = FaunaBehaviour.new()
	beh.setup(groups)
	var min_agl := INF
	var n_birds := 0
	for step in range(240):
		var t := step * 0.5
		beh.update(Vector3(200.0, 300.0, 200.0) if step > 100 else Vector3(-5000.0, 0.0, 0.0), t)
		for g in groups:
			if g["type"] != "birds":
				continue
			for i in range((g["members"] as Array).size()):
				var p := FaunaBehaviour.bird_position(g, i, t)
				min_agl = minf(min_agl, p.y - _hill(p.x, p.z))
				if step == 0:
					n_birds += 1
	_check(n_birds >= 15 and min_agl >= 15.0,
		"oiseaux sur une pente de 20 %% pendant 2 min : jamais sous 15 m du sol (minimum %.1f m, %d oiseaux)" % [min_agl, n_birds])
	var sizes_ok := true
	for g in groups:
		if g["type"] != "birds":
			continue
		var n: int = (g["members"] as Array).size()
		sizes_ok = sizes_ok and n >= 5 and n <= 15
	_check(sizes_ok, "bandes de 5 à 15 oiseaux")


func _test_absences_and_deer_spacing() -> void:
	var woods := [_wood("w1", 100.0, 40.0, 300.0)]
	var g0: Array = FaunaPlacer.place_chunk(0, woods, [{"id": "n3", "kind": "village", "x": 0.0, "y": 0.0, "z": 0.0, "radius_m": 100.0}],
		null, {"birds": 1.0, "livestock": 1.0, "deer": 1.0})
	_check(g0.filter(func(g): return g["type"] == "herd").is_empty(), "pas de point livestock : aucun bétail")
	var g1: Array = FaunaPlacer.place_chunk(0, woods, [], null, {"birds": 1.0, "deer": 0.0})
	_check(g1.filter(func(g): return g["type"] == "deer").is_empty(), "fauna.deer = 0 : aucun chevreuil")

	var deer_per_chunk := []
	for k in range(9):
		var ws := []
		for i in range(6):
			ws.append(_wood("k%d_w%d" % [k, i], k * 1000.0 + i * 150.0, 80.0, 120.0))
		var gs: Array = FaunaPlacer.place_chunk(k, ws, [], null, {"deer": 1.0})
		deer_per_chunk.append(gs.filter(func(g): return g["type"] == "deer").size())
	var spaced := true
	for k in range(9):
		spaced = spaced and (deer_per_chunk[k] == 0 or (k % 3 == 0 and deer_per_chunk[k] == 1))
	_check(spaced and deer_per_chunk[0] == 1, "au plus un chevreuil tous les 3 km (%s)" % str(deer_per_chunk))

	var steep: Array = FaunaPlacer.place_chunk(0, [], [{"id": "n9", "kind": "livestock", "x": 300.0, "y": 0.0, "z": 300.0, "radius_m": 100.0}],
		null, {"livestock": 1.0}, {"height_at": Callable(self, "_steep")})
	_check(steep.is_empty(), "pente de 50 % (> 25 %) : aucune bête")


func _init() -> void:
	_test_determinism_and_exclusions()
	_test_birds_altitude()
	_test_absences_and_deer_spacing()
	print("test_fauna_placer : %d vérifications, %d échecs" % [_checked, _failures])
	quit(0 if _failures == 0 else 1)
